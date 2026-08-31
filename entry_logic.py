import sqlite3
import customtkinter as ctk

from PIL import Image
from crypto import Crypto
from utils import padx, pady, scale, scale_v


class EntryLogic:
    def __init__(self, window, entries, vault_key) -> None:
        self.vault_key = vault_key
        self.crypto = Crypto()
        self.window = window
        self.data = self.crypto.decrypt_passwords(self.vault_key)
        self.entries = entries
        self.db = sqlite3.connect("vault.db")
        self.cursor = self.db.cursor()
        self.entries_data: dict[object, object] = {}

        self.BACKGROUND_COLOR = "#050B19"
        self.ENTRIES_MAIN_COLOR = "#0C1424"

        # Frames
        self.entries_frm = ctk.CTkScrollableFrame(
            master=self.entries.entries_frm,
            border_width=0,
            border_color="#403C85",
            fg_color=self.ENTRIES_MAIN_COLOR,
            bg_color=self.BACKGROUND_COLOR,
            height=scale_v(0.78),
            width=scale(0.3)
        )

        self.entries_frm._scrollbar.grid_remove()

        self.display_entry_data_frm = ctk.CTkFrame(
            master=self.entries.main_frm,
            height=scale_v(0.8),
            width=scale(0.25),
            fg_color=self.ENTRIES_MAIN_COLOR,
            bg_color=self.BACKGROUND_COLOR
        )

        self.display_entry_data_frm.grid_propagate(False)

        self.entry = None

        # Labels
        self.no_entry_selected_lbl = ctk.CTkLabel(
            master=self.display_entry_data_frm,
            text="No entry selected..."
        )

        self.entry_lbl = None

        empty_folder_height = scale_v(0.2)
        gap = scale_v(0.02)

        empty_folder = Image.open("static/no_entries_added.png").convert("RGBA")
        bbox = empty_folder.getchannel("A").getbbox()

        if bbox:
            empty_folder = empty_folder.crop(bbox)

        original_width = empty_folder.width
        original_height = empty_folder.height

        source_gap = int(original_height * (gap / empty_folder_height))

        padded_folder = Image.new(
            "RGBA",
            (original_width, original_height + source_gap),
            (0, 0, 0, 0)
        )

        padded_folder.paste(empty_folder, (0, 0), empty_folder)

        empty_folder_width = int(
            empty_folder_height * (original_width / original_height)
        )

        self.empty_folder_img = ctk.CTkImage(
            light_image=padded_folder,
            dark_image=padded_folder,
            size=(empty_folder_width, empty_folder_height + gap)
        )

        self.nothing_added_lbl = ctk.CTkLabel(
            master=self.entries.entries_frm,
            text="No entries added",
            font=("Arial", scale_v(0.03)),
            text_color="#FFFFFF",
            height=scale_v(0.1),
            image=self.empty_folder_img,
            compound="top"
        )

        # Buttons

    def open_entry(self, entry_text):
        for child in self.display_entry_data_frm.winfo_children():
            child.destroy()

        login_name = ctk.CTkLabel(
            master=self.display_entry_data_frm,
            text=f"{entry_text} -> {self.data[entry_text]}"
        )

        login_name.grid(row=0, column=0)

    def display_entry_data(self):
        self.display_entry_data_frm.grid(row=1, column=3, sticky="nw")

        no_entry_selected_height = scale_v(0.2)
        gap = scale_v(0.02)

        no_entry_selected = Image.open(
            "static/no_entries_selected_fixed.png"
        ).convert("RGBA")

        bbox = no_entry_selected.getchannel("A").getbbox()

        if bbox:
            no_entry_selected = no_entry_selected.crop(bbox)

        original_width = no_entry_selected.width
        original_height = no_entry_selected.height

        source_gap = int(
            original_height * (gap / no_entry_selected_height)
        )

        padded_no_entry_selected = Image.new(
            "RGBA",
            (original_width, original_height + source_gap),
            (0, 0, 0, 0)
        )

        padded_no_entry_selected.paste(
            no_entry_selected,
            (0, 0),
            no_entry_selected
        )

        no_entry_selected_width = int(
            no_entry_selected_height * (original_width / original_height)
        )

        self.no_entry_selected_img = ctk.CTkImage(
            light_image=padded_no_entry_selected,
            dark_image=padded_no_entry_selected,
            size=(no_entry_selected_width, no_entry_selected_height + gap)
        )

        self.no_entry_selected_lbl = ctk.CTkLabel(
            master=self.display_entry_data_frm,
            text="No entry selected...",
            font=("Arial", scale_v(0.03)),
            image=self.no_entry_selected_img,
            compound="top"
        )

        self.display_entry_data_frm.grid_rowconfigure(0, weight=1)
        self.display_entry_data_frm.grid_columnconfigure(0, weight=1)

        self.no_entry_selected_lbl.grid(row=0, column=0)

    def populate_entries(self) -> None:
        self.cursor.execute("SELECT COUNT(*) FROM passwords")
        count = self.cursor.fetchone()[0]

        self.entries_frm.pack(fill="both")

        if count == 0:
            self.nothing_added_lbl.place(
                relx=0.5,
                rely=0.5,
                anchor="center"
            )

        elif self.data is not None:
            self.nothing_added_lbl.place_forget()

            for entry in self.data.keys():
                self.entry = ctk.CTkFrame(
                    master=self.entries_frm,
                    border_width=2,
                    border_color="#403C85",
                    fg_color=self.ENTRIES_MAIN_COLOR,
                    bg_color=self.BACKGROUND_COLOR,
                    width=scale(0.3)
                )

                self.entry_lbl = ctk.CTkLabel(
                    master=self.entry,
                    text=entry,
                    width=scale(0.45),
                    height=scale_v(0.1)
                )

                self.entry.bind(
                    "<Button-1>",
                    lambda event, text=entry: self.open_entry(text)
                )

                self.entry_lbl.bind(
                    "<Button-1>",
                    lambda event, text=entry: self.open_entry(text)
                )

                self.entry.pack(
                    padx=padx(0.02),
                    pady=pady(0.01)
                )

                self.entry_lbl.pack(
                    padx=padx(0.04),
                    pady=pady(0.01)
                )

    def refresh_entries(self) -> None:
        """Reload decrypted data and redraw the entries list."""

        self.data = self.crypto.decrypt_passwords(self.vault_key)

        # clear out old entry widgets
        for child in self.entries_frm.winfo_children():
            child.destroy()

        self.populate_entries()

    def add_entry(self):
        if (
            len(self.entry_password_entry.get()) == 0
            or len(self.entry_name_entry.get()) == 0
        ):
            if len(self.entry_password_entry.get()) == 0:
                self.entry_password_entry.configure(
                    placeholder_text="Nothing entered"
                )

            if len(self.entry_name_entry.get()) == 0:
                self.entry_name_entry.configure(
                    placeholder_text="Nothing entered"
                )

            return

        type_entry = None

        match self.radio_var.get():
            case 1:
                type_entry = "Login"

            case 2:
                type_entry = "Card"

            case 3:
                type_entry = "Note"

        if type_entry:
            self.crypto.store_entry(
                self.vault_key,
                self.entry_name_entry.get(),
                self.entry_password_entry.get(),
                type_entry
            )

            self.dialog.destroy()
            self.refresh_entries()

    def add_entry_popup(self) -> None:
        self.dialog = ctk.CTkToplevel()

        self.dialog.title("Add Entry")
        self.dialog.geometry(f"{scale(0.4)}x{scale_v(0.7)}")
        self.dialog.grid_columnconfigure(0, weight=1)

        # RADIO BUTTON GROUP
        self.radio_var = ctk.IntVar(value=0)

        radio_btns_frm = ctk.CTkFrame(master=self.dialog)

        radio_btns_frm.grid(
            row=0,
            column=0,
            pady=pady(0.02)
        )

        type_entry = ctk.CTkLabel(
            master=radio_btns_frm,
            text="Type of Entry e.g. Login, Card, Note",
            font=("Arial", scale(0.015))
        )

        type_entry.grid(
            row=0,
            column=0,
            columnspan=3,
            pady=(pady(0.02), pady(0.015)),
            padx=padx(0.03)
        )

        login_radio_btn = ctk.CTkRadioButton(
            master=radio_btns_frm,
            text="Login",
            value=1,
            variable=self.radio_var,
            radiobutton_width=scale(0.013),
            radiobutton_height=scale(0.013)
        )

        card_radio_btn = ctk.CTkRadioButton(
            master=radio_btns_frm,
            text="Card",
            value=2,
            variable=self.radio_var,
            radiobutton_width=scale(0.013),
            radiobutton_height=scale(0.013)
        )

        notes_radio_btn = ctk.CTkRadioButton(
            master=radio_btns_frm,
            text="Note",
            value=3,
            variable=self.radio_var,
            radiobutton_width=scale(0.013),
            radiobutton_height=scale(0.013)
        )

        login_radio_btn.grid(
            row=1,
            column=0,
            padx=padx(0.02),
            pady=(0, pady(0.02))
        )

        card_radio_btn.grid(
            row=1,
            column=1,
            padx=padx(0.02),
            pady=(0, pady(0.02))
        )

        notes_radio_btn.grid(
            row=1,
            column=2,
            padx=padx(0.02),
            pady=(0, pady(0.02))
        )

        # ENTRY NAME
        entry_name_lbl = ctk.CTkLabel(
            master=self.dialog,
            text="Entry name:",
            font=("Arial", scale(0.015))
        )

        self.entry_name_entry = ctk.CTkEntry(
            master=self.dialog,
            width=scale(0.35),
            placeholder_text="Entry name"
        )

        entry_name_lbl.grid(
            row=1,
            column=0,
            pady=pady(0.025)
        )

        self.entry_name_entry.grid(
            row=2,
            column=0
        )

        # ENTRY PASSWORD
        entry_password_lbl = ctk.CTkLabel(
            master=self.dialog,
            text="Entry password:",
            font=("Arial", scale(0.015))
        )

        self.entry_password_entry = ctk.CTkEntry(
            master=self.dialog,
            width=scale(0.35),
            placeholder_text="Entry password"
        )

        entry_password_lbl.grid(
            row=3,
            column=0,
            pady=(pady(0.06), pady(0.025))
        )

        self.entry_password_entry.grid(
            row=4,
            column=0
        )

        btns_frm = ctk.CTkFrame(
            master=self.dialog,
            fg_color="transparent"
        )

        btns_frm.grid(
            row=5,
            column=0,
            pady=pady(0.035)
        )

        add_entry_btn = ctk.CTkButton(
            master=btns_frm,
            text="Add entry",
            command=self.add_entry
        )

        add_entry_btn.grid(
            row=0,
            column=0,
            padx=padx(0.02),
            ipadx=scale(0.02),
            ipady=scale_v(0.05)
        )

        cancel_btn = ctk.CTkButton(
            master=btns_frm,
            text="Cancel",
            command=self.dialog.destroy
        )

        cancel_btn.grid(
            row=0,
            column=1,
            padx=padx(0.02)
        )

        self.dialog.mainloop()

    def run(self) -> None:
        self.populate_entries()
        self.display_entry_data()