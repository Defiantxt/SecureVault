import customtkinter as ctk
import ctypes as ct


DWMWA_CAPTION_COLOR = 35
DWMWA_TEXT_COLOR = 36

def hex_to_colorref(hex_color):
    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)

    # COLORREF format = 0x00BBGGRR
    return b << 16 | g << 8 | r


def set_title_bar_color(window, bg="#040d1a", text="#FFFFFF"):
    window.update()

    hwnd = ct.windll.user32.GetParent(window.winfo_id())

    bg_color = ct.c_int(hex_to_colorref(bg))
    text_color = ct.c_int(hex_to_colorref(text))

    ct.windll.dwmapi.DwmSetWindowAttribute(
        hwnd,
        DWMWA_CAPTION_COLOR,
        ct.byref(bg_color),
        ct.sizeof(bg_color)
    )

    ct.windll.dwmapi.DwmSetWindowAttribute(
        hwnd,
        DWMWA_TEXT_COLOR,
        ct.byref(text_color),
        ct.sizeof(text_color)
    )


window = ctk.CTk(fg_color="#040d1a")
screen_width = window.winfo_screenwidth()
screen_height = window.winfo_screenheight()

width = int(screen_width * 0.4)
height = int(screen_height * 0.5)

# Prevent window from becoming too small
width = max(700, min(width, 1200))
height = max(500, min(height, 800))

window.geometry(f"{width}x{height}")

x = (screen_width - width) // 2
y = (screen_height - height) // 2
window.geometry(f"{width}x{height}+{x}+{y}")

set_title_bar_color(window)

window.mainloop()