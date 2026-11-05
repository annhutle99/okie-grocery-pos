# modules/auth.py
# Authentication Portal, Shift Logging & Security Verification for SmartRetail Final Revision

from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from datetime import date
from db.connection import get_connection
from utils.ui import FlatBtn


class LoginDialog(tk.Frame):
    """
    Full-Screen Role Selection & Sign-In Portal for O!kie Grocery (Manager vs Cashier).
    Renders as an overlay Frame filling the main window.
    """

    def __init__(self, parent, on_login_success=None):
        super().__init__(parent, bg="#c8102e")
        self.on_login_success = on_login_success
        self.user_data = None
        # Fill entire parent window immediately before building sub-widgets to prevent frame flash
        self.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.lift()
        self._build_ui()

    def _build_ui(self):
        # ── Left Brand Panel (O!kie Red Theme) ────────────────────────────
        left = tk.Frame(self, bg="#c8102e", width=440)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)

        # Vertical centering frame for brand content
        brand_center = tk.Frame(left, bg="#c8102e")
        brand_center.place(relx=0.5, rely=0.5, anchor="center")

        # Official O!kie Grocery Logo Picture
        self._draw_brand_logo(brand_center)

        tk.Label(
            brand_center,
            text="O!kie Grocery",
            font=("Helvetica", 32, "bold"),
            fg="#ffffff",
            bg="#c8102e"
        ).pack()

        tk.Label(
            brand_center,
            text="Supermarket POS & Inventory System",
            font=("Helvetica", 12, "bold"),
            fg="#fef08a",
            bg="#c8102e"
        ).pack(pady=(4, 0))

        # Divider line in bright sunshine yellow accent
        tk.Frame(brand_center, bg="#facc15", height=3, width=220).pack(pady=24)

        # Feature bullets with custom vector icons (No Emojis)
        features = [
            ("inventory", "Inventory & Stock Management"),
            ("pos", "POS Cashier & Receipt Printing"),
            ("analytics", "Analytics & Sales Reports"),
            ("voucher", "Voucher & Discount System"),
        ]
        for icon_type, text in features:
            self._draw_feature_row(brand_center, icon_type, text)

        # ── Right Form Panel ──────────────────────────────────────────────
        right = tk.Frame(self, bg="#f8fafc")
        right.pack(side="right", fill="both", expand=True)

        # Center the login card vertically and horizontally on the right side
        form_card = tk.Frame(right, bg="#ffffff",
                             highlightbackground="#e2e8f0",
                             highlightthickness=1, bd=0)
        form_card.place(relx=0.5, rely=0.5, anchor="center", width=440)

        # Card Header
        card_hdr = tk.Frame(form_card, bg="#c8102e", padx=24, pady=22)
        card_hdr.pack(fill="x")

        tk.Label(card_hdr, text="Sign In", font=("Helvetica", 20, "bold"),
                 fg="#ffffff", bg="#c8102e").pack(anchor="w")
        tk.Label(card_hdr, text="Select your role and enter credentials",
                 font=("Helvetica", 10), fg="#fef08a", bg="#c8102e").pack(anchor="w", pady=(4, 0))

        # Role tabs (custom, for O!kie branding)
        self._active_role = tk.StringVar(value="cashier")

        tab_bar = tk.Frame(form_card, bg="#f1f5f9", padx=4, pady=4)
        tab_bar.pack(fill="x")

        self._tab_btns = {}
        for role, label in [("cashier", "Cashier Sign In"), ("manager", "Manager Sign In")]:
            btn = tk.Label(
                tab_bar,
                text=label,
                font=("Helvetica", 10, "bold"),
                padx=20, pady=8,
                cursor="hand2",
                bg="#c8102e" if role == "cashier" else "#f1f5f9",
                fg="#ffffff" if role == "cashier" else "#64748b"
            )
            btn.pack(side="left", fill="x", expand=True)
            btn.bind("<Button-1>", lambda e, r=role: self._switch_role(r))
            self._tab_btns[role] = btn

        # Form Body
        self._form_body = tk.Frame(form_card, bg="#ffffff", padx=28, pady=24)
        self._form_body.pack(fill="x")

        self._user_var = tk.StringVar()
        self._pass_var = tk.StringVar()
        self._build_form_body()

    def _build_form_body(self):
        for w in self._form_body.winfo_children():
            w.destroy()

        role = self._active_role.get()

        tk.Label(self._form_body, text="User ID / Username:",
                 font=("Helvetica", 10, "bold"), fg="#334155", bg="#ffffff").pack(anchor="w", pady=(0, 4))

        user_entry = tk.Entry(self._form_body, textvariable=self._user_var,
                              font=("Helvetica", 11), bg="#f1f5f9", fg="#0f172a",
                              relief="flat", highlightthickness=1,
                              highlightbackground="#e2e8f0", highlightcolor="#c8102e")
        user_entry.pack(fill="x", ipady=8, pady=(0, 16))

        tk.Label(self._form_body, text="Password:",
                 font=("Helvetica", 10, "bold"), fg="#334155", bg="#ffffff").pack(anchor="w", pady=(0, 4))

        pass_entry = tk.Entry(self._form_body, textvariable=self._pass_var, show="•",
                              font=("Helvetica", 11), bg="#f1f5f9", fg="#0f172a",
                              relief="flat", highlightthickness=1,
                              highlightbackground="#e2e8f0", highlightcolor="#c8102e")
        # Forgot Password link (Only available for Manager Sign In)
        if role == "manager":
            pass_entry.pack(fill="x", ipady=8, pady=(0, 6))

            forgot_row = tk.Frame(self._form_body, bg="#ffffff")
            forgot_row.pack(fill="x", pady=(0, 16))

            forgot_lbl = tk.Label(
                forgot_row,
                text="Forgot Password?",
                font=("Helvetica", 9, "bold"),
                fg="#d97706",
                bg="#ffffff",
                cursor="hand2"
            )
            forgot_lbl.pack(side="right")
            forgot_lbl.bind("<Button-1>", lambda e: self._open_forgot_password())
        else:
            pass_entry.pack(fill="x", ipady=8, pady=(0, 24))

        user_entry.bind("<Return>", lambda e: self._attempt_login())
        pass_entry.bind("<Return>", lambda e: self._attempt_login())

        btn_color = "#c8102e" if role == "cashier" else "#d97706"
        btn_hover = "#a50b23" if role == "cashier" else "#b45309"
        FlatBtn(
            self._form_body,
            text=f"SIGN IN AS {role.upper()}",
            bg=btn_color,
            hover_bg=btn_hover,
            pady=13,
            font=("Helvetica", 11, "bold"),
            command=self._attempt_login
        ).pack(fill="x")

        # Footer hint
        tk.Label(self._form_body, text="© O!kie Grocery System",
                 font=("Helvetica", 9), fg="#94a3b8", bg="#ffffff").pack(pady=(20, 0))

        # Focus username field
        user_entry.focus()

    def _open_forgot_password(self):
        role = self._active_role.get()
        username = self._user_var.get().strip()
        dlg = ForgotPasswordDialog(self, default_username=username, default_role=role)
        self.wait_window(dlg)
        if hasattr(dlg, "reset_username") and dlg.reset_username:
            self._user_var.set(dlg.reset_username)
            self._pass_var.set("")

    def _switch_role(self, role: str):
        self._active_role.set(role)
        for r, btn in self._tab_btns.items():
            if r == role:
                btn.config(bg="#c8102e" if role == "cashier" else "#d97706", fg="#ffffff")
            else:
                btn.config(bg="#f1f5f9", fg="#64748b")
        self._user_var.set("")
        self._pass_var.set("")
        self._build_form_body()

    def _attempt_login(self):
        username_input = self._user_var.get().strip()
        password_input = self._pass_var.get().strip()
        role = self._active_role.get()

        if not username_input or not password_input:
            messagebox.showwarning("Input Required", "Please enter User ID / Username and Password.", parent=self)
            return

        try:
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)

            cursor.execute("""
                SELECT * FROM users
                WHERE (username = %s OR user_code = %s) AND password = %s AND role = %s AND is_active = 1
            """, (username_input, username_input, password_input, role))
            user = cursor.fetchone()

            if not user:
                conn.close()
                self._pass_var.set("")  # clear password on failed login
                messagebox.showerror("Sign In Failed", f"Invalid {role.capitalize()} credentials or account inactive.", parent=self)
                return

            # If Cashier, log shift clock-in
            shift_id = None
            if role == "cashier":
                today_str = date.today().strftime("%Y-%m-%d")
                cursor.execute("""
                    INSERT INTO cashier_shifts (user_id, cashier_code, cashier_name, shift_date, time_in)
                    VALUES (%s, %s, %s, %s, NOW())
                """, (user["user_id"], user["user_code"], user["full_name"], today_str))
                shift_id = cursor.lastrowid
                conn.commit()

            conn.close()

            user["active_shift_id"] = shift_id
            self.user_data = user

            # Remove login screen and reveal main app
            self.destroy()

            if self.on_login_success:
                self.on_login_success(user)

        except Exception as e:
            messagebox.showerror("Error", f"Login error: {e}", parent=self)

    def _draw_brand_logo(self, parent):
        import os
        from PIL import Image, ImageTk

        logo_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "images", "logo.png")
        if os.path.exists(logo_path):
            try:
                img = Image.open(logo_path)
                img = img.resize((160, 160), Image.Resampling.LANCZOS)
                self.logo_tk = ImageTk.PhotoImage(img)
                lbl = tk.Label(parent, image=self.logo_tk, bg="#c8102e")
                lbl.pack(pady=(0, 16))
                return
            except Exception as e:
                print(f"Error loading logo image: {e}")

        # Fallback Canvas
        canvas = tk.Canvas(parent, width=96, height=96, bg="#c8102e", highlightthickness=0, bd=0)
        canvas.pack(pady=(0, 16))
        canvas.create_rectangle(6, 6, 90, 90, fill="#a50b23", outline="#facc15", width=2)
        canvas.create_polygon(26, 30, 70, 30, 64, 54, 32, 54, fill="#c8102e", outline="#ffffff", width=2)
        canvas.create_oval(35, 64, 43, 72, fill="#facc15", outline="#ffffff", width=1.5)
        canvas.create_oval(55, 64, 63, 72, fill="#facc15", outline="#ffffff", width=1.5)

    def _draw_feature_row(self, parent, icon_type, text):
        row = tk.Frame(parent, bg="#c8102e")
        row.pack(anchor="w", pady=6)

        c = tk.Canvas(row, width=24, height=24, bg="#c8102e", highlightthickness=0, bd=0)
        c.pack(side="left", padx=(0, 12))

        if icon_type == "inventory":
            # Isometric box icon
            c.create_polygon(12, 3, 20, 7, 12, 11, 4, 7, fill="#facc15", outline="#ffffff", width=1.5)
            c.create_polygon(4, 7, 12, 11, 12, 20, 4, 16, fill="#a50b23", outline="#ffffff", width=1.5)
            c.create_polygon(20, 7, 12, 11, 12, 20, 20, 16, fill="#c8102e", outline="#ffffff", width=1.5)
        elif icon_type == "pos":
            # POS / Receipt Terminal icon
            c.create_rectangle(4, 3, 20, 21, fill="#a50b23", outline="#facc15", width=1.5)
            c.create_line(7, 7, 17, 7, fill="#ffffff", width=1.5)
            c.create_line(7, 11, 17, 11, fill="#facc15", width=1.5)
            c.create_line(7, 15, 14, 15, fill="#ffffff", width=1.5)
        elif icon_type == "analytics":
            # Bar chart icon
            c.create_rectangle(3, 14, 7, 20, fill="#a50b23", outline="#ffffff", width=1)
            c.create_rectangle(9, 9, 13, 20, fill="#facc15", outline="#ffffff", width=1)
            c.create_rectangle(15, 4, 19, 20, fill="#ffffff", outline="#ffffff", width=1)
            c.create_line(2, 20, 21, 20, fill="#ffffff", width=1.5)
        elif icon_type == "voucher":
            # Ticket / Tag icon
            c.create_rectangle(3, 6, 21, 18, fill="#a50b23", outline="#facc15", width=1.5)
            c.create_line(12, 6, 12, 18, fill="#ffffff", dash=(2, 2), width=1)
            c.create_oval(1, 10, 5, 14, fill="#c8102e", outline="#c8102e")
            c.create_oval(19, 10, 23, 14, fill="#c8102e", outline="#c8102e")

        tk.Label(row, text=text, font=("Helvetica", 11, "bold"), fg="#ffffff", bg="#c8102e").pack(side="left")




