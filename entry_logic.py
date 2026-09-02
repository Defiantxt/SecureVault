import tkinter as tk
import time

import customtkinter as ctk

from PIL import Image
from add_entry_dialog import AddEntryDialog
from crypto import Crypto, TRASH_RETENTION_SECONDS
from entry_navigation import (
    EntryView,
    filter_entry_records,
    get_empty_state_label,
    get_view_presentation,
)
from utils import padx, pady, scale, scale_v


class EntryLogic:
    def __init__(self, window, entries, vault_key, crypto=None) -> None:
        self.vault_key = vault_key
        self.crypto = crypto if crypto is not None else Crypto()
        self.window = window
        self.entries = entries
        self.current_view = EntryView.ALL_ENTRIES
        self.search_text = ""
        app_settings = self.crypto.get_app_settings()
        self.password_reveal_seconds = int(
            app_settings.get("password_reveal_seconds", 15)
        )
        self.clipboard_clear_seconds = int(
            app_settings.get("clipboard_clear_seconds", 30)
        )
        self.entry_records: dict[int, dict[str, object]] = {}
        self.entry_details: dict[str, dict[str, object]] = {}
        self.data: dict[str, str] = {}
        self._reload_entry_records()
        self.entries_data: dict[int, ctk.CTkFrame] = {}
        self.entry_favorite_btns: dict[int, ctk.CTkButton] = {}
        self.selected_entry_id: int | None = None
        self.selected_entry_name: str | None = None
        self.selected_password = ""
        self.password_is_visible = False
        self.password_value_lbl = None
        self.password_toggle_btn = None
        self.copy_password_btn = None
        self.copy_button_default_text = "Copy password"
        self.note_value_textbox = None
        self.password_hide_after_id = None
        self.clipboard_clear_after_id = None
        self.favorite_btn = None
        self.edit_dialog = None
        self.edit_entry_id = None
        self.edit_name_entry = None
        self.edit_password_entry = None
        self.edit_note_textbox = None
        self.edit_content_lbl = None
        self.edit_content_frm = None
        self.edit_content_drafts = {"password": "", "note": ""}
        self.edit_type_var = None
        self.edit_error_lbl = None
        self.delete_dialog = None
        self.delete_error_lbl = None
        self.add_entry_dialog = AddEntryDialog(
            self.window,
            self._submit_new_entry,
        )

        self.BACKGROUND_COLOR = "#050B19"
        self.ENTRIES_MAIN_COLOR = "#0C1424"
        self.CARD_BORDER_COLOR = "#273550"
        self.SELECTED_BORDER_COLOR = "#7568F8"
        self.MUTED_TEXT = "#9AA6BE"

        # Frames
        self.entries_frm = ctk.CTkScrollableFrame(
            master=self.entries.entries_frm,
            border_width=1,
            border_color=self.CARD_BORDER_COLOR,
            fg_color=self.ENTRIES_MAIN_COLOR,
            bg_color=self.BACKGROUND_COLOR,
            width=scale(0.3),
            corner_radius=scale(0.01)
        )

        self.entries_frm._scrollbar.grid_remove()
        scroll_border_spacing = self.entries_frm._apply_widget_scaling(
            self.entries_frm._parent_frame.cget("corner_radius")
            + self.entries_frm._parent_frame.cget("border_width")
        )
        self.entries_frm._parent_canvas.grid_configure(
            padx=scroll_border_spacing
        )

        self.display_entry_data_frm = ctk.CTkFrame(
            master=self.entries.main_frm,
            width=scale(0.25),
            fg_color=self.ENTRIES_MAIN_COLOR,
            bg_color=self.BACKGROUND_COLOR,
            border_width=1,
            border_color=self.CARD_BORDER_COLOR,
            corner_radius=scale(0.01)
        )

        self.display_entry_data_frm.grid_propagate(False)

        self.entry = None

        # Labels
        self.no_entry_selected_lbl = ctk.CTkLabel(
            master=self.display_entry_data_frm,
            text="No entry selected..."
        )

        self.entry_lbl = None

        empty_folder_height = scale_v(0.2)
        gap = scale_v(0.02)

        empty_folder = Image.open("static/no_entries_added.png").convert("RGBA")
        bbox = empty_folder.getchannel("A").getbbox()

        if bbox:
            empty_folder = empty_folder.crop(bbox)

        original_width = empty_folder.width
        original_height = empty_folder.height

        source_gap = int(original_height * (gap / empty_folder_height))

        padded_folder = Image.new(
            "RGBA",
            (original_width, original_height + source_gap),
            (0, 0, 0, 0)
        )

        padded_folder.paste(empty_folder, (0, 0), empty_folder)

        empty_folder_width = int(
            empty_folder_height * (original_width / original_height)
        )

        self.empty_folder_img = ctk.CTkImage(
            light_image=padded_folder,
            dark_image=padded_folder,
            size=(empty_folder_width, empty_folder_height + gap)
        )

        self.nothing_added_lbl = ctk.CTkLabel(
            master=self.entries.entries_frm,
            text="No entries added",
            font=("Arial", scale_v(0.03)),
            text_color="#FFFFFF",
            height=scale_v(0.1),
            image=self.empty_folder_img,
            compound="top"
        )

        # Buttons

    def _reload_entry_records(self) -> None:
        """Reload records while retaining the legacy name/password mappings."""

        self.entry_records = (
            self.crypto.decrypt_entry_records(self.vault_key) or {}
        )
        self.entry_details = {
            str(record["name"]): {
                "password": str(record["password"]),
                "type": str(record["type"]),
                "favorite": bool(record["favorite"]),
            }
            for record in self.entry_records.values()
            if record.get("deleted_at") is None
        }
        self.data = {
            name: str(details["password"])
            for name, details in self.entry_details.items()
        }

    def _visible_entry_records(self) -> dict[int, dict[str, object]]:
        return filter_entry_records(
            self.entry_records,
            self.current_view,
            self.search_text,
        )

    def show_view(self, view: EntryView | str) -> None:
        """Switch the list to one navigation category."""

        self.current_view = EntryView(view)
        self.entries.set_heading(
            get_view_presentation(self.current_view).title
        )
        self._redraw_current_entries()

    def set_search_query(self, search_text: str) -> None:
        """Apply live name/type search within the selected category."""

        self.search_text = search_text
        self._redraw_current_entries()

    def apply_settings(self, settings: dict[str, int]) -> str | None:
        """Persist validated settings and apply their timers immediately."""

        try:
            for name, value in settings.items():
                self.crypto.set_setting(name, value)
            current = self.crypto.get_app_settings()
            self.password_reveal_seconds = int(
                current["password_reveal_seconds"]
            )
            self.clipboard_clear_seconds = int(
                current["clipboard_clear_seconds"]
            )
        except (KeyError, TypeError, ValueError) as exc:
            return str(exc) or "The settings could not be saved."

        if self.selected_entry_id in self._visible_entry_records():
            self.open_entry(self.selected_entry_id)
        return None

    def _select_entry_card(self, entry_id: int) -> None:
        """Highlight the active entry while returning the others to rest."""

        self.selected_entry_id = entry_id
        for record_id, entry_frame in self.entries_data.items():
            is_selected = record_id == entry_id
            entry_frame.configure(
                border_color=(
                    self.SELECTED_BORDER_COLOR
                    if is_selected
                    else self.CARD_BORDER_COLOR
                ),
                fg_color=("#131C31" if is_selected else self.ENTRIES_MAIN_COLOR)
            )

    def _resolve_entry_id(self, entry: int | str) -> int | None:
        """Resolve legacy name callbacks while preferring stable record IDs."""

        if isinstance(entry, int):
            return entry if entry in self.entry_records else None

        for record_id, record in self.entry_records.items():
            if record["name"] == entry:
                return record_id
        return None

    def _toggle_favorite(self, entry_id: int | None = None) -> None:
        """Toggle favorite state and redraw the list/detail indicators."""

        record_id = (
            entry_id if entry_id is not None else self.selected_entry_id
        )
        if record_id is None or record_id not in self.entry_records:
            return

        record = self.entry_records[record_id]
        if record.get("deleted_at") is not None:
            return

        new_value = not bool(record["favorite"])
        if self.crypto.set_favorite(record_id, new_value):
            record["favorite"] = new_value

            if self.current_view is EntryView.FAVORITES and not new_value:
                self._redraw_current_entries()
                return

            symbol = "\u2605" if new_value else "\u2606"
            color = "#FFC83D" if new_value else "#8E9AB2"

            list_button = self.entry_favorite_btns.get(record_id)
            if list_button is not None:
                list_button.configure(text=symbol, text_color=color)

            if self.selected_entry_id == record_id and self.favorite_btn:
                self.favorite_btn.configure(text=symbol, text_color=color)

    def _cancel_password_hide_timer(self) -> None:
        if self.password_hide_after_id is None:
            return

        try:
            self.window.after_cancel(self.password_hide_after_id)
        except tk.TclError:
            pass
        self.password_hide_after_id = None

    def _mask_password(self) -> None:
        """Mask the current password and reset its reveal control."""

        self.password_hide_after_id = None
        self.password_is_visible = False

        try:
            if self.password_value_lbl is not None:
                self.password_value_lbl.configure(text="\u2022" * 12)
            if self.password_toggle_btn is not None:
                self.password_toggle_btn.configure(text="Show")
        except tk.TclError:
            # The selected card may have been replaced before the timer fired.
            pass

    def _toggle_password_visibility(self) -> None:
        """Reveal briefly or mask the password displayed in the detail card."""

        if self.password_value_lbl is None or self.password_toggle_btn is None:
            return

        if self.password_is_visible:
            self._cancel_password_hide_timer()
            self._mask_password()
            return

        self.password_is_visible = True
        self.password_value_lbl.configure(text=self.selected_password)
        self.password_toggle_btn.configure(text="Hide")
        self.password_hide_after_id = self.window.after(
            self.password_reveal_seconds * 1000,
            self._mask_password
        )

    @staticmethod
    def _reset_copy_button(button, default_text: str) -> None:
        try:
            if button.winfo_exists():
                button.configure(text=default_text)
        except tk.TclError:
            pass

    def _clear_clipboard_if_unchanged(self, copied_password: str) -> None:
        """Clear only the password this app most recently copied."""

        self.clipboard_clear_after_id = None
        try:
            if self.window.clipboard_get() == copied_password:
                self.window.clipboard_clear()
        except tk.TclError:
            # Empty, unavailable, or non-text clipboard content needs no action.
            pass

    def _copy_password(self) -> None:
        """Copy the selected password and briefly confirm the action."""

        if not self.selected_password:
            return

        button = self.copy_password_btn
        copied_password = self.selected_password
        default_text = self.copy_button_default_text

        try:
            self.window.clipboard_clear()
            self.window.clipboard_append(copied_password)
            self.window.update_idletasks()
        except tk.TclError:
            if button is not None:
                button.configure(text="Copy unavailable")
                self.window.after(
                    1600,
                    lambda current_button=button: self._reset_copy_button(
                        current_button,
                        default_text
                    )
                )
            return

        if self.clipboard_clear_after_id is not None:
            try:
                self.window.after_cancel(self.clipboard_clear_after_id)
            except tk.TclError:
                pass

        self.clipboard_clear_after_id = self.window.after(
            self.clipboard_clear_seconds * 1000,
            lambda password=copied_password: self._clear_clipboard_if_unchanged(
                password
            )
        )

        if button is not None:
            button.configure(text="Copied to clipboard")
            self.window.after(
                1600,
                lambda current_button=button: self._reset_copy_button(
                    current_button,
                    default_text
                )
            )

    def _render_entry_value(self, content_frm, entry_type: str) -> None:
        """Render a masked secret or a readable multiline note."""

        is_note = entry_type == "Note"
        value_section = ctk.CTkFrame(
            master=content_frm,
            fg_color="transparent"
        )
        value_section.grid(row=2, column=0, sticky="ew")
        value_section.grid_columnconfigure(0, weight=1)

        value_lbl = ctk.CTkLabel(
            master=value_section,
            text="NOTE" if is_note else "PASSWORD",
            font=("Arial", scale(0.009), "bold"),
            text_color=self.MUTED_TEXT,
            anchor="w"
        )
        value_lbl.grid(row=0, column=0, sticky="w")

        self.password_value_lbl = None
        self.password_toggle_btn = None
        self.note_value_textbox = None

        if is_note:
            note_box = ctk.CTkTextbox(
                master=value_section,
                height=scale_v(0.2),
                fg_color="#101A2C",
                border_width=1,
                border_color=self.CARD_BORDER_COLOR,
                corner_radius=scale(0.008),
                text_color="#F2F4FA",
                font=("Arial", scale(0.011)),
                wrap="word",
                scrollbar_button_color="#34425F",
                scrollbar_button_hover_color="#48597A"
            )
            note_box.grid(
                row=1,
                column=0,
                sticky="ew",
                pady=(pady(0.01), 0)
            )
            note_box.insert("1.0", self.selected_password)
            note_box.configure(state="disabled")
            self.note_value_textbox = note_box
            self.copy_button_default_text = "Copy note"
        else:
            password_box = ctk.CTkFrame(
                master=value_section,
                fg_color="#101A2C",
                border_width=1,
                border_color=self.CARD_BORDER_COLOR,
                corner_radius=scale(0.008)
            )
            password_box.grid(
                row=1,
                column=0,
                sticky="ew",
                pady=(pady(0.01), 0)
            )
            password_box.grid_columnconfigure(0, weight=1)

            self.password_value_lbl = ctk.CTkLabel(
                master=password_box,
                text="\u2022" * 12,
                font=("Consolas", scale(0.012)),
                text_color="#F2F4FA",
                anchor="w",
                justify="left",
                wraplength=scale(0.135)
            )
            self.password_value_lbl.grid(
                row=0,
                column=0,
                sticky="ew",
                padx=(padx(0.012), padx(0.005)),
                pady=pady(0.017)
            )

            self.password_toggle_btn = ctk.CTkButton(
                master=password_box,
                text="Show",
                command=self._toggle_password_visibility,
                width=scale(0.045),
                height=scale_v(0.044),
                fg_color="#202B42",
                hover_color="#2C3956",
                border_width=1,
                border_color="#34425F",
                corner_radius=scale(0.006),
                font=("Arial", scale(0.009), "bold"),
                text_color="#DCE2F0"
            )
            self.password_toggle_btn.grid(
                row=0,
                column=1,
                padx=(0, padx(0.008)),
                pady=pady(0.01)
            )
            self.copy_button_default_text = "Copy password"

        self.copy_password_btn = ctk.CTkButton(
            master=content_frm,
            text=self.copy_button_default_text,
            command=self._copy_password,
            height=scale_v(0.058),
            fg_color="#4236B8",
            hover_color="#5044CD",
            corner_radius=scale(0.008),
            font=("Arial", scale(0.0115), "bold")
        )
        self.copy_password_btn.grid(
            row=3,
            column=0,
            sticky="ew",
            pady=(pady(0.02), 0)
        )

    def open_entry(self, entry: int | str) -> None:
        """Render a polished detail card for the clicked vault entry."""

        entry_id = self._resolve_entry_id(entry)
        if entry_id is None:
            return

        record = self.entry_records[entry_id]
        entry_text = str(record["name"])
        password = str(record["password"])
        entry_type = str(record["type"])
        is_trashed = record.get("deleted_at") is not None

        self._cancel_password_hide_timer()
        self._select_entry_card(entry_id)
        self.selected_entry_name = entry_text
        self.selected_password = password
        self.password_is_visible = False

        for child in self.display_entry_data_frm.winfo_children():
            child.destroy()

        content_frm = ctk.CTkFrame(
            master=self.display_entry_data_frm,
            fg_color="transparent"
        )
        content_frm.grid(
            row=0,
            column=0,
            sticky="nsew",
            padx=padx(0.018),
            pady=pady(0.027)
        )
        content_frm.grid_columnconfigure(0, weight=1)
        content_frm.grid_rowconfigure(5, weight=1)

        header_frm = ctk.CTkFrame(
            master=content_frm,
            fg_color="transparent"
        )
        header_frm.grid(row=0, column=0, sticky="ew")
        header_frm.grid_columnconfigure(1, weight=1)

        avatar_size = scale(0.044)
        avatar_frm = ctk.CTkFrame(
            master=header_frm,
            width=avatar_size,
            height=avatar_size,
            fg_color="#302966",
            border_width=1,
            border_color="#5D52C6",
            corner_radius=scale(0.012)
        )
        avatar_frm.grid(row=0, column=0, rowspan=2, sticky="nw")
        avatar_frm.grid_propagate(False)

        initial = entry_text.strip()[:1].upper() or "?"
        avatar_lbl = ctk.CTkLabel(
            master=avatar_frm,
            text=initial,
            font=("Arial", scale(0.022), "bold"),
            text_color="#C7C1FF"
        )
        avatar_lbl.place(relx=0.5, rely=0.5, anchor="center")

        title_lbl = ctk.CTkLabel(
            master=header_frm,
            text=entry_text,
            font=("Arial", scale(0.018), "bold"),
            text_color="#FFFFFF",
            anchor="w",
            justify="left",
            wraplength=scale(0.15)
        )
        title_lbl.grid(
            row=0,
            column=1,
            sticky="ew",
            padx=(padx(0.014), 0)
        )

        type_lbl = ctk.CTkLabel(
            master=header_frm,
            text=entry_type.upper(),
            font=("Arial", scale(0.0085), "bold"),
            text_color="#B8AEFF",
            fg_color="#272151",
            corner_radius=scale(0.005),
            height=scale_v(0.028)
        )
        type_lbl.grid(
            row=1,
            column=1,
            sticky="w",
            padx=(padx(0.014), 0),
            pady=(pady(0.006), 0),
            ipadx=padx(0.007)
        )

        self.favorite_btn = None
        if not is_trashed:
            is_favorite = bool(record["favorite"])
            self.favorite_btn = ctk.CTkButton(
                master=header_frm,
                text="\u2605" if is_favorite else "\u2606",
                command=lambda record_id=entry_id: self._toggle_favorite(
                    record_id
                ),
                width=scale(0.035),
                height=scale_v(0.05),
                fg_color="transparent",
                hover_color="#202B42",
                corner_radius=scale(0.007),
                font=("Segoe UI Symbol", scale(0.021)),
                text_color="#FFC83D" if is_favorite else "#8E9AB2"
            )
            self.favorite_btn.grid(
                row=0,
                column=2,
                rowspan=2,
                sticky="ne",
                padx=(padx(0.006), 0)
            )
        else:
            ctk.CTkLabel(
                master=header_frm,
                text="TRASHED",
                font=("Arial", scale(0.008), "bold"),
                text_color="#FF9DA5",
                fg_color="#3A1E2A",
                corner_radius=scale(0.005),
                height=scale_v(0.03),
            ).grid(
                row=0,
                column=2,
                rowspan=2,
                sticky="ne",
                padx=(padx(0.006), 0),
                ipadx=padx(0.006),
            )

        divider = ctk.CTkFrame(
            master=content_frm,
            height=1,
            fg_color=self.CARD_BORDER_COLOR,
            corner_radius=0
        )
        divider.grid(
            row=1,
            column=0,
            sticky="ew",
            pady=(pady(0.035), pady(0.03))
        )

        self._render_entry_value(content_frm, entry_type)

        security_background = "#28171E" if is_trashed else "#0D211F"
        security_border = "#603041" if is_trashed else "#17443C"
        status_color = "#FF8B95" if is_trashed else "#35D29A"
        status_text_color = "#EAA4AA" if is_trashed else "#8FD8C2"
        if is_trashed:
            expires_at = int(record["deleted_at"]) + TRASH_RETENTION_SECONDS
            remaining = max(0, expires_at - int(time.time()))
            remaining_days = max(1, (remaining + 86399) // 86400)
            status_text = (
                "In Trash - permanently removed after the next login "
                f"in {remaining_days} day{'s' if remaining_days != 1 else ''}"
                if remaining > 0
                else "In Trash - due for permanent removal at next login"
            )
        else:
            status_text = "Encrypted and stored securely"

        security_frm = ctk.CTkFrame(
            master=content_frm,
            fg_color=security_background,
            border_width=1,
            border_color=security_border,
            corner_radius=scale(0.008)
        )
        security_frm.grid(
            row=4,
            column=0,
            sticky="ew",
            pady=(pady(0.025), 0)
        )
        security_frm.grid_columnconfigure(1, weight=1)

        status_dot = ctk.CTkLabel(
            master=security_frm,
            text="\u2022",
            font=("Arial", scale(0.022), "bold"),
            text_color=status_color,
            width=scale(0.018)
        )
        status_dot.grid(
            row=0,
            column=0,
            padx=(padx(0.01), padx(0.004)),
            pady=pady(0.012)
        )

        status_lbl = ctk.CTkLabel(
            master=security_frm,
            text=status_text,
            font=("Arial", scale(0.0095)),
            text_color=status_text_color,
            anchor="w",
            wraplength=scale(0.16)
        )
        status_lbl.grid(
            row=0,
            column=1,
            sticky="ew",
            padx=(0, padx(0.01)),
            pady=pady(0.012)
        )

        if is_trashed:
            hint_text = (
                "Restore this entry before editing it or adding it to "
                "Favorites."
            )
        elif entry_type == "Note":
            hint_text = (
                "Note content is encrypted and stored securely. Copied notes "
                f"clear from the clipboard after {self.clipboard_clear_seconds} "
                "seconds."
            )
        else:
            hint_text = (
                "Revealed passwords hide after "
                f"{self.password_reveal_seconds} seconds. Copied passwords "
                f"clear after {self.clipboard_clear_seconds} seconds."
            )
        hint_lbl = ctk.CTkLabel(
            master=content_frm,
            text=hint_text,
            font=("Arial", scale(0.009)),
            text_color="#707C94",
            justify="left",
            anchor="sw",
            wraplength=scale(0.2)
        )
        hint_lbl.grid(
            row=6,
            column=0,
            sticky="sew",
            pady=(0, pady(0.018))
        )

        actions_frm = ctk.CTkFrame(
            master=content_frm,
            fg_color="transparent"
        )
        actions_frm.grid(row=7, column=0, sticky="ew")
        actions_frm.grid_columnconfigure((0, 1), weight=1)

        if is_trashed:
            restore_btn = ctk.CTkButton(
                master=actions_frm,
                text="Restore",
                command=lambda record_id=entry_id: self._restore_entry(
                    record_id
                ),
                height=scale_v(0.058),
                fg_color="#274F47",
                hover_color="#32665B",
                corner_radius=scale(0.008),
                font=("Arial", scale(0.0115), "bold"),
            )
            restore_btn.grid(
                row=0,
                column=0,
                sticky="ew",
                padx=(0, padx(0.007)),
            )

            delete_btn = ctk.CTkButton(
                master=actions_frm,
                text="Delete permanently",
                command=lambda record_id=entry_id: self.delete_entry_popup(
                    record_id
                ),
                height=scale_v(0.058),
                fg_color="#3A1E2A",
                hover_color="#522535",
                border_width=1,
                border_color="#6B2B3E",
                corner_radius=scale(0.008),
                font=("Arial", scale(0.0105), "bold"),
                text_color="#FF747D",
            )
            delete_btn.grid(
                row=0,
                column=1,
                sticky="ew",
                padx=(padx(0.007), 0),
            )
        else:
            edit_btn = ctk.CTkButton(
                master=actions_frm,
                text="Edit",
                command=lambda record_id=entry_id: self.edit_entry_popup(
                    record_id
                ),
                height=scale_v(0.058),
                fg_color="#35318A",
                hover_color="#4540A6",
                corner_radius=scale(0.008),
                font=("Arial", scale(0.0115), "bold")
            )
            edit_btn.grid(
                row=0,
                column=0,
                sticky="ew",
                padx=(0, padx(0.007))
            )

            delete_btn = ctk.CTkButton(
                master=actions_frm,
                text="Move to trash",
                command=lambda record_id=entry_id: self.delete_entry_popup(
                    record_id
                ),
                height=scale_v(0.058),
                fg_color="#3A1E2A",
                hover_color="#522535",
                border_width=1,
                border_color="#6B2B3E",
                corner_radius=scale(0.008),
                font=("Arial", scale(0.011), "bold"),
                text_color="#FF747D"
            )
            delete_btn.grid(
                row=0,
                column=1,
                sticky="ew",
                padx=(padx(0.007), 0)
            )

    def _place_dialog(self, dialog, width: int, height: int) -> None:
        """Size and center a modal over the SecureVault window."""

        # CustomTkinter redraws the Windows title bar shortly after a
        # CTkToplevel is created. Build the dialog while hidden so that redraw
        # cannot return focus to the button which opened it.
        dialog.withdraw()
        self.window.update_idletasks()
        x = self.window.winfo_rootx() + (
            self.window.winfo_width() - width
        ) // 2
        y = self.window.winfo_rooty() + (
            self.window.winfo_height() - height
        ) // 2
        dialog.geometry(f"{width}x{height}+{x}+{y}")
        dialog.resizable(False, False)
        dialog.transient(self.window)

    @staticmethod
    def _show_modal(dialog, focus_widget=None) -> None:
        """Present a built dialog after CustomTkinter's title-bar redraw."""

        def focus_modal_if_needed() -> None:
            try:
                dialog.attributes("-topmost", False)
                dialog.lift()
                focused = dialog.focus_displayof()
                focus_is_inside = (
                    focused is not None
                    and focused.winfo_toplevel() == dialog
                )
                if not focus_is_inside:
                    if (
                        focus_widget is not None
                        and focus_widget.winfo_exists()
                    ):
                        focus_widget.focus_force()
                    else:
                        dialog.focus_force()
            except tk.TclError:
                pass

        def present() -> None:
            try:
                if not dialog.winfo_exists():
                    return
                # A brief topmost phase keeps Windows from placing the owner
                # back over the popup while CustomTkinter finishes its delayed
                # title-bar work. It is removed immediately after settling.
                dialog.attributes("-topmost", True)
                dialog.deiconify()
                dialog.lift()
                dialog.grab_set()
                if focus_widget is not None and focus_widget.winfo_exists():
                    focus_widget.focus_force()
                else:
                    dialog.focus_force()
                dialog.after(140, focus_modal_if_needed)
            except tk.TclError:
                pass

        dialog.after(60, present)

    @staticmethod
    def _close_dialog(dialog) -> None:
        try:
            dialog.grab_release()
        except tk.TclError:
            pass
        dialog.destroy()

    def _close_edit_dialog(self) -> None:
        """Close the editor and release references to its plaintext fields."""

        if self.edit_dialog is None:
            return

        try:
            if self.edit_name_entry is not None:
                self.edit_name_entry.delete(0, "end")
            if self.edit_password_entry is not None:
                self.edit_password_entry.delete(0, "end")
            if self.edit_note_textbox is not None:
                self.edit_note_textbox.delete("1.0", "end")
        except tk.TclError:
            pass

        dialog = self.edit_dialog
        self.edit_dialog = None
        self.edit_entry_id = None
        self.edit_name_entry = None
        self.edit_password_entry = None
        self.edit_note_textbox = None
        self.edit_content_lbl = None
        self.edit_content_frm = None
        self.edit_content_drafts = {"password": "", "note": ""}
        self.edit_type_var = None
        self.edit_error_lbl = None
        self._close_dialog(dialog)

    def _close_delete_dialog(self) -> None:
        if self.delete_dialog is None:
            return

        dialog = self.delete_dialog
        self.delete_dialog = None
        self.delete_error_lbl = None
        self._close_dialog(dialog)

    def _cache_edit_content(self) -> None:
        """Retain independent drafts when changing an entry's type."""

        try:
            if self.edit_password_entry is not None:
                self.edit_content_drafts["password"] = (
                    self.edit_password_entry.get()
                )
            if self.edit_note_textbox is not None:
                self.edit_content_drafts["note"] = (
                    self.edit_note_textbox.get("1.0", "end-1c")
                )
        except tk.TclError:
            pass

    def _render_edit_content_input(self, entry_type: str) -> None:
        """Swap the edit form between a secret field and note editor."""

        if self.edit_content_frm is None or self.edit_content_lbl is None:
            return

        self._cache_edit_content()
        for child in self.edit_content_frm.winfo_children():
            child.destroy()

        self.edit_password_entry = None
        self.edit_note_textbox = None
        is_note = entry_type == "Note"
        self.edit_content_lbl.configure(
            text="NOTE CONTENT" if is_note else "PASSWORD"
        )

        if is_note:
            self.edit_note_textbox = ctk.CTkTextbox(
                master=self.edit_content_frm,
                height=scale_v(0.16),
                fg_color="#101A2C",
                border_width=1,
                border_color=self.CARD_BORDER_COLOR,
                corner_radius=scale(0.007),
                text_color="#FFFFFF",
                font=("Arial", scale(0.011)),
                wrap="word",
                scrollbar_button_color="#34425F",
                scrollbar_button_hover_color="#48597A"
            )
            self.edit_note_textbox.grid(row=0, column=0, sticky="ew")
            self.edit_note_textbox.insert(
                "1.0",
                self.edit_content_drafts["note"]
            )
            self.edit_note_textbox.bind(
                "<Control-Return>",
                lambda _event: self._save_edit_shortcut()
            )
            self.edit_note_textbox.bind(
                "<Control-KP_Enter>",
                lambda _event: self._save_edit_shortcut()
            )
            self.edit_note_textbox.after(
                1,
                self.edit_note_textbox.focus_set
            )
            return

        self.edit_content_frm.grid_columnconfigure(0, weight=1)
        self.edit_password_entry = ctk.CTkEntry(
            master=self.edit_content_frm,
            height=scale_v(0.055),
            fg_color="#101A2C",
            border_color=self.CARD_BORDER_COLOR,
            text_color="#FFFFFF",
            show="\u2022"
        )
        self.edit_password_entry.insert(
            0,
            self.edit_content_drafts["password"]
        )
        self.edit_password_entry.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=(0, padx(0.008))
        )
        self.edit_password_entry.bind(
            "<Return>",
            lambda _event: self._save_edit_shortcut()
        )

        password_visible = False

        def toggle_edit_password() -> None:
            nonlocal password_visible
            password_visible = not password_visible
            if self.edit_password_entry is None:
                return
            self.edit_password_entry.configure(
                show="" if password_visible else "\u2022"
            )
            reveal_btn.configure(
                text="Hide" if password_visible else "Show"
            )

        reveal_btn = ctk.CTkButton(
            master=self.edit_content_frm,
            text="Show",
            command=toggle_edit_password,
            width=scale(0.052),
            height=scale_v(0.055),
            fg_color="#202B42",
            hover_color="#2C3956",
            border_width=1,
            border_color="#34425F",
            corner_radius=scale(0.006)
        )
        reveal_btn.grid(row=0, column=1)

    def _save_edit_shortcut(self):
        """Save the current editor without inserting a newline."""

        if self.edit_entry_id is not None:
            self._save_entry_edits(self.edit_entry_id)
        return "break"

    def edit_entry_popup(self, entry_id: int) -> None:
        """Open a styled form for editing an encrypted vault record."""

        record = self.entry_records.get(entry_id)
        if record is None or record.get("deleted_at") is not None:
            return

        self._cancel_password_hide_timer()
        self._mask_password()

        dialog = ctk.CTkToplevel(
            master=self.window,
            fg_color=self.ENTRIES_MAIN_COLOR
        )
        dialog.title("Edit entry")
        self.edit_dialog = dialog
        self.edit_entry_id = entry_id
        self._place_dialog(dialog, scale(0.34), scale_v(0.7))
        dialog.grid_columnconfigure(0, weight=1)

        title_lbl = ctk.CTkLabel(
            master=dialog,
            text="Edit vault entry",
            font=("Arial", scale(0.018), "bold"),
            text_color="#FFFFFF",
            anchor="w"
        )
        title_lbl.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=padx(0.025),
            pady=(pady(0.03), pady(0.025))
        )

        name_lbl = ctk.CTkLabel(
            master=dialog,
            text="ENTRY NAME",
            font=("Arial", scale(0.009), "bold"),
            text_color=self.MUTED_TEXT,
            anchor="w"
        )
        name_lbl.grid(
            row=1,
            column=0,
            sticky="ew",
            padx=padx(0.025)
        )

        self.edit_name_entry = ctk.CTkEntry(
            master=dialog,
            height=scale_v(0.055),
            fg_color="#101A2C",
            border_color=self.CARD_BORDER_COLOR,
            text_color="#FFFFFF"
        )
        self.edit_name_entry.insert(0, str(record["name"]))
        self.edit_name_entry.grid(
            row=2,
            column=0,
            sticky="ew",
            padx=padx(0.025),
            pady=(pady(0.008), pady(0.022))
        )

        type_lbl = ctk.CTkLabel(
            master=dialog,
            text="ENTRY TYPE",
            font=("Arial", scale(0.009), "bold"),
            text_color=self.MUTED_TEXT,
            anchor="w"
        )
        type_lbl.grid(
            row=3,
            column=0,
            sticky="ew",
            padx=padx(0.025)
        )

        entry_types = ["Login", "Card", "Note"]
        selected_type = str(record["type"])
        if selected_type not in entry_types:
            entry_types.append(selected_type)
        self.edit_type_var = ctk.StringVar(value=selected_type)
        type_menu = ctk.CTkOptionMenu(
            master=dialog,
            values=entry_types,
            variable=self.edit_type_var,
            command=self._render_edit_content_input,
            height=scale_v(0.055),
            fg_color="#202B42",
            button_color="#4236B8",
            button_hover_color="#5044CD",
            dropdown_fg_color="#101A2C"
        )
        type_menu.grid(
            row=4,
            column=0,
            sticky="ew",
            padx=padx(0.025),
            pady=(pady(0.008), pady(0.022))
        )

        self.edit_content_lbl = ctk.CTkLabel(
            master=dialog,
            text="PASSWORD",
            font=("Arial", scale(0.009), "bold"),
            text_color=self.MUTED_TEXT,
            anchor="w"
        )
        self.edit_content_lbl.grid(
            row=5,
            column=0,
            sticky="ew",
            padx=padx(0.025)
        )

        self.edit_content_frm = ctk.CTkFrame(
            master=dialog,
            fg_color="transparent"
        )
        self.edit_content_frm.grid(
            row=6,
            column=0,
            sticky="ew",
            padx=padx(0.025),
            pady=(pady(0.008), pady(0.012))
        )
        self.edit_content_frm.grid_columnconfigure(0, weight=1)
        current_content = str(record["password"])
        self.edit_content_drafts = {
            "password": current_content,
            "note": current_content,
        }
        self._render_edit_content_input(selected_type)

        self.edit_error_lbl = ctk.CTkLabel(
            master=dialog,
            text="",
            font=("Arial", scale(0.0095)),
            text_color="#FF747D"
        )
        self.edit_error_lbl.grid(
            row=7,
            column=0,
            sticky="ew",
            padx=padx(0.025)
        )

        actions_frm = ctk.CTkFrame(
            master=dialog,
            fg_color="transparent"
        )
        actions_frm.grid(
            row=8,
            column=0,
            sticky="ew",
            padx=padx(0.025),
            pady=(pady(0.012), pady(0.03))
        )
        actions_frm.grid_columnconfigure((0, 1), weight=1)

        cancel_btn = ctk.CTkButton(
            master=actions_frm,
            text="Cancel",
            command=self._close_edit_dialog,
            height=scale_v(0.055),
            fg_color="#202B42",
            hover_color="#2C3956"
        )
        cancel_btn.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=(0, padx(0.007))
        )

        save_btn = ctk.CTkButton(
            master=actions_frm,
            text="Save changes",
            command=lambda: self._save_entry_edits(entry_id),
            height=scale_v(0.055),
            fg_color="#4236B8",
            hover_color="#5044CD"
        )
        save_btn.grid(
            row=0,
            column=1,
            sticky="ew",
            padx=(padx(0.007), 0)
        )

        dialog.protocol(
            "WM_DELETE_WINDOW",
            self._close_edit_dialog
        )
        dialog.bind(
            "<Escape>",
            lambda _event: self._close_edit_dialog()
        )
        dialog.bind(
            "<Control-Return>",
            lambda _event: self._save_edit_shortcut()
        )
        dialog.bind(
            "<Control-KP_Enter>",
            lambda _event: self._save_edit_shortcut()
        )
        self.edit_name_entry.bind(
            "<Return>",
            lambda _event: self._save_edit_shortcut()
        )
        self._show_modal(dialog, self.edit_name_entry)

    def _save_entry_edits(self, entry_id: int) -> None:
        """Validate and persist the edit dialog's encrypted values."""

        if (
            self.edit_dialog is None
            or self.edit_name_entry is None
            or self.edit_type_var is None
        ):
            return

        name = self.edit_name_entry.get().strip()
        entry_type = self.edit_type_var.get()
        if entry_type == "Note":
            if self.edit_note_textbox is None:
                return
            content = self.edit_note_textbox.get("1.0", "end-1c")
        else:
            if self.edit_password_entry is None:
                return
            content = self.edit_password_entry.get()

        if not name or not content.strip():
            if self.edit_error_lbl is not None:
                self.edit_error_lbl.configure(
                    text=(
                        "Entry name and note content are required."
                        if entry_type == "Note"
                        else "Entry name and password are required."
                    )
                )
            return

        if not self.crypto.update_entry(
            self.vault_key,
            entry_id,
            name,
            content,
            entry_type
        ):
            if self.edit_error_lbl is not None:
                self.edit_error_lbl.configure(
                    text="This entry no longer exists."
                )
            return

        self.selected_entry_id = entry_id
        self._close_edit_dialog()
        self.refresh_entries()

    def delete_entry_popup(self, entry_id: int) -> None:
        """Confirm moving an active entry to Trash or deleting trashed data."""

        record = self.entry_records.get(entry_id)
        if record is None:
            return
        permanent = record.get("deleted_at") is not None

        self._cancel_password_hide_timer()
        self._mask_password()

        dialog = ctk.CTkToplevel(
            master=self.window,
            fg_color=self.ENTRIES_MAIN_COLOR
        )
        dialog.title("Permanently delete entry" if permanent else "Move to Trash")
        self.delete_dialog = dialog
        self._place_dialog(dialog, scale(0.29), scale_v(0.34))
        dialog.grid_columnconfigure(0, weight=1)

        title_lbl = ctk.CTkLabel(
            master=dialog,
            text=(
                "Permanently delete this entry?"
                if permanent
                else "Move this entry to Trash?"
            ),
            font=("Arial", scale(0.017), "bold"),
            text_color="#FFFFFF"
        )
        title_lbl.grid(
            row=0,
            column=0,
            padx=padx(0.025),
            pady=(pady(0.035), pady(0.018))
        )

        message_lbl = ctk.CTkLabel(
            master=dialog,
            text=(
                f'"{record["name"]}" will be permanently deleted. '
                "This action cannot be undone."
                if permanent
                else (
                    f'"{record["name"]}" will stay in Trash for 3 days. '
                    "You can restore it before it expires."
                )
            ),
            font=("Arial", scale(0.0105)),
            text_color=self.MUTED_TEXT,
            justify="center",
            wraplength=scale(0.22)
        )
        message_lbl.grid(
            row=1,
            column=0,
            padx=padx(0.025),
            pady=(0, pady(0.012))
        )

        self.delete_error_lbl = ctk.CTkLabel(
            master=dialog,
            text="",
            font=("Arial", scale(0.0095)),
            text_color="#FF747D"
        )
        self.delete_error_lbl.grid(row=2, column=0)

        actions_frm = ctk.CTkFrame(
            master=dialog,
            fg_color="transparent"
        )
        actions_frm.grid(
            row=3,
            column=0,
            sticky="ew",
            padx=padx(0.025),
            pady=(pady(0.012), pady(0.03))
        )
        actions_frm.grid_columnconfigure((0, 1), weight=1)

        cancel_btn = ctk.CTkButton(
            master=actions_frm,
            text="Cancel",
            command=self._close_delete_dialog,
            height=scale_v(0.055),
            fg_color="#202B42",
            hover_color="#2C3956"
        )
        cancel_btn.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=(0, padx(0.007))
        )

        delete_btn = ctk.CTkButton(
            master=actions_frm,
            text="Delete permanently" if permanent else "Move to Trash",
            command=lambda: self._confirm_delete(entry_id, permanent),
            height=scale_v(0.055),
            fg_color="#8A293C",
            hover_color="#A5354A",
            text_color="#FFFFFF"
        )
        delete_btn.grid(
            row=0,
            column=1,
            sticky="ew",
            padx=(padx(0.007), 0)
        )

        dialog.protocol(
            "WM_DELETE_WINDOW",
            self._close_delete_dialog
        )
        dialog.bind(
            "<Escape>",
            lambda _event: self._close_delete_dialog()
        )
        self._show_modal(dialog, cancel_btn)

    def _confirm_delete(self, entry_id: int, permanent: bool = False) -> None:
        """Apply the lifecycle action captured by the confirmation dialog."""

        changed = (
            self.crypto.permanently_delete_entry(entry_id)
            if permanent
            else self.crypto.move_to_trash(entry_id)
        )
        if not changed:
            if self.delete_error_lbl is not None:
                self.delete_error_lbl.configure(
                    text="This entry no longer exists."
                )
            return

        self._close_delete_dialog()

        if self.selected_entry_id == entry_id:
            self.selected_entry_id = None
            self.selected_entry_name = None
            self.selected_password = ""
        self.refresh_entries()

    def _restore_entry(self, entry_id: int) -> None:
        """Restore a trashed entry as an active, non-favorite record."""

        if not self.crypto.restore_entry(entry_id):
            return
        if self.selected_entry_id == entry_id:
            self.selected_entry_id = None
            self.selected_entry_name = None
            self.selected_password = ""
        self.refresh_entries()

    def display_entry_data(self):
        self.display_entry_data_frm.grid(
            row=1,
            column=3,
            sticky="nsew",
            padx=(0, padx(0.018)),
            pady=(0, pady(0.02))
        )

        no_entry_selected_height = scale_v(0.2)
        gap = scale_v(0.02)

        no_entry_selected = Image.open(
            "static/no_entries_selected_fixed.png"
        ).convert("RGBA")

        bbox = no_entry_selected.getchannel("A").getbbox()

        if bbox:
            no_entry_selected = no_entry_selected.crop(bbox)

        original_width = no_entry_selected.width
        original_height = no_entry_selected.height

        source_gap = int(
            original_height * (gap / no_entry_selected_height)
        )

        padded_no_entry_selected = Image.new(
            "RGBA",
            (original_width, original_height + source_gap),
            (0, 0, 0, 0)
        )

        padded_no_entry_selected.paste(
            no_entry_selected,
            (0, 0),
            no_entry_selected
        )

        no_entry_selected_width = int(
            no_entry_selected_height * (original_width / original_height)
        )

        self.no_entry_selected_img = ctk.CTkImage(
            light_image=padded_no_entry_selected,
            dark_image=padded_no_entry_selected,
            size=(no_entry_selected_width, no_entry_selected_height + gap)
        )

        self.no_entry_selected_lbl = ctk.CTkLabel(
            master=self.display_entry_data_frm,
            text="No entry selected...",
            font=("Arial", scale_v(0.03)),
            text_color="#D7DCE8",
            image=self.no_entry_selected_img,
            compound="top"
        )

        self.display_entry_data_frm.grid_rowconfigure(0, weight=1)
        self.display_entry_data_frm.grid_columnconfigure(0, weight=1)

        self.no_entry_selected_lbl.grid(row=0, column=0)

    def populate_entries(self) -> None:
        self.entries_data.clear()
        self.entry_favorite_btns.clear()
        self.entries_frm.pack(fill="both", expand=True)
        visible_records = self._visible_entry_records()

        if not visible_records:
            self.nothing_added_lbl.configure(
                text=get_empty_state_label(
                    self.current_view,
                    self.search_text,
                )
            )
            self.nothing_added_lbl.place(
                relx=0.5,
                rely=0.5,
                anchor="center"
            )

        else:
            self.nothing_added_lbl.place_forget()

            for entry_id, record in visible_records.items():
                entry_name = str(record["name"])
                self.entry = ctk.CTkFrame(
                    master=self.entries_frm,
                    border_width=1,
                    border_color=self.CARD_BORDER_COLOR,
                    fg_color=self.ENTRIES_MAIN_COLOR,
                    bg_color=self.BACKGROUND_COLOR,
                    width=scale(0.3),
                    corner_radius=scale(0.008)
                )
                self.entry.grid_columnconfigure(0, weight=1)

                self.entry_lbl = ctk.CTkLabel(
                    master=self.entry,
                    text=entry_name,
                    width=scale(0.2),
                    height=scale_v(0.075),
                    font=("Arial", scale(0.012), "bold"),
                    text_color="#F4F6FB",
                    anchor="w",
                    justify="left",
                    wraplength=scale(0.19)
                )

                is_trashed = record.get("deleted_at") is not None
                if is_trashed:
                    favorite_btn = ctk.CTkLabel(
                        master=self.entry,
                        text="TRASH",
                        width=scale(0.04),
                        height=scale_v(0.04),
                        fg_color="#3A1E2A",
                        corner_radius=scale(0.005),
                        font=("Arial", scale(0.0075), "bold"),
                        text_color="#FF9DA5",
                    )
                else:
                    is_favorite = bool(record["favorite"])
                    favorite_btn = ctk.CTkButton(
                        master=self.entry,
                        text="\u2605" if is_favorite else "\u2606",
                        command=lambda record_id=entry_id: self._toggle_favorite(
                            record_id
                        ),
                        width=scale(0.04),
                        height=scale_v(0.055),
                        fg_color="transparent",
                        hover_color="#202B42",
                        corner_radius=scale(0.006),
                        font=("Segoe UI Symbol", scale(0.017)),
                        text_color="#FFC83D" if is_favorite else "#8E9AB2"
                    )

                self.entries_data[entry_id] = self.entry
                if not is_trashed:
                    self.entry_favorite_btns[entry_id] = favorite_btn

                self.entry.bind(
                    "<Button-1>",
                    lambda event, record_id=entry_id: self.open_entry(
                        record_id
                    )
                )

                self.entry_lbl.bind(
                    "<Button-1>",
                    lambda event, record_id=entry_id: self.open_entry(
                        record_id
                    )
                )

                self.entry.pack(
                    fill="x",
                    padx=padx(0.02),
                    pady=pady(0.01)
                )

                self.entry_lbl.grid(
                    row=0,
                    column=0,
                    sticky="ew",
                    padx=(padx(0.018), padx(0.004)),
                    pady=pady(0.008)
                )

                favorite_btn.grid(
                    row=0,
                    column=1,
                    padx=(padx(0.004), padx(0.012)),
                    pady=pady(0.008)
                )

    def refresh_entries(self) -> None:
        """Reload decrypted data and redraw the entries list."""

        self._reload_entry_records()
        self._redraw_current_entries()

    def _redraw_current_entries(self) -> None:
        """Redraw the active view and keep only a still-visible selection."""

        previous_selection = self.selected_entry_id

        for child in self.entries_frm.winfo_children():
            child.destroy()

        self.populate_entries()
        visible_records = self._visible_entry_records()

        if previous_selection in visible_records:
            self.open_entry(previous_selection)
        else:
            self._reset_entry_detail()

    def _reset_entry_detail(self) -> None:
        self._cancel_password_hide_timer()
        self.selected_entry_id = None
        self.selected_entry_name = None
        self.selected_password = ""
        self.password_is_visible = False
        self.password_value_lbl = None
        self.password_toggle_btn = None
        self.copy_password_btn = None
        self.copy_button_default_text = "Copy password"
        self.note_value_textbox = None
        self.favorite_btn = None

        for child in self.display_entry_data_frm.winfo_children():
            child.destroy()
        self.display_entry_data()

    def _submit_new_entry(
        self,
        name: str,
        content: str,
        entry_type: str,
    ) -> str | None:
        """Encrypt a validated dialog submission and refresh the view."""

        try:
            self.crypto.store_entry(
                self.vault_key,
                name,
                content,
                entry_type,
            )
            self.refresh_entries()
        except Exception:
            return "The entry could not be saved."
        return None

    def add_entry_popup(self) -> None:
        self.add_entry_dialog.open()

    def run(self) -> None:
        self.populate_entries()
        self.display_entry_data()
