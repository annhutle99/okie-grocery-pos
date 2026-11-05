# utils/scanner.py
# Barcode Scanner & Product Photo Capture — Tkinter-native, macOS compatible
#
# Performance & Aesthetics Architecture:
#   1. zxing-cpp / pyzbar / cv2 barcode decoding engine (instant C++ native decoding)
#   2. Low-latency 640x480 frame capture with buffer size = 1
#   3. Background thread handles CV reading, flipping, decoding, overlay, & resizing
#   4. Main thread only updates ImageTk.PhotoImage — ZERO freeze/lag
#   5. Always stay-on-top z-index layering so camera window pops up IN FRONT of all modals
#   6. Clean Apple Liquid Glass aesthetic buttons and anti-aliased typography

from __future__ import annotations
import tkinter as tk
from tkinter import simpledialog, messagebox
import threading
import queue
import cv2
import os
import time
from PIL import Image, ImageTk
from utils.ui import FlatBtn
from utils.sound import beep_success, beep_error


# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

DISPLAY_W    = 720      # Display width  (px)
DISPLAY_H    = 480      # Display height (px)
STABLE_SECS  = 1.0      # Seconds barcode must be held steady before confirming
UPDATE_MS    = 25       # ~40 FPS tick rate for ultra-smooth UI
FRAME_Q_MAX  = 1        # Keep latest frame only to prevent latency lag


# ─────────────────────────────────────────────────────────────────────────────
# Barcode decoder — loaded once with fallbacks
# ─────────────────────────────────────────────────────────────────────────────

def _make_decoder():
    """Build fast, reliable barcode decoding function."""
    # 1. zxing-cpp (Highest speed, C++ native wheel, zero external dylibs)
    try:
        import zxingcpp
        def decode_zxing(img):
            results = zxingcpp.read_barcodes(img)
            if results:
                for r in results:
                    txt = r.text.strip()
                    if txt:
                        return txt
            return None
        return decode_zxing
    except ImportError:
        pass

    # 2. pyzbar (Requires libzbar system library)
    try:
        from pyzbar import pyzbar
        def decode_pyzbar(img):
            barcodes = pyzbar.decode(img)
            if barcodes:
                for b in barcodes:
                    txt = b.data.decode("utf-8").strip()
                    if txt:
                        return txt
            return None
        return decode_pyzbar
    except Exception:
        pass

    # 3. OpenCV BarcodeDetector
    if hasattr(cv2, 'barcode'):
        try:
            det = cv2.barcode.BarcodeDetector()
            def decode_cv2(img):
                res = det.detectAndDecode(img)
                if res:
                    for item in res:
                        if isinstance(item, (list, tuple)):
                            for val in item:
                                str_val = str(val).strip()
                                if str_val and str_val.isalnum():
                                    return str_val
                        elif isinstance(item, str) and item.strip():
                            return item.strip()
                return None
            return decode_cv2
        except Exception:
            pass

    return lambda _: None   # Fallback dummy decoder


_DECODE = _make_decoder()


# ─────────────────────────────────────────────────────────────────────────────
# Anti-Aliased Overlay Drawing Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _draw_barcode_overlay(frame, stable_pct: float, remaining_secs: float, detected_code: str) -> tuple:
    """Draw horizontal barcode scanning overlay with anti-aliased graphics."""
    h, w = frame.shape[:2]

    box_w = int(w * 0.70)
    box_h = int(h * 0.32)
    x1 = (w - box_w) // 2
    y1 = (h - box_h) // 2
    x2 = x1 + box_w
    y2 = y1 + box_h

    # Dim area outside scanning box
    mask = frame.copy()
    cv2.rectangle(mask, (0, 0), (w, h), (15, 23, 42), -1)
    mask[y1:y2, x1:x2] = frame[y1:y2, x1:x2]
    cv2.addWeighted(mask, 0.45, frame, 0.55, 0, frame)

    # Corner brackets — bright neon green when holding steady, clean white when scanning
    clr = (80, 235, 120) if stable_pct > 0 else (245, 245, 245)
    ll, th = 28, 3
    for px, py, dx, dy in [(x1,y1,1,1),(x2,y1,-1,1),(x1,y2,1,-1),(x2,y2,-1,-1)]:
        cv2.line(frame, (px, py), (px + dx*ll, py), clr, th, cv2.LINE_AA)
        cv2.line(frame, (px, py), (px, py + dy*ll), clr, th, cv2.LINE_AA)

    # Stability progress bar under box
    bar_y = y2 + 10
    cv2.rectangle(frame, (x1, bar_y), (x2, bar_y + 7), (30, 38, 55), -1)
    if stable_pct > 0:
        filled = int((x2 - x1) * min(stable_pct, 1.0))
        cv2.rectangle(frame, (x1, bar_y), (x1 + filled, bar_y + 7), (80, 235, 120), -1)

    # Status banner at bottom
    cv2.rectangle(frame, (0, h - 46), (w, h), (10, 15, 28), -1)
    if detected_code:
        txt = f"SCANNING: {detected_code}  — Hold steady ({remaining_secs:.1f}s)"
        cv2.putText(frame, txt, (16, h - 16), cv2.FONT_HERSHEY_SIMPLEX, 0.54, (80, 235, 120), 2, cv2.LINE_AA)
    else:
        cv2.putText(frame, "Place barcode inside the scanning box", (16, h - 16),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.54, (230, 235, 245), 2, cv2.LINE_AA)
    cv2.putText(frame, "ESC or Cancel to close", (w - 205, h - 16),
                cv2.FONT_HERSHEY_SIMPLEX, 0.42, (140, 155, 175), 1, cv2.LINE_AA)

    return frame, (x1, y1, x2, y2)


