import sqlite3
import customtkinter as ctk


class EntryLogic:
    def __init__(self, entries):
        self.entries = entries
        self.db = sqlite3.connect("vault.db")
        self.cursor = self.db.cursor()

    def db_empty(self):
        self.cursor.execute("SELECT COUNT(*) FROM passwords")
        count = self.cursor.fetchone()[0]
        if count == 0:
            self.nothing_added_lbl = ctk.CTkLabel(self.entries.entries_frm, text="No entries added", text_color="#000000")
            self.nothing_added_lbl.pack()

    def run(self):
        self.db_empty()
