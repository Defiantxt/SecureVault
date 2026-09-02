import sqlite3
import tempfile
import unittest
from pathlib import Path

from crypto import (
    CLIPBOARD_CLEAR_SECONDS,
    PASSWORD_REVEAL_SECONDS,
    TRASH_RETENTION_SECONDS,
    Crypto,
)


class FakeKeyring:
    """Small in-memory keyring used to keep tests off the OS keychain."""

    def __init__(self, pepper="test-pepper"):
        self.values = {}
        if pepper is not None:
            self.values[("SecureVault", "vault_pepper")] = pepper

    def get_password(self, service_name, account_name):
        return self.values.get((service_name, account_name))

    def set_password(self, service_name, account_name, value):
        self.values[(service_name, account_name)] = value


class CryptoPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test-vault.db"
        self.keyring = FakeKeyring()
        self.vault_key = bytearray(b"K" * 32)
        self.current_epoch = 2_000_000
        self.crypto = Crypto(
            self.db_path,
            keyring_backend=self.keyring,
            clock=lambda: self.current_epoch,
        )

    def tearDown(self):
        self.crypto.close()
        self.temp_dir.cleanup()

    def add_entry(self, name="Example", content="secret", entry_type="Login"):
        self.crypto.store_entry(
            self.vault_key,
            name,
            content,
            entry_type,
        )
        return self.crypto.cursor.lastrowid

    def test_delete_alias_soft_deletes_and_clears_favorite_atomically(self):
        entry_id = self.add_entry()
        self.assertTrue(self.crypto.set_favorite(entry_id, True))

        self.assertTrue(self.crypto.delete_entry(entry_id, deleted_at=123_456))
        record = self.crypto.decrypt_entry_records(self.vault_key)[entry_id]

        self.assertEqual(record["deleted_at"], 123_456)
        self.assertFalse(record["favorite"])

    def test_repeated_move_to_trash_does_not_extend_retention(self):
        entry_id = self.add_entry()

        self.assertTrue(self.crypto.move_to_trash(entry_id, deleted_at=100))
        self.assertFalse(self.crypto.move_to_trash(entry_id, deleted_at=200))

        record = self.crypto.decrypt_entry_records(self.vault_key)[entry_id]
        self.assertEqual(record["deleted_at"], 100)

    def test_trashed_entries_cannot_be_favorited_or_edited(self):
        entry_id = self.add_entry(content="original")
        self.assertTrue(self.crypto.move_to_trash(entry_id, deleted_at=100))

        self.assertFalse(self.crypto.set_favorite(entry_id, True))
        self.assertFalse(
            self.crypto.update_entry(
                self.vault_key,
                entry_id,
                "Changed",
                "changed-secret",
                "Note",
            )
        )

        record = self.crypto.decrypt_entry_records(self.vault_key)[entry_id]
        self.assertEqual(record["name"], "Example")
        self.assertEqual(record["password"], "original")
        self.assertEqual(record["type"], "Login")
        self.assertFalse(record["favorite"])

    def test_restore_keeps_favorite_false_and_allows_active_updates(self):
        entry_id = self.add_entry()
        self.assertTrue(self.crypto.set_favorite(entry_id, True))
        self.assertTrue(self.crypto.move_to_trash(entry_id, deleted_at=100))

        self.assertTrue(self.crypto.restore_entry(entry_id))
        self.assertFalse(self.crypto.restore_entry(entry_id))
        restored = self.crypto.decrypt_entry_records(self.vault_key)[entry_id]
        self.assertIsNone(restored["deleted_at"])
        self.assertFalse(restored["favorite"])

        self.assertTrue(
            self.crypto.update_entry(
                self.vault_key,
                entry_id,
                "Updated",
                "new-secret",
                "Card",
            )
        )

    def test_permanent_delete_is_restricted_to_trash(self):
        entry_id = self.add_entry()

        self.assertFalse(self.crypto.permanently_delete_entry(entry_id))
        self.assertIn(
            entry_id,
            self.crypto.decrypt_entry_records(self.vault_key),
        )

        self.assertTrue(self.crypto.move_to_trash(entry_id, deleted_at=100))
        self.assertTrue(self.crypto.permanently_delete_entry(entry_id))
        self.assertFalse(self.crypto.permanently_delete_entry(entry_id))
        self.assertNotIn(
            entry_id,
            self.crypto.decrypt_entry_records(self.vault_key),
        )

    def test_purge_uses_exact_three_day_boundary(self):
        cutoff = self.current_epoch - TRASH_RETENTION_SECONDS
        older_id = self.add_entry(name="Older")
        exact_id = self.add_entry(name="Exact")
        newer_id = self.add_entry(name="Newer")
        future_id = self.add_entry(name="Future")
        active_id = self.add_entry(name="Active")
        self.crypto.move_to_trash(older_id, deleted_at=cutoff - 1)
        self.crypto.move_to_trash(exact_id, deleted_at=cutoff)
        self.crypto.move_to_trash(newer_id, deleted_at=cutoff + 1)
        self.crypto.move_to_trash(
            future_id,
            deleted_at=self.current_epoch + 1,
        )

        self.assertEqual(self.crypto.purge_expired_trash(), 2)
        remaining = self.crypto.decrypt_entry_records(self.vault_key)
        self.assertNotIn(older_id, remaining)
        self.assertNotIn(exact_id, remaining)
        self.assertIn(newer_id, remaining)
        self.assertIn(future_id, remaining)
        self.assertIn(active_id, remaining)

    def test_purge_and_delete_accept_valid_epoch_zero(self):
        entry_id = self.add_entry()
        self.assertTrue(self.crypto.move_to_trash(entry_id, deleted_at=0))

        self.assertEqual(
            self.crypto.purge_expired_trash(TRASH_RETENTION_SECONDS - 1),
            0,
        )
        self.assertEqual(
            self.crypto.purge_expired_trash(TRASH_RETENTION_SECONDS),
            1,
        )

    def test_invalid_epochs_are_rejected_without_mutating_entries(self):
        entry_id = self.add_entry()

        with self.assertRaises(ValueError):
            self.crypto.move_to_trash(entry_id, deleted_at=-1)
        with self.assertRaises(TypeError):
            self.crypto.move_to_trash(entry_id, deleted_at=True)
        with self.assertRaises(ValueError):
            self.crypto.purge_expired_trash(float("nan"))

        record = self.crypto.decrypt_entry_records(self.vault_key)[entry_id]
        self.assertIsNone(record["deleted_at"])

    def test_legacy_name_keyed_views_exclude_trashed_entries(self):
        active_id = self.add_entry(name="Active")
        trashed_id = self.add_entry(name="Trashed")
        self.crypto.move_to_trash(trashed_id, deleted_at=100)

        records = self.crypto.decrypt_entry_records(self.vault_key)
        legacy = self.crypto.decrypt_entries(self.vault_key)

        self.assertIn(active_id, records)
        self.assertEqual(records[trashed_id]["deleted_at"], 100)
        self.assertEqual(set(legacy), {"Active"})

    def test_app_settings_have_secure_defaults_and_persist(self):
        self.assertEqual(
            self.crypto.get_app_settings(),
            {
                PASSWORD_REVEAL_SECONDS: 15,
                CLIPBOARD_CLEAR_SECONDS: 30,
            },
        )

        self.assertTrue(self.crypto.set_password_reveal_seconds(60))
        self.assertTrue(self.crypto.set_clipboard_clear_seconds(120))
        self.assertEqual(self.crypto.get_password_reveal_seconds(), 60)
        self.assertEqual(self.crypto.get_clipboard_clear_seconds(), 120)

        self.crypto.close()
        self.crypto = Crypto(
            self.db_path,
            keyring_backend=self.keyring,
            clock=lambda: self.current_epoch,
        )
        self.assertEqual(
            self.crypto.get_app_settings(),
            {
                PASSWORD_REVEAL_SECONDS: 60,
                CLIPBOARD_CLEAR_SECONDS: 120,
            },
        )

    def test_app_setting_validation_rejects_unsafe_values(self):
        with self.assertRaises(KeyError):
            self.crypto.set_setting("unknown", 15)
        with self.assertRaises(KeyError):
            self.crypto.get_setting("unknown")
        with self.assertRaises(TypeError):
            self.crypto.set_password_reveal_seconds(True)
        with self.assertRaises(TypeError):
            self.crypto.set_password_reveal_seconds(15.0)
        with self.assertRaises(ValueError):
            self.crypto.set_password_reveal_seconds(4)
        with self.assertRaises(ValueError):
            self.crypto.set_clipboard_clear_seconds(301)

    def test_corrupt_setting_falls_back_to_secure_default(self):
        self.crypto.cursor.execute(
            "UPDATE app_settings SET value = ? WHERE key = ?",
            (99_999, PASSWORD_REVEAL_SECONDS),
        )
        self.crypto.db.commit()

        self.assertEqual(self.crypto.get_password_reveal_seconds(), 15)


