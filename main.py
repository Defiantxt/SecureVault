import customtkinter as ctk

from app_controller import VaultAppController
from crypto import zero_vault_key
from entries import Entries
from entry_logic import EntryLogic
from login_layout import Login
from settings_window import SettingsWindow
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
if isinstance(vault_key, bytearray):
    unlocked_key = vault_key
    try:
        # Purging is intentionally performed only after successful
        # authentication and before any decrypted records are loaded.
        login.crypto.purge_expired_trash()

        # Reuse the same window: clear the login UI before building the main layout.
        for child in window.winfo_children():
            child.destroy()

        # Reset any column/row config Login applied to the window.
        for i in range(6):
            window.grid_columnconfigure(i, weight=0, minsize=0)
        for i in range(6):
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
        entries = Entries(window, width, height, unlocked_key)
        entry_logic = EntryLogic(
            window,
            entries,
            unlocked_key,
            crypto=login.crypto,
        )
        settings_window = SettingsWindow(
            window,
            entry_logic.crypto.get_app_settings,
            entry_logic.apply_settings,
        )

        def lock_vault() -> None:
            zero_vault_key(unlocked_key)
            window.destroy()

        app_controller = VaultAppController(
            sidebar,
            entries,
            entry_logic,
            settings_window,
            lock_vault,
        )
        app_controller.connect()

        sidebar.run()
        entries.run()
        entry_logic.run()

        window.mainloop()
    finally:
        zero_vault_key(unlocked_key)
        login.crypto.close()
else:
    login.crypto.close()
