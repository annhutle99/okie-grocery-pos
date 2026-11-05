# modules/inventory.py
# Product Management, Expiry Tracking & Camera Photo Capture for SmartRetail Final Revision

from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from typing import Optional
from decimal import Decimal
from datetime import datetime
import os
from PIL import Image, ImageTk

from db.connection import get_connection
from utils.ui import FlatBtn, CardFrame, ClearableEntry
from utils.scanner import capture_product_photo, scan_barcode_camera

TAX_RATE = Decimal("0.12")


class InventoryFrame(tk.Frame):
    def __init__(self, parent, controller=None, **kwargs):
        super().__init__(parent, bg="#f8fafc", **kwargs)
        self.controller = controller
        self.categories = []
        self._build_ui()
        self.load_categories()
        self.load_products()

    # ── UI Layout ──────────────────────────────────────────────────────────
    def _build_ui(self):
        # Header
        header = tk.Frame(self, bg="#0f172a", padx=20, pady=14)
        header.pack(fill="x")

        tk.Label(header, text="Inventory & Product Stock Management", font=("Helvetica", 16, "bold"), fg="#ffffff", bg="#0f172a").pack(side="left")

        # Toolbar Card — Row 1: Search & Filters | Row 2: Action Buttons
        toolbar = CardFrame(self, bg="#ffffff", padx=16, pady=12)
        toolbar.pack(fill="x", padx=20, pady=16)

        # ── Row 1: Search & Category Filters ──────────────────────────────
        filter_row = tk.Frame(toolbar, bg="#ffffff")
        filter_row.pack(fill="x", pady=(0, 10))

        tk.Label(filter_row, text="Search:", font=("Helvetica", 10, "bold"), fg="#334155", bg="#ffffff").pack(side="left", padx=(0, 4))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *a: self.load_products())
        self.search_entry = ClearableEntry(filter_row, textvariable=self.search_var, width=22)
        self.search_entry.pack(side="left", padx=4)

        tk.Label(filter_row, text="Category:", font=("Helvetica", 10, "bold"), fg="#334155", bg="#ffffff").pack(side="left", padx=(16, 4))
        self.cat_filter_var = tk.StringVar(value="All")
        self.cat_combo = ttk.Combobox(filter_row, textvariable=self.cat_filter_var, state="readonly", width=16)
        self.cat_combo.pack(side="left", padx=4)
        self.cat_combo.bind("<<ComboboxSelected>>", lambda e: self.load_products())

        self.show_inactive = tk.BooleanVar(value=False)
        tk.Checkbutton(filter_row, text="Show Archived Items", variable=self.show_inactive, font=("Helvetica", 10, "bold"), fg="#475569", bg="#ffffff", command=self.load_products).pack(side="left", padx=16)

        FlatBtn(filter_row, text="Camera Scan", bg="#0f172a", hover_bg="#1e293b", command=self._scan_camera_barcode).pack(side="right")

        # ── Row 2: Product Action Buttons ─────────────────────────────────
        action_row = tk.Frame(toolbar, bg="#ffffff")
        action_row.pack(fill="x")

        tk.Label(action_row, text="Product Actions:", font=("Helvetica", 10, "bold"), fg="#64748b", bg="#ffffff").pack(side="left", padx=(0, 10))

        FlatBtn(action_row, text="+ Add Product", bg="#34c759", hover_bg="#248a3d", command=self.open_add_form).pack(side="left", padx=4)
        FlatBtn(action_row, text="Edit Product", bg="#ff9500", hover_bg="#c97500", command=self.edit_product).pack(side="left", padx=4)
        FlatBtn(action_row, text="Restock", bg="#007aff", hover_bg="#0056b3", command=self.restock_product).pack(side="left", padx=4)
        FlatBtn(action_row, text="Promo Rules", bg="#8b5cf6", hover_bg="#7c3aed", command=self.manage_promo_rules).pack(side="left", padx=4)
        FlatBtn(action_row, text="Mobile Companion", bg="#d97706", hover_bg="#b45309", command=self.open_mobile_companion).pack(side="left", padx=4)

        self.btn_archive = FlatBtn(action_row, text="Archive Product", bg="#ff3b30", hover_bg="#d70015", command=self.toggle_archive_product)
        self.btn_archive.pack(side="left", padx=4)

        FlatBtn(action_row, text="Delete Product", bg="#dc2626", hover_bg="#991b1b", command=self.delete_product).pack(side="left", padx=4)

        # Products Table Container
        table_frame = CardFrame(self, bg="#ffffff", padx=2, pady=2)
        table_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        cols = ("ID", "Barcode", "Product Name", "Category", "Cost Price", "Retail Price (12% VAT)", "Stock Qty", "Reorder Level", "Expiry Date", "Basic Commodity", "Photo")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings", height=15)

        widths = {
            "ID": 45,
            "Barcode": 140,
            "Product Name": 210,
            "Category": 165,
            "Cost Price": 95,
            "Retail Price (12% VAT)": 160,
            "Stock Qty": 85,
            "Reorder Level": 95,
            "Expiry Date": 100,
            "Basic Commodity": 135,
            "Photo": 75
        }

        for col in cols:
            self.tree.heading(col, text=col)
            stretch = True if col in ("Product Name", "Category", "Barcode") else False
            anchor = "w" if col in ("Product Name", "Barcode") else "center"
            self.tree.column(col, width=widths.get(col, 100), minwidth=60, anchor=anchor, stretch=stretch)

        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        self.tree.tag_configure("low_stock", foreground="#ea580c", font=("Helvetica", 10, "bold"))
        self.tree.tag_configure("out_of_stock", foreground="#dc2626", font=("Helvetica", 10, "bold"))
        self.tree.tag_configure("expired", foreground="#991b1b", background="#fee2e2", font=("Helvetica", 10, "bold"))
        self.tree.tag_configure("archived", foreground="#64748b", background="#f1f5f9", font=("Helvetica", 10, "italic"))

        self.tree.bind("<Double-1>", lambda e: self.view_photo())
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)

    # ── Selection & Dynamic Button Toggle ───────────────────────────────
    def _on_tree_select(self, event=None):
        sel = self.tree.selection()
        if not sel:
            return
        iid = sel[0]
        tags = self.tree.item(iid, "tags")
        if "archived" in tags:
            self.btn_archive.config(text="Restore Product")
            self.btn_archive.set_colors(bg="#34c759", hover_bg="#248a3d")
        else:
            self.btn_archive.config(text="Archive Product")
            self.btn_archive.set_colors(bg="#ff3b30", hover_bg="#d70015")

    # ── Product Data Operations ────────────────────────────────────────────
    def load_categories(self):
        try:
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT category_name FROM categories ORDER BY category_name ASC")
            rows = cursor.fetchall()
            conn.close()
            self.categories = [r["category_name"] for r in rows]
            self.cat_combo["values"] = ["All"] + self.categories
        except Exception:
            pass

    def load_products(self):
        for row in self.tree.get_children():
            self.tree.delete(row)

        query = """
            SELECT p.*, ip.promo_type, ip.promo_label, ip.second_item_discount_percent, ip.discount_percent as promo_disc_pct
            FROM products p
            LEFT JOIN item_promotions ip ON p.item_id = ip.item_id AND ip.is_active = 1
            WHERE 1=1
        """
        params = []

        if not self.show_inactive.get():
            query += " AND p.is_active = 1"

        search = self.search_var.get().strip()
        if search:
            query += " AND (p.item_name LIKE %s OR p.barcode LIKE %s)"
            params.extend([f"%{search}%", f"%{search}%"])

        cat = self.cat_filter_var.get()
        if cat and cat != "All":
            query += " AND p.category = %s"
            params.append(cat)

        query += " ORDER BY p.item_id DESC"

        try:
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute(query, params)
            products = cursor.fetchall()
            conn.close()

            today_date = datetime.now().date()

            for p in products:
                iid = p["item_id"]
                stock = p["stock_qty"]
                reorder = p["reorder_level"]
                exp_date = p["expiry_date"]
                has_photo = "YES" if p["image_path"] and os.path.exists(p["image_path"]) else "NO"
                commodity = "YES (5% PWD)" if p["is_basic_commodity"] == 1 else "NO"

                is_active = p.get("is_active", 1)

                if is_active == 0:
                    tag = "archived"
                    display_name = f"{p['item_name']} [ARCHIVED]"
                elif exp_date and exp_date <= today_date:
                    tag = "expired"
                    display_name = p["item_name"]
                elif stock <= 0:
                    tag = "out_of_stock"
                    display_name = p["item_name"]
                elif stock <= reorder:
                    tag = "low_stock"
                    display_name = p["item_name"]
                else:
                    tag = "normal"
                    display_name = p["item_name"]

                # Append Promo Tag if active
                ptype = p.get("promo_type")
                if ptype == "b1t1_free":
                    display_name += " [B1T1 FREE]"
                elif ptype == "b1g1_percent":
                    display_name += f" [B1G1 {p.get('second_item_discount_percent', 50):.0f}% OFF]"
                elif ptype == "bundle":
                    display_name += f" [BUNDLE {p.get('promo_disc_pct', 0):.0f}%]"
                elif ptype == "discount":
                    display_name += f" [PROMO {p.get('promo_disc_pct', 0):.0f}%]"

                exp_str = exp_date.strftime("%Y-%m-%d") if exp_date else "N/A"

                self.tree.insert("", "end", iid=str(iid), values=(
                    iid, p["barcode"] or "N/A", display_name, p["category"],
                    f"PHP {Decimal(str(p['cost_price'])):,.2f}",
                    f"PHP {Decimal(str(p['unit_price'])):,.2f}",
                    stock, reorder, exp_str, commodity, has_photo
                ), tags=(tag,))
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load products: {e}")

    def manage_promo_rules(self):
        iid = self._get_selected_product_id()
        if not iid:
            return
        try:
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM products WHERE item_id = %s", (iid,))
            prod = cursor.fetchone()
            conn.close()

            if prod:
                ItemPromoDialog(self, product=prod, on_save=self.load_products)
        except Exception as e:
            messagebox.showerror("Error", f"Could not open promo manager: {e}")

    def refresh(self):
        """Reload products and categories from database to reflect latest stock levels."""
        self.load_categories()
        self.load_products()

    def _scan_camera_barcode(self):
        """Open barcode scanner in background thread — UI stays responsive."""
        def _on_result(code: str | None):
            if code:
                self.search_var.set(code)
        scan_barcode_camera(parent_widget=self, on_result=_on_result)

    def _get_selected_product_id(self) -> Optional[int]:
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("No Selection", "Please select a product from the table.")
            return None
        return int(sel[0])

    def view_photo(self):
        iid = self._get_selected_product_id()
        if not iid:
            return
        try:
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT image_path, item_name FROM products WHERE item_id = %s", (iid,))
            prod = cursor.fetchone()
            conn.close()

            if prod and prod["image_path"] and os.path.exists(prod["image_path"]):
                win = tk.Toplevel(self)
                win.title(f"Product Image — {prod['item_name']}")
                win.geometry("500x500")
                win.configure(bg="#ffffff")

                img = Image.open(prod["image_path"])
                img.thumbnail((450, 450))
                tk_img = ImageTk.PhotoImage(img)

                lbl = tk.Label(win, image=tk_img, bg="#ffffff")
                lbl.image = tk_img
                lbl.pack(padx=20, pady=20)
            else:
                messagebox.showinfo("No Photo", "No captured photo available for this product.", parent=self)
        except Exception as e:
            messagebox.showerror("Error", f"Image load error: {e}")

    def open_add_form(self):
        ProductFormDialog(self, title="Add New Product", categories=self.categories, on_save=self.load_products)

    def edit_product(self):
        iid = self._get_selected_product_id()
        if not iid:
            return
        try:
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM products WHERE item_id = %s", (iid,))
            prod = cursor.fetchone()
            conn.close()

            if prod:
                ProductFormDialog(self, title=f"Edit Product #{iid}", product=prod, categories=self.categories, on_save=self.load_products)
        except Exception as e:
            messagebox.showerror("Error", f"Edit error: {e}")

    def restock_product(self):
        iid = self._get_selected_product_id()
        if not iid:
            return
        add_qty_str = simpledialog.askstring("Restock Product", "Enter quantity to add to inventory stock:", parent=self)
        if add_qty_str and add_qty_str.isdigit():
            add_qty = int(add_qty_str)
            if add_qty > 0:
                try:
                    conn = get_connection()
                    cursor = conn.cursor()
                    cursor.execute("UPDATE products SET stock_qty = stock_qty + %s WHERE item_id = %s", (add_qty, iid))
                    cursor.execute("INSERT INTO inventory_movements (item_id, movement_type, quantity, notes) VALUES (%s, 'restock', %s, 'Manual Restock')", (iid, add_qty))
                    conn.commit()
                    conn.close()
                    messagebox.showinfo("Success", f"Added {add_qty} units to product #{iid}.", parent=self)
                    self.load_products()
                except Exception as e:
                    messagebox.showerror("Error", f"Restock error: {e}")

    def toggle_archive_product(self):
        iid = self._get_selected_product_id()
        if not iid:
            return

        tags = self.tree.item(str(iid), "tags")
        is_archived = "archived" in tags
        action_name = "Restore / Reactivate" if is_archived else "Archive"
        new_status = 1 if is_archived else 0

        if messagebox.askyesno(f"Confirm {action_name}", f"Are you sure you want to {action_name.lower()} product #{iid}?", parent=self):
            try:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("UPDATE products SET is_active = %s WHERE item_id = %s", (new_status, iid))
                conn.commit()
                conn.close()
                self.load_products()
                messagebox.showinfo("Success", f"Product #{iid} successfully {'restored to active inventory' if is_archived else 'archived'}.", parent=self)
            except Exception as e:
                messagebox.showerror("Error", f"Operation failed: {e}", parent=self)

    def delete_product(self):
        iid = self._get_selected_product_id()
        if not iid:
            return

        try:
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)

            cursor.execute("SELECT item_name FROM products WHERE item_id = %s", (iid,))
            prod = cursor.fetchone()
            item_name = prod["item_name"] if prod else f"Product #{iid}"

            # Check if product is referenced in sales history
            cursor.execute("SELECT COUNT(*) AS sales_count FROM sale_items WHERE item_id = %s", (iid,))
            row = cursor.fetchone()
            sales_count = row["sales_count"] if row else 0

            if sales_count > 0:
                # Product has transaction history — offer soft Archive to preserve sales records
                if messagebox.askyesno(
                    "Product Has Sales Records",
                    f"Product '{item_name}' (ID #{iid}) has {sales_count} past sales record(s) on file.\n\n"
                    f"Permanently deleting it would break accounting receipts. Would you like to ARCHIVE this product instead to hide it from sales while keeping records intact?",
                    parent=self
                ):
                    cursor.execute("UPDATE products SET is_active = 0 WHERE item_id = %s", (iid,))
                    conn.commit()
                    conn.close()
                    self.load_products()
                    messagebox.showinfo("Product Archived", f"Product '{item_name}' has been archived.", parent=self)
                    return
                else:
                    if not messagebox.askyesno(
                        "PERMANENT DELETE WARNING",
                        f"WARNING: Are you absolutely sure you want to PERMANENTLY DELETE '{item_name}'?\n\nThis will permanently erase the product from database catalog.",
                        parent=self
                    ):
                        conn.close()
                        return

            else:
                if not messagebox.askyesno(
                    "Confirm Permanent Delete",
                    f"Are you sure you want to permanently delete product '{item_name}' (ID #{iid})?",
                    parent=self
                ):
                    conn.close()
                    return

            # Execute Permanent Delete
            cursor = conn.cursor()
            cursor.execute("DELETE FROM inventory_movements WHERE item_id = %s", (iid,))
            cursor.execute("DELETE FROM products WHERE item_id = %s", (iid,))
            conn.commit()
            conn.close()

            self.load_products()
            messagebox.showinfo("Product Deleted", f"Product '{item_name}' (ID #{iid}) has been permanently deleted.", parent=self)

        except Exception as e:
            messagebox.showerror("Delete Error", f"Failed to delete product: {e}", parent=self)

    def open_mobile_companion(self):
        dlg = MobileCompanionDialog(self, on_update_callback=self._on_mobile_sync)
        dlg._center()

    def _on_mobile_sync(self):
        self.load_products()
        if self.controller and hasattr(self.controller, "frames"):
            for frame_key in ("dashboard", "analytics", "history"):
                if frame_key in self.controller.frames:
                    try:
                        self.controller.frames[frame_key].refresh()
                    except Exception as e:
                        print(f"Error refreshing {frame_key} on mobile sync: {e}")


