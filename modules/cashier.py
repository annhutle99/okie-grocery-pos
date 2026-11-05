# modules/cashier.py
# Supermarket POS Cashier Module for SmartRetail Final Revision

from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from typing import Optional
from decimal import Decimal
from datetime import datetime
import os
import io
from PIL import ImageTk, Image

from db.connection import get_connection
from utils.receipt import generate_receipt, save_receipt
from utils.ui import FlatBtn, CardFrame, ClearableEntry
from utils.scanner import scan_barcode_camera
from utils.sound import beep_success, beep_error
from utils.gcash_server import start_gcash_server, create_payment_session, poll_payment_status
from modules.auth import SecurityManager

TAX_RATE = Decimal("0.12")   # 12% VAT


class CashierFrame(tk.Frame):
    def __init__(self, parent, controller=None, user_info=None, **kwargs):
        super().__init__(parent, bg="#f8fafc", **kwargs)
        self.controller = controller
        self.user_info = user_info or {"user_code": "CSH-101", "full_name": "Belda, Marinel B."}
        
        self.cart: dict[int, dict] = {}   # item_id -> cart_item dict
        self.active_pwd_id = None
        self.applied_voucher = None
        
        self._build_ui()
        start_gcash_server()

    def set_user_info(self, user_info: dict):
        self.user_info = user_info
        code = user_info.get("user_code", "CSH-101")
        name = user_info.get("full_name", "")
        shift_id = user_info.get("active_shift_id")
        time_in_str = datetime.now().strftime("%I:%M %p")
        
        if shift_id:
            try:
                conn = get_connection()
                cursor = conn.cursor(dictionary=True)
                cursor.execute("SELECT time_in FROM cashier_shifts WHERE shift_id = %s", (shift_id,))
                row = cursor.fetchone()
                conn.close()
                if row and row.get("time_in"):
                    time_in_str = row["time_in"].strftime("%I:%M %p")
            except Exception:
                pass
                
        self.lbl_cashier_info.config(text=f"Cashier: {code} {name}  |  Shift Time In: {time_in_str}")

    # ── UI Layout ──────────────────────────────────────────────────────────
    def _build_ui(self):
        # ─ Top Header Bar ─
        header = tk.Frame(self, bg="#0f172a", padx=20, pady=12)
        header.pack(fill="x")

        tk.Label(
            header,
            text="O!kie Grocery POS — Supermarket Checkout Terminal",
            font=("Helvetica", 16, "bold"),
            fg="#ffffff",
            bg="#0f172a"
        ).pack(side="left")

        self.lbl_cashier_info = tk.Label(
            header,
            text=f"Cashier: {self.user_info.get('user_code','CSH-101')} {self.user_info.get('full_name','')}",
            font=("Helvetica", 11, "bold"),
            fg="#38bdf8",
            bg="#0f172a"
        )
        self.lbl_cashier_info.pack(side="right")

        # ─ Main 2-Column Container ─
        main = tk.Frame(self, bg="#f8fafc", padx=20, pady=20)
        main.pack(fill="both", expand=True)
        main.columnconfigure(0, weight=3)
        main.columnconfigure(1, weight=2)
        main.rowconfigure(0, weight=1)

        # ─ LEFT COLUMN: Item Input & Cart Table ───────────────────────────
        left = CardFrame(main, bg="#ffffff", padx=16, pady=16)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))

        # Barcode & Qty Entry Row
        input_row = tk.Frame(left, bg="#ffffff")
        input_row.pack(fill="x", pady=(0, 12))

        tk.Label(input_row, text="Barcode / ID:", font=("Helvetica", 10, "bold"), fg="#334155", bg="#ffffff").pack(side="left", padx=(0, 4))
        self.bc_var = tk.StringVar()
        bc_entry = ClearableEntry(input_row, textvariable=self.bc_var, width=18)
        bc_entry.pack(side="left", padx=4)
        bc_entry.bind("<Return>", lambda e: self.scan_product())

        tk.Label(input_row, text="Qty:", font=("Helvetica", 10, "bold"), fg="#334155", bg="#ffffff").pack(side="left", padx=(10, 4))
        self.qty_input_var = tk.StringVar(value="1")
        qty_entry = tk.Entry(input_row, textvariable=self.qty_input_var, font=("Helvetica", 11), width=4, bg="#f1f5f9", fg="#0f172a", relief="flat")
        qty_entry.pack(side="left", padx=4, ipady=6)

        FlatBtn(input_row, text="Add Item", bg="#007aff", hover_bg="#0056b3", command=self.scan_product).pack(side="left", padx=6)
        FlatBtn(input_row, text="Camera Scan", bg="#0f172a", hover_bg="#1e293b", command=self._camera_scan).pack(side="left", padx=2)
        FlatBtn(input_row, text="Check Price", bg="#475569", hover_bg="#334155", command=self._open_price_check).pack(side="right")

        # Cart Table Container (fixes Treeview scrollbar packing overflow bug)
        tbl_container = tk.Frame(left, bg="#ffffff")
        tbl_container.pack(fill="both", expand=True, pady=(0, 10))

        cols = ("item_id", "Product Name", "Unit Price", "Qty", "Line Total", "Vatable")
        self.cart_tree = ttk.Treeview(tbl_container, columns=cols, show="headings", height=14)
        display_cols = {
            "item_id":      ("ID", 50, "center"),
            "Product Name": ("Product Name", 240, "w"),
            "Unit Price":   ("Unit Price", 100, "e"),
            "Qty":          ("Qty", 60, "center"),
            "Line Total":   ("Line Total", 110, "e"),
            "Vatable":      ("VAT", 50, "center"),
        }
        for col, (heading, width, align) in display_cols.items():
            self.cart_tree.heading(col, text=heading)
            self.cart_tree.column(col, width=width, anchor=align)

        vsb = ttk.Scrollbar(tbl_container, orient="vertical", command=self.cart_tree.yview)
        self.cart_tree.configure(yscrollcommand=vsb.set)
        
        self.cart_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # Cart Action Controls
        ctrl = tk.Frame(left, bg="#ffffff")
        ctrl.pack(fill="x", pady=4)

        FlatBtn(ctrl, text="Qty +1", bg="#34c759", hover_bg="#248a3d", command=self.increase_qty).pack(side="left", padx=3)
        FlatBtn(ctrl, text="Qty -1", bg="#ff9500", hover_bg="#c97500", command=self.decrease_qty).pack(side="left", padx=3)
        FlatBtn(ctrl, text="Void Item (Mgr)", bg="#ff3b30", hover_bg="#d70015", command=self.remove_item).pack(side="left", padx=3)
        FlatBtn(ctrl, text="Clear Bill", bg="#64748b", hover_bg="#475569", command=self.clear_cart).pack(side="right")

        # ─ RIGHT COLUMN: Discounts & Payment Panel ─────────────────────────
        right = CardFrame(main, bg="#ffffff", padx=16, pady=16)
        right.grid(row=0, column=1, sticky="nsew")

        tk.Label(right, text="Summary & Discounts", font=("Helvetica", 14, "bold"), fg="#0f172a", bg="#ffffff").pack(anchor="w", pady=(0, 10))

        # Financial Summary Cards
        summary_box = tk.Frame(right, bg="#f8fafc", padx=14, pady=12, highlightbackground="#e2e8f0", highlightthickness=1)
        summary_box.pack(fill="x")

        self.subtotal_var = tk.StringVar(value="PHP 0.00")
        self.discount_var = tk.StringVar(value="PHP 0.00")
        self.vat_var = tk.StringVar(value="PHP 0.00")
        self.total_var = tk.StringVar(value="PHP 0.00")

        for label, var, size, color in [
            ("Subtotal:", self.subtotal_var, 10, "#475569"),
            ("Discount Applied:", self.discount_var, 10, "#ff9500"),
            ("12% VAT Amount:", self.vat_var, 10, "#475569"),
            ("TOTAL DUE:", self.total_var, 18, "#34c759"),
        ]:
            row_f = tk.Frame(summary_box, bg="#f8fafc")
            row_f.pack(fill="x", pady=4)
            tk.Label(row_f, text=label, font=("Helvetica", size, "bold"), fg=color, bg="#f8fafc").pack(side="left")
            tk.Label(row_f, textvariable=var, font=("Helvetica", size, "bold"), fg=color, bg="#f8fafc").pack(side="right")

        # Discount Controls
        disc_frame = tk.LabelFrame(right, text=" Apply Discounts & Vouchers ", font=("Helvetica", 10, "bold"), fg="#007aff", bg="#ffffff", padx=10, pady=10)
        disc_frame.pack(fill="x", pady=14)

        # 5% PWD Button (Formatted for multi-line readability)
        FlatBtn(disc_frame, text="Apply 5% PWD / Senior Discount\n(Basic Commodities Only)", bg="#007aff", hover_bg="#0056b3", command=self._apply_pwd_discount).pack(fill="x", pady=4)

        # Voucher Entry (Re-aligned layout to avoid text clipping)
        v_box = tk.Frame(disc_frame, bg="#ffffff")
        v_box.pack(fill="x", pady=(6, 0))

        tk.Label(v_box, text="Voucher Code:", font=("Helvetica", 9, "bold"), fg="#334155", bg="#ffffff").pack(anchor="w", pady=(0, 2))

        v_row = tk.Frame(v_box, bg="#ffffff")
        v_row.pack(fill="x")

        self.voucher_var = tk.StringVar()
        self.voucher_entry = ClearableEntry(v_row, textvariable=self.voucher_var, width=14)
        self.voucher_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))

        FlatBtn(v_row, text="Apply Voucher", bg="#0f172a", hover_bg="#1e293b", padx=10, pady=6, command=self._apply_voucher).pack(side="right")

        # Payment Methods
        pay_frame = tk.LabelFrame(right, text=" Select Payment Method ", font=("Helvetica", 10, "bold"), fg="#0f172a", bg="#ffffff", padx=10, pady=10)
        pay_frame.pack(fill="x", pady=(0, 14))

        FlatBtn(pay_frame, text="CASH PAYMENT", bg="#34c759", hover_bg="#248a3d", pady=12, command=self._open_cash_modal).pack(fill="x", pady=4)
        FlatBtn(pay_frame, text="ONLINE / GCASH QR PAYMENT (DEMO)", bg="#005ce6", hover_bg="#0046b3", pady=12, command=self._open_gcash_modal).pack(fill="x", pady=4)

    # ── Barcode & Scanning Logic ───────────────────────────────────────────
    def _camera_scan(self):
        """Open camera scanner in background thread — Tkinter does NOT freeze."""
        # Prevent double-open
        if getattr(self, '_scanner_active', False):
            return
        self._scanner_active = True

        # Show user feedback that scanner is running
        self.lbl_cashier_info.config(text="[Camera Active — Scan barcode...] Press Q or ESC in camera window to cancel")

        def _on_scan_result(code: str | None):
            self._scanner_active = False
            # Restore cashier info label
            code_d = self.user_info.get('user_code', 'CSH-101')
            name_d = self.user_info.get('full_name', '')
            self.lbl_cashier_info.config(text=f"Cashier: {code_d} {name_d}")

            if code:
                self.bc_var.set(code)
                self.scan_product()

        scan_barcode_camera(parent_widget=self, on_result=_on_scan_result)

    def scan_product(self):
        query = self.bc_var.get().strip()
        if not query:
            return
        
        try:
            qty_add = int(self.qty_input_var.get().strip() or "1")
            if qty_add <= 0:
                qty_add = 1
        except ValueError:
            qty_add = 1

        self.bc_var.set("")
        self.qty_input_var.set("1")

        try:
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)

            cursor.execute("SELECT * FROM products WHERE (barcode = %s OR item_id = %s) AND is_active = 1", (query, query if query.isdigit() else -1))
            product = cursor.fetchone()
            conn.close()

            if not product:
                beep_error()   # error sound — product not found
                messagebox.showwarning("Not Found", f"No active product found for ID/Barcode: {query}")
                return

            self._add_product_to_cart(product, qty_add, show_feedback=False)

        except Exception as e:
            messagebox.showerror("Error", f"Scan error: {e}")

    def _add_product_to_cart(self, product: dict, qty_add: int = 1, show_feedback: bool = True):
        try:
            item_id = product["item_id"]
            current_cart_qty = self.cart[item_id]["quantity"] if item_id in self.cart else 0

            # Check if product has a B1T1 promo and single unit scan/add
            if qty_add == 1:
                try:
                    conn = get_connection()
                    cursor = conn.cursor(dictionary=True)
                    cursor.execute("SELECT promo_type FROM item_promotions WHERE item_id = %s AND is_active = 1", (item_id,))
                    promo_row = cursor.fetchone()
                    conn.close()
                    if promo_row and promo_row.get("promo_type") in ("b1t1_free", "b1g1_percent"):
                        qty_add = 2  # B1T1 Pair: 1 Paid + 1 Free/Discounted
                except Exception:
                    pass

            new_qty = current_cart_qty + qty_add

            if new_qty > product["stock_qty"]:
                messagebox.showwarning("Insufficient Stock", f"Only {product['stock_qty']} unit(s) available for '{product['item_name']}'.", parent=self)
                return

            self.cart[item_id] = {
                "item_id": item_id,
                "barcode": product["barcode"],
                "item_name": product["item_name"],
                "category": product["category"],
                "unit_price": Decimal(str(product["unit_price"])),
                "quantity": new_qty,
                "stock_qty": product["stock_qty"],
                "is_basic_commodity": product["is_basic_commodity"],
                "is_vatable": 0 if product["is_basic_commodity"] == 1 else 1,
            }

            self._refresh_cart_ui()
            beep_success()     # supermarket beep — item successfully added
            if show_feedback:
                messagebox.showinfo("Item Added", f"Added {product['item_name']} (Qty: {qty_add}) to checkout cart.", parent=self)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to add product: {e}", parent=self)

    def _open_price_check(self):
        PriceCheckModal(self, on_add_to_cart=self._add_product_to_cart)

    def _refresh_cart_ui(self):
        for row in self.cart_tree.get_children():
            self.cart_tree.delete(row)

        raw_subtotal = Decimal("0.00")
        total_discount = Decimal("0.00")
        vatable_sales = Decimal("0.00")
        vat_exempt_sales = Decimal("0.00")

        # Fetch active promotions for items in cart
        promo_map = {}
        if self.cart:
            try:
                conn = get_connection()
                cursor = conn.cursor(dictionary=True)
                item_ids = list(self.cart.keys())
                format_strings = ','.join(['%s'] * len(item_ids))
                cursor.execute(f"SELECT * FROM item_promotions WHERE item_id IN ({format_strings}) AND is_active = 1", tuple(item_ids))
                for r in cursor.fetchall():
                    promo_map[r["item_id"]] = r
                conn.close()
            except Exception:
                pass

        # Process Cart Items & Apply Discounts
        for item_id, item in self.cart.items():
            unit_price = item["unit_price"]
            qty = item["quantity"]
            raw_line_total = unit_price * Decimal(str(qty))
            line_promo_discount = Decimal("0.00")
            promo_tag = ""

            promo = promo_map.get(item_id)
            if promo:
                ptype = promo.get("promo_type")
                lbl = promo.get("promo_label") or "PROMO"

                if ptype == "b1t1_free":
                    pairs = qty // 2
                    free_qty = pairs
                    if free_qty > 0:
                        line_promo_discount = Decimal(str(free_qty)) * unit_price
                        promo_tag = f"[{lbl} - {free_qty} FREE]"
                    else:
                        promo_tag = f"[{lbl}]"

                elif ptype == "b1g1_percent":
                    pairs = qty // 2
                    if pairs > 0:
                        disc_pct = Decimal(str(promo.get("second_item_discount_percent", 50.0))) / Decimal("100")
                        line_promo_discount = (Decimal(str(pairs)) * unit_price * disc_pct).quantize(Decimal("0.01"))
                        promo_tag = f"[{lbl} - {pairs} Pair(s)]"
                    else:
                        promo_tag = f"[{lbl}]"

                elif ptype == "bundle":
                    min_q = promo.get("min_qty", 2)
                    if qty >= min_q:
                        pct = Decimal(str(promo.get("discount_percent", 0.0))) / Decimal("100")
                        amt = Decimal(str(promo.get("discount_amount", 0.0)))
                        if pct > 0:
                            line_promo_discount = (raw_line_total * pct).quantize(Decimal("0.01"))
                        elif amt > 0:
                            line_promo_discount = min(raw_line_total, amt * Decimal(str(qty)))
                        promo_tag = f"[{lbl}]"
                    else:
                        promo_tag = f"[Buy {min_q}+ for Bundle]"

                elif ptype == "discount":
                    pct = Decimal(str(promo.get("discount_percent", 0.0))) / Decimal("100")
                    amt = Decimal(str(promo.get("discount_amount", 0.0)))
                    if pct > 0:
                        line_promo_discount = (raw_line_total * pct).quantize(Decimal("0.01"))
                    elif amt > 0:
                        line_promo_discount = min(raw_line_total, amt * Decimal(str(qty)))
                    promo_tag = f"[{lbl}]"

            item["line_promo_discount"] = line_promo_discount
            item["promo_tag"] = promo_tag
            net_line_total = max(Decimal("0.00"), raw_line_total - line_promo_discount)
            item["line_total"] = net_line_total
            item["raw_line_total"] = raw_line_total

            total_discount += line_promo_discount
            raw_subtotal += raw_line_total

            # Check PWD 5% Basic Commodities Discount
            if self.active_pwd_id and item["is_basic_commodity"] == 1:
                pwd_discount_item = (net_line_total * Decimal("0.05")).quantize(Decimal("0.01"))
                total_discount += pwd_discount_item
                vat_exempt_sales += (net_line_total - pwd_discount_item)
            else:
                vatable_sales += net_line_total

            display_name = item["item_name"]
            if promo_tag:
                display_name += f" {promo_tag}"

            self.cart_tree.insert("", "end", iid=str(item_id), values=(
                item_id, display_name, f"PHP {unit_price:.2f}", qty, f"PHP {net_line_total:.2f}",
                "YES" if item["is_basic_commodity"] == 1 else "NO"
            ))

        # If cart is empty, reset active discounts automatically
        if not self.cart:
            self.applied_voucher = None
            self.active_pwd_id = None
            self.subtotal_var.set("PHP 0.00")
            self.discount_var.set("PHP 0.00")
            self.vat_var.set("PHP 0.00")
            self.total_var.set("PHP 0.00")
            return

        # Apply Voucher if active
        if self.applied_voucher:
            v_val = Decimal(str(self.applied_voucher["discount_value"]))
            if self.applied_voucher["discount_type"] == "percent":
                v_disc = (raw_subtotal * (v_val / Decimal("100"))).quantize(Decimal("0.01"))
            else:
                # Capped to maximum available subtotal
                v_disc = min(v_val, raw_subtotal)
            total_discount += v_disc

        final_total = max(Decimal("0.00"), raw_subtotal - total_discount)

        # 12% VAT Portion Calculation
        vat_amount = (vatable_sales * Decimal("0.12") / Decimal("1.12")).quantize(Decimal("0.01"))

        self.subtotal_var.set(f"PHP {raw_subtotal:,.2f}")
        self.discount_var.set(f"PHP {total_discount:,.2f}")
        self.vat_var.set(f"PHP {vat_amount:,.2f}")
        self.total_var.set(f"PHP {final_total:,.2f}")

    def _get_selected_cart_id(self) -> Optional[int]:
        sel = self.cart_tree.selection()
        if not sel:
            messagebox.showwarning("No Selection", "Please select a cart item first.", parent=self)
            return None
        return int(self.cart_tree.item(sel[0])["values"][0])

    def increase_qty(self):
        iid = self._get_selected_cart_id()
        if iid is None:
            return
        item = self.cart[iid]

        step = 1
        try:
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT promo_type FROM item_promotions WHERE item_id = %s AND is_active = 1", (iid,))
            promo_row = cursor.fetchone()
            conn.close()
            if promo_row and promo_row.get("promo_type") in ("b1t1_free", "b1g1_percent"):
                step = 2
        except Exception:
            pass

        if item["quantity"] + step > item["stock_qty"]:
            if step > 1 and item["quantity"] + 1 <= item["stock_qty"]:
                item["quantity"] += 1
            else:
                messagebox.showwarning("Insufficient Stock", f"Maximum available: {item['stock_qty']} units.")
                return
        else:
            item["quantity"] += step
        self._refresh_cart_ui()

    def decrease_qty(self):
        iid = self._get_selected_cart_id()
        if iid is None:
            return
        item = self.cart[iid]

        step = 1
        try:
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT promo_type FROM item_promotions WHERE item_id = %s AND is_active = 1", (iid,))
            promo_row = cursor.fetchone()
            conn.close()
            if promo_row and promo_row.get("promo_type") in ("b1t1_free", "b1g1_percent"):
                step = 2
        except Exception:
            pass

        if item["quantity"] <= step:
            self.remove_item()
        else:
            item["quantity"] -= step
            self._refresh_cart_ui()

    def remove_item(self):
        iid = self._get_selected_cart_id()
        if iid is None:
            return

        # Requires Manager Verification to Void an Item from Cart
        if not SecurityManager.prompt_manager_approval(self, title="Manager Password Required to Void Item"):
            return

        del self.cart[iid]
        self._refresh_cart_ui()
        messagebox.showinfo("Item Voided", "Item successfully voided from bill by Manager.", parent=self)

    def clear_cart(self, force: bool = False):
        if not force and self.cart and not messagebox.askyesno("Clear Bill", "Clear all items from current checkout?", parent=self):
            return
        self.cart.clear()
        self.active_pwd_id = None
        self.applied_voucher = None
        self.voucher_var.set("")
        self.bc_var.set("")
        self.qty_input_var.set("1")
        self._refresh_cart_ui()

    def reset_session(self):
        """Force clear all cart items, discounts, and input fields on logout/shift change."""
        self.clear_cart(force=True)

    # ── Discounts & Voucher Handlers ──────────────────────────────────────
    def _apply_pwd_discount(self):
        if not self.cart:
            messagebox.showwarning("Empty Cart", "Add items to cart before applying discount.", parent=self)
            return

        pwd_id = simpledialog.askstring("5% PWD / Senior Discount", "Enter PWD / Senior Citizen ID Number:", parent=self)
        if pwd_id is None:
            # User clicked Cancel
            return

        pwd_id_clean = pwd_id.strip()
        if not pwd_id_clean:
            messagebox.showwarning("Input Required", "PWD / Senior Citizen ID Number cannot be empty. Discount not applied.", parent=self)
            return

        self.active_pwd_id = pwd_id_clean
        messagebox.showinfo("Discount Applied", f"5% PWD Discount applied to Basic Commodities.\nLogged PWD ID: {self.active_pwd_id}", parent=self)
        self._refresh_cart_ui()

    def _apply_voucher(self):
        from datetime import date

        if not self.cart:
            messagebox.showwarning("Empty Cart", "Cannot apply voucher to an empty cart. Please add items to cart first.", parent=self)
            return

        v_code = self.voucher_var.get().strip().upper()
        if not v_code:
            messagebox.showwarning("Input Required", "Please enter a voucher code.", parent=self)
            return

        try:
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM vouchers WHERE voucher_code = %s", (v_code,))
            voucher = cursor.fetchone()
            conn.close()

            if not voucher:
                messagebox.showerror("Invalid Voucher", "Voucher code does not exist.", parent=self)
                return

            if voucher.get("is_redeemed"):
                messagebox.showerror("Invalid Voucher", "This voucher code has already been redeemed.", parent=self)
                return

            if voucher.get("expiry_date") and voucher["expiry_date"] < date.today():
                exp_str = voucher["expiry_date"].strftime("%Y-%m-%d")
                messagebox.showerror("Expired Voucher", f"Voucher '{v_code}' expired on {exp_str}.", parent=self)
                return

            self.applied_voucher = voucher
            messagebox.showinfo("Voucher Applied", f"Voucher '{v_code}' applied successfully!", parent=self)
            self._refresh_cart_ui()
        except Exception as e:
            messagebox.showerror("Error", f"Voucher verification error: {e}", parent=self)

    # ── Payment Modals & Sale Completion ──────────────────────────────────
    def _open_cash_modal(self):
        if not self.cart:
            messagebox.showwarning("Empty Cart", "Cart is empty.", parent=self)
            return

        final_total = Decimal(self.total_var.get().replace("PHP ", "").replace(",", ""))

        win = tk.Toplevel(self)
        win.title("Cash Payment")
        win.geometry("400x350")
        win.configure(bg="#ffffff")
        win.transient(self)
        win.grab_set()

        tk.Label(win, text="CASH PAYMENT", font=("Helvetica", 14, "bold"), fg="#0f172a", bg="#ffffff").pack(pady=(20, 10))
        tk.Label(win, text=f"Total Due: PHP {final_total:,.2f}", font=("Helvetica", 16, "bold"), fg="#16a34a", bg="#ffffff").pack(pady=4)

        tk.Label(win, text="Cash Received (PHP):", font=("Helvetica", 10, "bold"), fg="#334155", bg="#ffffff").pack(anchor="w", padx=40, pady=(16, 2))
        cash_var = tk.StringVar()
        cash_entry = tk.Entry(win, textvariable=cash_var, font=("Helvetica", 14, "bold"), width=16, bg="#f1f5f9", relief="flat")
        cash_entry.pack(ipady=6)
        cash_entry.focus()

        change_lbl = tk.Label(win, text="Change: PHP 0.00", font=("Helvetica", 12, "bold"), fg="#2563eb", bg="#ffffff")
        change_lbl.pack(pady=10)

        def calc_change(*args):
            try:
                c_val = Decimal(cash_var.get().strip() or "0")
                chg = c_val - final_total
                change_lbl.config(text=f"Change: PHP {max(Decimal('0.00'), chg):,.2f}")
            except Exception:
                change_lbl.config(text="Change: ---")

        cash_var.trace_add("write", calc_change)

        FlatBtn(win, text="COMPLETE CASH SALE", bg="#16a34a", hover_bg="#15803d", pady=12, command=lambda: self._execute_checkout("cash", cash_var.get(), win)).pack(fill="x", padx=40, pady=16)

    def _open_gcash_modal(self):
        if not self.cart:
            messagebox.showwarning("Empty Cart", "Cart is empty.", parent=self)
            return

        final_total = float(Decimal(self.total_var.get().replace("PHP ", "").replace(",", "")))
        temp_sale_id = f"TXN-{int(datetime.now().timestamp())}"

        pay_url, qr_img, local_ip = create_payment_session(temp_sale_id, final_total, "O!KIE GROCERY CORPORATION")

        win = tk.Toplevel(self)
        win.title("Online GCash QR Payment")
        win.geometry("460x560")
        win.configure(bg="#005ce6")
        win.transient(self)
        win.grab_set()

        tk.Label(win, text="GCash QR Payment", font=("Helvetica", 16, "bold"), fg="#ffffff", bg="#005ce6").pack(pady=(16, 4))
        tk.Label(win, text=f"Scan QR code with your Phone Camera\nURL: {pay_url}", font=("Helvetica", 9), fg="#e2e8f0", bg="#005ce6").pack()

        # Display QR Code Image
        buffer = io.BytesIO()
        qr_img.save(buffer, format="PNG")
        buffer.seek(0)
        pil_qr = Image.open(buffer)
        tk_qr = ImageTk.PhotoImage(pil_qr)

        qr_label = tk.Label(win, image=tk_qr, bg="#ffffff", padx=12, pady=12)
        qr_label.image = tk_qr
        qr_label.pack(pady=16)

        status_lbl = tk.Label(win, text="Waiting for customer to scan and pay on phone...", font=("Helvetica", 11, "bold"), fg="#ffffff", bg="#005ce6")
        status_lbl.pack(pady=8)

        # Real-Time Payment Polling Loop
        is_active = [True]

        def poll_loop():
            if not is_active[0]:
                return
            st = poll_payment_status(temp_sale_id)
            if st.get("status") == "PAID":
                is_active[0] = False
                status_lbl.config(text="PAYMENT CONFIRMED ON PHONE!", fg="#4ade80")
                win.after(800, lambda: self._execute_checkout("gcash", str(final_total), win, payment_ref=st.get("payment_ref")))
            else:
                win.after(1000, poll_loop)

        win.after(1000, poll_loop)

        def on_close():
            is_active[0] = False
            win.destroy()

        win.protocol("WM_DELETE_WINDOW", on_close)

    def _execute_checkout(self, payment_method: str, cash_str: str, modal_win=None, payment_ref=None):
        try:
            final_total = Decimal(self.total_var.get().replace("PHP ", "").replace(",", ""))
            subtotal = Decimal(self.subtotal_var.get().replace("PHP ", "").replace(",", ""))
            discount = Decimal(self.discount_var.get().replace("PHP ", "").replace(",", ""))
            vat_amount = Decimal(self.vat_var.get().replace("PHP ", "").replace(",", ""))

            cash_received = Decimal(cash_str.strip() or "0") if payment_method == "cash" else final_total
            change_amount = max(Decimal("0.00"), cash_received - final_total)

            if payment_method == "cash" and cash_received < final_total:
                messagebox.showwarning("Insufficient Cash", f"Cash received (PHP {cash_received:,.2f}) is less than total (PHP {final_total:,.2f}).", parent=modal_win)
                return

            si_number = f"SI-{int(datetime.now().timestamp()):0>10}"

            # Execute Atomic MySQL Transaction
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)
            conn.start_transaction()

            # Create Sale Record
            cursor.execute("""
                INSERT INTO sales
                (si_number, shift_id, cashier_code, cashier_name, subtotal, vatable_sales, vat_exempt_sales, tax_amount, discount_type, discount_amount, pwd_id_number, voucher_code, total_amount, payment_method, payment_reference, cash_received, change_amount)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                si_number,
                self.user_info.get("active_shift_id"),
                self.user_info.get("user_code", "CSH-101"), self.user_info.get("full_name", "Cashier"),
                float(subtotal), float(subtotal - discount), 0.00, float(vat_amount),
                "pwd" if self.active_pwd_id else ("voucher" if self.applied_voucher else "none"),
                float(discount), self.active_pwd_id, self.applied_voucher["voucher_code"] if self.applied_voucher else None,
                float(final_total), payment_method, payment_ref, float(cash_received), float(change_amount)
            ))
            sale_id = cursor.lastrowid

            # Save Sale Items & Deduct Stock
            for item_id, item in self.cart.items():
                line_total = item.get("line_total", item["unit_price"] * item["quantity"])
                promo_disc = item.get("line_promo_discount", Decimal("0.00"))
                promo_tag = item.get("promo_tag", "")
                is_vatable_val = 0 if item.get("is_basic_commodity") == 1 else 1
                cursor.execute("""
                    INSERT INTO sale_items (sale_id, item_id, item_name, barcode, unit_price, quantity, line_total, line_promo_discount, promo_tag, is_vatable)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (sale_id, item_id, item["item_name"], item["barcode"], float(item["unit_price"]), item["quantity"], float(line_total), float(promo_disc), promo_tag, is_vatable_val))

                cursor.execute("UPDATE products SET stock_qty = stock_qty - %s WHERE item_id = %s", (item["quantity"], item_id))
                cursor.execute("INSERT INTO inventory_movements (item_id, movement_type, quantity, notes, reference_id) VALUES (%s, 'sale', %s, %s, %s)", (item_id, item["quantity"], f"Sale SI #{si_number}", sale_id))

            # Mark voucher as redeemed if used
            if self.applied_voucher:
                cursor.execute("UPDATE vouchers SET is_redeemed = 1, redeemed_at = NOW(), redeemed_by_sale_id = %s WHERE voucher_id = %s", (sale_id, self.applied_voucher["voucher_id"]))

            conn.commit()
            conn.close()

            # Build Robinsons Sales Invoice receipt
            sale_dict = {
                "sale_id": sale_id,
                "si_number": si_number,
                "cashier_code": self.user_info.get("user_code", "CSH-101"),
                "cashier_name": self.user_info.get("full_name", "Cashier"),
                "subtotal": subtotal,
                "total_amount": final_total,
                "vatable_sales": subtotal - discount,
                "vat_exempt_sales": Decimal("0.00"),
                "tax_amount": vat_amount,
                "payment_method": payment_method,
                "cash_received": cash_received,
                "change_amount": change_amount,
                "sale_date": datetime.now()
            }
            items_list = list(self.cart.values())
            receipt_text = generate_receipt(sale_dict, items_list)
            save_receipt(receipt_text, si_number)

            if modal_win:
                modal_win.destroy()

            # Open Receipt Preview Dialog
            ReceiptDialog(self, receipt_text, si_number, on_close=lambda: self.clear_cart(force=True))

        except Exception as e:
            messagebox.showerror("Checkout Error", f"Transaction rolled back: {e}")


