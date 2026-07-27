import customtkinter as ctk
from utils import set_title_bar_color, get_window_size
from sidebar import Sidebar
from entries import Entries
from login_layout import Login
from entry_logic import EntryLogic

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

    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()

    width, height = get_window_size()

    x = (screen_width - width) // 2
    y = (screen_height - height) // 2

    window.geometry(f"{width}x{height}+{x}+{y}")

    set_title_bar_color(window)

    sidebar = Sidebar(window, width, height)
    entries = Entries(window, width, height, vault_key)
    entry_logic = EntryLogic(entries)

    sidebar.run()
    entries.run()
    entry_logic.run()

    window.mainloop()
