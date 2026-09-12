"""Manual, isolated UI preview.

Run ``python test_main.py`` to inspect the unlocked interface without touching
the real vault database or OS credential store. Importing this module is safe,
so automated test discovery no longer launches a GUI.
"""

import customtkinter as ctk

from app_controller import VaultAppController
from crypto import Crypto, zero_vault_key
from entries import Entries
from entry_logic import EntryLogic
from settings_window import SettingsWindow
from sidebar import Sidebar
from utils import get_window_size, set_title_bar_color


WINDOW_BACKGROUND = "#040d1a"


def run_preview() -> None:
    window = ctk.CTk(fg_color=WINDOW_BACKGROUND)
    window.title("SecureVault UI Preview")
    width, height = get_window_size()
    x = (window.winfo_screenwidth() - width) // 2
    y = (window.winfo_screenheight() - height) // 2
    window.geometry(f"{width}x{height}+{x}+{y}")
    set_title_bar_color(window)

    preview_key = bytearray(range(32))
    repository = Crypto(":memory:", pepper="securevault-preview-pepper")
    repository.store_entry(
        preview_key,
        "Personal inbox",
        "preview-password",
        "Login",
        service="Gmail",
    )
    repository.store_entry(
        preview_key,
        "Travel card",
        "4111 1111 1111 1111",
        "Card",
        pin="0427",
        expiry="08/29",
    )
    repository.store_entry(
        preview_key,
        "Recovery codes",
        "alpha\nbravo\ncharlie",
        "Note",
    )
    repository.store_entry(
        preview_key,
        "Archived account",
        "old-preview-password",
        "Login",
        service="Example service",
    )
    repository.set_favorite(1, True)
    repository.move_to_trash(4)

    sidebar = Sidebar(window, width, height)
    entries = Entries(window, width, height, preview_key)
    entry_logic = EntryLogic(
        window,
        entries,
        preview_key,
        crypto=repository,
    )
    settings = SettingsWindow(
        window,
        repository.get_app_settings,
        entry_logic.apply_settings,
    )

    def close_preview() -> None:
        zero_vault_key(preview_key)
        repository.close()
        window.destroy()

    controller = VaultAppController(
        sidebar,
        entries,
        entry_logic,
        settings,
        close_preview,
    )
    controller.connect()
    sidebar.run()
    entries.run()
    entry_logic.run()
    window.protocol("WM_DELETE_WINDOW", close_preview)
    window.mainloop()


if __name__ == "__main__":
    run_preview()
