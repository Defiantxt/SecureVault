import customtkinter as ctk
from PIL import Image
from customtkinter import CTkImage
from os import listdir
from utils import set_title_bar_color, scale, scale_v, padx, pady


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
                                    fg_color=BACKGROUND_COLOR,
                                    bg_color=BACKGROUND_COLOR,
                                    width=self.width)
        self.entries_frm = ctk.CTkFrame(master=self.main_frm,
                                        fg_color="#FFFFFF",
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
        self.main_frm.grid(row=0, column=0)
        self.entries_frm.grid(row=1, column=0)

    def place_labels(self):
        self.option_selected.grid(row=0, column=0, padx=padx(0.045))

    def place_entries(self):
        self.search_ent.grid(row=0, column=1)

    def run(self):
        self.place_frames()
        self.place_labels()
        self.place_entries()