# ── Product Form Dialog with Price & VAT Auto Calculator & Camera Photo Capture ──
class ProductFormDialog(tk.Toplevel):
    def __init__(self, parent, title: str, categories: list, product: dict = None, on_save=None):
        super().__init__(parent)
        self.title(title)
        self.geometry("540x680")
        self.configure(bg="#ffffff")
        self.transient(parent)
        self.grab_set()

        self.categories = categories
        self.product = product
        self.on_save = on_save
        self.captured_photo_path = product.get("image_path") if product else None

        self._build_form()
        self._center()

    def _build_form(self):
        tk.Label(self, text=self.title(), font=("Helvetica", 14, "bold"), fg="#0f172a", bg="#ffffff").pack(pady=(16, 10))

        form_frame = tk.Frame(self, bg="#ffffff", padx=24)
        form_frame.pack(fill="both", expand=True)

        self.vars = {}

        # ── Barcode Row with Scan Camera Button ────────────────────────────
        bc_row = tk.Frame(form_frame, bg="#ffffff")
        bc_row.pack(fill="x", pady=4)
        tk.Label(bc_row, text="Barcode:", font=("Helvetica", 9, "bold"), fg="#334155", bg="#ffffff", width=24, anchor="w").pack(side="left")
        self.vars["barcode_var"] = tk.StringVar(value=self.product.get("barcode") if self.product else "")
        bc_entry = tk.Entry(bc_row, textvariable=self.vars["barcode_var"], font=("Helvetica", 10), bg="#f1f5f9", relief="flat")
        bc_entry.pack(side="left", fill="x", expand=True, ipady=4, padx=(0, 6))
        FlatBtn(bc_row, text="Scan Barcode", bg="#0f172a", hover_bg="#1e293b", command=self._scan_barcode_field).pack(side="right")

        fields = [
            ("Product Name:", "name_var", self.product.get("item_name") if self.product else ""),
            ("Cost Price (Wholesale):", "cost_var", str(self.product.get("cost_price", 0)) if self.product else "0.00"),
            ("Profit Markup (%):", "markup_var", str(self.product.get("markup_percent", 20)) if self.product else "20.00"),
            ("Final Retail Price (12% VAT Inc.):", "price_var", str(self.product.get("unit_price", 0)) if self.product else "0.00"),
            ("Stock Quantity to Add:", "stock_var", str(self.product.get("stock_qty", 0)) if self.product else "10"),
            ("Reorder Alert Level:", "reorder_var", str(self.product.get("reorder_level", 5)) if self.product else "5"),
            ("Expiry Date (YYYY-MM-DD):", "expiry_var", str(self.product.get("expiry_date") or "") if self.product else ""),
        ]

        for label, var_name, default in fields:
            row = tk.Frame(form_frame, bg="#ffffff")
            row.pack(fill="x", pady=4)
            tk.Label(row, text=label, font=("Helvetica", 9, "bold"), fg="#334155", bg="#ffffff", width=24, anchor="w").pack(side="left")
            var = tk.StringVar(value=default)
            self.vars[var_name] = var
            entry = tk.Entry(row, textvariable=var, font=("Helvetica", 10), bg="#f1f5f9", relief="flat")
            entry.pack(side="right", fill="x", expand=True, ipady=4)

        # Auto Calculate Price from Cost + Markup + 12% VAT
        def auto_calc_price(*args):
            try:
                cost = Decimal(self.vars["cost_var"].get().strip() or "0")
                markup = Decimal(self.vars["markup_var"].get().strip() or "0")
                price_no_vat = cost * (Decimal("1") + (markup / Decimal("100")))
                price_with_vat = (price_no_vat * Decimal("1.12")).quantize(Decimal("0.01"))
                self.vars["price_var"].set(str(price_with_vat))
            except Exception:
                pass

        self.vars["cost_var"].trace_add("write", auto_calc_price)
        self.vars["markup_var"].trace_add("write", auto_calc_price)

        # Category Dropdown
        cat_row = tk.Frame(form_frame, bg="#ffffff")
        cat_row.pack(fill="x", pady=4)
        tk.Label(cat_row, text="Category:", font=("Helvetica", 9, "bold"), fg="#334155", bg="#ffffff", width=24, anchor="w").pack(side="left")
        self.cat_var = tk.StringVar(value=self.product.get("category") if self.product else (self.categories[0] if self.categories else "General"))
        ttk.Combobox(cat_row, textvariable=self.cat_var, values=self.categories, state="readonly").pack(side="right", fill="x", expand=True)

        # Basic Commodity Checkbox (PWD 5% Discount)
        self.is_commodity_var = tk.BooleanVar(value=bool(self.product.get("is_basic_commodity", 0)) if self.product else False)
        tk.Checkbutton(form_frame, text="Basic Commodity (Eligible for 5% PWD / Senior Discount)", variable=self.is_commodity_var, font=("Helvetica", 9, "bold"), fg="#2563eb", bg="#ffffff").pack(anchor="w", pady=8)

        # Camera Photo Capture Button
        cam_row = tk.Frame(form_frame, bg="#ffffff")
        cam_row.pack(fill="x", pady=6)
        self.photo_status_lbl = tk.Label(cam_row, text="Photo: " + ("Captured" if self.captured_photo_path else "None"), font=("Helvetica", 9), fg="#64748b", bg="#ffffff")
        self.photo_status_lbl.pack(side="left")
        FlatBtn(cam_row, text="Take Camera Photo", bg="#0f172a", hover_bg="#1e293b", command=self._take_photo).pack(side="right")

        # Save Button
        FlatBtn(self, text="SAVE PRODUCT", bg="#16a34a", hover_bg="#15803d", pady=12, command=self._save).pack(fill="x", padx=24, pady=16)

    def _scan_barcode_field(self):
        """Open camera barcode scanner to auto-fill the barcode input box."""
        def _on_scanned(code: str | None):
            if code:
                self.vars["barcode_var"].set(code)
        scan_barcode_camera(parent_widget=self, on_result=_on_scanned)

    def _take_photo(self):
        barcode = self.vars["barcode_var"].get().strip() or "temp"
        self.photo_status_lbl.config(text="Photo: Camera open... press SPACE to capture", fg="#007aff")

        def _on_captured(filepath: str | None):
            if filepath:
                self.captured_photo_path = filepath
                self.photo_status_lbl.config(text="Photo: Captured!", fg="#16a34a")
            else:
                self.photo_status_lbl.config(text="Photo: Cancelled", fg="#64748b")

        capture_product_photo(barcode, parent_widget=self, on_result=_on_captured)

    def _save(self):
        name = self.vars["name_var"].get().strip()
        barcode = self.vars["barcode_var"].get().strip() or None
        if not name:
            messagebox.showwarning("Input Required", "Product name is required.", parent=self)
            return

        try:
            cost = Decimal(self.vars["cost_var"].get().strip() or "0")
            markup = Decimal(self.vars["markup_var"].get().strip() or "20")
            price = Decimal(self.vars["price_var"].get().strip() or "0")
            stock = int(self.vars["stock_var"].get().strip() or "0")
            reorder = int(self.vars["reorder_var"].get().strip() or "5")
            exp_str = self.vars["expiry_var"].get().strip() or None
            category = self.cat_var.get()
            is_commodity = 1 if self.is_commodity_var.get() else 0

            conn = get_connection()
            cursor = conn.cursor()

            if self.product:
                cursor.execute("""
                    UPDATE products SET barcode=%s, item_name=%s, category=%s, cost_price=%s, markup_percent=%s, unit_price=%s, stock_qty=%s, reorder_level=%s, expiry_date=%s, image_path=%s, is_basic_commodity=%s
                    WHERE item_id=%s
                """, (barcode, name, category, float(cost), float(markup), float(price), stock, reorder, exp_str, self.captured_photo_path, is_commodity, self.product["item_id"]))
            else:
                cursor.execute("""
                    INSERT INTO products (barcode, item_name, category, cost_price, markup_percent, unit_price, stock_qty, reorder_level, expiry_date, image_path, is_basic_commodity)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (barcode, name, category, float(cost), float(markup), float(price), stock, reorder, exp_str, self.captured_photo_path, is_commodity))
                item_id = cursor.lastrowid
                cursor.execute("INSERT INTO inventory_movements (item_id, movement_type, quantity, notes) VALUES (%s, 'restock', %s, 'Initial Stock')", (item_id, stock))

            conn.commit()
            conn.close()

            if self.on_save:
                self.on_save()
            self.destroy()
        except Exception as e:
            messagebox.showerror("Save Error", f"Failed to save product: {e}", parent=self)

    def _center(self):
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")


class ItemPromoDialog(tk.Toplevel):
    """
    Manager Dialog to configure Item-level Promotions:
    1. Buy 1 Get 1 FREE (B1T1 Free - 100% off 2nd item)
    2. Buy 1 Get 2nd at X% Off (e.g. 50% Off 2nd item)
    3. Bundle / Bulk Discount (Buy N or more get X% or PHP Y off)
    4. Direct Item Discount (X% or PHP Y off per unit)
    """

    def __init__(self, parent, product: dict, on_save=None):
        super().__init__(parent)
        self.product = product
        self.on_save = on_save

        self.title(f"Promo Rules — {product['item_name']} ({product['barcode'] or 'No Barcode'})")
        self.geometry("520x580")
        self.configure(bg="#ffffff")
        self.transient(parent)
        self.grab_set()

        self.existing_promo = self._fetch_existing_promo()
        self._build_ui()
        self._center()

    def _fetch_existing_promo(self) -> dict | None:
        try:
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM item_promotions WHERE item_id = %s AND is_active = 1", (self.product["item_id"],))
            row = cursor.fetchone()
            conn.close()
            return row
        except Exception:
            return None

    def _build_ui(self):
        header = tk.Frame(self, bg="#8b5cf6", padx=16, pady=12)
        header.pack(fill="x")
        tk.Label(header, text="Item Promotion & Bundle Manager", font=("Helvetica", 14, "bold"), fg="#ffffff", bg="#8b5cf6").pack(anchor="w")
        tk.Label(header, text=f"Product: {self.product['item_name']}  |  Price: PHP {Decimal(str(self.product['unit_price'])):,.2f}", font=("Helvetica", 10), fg="#f3e8ff", bg="#8b5cf6").pack(anchor="w", pady=(2, 0))

        form = tk.Frame(self, bg="#ffffff", padx=20, pady=16)
        form.pack(fill="both", expand=True)

        tk.Label(form, text="Select Promotion Type:", font=("Helvetica", 10, "bold"), fg="#1e293b", bg="#ffffff").pack(anchor="w", pady=(0, 6))

        self.promo_type_var = tk.StringVar(value=self.existing_promo.get("promo_type", "none") if self.existing_promo else "none")

        promo_options = [
            ("No Active Promotion", "none", "Normal retail price applies."),
            ("Buy 1 Get 1 FREE (B1T1 Free)", "b1t1_free", "Every 2nd item added to cart is 100% FREE."),
            ("Buy 1 Get 2nd Item at % OFF (e.g. 50% Off)", "b1g1_percent", "Every 2nd item gets a custom % discount."),
            ("Bundle / Bulk Discount (Buy N or more)", "bundle", "Get a discount when buying N or more units."),
            ("Direct Item Promo Discount", "discount", "Direct percentage or PHP amount off per unit.")
        ]

        for title, key, desc in promo_options:
            rf = tk.Frame(form, bg="#ffffff")
            rf.pack(fill="x", pady=2)
            rb = tk.Radiobutton(rf, text=title, value=key, variable=self.promo_type_var, font=("Helvetica", 10, "bold"), fg="#0f172a", bg="#ffffff", activebackground="#ffffff", command=self._on_type_change)
            rb.pack(anchor="w")
            tk.Label(rf, text=f"   {desc}", font=("Helvetica", 8), fg="#64748b", bg="#ffffff").pack(anchor="w")

        # Divider
        tk.Frame(form, bg="#e2e8f0", height=1).pack(fill="x", pady=10)

        # Dynamic Fields Frame
        self.fields_frame = tk.Frame(form, bg="#ffffff")
        self.fields_frame.pack(fill="x")

        # Form Variables
        self.b1g1_pct_var = tk.StringVar(value=str(self.existing_promo.get("second_item_discount_percent", 50.0)) if self.existing_promo else "50.0")
        self.min_qty_var = tk.StringVar(value=str(self.existing_promo.get("min_qty", 2)) if self.existing_promo else "2")
        self.disc_pct_var = tk.StringVar(value=str(self.existing_promo.get("discount_percent", 10.0)) if self.existing_promo else "10.0")
        self.disc_amt_var = tk.StringVar(value=str(self.existing_promo.get("discount_amount", 0.0)) if self.existing_promo else "0.00")
        self.label_var = tk.StringVar(value=self.existing_promo.get("promo_label", "") if self.existing_promo else "")

        self._render_fields()

        # Action Buttons Footer
        footer = tk.Frame(self, bg="#ffffff", padx=20, pady=12)
        footer.pack(side="bottom", fill="x")

        FlatBtn(footer, text="SAVE PROMO RULE", bg="#8b5cf6", hover_bg="#7c3aed", command=self.save_promo).pack(side="right", padx=4)
        if self.existing_promo and self.existing_promo.get("promo_type") != "none":
            FlatBtn(footer, text="Disable / Remove Promo", bg="#ff3b30", hover_bg="#d70015", command=self.delete_promo).pack(side="right", padx=4)
        FlatBtn(footer, text="Cancel", bg="#94a3b8", hover_bg="#64748b", command=self.destroy).pack(side="left")

    def _on_type_change(self):
        self._render_fields()

    def _render_fields(self):
        for widget in self.fields_frame.winfo_children():
            widget.destroy()

        ptype = self.promo_type_var.get()
        if ptype == "none":
            tk.Label(self.fields_frame, text="No promotion active.", font=("Helvetica", 9, "italic"), fg="#94a3b8", bg="#ffffff").pack(anchor="w")
            return

        if ptype == "b1g1_percent":
            row = tk.Frame(self.fields_frame, bg="#ffffff")
            row.pack(fill="x", pady=3)
            tk.Label(row, text="2nd Item Discount (%):", font=("Helvetica", 9, "bold"), fg="#334155", bg="#ffffff", width=22, anchor="w").pack(side="left")
            tk.Entry(row, textvariable=self.b1g1_pct_var, font=("Helvetica", 10), bg="#f1f5f9", relief="flat").pack(side="left", fill="x", expand=True, ipady=3)
            if not self.label_var.get() or self.label_var.get() == "BUY 1 TAKE 1 FREE":
                self.label_var.set("B1G1 50% OFF")

        elif ptype == "b1t1_free":
            if not self.label_var.get() or "50%" in self.label_var.get():
                self.label_var.set("BUY 1 TAKE 1 FREE")

        elif ptype == "bundle":
            row1 = tk.Frame(self.fields_frame, bg="#ffffff")
            row1.pack(fill="x", pady=3)
            tk.Label(row1, text="Min Qty Required:", font=("Helvetica", 9, "bold"), fg="#334155", bg="#ffffff", width=22, anchor="w").pack(side="left")
            tk.Entry(row1, textvariable=self.min_qty_var, font=("Helvetica", 10), bg="#f1f5f9", relief="flat").pack(side="left", fill="x", expand=True, ipady=3)

            row2 = tk.Frame(self.fields_frame, bg="#ffffff")
            row2.pack(fill="x", pady=3)
            tk.Label(row2, text="Bundle Discount (%):", font=("Helvetica", 9, "bold"), fg="#334155", bg="#ffffff", width=22, anchor="w").pack(side="left")
            tk.Entry(row2, textvariable=self.disc_pct_var, font=("Helvetica", 10), bg="#f1f5f9", relief="flat").pack(side="left", fill="x", expand=True, ipady=3)
            if not self.label_var.get() or "FREE" in self.label_var.get():
                self.label_var.set("BUNDLE DISC")

        elif ptype == "discount":
            row1 = tk.Frame(self.fields_frame, bg="#ffffff")
            row1.pack(fill="x", pady=3)
            tk.Label(row1, text="Discount Percent (%):", font=("Helvetica", 9, "bold"), fg="#334155", bg="#ffffff", width=22, anchor="w").pack(side="left")
            tk.Entry(row1, textvariable=self.disc_pct_var, font=("Helvetica", 10), bg="#f1f5f9", relief="flat").pack(side="left", fill="x", expand=True, ipady=3)

            row2 = tk.Frame(self.fields_frame, bg="#ffffff")
            row2.pack(fill="x", pady=3)
            tk.Label(row2, text="OR Fixed Amount Off (PHP):", font=("Helvetica", 9, "bold"), fg="#334155", bg="#ffffff", width=22, anchor="w").pack(side="left")
            tk.Entry(row2, textvariable=self.disc_amt_var, font=("Helvetica", 10), bg="#f1f5f9", relief="flat").pack(side="left", fill="x", expand=True, ipady=3)
            if not self.label_var.get() or "FREE" in self.label_var.get():
                self.label_var.set("SPECIAL PROMO")

        # Receipt Promo Label Field
        row_lbl = tk.Frame(self.fields_frame, bg="#ffffff")
        row_lbl.pack(fill="x", pady=4)
        tk.Label(row_lbl, text="Receipt Promo Label:", font=("Helvetica", 9, "bold"), fg="#334155", bg="#ffffff", width=22, anchor="w").pack(side="left")
        tk.Entry(row_lbl, textvariable=self.label_var, font=("Helvetica", 10), bg="#f1f5f9", relief="flat").pack(side="left", fill="x", expand=True, ipady=3)

    def save_promo(self):
        ptype = self.promo_type_var.get()
        item_id = self.product["item_id"]

        try:
            b1g1_pct = float(self.b1g1_pct_var.get().strip() or "100.0") if ptype == "b1g1_percent" else (100.0 if ptype == "b1t1_free" else 0.0)
            min_qty = int(self.min_qty_var.get().strip() or "2")
            disc_pct = float(self.disc_pct_var.get().strip() or "0.0")
            disc_amt = float(self.disc_amt_var.get().strip() or "0.0")
            lbl = self.label_var.get().strip() or ("BUY 1 TAKE 1" if "b1t1" in ptype else "PROMO")

            conn = get_connection()
            cursor = conn.cursor()

            if ptype == "none":
                cursor.execute("DELETE FROM item_promotions WHERE item_id = %s", (item_id,))
            else:
                cursor.execute("""
                    INSERT INTO item_promotions (item_id, promo_type, second_item_discount_percent, min_qty, discount_percent, discount_amount, promo_label, is_active)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 1)
                    ON DUPLICATE KEY UPDATE
                        promo_type=VALUES(promo_type),
                        second_item_discount_percent=VALUES(second_item_discount_percent),
                        min_qty=VALUES(min_qty),
                        discount_percent=VALUES(discount_percent),
                        discount_amount=VALUES(discount_amount),
                        promo_label=VALUES(promo_label),
                        is_active=1
                """, (item_id, ptype, b1g1_pct, min_qty, disc_pct, disc_amt, lbl))

            conn.commit()
            conn.close()

            messagebox.showinfo("Promo Saved", f"Promotion rule saved for '{self.product['item_name']}'!", parent=self)
            if self.on_save:
                self.on_save()
            self.destroy()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save promotion: {e}", parent=self)

    def delete_promo(self):
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM item_promotions WHERE item_id = %s", (self.product["item_id"],))
            conn.commit()
            conn.close()
            messagebox.showinfo("Promo Disabled", "Promotion rule disabled for this item.", parent=self)
            if self.on_save:
                self.on_save()
            self.destroy()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to disable promo: {e}", parent=self)

    def _center(self):
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")


# ── Mobile Companion QR Code & Sync Modal Dialog ──────────────────────────────
class MobileCompanionDialog(tk.Toplevel):
    """
    Modal window displaying LAN IP & dynamic QR Code for phone camera scanning.
    Starts Flask server in background and manages live synchronization callback.
    """
    def __init__(self, parent, on_update_callback=None):
        super().__init__(parent)
        self.on_update_callback = on_update_callback
        self.title("Mobile Inventory Companion — Scan & Sync")
        self.geometry("540x670")
        self.configure(bg="#ffffff")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.qr_image_tk = None

        self._build_ui()
        self._start_server()

    def _build_ui(self):
        # Header Bar in O!kie Manager Amber
        hdr = tk.Frame(self, bg="#d97706", padx=20, pady=12)
        hdr.pack(fill="x")

        tk.Label(hdr, text="Mobile Inventory Companion", font=("Helvetica", 15, "bold"), fg="#ffffff", bg="#d97706").pack(anchor="w")
        tk.Label(hdr, text="Scan QR Code with your smartphone to manage stock & scan items", font=("Helvetica", 9, "bold"), fg="#fef08a", bg="#d97706").pack(anchor="w", pady=(2, 0))

        # Main Body
        body = tk.Frame(self, bg="#ffffff", padx=20, pady=12)
        body.pack(fill="both", expand=True)

        # Status Tag
        self.lbl_status = tk.Label(body, text="Initializing Mobile Server...", font=("Helvetica", 9, "bold"), fg="#d97706", bg="#fffbeb", padx=12, pady=5)
        self.lbl_status.pack(pady=(0, 6))

        # QR Display Container
        self.qr_frame = tk.Frame(body, bg="#ffffff", highlightbackground="#e2e8f0", highlightthickness=1, padx=10, pady=10)
        self.qr_frame.pack(pady=2)

        self.lbl_qr = tk.Label(self.qr_frame, text="Generating QR Code...", bg="#ffffff", font=("Helvetica", 10), fg="#64748b")
        self.lbl_qr.pack()

        # URL Text with Auto-Wrap
        self.lbl_url = tk.Label(body, text="", font=("Helvetica", 9, "bold"), fg="#0f172a", bg="#ffffff", wraplength=490, justify="center")
        self.lbl_url.pack(pady=(8, 4))

        # Helpful hint box
        hint_box = tk.Frame(body, bg="#f8fafc", highlightbackground="#e2e8f0", highlightthickness=1, padx=12, pady=8)
        hint_box.pack(fill="x", pady=6)

        hints = [
            "1. Connect phone to same Wi-Fi network as this laptop.",
            "2. Open Phone Camera & Scan the QR code above.",
            "3. Sign in as Manager to check stock, scan items & add products.",
            "4. All changes sync LIVE to this laptop automatically!"
        ]
        for h in hints:
            tk.Label(hint_box, text=h, font=("Helvetica", 8, "bold"), fg="#475569", bg="#f8fafc", anchor="w").pack(fill="x", pady=1)

        # Close / Stop Server Button
        FlatBtn(body, text="STOP COMPANION & CLOSE", bg="#dc2626", hover_bg="#991b1b", pady=10, font=("Helvetica", 10, "bold"), command=self._on_close).pack(fill="x", pady=(10, 0))

    def _start_server(self):
        try:
            from utils.mobile_companion import start_mobile_companion_session
            full_url, qr_tk = start_mobile_companion_session(notify_callback=self._handle_notify)
            self.qr_image_tk = qr_tk
            self.lbl_qr.config(image=self.qr_image_tk, text="")
            self.lbl_url.config(text=f"Server URL: {full_url}")
            self.lbl_status.config(text="SERVER ACTIVE | READY FOR SCANNING", fg="#166534", bg="#dcfce7")
        except Exception as e:
            self.lbl_status.config(text=f"Server Launch Error: {e}", fg="#991b1b", bg="#fee2e2")

    def _handle_notify(self):
        if self.on_update_callback:
            try:
                self.after(0, self.on_update_callback)
            except Exception:
                pass

    def _on_close(self):
        try:
            from utils.mobile_companion import stop_mobile_companion_session
            stop_mobile_companion_session()
        except Exception:
            pass
        self.destroy()

    def _center(self):
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

