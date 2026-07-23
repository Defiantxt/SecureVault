import sqlite3
from PIL import Image
from entries import Entries
from utils import scale
import customtkinter as ctk

class EntryLogic:
    def __init__(self, window, width, height):
        self.entries = Entries(window, width, height, None)
        self.db = sqlite3.connect("vault.db")
        self.cursor = self.db.cursor()

    def db_empty(self):
        self.cursor.execute("SELECT COUNT(*) FROM passwords")
        count = self.cursor.fetchone()[0]
        if count == 0:
            self.nothing_added_lbl = ctk.CTkLabel(self.entries.entries_frm, text="No entries added", text_color="turquoise")
            self.nothing_added_lbl.pack()