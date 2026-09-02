import ctypes as ct

import customtkinter as ctk
from PIL import Image

from crypto import Crypto
from utils import padx, pady, scale, scale_v, set_title_bar_color

ct.windll.shcore.SetProcessDpiAwareness(2)


class Login:

    def __init__(self, window):
        self.crypto = Crypto()
        self.vault_key: bytearray | None = None

        ctk.set_appearance_mode("dark")

        self.window = window
        self.window.title("SecureVault")
        self.screen_width = window.winfo_screenwidth()
        self.screen_height = window.winfo_screenheight()

        self.width = scale(0.38)
        self.height = scale_v(0.9)
        self.window.grid_rowconfigure(0, weight=1)
        self.window.grid_columnconfigure(0, weight=1)
        x = (self.screen_width - self.width) // 2
        y = (self.screen_height - self.height) // 2
        window.geometry(f"{self.width}x{self.height}+{x}+{y}")
        set_title_bar_color(window, bg="#040d1a")

        # cTK FRAMES
        self.main_frm = ctk.CTkFrame(
            self.window, fg_color="#040d1a", bg_color="#040d1a"
        )
        self.title_frame = ctk.CTkFrame(
            self.main_frm, fg_color="#040d1a", bg_color="#040d1a"
        )
        if self.crypto.user_exists():
            self.password_frm = ctk.CTkFrame(
                self.main_frm,
                width=scale(0.35),
                height=scale_v(0.39),
                fg_color="#08121F",
                border_color="#3D3D3D",
                border_width=1,
            )
        else:
            self.password_frm = ctk.CTkFrame(
                self.main_frm,
                width=scale(0.35),
                height=scale_v(0.3),
                fg_color="#08121F",
                border_color="#3D3D3D",
                border_width=1,
            )
        self.secure_frame = ctk.CTkFrame(
            self.main_frm, bg_color="#040d1a", fg_color="#040d1a"
        )

        # cTK LABELS
        self.secure = ctk.CTkLabel(
            self.title_frame,
            text="Secure",
            fg_color="transparent",
            text_color="#DCDEE1",
            font=("Arial", scale(0.022), "bold"),
        )

        self.vault = ctk.CTkLabel(
            self.title_frame,
            text="Vault",
            fg_color="transparent",
            text_color="#4a3dca",
            font=("Arial", scale(0.022), "bold"),
        )

        self.motto = ctk.CTkLabel(
            self.main_frm,
            text="Your passwords. Secure & private.",
            fg_color="transparent",
            text_color="#DCDEE1",
            font=("Arial", scale_v(0.023)),
        )

        security_check_height = scale_v(0.045)
        security_check = Image.open("static/security_check.png")
        bbox = security_check.getbbox()
        if bbox:
            security_check = security_check.crop(bbox)
        security_check_width = int(
            security_check_height
            * (security_check.width / security_check.height)
        )
        self.image_2 = ctk.CTkImage(
            light_image=security_check,
            dark_image=security_check,
            size=(security_check_width, security_check_height),
        )

        self.icon_label = ctk.CTkLabel(
            self.secure_frame, image=self.image_2, text=""
        )

        if self.crypto.user_exists():
            self.unlock_vault = ctk.CTkLabel(
                self.password_frm,
                text="Unlock Your Vault",
                fg_color="transparent",
                text_color="#DCDEE1",
                font=("Arial", scale_v(0.03), "bold"),
            )
            self.enter_pass = ctk.CTkLabel(
                self.password_frm,
                text="Enter your master password to continue",
                font=("Arial", scale_v(0.025)),
                fg_color="transparent",
                text_color="#DCDEE1",
            )
        else:
            self.create_master = ctk.CTkLabel(
                self.password_frm,
                text="Create Master Password",
                fg_color="transparent",
                text_color="#DCDEE1",
                font=("Arial", scale(0.014), "bold"),
            )
            self.enter_pass = ctk.CTkLabel(
                self.password_frm,
                text="Enter a master password to continue",
                font=("Arial", scale(0.015)),
                fg_color="transparent",
                text_color="#DCDEE1",
            )

        self.text_label = ctk.CTkLabel(
            self.secure_frame,
            text="All data is encrypted locally",
            fg_color="transparent",
            text_color="#DCDEE1",
            font=("Arial", scale_v(0.02)),
        )

        # cTK ENTRIES
        self.password_ent = ctk.CTkEntry(
            self.password_frm,
            width=scale(0.3),
            height=scale_v(0.06),
            placeholder_text="Master Password",
            show="•",
            fg_color="transparent",
            border_width=1,
        )

        # cTK BUTTONS
        self.unlock_btn = ctk.CTkButton(
            self.password_frm,
            width=scale(0.3),
            height=scale_v(0.06),
            text="Unlock",
            fg_color="#4236B8",
            hover_color="#34228A",
            font=("Arial", scale(0.014)),
            command=self.unlock,
        )
        self.sign_up_btn = ctk.CTkButton(
            self.password_frm,
            width=scale(0.3),
            height=scale_v(0.06),
            text="Sign Up",
            fg_color="#4236B8",
            hover_color="#34228A",
            font=("Arial", scale(0.014)),
            command=self.sign_up,
        )
        self.forgot = ctk.CTkButton(
            self.password_frm,
            text="About SecureVault security",
            border_color="#08121F",
            bg_color="#08121F",
            fg_color="#08121F",
            text_color="#4a3dca",
            hover_color="#08121F",
            font=("Arial", scale_v(0.025)),
        )

    def place_frames(self):
        self.main_frm.grid(row=0, column=0)
        self.password_frm.pack_propagate(False)

    def create_logo(self):
        logo_height = scale_v(0.15)
        logo = Image.open("static/logo.png")
        bbox = logo.getbbox()
        if bbox:
            logo = logo.crop(bbox)
        logo_width = int(logo_height * (logo.width / logo.height))
        self.logo = ctk.CTkImage(
            light_image=logo, dark_image=logo, size=(logo_width, logo_height)
        )
        self.image_label = ctk.CTkLabel(
            self.main_frm, image=self.logo, fg_color="transparent", text=""
        )

    def place_labels(self):
        self.image_label.pack(pady=(pady(0.0308), pady(0.0103)))
        self.title_frame.pack(pady=(0, pady(0.0051)))
        self.secure.pack(side="left")
        self.vault.pack(side="left")
        self.motto.pack(pady=(0, pady(0.0205)))

        self.password_frm.pack(
            pady=(pady(0.0154), pady(0.0154)), padx=padx(0.02)
        )
        if self.crypto.user_exists():
            self.unlock_vault.pack(pady=(pady(0.0308), 0))
            self.enter_pass.pack()
        else:
            self.create_master.pack(pady=(pady(0.0308), 0))
            self.enter_pass.pack()

        self.secure_frame.pack(
            side="bottom", pady=(pady(0.0154), pady(0.0154))
        )
        self.icon_label.pack(side="left", padx=(0, padx(0.0075)))
        self.text_label.pack(side="left", pady=pady(0.04))

    def place_buttons(self):
        if self.crypto.user_exists():
            self.unlock_btn.pack()
            self.forgot.pack(pady=pady(0.03))
        else:
            self.sign_up_btn.pack()

    def place_entries(self):
        self.password_ent.pack(
            pady=(pady(0.0205), pady(0.0123)), padx=padx(0.01)
        )

    def unlock(self):
        if len(self.password_ent.get()) == 0:
            self.password_ent.configure(
                placeholder_text="Nothing was entered",
                show="",
                text_color="#DCDEE1",
            )
            self.window.focus()
            self.password_ent.configure(show="•")
            return

        key = self.crypto.verify_master_password_hash(self.password_ent.get())

        if key:
            self.vault_key = key
            # Exit the login mainloop (main.py reuses this same window).
            # Deferred so the button's click animation finishes first.
            self.window.after(150, self.window.quit)
        else:
            self.password_ent.delete(0, "end")
            self.password_ent.configure(
                placeholder_text="Incorrect password",
                show="",
                text_color="#DCDEE1",
            )
            self.window.focus()
            self.password_ent.configure(show="•")

    def sign_up(self):
        if len(self.password_ent.get()) == 0:
            self.password_ent.configure(
                placeholder_text="Nothing was entered",
                show="",
                text_color="#DCDEE1",
            )
            self.window.focus()
            self.password_ent.configure(show="•")

        elif len(self.password_ent.get()) < 8:
            self.password_ent.delete(0, "end")
            self.password_ent.configure(
                placeholder_text="Password is too short",
                show="",
                text_color="#DCDEE1",
            )
            self.window.focus()
            self.password_ent.configure(show="•")

        else:
            self.vault_key = self.crypto.setup_master_password(
                self.password_ent.get()
            )
            # Exit the login mainloop (main.py reuses this same window).
            # Deferred so the button's click animation finishes first.
            self.window.after(150, self.window.quit)

    def get_vault_key(self) -> bytearray | None:
        return self.vault_key

    def run(self):
        self.window.update_idletasks()

        width = self.window.winfo_width()
        height = self.window.winfo_height()

        screen_width = self.window.winfo_screenwidth()
        screen_height = self.window.winfo_screenheight()

        x = (screen_width - width) // 2
        y = (screen_height - height) // 2

        self.window.geometry(f"+{x}+{y}")
        self.create_logo()
        self.place_frames()
        self.place_labels()
        self.place_entries()
        self.place_buttons()
        self.window.mainloop()