class CryptoMigrationTests(unittest.TestCase):
    def test_old_password_schema_migrates_idempotently(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "legacy.db"
            db = sqlite3.connect(db_path)
            db.execute(
                """
                CREATE TABLE passwords (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    name_nonce BLOB NOT NULL,
                    encrypted_password BLOB NOT NULL,
                    password_nonce BLOB NOT NULL,
                    type_entry BLOB NOT NULL,
                    type_nonce BLOB NOT NULL
                )
                """
            )
            db.execute(
                """
                INSERT INTO passwords (
                    name, name_nonce, encrypted_password, password_nonce,
                    type_entry, type_nonce
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (b"name", b"nonce", b"secret", b"nonce", b"type", b"nonce"),
            )
            db.commit()
            db.close()

            fake_keyring = FakeKeyring()
            first = Crypto(db_path, keyring_backend=fake_keyring)
            first.close()
            second = Crypto(db_path, keyring_backend=fake_keyring)
            columns = {
                row[1]: row
                for row in second.cursor.execute(
                    "PRAGMA table_info(passwords)"
                ).fetchall()
            }
            indexes = {
                row[1]
                for row in second.cursor.execute(
                    "PRAGMA index_list(passwords)"
                ).fetchall()
            }
            migrated_row = second.cursor.execute(
                "SELECT favorite, deleted_at FROM passwords WHERE id = 1"
            ).fetchone()
            second.close()

            self.assertIn("favorite", columns)
            self.assertIn("deleted_at", columns)
            self.assertEqual(columns["deleted_at"][2].upper(), "INTEGER")
            self.assertEqual(columns["deleted_at"][3], 0)
            self.assertIn("idx_passwords_deleted_at", indexes)
            self.assertEqual(migrated_row, (0, None))

    def test_empty_fake_keyring_receives_a_new_pepper(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            fake_keyring = FakeKeyring(pepper=None)
            crypto = Crypto(
                Path(temp_dir) / "vault.db",
                keyring_backend=fake_keyring,
            )
            pepper = fake_keyring.get_password(
                "SecureVault",
                "vault_pepper",
            )
            crypto.close()

            self.assertIsInstance(pepper, str)
            self.assertEqual(len(pepper), 64)


if __name__ == "__main__":
    unittest.main()
