import tkinter as tk
from collections.abc import Callable, Mapping

import customtkinter as ctk

from dialog_geometry import place_centered_toplevel
from utils import scale


SettingsProvider = Callable[[], Mapping[str, int]]
SettingsSaver = Callable[[dict[str, int]], str | None]


class SettingsWindow:
    """A single-instance settings toplevel with persisted security options."""

    BACKGROUND = "#050B19"
    SURFACE = "#0C1424"
    FIELD = "#101A2C"
    BORDER = "#273550"
    MUTED = "#9AA6BE"
    ACCENT = "#4236B8"

    REVEAL_CHOICES = (5, 15, 30, 60)
    CLIPBOARD_CHOICES = (15, 30, 60, 120)

    def __init__(
        self,
        parent,
        settings_provider: SettingsProvider,
        on_save: SettingsSaver,
    ) -> None:
        self.parent = parent
        self.settings_provider = settings_provider
        self.on_save = on_save
        self.dialog = None
        self.reveal_var = None
        self.clipboard_var = None
        self.error_label = None

    @staticmethod
    def _format_seconds(seconds: int) -> str:
        return f"{seconds} seconds"

    @staticmethod
    def _parse_seconds(value: str) -> int:
        return int(value.split(maxsplit=1)[0])

    def open(self) -> None:
        if self.dialog is not None:
            try:
                if self.dialog.winfo_exists():
                    self.dialog.deiconify()
                    self.dialog.lift()
                    self.dialog.focus_force()
                    return
            except tk.TclError:
                self.dialog = None

        settings = dict(self.settings_provider())
        reveal_seconds = int(settings.get("password_reveal_seconds", 15))
        clipboard_seconds = int(settings.get("clipboard_clear_seconds", 30))
        if reveal_seconds not in self.REVEAL_CHOICES:
            reveal_seconds = 15
        if clipboard_seconds not in self.CLIPBOARD_CHOICES:
            clipboard_seconds = 30

        dialog = ctk.CTkToplevel(master=self.parent, fg_color=self.BACKGROUND)
        dialog.withdraw()
        dialog.title("SecureVault settings")
        dialog.transient(self.parent)
        dialog.grid_columnconfigure(0, weight=1)
        dialog.grid_rowconfigure(0, weight=1)
        self.dialog = dialog

        content = ctk.CTkScrollableFrame(
            master=dialog,
            fg_color=self.SURFACE,
            border_width=1,
            border_color=self.BORDER,
            corner_radius=12,
            scrollbar_button_color="#34425F",
            scrollbar_button_hover_color="#48597A",
        )
        content.grid(
            row=0,
            column=0,
            sticky="nsew",
            padx=16,
            pady=(16, 8),
        )
        content.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            master=content,
            text="Settings",
            font=("Arial", scale(0.019), "bold"),
            text_color="#FFFFFF",
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=20, pady=(16, 2))
        ctk.CTkLabel(
            master=content,
            text="Tune how SecureVault protects secrets while the vault is open.",
            font=("Arial", scale(0.0095)),
            text_color=self.MUTED,
            anchor="w",
            justify="left",
            wraplength=440,
        ).grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 18))

        self.reveal_var = ctk.StringVar(
            value=self._format_seconds(reveal_seconds)
        )
        self._add_option_card(
            content,
            row=2,
            title="Hide revealed passwords after",
            description=(
                "A visible password is masked again automatically after this "
                "amount of time."
            ),
            variable=self.reveal_var,
            choices=self.REVEAL_CHOICES,
        )

        self.clipboard_var = ctk.StringVar(
            value=self._format_seconds(clipboard_seconds)
        )
        self._add_option_card(
            content,
            row=3,
            title="Clear copied secrets after",
            description=(
                "SecureVault clears the clipboard only if it still contains "
                "the secret copied from this app."
            ),
            variable=self.clipboard_var,
            choices=self.CLIPBOARD_CHOICES,
        )

        trash_card = ctk.CTkFrame(
            master=content,
            fg_color=self.FIELD,
            border_width=1,
            border_color=self.BORDER,
            corner_radius=10,
        )
        trash_card.grid(
            row=4,
            column=0,
            sticky="ew",
            padx=20,
            pady=(0, 12),
        )
        trash_card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            master=trash_card,
            text="Trash retention",
            font=("Arial", scale(0.011), "bold"),
            text_color="#F3F5FA",
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 3))
        ctk.CTkLabel(
            master=trash_card,
            text=(
                "Deleted entries remain recoverable for 3 days. Expired "
                "entries are permanently removed after the next successful login."
            ),
            font=("Arial", scale(0.009)),
            text_color=self.MUTED,
            anchor="w",
            justify="left",
            wraplength=410,
        ).grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 14))

        self.error_label = ctk.CTkLabel(
            master=content,
            text="",
            font=("Arial", scale(0.009)),
            text_color="#FF747D",
        )
        self.error_label.grid(row=5, column=0, sticky="ew", padx=20)

        actions = ctk.CTkFrame(master=dialog, fg_color="transparent")
        actions.grid(row=1, column=0, sticky="ew", padx=16, pady=(8, 16))
        actions.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkButton(
            master=actions,
            text="Cancel",
            command=self.close,
            height=44,
            fg_color="#202B42",
            hover_color="#2C3956",
        ).grid(row=0, column=0, sticky="ew", padx=(0, 7))
        save_button = ctk.CTkButton(
            master=actions,
            text="Save settings",
            command=self._save,
            height=44,
            fg_color=self.ACCENT,
            hover_color="#5044CD",
        )
        save_button.grid(row=0, column=1, sticky="ew", padx=(7, 0))

        dialog.protocol("WM_DELETE_WINDOW", self.close)
        dialog.bind("<Escape>", lambda _event: self.close())
        dialog.bind("<Control-Return>", lambda _event: self._save())
        self._position_dialog(dialog)
        dialog.after(60, lambda: self._present(dialog, save_button))

    def _add_option_card(
        self,
        parent,
        row: int,
        title: str,
        description: str,
        variable,
        choices: tuple[int, ...],
    ) -> None:
        card = ctk.CTkFrame(
            master=parent,
            fg_color=self.FIELD,
            border_width=1,
            border_color=self.BORDER,
            corner_radius=10,
        )
        card.grid(row=row, column=0, sticky="ew", padx=20, pady=(0, 12))
        card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            master=card,
            text=title,
            font=("Arial", scale(0.011), "bold"),
            text_color="#F3F5FA",
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 3))
        ctk.CTkLabel(
            master=card,
            text=description,
            font=("Arial", scale(0.009)),
            text_color=self.MUTED,
            anchor="w",
            justify="left",
            wraplength=300,
        ).grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 14))
        ctk.CTkOptionMenu(
            master=card,
            values=[self._format_seconds(value) for value in choices],
            variable=variable,
            width=135,
            height=38,
            fg_color="#202B42",
            button_color=self.ACCENT,
            button_hover_color="#5044CD",
            dropdown_fg_color=self.FIELD,
        ).grid(
            row=0,
            column=1,
            rowspan=2,
            padx=(8, 16),
            pady=14,
        )

    def _position_dialog(self, dialog) -> None:
        self.parent.update_idletasks()
        place_centered_toplevel(
            dialog,
            self.parent,
            preferred_width=580,
            preferred_height=590,
            minimum_width=400,
            minimum_height=420,
        )
        dialog.resizable(True, True)

    @staticmethod
    def _present(dialog, focus_widget) -> None:
        try:
            if not dialog.winfo_exists():
                return
            dialog.deiconify()
            dialog.lift()
            dialog.grab_set()
            focus_widget.focus_force()
        except tk.TclError:
            pass

    def _save(self):
        if self.reveal_var is None or self.clipboard_var is None:
            return "break"

        values = {
            "password_reveal_seconds": self._parse_seconds(
                self.reveal_var.get()
            ),
            "clipboard_clear_seconds": self._parse_seconds(
                self.clipboard_var.get()
            ),
        }
        try:
            error = self.on_save(values)
        except Exception:
            error = "The settings could not be saved."
        if error:
            if self.error_label is not None:
                self.error_label.configure(text=error)
            return "break"

        self.close()
        return "break"

    def close(self) -> None:
        if self.dialog is None:
            return

        dialog = self.dialog
        self.dialog = None
        self.reveal_var = None
        self.clipboard_var = None
        self.error_label = None
        try:
            dialog.grab_release()
        except tk.TclError:
            pass
        try:
            dialog.destroy()
        except tk.TclError:
            pass
