import customtkinter as ctk

from entries import Entries
from entry_logic import EntryLogic
from login_layout import Login
from sidebar import Sidebar
from utils import get_window_size

WINDOW_BACKGROUND = "#040d1a"

# Single root window for the whole app (login + main).
window = ctk.CTk(fg_color=WINDOW_BACKGROUND)
window.title("SecureVault")

login = Login(window)
login.run()  # builds the login UI and blocks in mainloop until login finishes

vault_key = login.get_vault_key()

# Open the main app only if login succeeded
if vault_key:
    # Reuse the same window: clear the login UI before building the main layout.
    for child in window.winfo_children():
        child.destroy()

        # Reset any column/row config Login applied to the window
        for i in range(window.grid_size()[0]):
            window.grid_columnconfigure(i, weight=0, minsize=0)
        for i in range(window.grid_size()[1]):
            window.grid_rowconfigure(i, weight=0, minsize=0)

    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()

    width, height = get_window_size()

    scale = window._get_window_scaling()

    scaled_width = round(width * scale)
    scaled_height = round(height * scale)

    x = (screen_width - scaled_width) // 2
    y = (screen_height - scaled_height) // 2

    window.geometry(f"{width}x{height}+{x}+{y}")

    sidebar = Sidebar(window, width, height)
    entries = Entries(window, width, height, vault_key)
    entry_logic = EntryLogic(window, entries, vault_key)
    sidebar.sidebar_btns["add_new_ent"].configure(command=entry_logic.add_entry_popup)

    sidebar.run()
    entries.run()
    entry_logic.run()

    window.mainloop()
