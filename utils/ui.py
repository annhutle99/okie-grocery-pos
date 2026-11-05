# utils/ui.py
# Apple Liquid Glass UI Component System for SmartRetail Final Revision

from __future__ import annotations
import tkinter as tk


class FlatBtn(tk.Label):
    """
    Custom Apple-inspired flat button widget using tk.Label.
    Bypasses native macOS Aqua button rendering issues for crisp custom colors.
    """

    def __init__(
        self,
        parent,
        text: str,
        command=None,
        bg: str = "#007aff",        # Apple Primary Blue
        fg: str = "#ffffff",
        hover_bg: str = "#0056b3",
        font: tuple = ("Helvetica", 10, "bold"),
        padx: int = 14,
        pady: int = 8,
        **kwargs
    ):
        super().__init__(
            parent,
            text=text,
            bg=bg,
            fg=fg,
            font=font,
            padx=padx,
            pady=pady,
            justify="center",
            cursor="hand2",
            relief="flat",
            bd=0,
            **kwargs
        )
        self.command = command
        self.normal_bg = bg
        self.hover_bg = hover_bg

        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)

    def _on_enter(self, event):
        self.configure(bg=self.hover_bg)

    def _on_leave(self, event):
        self.configure(bg=self.normal_bg)

    def _on_click(self, event=None):
        if self.command:
            self.command()

    def set_colors(self, bg: str, hover_bg: str, fg: str = "#ffffff"):
        self.normal_bg = bg
        self.hover_bg = hover_bg
        self.configure(bg=bg, fg=fg)


class CardFrame(tk.Frame):
    """Apple-inspired clean light glass card frame with crisp subtle border."""
    def __init__(
        self,
        parent,
        bg: str = "#ffffff",
        border_color: str = "#e2e8f0",
        padx: int = 16,
        pady: int = 16,
        **kwargs
    ):
        super().__init__(
            parent,
            bg=bg,
            highlightbackground=border_color,
            highlightthickness=1,
            bd=0,
            padx=padx,
            pady=pady,
            **kwargs
        )


class ClearableEntry(tk.Frame):
    """
    Apple-inspired seamless search input box with integrated clear ('✕') button.
    Eliminates native macOS double borders and provides clean focus styling.
    """

    def __init__(
        self,
        parent,
        textvariable: tk.StringVar,
        width: int = 22,
        font: tuple = ("Helvetica", 10),
        bg: str = "#f1f5f9",
        fg: str = "#0f172a",
        on_clear=None,
        **kwargs
    ):
        super().__init__(
            parent,
            bg=bg,
            highlightbackground="#cbd5e1",
            highlightthickness=1,
            bd=0,
            padx=4,
            pady=2,
            **kwargs
        )
        self.var = textvariable
        self.on_clear = on_clear
        self.normal_border = "#cbd5e1"
        self.active_border = "#007aff"

        self.btn_clear = tk.Label(
            self,
            text="   ",
            font=("Helvetica", 10, "bold"),
            bg=bg,
            fg="#94a3b8",
            cursor="",
            bd=0,
            relief="flat",
            highlightthickness=0,
            width=2
        )
        self.btn_clear.pack(side="right", padx=(0, 4))

        self.entry = tk.Entry(
            self,
            textvariable=self.var,
            font=font,
            width=width,
            bg=bg,
            fg=fg,
            relief="flat",
            bd=0,
            highlightthickness=0,
            insertbackground="#0f172a"
        )
        self.entry.pack(side="left", fill="both", expand=True, padx=(4, 2), ipady=3)

        self.btn_clear.bind("<Enter>", self._on_enter_clear)
        self.btn_clear.bind("<Leave>", self._on_leave_clear)
        self.btn_clear.bind("<Button-1>", self._clear)

        self.entry.bind("<FocusIn>", self._on_focus_in)
        self.entry.bind("<FocusOut>", self._on_focus_out)

        self.var.trace_add("write", self._toggle_btn)
        self._toggle_btn()

    def _on_focus_in(self, event=None):
        self.config(highlightbackground=self.active_border, highlightthickness=1)

    def _on_focus_out(self, event=None):
        self.config(highlightbackground=self.normal_border, highlightthickness=1)

    def _on_enter_clear(self, event=None):
        if self.var.get():
            self.btn_clear.config(fg="#ef4444")

    def _on_leave_clear(self, event=None):
        if self.var.get():
            self.btn_clear.config(fg="#94a3b8")

    def _toggle_btn(self, *args):
        if self.var.get():
            self.btn_clear.config(text=" ✕ ", cursor="hand2")
        else:
            self.btn_clear.config(text="   ", cursor="")

    def _clear(self, event=None):
        if self.var.get():
            self.var.set("")
            self.entry.focus()
            if self.on_clear:
                self.on_clear()

    def bind(self, sequence=None, func=None, add=None):
        """Forward event bindings to the underlying Entry widget."""
        return self.entry.bind(sequence, func, add)

    def focus(self):
        return self.entry.focus()


class StatusBadge(tk.Label):
    """Apple-style status pill badge."""
    def __init__(self, parent, text: str, bg: str = "#dbeafe", fg: str = "#1d4ed8", **kwargs):
        super().__init__(
            parent,
            text=text,
            font=("Helvetica", 9, "bold"),
            bg=bg,
            fg=fg,
            padx=10,
            pady=4,
            relief="flat",
            bd=0,
            **kwargs
        )


class PrivacyToggle(tk.Label):
    """Eye icon toggle button to show/hide monetary totals for business privacy."""
    def __init__(self, parent, on_toggle=None, initial_visible: bool = True, **kwargs):
        self.is_visible = initial_visible
        self.on_toggle = on_toggle
        text = "  SHOW BALANCE  " if not self.is_visible else "  HIDE BALANCE  "
        super().__init__(
            parent,
            text=text,
            font=("Helvetica", 9, "bold"),
            bg="#f1f5f9",
            fg="#007aff",
            padx=10,
            pady=5,
            cursor="hand2",
            relief="flat",
            bd=0,
            **kwargs
        )
        self.bind("<Button-1>", self._toggle)

    def _toggle(self, event=None):
        self.is_visible = not self.is_visible
        self.config(text="  SHOW BALANCE  " if not self.is_visible else "  HIDE BALANCE  ")
        if self.on_toggle:
            self.on_toggle(self.is_visible)

    def reset_to_hidden(self):
        """Force button back to hidden state — used when navigating away and returning."""
        self.is_visible = False
        self.config(text="  SHOW BALANCE  ")
