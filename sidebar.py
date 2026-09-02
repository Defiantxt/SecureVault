from functools import partial
from os import listdir

import customtkinter as ctk
from customtkinter import CTkImage
from PIL import Image

from utils import padx, pady, scale, scale_v

# COLORS
BACKGROUND_COLOR = "#040d1a"
SIDEBAR_MAIN_COLOR = "#091221"
NAVY_BLUE = "#151D2E"

class Sidebar:
    """The main-layout sidebar: branding, navigation buttons, and vault status.

    Construction creates all widgets; run() places them in the window
    and wires up icons and hover effects.
    """

    def __init__(self, window, width, height):
        """Create the sidebar widgets: frames, labels, buttons, and lookup tables.

        Note: add_sidebar_btns() grids the nav buttons immediately;
        everything else is placed later by run().
        """
        self.window = window
        self.width = width
        self.height = height
        self.last_clicked_btn = None
        self.action_handler = None

        # FRAMES
        self.main_frm = ctk.CTkFrame(master=self.window,
                                fg_color=BACKGROUND_COLOR,
                                bg_color=BACKGROUND_COLOR,
                                width=self.width)
        self.side_bar_frm = ctk.CTkFrame(master=self.main_frm,
                                    fg_color=SIDEBAR_MAIN_COLOR,
                                    bg_color=SIDEBAR_MAIN_COLOR,
                                    height=self.height)
        self.logo_frame = ctk.CTkFrame(master=self.side_bar_frm,
                                  fg_color="transparent",
                                  bg_color="transparent")
        self.horizontal_border = ctk.CTkFrame(self.side_bar_frm,
                                         width=scale(0.175),
                                         height=2,
                                         fg_color=NAVY_BLUE,
                                         corner_radius=0,
                                         )
        self.vault_unlocked_frm = ctk.CTkFrame(master=self.side_bar_frm,
                                          fg_color="transparent",
                                          bg_color="transparent",
                                          )
        # Full-width top divider: lives in the window (not main_frm) so its
        # width can't dictate how wide the sidebar column becomes.
        self.horizontal_border_2 = ctk.CTkFrame(self.window,
                                         width=1,
                                         height=1,
                                         fg_color=NAVY_BLUE,
                                         corner_radius=0)

        self.horizontal_border_3 = ctk.CTkFrame(self.side_bar_frm,
                                         width=scale(0.175),
                                         height=2,
                                         fg_color=NAVY_BLUE,
                                         corner_radius=0)
        self.right_border = ctk.CTkFrame(self.side_bar_frm,
                                    width=1,
                                    height=height,
                                    fg_color=NAVY_BLUE,
                                    corner_radius=0)
        self.create_security_icon()

        # LABELS
        self.image_labels = {
            "add_new_ent": "plus_icon.png",
            "all_ents": "lock_icon.png",
            "favorites": "star_icon.png",
            "logins": "user_icon.png",
            "cards": "card_icon.png",
            "notes": "notes_icon.png",
            "trash": "trash_icon.png",
            "settings": "settings_icon.png",
            "lock_vault": "lock_vault_icon.png",
        }
        self.labels = {
            "add_new_ent": " Add New Entry",
            "all_ents": "   All Entries",
            "favorites": "   Favorites",
            "logins": "   Logins",
            "cards": "   Cards",
            "notes": "   Notes",
            "trash": "   Trash",
        }
        self.icon_labels = {
            "plus_icon.png": "add_new_ent",
            "lock_icon.png": "all_ents",
            "star_icon.png": "favorites",
            "user_icon.png": "logins",
            "card_icon.png": "cards",
            "notes_icon.png": "notes",
            "trash_icon.png": "trash",
            "settings_icon.png": "settings",
            "lock_vault_icon.png": "lock_vault",
        }
        self.sidebar_btns: dict = self.add_sidebar_btns()

        # cTK Labels
        self.secure_vault = ctk.CTkLabel(master=self.logo_frame,
                                    text="SecureVault",
                                    font=("Arial", scale(0.013), "bold"),
                                    fg_color="transparent",
                                    text_color="#9E93EC")
        self.motto = ctk.CTkLabel(master=self.logo_frame,
                             text="Your passwords. Secure & private.",
                             font=("Arial", scale(0.01)),
                             text_color="#8E96AE",
                             fg_color="transparent",
                             height=10)
        self.security_check_label = ctk.CTkLabel(master=self.vault_unlocked_frm, image=self.security_check_image, text="",)

        self.vault_unlocked_label = ctk.CTkLabel(master=self.vault_unlocked_frm,
                                            text="Vault Unlocked",
                                            font=("Arial", scale(0.0125)),
                                            fg_color="transparent",
                                            text_color="#00C895")

        self.all_data_secure = ctk.CTkLabel(master=self.vault_unlocked_frm,
                                       text="All data is secure",
                                       font=("Arial", scale(0.011)),
                                       text_color="#8E96AE",
                                       fg_color="transparent",
                                       height=10)

        # cTK Buttons
        self.settings = ctk.CTkButton(master=self.side_bar_frm,
                                 text="  Settings",
                                 fg_color=SIDEBAR_MAIN_COLOR,
                                 width=scale(0.2),
                                 height=scale_v(0.067),
                                 hover_color="#34228A",
                                 anchor="w",
                                 font=("Arial", scale(0.0125)),
                                 command=partial(self._handle_button_action, "settings")
                                 )
        self.sidebar_btns["settings"] = self.settings  # add "settings" as a CTk Object
        self.lock_vault = ctk.CTkButton(master=self.side_bar_frm,
                                   text="  Lock Vault",
                                   fg_color=SIDEBAR_MAIN_COLOR,
                                   width=scale(0.2),
                                   height=scale_v(0.076),
                                   hover_color="#34228A",
                                   anchor="w",
                                   font=("Arial", scale(0.0125)),
                                   command=partial(self._handle_button_action, "lock_vault")
                                   )
        self.sidebar_btns["lock_vault"] = self.lock_vault  # add "lock_vault" as a CTk Object

    def create_logo(self):
        """Load the SecureVault logo, crop and scale it, and wrap it in a label.

        Stores the result as self.logo_label; place_labels() puts it on
        screen. Height is derived from the width to keep the aspect ratio.
        """
        logo_width = scale(0.027)
        original_logo = Image.open("static/logo.png")
        original_logo = original_logo.crop(original_logo.getbbox())
        logo_height = int(logo_width * (original_logo.height / original_logo.width))
        logo_image = CTkImage(light_image=original_logo,
                              dark_image=original_logo,
                              size=(logo_width, logo_height))

        self.logo_label = ctk.CTkLabel(master=self.logo_frame, image=logo_image, text="")

    def change_image_on_hover(self, button_key, button_object):
        """Swap a button's icon to its purple variant while hovered.

        Binds <Enter>/<Leave> on `button_object` so the icon switches to
        the matching image in static/icons/purple/ on hover and back to
        the gray version in static/icons/ when the cursor leaves.
        `button_key` must be a key in self.image_labels.
        """
        gray_icon_path = f"static/icons/{self.image_labels[button_key]}"
        purple_icon_path = f"static/icons/purple/{self.image_labels[button_key]}"

        def make_icon(path):
            img = Image.open(path)
            img = img.crop(img.getbbox())
            w = scale(0.015)
            h = int(w * (img.height / img.width))
            return CTkImage(light_image=img, dark_image=img, size=(w, h))

        gray_icon = make_icon(gray_icon_path)
        purple_icon = make_icon(purple_icon_path)

        def on_enter(_):
            button_object.configure(image=purple_icon)

        def on_leave(_):
            # Only revert to gray if this button isn't the currently selected one
            if self.last_clicked_btn != button_key:
                button_object.configure(image=gray_icon)

        button_object.bind("<Enter>", on_enter)
        button_object.bind("<Leave>", on_leave)

    def change_image_on_click(self, button_key, gray=False, purple=False):
        gray_icon_path = f"static/icons/{self.image_labels[button_key]}"
        purple_icon_path = f"static/icons/purple/{self.image_labels[button_key]}"

        def make_icon(path):
            img = Image.open(path)
            img = img.crop(img.getbbox())
            w = scale(0.015)
            h = int(w * (img.height / img.width))
            return CTkImage(light_image=img, dark_image=img, size=(w, h))

        if gray:
            gray_icon = make_icon(gray_icon_path)
            self.sidebar_btns[button_key].configure(image=gray_icon)
        if purple:
            purple_icon = make_icon(purple_icon_path)
            self.sidebar_btns[button_key].configure(image=purple_icon)

    def add_sidebar_btns(self) -> dict:
        """Create and grid the navigation buttons; return them keyed by name.

        Builds one button per entry in self.labels. The first entry
        ("add_new_ent") is styled as the highlighted primary action; the
        rest get the plain sidebar style. Returns a dict mapping each
        label key to its CTkButton so callers can attach icons and
        hover behavior later.
        """
        btn_dict = {}
        for i, (key, text) in enumerate(self.labels.items()):
            btn = ctk.CTkButton(master=self.side_bar_frm,
                              text=text,
                              width=scale(0.2),
                              height=scale_v(0.076),
                              fg_color=SIDEBAR_MAIN_COLOR,
                              hover_color="#34228A",
                              anchor="w",
                              font=("Arial", scale(0.0125)),
                              command=partial(self._handle_button_action, key)
                              )
            if i == 0:
                btn.configure(fg_color="#4236B8",
                              hover_color="#34228A",
                              height=scale_v(0.076),
                              anchor="c",
                              font=("Arial", scale(0.0125)),
                              command=partial(self._handle_button_action, key)
                              )
                btn.grid(row=1, column=0, pady=pady(0.025), padx=padx(0.020))
            else:
                btn.grid(row=i+1, column=0, pady=pady(0.0015))
            btn_dict[key] = btn
        return btn_dict

    def add_icons(self) -> None:
        """Attach its gray icon to every sidebar button.

        Scans static/icons/ (skipping subfolders), maps each file to its
        button via self.icon_labels, and sets the cropped, scaled image
        on the left of the button text. The plus icon gets special
        padding since its button is center-anchored.
        """
        for icon in listdir("static/icons"):
            if "." in icon: #  make sure it's not a folder
                sidebar_dict_key = self.icon_labels[icon]
                sidebar_btn_obj = self.sidebar_btns[sidebar_dict_key]
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

    def place_frames(self) -> None:
        """Grid the layout frames and divider borders into the window."""
        self.main_frm.grid(row=1, column=0, sticky="nsw")
        self.side_bar_frm.grid(row=0, column=0, sticky="w")
        self.logo_frame.grid(row=0, column=0)
        self.horizontal_border.grid(row=8, column=0, pady=(pady(0.015), pady(0.007)))
        self.horizontal_border_2.grid(row=0, column=0, columnspan=2, sticky="new")
        self.horizontal_border_3.grid(row=11, column=0, pady=(pady(0.015), pady(0.035)))
        self.vault_unlocked_frm.grid(row=12, column=0, padx=(padx(0.013), padx(0.007)), pady=(0, pady(0.035)), sticky="w")
        self.right_border.grid(row=0, rowspan=14, column=1, sticky="nsw")


    def place_labels(self) -> None:
        """Grid the branding and vault-status labels into their frames.

        Requires create_logo() to have run first (it creates self.logo_label).
        """
        self.secure_vault.grid(row=0, column=1,
                          padx=padx(0.0007),
                          pady=(pady(0.013), pady(0.027)),
                          sticky="nw")
        self.motto.grid(row=0, column=1,
                   padx=(padx(0.0007), padx(0.027)),
                   pady=(0, pady(0.015)),
                   sticky="s")
        self.logo_label.grid(row=0, column=0, padx=(padx(0.013), padx(0.017)), pady=(pady(0.013), 0))
        self.security_check_label.grid(row=0, column=0, padx=(padx(0.013), padx(0.007)))
        self.vault_unlocked_label.grid(row=0, column=1,
                                  padx=padx(0.01),
                                  pady=(pady(0.01), pady(0.027)),
                                  sticky="nw")
        self.all_data_secure.grid(row=0, column=1,
                                  padx=(padx(0.01), padx(0.027)),
                                  pady=(0, pady(0.010)),
                                  sticky="s")

    def place_buttons(self) -> None:
        """Grid the Settings and Lock Vault buttons at the bottom of the sidebar."""
        self.settings.grid(row=9, column=0, pady=(pady(0.015), pady(0.0015)))
        self.lock_vault.grid(row=10, column=0, pady=(pady(0.0015), 0))

    def create_security_icon(self) -> None:
        """Load the vault-status check icon, cropped and scaled to the window.

        Stores the result as self.security_check_image for use by the
        "Vault Unlocked" status label.
        """
        security_check_height = scale_v(0.045)
        security_check = Image.open("static/security_check.png")
        security_check = security_check.crop(security_check.getbbox())
        security_check_width = int(security_check_height * (security_check.width / security_check.height))
        self.security_check_image = CTkImage(light_image=security_check,
                                             dark_image=security_check,
                                             size=(security_check_width, security_check_height))

    def sidebar_button_clicked(self, button_clicked) -> None:
        """Highlight the clicked nav button and un-highlight the previously selected one."""
        if button_clicked == "add_new_ent" or button_clicked == self.last_clicked_btn:
            return

        if self.last_clicked_btn is not None:
            self.change_image_on_click(self.last_clicked_btn, gray=True)
            self.sidebar_btns[self.last_clicked_btn].configure(fg_color=SIDEBAR_MAIN_COLOR)

        self.last_clicked_btn = button_clicked
        self.change_image_on_click(button_clicked, purple=True)
        self.sidebar_btns[button_clicked].configure(fg_color="#34228A")

    def set_action_handler(self, handler) -> None:
        """Register the application-level callback for sidebar actions."""

        self.action_handler = handler

    def _handle_button_action(self, action: str) -> None:
        """Keep navigation styling and application behavior in one path."""

        navigation_actions = {
            "all_ents",
            "favorites",
            "logins",
            "cards",
            "notes",
            "trash",
        }
        if action in navigation_actions:
            self.sidebar_button_clicked(action)

        if self.action_handler is not None:
            self.action_handler(action)
        elif action == "lock_vault":
            self.window.destroy()

    def run(self) -> None:
        """Assemble the sidebar: place all widgets, add icons, and enable hover effects."""
        self.create_logo()
        self.place_frames()
        self.add_icons()
        for btn, btn_object in self.sidebar_btns.items():
            self.change_image_on_hover(btn, btn_object)
        self.place_labels()
        self.place_buttons()
        self.sidebar_button_clicked("all_ents")
