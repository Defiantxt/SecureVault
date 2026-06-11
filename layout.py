import tkinter as tk
import customtkinter as ctk
import ctypes as ct
from PIL import Image, ImageTk


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

def send_email():
    pass

def unlock():
    if len(password_ent.get()) == 0:
        password_ent.configure(placeholder_text="Nothing was entered!", show="", text_color="#DCDEE1")


ct.windll.shcore.SetProcessDpiAwareness(2)

ctk.set_appearance_mode("dark")

window = tk.Tk()
window.title("SecureVault")
width = 800
height = 975

window.geometry(f"{width}x{height}")
window.configure(bg="#040d1a")

set_title_bar_color(window)

# Center content in window
window.grid_rowconfigure(0, weight=1)
window.grid_columnconfigure(0, weight=1)


# Main container
main_frame = tk.Frame(window, bg="#040d1a")
main_frame.grid(row=0, column=0)

img = Image.open("static/logo.png")

bbox = img.getbbox()
img = img.crop(bbox)

photo = ImageTk.PhotoImage(img)

image_label = tk.Label(main_frame, image=photo, bg="#040d1a")
image_label.image = photo  # type: ignore[attr-defined]
# Image logo
image = tk.PhotoImage(file="static/logo.png")
image_label = tk.Label(
    main_frame,
    image=photo,
    bg="#040d1a",
    borderwidth=0
)
image_label.image = photo  # type: ignore[attr-defined]

image_label.pack()



# Title
title_frame = tk.Frame(main_frame, bg="#040d1a")
title_frame.pack(pady=(0, 5))
secure = tk.Label(
    title_frame,
    text="Secure",
    bg="#040d1a",
    fg="#DCDEE1",
    font=("Arial", 22, "bold")
)

vault = tk.Label(
    title_frame,
    text="Vault",
    bg="#040d1a",
    fg="#4a3dca",
    font=("Arial", 22, "bold")
)

secure.pack(side="left")
vault.pack(side="left")

# Motto
motto = tk.Label(
    main_frame,
    text="Your passwords. Secure & private.",
    bg="#040d1a",
    fg="#DCDEE1",
    font=("Arial", 10)
)

motto.pack(pady=(0, 20))


# Login Frame
password_frm = ctk.CTkFrame(
    main_frame,
    width=350,
    height=225,
    fg_color="#08121F",
    border_color="#3D3D3D",
    border_width=1,
)

password_frm.pack(pady=(15, 15))
password_frm.pack_propagate(False)

# Unlock Vault
# If database has a user
unlock_vault = tk.Label(password_frm, text="Unlock Your Vault", bg="#08121F", font=("Arial", 14, "bold"), fg="#DCDEE1")
unlock_vault.pack(pady=(30, 0))
enter_pass = tk.Label(
    password_frm, text="Enter your master password to continue",
    font=("Arial", 10),
    bg="#08121F",
    fg="#DCDEE1"
)
enter_pass.pack()

# Password Entry
password_ent = ctk.CTkEntry(
    password_frm,
    width=320,
    height=30,
    placeholder_text="Master Password",
    show="•",
    fg_color="transparent",
    border_width=1
)

password_ent.pack(pady=(20, 12))

# Unlock Button
unlock_btn = ctk.CTkButton(
    password_frm,
    text="Unlock",
    width=320,
    height=35,
    fg_color="#4236B8",
    hover_color="#34228A",
    font=("Arial", 14),
    command=unlock
)
unlock_btn.pack()

# Forgot password
forgot = ctk.CTkButton(password_frm, text="Forgot Master Password?", border_color="#08121F",
                       bg_color="#08121F", fg_color="#08121F", text_color="#4a3dca", hover_color="#08121F",
                       command=send_email
                       )
forgot.pack(pady=(20, 8))

# All data encrypted locally
secure_frame = ctk.CTkFrame(main_frame, bg_color="#040d1a", fg_color="#040d1a")
secure_frame.pack(side="bottom", pady=(15, 15))

image_2 = tk.PhotoImage(file="static/security_check.png")

icon_label = tk.Label(
    secure_frame,
    image=image_2,
    bg="#040d1a",
    borderwidth=0
)
icon_label.image = image_2  # type: ignore[attr-defined]
icon_label.pack(side="left", padx=(0, 6))

text_label = tk.Label(
    secure_frame,
    text="All data is encrypted locally",
    bg="#040d1a",
    fg="#DCDEE1",
    font=("Arial", 10)
)
text_label.pack(side="left")

window.mainloop()