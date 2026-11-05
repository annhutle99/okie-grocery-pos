# modules/dashboard.py
# Executive Business Dashboard & Management Portal for SmartRetail Final Revision

from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from decimal import Decimal
from datetime import date
import os
from PIL import Image, ImageTk

from db.connection import get_connection
from utils.ui import FlatBtn, CardFrame, PrivacyToggle
from modules.auth import SecurityManager


# ── Add Cashier Account Modal ──────────────────────────────────────────────────
class AddCashierDialog(tk.Toplevel):
    """
    Unified Form Modal for Creating New Cashier Accounts with Strict Validation.
    """
    def __init__(self, parent, on_success=None):
        super().__init__(parent)
        self.on_success = on_success
        self.title("Add New Cashier Account")
        self.geometry("440x480")
        self.configure(bg="#ffffff")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self._build_ui()

    def _build_ui(self):
        # Header
        hdr = tk.Frame(self, bg="#0f172a", padx=20, pady=16)
        hdr.pack(fill="x")

        tk.Label(hdr, text="Create Cashier Account", font=("Helvetica", 14, "bold"), fg="#ffffff", bg="#0f172a").pack(anchor="w")
        tk.Label(hdr, text="Fill out cashier credentials and access details", font=("Helvetica", 9), fg="#94a3b8", bg="#0f172a").pack(anchor="w", pady=(2, 0))

        # Form body
        form = tk.Frame(self, bg="#ffffff", padx=24, pady=20)
        form.pack(fill="both", expand=True)

        # Auto-suggest Cashier Code
        suggested_code = self._get_next_cashier_code()

        fields = [
            ("Cashier Code (e.g. CSH-102):", "code", suggested_code),
            ("Cashier Username:", "username", ""),
            ("Cashier Full Name:", "fullname", ""),
            ("Password:", "password", ""),
        ]

        self.vars = {}
        for label_text, var_key, default_val in fields:
            tk.Label(form, text=label_text, font=("Helvetica", 9, "bold"), fg="#334155", bg="#ffffff").pack(anchor="w", pady=(0, 2))
            var = tk.StringVar(value=default_val)
            self.vars[var_key] = var
            
            show_char = "•" if var_key == "password" else ""
            entry = tk.Entry(form, textvariable=var, show=show_char, font=("Helvetica", 11), bg="#f1f5f9", fg="#0f172a", relief="flat", highlightthickness=1, highlightbackground="#cbd5e1", highlightcolor="#007aff")
            entry.pack(fill="x", ipady=6, pady=(0, 12))

        FlatBtn(
            form,
            text="CREATE CASHIER ACCOUNT",
            bg="#16a34a",
            hover_bg="#15803d",
            pady=12,
            font=("Helvetica", 10, "bold"),
            command=self._save_cashier
        ).pack(fill="x", pady=(10, 0))

    def _get_next_cashier_code(self) -> str:
        try:
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT user_code FROM users WHERE role = 'cashier' ORDER BY user_id DESC LIMIT 1")
            row = cursor.fetchone()
            conn.close()
            if row and row["user_code"].startswith("CSH-"):
                try:
                    num = int(row["user_code"].replace("CSH-", "")) + 1
                    return f"CSH-{num:03d}"
                except ValueError:
                    pass
        except Exception:
            pass
        return "CSH-102"

    def _save_cashier(self):
        code = self.vars["code"].get().strip()
        uname = self.vars["username"].get().strip()
        name = self.vars["fullname"].get().strip()
        pwd = self.vars["password"].get().strip()

        # Validation: Check for empty fields
        missing = []
        if not code: missing.append("Cashier Code")
        if not uname: missing.append("Username")
        if not name: missing.append("Full Name")
        if not pwd: missing.append("Password")

        if missing:
            messagebox.showwarning(
                "Input Required",
                "Please fill out all required fields:\n• " + "\n• ".join(missing),
                parent=self
            )
            return

        try:
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)

            cursor.execute("SELECT user_id FROM users WHERE user_code = %s OR username = %s", (code, uname))
            existing = cursor.fetchone()
            if existing:
                conn.close()
                messagebox.showerror("Duplicate Credentials", f"Cashier Code '{code}' or Username '{uname}' already exists.", parent=self)
                return

            cursor.execute("""
                INSERT INTO users (user_code, username, password, full_name, role, is_active)
                VALUES (%s, %s, %s, %s, 'cashier', 1)
            """, (code, uname, pwd, name))
            conn.commit()
            conn.close()

            messagebox.showinfo("Success", f"Cashier account '{name}' ({code}) created successfully!", parent=self.master)
            if self.on_success:
                self.on_success()
            self.destroy()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to create cashier: {e}", parent=self)