# ── Receipt Dialog ─────────────────────────────────────────────────────────────
class ReceiptDialog(tk.Toplevel):
    def __init__(self, parent, receipt_text: str, si_number: str, on_close=None):
        super().__init__(parent)
        self.on_close = on_close
        self.title("Sales Invoice Receipt — O!kie Grocery")
        self.configure(bg="#ffffff")
        self.geometry("390x700")
        self.transient(parent)
        self.grab_set()

        # Intercept window manager close (X button) to guarantee clear_cart is executed
        self.protocol("WM_DELETE_WINDOW", self._finish)

        # Render Logo Thumbnail
        logo_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "images", "logo.png")
        if os.path.exists(logo_path):
            try:
                from PIL import Image, ImageTk
                r_img = Image.open(logo_path).resize((48, 48), Image.Resampling.LANCZOS)
                self.r_logo_tk = ImageTk.PhotoImage(r_img)
                lbl_r_logo = tk.Label(self, image=self.r_logo_tk, bg="#ffffff")
                lbl_r_logo.pack(pady=(12, 0))
            except Exception:
                pass

        tk.Label(self, text="Sales Invoice Created", font=("Helvetica", 14, "bold"), fg="#16a34a", bg="#ffffff").pack(pady=(4, 2))
        tk.Label(self, text=f"SI Number: {si_number}", font=("Helvetica", 9), fg="#64748b", bg="#ffffff").pack()

        # Action Button anchored at bottom
        FlatBtn(self, text="CLOSE & PROCEED TO NEXT CUSTOMER", bg="#c8102e", hover_bg="#a00c24", pady=12, command=self._finish).pack(side="bottom", fill="x", padx=16, pady=16)

        # Receipt Container Frame with Scrollbar & Monospace Paper Layout
        receipt_frame = tk.Frame(self, bg="#ffffff", highlightthickness=1, highlightbackground="#cbd5e1")
        receipt_frame.pack(side="top", fill="both", expand=True, padx=20, pady=(4, 10))

        scrollbar = tk.Scrollbar(receipt_frame, orient="vertical")
        text_widget = tk.Text(
            receipt_frame,
            font=("Courier", 10),
            bg="#ffffff",
            fg="#0f172a",
            width=44,
            height=26,
            relief="flat",
            padx=14,
            pady=12,
            wrap="none",
            yscrollcommand=scrollbar.set
        )
        scrollbar.config(command=text_widget.yview)

        scrollbar.pack(side="right", fill="y")
        text_widget.pack(side="left", fill="both", expand=True)

        text_widget.insert("1.0", receipt_text)
        text_widget.yview_moveto(0.0)
        text_widget.configure(state="disabled")

    def _finish(self):
        if self.on_close:
            try:
                self.on_close()
            except Exception:
                pass
        self.destroy()


