import ctypes as ct
import math
from typing import Annotated


DWMWA_CAPTION_COLOR = 35
DWMWA_TEXT_COLOR = 36

BACKGROUND_COLOR = "#040d1a"
SIDE_BAR_MAIN_COLOR = "#091221"
NAVY_BLUE = "#151D2E"

def hex_to_colorref(hex_color):
    """Convert a "#RRGGBB" hex string to a Windows COLORREF (0x00BBGGRR) int."""
    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return b << 16 | g << 8 | r


def set_title_bar_color(window, bg=SIDE_BAR_MAIN_COLOR, text="#FFFFFF"):
    """Color the window's title bar via the Windows DWM API.

    Sets the caption background to `bg` and the title text to `text`
    (both "#RRGGBB" strings) so the title bar matches the app theme.
    Windows-only; requires Windows 11 (build 22000+).
    """
    window.update()
    hwnd = ct.windll.user32.GetParent(window.winfo_id())
    bg_color = ct.c_int(hex_to_colorref(bg))
    text_color = ct.c_int(hex_to_colorref(text))
    ct.windll.dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_CAPTION_COLOR, ct.byref(bg_color), ct.sizeof(bg_color))
    ct.windll.dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_TEXT_COLOR, ct.byref(text_color), ct.sizeof(text_color))


def _compute_window_size():
    screen_width = ct.windll.user32.GetSystemMetrics(0)
    screen_height = ct.windll.user32.GetSystemMetrics(1)
    width = max(700, min(int(screen_width * 0.7), 1200))
    height = max(500, min(int(screen_height * 0.7), 800))
    return width, height

WINDOW_WIDTH, WINDOW_HEIGHT = _compute_window_size()


def get_window_size():
    return WINDOW_WIDTH, WINDOW_HEIGHT


def scale(n: Annotated[float | int, "0.0–1.0"]) -> int:
    """Return `n` as a fraction of the window diagonal, in pixels.

    Used for element sizes (widths, heights, font sizes) so they scale
    with the window on different screen resolutions. `n` must be a
    number between 0.0 and 1.0 inclusive; raises TypeError or
    ValueError otherwise.
    """
    width, height = get_window_size()
    if not isinstance(n, (float, int)):
        raise TypeError("n must be a number between 0.0 and 1.0")
    if not (0.0 <= n <= 1.0):
        raise ValueError("n must be between 0.0 and 1.0 inclusive")

    diagonal = math.sqrt(width ** 2 + height ** 2)
    return int(diagonal * n)


def padx(n: Annotated[float, "0.0–1.0"]) -> int:
    """Return `n` as a fraction of the window width, in pixels.

    Used for horizontal padding/spacing. `n` must be a number between
    0.0 and 1.0 inclusive; raises TypeError or ValueError otherwise.
    """
    width, _ = get_window_size()
    if not isinstance(n, (float, int)):
        raise TypeError("n must be a number between 0.0 and 1.0")
    if not (0.0 <= n <= 1.0):
        raise ValueError("n must be between 0.0 and 1.0 inclusive")
    return int(width * n)


def pady(n: Annotated[float, "0.0–1.0"]) -> int:
    """Return `n` as a fraction of the window height, in pixels.

    Used for vertical padding/spacing. `n` must be a number between
    0.0 and 1.0 inclusive; raises TypeError or ValueError otherwise.
    """
    _, height = get_window_size()
    if not isinstance(n, (float, int)):
        raise TypeError("n must be a number between 0.0 and 1.0")
    if not (0.0 <= n <= 1.0):
        raise ValueError("n must be between 0.0 and 1.0 inclusive")
    return int(height * n)