def _draw_product_overlay(frame) -> tuple:
    """Draw vertical product photo overlay with anti-aliased graphics."""
    h, w = frame.shape[:2]

    box_w = int(w * 0.55)
    box_h = int(h * 0.72)
    x1 = (w - box_w) // 2
    y1 = (h - box_h) // 2
    x2 = x1 + box_w
    y2 = y1 + box_h

    mask = frame.copy()
    cv2.rectangle(mask, (0, 0), (w, h), (15, 23, 42), -1)
    mask[y1:y2, x1:x2] = frame[y1:y2, x1:x2]
    cv2.addWeighted(mask, 0.40, frame, 0.60, 0, frame)

    clr = (0, 215, 185)
    ll, th = 32, 3
    for px, py, dx, dy in [(x1,y1,1,1),(x2,y1,-1,1),(x1,y2,1,-1),(x2,y2,-1,-1)]:
        cv2.line(frame, (px, py), (px + dx*ll, py), clr, th, cv2.LINE_AA)
        cv2.line(frame, (px, py), (px, py + dy*ll), clr, th, cv2.LINE_AA)

    cv2.rectangle(frame, (0, h - 46), (w, h), (10, 15, 28), -1)
    cv2.putText(frame, "Center product in frame  —  press SPACE or Capture button",
                (16, h - 16), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (230, 235, 245), 2, cv2.LINE_AA)
    cv2.putText(frame, "ESC or Cancel to close", (w - 205, h - 16),
                cv2.FONT_HERSHEY_SIMPLEX, 0.42, (140, 155, 175), 1, cv2.LINE_AA)

    return frame, (x1, y1, x2, y2)


def _resize_frame(frame, max_w=DISPLAY_W, max_h=DISPLAY_H):
    """Resize frame to fit display, preserving aspect ratio."""
    fh, fw = frame.shape[:2]
    ratio = min(max_w / fw, max_h / fh, 1.0)
    if ratio < 1.0:
        nw, nh = int(fw * ratio), int(fh * ratio)
        return cv2.resize(frame, (nw, nh), interpolation=cv2.INTER_LINEAR)
    return frame


# ─────────────────────────────────────────────────────────────────────────────
# Barcode Scanner Window
# ─────────────────────────────────────────────────────────────────────────────

