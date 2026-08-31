import customtkinter as ctk

from entries import Entries
from entry_logic import EntryLogic
from sidebar import Sidebar
from utils import get_window_size, set_title_bar_color

WINDOW_BACKGROUND = "#040d1a"

# Single root window for the whole app (login + main).
window = ctk.CTk(fg_color=WINDOW_BACKGROUND)
window.title("SecureVault")

screen_width = window.winfo_screenwidth()
screen_height = window.winfo_screenheight()

width, height = get_window_size()

x = (screen_width - width) // 2
y = (screen_height - height) // 2

window.geometry(f"{width}x{height}+{x}+{y}")

set_title_bar_color(window)


window.grid_rowconfigure(1, weight=1)
window.grid_columnconfigure(1, weight=1)

sidebar = Sidebar(window, width, height)
entries = Entries(window, width, height, None)
entry_logic = EntryLogic(entries, None)
sidebar.sidebar_btns["add_new_ent"].configure(command=entry_logic.add_entry_popup)

sidebar.run()
entries.run()
entry_logic.run()

window.mainloop()