import unittest

from entry_navigation import (
    NAVIGATION_VIEWS,
    NO_SEARCH_RESULTS_LABEL,
    EntryView,
    filter_entry_records,
    get_empty_state_label,
    get_view_presentation,
)


class EntryNavigationTests(unittest.TestCase):
    def setUp(self):
        self.records = {
            11: {
                "id": 11,
                "name": "Personal Email",
                "password": "secret-one",
                "type": "Login",
                "favorite": True,
                "deleted_at": None,
            },
            4: {
                "id": 4,
                "name": "Travel Card",
                "password": "4111 1111 1111 1111",
                "type": "Card",
                "favorite": False,
                "deleted_at": None,
            },
            27: {
                "id": 27,
                "name": "Personal Email",
                "password": "duplicate-name-secret",
                "type": "Note",
                "favorite": False,
                "deleted_at": None,
            },
            8: {
                "id": 8,
                "name": "Old Login",
                "password": "trashed-secret",
                "type": "Login",
                "favorite": True,
                "deleted_at": 1_700_000_000,
            },
            15: {
                "id": 15,
                "name": "Epoch Trash",
                "password": "zero-is-still-deleted",
                "type": "Note",
                "favorite": False,
                "deleted_at": 0,
            },
        }

    def test_view_identifiers_and_presentation_copy_are_complete(self):
        self.assertEqual(
            [view.value for view in NAVIGATION_VIEWS],
            [
                "all_entries",
                "favorites",
                "logins",
                "cards",
                "notes",
                "trash",
            ],
        )
        self.assertEqual(
            get_view_presentation("all_entries").title,
            "All Entries",
        )
        self.assertEqual(
            get_view_presentation(EntryView.TRASH).empty_state_label,
            "Trash is empty",
        )

    def test_unknown_view_is_rejected(self):
        with self.assertRaises(ValueError):
            filter_entry_records(self.records, "unknown")

    def test_all_entries_excludes_trash_and_preserves_input_order(self):
        result = filter_entry_records(self.records, EntryView.ALL_ENTRIES)

        self.assertEqual(list(result), [11, 4, 27])

    def test_missing_deleted_at_is_treated_as_active_for_legacy_records(self):
        legacy = {
            31: {
                "id": 31,
                "name": "Legacy",
                "password": "secret",
                "type": "Login",
                "favorite": False,
            }
        }

        self.assertEqual(
            list(filter_entry_records(legacy, EntryView.ALL_ENTRIES)),
            [31],
        )
        self.assertEqual(
            filter_entry_records(legacy, EntryView.TRASH),
            {},
        )

    def test_favorites_contains_only_active_favorites(self):
        result = filter_entry_records(self.records, EntryView.FAVORITES)

        self.assertEqual(list(result), [11])

    def test_type_views_match_decrypted_type_case_insensitively(self):
        records = dict(self.records)
        records[99] = {
            "id": 99,
            "name": "Work Account",
            "password": "secret",
            "type": " login ",
            "favorite": False,
            "deleted_at": None,
        }

        self.assertEqual(
            list(filter_entry_records(records, EntryView.LOGINS)),
            [11, 99],
        )
        self.assertEqual(
            list(filter_entry_records(records, EntryView.CARDS)),
            [4],
        )
        self.assertEqual(
            list(filter_entry_records(records, EntryView.NOTES)),
            [27],
        )

    def test_trash_includes_every_non_null_timestamp_including_zero(self):
        result = filter_entry_records(self.records, EntryView.TRASH)

        self.assertEqual(list(result), [8, 15])

    def test_search_is_trimmed_case_insensitive_and_matches_name_or_type(self):
        by_name = filter_entry_records(
            self.records,
            EntryView.ALL_ENTRIES,
            "  EMAIL  ",
        )
        by_type = filter_entry_records(
            self.records,
            EntryView.ALL_ENTRIES,
            "CaRd",
        )

        self.assertEqual(list(by_name), [11, 27])
        self.assertEqual(list(by_type), [4])

    def test_search_never_matches_password_or_note_content(self):
        self.assertEqual(
            filter_entry_records(
                self.records,
                EntryView.ALL_ENTRIES,
                "duplicate-name-secret",
            ),
            {},
        )

    def test_view_filter_runs_before_search_and_keeps_trash_isolated(self):
        self.assertEqual(
            filter_entry_records(
                self.records,
                EntryView.ALL_ENTRIES,
                "Old Login",
            ),
            {},
        )
        self.assertEqual(
            list(
                filter_entry_records(
                    self.records,
                    EntryView.TRASH,
                    "login",
                )
            ),
            [8],
        )

    def test_duplicate_names_keep_their_stable_ids_and_order(self):
        result = filter_entry_records(
            self.records,
            EntryView.ALL_ENTRIES,
            "personal email",
        )

        self.assertEqual(list(result), [11, 27])
        self.assertIs(result[11], self.records[11])
        self.assertIs(result[27], self.records[27])

    def test_filtering_does_not_mutate_input_mapping_or_records(self):
        original_order = list(self.records)
        original_deleted_at = self.records[8]["deleted_at"]

        filter_entry_records(self.records, EntryView.FAVORITES, "email")

        self.assertEqual(list(self.records), original_order)
        self.assertEqual(self.records[8]["deleted_at"], original_deleted_at)

    def test_empty_state_label_is_search_aware(self):
        self.assertEqual(
            get_empty_state_label(EntryView.NOTES),
            "No note entries",
        )
        self.assertEqual(
            get_empty_state_label(EntryView.NOTES, "  missing "),
            NO_SEARCH_RESULTS_LABEL,
        )


if __name__ == "__main__":
    unittest.main()
