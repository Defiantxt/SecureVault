import customtkinter as ctk
from utils import set_title_bar_color, get_window_size
from sidebar import Sidebar
from entries import Entries
from login_layout import Login
from entry_logic import EntryLogic

WINDOW_BACKGROUND = "#040d1a"

# Login window
login_window = ctk.CTk(fg_color=WINDOW_BACKGROUND)
login_window.title("SecureVault")

login = Login(login_window)
login.run()

vault_key = login.get_vault_key()

# Open main app only if login succeeded
if vault_key:
    main_window = ctk.CTk(fg_color=WINDOW_BACKGROUND)
    main_window.title("SecureVault")

    screen_width = main_window.winfo_screenwidth()
    screen_height = main_window.winfo_screenheight()

    width, height = get_window_size()


    x = (screen_width - width) // 2
    y = (screen_height - height) // 2

    main_window.geometry(f"{width}x{height}+{x}+{y}")

    set_title_bar_color(main_window)

    sidebar = Sidebar(main_window, width, height)
    entries = Entries(main_window, width, height, vault_key)
    entry_logic = EntryLogic(main_window, width, height)

    sidebar.run()
    entries.run()

    main_window.mainloop()