class DashboardFrame(tk.Frame):
    def __init__(self, parent, controller=None, **kwargs):
        super().__init__(parent, bg="#f8fafc", **kwargs)
        self.controller = controller
        # Default to False: Automatically HIDE balance upon login for business privacy
        self.show_privacy_balance = False
        self._build_ui()
        self.refresh()

    def switch_tab(self, tab_name: str):
        if callable(self.controller):
            self.controller(tab_name)
        elif hasattr(self.controller, "show_frame"):
            self.controller.show_frame(tab_name)

    # ── UI Layout ──────────────────────────────────────────────────────────
    def _build_ui(self):
        # Header Bar
        header = tk.Frame(self, bg="#0f172a", padx=20, pady=14)
        header.pack(fill="x")

        tk.Label(header, text="O!kie Grocery — Executive Business Dashboard", font=("Helvetica", 16, "bold"), fg="#ffffff", bg="#0f172a").pack(side="left")

        # Privacy Toggle — starts in HIDDEN mode
        self.privacy_btn = PrivacyToggle(header, on_toggle=self._on_privacy_toggle, initial_visible=self.show_privacy_balance)
        self.privacy_btn.pack(side="right", padx=10)

        # Financial Summary KPI Cards
        cards_row = tk.Frame(self, bg="#f8fafc", padx=20, pady=16)
        cards_row.pack(fill="x")
        cards_row.columnconfigure((0, 1, 2, 3, 4), weight=1, uniform="kpi_cards")

        self.stat_vars = {}
        card_defs = [
            ("total_cost", "Wholesale Cost Value", "#0f172a", "PHP ••••••••"),
            ("total_retail", "Retail Inventory Value", "#007aff", "PHP ••••••••"),
            ("net_profit", "Potential Stock Margin", "#34c759", "PHP ••••••••"),
            ("realized_pnl", "Realized Cash P&L", "#dc2626", "PHP ••••••••"),
            ("today_sales", "Today's Sales Income", "#d97706", "PHP ••••••••"),
        ]

        self.card_labels = {}
        for i, (key, title, color, default) in enumerate(card_defs):
            card = CardFrame(cards_row, bg="#ffffff", padx=14, pady=14)
            card.grid(row=0, column=i, padx=5, sticky="nsew")

            tk.Label(card, text=title, font=("Helvetica", 9, "bold"), fg="#64748b", bg="#ffffff").pack(anchor="w")
            var = tk.StringVar(value=default)
            self.stat_vars[key] = var
            lbl = tk.Label(card, textvariable=var, font=("Helvetica", 15, "bold"), fg=color, bg="#ffffff")
            lbl.pack(anchor="w", pady=(4, 0))
            self.card_labels[key] = lbl

        # Quick Manager Tools Row
        mgr_tools = CardFrame(self, bg="#ffffff", padx=16, pady=12)
        mgr_tools.pack(fill="x", padx=20, pady=(0, 16))

        tk.Label(mgr_tools, text="Manager Utilities:", font=("Helvetica", 10, "bold"), fg="#0f172a", bg="#ffffff").pack(side="left", padx=(0, 10))

        FlatBtn(mgr_tools, text="Cashier Shift Logs", bg="#007aff", hover_bg="#0056b3", command=self._open_shift_logs).pack(side="left", padx=4)
        FlatBtn(mgr_tools, text="Manage Cashiers", bg="#0f172a", hover_bg="#1e293b", command=self._open_cashier_manager).pack(side="left", padx=4)
        FlatBtn(mgr_tools, text="Manage Vouchers", bg="#af52de", hover_bg="#8e32be", command=self._open_voucher_manager).pack(side="left", padx=4)
        FlatBtn(mgr_tools, text="Change Manager Password (IT)", bg="#ff3b30", hover_bg="#d70015", command=self._change_manager_password).pack(side="right")

        # Expiry & Low Stock Alert Tables (with Barcode & Double-Click Image Preview)
        tables_row = tk.Frame(self, bg="#f8fafc", padx=20, pady=0)
        tables_row.pack(fill="both", expand=True)
        tables_row.columnconfigure((0, 1), weight=1)

        # ── Left: Low Stock Alerts ─────────────────────────────────────────
        left_box = CardFrame(tables_row, bg="#ffffff", padx=12, pady=12)
        left_box.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        tk.Label(left_box, text="Low Stock Alerts", font=("Helvetica", 11, "bold"), fg="#ea580c", bg="#ffffff").pack(anchor="w", pady=(0, 8))

        cols1 = ("Barcode", "Product Name", "Category", "Stock", "Reorder", "Photo")
        self.tree_low = ttk.Treeview(left_box, columns=cols1, show="headings", height=9)

        w1 = {"Barcode": 135, "Product Name": 180, "Category": 110, "Stock": 60, "Reorder": 70, "Photo": 60}
        for c in cols1:
            self.tree_low.heading(c, text=c)
            stretch = True if c in ("Product Name", "Barcode") else False
            anchor = "w" if c in ("Product Name", "Barcode") else "center"
            self.tree_low.column(c, width=w1.get(c, 80), anchor=anchor, stretch=stretch)

        vsb1 = ttk.Scrollbar(left_box, orient="vertical", command=self.tree_low.yview)
        self.tree_low.configure(yscrollcommand=vsb1.set)
        self.tree_low.pack(side="left", fill="both", expand=True)
        vsb1.pack(side="right", fill="y")

        self.tree_low.bind("<Double-1>", lambda e: self._view_alert_photo(self.tree_low))

        # ── Right: Expiration Date Alerts ──────────────────────────────────
        right_box = CardFrame(tables_row, bg="#ffffff", padx=12, pady=12)
        right_box.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        tk.Label(right_box, text="Expiration Date Alerts", font=("Helvetica", 11, "bold"), fg="#dc2626", bg="#ffffff").pack(anchor="w", pady=(0, 8))

        cols2 = ("Barcode", "Product Name", "Category", "Expiry Date", "Days Left", "Photo")
        self.tree_exp = ttk.Treeview(right_box, columns=cols2, show="headings", height=9)

        w2 = {"Barcode": 135, "Product Name": 170, "Category": 105, "Expiry Date": 95, "Days Left": 90, "Photo": 60}
        for c in cols2:
            self.tree_exp.heading(c, text=c)
            stretch = True if c in ("Product Name", "Barcode") else False
            anchor = "w" if c in ("Product Name", "Barcode") else "center"
            self.tree_exp.column(c, width=w2.get(c, 80), anchor=anchor, stretch=stretch)

        vsb2 = ttk.Scrollbar(right_box, orient="vertical", command=self.tree_exp.yview)
        self.tree_exp.configure(yscrollcommand=vsb2.set)
        self.tree_exp.pack(side="left", fill="both", expand=True)
        vsb2.pack(side="right", fill="y")

        self.tree_exp.bind("<Double-1>", lambda e: self._view_alert_photo(self.tree_exp))

    def _on_privacy_toggle(self, is_visible: bool):
        self.show_privacy_balance = is_visible
        self.refresh()

    def _view_alert_photo(self, tree_widget: ttk.Treeview):
        """Open photo preview modal when double-clicking a row in alert tables."""
        sel = tree_widget.selection()
        if not sel:
            return
        item_vals = tree_widget.item(sel[0], "values")
        if not item_vals:
            return
        barcode = item_vals[0]
        prod_name = item_vals[1]

        try:
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT image_path, item_name FROM products WHERE barcode = %s OR item_name = %s", (barcode, prod_name))
            prod = cursor.fetchone()
            conn.close()

            if prod and prod["image_path"] and os.path.exists(prod["image_path"]):
                win = tk.Toplevel(self)
                win.title(f"Product Photo — {prod['item_name']}")
                win.geometry("500x500")
                win.configure(bg="#ffffff")
                win.transient(self)

                img = Image.open(prod["image_path"])
                img.thumbnail((450, 450))
                tk_img = ImageTk.PhotoImage(img)

                lbl = tk.Label(win, image=tk_img, bg="#ffffff")
                lbl.image = tk_img
                lbl.pack(padx=20, pady=20)
            else:
                messagebox.showinfo("No Photo Available", f"No photo has been captured for '{prod_name}'.\n\nYou can take a camera photo in Inventory Management.", parent=self)
        except Exception as e:
            messagebox.showerror("Error", f"Could not load image: {e}", parent=self)

    def on_navigate(self):
        """Called by main.py when the user navigates TO this tab. Resets privacy then reloads data."""
        self.show_privacy_balance = False
        if hasattr(self, "privacy_btn"):
            self.privacy_btn.reset_to_hidden()
        self.refresh()

    def refresh(self):
        try:
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)

            # Calculate Stock Wholesale Cost, Retail Value, Net Profit
            cursor.execute("""
                SELECT 
                    COALESCE(SUM(cost_price * stock_qty), 0) AS total_cost,
                    COALESCE(SUM(unit_price * stock_qty), 0) AS total_retail
                FROM products WHERE is_active = 1
            """)
            inv_stats = cursor.fetchone()

            tot_cost = Decimal(str(inv_stats["total_cost"]))
            tot_retail = Decimal(str(inv_stats["total_retail"]))
            net_profit = tot_retail - tot_cost

            # All-time Sales Revenue to calculate Realized Cash P&L
            cursor.execute("""
                SELECT COALESCE(SUM(total_amount), 0) AS total_sales
                FROM sales WHERE status = 'completed'
            """)
            sales_row = cursor.fetchone()
            total_sales = Decimal(str(sales_row["total_sales"]))
            realized_pnl = total_sales - tot_cost

            # Today's Completed Sales Income
            cursor.execute("""
                SELECT COALESCE(SUM(total_amount), 0) AS today_sales
                FROM sales 
                WHERE status = 'completed' AND DATE(sale_date) = CURDATE()
            """)
            today_sales = Decimal(str(cursor.fetchone()["today_sales"]))

            if self.show_privacy_balance:
                self.stat_vars["total_cost"].set(f"PHP {tot_cost:,.2f}")
                self.stat_vars["total_retail"].set(f"PHP {tot_retail:,.2f}")
                self.stat_vars["net_profit"].set(f"PHP {net_profit:,.2f}")
                self.stat_vars["today_sales"].set(f"PHP {today_sales:,.2f}")

                if realized_pnl < 0:
                    self.stat_vars["realized_pnl"].set(f"-PHP {abs(realized_pnl):,.2f}")
                    self.card_labels["realized_pnl"].config(fg="#dc2626")   # Red: Unrecovered stock investment
                else:
                    self.stat_vars["realized_pnl"].set(f"+PHP {realized_pnl:,.2f}")
                    self.card_labels["realized_pnl"].config(fg="#16a34a")   # Green: Net profit earned
            else:
                self.stat_vars["total_cost"].set("PHP ••••••••")
                self.stat_vars["total_retail"].set("PHP ••••••••")
                self.stat_vars["net_profit"].set("PHP ••••••••")
                self.stat_vars["realized_pnl"].set("PHP ••••••••")
                self.stat_vars["today_sales"].set("PHP ••••••••")

            # Load Low Stock Alerts (with Barcode & Photo indicator)
            for r in self.tree_low.get_children():
                self.tree_low.delete(r)
            cursor.execute("""
                SELECT barcode, item_name, category, stock_qty, reorder_level, image_path 
                FROM products WHERE stock_qty <= reorder_level AND is_active = 1 
                ORDER BY stock_qty ASC LIMIT 25
            """)
            for p in cursor.fetchall():
                has_photo = "YES" if p["image_path"] and os.path.exists(p["image_path"]) else "NO"
                bc = p["barcode"] or "N/A"
                self.tree_low.insert("", "end", values=(bc, p["item_name"], p["category"], p["stock_qty"], p["reorder_level"], has_photo))

            # Load Expiration Alerts (with Barcode & Photo indicator)
            for r in self.tree_exp.get_children():
                self.tree_exp.delete(r)
            cursor.execute("""
                SELECT barcode, item_name, category, expiry_date, image_path 
                FROM products WHERE expiry_date IS NOT NULL AND is_active = 1 
                ORDER BY expiry_date ASC LIMIT 25
            """)
            today_d = date.today()
            for p in cursor.fetchall():
                exp_d = p["expiry_date"]
                days_left = (exp_d - today_d).days
                days_str = f"{days_left} Days" if days_left >= 0 else "EXPIRED!"
                has_photo = "YES" if p["image_path"] and os.path.exists(p["image_path"]) else "NO"
                bc = p["barcode"] or "N/A"
                self.tree_exp.insert("", "end", values=(bc, p["item_name"], p["category"], exp_d.strftime("%Y-%m-%d"), days_str, has_photo))

            conn.close()
        except Exception as e:
            print(f"Dashboard refresh error: {e}")

    # ── Manager Tools Dialogs ──────────────────────────────────────────────
    def _open_shift_logs(self):
        win = tk.Toplevel(self)
        win.title("Cashier Shift Time Logs")
        win.geometry("600x400")
        win.configure(bg="#ffffff")
        win.transient(self)

        tk.Label(win, text="Cashier Duty Shift Logs", font=("Helvetica", 14, "bold"), fg="#0f172a", bg="#ffffff").pack(pady=12)

        cols = ("Shift ID", "Date", "Cashier Code", "Cashier Name", "Time In", "Time Out", "Hours Worked")
        tree = ttk.Treeview(win, columns=cols, show="headings", height=10)
        for c in cols:
            tree.heading(c, text=c)
            tree.column(c, width=80, anchor="center")
        tree.pack(fill="both", expand=True, padx=16, pady=10)

        try:
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM cashier_shifts ORDER BY shift_id DESC LIMIT 50")
            for s in cursor.fetchall():
                t_in = s["time_in"].strftime("%H:%M:%S") if s["time_in"] else ""
                t_out = s["time_out"].strftime("%H:%M:%S") if s["time_out"] else "ON DUTY"
                hrs = f"{float(s['total_hours']):.2f} hrs" if s["total_hours"] else "-"
                tree.insert("", "end", values=(s["shift_id"], s["shift_date"], s["cashier_code"], s["cashier_name"], t_in, t_out, hrs))
            conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load shifts: {e}")




    def _open_cashier_manager(self):
        win = tk.Toplevel(self)
        win.title("Manage Cashier Accounts")
        win.geometry("650x450")
        win.configure(bg="#ffffff")
        win.transient(self)

        tk.Label(win, text="Cashier Account Management", font=("Helvetica", 14, "bold"), fg="#0f172a", bg="#ffffff").pack(pady=12)

        cols = ("ID", "Code", "Username", "Full Name", "Status")
        tree = ttk.Treeview(win, columns=cols, show="headings", height=8)
        for c in cols:
            tree.heading(c, text=c)
            tree.column(c, width=110, anchor="center")
        tree.pack(fill="both", expand=True, padx=16, pady=6)

        def reload_cashiers():
            for r in tree.get_children():
                tree.delete(r)
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM users WHERE role = 'cashier' ORDER BY user_id DESC")
            for u in cursor.fetchall():
                tree.insert("", "end", iid=str(u["user_id"]), values=(u["user_id"], u["user_code"], u["username"], u["full_name"], "Active" if u["is_active"] else "Inactive"))
            conn.close()

        reload_cashiers()

        btn_bar = tk.Frame(win, bg="#ffffff", pady=10)
        btn_bar.pack(fill="x", padx=16)

        def add_cashier():
            AddCashierDialog(win, on_success=reload_cashiers)

        def reset_pass():
            sel = tree.selection()
            if not sel:
                messagebox.showwarning("Selection Required", "Please select a cashier from the table first.", parent=win)
                return
            
            uid = sel[0]
            new_pwd = simpledialog.askstring("Reset Password", "Enter New Password for Cashier:", show="•", parent=win)
            if new_pwd is None:
                return

            if not new_pwd.strip():
                messagebox.showwarning("Input Required", "Password cannot be empty. Please enter a valid password.", parent=win)
                return

            try:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("UPDATE users SET password = %s WHERE user_id = %s", (new_pwd.strip(), uid))
                conn.commit()
                conn.close()
                messagebox.showinfo("Success", "Cashier password updated successfully!", parent=win)
                reload_cashiers()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to reset password: {e}", parent=win)

        def toggle_status():
            sel = tree.selection()
            if not sel:
                messagebox.showwarning("Selection Required", "Please select a cashier from the table first.", parent=win)
                return
            
            uid = sel[0]
            try:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("UPDATE users SET is_active = NOT is_active WHERE user_id = %s", (uid,))
                conn.commit()
                conn.close()
                reload_cashiers()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to update cashier status: {e}", parent=win)

        FlatBtn(btn_bar, text="Add New Cashier", bg="#16a34a", hover_bg="#15803d", command=add_cashier).pack(side="left", padx=4)
        FlatBtn(btn_bar, text="Reset Password", bg="#2563eb", hover_bg="#1d4ed8", command=reset_pass).pack(side="left", padx=4)
        FlatBtn(btn_bar, text="Toggle Active/Deactivate", bg="#dc2626", hover_bg="#b91c1c", command=toggle_status).pack(side="left", padx=4)

    def _open_voucher_manager(self):
        import random
        import string
        from datetime import datetime, timedelta, date

        win = tk.Toplevel(self)
        win.title("Voucher Management & Expiration Tracker")
        win.geometry("820x600")
        win.configure(bg="#ffffff")
        win.transient(self)

        # Header
        top_hdr = tk.Frame(win, bg="#0f172a", padx=16, pady=12)
        top_hdr.pack(fill="x")
        tk.Label(top_hdr, text="Voucher Manager & Expiration Tracker", font=("Helvetica", 14, "bold"), fg="#ffffff", bg="#0f172a").pack(side="left")

        # Creation Panel (CardFrame)
        create_card = CardFrame(win, bg="#ffffff", padx=16, pady=12)
        create_card.pack(fill="x", padx=16, pady=12)

        tk.Label(create_card, text="Create New Single-Use Voucher", font=("Helvetica", 11, "bold"), fg="#0f172a", bg="#ffffff").grid(row=0, column=0, columnspan=6, sticky="w", pady=(0, 8))

        # Row 1: Code & Discount
        tk.Label(create_card, text="Voucher Code:", font=("Helvetica", 9, "bold"), fg="#334155", bg="#ffffff").grid(row=1, column=0, sticky="w", padx=(0, 6))
        code_var = tk.StringVar()
        code_ent = tk.Entry(create_card, textvariable=code_var, font=("Helvetica", 10), width=15, bg="#f1f5f9", relief="flat")
        code_ent.grid(row=1, column=1, sticky="w", ipady=3, padx=(0, 4))

        def auto_gen():
            rand_code = "SAVE-" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
            code_var.set(rand_code)

        FlatBtn(create_card, text="Auto Code", bg="#64748b", hover_bg="#475569", padx=6, pady=2, command=auto_gen).grid(row=1, column=2, sticky="w", padx=(0, 16))

        tk.Label(create_card, text="Discount:", font=("Helvetica", 9, "bold"), fg="#334155", bg="#ffffff").grid(row=1, column=3, sticky="w", padx=(0, 6))
        val_var = tk.StringVar(value="50.00")
        tk.Entry(create_card, textvariable=val_var, font=("Helvetica", 10), width=8, bg="#f1f5f9", relief="flat").grid(row=1, column=4, sticky="w", ipady=3, padx=(0, 4))

        type_var = tk.StringVar(value="fixed")
        type_combo = ttk.Combobox(create_card, textvariable=type_var, values=["fixed", "percent"], state="readonly", width=8)
        type_combo.grid(row=1, column=5, sticky="w")

        # Row 2: Valid Until / Expiration Date
        tk.Label(create_card, text="Valid Until (YYYY-MM-DD):", font=("Helvetica", 9, "bold"), fg="#334155", bg="#ffffff").grid(row=2, column=0, sticky="w", pady=(10, 0), padx=(0, 6))

        default_exp = (date.today() + timedelta(days=30)).strftime("%Y-%m-%d")
        exp_var = tk.StringVar(value=default_exp)

        exp_ent = tk.Entry(create_card, textvariable=exp_var, font=("Helvetica", 10), width=15, bg="#f1f5f9", relief="flat")
        exp_ent.grid(row=2, column=1, sticky="w", ipady=3, pady=(10, 0), padx=(0, 4))

        exp_preset_frame = tk.Frame(create_card, bg="#ffffff")
        exp_preset_frame.grid(row=2, column=2, columnspan=3, sticky="w", pady=(10, 0))

        def set_exp(days):
            if days is None:
                exp_var.set("")
            else:
                exp_var.set((date.today() + timedelta(days=days)).strftime("%Y-%m-%d"))

        FlatBtn(exp_preset_frame, text="+7 Days", bg="#e2e8f0", fg="#334155", hover_bg="#cbd5e1", padx=4, pady=2, command=lambda: set_exp(7)).pack(side="left", padx=2)
        FlatBtn(exp_preset_frame, text="+30 Days", bg="#e2e8f0", fg="#334155", hover_bg="#cbd5e1", padx=4, pady=2, command=lambda: set_exp(30)).pack(side="left", padx=2)
        FlatBtn(exp_preset_frame, text="No Expiry", bg="#e2e8f0", fg="#334155", hover_bg="#cbd5e1", padx=4, pady=2, command=lambda: set_exp(None)).pack(side="left", padx=2)

        def create_v():
            c = code_var.get().strip().upper()
            val_str = val_var.get().strip()
            t = type_var.get()
            exp_str = exp_var.get().strip()

            if not c:
                messagebox.showwarning("Input Required", "Please enter or generate a voucher code.", parent=win)
                return
            try:
                val = float(val_str)
                if val <= 0:
                    raise ValueError("Discount value must be positive.")
            except ValueError:
                messagebox.showerror("Invalid Value", "Please enter a valid discount value.", parent=win)
                return

            exp_val = None
            if exp_str:
                try:
                    exp_val = datetime.strptime(exp_str, "%Y-%m-%d").date()
                except ValueError:
                    messagebox.showerror("Invalid Date", "Expiration date must be in YYYY-MM-DD format (or leave blank).", parent=win)
                    return

            try:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO vouchers (voucher_code, discount_type, discount_value, expiry_date) VALUES (%s, %s, %s, %s)",
                    (c, t, val, exp_val)
                )
                conn.commit()
                conn.close()
                messagebox.showinfo("Success", f"Voucher '{c}' created successfully!", parent=win)
                code_var.set("")
                reload_vouchers()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to create voucher: {e}", parent=win)

        FlatBtn(create_card, text="CREATE VOUCHER", bg="#9333ea", hover_bg="#7e22ce", padx=10, pady=5, command=create_v).grid(row=2, column=5, sticky="e", pady=(10, 0))

        # Existing Vouchers Table Section
        list_frame = CardFrame(win, bg="#ffffff", padx=12, pady=12)
        list_frame.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        tbl_hdr = tk.Frame(list_frame, bg="#ffffff")
        tbl_hdr.pack(fill="x", pady=(0, 8))

        tk.Label(tbl_hdr, text="Active & Redeemed Voucher Inventory", font=("Helvetica", 11, "bold"), fg="#0f172a", bg="#ffffff").pack(side="left")

        def revoke_voucher():
            sel = tree.selection()
            if not sel:
                messagebox.showwarning("Select Voucher", "Please select a voucher from the table to delete/revoke.", parent=win)
                return
            vid = sel[0]
            code = tree.item(vid, "values")[1]
            if messagebox.askyesno("Confirm Revoke", f"Are you sure you want to delete/revoke voucher '{code}'?", parent=win):
                try:
                    conn = get_connection()
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM vouchers WHERE voucher_id = %s", (vid,))
                    conn.commit()
                    conn.close()
                    messagebox.showinfo("Success", f"Voucher '{code}' has been removed.", parent=win)
                    reload_vouchers()
                except Exception as e:
                    messagebox.showerror("Error", f"Could not delete voucher: {e}", parent=win)

        FlatBtn(tbl_hdr, text="Refresh", bg="#0f172a", hover_bg="#1e293b", padx=10, pady=3, command=lambda: reload_vouchers()).pack(side="right", padx=(4, 0))
        FlatBtn(tbl_hdr, text="Delete / Revoke Voucher", bg="#dc2626", hover_bg="#b91c1c", padx=10, pady=3, command=revoke_voucher).pack(side="right")

        tree_box = tk.Frame(list_frame, bg="#ffffff")
        tree_box.pack(fill="both", expand=True)

        cols = ("ID", "Voucher Code", "Type", "Discount Value", "Valid Until", "Status", "Redeemed Date")
        tree = ttk.Treeview(tree_box, columns=cols, show="headings", height=10)

        widths = {"ID": 50, "Voucher Code": 140, "Type": 80, "Discount Value": 110, "Valid Until": 110, "Status": 110, "Redeemed Date": 140}
        for col in cols:
            tree.heading(col, text=col)
            tree.column(col, width=widths.get(col, 100), anchor="center")

        tree.pack(side="left", fill="both", expand=True)
        vsb = ttk.Scrollbar(tree_box, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")

        # Right-click context menu to delete voucher
        ctx_menu = tk.Menu(win, tearoff=0)
        ctx_menu.add_command(label="Delete / Revoke Voucher", command=revoke_voucher)

        def show_ctx_menu(event):
            item = tree.identify_row(event.y)
            if item:
                tree.selection_set(item)
                ctx_menu.tk_popup(event.x_root, event.y_root)

        tree.bind("<Button-2>", show_ctx_menu)
        tree.bind("<Button-3>", show_ctx_menu)

        def reload_vouchers():
            for r in tree.get_children():
                tree.delete(r)
            try:
                conn = get_connection()
                cursor = conn.cursor(dictionary=True)
                cursor.execute("SELECT * FROM vouchers ORDER BY voucher_id DESC")
                vouchers = cursor.fetchall()
                conn.close()

                today_d = date.today()
                for v in vouchers:
                    v_id = v["voucher_id"]
                    code = v["voucher_code"]
                    v_type = v["discount_type"].capitalize()
                    val = f"PHP {v['discount_value']:,.2f}" if v["discount_type"] == "fixed" else f"{v['discount_value']}%"
                    exp = v["expiry_date"].strftime("%Y-%m-%d") if v.get("expiry_date") else "No Expiry"

                    if v["is_redeemed"]:
                        status = "REDEEMED"
                    elif v.get("expiry_date") and v["expiry_date"] < today_d:
                        status = "EXPIRED"
                    else:
                        status = "ACTIVE"

                    r_date = v["redeemed_at"].strftime("%Y-%m-%d %H:%M") if v.get("redeemed_at") else "-"
                    tree.insert("", "end", iid=str(v_id), values=(v_id, code, v_type, val, exp, status, r_date))
            except Exception as e:
                print(f"Error loading vouchers: {e}")

        reload_vouchers()

    def _change_manager_password(self):
        if not SecurityManager.prompt_it_code(self, action_name="Manager Password Change"):
            return

        new_pwd = simpledialog.askstring("New Manager Password", "Enter your new Manager password:", show="•", parent=self)
        if new_pwd is None:
            return
        if not new_pwd.strip():
            messagebox.showwarning("Input Required", "New password cannot be empty.", parent=self)
            return

        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET password = %s WHERE role = 'manager'", (new_pwd.strip(),))
            conn.commit()
            conn.close()
            messagebox.showinfo("Success", "Manager password updated successfully!", parent=self)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to update password: {e}", parent=self)