class SecurityManager:
    """Helper class for Manager Verification and IT Code Authorization Modals."""

    @staticmethod
    def prompt_manager_approval(parent, title="Manager Verification Required") -> bool:
        """Prompts for Manager password to approve actions like voiding cart items."""
        pwd = simpledialog.askstring(title, "Enter Manager Password to authorize action:", show="•", parent=parent)
        if pwd is None:
            # User clicked 'Cancel' or closed dialog
            return False

        if not pwd.strip():
            messagebox.showwarning("Input Required", "Please enter the Manager Password.", parent=parent)
            return False

        try:
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT user_code, full_name FROM users WHERE role = 'manager' AND password = %s AND is_active = 1", (pwd.strip(),))
            mgr = cursor.fetchone()
            conn.close()

            if mgr:
                return True
            else:
                messagebox.showerror("Unauthorized", "Invalid Manager password.", parent=parent)
                return False
        except Exception as e:
            messagebox.showerror("Error", f"Database error: {e}", parent=parent)
            return False

    @staticmethod
    def prompt_it_code(parent, action_name="this action") -> bool:
        """Prompts for Special IT Admin Code required for Manager Password Change & System Reset."""
        code = simpledialog.askstring("IT Security Authorization", f"Enter Special IT Code to perform {action_name}:", show="•", parent=parent)
        if code is None:
            # User clicked 'Cancel' or closed dialog
            return False

        if not code.strip():
            messagebox.showwarning("Input Required", "Please enter the Special IT Code.", parent=parent)
            return False

        try:
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT config_value FROM system_config WHERE config_key = 'it_special_code'")
            row = cursor.fetchone()
            conn.close()

            valid_code = row["config_value"] if row else "IT-ADMIN-9999"
            if code.strip() == valid_code:
                return True
            else:
                messagebox.showerror("Security Denial", "Invalid IT Special Code. Access denied.", parent=parent)
                return False
        except Exception as e:
            messagebox.showerror("Error", f"Database error: {e}", parent=parent)
            return False


