# modules/history.py
# Sales History & Void Transaction Management for SmartRetail Final Revision

from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from typing import Optional
from datetime import datetime, timedelta
from decimal import Decimal

from db.connection import get_connection
from utils.receipt import generate_receipt_text
from utils.ui import FlatBtn, CardFrame, ClearableEntry
from modules.auth import SecurityManager


class SalesHistoryFrame(tk.Frame):
    def __init__(self, parent, controller=None, **kwargs):
        super().__init__(parent, bg="#f8fafc", **kwargs)
        self.controller = controller
        self._build_ui()
        self.refresh()

    # ── UI Layout ──────────────────────────────────────────────────────────
    def _build_ui(self):
        # Header
        header = tk.Frame(self, bg="#0f172a", padx=20, pady=14)
        header.pack(fill="x")

        tk.Label(header, text="Sales History & Transaction Audit Logs", font=("Helvetica", 16, "bold"), fg="#ffffff", bg="#0f172a").pack(side="left")

        # Filters Card
        filter_card = CardFrame(self, bg="#ffffff", padx=16, pady=12)
        filter_card.pack(fill="x", padx=20, pady=16)

        tk.Label(filter_card, text="Search (SI No / Cashier):", font=("Helvetica", 10, "bold"), fg="#334155", bg="#ffffff").grid(row=0, column=0, sticky="w", padx=(0, 4))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *a: self.apply_filters())
        self.search_entry = ClearableEntry(filter_card, textvariable=self.search_var, width=18)
        self.search_entry.grid(row=0, column=1, padx=(0, 16))

        tk.Label(filter_card, text="Date Range:", font=("Helvetica", 10, "bold"), fg="#334155", bg="#ffffff").grid(row=0, column=2, sticky="w", padx=(0, 4))
        self.date_filter_var = tk.StringVar(value="All Time")
        date_combo = ttk.Combobox(filter_card, textvariable=self.date_filter_var, values=["Today", "Yesterday", "This Week", "This Month", "All Time"], state="readonly", width=12)
        date_combo.grid(row=0, column=3, padx=(0, 16))
        date_combo.bind("<<ComboboxSelected>>", lambda e: self.apply_filters())

        tk.Label(filter_card, text="Status:", font=("Helvetica", 10, "bold"), fg="#334155", bg="#ffffff").grid(row=0, column=4, sticky="w", padx=(0, 4))
        self.status_filter_var = tk.StringVar(value="All")
        status_combo = ttk.Combobox(filter_card, textvariable=self.status_filter_var, values=["All", "completed", "voided"], state="readonly", width=12)
        status_combo.grid(row=0, column=5, padx=(0, 16))
        status_combo.bind("<<ComboboxSelected>>", lambda e: self.apply_filters())

        FlatBtn(filter_card, text="Reset Filters", bg="#475569", hover_bg="#334155", command=self.reset_filters).grid(row=0, column=6, sticky="e")

        # Table & Actions Container
        content_frame = tk.Frame(self, bg="#f8fafc", padx=20, pady=0)
        content_frame.pack(fill="both", expand=True)

        # Left: Sales List Table
        table_frame = CardFrame(content_frame, bg="#ffffff", padx=2, pady=2)
        table_frame.pack(side="left", fill="both", expand=True, padx=(0, 12))

        cols = ("sale_id", "si_number", "date", "cashier", "items", "payment", "discount", "total", "status")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings", selectmode="browse")

        headers = {
            "sale_id": "ID",
            "si_number": "SI Number",
            "date": "Date & Time",
            "cashier": "Cashier",
            "items": "Items",
            "payment": "Method",
            "discount": "Discount / Promo",
            "total": "Total (PHP)",
            "status": "Status"
        }
        widths = {
            "sale_id": 40,
            "si_number": 130,
            "date": 130,
            "cashier": 130,
            "items": 50,
            "payment": 70,
            "discount": 140,
            "total": 100,
            "status": 80
        }

        for c in cols:
            self.tree.heading(c, text=headers[c])
            self.tree.column(c, width=widths[c], anchor="center")

        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self.tree.tag_configure("completed", foreground="#16a34a", font=("Helvetica", 10, "bold"))
        self.tree.tag_configure("voided", foreground="#dc2626", font=("Helvetica", 10, "bold"))

        self.tree.bind("<Double-1>", lambda e: self.view_details())

        # Right: Action Buttons Panel
        action_frame = CardFrame(content_frame, bg="#ffffff", padx=16, pady=16)
        action_frame.pack(side="right", fill="y")

        tk.Label(action_frame, text="Transaction Actions", font=("Helvetica", 12, "bold"), fg="#0f172a", bg="#ffffff").pack(anchor="w", pady=(0, 12))

        FlatBtn(action_frame, text="View Sale Details", bg="#007aff", hover_bg="#0056b3", command=self.view_details).pack(fill="x", pady=6)
        FlatBtn(action_frame, text="View Sales Invoice", bg="#af52de", hover_bg="#8e32be", command=self.view_receipt).pack(fill="x", pady=6)
        FlatBtn(action_frame, text="Void Sale (Mgr)", bg="#ff3b30", hover_bg="#d70015", command=self.void_transaction).pack(fill="x", pady=6)

        ttk.Separator(action_frame, orient="horizontal").pack(fill="x", pady=16)

        # Bottom Summary Status Bar
        status_bar = tk.Frame(self, bg="#0f172a", padx=20, pady=8)
        status_bar.pack(fill="x", side="bottom")

        self.lbl_record_count = tk.Label(status_bar, text="Showing 0 sales", font=("Helvetica", 10), fg="#cbd5e1", bg="#0f172a")
        self.lbl_record_count.pack(side="left")

        self.lbl_total_sum = tk.Label(status_bar, text="Total Income: PHP 0.00", font=("Helvetica", 10, "bold"), fg="#4ade80", bg="#0f172a")
        self.lbl_total_sum.pack(side="right")

    def refresh(self):
        self.apply_filters()

    def reset_filters(self):
        self.search_var.set("")
        self.date_filter_var.set("All Time")
        self.status_filter_var.set("All")
        self.apply_filters()

    def apply_filters(self):
        for r in self.tree.get_children():
            self.tree.delete(r)

        query = """
            SELECT s.sale_id, s.si_number, s.sale_date, s.cashier_code, s.cashier_name, s.payment_method, 
                   s.total_amount, s.status, s.discount_type, s.discount_amount, s.pwd_id_number, s.voucher_code,
                   COALESCE(SUM(si.quantity), 0) as item_count
            FROM sales s
            LEFT JOIN sale_items si ON s.sale_id = si.sale_id
            WHERE 1=1
        """
        params = []

        search = self.search_var.get().strip()
        if search:
            query += " AND (s.si_number LIKE %s OR s.cashier_name LIKE %s OR s.cashier_code LIKE %s)"
            params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])

        date_opt = self.date_filter_var.get()
        now = datetime.now()
        if date_opt == "Today":
            query += " AND s.sale_date >= %s"
            params.append(now.strftime("%Y-%m-%d 00:00:00"))
        elif date_opt == "Yesterday":
            y_start = (now - timedelta(days=1)).strftime("%Y-%m-%d 00:00:00")
            y_end = (now - timedelta(days=1)).strftime("%Y-%m-%d 23:59:59")
            query += " AND s.sale_date BETWEEN %s AND %s"
            params.extend([y_start, y_end])
        elif date_opt == "This Week":
            w_start = (now - timedelta(days=now.weekday())).strftime("%Y-%m-%d 00:00:00")
            query += " AND s.sale_date >= %s"
            params.append(w_start)
        elif date_opt == "This Month":
            query += " AND s.sale_date >= %s"
            params.append(now.strftime("%Y-%m-01 00:00:00"))

        status_opt = self.status_filter_var.get()
        if status_opt != "All":
            query += " AND s.status = %s"
            params.append(status_opt)

        query += " GROUP BY s.sale_id ORDER BY s.sale_id DESC"

        try:
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute(query, params)
            rows = cursor.fetchall()
            conn.close()

            total_income = Decimal("0.00")
            for r in rows:
                s_id = r["sale_id"]
                si_no = r["si_number"]
                s_date = r["sale_date"].strftime("%Y-%m-%d %H:%M") if r["sale_date"] else ""
                cashier = f"{r['cashier_code']} {r['cashier_name']}"
                payment = r["payment_method"].upper()
                total = Decimal(str(r["total_amount"]))
                status = r["status"]
                item_count = r["item_count"]

                disc_amt = Decimal(str(r["discount_amount"])) if r.get("discount_amount") is not None else Decimal("0.00")
                disc_type = r.get("discount_type", "none")
                pwd_id = r.get("pwd_id_number")
                voucher = r.get("voucher_code")

                if pwd_id or disc_type == "pwd":
                    promo_desc = f"PWD 5% ({pwd_id})" if pwd_id else "PWD 5% Discount"
                elif voucher or disc_type == "voucher":
                    promo_desc = f"Voucher: {voucher}" if voucher else f"Voucher (-PHP {disc_amt:,.2f})"
                elif disc_amt > 0:
                    promo_desc = f"Promo (-PHP {disc_amt:,.2f})"
                else:
                    promo_desc = "None"

                if status == "completed":
                    total_income += total

                self.tree.insert("", "end", iid=str(s_id), values=(
                    s_id, si_no, s_date, cashier, item_count, payment, promo_desc, f"PHP {total:,.2f}", status.capitalize()
                ), tags=(status,))

            self.lbl_record_count.config(text=f"Showing {len(rows)} transaction records")
            self.lbl_total_sum.config(text=f"Total Net Sales Income: PHP {total_income:,.2f}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to fetch sales history: {e}")

    def _get_selected_sale_id(self) -> Optional[int]:
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("No Selection", "Please select a sale transaction from the table.", parent=self)
            return None
        return int(sel[0])

    def view_details(self):
        sale_id = self._get_selected_sale_id()
        if not sale_id:
            return

        try:
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM sales WHERE sale_id = %s", (sale_id,))
            sale = cursor.fetchone()
            cursor.execute("SELECT * FROM sale_items WHERE sale_id = %s", (sale_id,))
            items = cursor.fetchall()
            conn.close()

            if not sale:
                return

            win = tk.Toplevel(self)
            win.title(f"Sale Details — SI #{sale['si_number']}")
            win.geometry("550x520")
            win.configure(bg="#ffffff")
            win.transient(self)
            win.grab_set()

            top = tk.Frame(win, bg="#ffffff", padx=20, pady=16)
            top.pack(fill="x")
            tk.Label(top, text=f"Sales Invoice #{sale['si_number']}", font=("Helvetica", 14, "bold"), fg="#0f172a", bg="#ffffff").pack(anchor="w")
            date_str = sale["sale_date"].strftime("%Y-%m-%d %I:%M %p") if sale["sale_date"] else ""
            tk.Label(top, text=f"Date: {date_str} | Cashier: {sale['cashier_code']} {sale['cashier_name']}", font=("Helvetica", 10), fg="#64748b", bg="#ffffff").pack(anchor="w")

            items_frame = tk.Frame(win, bg="#ffffff", padx=20)
            items_frame.pack(fill="both", expand=True)

            tree_items = ttk.Treeview(items_frame, columns=("name", "price", "qty", "total"), show="headings", height=8)
            tree_items.heading("name", text="Item Name")
            tree_items.heading("price", text="Unit Price")
            tree_items.heading("qty", text="Qty")
            tree_items.heading("total", text="Line Total")

            tree_items.column("name", width=220)
            tree_items.column("price", width=90, anchor="center")
            tree_items.column("qty", width=60, anchor="center")
            tree_items.column("total", width=100, anchor="center")
            tree_items.pack(fill="both", expand=True)

            for it in items:
                tree_items.insert("", "end", values=(it["item_name"], f"PHP {Decimal(str(it['unit_price'])):,.2f}", it["quantity"], f"PHP {Decimal(str(it['line_total'])):,.2f}"))

            summary_frame = tk.Frame(win, bg="#f8fafc", padx=20, pady=16)
            summary_frame.pack(fill="x")

            subtotal = Decimal(str(sale["subtotal"]))
            discount = Decimal(str(sale["discount_amount"]))
            tax = Decimal(str(sale["tax_amount"]))
            total = Decimal(str(sale["total_amount"]))

            sum_text = (
                f"Subtotal: PHP {subtotal:,.2f}   |   Discount: PHP {discount:,.2f}   |   12% VAT: PHP {tax:,.2f}\n"
                f"TOTAL AMOUNT PAID: PHP {total:,.2f} ({sale['payment_method'].upper()})"
            )
            tk.Label(summary_frame, text=sum_text, font=("Helvetica", 10, "bold"), fg="#0f172a", bg="#f8fafc", justify="center").pack()

            FlatBtn(win, text="Close", bg="#475569", hover_bg="#334155", command=win.destroy).pack(pady=14)

        except Exception as e:
            messagebox.showerror("Error", f"Details error: {e}")

    def view_receipt(self):
        sale_id = self._get_selected_sale_id()
        if not sale_id:
            return

        try:
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM sales WHERE sale_id = %s", (sale_id,))
            sale = cursor.fetchone()
            cursor.execute("SELECT * FROM sale_items WHERE sale_id = %s", (sale_id,))
            items = cursor.fetchall()
            conn.close()

            if not sale:
                return

            receipt_text = generate_receipt_text(sale, items)

            win = tk.Toplevel(self)
            win.title(f"Sales Invoice — SI #{sale['si_number']}")
            win.geometry("390x700")
            win.configure(bg="#ffffff")
            win.transient(self)
            win.grab_set()

            # Close button anchored at bottom
            FlatBtn(win, text="Close", bg="#475569", hover_bg="#334155", pady=10, command=win.destroy).pack(side="bottom", fill="x", padx=16, pady=16)

            rf = tk.Frame(win, bg="#ffffff", highlightthickness=1, highlightbackground="#cbd5e1")
            rf.pack(side="top", fill="both", expand=True, padx=16, pady=(16, 10))

            sb = tk.Scrollbar(rf, orient="vertical")
            txt = tk.Text(rf, font=("Courier", 10), bg="#ffffff", fg="#0f172a", width=44, height=26, relief="flat", padx=8, pady=12, wrap="none", yscrollcommand=sb.set)
            sb.config(command=txt.yview)

            sb.pack(side="right", fill="y")
            txt.pack(side="left", fill="both", expand=True)

            txt.insert("1.0", receipt_text)
            txt.config(state="disabled")

        except Exception as e:
            messagebox.showerror("Error", f"Receipt error: {e}")

    def void_transaction(self):
        sale_id = self._get_selected_sale_id()
        if not sale_id:
            return

        # Requires Manager Verification & Password
        if not SecurityManager.prompt_manager_approval(self, title="Manager Password Authorization Required to Void Sale"):
            return

        try:
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT status, si_number FROM sales WHERE sale_id = %s", (sale_id,))
            row = cursor.fetchone()
            conn.close()

            if not row:
                return
            if row["status"] == "voided":
                messagebox.showwarning("Already Voided", f"SI #{row['si_number']} is already voided.", parent=self)
                return

        except Exception as e:
            messagebox.showerror("Error", f"Database error: {e}")
            return

        reason = simpledialog.askstring("Void Reason", "Enter reason for voiding transaction SI #" + row["si_number"] + ":", parent=self)
        if not reason:
            return

        # Atomic Void Transaction
        conn = None
        try:
            conn = get_connection()
            conn.autocommit = False
            cursor = conn.cursor(dictionary=True)

            cursor.execute("SELECT item_id, quantity FROM sale_items WHERE sale_id = %s", (sale_id,))
            sale_items = cursor.fetchall()

            for item in sale_items:
                i_id = item["item_id"]
                qty = item["quantity"]
                cursor.execute("UPDATE products SET stock_qty = stock_qty + %s WHERE item_id = %s", (qty, i_id))
                cursor.execute("INSERT INTO inventory_movements (item_id, movement_type, quantity, notes, reference_id) VALUES (%s, 'return', %s, %s, %s)", (i_id, qty, f"Void SI #{row['si_number']}: {reason}", sale_id))

            cursor.execute("UPDATE sales SET status = 'voided', voided_by_manager = 'Manager', void_reason = %s WHERE sale_id = %s", (reason.strip(), sale_id))

            conn.commit()
            conn.close()

            messagebox.showinfo("Void Complete", f"Transaction SI #{row['si_number']} has been voided by Manager. Items restored to stock.", parent=self)
            self.refresh()
            if self.controller and hasattr(self.controller, "frames"):
                if "inventory" in self.controller.frames and hasattr(self.controller.frames["inventory"], "refresh"):
                    self.controller.frames["inventory"].refresh()

        except Exception as e:
            if conn:
                conn.rollback()
                conn.close()
            messagebox.showerror("Void Failed", f"Failed to void transaction: {e}")