# ── Interactive Price Checker Modal ───────────────────────────────────────────
class PriceCheckModal(tk.Toplevel):
    """
    Interactive Price Check Modal with Camera Barcode Scanning & Product Card.
    """

    def __init__(self, parent, on_add_to_cart=None):
        super().__init__(parent)
        self.parent = parent
        self.on_add_to_cart = on_add_to_cart
        self.title("Price Checker — O!kie Grocery")
        self.geometry("560x580")
        self.configure(bg="#f8fafc")
        self.transient(parent)
        self.grab_set()

        self._current_product = None
        self._build_ui()

    def _build_ui(self):
        # Header
        hdr = tk.Frame(self, bg="#0f172a", padx=20, pady=16)
        hdr.pack(fill="x")

        tk.Label(hdr, text="Price Checker & Product Scanner", font=("Helvetica", 16, "bold"), fg="#ffffff", bg="#0f172a").pack(anchor="w")
        tk.Label(hdr, text="Scan item barcode via camera/scanner or type barcode / ID", font=("Helvetica", 10), fg="#94a3b8", bg="#0f172a").pack(anchor="w", pady=(2, 0))

        # Search Card
        search_card = CardFrame(self, bg="#ffffff", padx=14, pady=14)
        search_card.pack(fill="x", padx=16, pady=16)

        tk.Label(search_card, text="Scan or Enter Barcode / Item ID:", font=("Helvetica", 10, "bold"), fg="#334155", bg="#ffffff").pack(anchor="w", pady=(0, 6))

        s_row = tk.Frame(search_card, bg="#ffffff")
        s_row.pack(fill="x")

        self.query_var = tk.StringVar()
        self.entry = ClearableEntry(s_row, textvariable=self.query_var, width=20)
        self.entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.entry.bind("<Return>", lambda e: self._do_search())

        FlatBtn(s_row, text="Check Price", bg="#007aff", hover_bg="#0056b3", padx=12, pady=6, command=self._do_search).pack(side="left", padx=3)
        FlatBtn(s_row, text="Camera Scan", bg="#0f172a", hover_bg="#1e293b", padx=12, pady=6, command=self._camera_scan).pack(side="left", padx=3)

        # Result Container
        self.result_frame = CardFrame(self, bg="#ffffff", padx=20, pady=20)
        self.result_frame.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        self._show_initial_state()
        self.entry.focus()

    def _show_initial_state(self):
        for w in self.result_frame.winfo_children():
            w.destroy()

        center_f = tk.Frame(self.result_frame, bg="#ffffff")
        center_f.place(relx=0.5, rely=0.5, anchor="center")

        c = tk.Canvas(center_f, width=64, height=64, bg="#ffffff", highlightthickness=0, bd=0)
        c.pack(pady=(0, 12))
        c.create_rectangle(8, 8, 56, 56, fill="#f1f5f9", outline="#cbd5e1", width=2)
        c.create_line(16, 20, 48, 20, fill="#0f172a", width=2)
        c.create_line(16, 28, 48, 28, fill="#007aff", width=2)
        c.create_line(16, 36, 36, 36, fill="#0f172a", width=2)

        tk.Label(center_f, text="Ready to Check Price", font=("Helvetica", 14, "bold"), fg="#334155", bg="#ffffff").pack()
        tk.Label(center_f, text="Use camera scan, physical scanner, or enter Item ID above.", font=("Helvetica", 10), fg="#94a3b8", bg="#ffffff").pack(pady=(4, 0))

    def _camera_scan(self):
        try:
            scanned = scan_barcode_camera(parent_widget=self)
            if scanned:
                self.query_var.set(scanned)
                self._do_search()
        except Exception as e:
            messagebox.showerror("Camera Error", f"Failed to open camera scanner: {e}", parent=self)

    def _do_search(self):
        query = self.query_var.get().strip()
        if not query:
            return

        try:
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM products WHERE (barcode = %s OR item_id = %s) AND is_active = 1", (query, query if query.isdigit() else -1))
            product = cursor.fetchone()
            conn.close()

            for w in self.result_frame.winfo_children():
                w.destroy()

            if not product:
                nf_frame = tk.Frame(self.result_frame, bg="#ffffff")
                nf_frame.place(relx=0.5, rely=0.5, anchor="center")

                tk.Label(nf_frame, text="Product Not Found", font=("Helvetica", 14, "bold"), fg="#ef4444", bg="#ffffff").pack()
                tk.Label(nf_frame, text=f"No active item matches Barcode / ID '{query}'.", font=("Helvetica", 10), fg="#64748b", bg="#ffffff").pack(pady=(4, 0))
                return

            self._current_product = product

            prod_card = tk.Frame(self.result_frame, bg="#ffffff")
            prod_card.pack(fill="both", expand=True)

            hdr_f = tk.Frame(prod_card, bg="#ffffff")
            hdr_f.pack(fill="x", pady=(0, 10))

            tk.Label(hdr_f, text=product["item_name"], font=("Helvetica", 18, "bold"), fg="#0f172a", bg="#ffffff", wraplength=460, justify="left").pack(anchor="w")

            badge_f = tk.Frame(hdr_f, bg="#ffffff")
            badge_f.pack(anchor="w", pady=(6, 0))

            tk.Label(badge_f, text=f"Barcode: {product['barcode'] or 'N/A'}", font=("Helvetica", 10, "bold"), fg="#475569", bg="#f1f5f9", padx=8, pady=3).pack(side="left", padx=(0, 8))
            tk.Label(badge_f, text=f"Category: {product['category']}", font=("Helvetica", 10, "bold"), fg="#007aff", bg="#eff6ff", padx=8, pady=3).pack(side="left")

            price_box = tk.Frame(prod_card, bg="#f0fdf4", padx=16, pady=12, highlightbackground="#bbf7d0", highlightthickness=1)
            price_box.pack(fill="x", pady=10)

            tk.Label(price_box, text="RETAIL PRICE (12% VAT INC.)", font=("Helvetica", 9, "bold"), fg="#166534", bg="#f0fdf4").pack(anchor="w")
            price_val = Decimal(str(product["unit_price"]))
            tk.Label(price_box, text=f"PHP {price_val:,.2f}", font=("Helvetica", 28, "bold"), fg="#16a34a", bg="#f0fdf4").pack(anchor="w")

            details_f = tk.Frame(prod_card, bg="#ffffff")
            details_f.pack(fill="x", pady=10)

            stock_qty = product["stock_qty"]
            is_low = stock_qty <= product.get("reorder_level", 10)
            stock_color = "#dc2626" if is_low else "#16a34a"
            stock_bg = "#fef2f2" if is_low else "#f0fdf4"

            s_frame = tk.Frame(details_f, bg=stock_bg, padx=12, pady=10, highlightbackground=stock_color, highlightthickness=1)
            s_frame.pack(side="left", fill="x", expand=True, padx=(0, 6))

            tk.Label(s_frame, text="Inventory Stock", font=("Helvetica", 9, "bold"), fg="#64748b", bg=stock_bg).pack(anchor="w")
            tk.Label(s_frame, text=f"{stock_qty} units available", font=("Helvetica", 12, "bold"), fg=stock_color, bg=stock_bg).pack(anchor="w")

            is_comm = product["is_basic_commodity"] == 1
            c_bg = "#eff6ff" if is_comm else "#f8fafc"
            c_fg = "#2563eb" if is_comm else "#64748b"

            c_frame = tk.Frame(details_f, bg=c_bg, padx=12, pady=10, highlightbackground="#cbd5e1", highlightthickness=1)
            c_frame.pack(side="right", fill="x", expand=True, padx=(6, 0))

            tk.Label(c_frame, text="Basic Commodity", font=("Helvetica", 9, "bold"), fg="#64748b", bg=c_bg).pack(anchor="w")
            tk.Label(c_frame, text="Eligible for 5% PWD" if is_comm else "Standard Item", font=("Helvetica", 11, "bold"), fg=c_fg, bg=c_bg).pack(anchor="w")

            if self.on_add_to_cart:
                FlatBtn(
                    prod_card,
                    text="ADD TO CURRENT CHECKOUT CART",
                    bg="#007aff",
                    hover_bg="#0056b3",
                    pady=12,
                    font=("Helvetica", 11, "bold"),
                    command=lambda: self._add_to_cart_and_close(product)
                ).pack(fill="x", pady=(12, 0))

        except Exception as e:
            messagebox.showerror("Search Error", f"Price check failed: {e}", parent=self)

    def _add_to_cart_and_close(self, product):
        if self.on_add_to_cart:
            self.on_add_to_cart(product)
        self.destroy()
