# main.py
# Main Entry Point for SmartRetail Application (Final Revision - 100% Light Mode)

from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox
import sys
import os
from datetime import datetime

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db.setup import initialize_database
from modules.auth import LoginDialog, clock_out_shift
from modules.dashboard import DashboardFrame
from modules.inventory import InventoryFrame
from modules.cashier import CashierFrame
from modules.history import SalesHistoryFrame
from modules.analytics import AnalyticsFrame
from utils.ui import FlatBtn
from utils.splash import SplashScreen


class LightNavItem(tk.Label):
    """Clean Light Mode sidebar navigation item."""

    def __init__(self, parent, text: str, key: str, command, **kwargs):
        super().__init__(
            parent,
            text=f"   {text}",
            font=("Helvetica", 11, "bold"),
            bg="#ffffff",
            fg="#475569",
            anchor="w",
            padx=16,
            pady=12,
            cursor="hand2",
            **kwargs
        )
        self.key = key
        self.command = command
        self.is_active = False

        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", lambda e: self.command(self.key))

    def _on_enter(self, event):
        if not self.is_active:
            self.config(bg="#f1f5f9", fg="#0f172a")

    def _on_leave(self, event):
        if not self.is_active:
            self.config(bg="#ffffff", fg="#475569")

    def set_active(self, active: bool):
        self.is_active = active
        if active:
            self.config(bg="#c8102e", fg="#ffffff")
        else:
            self.config(bg="#ffffff", fg="#475569")


