# modules/analytics.py
# Analytics, Audit Logs, CSV Report Export & IT Code System Reset for SmartRetail Final Revision

from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta
from decimal import Decimal
import csv
import os

from db.connection import get_connection
from utils.ui import FlatBtn
from modules.auth import SecurityManager


class AnalyticsFrame(tk.Frame):
    def __init__(self, parent, controller=None, **kwargs):
        super().__init__(parent, bg="#f8fafc", **kwargs)
        self.controller = controller
        self._build_ui()
        self.refresh()

    # ── UI Layout ──────────────────────────────────────────────────────────
    def _build_ui(self):
        # Header & Filter Toolbar
        header = tk.Frame(self, bg="#0f172a", padx=20, pady=14)
        header.pack(fill="x")

        tk.Label(header, text="Business Analytics & Audit Reports", font=("Helvetica", 16, "bold"), fg="#ffffff", bg="#0f172a").pack(side="left")

        # Period Filter & Export Buttons
        toolbar = tk.Frame(header, bg="#0f172a")
        toolbar.pack(side="right")

        tk.Label(toolbar, text="Period: ", font=("Helvetica", 9, "bold"), fg="#cbd5e1", bg="#0f172a").pack(side="left")
        self.period_var = tk.StringVar(value="Last 30 Days")
        period_combo = ttk.Combobox(toolbar, textvariable=self.period_var, values=["Today", "Yesterday", "Last 7 Days", "Last 30 Days", "This Month", "All Time"], state="readonly", width=12)
        period_combo.pack(side="left", padx=4)
        period_combo.bind("<<ComboboxSelected>>", lambda e: self.refresh())

        FlatBtn(toolbar, text="Export CSV Report", bg="#34c759", hover_bg="#248a3d", padx=10, pady=4, command=self.export_csv_report).pack(side="left", padx=4)
        FlatBtn(toolbar, text="SYSTEM RESET (IT)", bg="#ff3b30", hover_bg="#d70015", padx=10, pady=4, command=self.system_hard_reset).pack(side="left", padx=4)

        # Notebook / Tabs
        notebook_frame = tk.Frame(self, bg="#f8fafc", padx=16, pady=16)
        notebook_frame.pack(fill="both", expand=True)

        self.notebook = ttk.Notebook(notebook_frame)
        self.notebook.pack(fill="both", expand=True)

        # Tab 1: Top Products
        self.tab_top = tk.Frame(self.notebook, bg="#ffffff", padx=10, pady=10)
        self.notebook.add(self.tab_top, text=" Top Bestsellers ")
        self._setup_top_tree()

        # Tab 2: Category Breakdown
        self.tab_cat = tk.Frame(self.notebook, bg="#ffffff", padx=10, pady=10)
        self.notebook.add(self.tab_cat, text=" Category Share ")
        self._setup_cat_tree()

        # Tab 3: Voided Sales Audit Log
        self.tab_void = tk.Frame(self.notebook, bg="#ffffff", padx=10, pady=10)
        self.notebook.add(self.tab_void, text=" Voided Sales Audit ")
        self._setup_void_tree()

        # Tab 4: PWD Discount Audit Log
        self.tab_pwd = tk.Frame(self.notebook, bg="#ffffff", padx=10, pady=10)
        self.notebook.add(self.tab_pwd, text=" PWD Discounts Log ")
        self._setup_pwd_tree()

        # Tab 5: Stock Movement Audit Log
        self.tab_move = tk.Frame(self.notebook, bg="#ffffff", padx=10, pady=10)
        self.notebook.add(self.tab_move, text=" Stock Movements ")
        self._setup_move_tree()

    def _setup_top_tree(self):
        cols = ("Rank", "Product Name", "Category", "Units Sold", "Revenue (PHP)")
        self.tree_top = ttk.Treeview(self.tab_top, columns=cols, show="headings")
        for c in cols:
            self.tree_top.heading(c, text=c)
            self.tree_top.column(c, width=120, anchor="center")
        self.tree_top.pack(fill="both", expand=True)

    def _setup_cat_tree(self):
        cols = ("Category", "Transactions", "Units Sold", "Total Revenue (PHP)", "Share (%)")
        self.tree_cat = ttk.Treeview(self.tab_cat, columns=cols, show="headings")
        for c in cols:
            self.tree_cat.heading(c, text=c)
            self.tree_cat.column(c, width=120, anchor="center")
        self.tree_cat.pack(fill="both", expand=True)

    def _setup_void_tree(self):
        cols = ("SI Number", "Date & Time", "Cashier", "Manager Authorizer", "Total Amount", "Void Reason")
        frame = tk.Frame(self.tab_void, bg="#ffffff")
        frame.pack(fill="both", expand=True)

        hint = tk.Label(frame, text="Double-click a row to view full Void Reason",
                        font=("Helvetica", 8), fg="#94a3b8", bg="#ffffff")
        hint.pack(anchor="e", padx=4, pady=(0, 2))

        tree_frame = tk.Frame(frame, bg="#ffffff")
        tree_frame.pack(fill="both", expand=True)

        self.tree_void = ttk.Treeview(tree_frame, columns=cols, show="headings")
        sb_v = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree_void.yview)
        sb_h = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree_void.xview)
        self.tree_void.configure(yscrollcommand=sb_v.set, xscrollcommand=sb_h.set)

        col_widths = {"SI Number": 130, "Date & Time": 130, "Cashier": 130,
                      "Manager Authorizer": 130, "Total Amount": 110, "Void Reason": 300}
        for c in cols:
            self.tree_void.heading(c, text=c)
            self.tree_void.column(c, width=col_widths.get(c, 110), anchor="center", minwidth=80)

        sb_v.pack(side="right", fill="y")
        sb_h.pack(side="bottom", fill="x")
        self.tree_void.pack(side="left", fill="both", expand=True)
        self.tree_void.bind("<Double-1>", lambda e: self._show_detail_popup(
            self.tree_void, title_col="SI Number", detail_col="Void Reason", label="Void Reason"
        ))

    def _setup_pwd_tree(self):
        cols = ("SI Number", "Date & Time", "Cashier", "PWD / Senior ID No", "Subtotal", "5% Discount Amount", "Final Total")
        self.tree_pwd = ttk.Treeview(self.tab_pwd, columns=cols, show="headings")
        for c in cols:
            self.tree_pwd.heading(c, text=c)
            self.tree_pwd.column(c, width=110, anchor="center")
        self.tree_pwd.pack(fill="both", expand=True)

    def _setup_move_tree(self):
        cols = ("ID", "Date & Time", "Product Name", "Movement Type", "Quantity", "Notes")
        frame = tk.Frame(self.tab_move, bg="#ffffff")
        frame.pack(fill="both", expand=True)

        hint = tk.Label(frame, text="Double-click a row to view full Notes",
                        font=("Helvetica", 8), fg="#94a3b8", bg="#ffffff")
        hint.pack(anchor="e", padx=4, pady=(0, 2))

        tree_frame = tk.Frame(frame, bg="#ffffff")
        tree_frame.pack(fill="both", expand=True)

        self.tree_move = ttk.Treeview(tree_frame, columns=cols, show="headings")
        sb_v = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree_move.yview)
        sb_h = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree_move.xview)
        self.tree_move.configure(yscrollcommand=sb_v.set, xscrollcommand=sb_h.set)

        col_widths = {"ID": 60, "Date & Time": 130, "Product Name": 160,
                      "Movement Type": 110, "Quantity": 80, "Notes": 400}
        for c in cols:
            self.tree_move.heading(c, text=c)
            self.tree_move.column(c, width=col_widths.get(c, 110), anchor="center", minwidth=60)

        sb_v.pack(side="right", fill="y")
        sb_h.pack(side="bottom", fill="x")
        self.tree_move.pack(side="left", fill="both", expand=True)
        self.tree_move.bind("<Double-1>", lambda e: self._show_detail_popup(
            self.tree_move, title_col="Product Name", detail_col="Notes", label="Notes"
        ))

    def _show_detail_popup(self, tree: ttk.Treeview, title_col: str, detail_col: str, label: str):
        """Show a popup dialog with the full text of a cell when a row is double-clicked."""
        sel = tree.selection()
        if not sel:
            return
        values = tree.item(sel[0])["values"]
        cols = [tree.heading(c)["text"] for c in tree["columns"]]
        try:
            title_val = values[cols.index(title_col)] if title_col in cols else ""
            detail_val = values[cols.index(detail_col)] if detail_col in cols else ""
        except (ValueError, IndexError):
            return

        if not detail_val or str(detail_val).strip() in ("", "N/A"):
            messagebox.showinfo(label, f"No {label} recorded for this entry.", parent=self)
            return

        win = tk.Toplevel(self)
        win.title(f"{label} — {title_val}")
        win.geometry("460x260")
        win.resizable(False, False)
        win.configure(bg="#ffffff")
        win.transient(self)
        win.grab_set()

        hdr = tk.Frame(win, bg="#0f172a", padx=18, pady=12)
        hdr.pack(fill="x")
        tk.Label(hdr, text=label, font=("Helvetica", 11, "bold"), fg="#ffffff", bg="#0f172a").pack(anchor="w")
        tk.Label(hdr, text=str(title_val), font=("Helvetica", 9), fg="#94a3b8", bg="#0f172a").pack(anchor="w")

        body = tk.Frame(win, bg="#ffffff", padx=18, pady=14)
        body.pack(fill="both", expand=True)

        txt = tk.Text(body, font=("Helvetica", 11), bg="#f8fafc", fg="#0f172a", relief="flat",
                      wrap="word", height=6, highlightthickness=1, highlightbackground="#e2e8f0")
        txt.pack(fill="both", expand=True)
        txt.insert("1.0", str(detail_val))
        txt.config(state="disabled")

        FlatBtn(win, text="Close", bg="#475569", hover_bg="#334155", pady=9,
                command=win.destroy).pack(fill="x", padx=18, pady=(0, 14))

    def refresh(self):
        where_clause, params = self._get_period_clause("s.sale_date")

        try:
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)

            # 1. Top Bestsellers
            for r in self.tree_top.get_children():
                self.tree_top.delete(r)
            top_sql = f"""
                SELECT p.item_name, p.category, SUM(si.quantity) as units_sold, SUM(si.line_total) as total_rev
                FROM sale_items si
                JOIN sales s ON si.sale_id = s.sale_id
                JOIN products p ON si.item_id = p.item_id
                WHERE s.status = 'completed' {where_clause}
                GROUP BY si.item_id ORDER BY units_sold DESC LIMIT 20
            """
            cursor.execute(top_sql, params)
            for idx, r in enumerate(cursor.fetchall(), start=1):
                self.tree_top.insert("", "end", values=(idx, r["item_name"], r["category"], r["units_sold"], f"PHP {Decimal(str(r['total_rev'])):,.2f}"))

            # 2. Category Share
            for r in self.tree_cat.get_children():
                self.tree_cat.delete(r)
            cat_sql = f"""
                SELECT p.category, COUNT(DISTINCT s.sale_id) as tx_cnt, SUM(si.quantity) as total_units, SUM(si.line_total) as cat_rev
                FROM sale_items si
                JOIN sales s ON si.sale_id = s.sale_id
                JOIN products p ON si.item_id = p.item_id
                WHERE s.status = 'completed' {where_clause}
                GROUP BY p.category ORDER BY cat_rev DESC
            """
            cursor.execute(cat_sql, params)
            cat_rows = cursor.fetchall()
            tot_all = sum([r["cat_rev"] for r in cat_rows]) or 1
            for r in cat_rows:
                rev = Decimal(str(r["cat_rev"]))
                share = (rev / tot_all) * 100
                self.tree_cat.insert("", "end", values=(r["category"], r["tx_cnt"], r["total_units"], f"PHP {rev:,.2f}", f"{share:.1f}%"))

            # 3. Voided Sales — filtered by period
            for r in self.tree_void.get_children():
                self.tree_void.delete(r)
            void_where, void_params = self._get_period_clause("sale_date")
            cursor.execute(
                f"SELECT si_number, sale_date, cashier_name, voided_by_manager, total_amount, void_reason "
                f"FROM sales WHERE status = 'voided' {void_where} ORDER BY sale_id DESC",
                void_params
            )
            for r in cursor.fetchall():
                dt_s = r["sale_date"].strftime("%Y-%m-%d %H:%M") if r["sale_date"] else ""
                self.tree_void.insert("", "end", values=(r["si_number"], dt_s, r["cashier_name"], r["voided_by_manager"] or "Manager", f"PHP {Decimal(str(r['total_amount'])):,.2f}", r["void_reason"] or "N/A"))

            # 4. PWD Discounts Log — filtered by period
            for r in self.tree_pwd.get_children():
                self.tree_pwd.delete(r)
            pwd_where, pwd_params = self._get_period_clause("sale_date")
            cursor.execute(
                f"SELECT si_number, sale_date, cashier_name, pwd_id_number, subtotal, discount_amount, total_amount "
                f"FROM sales WHERE pwd_id_number IS NOT NULL AND status = 'completed' {pwd_where} ORDER BY sale_id DESC",
                pwd_params
            )
            for r in cursor.fetchall():
                dt_s = r["sale_date"].strftime("%Y-%m-%d %H:%M") if r["sale_date"] else ""
                self.tree_pwd.insert("", "end", values=(r["si_number"], dt_s, r["cashier_name"], r["pwd_id_number"], f"PHP {Decimal(str(r['subtotal'])):,.2f}", f"PHP {Decimal(str(r['discount_amount'])):,.2f}", f"PHP {Decimal(str(r['total_amount'])):,.2f}"))

            # 5. Stock Movements Log — filtered by period
            for r in self.tree_move.get_children():
                self.tree_move.delete(r)
            move_where, move_params = self._get_period_clause("m.moved_at")
            cursor.execute(
                f"""SELECT m.movement_id, m.moved_at, p.item_name, m.movement_type, m.quantity, m.notes
                    FROM inventory_movements m JOIN products p ON m.item_id = p.item_id
                    WHERE 1=1 {move_where}
                    ORDER BY m.movement_id DESC""",
                move_params
            )
            for r in cursor.fetchall():
                dt_s = r["moved_at"].strftime("%Y-%m-%d %H:%M") if r["moved_at"] else ""
                self.tree_move.insert("", "end", values=(r["movement_id"], dt_s, r["item_name"], r["movement_type"].upper(), r["quantity"], r["notes"] or ""))

            conn.close()
        except Exception as e:
            print(f"Analytics refresh error: {e}")

    def _get_period_clause(self, date_col: str = "s.sale_date"):
        """Returns (WHERE fragment, params list) for the given date column.
        Pass the column exactly as it should appear in SQL, e.g. 's.sale_date',
        'sale_date', or 'm.moved_at'.
        """
        period = self.period_var.get()
        now = datetime.now()
        where = ""
        params = []

        if period == "Today":
            where = f"AND {date_col} >= %s"
            params.append(now.strftime("%Y-%m-%d 00:00:00"))
        elif period == "Yesterday":
            y_start = (now - timedelta(days=1)).strftime("%Y-%m-%d 00:00:00")
            y_end = (now - timedelta(days=1)).strftime("%Y-%m-%d 23:59:59")
            where = f"AND {date_col} BETWEEN %s AND %s"
            params.extend([y_start, y_end])
        elif period == "Last 7 Days":
            where = f"AND {date_col} >= %s"
            params.append((now - timedelta(days=7)).strftime("%Y-%m-%d 00:00:00"))
        elif period == "Last 30 Days":
            where = f"AND {date_col} >= %s"
            params.append((now - timedelta(days=30)).strftime("%Y-%m-%d 00:00:00"))
        elif period == "This Month":
            where = f"AND {date_col} >= %s"
            params.append(now.strftime("%Y-%m-01 00:00:00"))

        return where, params

    def export_csv_report(self):
        folder = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "reports")
        os.makedirs(folder, exist_ok=True)
        filepath = os.path.join(folder, f"daily_sales_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")

        try:
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM sales ORDER BY sale_id DESC")
            sales = cursor.fetchall()
            conn.close()

            if sales:
                keys = sales[0].keys()
                with open(filepath, "w", newline="", encoding="utf-8") as f:
                    dict_writer = csv.DictWriter(f, keys)
                    dict_writer.writeheader()
                    dict_writer.writerows(sales)
                messagebox.showinfo("Report Exported", f"Daily sales report exported to:\n{filepath}", parent=self)
            else:
                messagebox.showwarning("No Data", "No sales records to export.", parent=self)
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export CSV: {e}", parent=self)

    def system_hard_reset(self):
        if not SecurityManager.prompt_it_code(self, action_name="FULL SYSTEM HARD RESET"):
            return

        if not messagebox.askyesno("DANGER: SYSTEM HARD RESET", "Are you 100% sure you want to clear all sales, reset inventory stock, and restore default settings?", icon="warning", parent=self):
            return

        try:
            from db.setup import initialize_database
            ok, msg = initialize_database()
            if ok:
                messagebox.showinfo("System Reset Complete", "Database has been reset to default state.", parent=self)
                self.refresh()
            else:
                messagebox.showerror("Reset Error", msg, parent=self)
        except Exception as e:
            messagebox.showerror("Reset Error", f"Failed to reset system: {e}", parent=self)
