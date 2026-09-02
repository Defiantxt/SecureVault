import unittest

from app_controller import VaultAppController
from entry_navigation import EntryView


class _Sidebar:
    def set_action_handler(self, handler):
        self.handler = handler


class _EntriesView:
    def set_search_handler(self, handler):
        self.handler = handler


class _EntryController:
    def __init__(self):
        self.views = []
        self.searches = []
        self.add_opened = 0

    def show_view(self, view):
        self.views.append(view)

    def set_search_query(self, query):
        self.searches.append(query)

    def add_entry_popup(self):
        self.add_opened += 1


class _SettingsWindow:
    def __init__(self):
        self.opened = 0

    def open(self):
        self.opened += 1


class VaultAppControllerTests(unittest.TestCase):
    def setUp(self):
        self.sidebar = _Sidebar()
        self.entries = _EntriesView()
        self.entry_controller = _EntryController()
        self.settings = _SettingsWindow()
        self.locked = 0
        self.controller = VaultAppController(
            self.sidebar,
            self.entries,
            self.entry_controller,
            self.settings,
            self._lock,
        )
        self.controller.connect()

    def _lock(self):
        self.locked += 1

    def test_connects_sidebar_and_live_search(self):
        self.entries.handler("github")
        self.assertEqual(self.entry_controller.searches, ["github"])

    def test_routes_every_navigation_destination(self):
        expected = {
            "all_ents": EntryView.ALL_ENTRIES,
            "favorites": EntryView.FAVORITES,
            "logins": EntryView.LOGINS,
            "cards": EntryView.CARDS,
            "notes": EntryView.NOTES,
            "trash": EntryView.TRASH,
        }
        for action, view in expected.items():
            with self.subTest(action=action):
                self.sidebar.handler(action)
                self.assertEqual(self.entry_controller.views[-1], view)

    def test_routes_add_settings_and_lock_actions(self):
        self.sidebar.handler("add_new_ent")
        self.sidebar.handler("settings")
        self.sidebar.handler("lock_vault")

        self.assertEqual(self.entry_controller.add_opened, 1)
        self.assertEqual(self.settings.opened, 1)
        self.assertEqual(self.locked, 1)

    def test_unknown_action_is_ignored(self):
        self.sidebar.handler("not-an-action")
        self.assertEqual(self.entry_controller.views, [])


if __name__ == "__main__":
    unittest.main()
