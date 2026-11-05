# utils/splash.py
# O!kie Grocery POS - Fullscreen Video Splash Screen Implementation

from __future__ import annotations
import tkinter as tk
import os
import sys
import time
import queue
import threading
try:
    import cv2
    from PIL import Image, ImageTk
    HAS_VIDEO_LIBS = True
except ImportError:
    HAS_VIDEO_LIBS = False


class SplashScreen(tk.Toplevel):
    """
    High-performance, full-screen video splash screen.
    Uses a background worker thread for OpenCV decoding & scaling
    to ensure 100% smooth playback across the full monitor.
    Does NOT skip on mouse clicks or keypresses.
    """

    def __init__(self, parent: tk.Tk, video_path: str = None, on_done=None):
        super().__init__(parent)
        self.parent = parent
        self.on_done_callback = on_done

        # Configure Full-Screen Splash Window
        self.overrideredirect(True)  # Borderless full-screen
        self.configure(bg="#ffffff")
        self.attributes("-topmost", True)

        # Cover entire monitor
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"{sw}x{sh}+0+0")

        # Calculate video frame sizing to fill screen while preserving aspect ratio
        scale = min(sw / 1920.0, sh / 1080.0) if sw > 0 and sh > 0 else 1.0
        display_w = max(1, int(1920 * scale))
        display_h = max(1, int(1080 * scale))
        self.display_size = (display_w, display_h)

        # Main Video Label centered on white background
        self.video_label = tk.Label(self, bg="#ffffff", borderwidth=0, highlightthickness=0)
        self.video_label.place(relx=0.5, rely=0.5, anchor="center")

        # Resolve Video Path
        if not video_path:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            video_path = os.path.join(base_dir, "assets", "oikie_splash_screen.mp4")
            if not os.path.exists(video_path):
                alt_path = "/Users/an/Downloads/1ST TERM/oikie_splash_screen.mp4"
                if os.path.exists(alt_path):
                    video_path = alt_path

        self.video_path = video_path
        self.is_running = True
        self.current_tk_img = None
        self.frame_queue = queue.Queue(maxsize=4)
        self.worker_thread = None

        # Focus window
        self.focus_force()

        # Start Playback or Fallback
        if HAS_VIDEO_LIBS and os.path.exists(self.video_path):
            self._start_video_playback()
        else:
            self._start_fallback_display()

    def _start_video_playback(self):
        """Spawns background decoder and starts Tkinter update loop."""
        self.worker_thread = threading.Thread(target=self._video_decoder_worker, daemon=True)
        self.worker_thread.start()
        # Start frame update tick (~30fps => 33ms)
        self.after(20, self._update_frame)

    def _video_decoder_worker(self):
        """Background thread: Decodes MP4 frames, resizes them, pushes PIL Images to queue."""
        cap = cv2.VideoCapture(self.video_path)
        if not cap.isOpened():
            self.frame_queue.put(None)
            return

        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_delay = 1.0 / fps if fps > 0 else 1.0 / 30.0
        w, h = self.display_size

        while self.is_running:
            start_t = time.time()
            ret, frame = cap.read()
            if not ret:
                # Video finished
                break

            # Convert BGR (OpenCV) to RGB (PIL)
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Fast resize to calculated display size
            resized = cv2.resize(rgb_frame, (w, h), interpolation=cv2.INTER_LINEAR)
            img = Image.fromarray(resized)

            # Put image into queue
            try:
                self.frame_queue.put(img, timeout=1.0)
            except queue.Full:
                pass

            # Timing sync for 30fps
            elapsed = time.time() - start_t
            sleep_time = frame_delay - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

        cap.release()
        try:
            self.frame_queue.put(None, timeout=1.0)
        except Exception:
            pass

    def _update_frame(self):
        """Main thread GUI callback: Pops rendered frame from queue and displays it."""
        if not self.is_running:
            return

        try:
            img = self.frame_queue.get_nowait()
            if img is None:
                # Video playback finished naturally
                self.after(150, self.finish)
                return

            self.current_tk_img = ImageTk.PhotoImage(img)
            self.video_label.config(image=self.current_tk_img)

        except queue.Empty:
            pass

        if self.is_running:
            self.after(25, self._update_frame)

    def _start_fallback_display(self):
        """Static fallback display if video library or file is unavailable."""
        self.video_label.config(
            text="O!kie Grocery",
            font=("Helvetica", 36, "bold"),
            fg="#c8102e",
            bg="#ffffff"
        )
        self.after(2500, self.finish)

    def finish(self):
        """Safely clean up resources, trigger callback, and destroy splash window."""
        if not self.is_running:
            return
        self.is_running = False

        if self.on_done_callback:
            try:
                self.on_done_callback()
            except Exception as e:
                print(f"Error in splash screen on_done callback: {e}")

        try:
            self.destroy()
        except Exception:
            pass
