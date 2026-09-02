"""Cross-DPI geometry helpers for CustomTkinter toplevel windows."""

import ctypes
import sys
import tkinter as tk
from dataclasses import dataclass


@dataclass(frozen=True)
class Rect:
    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        return max(0, self.right - self.left)

    @property
    def height(self) -> int:
        return max(0, self.bottom - self.top)


def window_scale(widget) -> float:
    try:
        return max(0.01, float(widget._get_window_scaling()))
    except (AttributeError, TypeError, ValueError, tk.TclError):
        return 1.0


def widget_scale(widget) -> float:
    try:
        return max(0.01, float(widget._get_widget_scaling()))
    except (AttributeError, TypeError, ValueError, tk.TclError):
        return 1.0


def _window_handle(widget):
    if not sys.platform.startswith("win"):
        return None
    try:
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        user32.GetParent.argtypes = [wintypes.HWND]
        user32.GetParent.restype = wintypes.HWND
        widget_handle = wintypes.HWND(widget.winfo_id())
        return user32.GetParent(widget_handle) or widget_handle
    except (AttributeError, OSError, tk.TclError):
        return None


def window_rect(widget) -> Rect:
    if sys.platform.startswith("win"):
        try:
            from ctypes import wintypes

            handle = _window_handle(widget)
            if handle:
                rect = wintypes.RECT()
                user32 = ctypes.windll.user32
                user32.GetWindowRect.argtypes = [
                    wintypes.HWND,
                    ctypes.POINTER(wintypes.RECT),
                ]
                user32.GetWindowRect.restype = wintypes.BOOL
                if user32.GetWindowRect(handle, ctypes.byref(rect)):
                    return Rect(rect.left, rect.top, rect.right, rect.bottom)
        except (AttributeError, OSError, tk.TclError):
            pass

    try:
        return Rect(
            widget.winfo_rootx(),
            widget.winfo_rooty(),
            widget.winfo_rootx() + widget.winfo_width(),
            widget.winfo_rooty() + widget.winfo_height(),
        )
    except tk.TclError:
        return Rect(0, 0, 1, 1)


def monitor_work_area(widget) -> Rect:
    """Return the owner's monitor work area in physical screen pixels."""

    if sys.platform.startswith("win"):
        try:
            from ctypes import wintypes

            class MonitorInfo(ctypes.Structure):
                _fields_ = (
                    ("cbSize", wintypes.DWORD),
                    ("rcMonitor", wintypes.RECT),
                    ("rcWork", wintypes.RECT),
                    ("dwFlags", wintypes.DWORD),
                )

            handle = _window_handle(widget)
            if handle:
                user32 = ctypes.windll.user32
                user32.MonitorFromWindow.argtypes = [
                    wintypes.HWND,
                    wintypes.DWORD,
                ]
                user32.MonitorFromWindow.restype = wintypes.HMONITOR
                user32.GetMonitorInfoW.argtypes = [
                    wintypes.HMONITOR,
                    ctypes.POINTER(MonitorInfo),
                ]
                user32.GetMonitorInfoW.restype = wintypes.BOOL
                monitor = user32.MonitorFromWindow(handle, 2)
                info = MonitorInfo()
                info.cbSize = ctypes.sizeof(MonitorInfo)
                if monitor and user32.GetMonitorInfoW(
                    monitor,
                    ctypes.byref(info),
                ):
                    work = info.rcWork
                    return Rect(work.left, work.top, work.right, work.bottom)
        except (AttributeError, OSError, tk.TclError):
            pass

    scale = window_scale(widget)
    try:
        left = round(widget.winfo_vrootx() * scale)
        top = round(widget.winfo_vrooty() * scale)
        width = round(widget.winfo_screenwidth() * scale)
        height = round(widget.winfo_screenheight() * scale)
        return Rect(left, top, left + width, top + height)
    except tk.TclError:
        return Rect(0, 0, 1280, 720)


def place_centered_toplevel(
    dialog,
    owner,
    *,
    preferred_width: int,
    preferred_height: int,
    minimum_width: int,
    minimum_height: int,
    edge_margin: int = 16,
) -> tuple[int, int]:
    """Size and center a CTk toplevel inside its owner's monitor work area."""

    scale = window_scale(dialog)
    work_area = monitor_work_area(owner)
    edge = round(edge_margin * scale)
    decoration_width = round(
        (16 if sys.platform.startswith("win") else 4) * scale
    )
    decoration_height = round(
        (44 if sys.platform.startswith("win") else 32) * scale
    )
    maximum_width = max(
        260,
        int(
            (work_area.width - (2 * edge) - decoration_width) / scale
        ),
    )
    maximum_height = max(
        300,
        int(
            (work_area.height - (2 * edge) - decoration_height) / scale
        ),
    )
    width = min(maximum_width, max(minimum_width, preferred_width))
    height = min(maximum_height, max(minimum_height, preferred_height))

    dialog.minsize(
        min(minimum_width, maximum_width),
        min(minimum_height, maximum_height),
    )
    dialog.maxsize(maximum_width, maximum_height)

    # Measure the real decorated size before selecting physical coordinates.
    dialog.geometry(f"{width}x{height}+{work_area.left}+{work_area.top}")
    dialog.update_idletasks()
    outer = window_rect(dialog)
    outer_width = outer.width or round(width * scale)
    outer_height = outer.height or round(height * scale)
    owner_rect = window_rect(owner)
    x = owner_rect.left + (owner_rect.width - outer_width) // 2
    y = owner_rect.top + (owner_rect.height - outer_height) // 2
    x = max(
        work_area.left + edge,
        min(x, work_area.right - edge - outer_width),
    )
    y = max(
        work_area.top + edge,
        min(y, work_area.bottom - edge - outer_height),
    )
    dialog.geometry(f"{width}x{height}+{x}+{y}")
    return width, height


__all__ = [
    "Rect",
    "monitor_work_area",
    "place_centered_toplevel",
    "window_rect",
    "window_scale",
    "widget_scale",
]