def clock_out_shift(shift_id: int):
    """Clock out an active cashier shift and update total shift sales metrics."""
    if not shift_id:
        return
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT COUNT(*) AS total_count, COALESCE(SUM(total_amount), 0) AS total_amount FROM sales WHERE shift_id = %s", (shift_id,))
        res = cursor.fetchone()
        cnt = res["total_count"] if res else 0
        amt = res["total_amount"] if res else 0

        cursor.execute("""
            UPDATE cashier_shifts
            SET time_out = NOW(), total_sales_count = %s, total_sales_amount = %s
            WHERE shift_id = %s AND time_out IS NULL
        """, (cnt, amt, shift_id))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error clocking out shift {shift_id}: {e}")


class ForgotPasswordDialog(tk.Toplevel):
    """
    IT Support Authorized Password Reset Dialog for Manager & Cashier Accounts.
    Requires Special IT Code / Password to reset account password.
    """

    def __init__(self, parent, default_username: str = "", default_role: str = "manager"):
        super().__init__(parent)
        self.title("Forgot Password — IT Support Authorization")
        self.geometry("460x520")
        self.resizable(False, False)
        self.configure(bg="#ffffff")
        self.transient(parent)
        self.grab_set()

        self.default_username = default_username
        self.default_role = default_role
        self.reset_username = None

        self._build_ui()

    def _build_ui(self):
        # Header banner
        hdr_color = "#d97706"
        hdr = tk.Frame(self, bg=hdr_color, padx=22, pady=18)
        hdr.pack(fill="x")

        tk.Label(hdr, text="Reset Manager Password", font=("Helvetica", 14, "bold"),
                 fg="#ffffff", bg=hdr_color).pack(anchor="w")
        tk.Label(hdr, text="Requires IT Support Special Code authorization", font=("Helvetica", 9),
                 fg="#fef08a", bg=hdr_color).pack(anchor="w", pady=(2, 0))

        body = tk.Frame(self, bg="#ffffff", padx=26, pady=20)
        body.pack(fill="both", expand=True)

        # 1. User ID / Username
        tk.Label(body, text="Manager User ID / Username:", font=("Helvetica", 10, "bold"),
                 fg="#334155", bg="#ffffff").pack(anchor="w", pady=(0, 4))
        self._user_var = tk.StringVar(value=self.default_username)
        u_entry = tk.Entry(body, textvariable=self._user_var, font=("Helvetica", 11),
                           bg="#f1f5f9", fg="#0f172a", relief="flat", highlightthickness=1,
                           highlightbackground="#cbd5e1", highlightcolor="#d97706")
        u_entry.pack(fill="x", ipady=6, pady=(0, 12))

        # 2. IT Support Special Code / Password
        tk.Label(body, text="Special IT Code / Password:", font=("Helvetica", 10, "bold"),
                 fg="#c8102e", bg="#ffffff").pack(anchor="w", pady=(0, 4))
        self._it_code_var = tk.StringVar()
        it_entry = tk.Entry(body, textvariable=self._it_code_var, show="•", font=("Helvetica", 11),
                            bg="#fffbeb", fg="#0f172a", relief="flat", highlightthickness=1,
                            highlightbackground="#fcd34d", highlightcolor="#d97706")
        it_entry.pack(fill="x", ipady=6, pady=(0, 12))

        # 3. New Password
        tk.Label(body, text="New Password:", font=("Helvetica", 10, "bold"),
                 fg="#334155", bg="#ffffff").pack(anchor="w", pady=(0, 4))
        self._pass1_var = tk.StringVar()
        p1_entry = tk.Entry(body, textvariable=self._pass1_var, show="•", font=("Helvetica", 11),
                            bg="#f1f5f9", fg="#0f172a", relief="flat", highlightthickness=1,
                            highlightbackground="#cbd5e1", highlightcolor="#d97706")
        p1_entry.pack(fill="x", ipady=6, pady=(0, 12))

        # 4. Confirm New Password
        tk.Label(body, text="Confirm New Password:", font=("Helvetica", 10, "bold"),
                 fg="#334155", bg="#ffffff").pack(anchor="w", pady=(0, 4))
        self._pass2_var = tk.StringVar()
        p2_entry = tk.Entry(body, textvariable=self._pass2_var, show="•", font=("Helvetica", 11),
                            bg="#f1f5f9", fg="#0f172a", relief="flat", highlightthickness=1,
                            highlightbackground="#cbd5e1", highlightcolor="#d97706")
        p2_entry.pack(fill="x", ipady=6, pady=(0, 20))

        # Action Buttons
        btn_frame = tk.Frame(body, bg="#ffffff")
        btn_frame.pack(fill="x")

        FlatBtn(btn_frame, text="CANCEL", bg="#64748b", hover_bg="#475569", pady=10,
                command=self.destroy).pack(side="left", fill="x", expand=True, padx=(0, 6))

        FlatBtn(btn_frame, text="RESET PASSWORD", bg="#d97706", hover_bg="#b45309", pady=10,
                command=self._execute_reset).pack(side="right", fill="x", expand=True, padx=(6, 0))

        if not self.default_username:
            u_entry.focus()
        else:
            it_entry.focus()

    def _execute_reset(self):
        username = self._user_var.get().strip()
        it_code = self._it_code_var.get().strip()
        new_pass = self._pass1_var.get().strip()
        confirm_pass = self._pass2_var.get().strip()

        if not username:
            messagebox.showwarning("Input Required", "Please enter Manager User ID / Username.", parent=self)
            return
        if not it_code:
            messagebox.showwarning("Input Required", "Please enter Special IT Code.", parent=self)
            return
        if not new_pass:
            messagebox.showwarning("Input Required", "Please enter a new password.", parent=self)
            return
        if new_pass != confirm_pass:
            messagebox.showerror("Password Mismatch", "New password and Confirm password do not match.", parent=self)
            return

        try:
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)

            # 1. Verify Special IT Code
            cursor.execute("SELECT config_value FROM system_config WHERE config_key = 'it_special_code'")
            row = cursor.fetchone()
            valid_code = row["config_value"] if row else "IT-ADMIN-9999"

            if it_code != valid_code:
                conn.close()
                messagebox.showerror("Authorization Failure", "Invalid Special IT Code. Password reset denied.", parent=self)
                return

            # 2. Check if manager exists
            cursor.execute("""
                SELECT user_id, username, full_name, role FROM users
                WHERE (username = %s OR user_code = %s) AND role = 'manager' AND is_active = 1
            """, (username, username))
            user = cursor.fetchone()

            if not user:
                conn.close()
                messagebox.showerror("Account Not Found", f"No active Manager account found with Username/ID '{username}'.", parent=self)
                return

            # 3. Update password in DB
            cursor.execute("UPDATE users SET password = %s WHERE user_id = %s", (new_pass, user["user_id"]))
            conn.commit()
            conn.close()

            self.reset_username = user["username"]
            messagebox.showinfo(
                "Password Reset Successful",
                f"Password for {user['role'].capitalize()} '{user['full_name']}' ({user['username']}) has been updated successfully!\n\nYou may now sign in with your new password.",
                parent=self
            )
            self.destroy()

        except Exception as e:
            messagebox.showerror("Database Error", f"Failed to reset password: {e}", parent=self)