class BarcodeScannerWindow(tk.Toplevel):
    """
    Tkinter Toplevel showing live mirrored camera feed for barcode scanning.
    Heavy image processing runs on background thread to prevent UI freezing.
    Stays always-on-top so it pops up in front of all modal dialogs.
    """

    def __init__(self, parent, on_result):
        super().__init__(parent)
        self.on_result  = on_result
        self.title("SmartRetail — Barcode Camera Scanner")
        self.configure(bg="#0f172a")
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self._cancel)

        # Force window to stay in front of parent & modal dialogs
        self.transient(parent)
        self.attributes("-topmost", True)

        # State management
        self._running        = True
        self._result_sent    = False
        self._camera_error   = None
        self._frame_q: queue.Queue = queue.Queue(maxsize=FRAME_Q_MAX)
        self._confirmed_code: str | None = None
        self._tk_img         = None

        # ── Top Title Bar ──────────────────────────────────────────────────
        header = tk.Frame(self, bg="#0f172a", padx=16, pady=10)
        header.pack(fill="x")
        tk.Label(
            header, text="SmartRetail POS  •  Live Camera Barcode Scanner",
            font=("Helvetica", 11, "bold"), fg="#38bdf8", bg="#0f172a"
        ).pack(side="left")

        # ── Feed & Status Container ────────────────────────────────────────
        self._lbl_status = tk.Label(
            self, text="Connecting to camera — please wait...",
            font=("Helvetica", 12, "bold"), bg="#0f172a", fg="#94a3b8",
            width=60, height=12
        )
        self._lbl_status.pack(padx=16, pady=16)

        self._lbl_feed = tk.Label(self, bg="#000000")

        # ── Bottom Action Button Bar (Clean Apple Flat Buttons) ────────────
        btn_bar = tk.Frame(self, bg="#0f172a", padx=16, pady=12)
        btn_bar.pack(fill="x", side="bottom")

        FlatBtn(
            btn_bar, text="MANUAL BARCODE INPUT",
            bg="#007aff", hover_bg="#0056b3", fg="#ffffff",
            font=("Helvetica", 10, "bold"), padx=18, pady=8,
            command=self._manual_input
        ).pack(side="left")

        FlatBtn(
            btn_bar, text="CANCEL / CLOSE",
            bg="#ef4444", hover_bg="#dc2626", fg="#ffffff",
            font=("Helvetica", 10, "bold"), padx=18, pady=8,
            command=self._cancel
        ).pack(side="right")

        self.bind("<Escape>", lambda e: self._cancel())

        # Start camera worker thread
        threading.Thread(target=self._camera_loop, daemon=True).start()
        self.after(UPDATE_MS, self._tick)

        self._center()
        self.lift()
        self.focus_force()
        try:
            self.grab_set()
        except Exception:
            pass

    def _center(self):
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        x = max(0, (sw - w) // 2)
        y = max(0, (sh - h) // 2 - 30)
        self.geometry(f"+{x}+{y}")

    # ── Worker Thread ─────────────────────────────────────────────────────

    def _camera_loop(self):
        """Runs in background thread. Reads frames, decodes, & prepares display."""
        cap = None
        for idx in (0, 1):
            temp_cap = cv2.VideoCapture(idx)
            if temp_cap.isOpened():
                cap = temp_cap
                break
            temp_cap.release()

        if cap is None or not cap.isOpened():
            self._camera_error = "Could not open camera. Please check webcam connection or Mac privacy settings."
            self._running = False
            return

        cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_BUFFERSIZE,   1)

        stable_code  = None
        stable_start = None

        while self._running:
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.01)
                continue

            frame = cv2.flip(frame, 1)

            fh, fw = frame.shape[:2]
            bx1 = int(fw * 0.15); bx2 = int(fw * 0.85)
            by1 = int(fh * 0.25); by2 = int(fh * 0.75)
            crop = frame[by1:by2, bx1:bx2]
            code = _DECODE(crop) or _DECODE(frame)

            now = time.time()
            if code:
                if code != stable_code:
                    stable_code  = code
                    stable_start = now
                elapsed   = now - stable_start
                pct       = elapsed / STABLE_SECS
                remaining = max(0.0, STABLE_SECS - elapsed)
                confirmed = elapsed >= STABLE_SECS
            else:
                stable_code  = None
                stable_start = None
                elapsed = pct = remaining = 0.0
                confirmed = False

            if confirmed:
                cv2.rectangle(frame, (0, 0), (fw, fh), (80, 235, 120), 10)
                cv2.putText(frame, f"BARCODE CONFIRMED: {code}",
                            (fw // 2 - 210, fh // 2),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.85, (80, 235, 120), 3, cv2.LINE_AA)
            else:
                frame, _ = _draw_barcode_overlay(frame, pct, remaining, code or "")

            frame = _resize_frame(frame)
            rgb   = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            payload = (rgb, confirmed, code)

            if self._frame_q.full():
                try: self._frame_q.get_nowait()
                except queue.Empty: pass
            try: self._frame_q.put_nowait(payload)
            except queue.Full: pass

            if confirmed:
                beep_success()          # supermarket-style scan beep
                time.sleep(0.35)
                self._confirmed_code = code
                self._running = False
                break

        cap.release()

    # ── Main Thread Display Handler ───────────────────────────────────────

    def _tick(self):
        """Runs on Tkinter main thread every UPDATE_MS."""
        if self._result_sent:
            return

        if self._camera_error:
            self._lbl_status.configure(
                text=f"Camera Error:\n{self._camera_error}\n\nPlease click 'MANUAL BARCODE INPUT' to type code.",
                fg="#ef4444"
            )
            return

        try:
            rgb, confirmed, code = self._frame_q.get_nowait()
        except queue.Empty:
            if self._running:
                self.after(UPDATE_MS, self._tick)
            return

        if not self._lbl_feed.winfo_ismapped():
            self._lbl_status.pack_forget()
            self._lbl_feed.pack(padx=0, pady=0)

        img = Image.fromarray(rgb)
        tk_img = ImageTk.PhotoImage(img)
        self._tk_img = tk_img
        self._lbl_feed.configure(image=tk_img)

        if confirmed:
            self._finish(code)
            return

        if not self._running and self._confirmed_code:
            self._finish(self._confirmed_code)
            return

        self.after(UPDATE_MS, self._tick)

    # ── Actions ───────────────────────────────────────────────────────────

    def _manual_input(self):
        code = simpledialog.askstring("Manual Barcode Entry", "Enter product Barcode / SKU:", parent=self)
        if code and code.strip():
            beep_success()              # beep for manual barcode entry too
            self._finish(code.strip())

    def _finish(self, code: str):
        if not self._result_sent:
            self._result_sent = True
            self._running = False
            try: self.grab_release()
            except Exception: pass
            try: self.attributes("-topmost", False)
            except Exception: pass
            self.destroy()
            self.on_result(code)

    def _cancel(self):
        if not self._result_sent:
            self._result_sent = True
            self._running = False
            try: self.grab_release()
            except Exception: pass
            try: self.attributes("-topmost", False)
            except Exception: pass
            self.destroy()
            self.on_result(None)


# ─────────────────────────────────────────────────────────────────────────────
# Product Photo Window
# ─────────────────────────────────────────────────────────────────────────────

class ProductPhotoWindow(tk.Toplevel):
    """
    Tkinter Toplevel for capturing product photos.
    Press SPACE or the Capture button to save photo.
    Stays always-on-top so it pops up in front of all modal dialogs.
    """

    def __init__(self, parent, barcode: str, on_result):
        super().__init__(parent)
        self.barcode     = barcode
        self.on_result   = on_result
        self.title("SmartRetail — Product Photo Capture")
        self.configure(bg="#0f172a")
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self._cancel)

        # Force window to stay in front of parent & modal dialogs
        self.transient(parent)
        self.attributes("-topmost", True)

        self._running        = True
        self._result_sent    = False
        self._camera_error   = None
        self._frame_q: queue.Queue = queue.Queue(maxsize=FRAME_Q_MAX)
        self._last_raw       = None
        self._tk_img         = None
        self._capture_flag   = False

        # Top Title Bar
        header = tk.Frame(self, bg="#0f172a", padx=16, pady=10)
        header.pack(fill="x")
        tk.Label(
            header, text="SmartRetail POS  •  Product Photo Capture",
            font=("Helvetica", 11, "bold"), fg="#38bdf8", bg="#0f172a"
        ).pack(side="left")

        # UI Layout
        self._lbl_status = tk.Label(
            self, text="Connecting to camera — please wait...",
            font=("Helvetica", 12, "bold"), bg="#0f172a", fg="#94a3b8",
            width=60, height=12
        )
        self._lbl_status.pack(padx=16, pady=16)

        self._lbl_feed = tk.Label(self, bg="#000000")

        btn_bar = tk.Frame(self, bg="#0f172a", padx=16, pady=12)
        btn_bar.pack(fill="x", side="bottom")

        FlatBtn(
            btn_bar, text="CAPTURE PHOTO  (SPACE)",
            bg="#16a34a", hover_bg="#15803d", fg="#ffffff",
            font=("Helvetica", 10, "bold"), padx=18, pady=8,
            command=self._trigger_capture
        ).pack(side="left")

        FlatBtn(
            btn_bar, text="CANCEL / CLOSE",
            bg="#ef4444", hover_bg="#dc2626", fg="#ffffff",
            font=("Helvetica", 10, "bold"), padx=18, pady=8,
            command=self._cancel
        ).pack(side="right")

        self.bind("<space>",  lambda e: self._trigger_capture())
        self.bind("<Return>", lambda e: self._trigger_capture())
        self.bind("<Escape>", lambda e: self._cancel())

        threading.Thread(target=self._camera_loop, daemon=True).start()
        self.after(UPDATE_MS, self._tick)

        self._center()
        self.lift()
        self.focus_force()
        try:
            self.grab_set()
        except Exception:
            pass

    def _center(self):
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        x = max(0, (sw - w) // 2)
        y = max(0, (sh - h) // 2 - 30)
        self.geometry(f"+{x}+{y}")

    def _trigger_capture(self):
        self._capture_flag = True

    def _camera_loop(self):
        cap = None
        for idx in (0, 1):
            temp_cap = cv2.VideoCapture(idx)
            if temp_cap.isOpened():
                cap = temp_cap
                break
            temp_cap.release()

        if cap is None or not cap.isOpened():
            self._camera_error = "Could not open camera."
            self._running = False
            return

        cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_BUFFERSIZE,   1)

        while self._running:
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.01)
                continue

            frame = cv2.flip(frame, 1)
            self._last_raw = frame.copy()

            display, _ = _draw_product_overlay(frame.copy())
            display = _resize_frame(display)
            rgb = cv2.cvtColor(display, cv2.COLOR_BGR2RGB)

            if self._frame_q.full():
                try: self._frame_q.get_nowait()
                except queue.Empty: pass
            try: self._frame_q.put_nowait(rgb)
            except queue.Full: pass

        cap.release()

    def _tick(self):
        if self._result_sent:
            return

        if self._camera_error:
            self._lbl_status.configure(
                text=f"Camera Error:\n{self._camera_error}",
                fg="#ef4444"
            )
            return

        if self._capture_flag:
            self._capture_flag = False
            self._do_capture()
            return

        try:
            rgb = self._frame_q.get_nowait()
        except queue.Empty:
            if self._running:
                self.after(UPDATE_MS, self._tick)
            return

        if not self._lbl_feed.winfo_ismapped():
            self._lbl_status.pack_forget()
            self._lbl_feed.pack(padx=0, pady=0)

        img    = Image.fromarray(rgb)
        tk_img = ImageTk.PhotoImage(img)
        self._tk_img = tk_img
        self._lbl_feed.configure(image=tk_img)
        self.after(UPDATE_MS, self._tick)

    def _do_capture(self):
        frame = self._last_raw
        if frame is None:
            self.after(UPDATE_MS, self._tick)
            return

        _, (x1, y1, x2, y2) = _draw_product_overlay(frame.copy())
        crop = frame[y1:y2, x1:x2] if (y2 > y1 and x2 > x1) else frame

        folder = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "assets", "products"
        )
        os.makedirs(folder, exist_ok=True)
        filename = f"prod_{self.barcode}_{int(time.time())}.jpg"
        filepath = os.path.join(folder, filename)

        img = Image.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))
        img.thumbnail((600, 600))
        img.save(filepath, "JPEG", quality=85, optimize=True)

        self._result_sent = True
        self._running = False
        try: self.grab_release()
        except Exception: pass
        try: self.attributes("-topmost", False)
        except Exception: pass
        self.destroy()
        self.on_result(filepath)

    def _cancel(self):
        if not self._result_sent:
            self._result_sent = True
            self._running = False
            try: self.grab_release()
            except Exception: pass
            try: self.attributes("-topmost", False)
            except Exception: pass
            self.destroy()
            self.on_result(None)


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def scan_barcode_camera(parent_widget=None, on_result=None, parent=None):
    """
    Open the barcode scanner window.
    Non-blocking when on_result callback is provided.
    """
    root = parent_widget or parent or tk._default_root
    if root is None:
        return None

    if on_result is None:
        result = [None]
        def _cb(c): result[0] = c
        win = BarcodeScannerWindow(root, _cb)
        root.wait_window(win)
        return result[0]
    else:
        BarcodeScannerWindow(root, on_result)
        return None


def capture_product_photo(barcode="item", parent_widget=None, on_result=None, parent=None):
    """
    Open product photo capture window.
    Non-blocking when on_result callback is provided.
    """
    root = parent_widget or parent or tk._default_root
    if root is None:
        return None

    if on_result is None:
        result = [None]
        def _cb(p): result[0] = p
        win = ProductPhotoWindow(root, barcode, _cb)
        root.wait_window(win)
        return result[0]
    else:
        ProductPhotoWindow(root, barcode, on_result)
        return None