class SmartRetailApp(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("O!kie Grocery — POS & Business Inventory System")
        
        # Auto-maximize window to full screen dimensions
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        self.geometry(f"{screen_w}x{screen_h}+0+0")
        self.minsize(1024, 720)
        self.configure(bg="#f8fafc")

        try:
            self.state('zoomed')
        except Exception:
            pass

        self.current_user = None
        self.active_shift_id = None

        # Initialize Database
        db_ok, db_msg = initialize_database()
        if not db_ok:
            messagebox.showerror("Database Initialization Error", f"Could not initialize database:\n{db_msg}")

        # Setup TTK Light Mode Styles
        self._setup_styles()

        # Build Main Frame Layout
        self._create_layout()

        # Intercept window close to ensure cashier shift clock-out
        self.protocol("WM_DELETE_WINDOW", self._on_app_close)

        # Start Clock
        self._update_clock()

        # Hide root window while video splash screen plays full screen
        self.withdraw()
        self.after(50, self._start_splash)

    def _start_splash(self):
        SplashScreen(self, on_done=self._show_login)

    def _show_login(self):
        # Create or lift LoginDialog while root window is still hidden or before deiconifying
        if not hasattr(self, '_login_overlay') or not self._login_overlay or not self._login_overlay.winfo_exists():
            self._login_overlay = LoginDialog(self, on_login_success=self._on_login_success)
        else:
            self._login_overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
            self._login_overlay.lift()

        try:
            self.state('zoomed')
        except Exception:
            pass
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"{sw}x{sh}+0+0")
        self.update_idletasks()

        self.deiconify()
        self.lift()
        self.focus_force()

    def _on_login_success(self, user_data: dict):
        self.current_user = user_data
        self.active_shift_id = user_data.get("active_shift_id")

        role = user_data.get("role", "cashier")
        full_name = user_data.get("full_name", "User")
        user_code = user_data.get("user_code", "")

        # Update User Info Label in Header
        self.lbl_user_info.config(text=f"User: {full_name} ({user_code})  |  Role: {role.upper()}")

        # Update Sidebar Nav based on Role
        if role == "cashier":
            for key, btn in self.nav_buttons.items():
                if key == "cashier":
                    btn.pack(fill="x", pady=2)
                else:
                    btn.pack_forget()
            default_view = "cashier"
            # Pass cashier user info to POS frame
            if "cashier" in self.frames and hasattr(self.frames["cashier"], "set_user_info"):
                self.frames["cashier"].set_user_info(user_data)
        else:
            # Manager menu: Dashboard, Inventory, History, Analytics (No Cashier POS)
            for key, btn in self.nav_buttons.items():
                if key == "cashier":
                    btn.pack_forget()
                else:
                    btn.pack(fill="x", pady=2)
            default_view = "dashboard"

        # Show Main Window & Auto Maximize to Full Screen
        self.deiconify()
        try:
            self.state('zoomed')
        except Exception:
            pass
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"{sw}x{sh}+0+0")

        self.show_frame(default_view)

    def _setup_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")

        # Configure Clean Apple Light Mode Palette for Treeview & TTK widgets
        style.configure(
            "Treeview",
            background="#ffffff",
            foreground="#0f172a",
            fieldbackground="#ffffff",
            font=("Helvetica", 10),
            rowheight=34,
            borderwidth=1,
            relief="solid"
        )
        style.configure(
            "Treeview.Heading",
            font=("Helvetica", 10, "bold"),
            background="#f8fafc",
            foreground="#334155",
            relief="flat",
            padding=(6, 6)
        )
        style.map("Treeview", background=[("selected", "#007aff")], foreground=[("selected", "#ffffff")])
        style.map("Treeview.Heading", background=[("active", "#e2e8f0")])

        style.configure("TLabelframe", background="#ffffff", relief="solid", borderwidth=1, bordercolor="#e2e8f0")
        style.configure("TLabelframe.Label", font=("Helvetica", 10, "bold"), foreground="#1e293b", background="#ffffff")

        style.configure("TNotebook", background="#f1f5f9", borderwidth=0)
        style.configure("TNotebook.Tab", font=("Helvetica", 10, "bold"), padding=(16, 8), background="#e2e8f0", foreground="#475569")
        style.map("TNotebook.Tab", background=[("selected", "#c8102e")], foreground=[("selected", "#ffffff")])

    def _create_layout(self):
        # 1. Top Header Bar
        header = tk.Frame(self, bg="#ffffff", height=54, highlightbackground="#e2e8f0", highlightthickness=1)
        header.pack(side="top", fill="x")

        # Render Logo Thumbnail in Top Header Bar
        logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "images", "logo.png")
        if os.path.exists(logo_path):
            try:
                from PIL import Image, ImageTk
                h_img = Image.open(logo_path).resize((34, 34), Image.Resampling.LANCZOS)
                self.header_logo_tk = ImageTk.PhotoImage(h_img)
                lbl_logo = tk.Label(header, image=self.header_logo_tk, bg="#ffffff")
                lbl_logo.pack(side="left", padx=(14, 4))
            except Exception:
                pass

        lbl_app_title = tk.Label(
            header,
            text="O!kie Grocery  |  Supermarket POS & Business Inventory",
            font=("Helvetica", 13, "bold"),
            bg="#ffffff",
            fg="#0f172a",
            padx=10
        )
        lbl_app_title.pack(side="left", fill="y")

        # Logout Button
        btn_logout = FlatBtn(
            header,
            text="LOG OUT",
            bg="#ff3b30",
            hover_bg="#d70015",
            font=("Helvetica", 9, "bold"),
            padx=14,
            pady=6,
            command=self.logout
        )
        btn_logout.pack(side="right", padx=16, pady=10)

        # User Info Tag
        self.lbl_user_info = tk.Label(
            header,
            text="User: Not Logged In",
            font=("Helvetica", 10, "bold"),
            bg="#ffffff",
            fg="#c8102e",
            padx=16
        )
        self.lbl_user_info.pack(side="right", fill="y")

        # 2. Main Workspace Container
        main_container = tk.Frame(self, bg="#f1f5f9")
        main_container.pack(side="top", fill="both", expand=True)

        # 3. Left Sidebar Navigation
        self.sidebar = tk.Frame(main_container, bg="#ffffff", width=220, highlightbackground="#e2e8f0", highlightthickness=1)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        tk.Label(
            self.sidebar,
            text="NAVIGATION MENU",
            font=("Helvetica", 8, "bold"),
            bg="#ffffff",
            fg="#94a3b8",
            pady=14,
            padx=16
        ).pack(anchor="w")

        nav_items = [
            ("Dashboard", "dashboard"),
            ("Cashier POS", "cashier"),
            ("Inventory", "inventory"),
            ("Sales History", "history"),
            ("Analytics", "analytics"),
        ]

        self.nav_buttons = {}
        for text, key in nav_items:
            item = LightNavItem(self.sidebar, text=text, key=key, command=self.show_frame)
            item.pack(fill="x", pady=2)
            self.nav_buttons[key] = item

        # 4. Content Frame
        self.content_area = tk.Frame(main_container, bg="#f8fafc")
        self.content_area.pack(side="right", fill="both", expand=True)

        self.frames = {}
        self.frames["dashboard"] = DashboardFrame(self.content_area, self)
        self.frames["cashier"] = CashierFrame(self.content_area, self)
        self.frames["inventory"] = InventoryFrame(self.content_area, self)
        self.frames["history"] = SalesHistoryFrame(self.content_area, self)
        self.frames["analytics"] = AnalyticsFrame(self.content_area, self)

        for frame in self.frames.values():
            frame.grid(row=0, column=0, sticky="nsew")

        self.content_area.grid_rowconfigure(0, weight=1)
        self.content_area.grid_columnconfigure(0, weight=1)

        # 5. Bottom Status Bar
        status_bar = tk.Frame(self, bg="#ffffff", height=30, highlightbackground="#e2e8f0", highlightthickness=1)
        status_bar.pack(side="bottom", fill="x")

        self.lbl_status_msg = tk.Label(
            status_bar,
            text="System Ready",
            font=("Helvetica", 9),
            bg="#ffffff",
            fg="#64748b",
            padx=16
        )
        self.lbl_status_msg.pack(side="left")

        self.lbl_clock = tk.Label(
            status_bar,
            text="",
            font=("Helvetica", 9, "bold"),
            bg="#ffffff",
            fg="#334155",
            padx=16
        )
        self.lbl_clock.pack(side="right")

    def show_frame(self, page_name: str):
        """Bring frame to front and highlight active navigation button."""
        frame = self.frames.get(page_name)
        if frame:
            # Prefer on_navigate() (reset + refresh) over plain refresh()
            if hasattr(frame, "on_navigate"):
                try:
                    frame.on_navigate()
                except Exception as e:
                    print(f"Error navigating {page_name}: {e}")
            elif hasattr(frame, "refresh"):
                try:
                    frame.refresh()
                except Exception as e:
                    print(f"Error refreshing {page_name}: {e}")

            frame.tkraise()

            for k, nav in self.nav_buttons.items():
                nav.set_active(k == page_name)

            self.set_status(f"Active View: {page_name.upper()}")


    def set_status(self, message: str):
        self.lbl_status_msg.config(text=message)

    def _update_clock(self):
        now_str = datetime.now().strftime("%B %d, %Y  %I:%M:%S %p")
        self.lbl_clock.config(text=now_str)
        self.after(1000, self._update_clock)

    def logout(self):
        """Clock out cashier shift (if active) and return to full-screen login overlay."""
        if self.active_shift_id:
            clock_out_shift(self.active_shift_id)
            self.active_shift_id = None

        # Reset cashier POS session state (clears voucher text, barcode entries, and cart)
        if "cashier" in self.frames and hasattr(self.frames["cashier"], "reset_session"):
            self.frames["cashier"].reset_session()

        self.current_user = None
        self.deiconify()
        self.lift()
        self.focus_force()
        self._show_login()

    def _on_app_close(self):
        """Intercept application close to clock out active shift."""
        if self.active_shift_id:
            clock_out_shift(self.active_shift_id)
        self.destroy()


if __name__ == "__main__":
    app = SmartRetailApp()
    app.mainloop()
