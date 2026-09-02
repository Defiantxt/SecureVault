"""Application-level wiring for sidebar actions and entry search."""

from collections.abc import Callable

from entry_navigation import EntryView


class VaultAppController:
    """Route UI events without putting application behavior in widgets."""

    ACTION_VIEWS = {
        "all_ents": EntryView.ALL_ENTRIES,
        "favorites": EntryView.FAVORITES,
        "logins": EntryView.LOGINS,
        "cards": EntryView.CARDS,
        "notes": EntryView.NOTES,
        "trash": EntryView.TRASH,
    }

    def __init__(
        self,
        sidebar,
        entries_view,
        entry_controller,
        settings_window,
        on_lock: Callable[[], None],
    ) -> None:
        self.sidebar = sidebar
        self.entries_view = entries_view
        self.entry_controller = entry_controller
        self.settings_window = settings_window
        self.on_lock = on_lock

    def connect(self) -> None:
        self.sidebar.set_action_handler(self.handle_sidebar_action)
        self.entries_view.set_search_handler(
            self.entry_controller.set_search_query
        )

    def handle_sidebar_action(self, action: str) -> None:
        if action == "add_new_ent":
            self.entry_controller.add_entry_popup()
        elif action == "settings":
            self.settings_window.open()
        elif action == "lock_vault":
            self.on_lock()
        elif action in self.ACTION_VIEWS:
            self.entry_controller.show_view(self.ACTION_VIEWS[action])
