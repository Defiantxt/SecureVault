"""Responsive Add Entry dialog for SecureVault.

The dialog deliberately owns presentation and input state only.  Persistence is
provided by ``on_submit`` so callers can keep database/encryption work in their
controller layer.
"""

from __future__ import annotations

import math
import re
import sys
import tkinter as tk
from typing import Protocol

import customtkinter as ctk

from dialog_geometry import (
    Rect,
    monitor_work_area,
    widget_scale,
    window_rect,
    window_scale,
)


class SubmitCallback(Protocol):
    def __call__(
        self,
        name: str,
        content: str,
        entry_type: str,
        *,
        service: str = "",
        pin: str = "",
        expiry: str = "",
    ) -> str | None: ...


class AddEntryDialog:
    """A reusable, modal editor for creating Login, Card, and Note entries.

    ``on_submit`` is called as ``on_submit(name, content, entry_type,
    service=..., pin=..., expiry=...)``.  It should return ``None`` when the
    entry was stored successfully; returning a string leaves the dialog open
    and displays that string as an error.
    """

    ENTRY_TYPES = ("Login", "Card", "Note")

    BACKGROUND = "#050B19"
    PANEL = "#0C1424"
    INPUT = "#101A2C"
    INPUT_HOVER = "#162238"
    BORDER = "#273550"
    BORDER_ACTIVE = "#7568F8"
    PRIMARY = "#4236B8"
    PRIMARY_HOVER = "#5044CD"
    SECONDARY = "#202B42"
    SECONDARY_HOVER = "#2C3956"
    TEXT = "#F4F6FB"
    MUTED = "#9AA6BE"
    ERROR = "#FF747D"

    _EDGE_MARGIN = 16
    _MIN_WIDTH = 390
    _MIN_HEIGHT = 410
    _MAX_PREFERRED_WIDTH = 620

    def __init__(self, parent, on_submit: SubmitCallback) -> None:
        if not callable(on_submit):
            raise TypeError("on_submit must be callable")

        self.parent = parent
        self.on_submit = on_submit

        self.dialog: ctk.CTkToplevel | None = None
        self._shell: ctk.CTkFrame | None = None
        self._body: ctk.CTkScrollableFrame | None = None
        self._form: ctk.CTkFrame | None = None
        self._type_var: ctk.StringVar | None = None
        self._name_label: ctk.CTkLabel | None = None
        self._name_entry: ctk.CTkEntry | None = None
        self._subtitle_label: ctk.CTkLabel | None = None
        self._content_label: ctk.CTkLabel | None = None
        self._content_frame: ctk.CTkFrame | None = None
        self._service_entry: ctk.CTkEntry | None = None
        self._secret_entry: ctk.CTkEntry | None = None
        self._pin_entry: ctk.CTkEntry | None = None
        self._expiry_entry: ctk.CTkEntry | None = None
        self._note_textbox: ctk.CTkTextbox | None = None
        self._show_secret_button: ctk.CTkButton | None = None
        self._error_label: ctk.CTkLabel | None = None
        self._submit_button: ctk.CTkButton | None = None

        self._drafts = self._empty_drafts()
        self._active_type = "Login"
        self._secret_is_visible = False
        self._submitting = False
        self._preferred_width = 520
        self._last_height = self._MIN_HEIGHT

    def open(self) -> ctk.CTkToplevel:
        """Open the dialog, or focus the existing instance if already open."""

        if self._dialog_exists():
            self._present()
            return self.dialog  # type: ignore[return-value]

        self._reset_state()
        self._build_dialog()
        self._fit_to_content()
        self._present()
        return self.dialog  # type: ignore[return-value]

    def close(self) -> None:
        """Close the dialog safely and return focus to its owner."""

        dialog = self.dialog
        self.dialog = None
        if dialog is None:
            self._reset_state()
            self._clear_widget_references()
            return

        try:
            if dialog.grab_current() == dialog:
                dialog.grab_release()
        except tk.TclError:
            pass

        try:
            dialog.destroy()
        except tk.TclError:
            pass

        self._clear_widget_references()
        # Type-switch drafts deliberately retain plaintext while the dialog is
        # open.  Drop every retained value as soon as the modal is closed.
        self._reset_state()
        try:
            if self.parent.winfo_exists():
                self.parent.lift()
                self.parent.focus_set()
        except tk.TclError:
            pass

    def _dialog_exists(self) -> bool:
        if self.dialog is None:
            return False
        try:
            return bool(self.dialog.winfo_exists())
        except tk.TclError:
            self.dialog = None
            return False

    def _reset_state(self) -> None:
        self._drafts = self._empty_drafts()
        self._active_type = "Login"
        self._secret_is_visible = False
        self._submitting = False

    @staticmethod
    def _empty_drafts() -> dict[str, str]:
        """Return isolated plaintext drafts for each entry type."""

        return {
            "login_service": "",
            "login_password": "",
            "card_number": "",
            "card_pin": "",
            "card_expiry": "",
            "note": "",
        }

    def _clear_widget_references(self) -> None:
        self._shell = None
        self._body = None
        self._form = None
        self._type_var = None
        self._name_label = None
        self._name_entry = None
        self._subtitle_label = None
        self._content_label = None
        self._content_frame = None
        self._service_entry = None
        self._secret_entry = None
        self._pin_entry = None
        self._expiry_entry = None
        self._note_textbox = None
        self._show_secret_button = None
        self._error_label = None
        self._submit_button = None

    def _build_dialog(self) -> None:
        dialog = ctk.CTkToplevel(master=self.parent, fg_color=self.BACKGROUND)
        dialog.withdraw()
        dialog.title("Add vault entry")
        dialog.transient(self.parent)
        dialog.resizable(True, True)
        dialog.grid_columnconfigure(0, weight=1)
        dialog.grid_rowconfigure(0, weight=1)
        dialog.protocol("WM_DELETE_WINDOW", self.close)
        dialog.bind("<Escape>", lambda _event: self.close())
        dialog.bind("<Control-Return>", self._submit_shortcut)
        dialog.bind("<Control-KP_Enter>", self._submit_shortcut)
        dialog.bind("<Configure>", self._on_dialog_configure)
        self.dialog = dialog

        # Establish a sensible width before wrapped labels and requested sizes
        # are measured.  The final dimensions are computed after construction.
        dialog.geometry(f"{self._preferred_width}x{self._MIN_HEIGHT}")

        shell = ctk.CTkFrame(
            master=dialog,
            fg_color=self.PANEL,
            border_width=1,
            border_color=self.BORDER,
            corner_radius=14,
        )
        shell.grid(row=0, column=0, sticky="nsew", padx=14, pady=14)
        shell.grid_columnconfigure(0, weight=1)
        shell.grid_rowconfigure(2, weight=1)
        self._shell = shell

        self._build_header(shell)

        ctk.CTkFrame(
            master=shell,
            height=1,
            fg_color=self.BORDER,
            corner_radius=0,
        ).grid(row=1, column=0, sticky="ew")

        body = ctk.CTkScrollableFrame(
            master=shell,
            width=440,
            height=250,
            fg_color="transparent",
            corner_radius=0,
            scrollbar_button_color="#34425F",
            scrollbar_button_hover_color="#48597A",
        )
        body.grid(
            row=2,
            column=0,
            sticky="nsew",
            padx=(20, 12),
            pady=(16, 10),
        )
        body.grid_columnconfigure(0, weight=1)
        self._body = body

        form = ctk.CTkFrame(master=body, fg_color="transparent")
        form.grid(row=0, column=0, sticky="new", padx=(2, 8))
        form.grid_columnconfigure(0, weight=1)
        self._form = form
        self._build_form(form)

        ctk.CTkFrame(
            master=shell,
            height=1,
            fg_color=self.BORDER,
            corner_radius=0,
        ).grid(row=3, column=0, sticky="ew")

        self._build_footer(shell)

    def _build_header(self, shell: ctk.CTkFrame) -> None:
        header = ctk.CTkFrame(master=shell, fg_color="transparent")
        header.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=24,
            pady=(22, 18),
        )
        header.grid_columnconfigure(1, weight=1)

        icon = ctk.CTkFrame(
            master=header,
            width=48,
            height=48,
            fg_color="#302966",
            border_width=1,
            border_color="#5D52C6",
            corner_radius=12,
        )
        icon.grid(row=0, column=0, rowspan=2, sticky="w")
        icon.grid_propagate(False)
        ctk.CTkLabel(
            master=icon,
            text="+",
            font=("Arial", 25),
            text_color="#C7C1FF",
        ).place(relx=0.5, rely=0.47, anchor="center")

        ctk.CTkLabel(
            master=header,
            text="Add a vault entry",
            font=("Arial", 20, "bold"),
            text_color=self.TEXT,
            anchor="w",
        ).grid(row=0, column=1, sticky="ew", padx=(14, 0))

        subtitle_label = ctk.CTkLabel(
            master=header,
            text="Choose a type and keep the details encrypted.",
            font=("Arial", 12),
            text_color=self.MUTED,
            anchor="w",
            justify="left",
            wraplength=350,
        )
        subtitle_label.grid(
            row=1,
            column=1,
            sticky="ew",
            padx=(14, 0),
            pady=(2, 0),
        )
        self._subtitle_label = subtitle_label

    def _build_form(self, form: ctk.CTkFrame) -> None:
        ctk.CTkLabel(
            master=form,
            text="ENTRY TYPE",
            font=("Arial", 11, "bold"),
            text_color=self.MUTED,
            anchor="w",
        ).grid(row=0, column=0, sticky="ew")

        type_card = ctk.CTkFrame(
            master=form,
            fg_color=self.INPUT,
            border_width=1,
            border_color=self.BORDER,
            corner_radius=10,
        )
        type_card.grid(row=1, column=0, sticky="ew", pady=(8, 18))
        type_card.grid_columnconfigure((0, 1, 2), weight=1, uniform="entry_type")

        self._type_var = ctk.StringVar(master=self.dialog, value="Login")
        for column, entry_type in enumerate(self.ENTRY_TYPES):
            ctk.CTkRadioButton(
                master=type_card,
                text=entry_type,
                value=entry_type,
                variable=self._type_var,
                command=self._on_type_changed,
                width=90,
                radiobutton_width=20,
                radiobutton_height=20,
                border_width_unchecked=2,
                border_width_checked=5,
                fg_color=self.BORDER_ACTIVE,
                hover_color="#8B80FF",
                border_color="#687590",
                text_color="#EEF1F8",
                font=("Arial", 12, "bold"),
            ).grid(row=0, column=column, padx=10, pady=14)

        name_label = ctk.CTkLabel(
            master=form,
            text="ENTRY NAME",
            font=("Arial", 11, "bold"),
            text_color=self.MUTED,
            anchor="w",
        )
        name_label.grid(row=2, column=0, sticky="ew")
        self._name_label = name_label

        name_entry = ctk.CTkEntry(
            master=form,
            height=44,
            fg_color=self.INPUT,
            border_color=self.BORDER,
            text_color=self.TEXT,
            placeholder_text="e.g. Work account",
            font=("Arial", 13),
        )
        name_entry.grid(row=3, column=0, sticky="ew", pady=(8, 18))
        name_entry.bind("<Return>", self._submit_shortcut)
        self._name_entry = name_entry

        content_label = ctk.CTkLabel(
            master=form,
            text="PASSWORD",
            font=("Arial", 11, "bold"),
            text_color=self.MUTED,
            anchor="w",
        )
        content_label.grid(row=4, column=0, sticky="ew")
        self._content_label = content_label

        content_frame = ctk.CTkFrame(master=form, fg_color="transparent")
        content_frame.grid(row=5, column=0, sticky="ew", pady=(8, 6))
        content_frame.grid_columnconfigure(0, weight=1)
        self._content_frame = content_frame

        ctk.CTkLabel(
            master=form,
            text="Tip: press Ctrl+Enter to add this entry.",
            font=("Arial", 11),
            text_color="#76839D",
            anchor="w",
        ).grid(row=6, column=0, sticky="ew", pady=(7, 2))

        self._render_content_editor(resize=False)

    def _build_footer(self, shell: ctk.CTkFrame) -> None:
        footer = ctk.CTkFrame(master=shell, fg_color="transparent")
        footer.grid(
            row=4,
            column=0,
            sticky="ew",
            padx=24,
            pady=(8, 20),
        )
        footer.grid_columnconfigure((0, 1), weight=1, uniform="action")

        error_label = ctk.CTkLabel(
            master=footer,
            text="",
            height=30,
            font=("Arial", 11),
            text_color=self.ERROR,
            anchor="w",
            justify="left",
        )
        error_label.grid(
            row=0,
            column=0,
            columnspan=2,
            sticky="ew",
            pady=(0, 7),
        )
        self._error_label = error_label

        ctk.CTkButton(
            master=footer,
            text="Cancel",
            command=self.close,
            height=44,
            fg_color=self.SECONDARY,
            hover_color=self.SECONDARY_HOVER,
            border_width=1,
            border_color="#34425F",
            corner_radius=9,
            font=("Arial", 12, "bold"),
        ).grid(row=1, column=0, sticky="ew", padx=(0, 7))

        submit_button = ctk.CTkButton(
            master=footer,
            text="Add entry",
            command=self._submit,
            height=44,
            fg_color=self.PRIMARY,
            hover_color=self.PRIMARY_HOVER,
            corner_radius=9,
            font=("Arial", 12, "bold"),
        )
        submit_button.grid(row=1, column=1, sticky="ew", padx=(7, 0))
        self._submit_button = submit_button

    def _capture_content_draft(self) -> None:
        try:
            if self._active_type == "Login":
                if self._service_entry is not None:
                    self._drafts["login_service"] = (
                        self._service_entry.get()
                    )
                if self._secret_entry is not None:
                    self._drafts["login_password"] = (
                        self._secret_entry.get()
                    )
            elif self._active_type == "Card":
                if self._secret_entry is not None:
                    self._drafts["card_number"] = self._secret_entry.get()
                if self._pin_entry is not None:
                    self._drafts["card_pin"] = self._pin_entry.get()
                if self._expiry_entry is not None:
                    self._drafts["card_expiry"] = self._expiry_entry.get()
            elif self._note_textbox is not None:
                self._drafts["note"] = self._note_textbox.get("1.0", "end-1c")
        except tk.TclError:
            pass

    def _on_type_changed(self) -> None:
        if self._type_var is None:
            return
        self._capture_content_draft()
        self._active_type = self._type_var.get()
        self._secret_is_visible = False
        self._set_error("")
        self._render_content_editor(resize=True)

    def _configure_type_copy(self) -> None:
        """Keep field labels and examples relevant to the selected type."""

        if self._name_label is None or self._name_entry is None:
            return

        copy = {
            "Login": (
                "ENTRY NAME",
                "e.g. Work account",
                "Save account credentials and an optional service.",
            ),
            "Card": (
                "CARD NAME",
                "e.g. Travel card",
                "Keep your card number, PIN, and expiry date encrypted.",
            ),
            "Note": (
                "TITLE",
                "e.g. Recovery instructions",
                "Keep private notes encrypted and easy to identify.",
            ),
        }
        label, placeholder, subtitle = copy.get(
            self._active_type,
            copy["Login"],
        )
        self._name_label.configure(text=label)
        self._name_entry.configure(placeholder_text=placeholder)
        if self._subtitle_label is not None:
            self._subtitle_label.configure(text=subtitle)

    def _render_content_editor(self, *, resize: bool) -> None:
        if self._content_frame is None or self._content_label is None:
            return

        self._configure_type_copy()

        for child in self._content_frame.winfo_children():
            child.destroy()

        self._service_entry = None
        self._secret_entry = None
        self._pin_entry = None
        self._expiry_entry = None
        self._note_textbox = None
        self._show_secret_button = None
        is_note = self._active_type == "Note"

        if is_note:
            self._content_label.configure(text="NOTE CONTENT")
            note_textbox = ctk.CTkTextbox(
                master=self._content_frame,
                height=160,
                fg_color=self.INPUT,
                border_width=1,
                border_color=self.BORDER,
                corner_radius=9,
                text_color=self.TEXT,
                font=("Arial", 13),
                wrap="word",
                scrollbar_button_color="#34425F",
                scrollbar_button_hover_color="#48597A",
            )
            note_textbox.grid(row=0, column=0, sticky="ew")
            note_textbox.insert("1.0", self._drafts["note"])
            note_textbox.bind("<Control-Return>", self._submit_shortcut)
            note_textbox.bind("<Control-KP_Enter>", self._submit_shortcut)
            self._note_textbox = note_textbox
        elif self._active_type == "Login":
            self._content_label.configure(text="SERVICE (OPTIONAL)")
            self._content_frame.grid_columnconfigure(0, weight=1)

            service_entry = ctk.CTkEntry(
                master=self._content_frame,
                height=44,
                fg_color=self.INPUT,
                border_color=self.BORDER,
                text_color=self.TEXT,
                placeholder_text="e.g. Gmail",
                font=("Arial", 13),
            )
            service_entry.insert(0, self._drafts["login_service"])
            service_entry.grid(
                row=0,
                column=0,
                columnspan=2,
                sticky="ew",
            )
            service_entry.bind("<Return>", self._submit_shortcut)
            self._service_entry = service_entry

            ctk.CTkLabel(
                master=self._content_frame,
                text="PASSWORD",
                font=("Arial", 11, "bold"),
                text_color=self.MUTED,
                anchor="w",
            ).grid(
                row=1,
                column=0,
                columnspan=2,
                sticky="ew",
                pady=(16, 8),
            )

            secret_entry = ctk.CTkEntry(
                master=self._content_frame,
                height=44,
                fg_color=self.INPUT,
                border_color=self.BORDER,
                text_color=self.TEXT,
                placeholder_text="Enter a secure password",
                font=("Arial", 13),
                show="" if self._secret_is_visible else "\u2022",
            )
            secret_entry.insert(0, self._drafts["login_password"])
            secret_entry.grid(
                row=2,
                column=0,
                sticky="ew",
                padx=(0, 8),
            )
            secret_entry.bind("<Return>", self._submit_shortcut)
            self._secret_entry = secret_entry

            show_button = ctk.CTkButton(
                master=self._content_frame,
                text="Hide" if self._secret_is_visible else "Show",
                command=self._toggle_secret_visibility,
                width=70,
                height=44,
                fg_color=self.SECONDARY,
                hover_color=self.SECONDARY_HOVER,
                border_width=1,
                border_color="#34425F",
                corner_radius=8,
                font=("Arial", 11, "bold"),
            )
            show_button.grid(row=2, column=1)
            self._show_secret_button = show_button
        else:
            self._content_label.configure(text="CARD NUMBER")
            self._content_frame.grid_columnconfigure(0, weight=1)

            secret_entry = ctk.CTkEntry(
                master=self._content_frame,
                height=44,
                fg_color=self.INPUT,
                border_color=self.BORDER,
                text_color=self.TEXT,
                placeholder_text="Enter the card number",
                font=("Arial", 13),
                show="" if self._secret_is_visible else "\u2022",
            )
            secret_entry.insert(0, self._drafts["card_number"])
            secret_entry.grid(
                row=0,
                column=0,
                sticky="ew",
                padx=(0, 8),
            )
            secret_entry.bind("<Return>", self._submit_shortcut)
            self._secret_entry = secret_entry

            show_button = ctk.CTkButton(
                master=self._content_frame,
                text="Hide" if self._secret_is_visible else "Show",
                command=self._toggle_secret_visibility,
                width=70,
                height=44,
                fg_color=self.SECONDARY,
                hover_color=self.SECONDARY_HOVER,
                border_width=1,
                border_color="#34425F",
                corner_radius=8,
                font=("Arial", 11, "bold"),
            )
            show_button.grid(row=0, column=1)
            self._show_secret_button = show_button

            card_meta = ctk.CTkFrame(
                master=self._content_frame,
                fg_color="transparent",
            )
            card_meta.grid(
                row=1,
                column=0,
                columnspan=2,
                sticky="ew",
                pady=(16, 0),
            )
            card_meta.grid_columnconfigure(
                (0, 1),
                weight=1,
                uniform="card_meta",
            )

            pin_field = ctk.CTkFrame(master=card_meta, fg_color="transparent")
            pin_field.grid(row=0, column=1, sticky="ew", padx=(7, 0))
            pin_field.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(
                master=pin_field,
                text="PIN",
                font=("Arial", 11, "bold"),
                text_color=self.MUTED,
                anchor="w",
            ).grid(row=0, column=0, sticky="ew", pady=(0, 8))
            pin_entry = ctk.CTkEntry(
                master=pin_field,
                height=44,
                fg_color=self.INPUT,
                border_color=self.BORDER,
                text_color=self.TEXT,
                placeholder_text="Enter PIN",
                font=("Arial", 13),
                show="\u2022",
            )
            pin_entry.insert(0, self._drafts["card_pin"])
            pin_entry.grid(row=1, column=0, sticky="ew")
            pin_entry.bind("<Return>", self._submit_shortcut)
            self._pin_entry = pin_entry

            expiry_field = ctk.CTkFrame(
                master=card_meta,
                fg_color="transparent",
            )
            expiry_field.grid(row=0, column=0, sticky="ew", padx=(0, 7))
            expiry_field.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(
                master=expiry_field,
                text="EXPIRY DATE",
                font=("Arial", 11, "bold"),
                text_color=self.MUTED,
                anchor="w",
            ).grid(row=0, column=0, sticky="ew", pady=(0, 8))
            expiry_entry = ctk.CTkEntry(
                master=expiry_field,
                height=44,
                fg_color=self.INPUT,
                border_color=self.BORDER,
                text_color=self.TEXT,
                placeholder_text="MM/YY",
                font=("Arial", 13),
            )
            expiry_entry.insert(0, self._drafts["card_expiry"])
            expiry_entry.grid(row=1, column=0, sticky="ew")
            expiry_entry.bind("<Return>", self._submit_shortcut)
            self._expiry_entry = expiry_entry

        if resize and self._dialog_exists():
            self._fit_to_content()
            if is_note:
                target = self._note_textbox
            elif self._active_type == "Login":
                target = self._service_entry
            else:
                target = self._secret_entry
            if target is not None:
                target.after_idle(target.focus_set)

    def _toggle_secret_visibility(self) -> None:
        if self._secret_entry is None:
            return
        self._secret_is_visible = not self._secret_is_visible
        show = "" if self._secret_is_visible else "\u2022"
        self._secret_entry.configure(show=show)
        if self._pin_entry is not None:
            self._pin_entry.configure(show=show)
        if self._show_secret_button is not None:
            self._show_secret_button.configure(
                text="Hide" if self._secret_is_visible else "Show"
            )

    def _submit_shortcut(self, _event=None):
        self._submit()
        return "break"

    def _submit(self) -> None:
        if self._submitting or self._name_entry is None:
            return

        self._capture_content_draft()
        entry_type = self._active_type
        name = self._name_entry.get().strip()
        service = ""
        pin = ""
        expiry = ""
        if entry_type == "Login":
            content = self._drafts["login_password"]
            service = self._drafts["login_service"].strip()
        elif entry_type == "Card":
            content = self._drafts["card_number"]
            pin = self._drafts["card_pin"].strip()
            expiry = self._drafts["card_expiry"].strip()
        else:
            content = self._drafts["note"]

        if not name:
            message = (
                "Enter a title for this note."
                if entry_type == "Note"
                else (
                    "Enter a name for this card."
                    if entry_type == "Card"
                    else "Enter a name for this vault entry."
                )
            )
            self._set_error(message)
            self._name_entry.focus_set()
            return
        if not content.strip():
            noun = {
                "Login": "password",
                "Card": "card number",
                "Note": "note content",
            }.get(entry_type, "content")
            self._set_error(f"Enter {noun} before adding the entry.")
            target = self._note_textbox if entry_type == "Note" else self._secret_entry
            if target is not None:
                target.focus_set()
            return
        if entry_type == "Card" and not pin:
            self._set_error("Enter the card PIN before adding the entry.")
            if self._pin_entry is not None:
                self._pin_entry.focus_set()
            return
        if entry_type == "Card" and not expiry:
            self._set_error(
                "Enter the card expiry date before adding the entry."
            )
            if self._expiry_entry is not None:
                self._expiry_entry.focus_set()
            return
        if entry_type == "Card" and not re.fullmatch(
            r"(?:0[1-9]|1[0-2])/\d{2}", expiry
        ):
            self._set_error("Enter the expiry date as MM/YY.")
            if self._expiry_entry is not None:
                self._expiry_entry.focus_set()
            return

        self._set_error("")
        self._submitting = True
        if self._submit_button is not None:
            self._submit_button.configure(state="disabled", text="Adding...")

        try:
            error = self.on_submit(
                name,
                content,
                entry_type,
                service=service,
                pin=pin,
                expiry=expiry,
            )
        except Exception as exc:  # Keep callback failures inside the modal.
            error = str(exc).strip() or "The entry could not be saved."

        if error is None:
            self.close()
            return

        self._submitting = False
        if self._submit_button is not None:
            try:
                self._submit_button.configure(state="normal", text="Add entry")
            except tk.TclError:
                pass
        message = str(error).strip() or "The entry could not be saved."
        self._set_error(message)

    def _set_error(self, message: str) -> None:
        if self._error_label is None:
            return
        try:
            self._error_label.configure(text=message)
        except tk.TclError:
            return

    def _present(self) -> None:
        dialog = self.dialog
        if dialog is None:
            return

        def settle_focus() -> None:
            if not self._dialog_exists():
                return
            try:
                dialog.attributes("-topmost", False)
                dialog.lift()
                focused = dialog.focus_displayof()
                if focused is None or focused.winfo_toplevel() != dialog:
                    if self._name_entry is not None:
                        self._name_entry.focus_force()
                    else:
                        dialog.focus_force()
            except tk.TclError:
                pass

        def show() -> None:
            if not self._dialog_exists():
                return
            try:
                dialog.attributes("-topmost", True)
                dialog.deiconify()
                dialog.lift()
                dialog.grab_set()
                if self._name_entry is not None:
                    self._name_entry.focus_force()
                else:
                    dialog.focus_force()
                dialog.after(140, settle_focus)
            except tk.TclError:
                pass

        def finish_layout_and_show() -> None:
            if not self._dialog_exists():
                return
            # CTkScrollableFrame applies part of its requested-size update on
            # an idle callback.  Measure once more after that callback so a
            # roomy monitor gets the natural dialog height without a flash or
            # a needless scrollbar.
            self._fit_to_content()
            show()

        try:
            if dialog.winfo_viewable():
                show()
            else:
                dialog.after(30, finish_layout_and_show)
        except tk.TclError:
            pass

    def _fit_to_content(self) -> None:
        """Measure natural content, then clamp it to the monitor work area.

        Only the scrollable body occupies the weighted row, so shrinking the
        window never pushes the error message or action buttons off-screen.
        """

        dialog = self.dialog
        body = self._body
        form = self._form
        if dialog is None or body is None or form is None:
            return

        try:
            dialog.update_idletasks()
            current_widget_scale = widget_scale(form)
            form_height = math.ceil(
                form.winfo_reqheight() / current_widget_scale
            )
            body.configure(height=max(190, form_height + 6))
            dialog.update_idletasks()

            current_window_scale = window_scale(dialog)
            # Use the owner's monitor.  A withdrawn new toplevel can still be
            # parked on the primary monitor even when the app is elsewhere.
            work_area = monitor_work_area(self.parent)
            # ``winfo_width`` temporarily reports 1/100 while a CTkToplevel
            # is withdrawn, whereas GetWindowRect already reports the pending
            # full-size native window.  Subtracting those two measurements
            # would mistake the client area for title-bar decoration and cap
            # the dialog far too aggressively.  Reserve a conservative native
            # frame allowance instead; the final position is still corrected
            # from the real decorated rectangle below.
            decoration_width = round(
                (16 if sys.platform.startswith("win") else 4)
                * current_window_scale
            )
            decoration_height = round(
                (44 if sys.platform.startswith("win") else 32)
                * current_window_scale
            )
            edge_physical = round(
                self._EDGE_MARGIN * current_window_scale
            )

            max_width = max(
                320,
                math.floor(
                    (
                        work_area.width
                        - (2 * edge_physical)
                        - decoration_width
                    )
                    / current_window_scale
                ),
            )
            max_height = max(
                330,
                math.floor(
                    (
                        work_area.height
                        - (2 * edge_physical)
                        - decoration_height
                    )
                    / current_window_scale
                ),
            )

            parent_rect = window_rect(self.parent)
            parent_width = parent_rect.width / max(
                window_scale(self.parent), 0.01
            )
            preferred_width = round(parent_width * 0.52)
            preferred_width = max(480, min(preferred_width, self._MAX_PREFERRED_WIDTH))

            requested_width = math.ceil(
                dialog.winfo_reqwidth() / current_window_scale
            )
            requested_height = math.ceil(
                dialog.winfo_reqheight() / current_window_scale
            )
            target_width = min(
                max_width,
                max(self._MIN_WIDTH, preferred_width, requested_width),
            )
            target_height = min(
                max_height,
                max(self._MIN_HEIGHT, requested_height),
            )

            minimum_width = min(self._MIN_WIDTH, max_width)
            minimum_height = min(self._MIN_HEIGHT, max_height)
            dialog.minsize(minimum_width, minimum_height)
            dialog.maxsize(max_width, max_height)
            self._preferred_width = target_width
            self._last_height = target_height
            self._set_centered_geometry(target_width, target_height, work_area)
        except tk.TclError:
            pass

    def _set_centered_geometry(
        self,
        width: int,
        height: int,
        work_area: Rect,
    ) -> None:
        dialog = self.dialog
        if dialog is None:
            return

        # Measure the decorated window at the final client size while hidden.
        dialog.geometry(f"{width}x{height}+{work_area.left}+{work_area.top}")
        dialog.update_idletasks()
        dialog_rect = window_rect(dialog)
        parent_rect = window_rect(self.parent)

        current_window_scale = window_scale(dialog)
        outer_width = dialog_rect.width or round(
            width * current_window_scale
        )
        outer_height = dialog_rect.height or round(
            height * current_window_scale
        )
        edge = round(self._EDGE_MARGIN * current_window_scale)

        x = parent_rect.left + (parent_rect.width - outer_width) // 2
        y = parent_rect.top + (parent_rect.height - outer_height) // 2
        x = max(
            work_area.left + edge,
            min(x, work_area.right - edge - outer_width),
        )
        y = max(
            work_area.top + edge,
            min(y, work_area.bottom - edge - outer_height),
        )
        dialog.geometry(f"{width}x{height}+{x}+{y}")

    def _on_dialog_configure(self, event) -> None:
        if self.dialog is None or event.widget is not self.dialog:
            return
        if self._error_label is None:
            return
        try:
            logical_width = event.width / window_scale(self.dialog)
            self._error_label.configure(wraplength=max(220, logical_width - 90))
            if self._subtitle_label is not None:
                self._subtitle_label.configure(
                    wraplength=max(150, logical_width - 155)
                )
        except tk.TclError:
            pass


__all__ = ["AddEntryDialog", "SubmitCallback"]
