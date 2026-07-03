

import customtkinter as ctk
import ctypes as ct
from PIL import Image
from customtkinter import CTkImage
import math
from typing import Annotated
from os import listdir

DWMWA_CAPTION_COLOR = 35
DWMWA_TEXT_COLOR = 36
BACKGROUND_COLOR = "#040d1a"
SIDE_BAR_MAIN_COLOR = "#091221"
NAVY_BLUE = "#151D2E"

def hex_to_colorref(hex_color):
    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return b << 16 | g << 8 | r


def set_title_bar_color(window, bg=SIDE_BAR_MAIN_COLOR, text="#FFFFFF"):
    window.update()
    hwnd = ct.windll.user32.GetParent(window.winfo_id())
    bg_color = ct.c_int(hex_to_colorref(bg))
    text_color = ct.c_int(hex_to_colorref(text))
    ct.windll.dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_CAPTION_COLOR, ct.byref(bg_color), ct.sizeof(bg_color))
    ct.windll.dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_TEXT_COLOR, ct.byref(text_color), ct.sizeof(text_color))


window = ctk.CTk(fg_color=BACKGROUND_COLOR)
screen_width = window.winfo_screenwidth()
screen_height = window.winfo_screenheight()

width = max(700, min(int(screen_width * 0.7), 1200))
height = max(500, min(int(screen_height * 0.7), 800))

x = (screen_width - width) // 2
y = (screen_height - height) // 2
window.geometry(f"{width}x{height}+{x}+{y}")


def scale(n: Annotated[float | int, "0.0–1.0"]) -> int:
    """Scale against the window diagonal for element sizes.

    Precondition:
    - 0.0 <= n <= 1.0
    """
    if not isinstance(n, (float, int)):
        raise TypeError("n must be a number between 0.0 and 1.0")
    if not (0.0 <= n <= 1.0):
        raise ValueError("n must be between 0.0 and 1.0 inclusive")

    diagonal = math.sqrt(width ** 2 + height ** 2)
    return int(diagonal * n)

def padx(n: Annotated[float, "0.0–1.0"]) -> int:
    """Scale against window width for horizontal spacing.

    Precondition:
    - 0.0 <= n <= 1.0
    """
    if not isinstance(n, (float, int)):
        raise TypeError("n must be a number between 0.0 and 1.0")
    if not (0.0 <= n <= 1.0):
        raise ValueError("n must be between 0.0 and 1.0 inclusive")
    return int(width * n)

def pady(n: Annotated[float, "0.0–1.0"]) -> int:
    """Scale against window height for vertical spacing.

    Precondition:
    - 0.0 <= n <= 1.0
    """
    if not isinstance(n, (float, int)):
        raise TypeError("n must be a number between 0.0 and 1.0")
    if not (0.0 <= n <= 1.0):
        raise ValueError("n must be between 0.0 and 1.0 inclusive")
    return int(height * n)


set_title_bar_color(window)

main_frm = ctk.CTkFrame(master=window,
                        fg_color=BACKGROUND_COLOR,
                        bg_color=BACKGROUND_COLOR,
                        width=width)
main_frm.grid(row=0, column=0)

side_bar_frm = ctk.CTkFrame(master=main_frm,
                            fg_color=SIDE_BAR_MAIN_COLOR,
                            bg_color=SIDE_BAR_MAIN_COLOR,
                            height=height)
side_bar_frm.grid(row=0, column=0, sticky="w")

logo_width = scale(0.027)
original_logo = Image.open("static/logo.png")
original_logo = original_logo.crop(original_logo.getbbox())
logo_height = int(logo_width * (original_logo.height / original_logo.width))
logo_image = CTkImage(light_image=original_logo,
                      dark_image=original_logo,
                      size=(logo_width, logo_height))

logo_frame = ctk.CTkFrame(master=side_bar_frm,
                          fg_color="transparent",
                          bg_color="transparent")
logo_label = ctk.CTkLabel(master=logo_frame, image=logo_image, text="")
logo_label.grid(row=0, column=0, padx=(padx(0.013), padx(0.007)))

horizontal_border = ctk.CTkFrame(main_frm,
                                 width=scale(0.846),
                                 height=1,
                                 fg_color=NAVY_BLUE,
                                 corner_radius=0)
horizontal_border.grid(row=0, column=0, columnspan=2, sticky="n")

secure_vault = ctk.CTkLabel(master=logo_frame,
                            text="SecureVault",
                            font=("Arial", 14, "bold"),
                            fg_color="transparent",
                            text_color="#9E93EC")
secure_vault.grid(row=0, column=1,
                  padx=padx(0.0007),
                  pady=(pady(0.013), pady(0.027)),
                  sticky="nw")

motto = ctk.CTkLabel(master=logo_frame,
                     text="Your passwords. Secure & private.",
                     font=("Arial", 11),
                     text_color="#DCDEE1",
                     fg_color="transparent",
                     height=10)
motto.grid(row=0, column=1,
           padx=(padx(0.0007), padx(0.027)),
           pady=(0, pady(0.020)),
           sticky="s")
logo_frame.grid(row=0, column=0)

