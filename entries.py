import customtkinter as ctk

from utils import padx, pady, scale, scale_v

# COLORS
BACKGROUND_COLOR = "#050B19"
ENTRIES_MAIN_COLOR = "#0C1424"

class Entries:
    def __init__(self, window, width, height, vault_key):
        self.vault_key = vault_key
        self.window = window
        self.width = width
        self.height = height

        # FRAMES
        self.main_frm = ctk.CTkFrame(master=self.window,
                                    fg_color="#040d1a",
                                    bg_color="#040d1a",
                                    width=self.width
                                    )

        self.entries_frm = ctk.CTkFrame(master=self.main_frm,
                                        fg_color=ENTRIES_MAIN_COLOR,
                                        bg_color=BACKGROUND_COLOR,
                                        )

        # cTK LABELS
        self.option_selected = ctk.CTkLabel(master=self.main_frm,
                                            text="All Entries",
                                            font=("Arial", scale(0.019)),
                                            text_color="#FFFFFF",
                                            fg_color="transparent",
                                            )

        # cTK ENTRIES
        self.search_ent = ctk.CTkEntry(master=self.main_frm,
                                       placeholder_text="Search entries...",
                                       font=("Arial", scale(0.013)),
                                       placeholder_text_color="#8E96AE",
                                       fg_color="transparent",
                                       border_width=1
                                       )

    def place_frames(self):
        # Let the content area follow the window instead of relying on fixed
        # scale()/scale_v() dimensions for whole layout panes.
        self.window.grid_rowconfigure(1, weight=1)
        self.window.grid_columnconfigure(1, weight=1)
        self.main_frm.grid(row=1, column=1, sticky="nsew")
        self.main_frm.grid_columnconfigure(4, weight=1)  # push weight past display_entry_data_frm instead
        self.main_frm.grid_rowconfigure(1, weight=1)
        self.entries_frm.grid(
            row=1,
            column=0,
            columnspan=3,
            sticky="nsew",
            padx=(padx(0.02), padx(0.02)),
            pady=(0, pady(0.02))
        )

    def place_labels(self):
        self.option_selected.grid(row=0, column=0, padx=padx(0.045))

    def place_entries(self):
        self.search_ent.grid(row=0, column=1, pady=pady(0.045))

    def run(self):
        self.place_frames()
        self.place_labels()
        self.place_entries()