def add_sidebar_btns() -> dict:
    """Create sidebar buttons and store them as an object in a dictionary."""

    labels = {
        "add_new_ent": " Add New Entry",
        "all_ents": "   All Entries",
        "favorites": "   Favorites",
        "logins": "   Logins",
        "cards": "   Cards",
        "notes": "   Notes",
        "trash": "   Trash",
    }

    btn_dict = {}
    for i, (key, text) in enumerate(labels.items()):
        btn = ctk.CTkButton(master=side_bar_frm,
                          text=text,
                          width=scale(0.2),
                          height=scale(0.040),
                          fg_color=SIDE_BAR_MAIN_COLOR,
                          hover_color="#34228A",
                          anchor="w",
                          font=("Arial", scale(0.0125))
                          )
        if i == 0:
            btn.configure(fg_color="#4236B8",
                          hover_color="#34228A",
                          height=scale(0.040),
                          anchor="c",
                          font=("Arial", scale(0.0125)),
                          )
            btn.grid(row=1, column=0, pady=pady(0.025), padx=padx(0.020))
        else:
            btn.grid(row=i+1, column=0, pady=pady(0.0015))
        btn_dict[key] = btn

    return btn_dict

sidebar_btns: dict = add_sidebar_btns()

horizontal_border = ctk.CTkFrame(side_bar_frm,
                                 width=scale(0.175),
                                 height=1,
                                 fg_color=NAVY_BLUE,
                                 corner_radius=0,
                                 )
horizontal_border.grid(row=8, column=0, pady=(pady(0.015), pady(0.007)))

settings = ctk.CTkButton(master=side_bar_frm,
                         text="  Settings",
                         fg_color=SIDE_BAR_MAIN_COLOR,
                         width=scale(0.2),
                         height=scale(0.035),
                         hover_color="#34228A",
                         anchor="w",
                         font=("Arial", scale(0.0125))
                         )
settings.grid(row=9, column=0, pady=(pady(0.015), pady(0.0015)))

lock_vault = ctk.CTkButton(master=side_bar_frm,
                           text="  Lock Vault",
                           fg_color=SIDE_BAR_MAIN_COLOR,
                           width=scale(0.2),
                           height=scale(0.040),
                           hover_color="#34228A",
                           anchor="w",
                           font=("Arial", scale(0.0125))
                           )
lock_vault.grid(row=10, column=0, pady=(pady(0.0015), 0))

horizontal_border = ctk.CTkFrame(side_bar_frm,
                                 width=scale(0.175),
                                 height=1,
                                 fg_color=NAVY_BLUE,
                                 corner_radius=0)
horizontal_border.grid(row=11, column=0, pady=(pady(0.015), pady(0.035)))

sidebar_btns["settings"] = settings
sidebar_btns["lock_vault"] = lock_vault

print(sidebar_btns)

def add_icons():
    """Add icons to sidebar buttons"""
    icon_labels = {"plus_icon.png": "add_new_ent",
                   "lock_icon.png": "all_ents",
                   "star_icon.png": "favorites",
                   "user_icon.png": "logins",
                   "card_icon.png": "cards",
                   "notes_icon.png": "notes",
                   "trash_icon.png": "trash",
                   "settings_icon.png": "settings",
                   "lock_vault_icon.png": "lock_vault",
                   }
    for icon in listdir("static/icons"):
        sidebar_dict_key = icon_labels[icon]
        sidebar_btn_obj = sidebar_btns[sidebar_dict_key]
        image_icon = Image.open(f"static/icons/{icon}")
        image_icon = image_icon.crop(image_icon.getbbox())
        image_icon_size = scale(0.015)
        image_icon_height = int(image_icon_size * (image_icon.height / image_icon.width))
        image_icon_image = CTkImage(light_image=image_icon,
                                    dark_image=image_icon,
                                    size=(image_icon_size, image_icon_height)
                                    )
        sidebar_btn_obj.configure(image=image_icon_image, compound="left")
        if icon == "plus_icon.png":
            sidebar_btn_obj._text_label.grid_configure(padx=(0, scale(0.02)))
        else:
            sidebar_btn_obj._image_label.grid_configure(padx=(scale(0.02), 0))
        sidebar_btn_obj.image = image_icon_image

add_icons()

security_check_width = scale(0.020)
security_check = Image.open("static/security_check_main_layout.png")
security_check = security_check.crop(security_check.getbbox())
security_check_height = int(security_check_width * (security_check.height / security_check.width))
security_check_image = CTkImage(light_image=security_check,
                                dark_image=security_check,
                                size=(logo_width, logo_height))

vault_unlocked_frm = ctk.CTkFrame(master=side_bar_frm,
                                  fg_color="transparent",
                                  bg_color="transparent",
                                  )
security_check_label = ctk.CTkLabel(master=vault_unlocked_frm, image=security_check_image, text="")
security_check_label.grid(row=0, column=0, padx=(padx(0.013), padx(0.007)))

vault_unlocked_frm.grid(row=12, column=0, padx=(padx(0.013), padx(0.007)), pady=(0, pady(0.035)), sticky="w")


right_border = ctk.CTkFrame(side_bar_frm,
                            width=1,
                            height=height,
                            fg_color=NAVY_BLUE,
                            corner_radius=0)
right_border.grid(row=0, rowspan=14, column=1, sticky="nsw")

window.mainloop()

