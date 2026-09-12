import hashlib
import hmac
import math
import os
import secrets
import sqlite3
import time
from collections.abc import Callable

import keyring
from argon2.low_level import Type, hash_secret_raw
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

ARGON2_TIME_COST = 3
ARGON2_MEMORY_COST = 65536
ARGON2_PARALLELISM = 4
MASTER_VERIFIER_CONTEXT = b"SecureVault:master-verifier:v1"
TRASH_RETENTION_SECONDS = 3 * 24 * 60 * 60

PASSWORD_REVEAL_SECONDS = "password_reveal_seconds"
CLIPBOARD_CLEAR_SECONDS = "clipboard_clear_seconds"
APP_SETTING_SPECS = {
    PASSWORD_REVEAL_SECONDS: {
        "default": 15,
        "minimum": 5,
        "maximum": 300,
    },
    CLIPBOARD_CLEAR_SECONDS: {
        "default": 30,
        "minimum": 5,
        "maximum": 300,
    },
}


def zero_vault_key(vault_key: bytearray) -> None:
    """Overwrite mutable vault-key material in place."""
    vault_key[:] = b"\x00" * len(vault_key)


class Crypto:
    def __init__(
        self,
        db_path: str | os.PathLike[str] = "vault.db",
        *,
        keyring_backend=None,
        pepper: str | None = None,
        clock: Callable[[], int | float] | None = None,
    ) -> None:
        """Open a vault store and initialize its schema.

        The defaults retain the application's existing behavior. ``db_path``,
        ``keyring_backend``, ``pepper``, and ``clock`` are injectable so tests
        and alternate front ends do not need to touch the real vault, OS
        credential store, or wall clock.
        """
        self.service_name = "SecureVault"
        self.pepper_account = "vault_pepper"
        self._keyring = keyring if keyring_backend is None else keyring_backend
        self._clock = time.time if clock is None else clock

        self.db = sqlite3.connect(os.fspath(db_path))
        self.cursor = self.db.cursor()

        try:
            self.cursor.execute("PRAGMA secure_delete = ON")
            self.create_tables()
            if pepper is None:
                self.setup_pepper()
            else:
                self.PEPPER = self._validate_pepper(pepper)
        except Exception:
            self.db.close()
            raise

    @staticmethod
    def _validate_pepper(pepper: str) -> str:
        if not isinstance(pepper, str):
            raise TypeError("pepper must be a string")
        if not pepper:
            raise ValueError("pepper must not be empty")
        return pepper

    def close(self) -> None:
        """Close the SQLite connection owned by this instance."""
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

    def setup_pepper(self) -> None:
        stored_pepper = self._keyring.get_password(
            self.service_name,
            self.pepper_account,
        )

        if stored_pepper is None:
            if self.user_exists():
                raise RuntimeError(
                    "Vault exists but its pepper is missing. "
                    "Refusing to generate a replacement."
                )

            stored_pepper = secrets.token_hex(32)

            self._keyring.set_password(
                self.service_name,
                self.pepper_account,
                stored_pepper,
            )

        self.PEPPER = self._validate_pepper(stored_pepper)
    
    def create_tables(self) -> None:
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS security (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            master_hash BLOB NOT NULL,
            salt BLOB NOT NULL,
            iterations INT NOT NULL
        )
        """)

        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS passwords (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            name_nonce BLOB NOT NULL,
            encrypted_password BLOB NOT NULL,
            password_nonce BLOB NOT NULL,
            type_entry BLOB NOT NULL,
            type_nonce BLOB NOT NULL,
            encrypted_service BLOB DEFAULT NULL,
            service_nonce BLOB DEFAULT NULL,
            encrypted_pin BLOB DEFAULT NULL,
            pin_nonce BLOB DEFAULT NULL,
            encrypted_expiry BLOB DEFAULT NULL,
            expiry_nonce BLOB DEFAULT NULL,
            favorite INTEGER NOT NULL DEFAULT 0,
            deleted_at INTEGER DEFAULT NULL
        )
        """)

        self.cursor.execute("PRAGMA table_info(passwords)")
        password_columns = {row[1] for row in self.cursor.fetchall()}
        if "favorite" not in password_columns:
            self.cursor.execute(
                "ALTER TABLE passwords "
                "ADD COLUMN favorite INTEGER NOT NULL DEFAULT 0"
            )
        if "deleted_at" not in password_columns:
            self.cursor.execute(
                "ALTER TABLE passwords "
                "ADD COLUMN deleted_at INTEGER DEFAULT NULL"
            )
        optional_entry_columns = (
            "encrypted_service",
            "service_nonce",
            "encrypted_pin",
            "pin_nonce",
            "encrypted_expiry",
            "expiry_nonce",
        )
        for column_name in optional_entry_columns:
            if column_name not in password_columns:
                self.cursor.execute(
                    f"ALTER TABLE passwords ADD COLUMN {column_name} "
                    "BLOB DEFAULT NULL"
                )

        self.cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_passwords_deleted_at
            ON passwords(deleted_at)
            WHERE deleted_at IS NOT NULL
            """
        )

        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value INTEGER NOT NULL
            )
            """
        )
        self.cursor.executemany(
            """
            INSERT OR IGNORE INTO app_settings (key, value)
            VALUES (?, ?)
            """,
            (
                (name, spec["default"])
                for name, spec in APP_SETTING_SPECS.items()
            ),
        )

        self.db.commit()

    def user_exists(self) -> bool:
        self.cursor.execute("SELECT COUNT(*) FROM security")
        count = self.cursor.fetchone()[0]
        return count != 0

    def setup_master_password(self, master: str) -> bytearray | None:
        if not self.user_exists():
            print("Table is empty")
            salt = os.urandom(16)
            vault_key = self.derive_vault_key(master, salt, ARGON2_TIME_COST)
            keep_vault_key = False
            try:
                master_hash = self.create_master_verifier(vault_key)

                self.cursor.execute("""
                INSERT INTO security (master_hash, salt, iterations)
                VALUES (?, ?, ?)
                """, (master_hash, salt, ARGON2_TIME_COST))
                self.db.commit()
                print("Created new master password")
                keep_vault_key = True
            finally:
                if not keep_vault_key:
                    zero_vault_key(vault_key)
        else:
            print("Table is not empty")
            vault_key = self.verify_master_password_hash(master)
        return vault_key

    @staticmethod
    def _encrypt_optional_entry_field(
        aesgcm: AESGCM,
        value: str,
    ) -> tuple[bytes | None, bytes | None]:
        """Encrypt optional entry metadata, leaving absent values as NULL."""

        if value == "":
            return None, None
        nonce = os.urandom(12)
        return aesgcm.encrypt(nonce, value.encode(), None), nonce

    @staticmethod
    def _decrypt_optional_entry_field(
        aesgcm: AESGCM,
        ciphertext: bytes | None,
        nonce: bytes | None,
    ) -> str:
        """Decrypt optional metadata and normalize legacy NULLs to empty text."""

        if ciphertext is None and nonce is None:
            return ""
        if ciphertext is None or nonce is None:
            raise ValueError("Optional entry ciphertext and nonce must coexist")
        return aesgcm.decrypt(bytes(nonce), bytes(ciphertext), None).decode(
            "utf-8"
        )

    def store_entry(
        self,
        vault_key: bytearray,
        entry_name: str,
        entry_password: str,
        type_entry: str,
        *,
        service: str = "",
        pin: str = "",
        expiry: str = "",
    ) -> None:
        aesgcm = AESGCM(vault_key)

        name_nonce = os.urandom(12)
        password_nonce = os.urandom(12)
        type_nonce = os.urandom(12)

        name_ciphertext = aesgcm.encrypt(name_nonce, entry_name.encode(), None)
        password_ciphertext = aesgcm.encrypt(password_nonce, entry_password.encode(), None)
        type_ciphertext = aesgcm.encrypt(type_nonce, type_entry.encode(), None)
        service_ciphertext, service_nonce = (
            self._encrypt_optional_entry_field(aesgcm, service)
        )
        pin_ciphertext, pin_nonce = self._encrypt_optional_entry_field(
            aesgcm, pin
        )
        expiry_ciphertext, expiry_nonce = (
            self._encrypt_optional_entry_field(aesgcm, expiry)
        )

        self.cursor.execute("""
            INSERT INTO passwords (
                name, name_nonce, encrypted_password, password_nonce,
                type_entry, type_nonce, encrypted_service, service_nonce,
                encrypted_pin, pin_nonce, encrypted_expiry, expiry_nonce
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                name_ciphertext, name_nonce,
                password_ciphertext, password_nonce,
                type_ciphertext, type_nonce,
                service_ciphertext, service_nonce,
                pin_ciphertext, pin_nonce,
                expiry_ciphertext, expiry_nonce,
            ))

        self.db.commit()

    def update_entry(
        self,
        vault_key: bytearray,
        entry_id: int,
        entry_name: str,
        entry_password: str,
        type_entry: str,
        *,
        service: str = "",
        pin: str = "",
        expiry: str = "",
    ) -> bool:
        """Replace an entry's encrypted fields while preserving its identity."""
        aesgcm = AESGCM(vault_key)

        name_nonce = os.urandom(12)
        password_nonce = os.urandom(12)
        type_nonce = os.urandom(12)

        name_ciphertext = aesgcm.encrypt(name_nonce, entry_name.encode(), None)
        password_ciphertext = aesgcm.encrypt(
            password_nonce, entry_password.encode(), None
        )
        type_ciphertext = aesgcm.encrypt(type_nonce, type_entry.encode(), None)
        service_ciphertext, service_nonce = (
            self._encrypt_optional_entry_field(aesgcm, service)
        )
        pin_ciphertext, pin_nonce = self._encrypt_optional_entry_field(
            aesgcm, pin
        )
        expiry_ciphertext, expiry_nonce = (
            self._encrypt_optional_entry_field(aesgcm, expiry)
        )

        self.cursor.execute(
            """
            UPDATE passwords
            SET name = ?, name_nonce = ?,
                encrypted_password = ?, password_nonce = ?,
                type_entry = ?, type_nonce = ?,
                encrypted_service = ?, service_nonce = ?,
                encrypted_pin = ?, pin_nonce = ?,
                encrypted_expiry = ?, expiry_nonce = ?
            WHERE id = ? AND deleted_at IS NULL
            """,
            (
                name_ciphertext,
                name_nonce,
                password_ciphertext,
                password_nonce,
                type_ciphertext,
                type_nonce,
                service_ciphertext,
                service_nonce,
                pin_ciphertext,
                pin_nonce,
                expiry_ciphertext,
                expiry_nonce,
                entry_id,
            ),
        )
        updated = self.cursor.rowcount > 0
        self.db.commit()
        return updated

    @staticmethod
    def _coerce_epoch_seconds(value: int | float, *, name: str) -> int:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"{name} must be a number of UTC epoch seconds")
        if not math.isfinite(value):
            raise ValueError(f"{name} must be finite")

        epoch = int(value)
        if epoch < 0:
            raise ValueError(f"{name} must not be negative")
        return epoch

    def move_to_trash(
        self,
        entry_id: int,
        deleted_at: int | float | None = None,
    ) -> bool:
        """Soft-delete an active entry and clear its favorite state.

        Repeating the operation returns ``False`` and deliberately leaves the
        original timestamp unchanged, so reopening a stale dialog cannot
        extend the retention period.
        """
        timestamp = self._coerce_epoch_seconds(
            self._clock() if deleted_at is None else deleted_at,
            name="deleted_at",
        )
        self.cursor.execute(
            """
            UPDATE passwords
            SET deleted_at = ?, favorite = 0
            WHERE id = ? AND deleted_at IS NULL
            """,
            (timestamp, entry_id),
        )
        moved = self.cursor.rowcount > 0
        self.db.commit()
        return moved

    def delete_entry(
        self,
        entry_id: int,
        deleted_at: int | float | None = None,
    ) -> bool:
        """Backward-compatible alias that now moves an entry to trash."""
        return self.move_to_trash(entry_id, deleted_at)

    def restore_entry(self, entry_id: int) -> bool:
        """Restore a trashed entry without restoring its favorite state."""
        self.cursor.execute(
            """
            UPDATE passwords
            SET deleted_at = NULL, favorite = 0
            WHERE id = ? AND deleted_at IS NOT NULL
            """,
            (entry_id,),
        )
        restored = self.cursor.rowcount > 0
        self.db.commit()
        return restored

    def permanently_delete_entry(self, entry_id: int) -> bool:
        """Permanently delete an entry only when it is already in trash."""
        self.cursor.execute(
            "DELETE FROM passwords WHERE id = ? AND deleted_at IS NOT NULL",
            (entry_id,),
        )
        deleted = self.cursor.rowcount > 0
        self.db.commit()
        return deleted

    def purge_expired_trash(
        self,
        current_epoch: int | float | None = None,
    ) -> int:
        """Permanently remove trash aged exactly three days or more."""
        now = self._coerce_epoch_seconds(
            self._clock() if current_epoch is None else current_epoch,
            name="current_epoch",
        )
        cutoff = now - TRASH_RETENTION_SECONDS
        self.cursor.execute(
            """
            DELETE FROM passwords
            WHERE deleted_at IS NOT NULL AND deleted_at <= ?
            """,
            (cutoff,),
        )
        purged = self.cursor.rowcount
        self.db.commit()
        return purged

    def set_favorite(self, entry_id: int, favorite: bool) -> bool:
        """Set an active entry's favorite state; trash is immutable here."""
        self.cursor.execute(
            """
            UPDATE passwords
            SET favorite = ?
            WHERE id = ? AND deleted_at IS NULL
            """,
            (int(bool(favorite)), entry_id),
        )
        updated = self.cursor.rowcount > 0
        self.db.commit()
        return updated

    @staticmethod
    def _validate_setting_value(name: str, value: int) -> int:
        if name not in APP_SETTING_SPECS:
            raise KeyError(f"Unknown app setting: {name}")
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(f"{name} must be an integer number of seconds")

        spec = APP_SETTING_SPECS[name]
        minimum = spec["minimum"]
        maximum = spec["maximum"]
        if not minimum <= value <= maximum:
            raise ValueError(
                f"{name} must be between {minimum} and {maximum} seconds"
            )
        return value

    def get_setting(self, name: str) -> int:
        """Read a validated setting, falling back to its secure default."""
        if name not in APP_SETTING_SPECS:
            raise KeyError(f"Unknown app setting: {name}")

        self.cursor.execute(
            "SELECT value FROM app_settings WHERE key = ?",
            (name,),
        )
        row = self.cursor.fetchone()
        if row is None:
            return APP_SETTING_SPECS[name]["default"]

        try:
            return self._validate_setting_value(name, row[0])
        except (TypeError, ValueError):
            # A corrupt or manually edited database must not silently disable
            # the application's short secret-exposure timeouts.
            return APP_SETTING_SPECS[name]["default"]

    def set_setting(self, name: str, value: int) -> bool:
        """Validate and persist one supported non-secret app setting."""
        value = self._validate_setting_value(name, value)
        self.cursor.execute(
            """
            INSERT INTO app_settings (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (name, value),
        )
        self.db.commit()
        return True

    def get_app_setting(self, name: str) -> int:
        """Alias retained for callers that use an app-specific name."""
        return self.get_setting(name)

    def set_app_setting(self, name: str, value: int) -> bool:
        """Alias retained for callers that use an app-specific name."""
        return self.set_setting(name, value)

    def get_app_settings(self) -> dict[str, int]:
        """Return all supported settings with defaults filled in."""
        return {
            name: self.get_setting(name)
            for name in APP_SETTING_SPECS
        }

    def get_password_reveal_seconds(self) -> int:
        return self.get_setting(PASSWORD_REVEAL_SECONDS)

    def set_password_reveal_seconds(self, value: int) -> bool:
        return self.set_setting(PASSWORD_REVEAL_SECONDS, value)

    def get_clipboard_clear_seconds(self) -> int:
        return self.get_setting(CLIPBOARD_CLEAR_SECONDS)

    def set_clipboard_clear_seconds(self, value: int) -> bool:
        return self.set_setting(CLIPBOARD_CLEAR_SECONDS, value)

    @staticmethod
    def create_master_verifier(vault_key: bytearray) -> bytes:
        """Create a verifier without storing the vault key itself."""
        return hmac.new(vault_key, MASTER_VERIFIER_CONTEXT, hashlib.sha256).digest()

    def derive_vault_key(
        self,
        password: str,
        salt: bytes,
        time_cost: int = ARGON2_TIME_COST,
    ) -> bytearray:
        """Derive the encryption key from the password and secret pepper."""
        peppered_password = hmac.new(
            self.PEPPER.encode("utf-8"),
            password.encode("utf-8"),
            hashlib.sha256,
        ).digest()

        return bytearray(
            hash_secret_raw(
                secret=peppered_password,
                salt=salt,
                time_cost=time_cost,
                memory_cost=ARGON2_MEMORY_COST,
                parallelism=ARGON2_PARALLELISM,
                hash_len=32,
                type=Type.ID,
            )
        )

    def verify_master_password_hash(
        self, entered_master_password: str
    ) -> bytearray | None:
        self.cursor.execute("SELECT master_hash, salt, iterations FROM security LIMIT 1")
        stored_hash, salt, time_cost = self.cursor.fetchone()
        vault_key = self.derive_vault_key(entered_master_password, salt, time_cost)
        keep_vault_key = False
        try:
            master_hash = self.create_master_verifier(vault_key)
            if hmac.compare_digest(bytes(master_hash), bytes(stored_hash)):
                print("Access granted")
                keep_vault_key = True
                return vault_key
            print("Wrong password")
            return None
        finally:
            if not keep_vault_key:
                zero_vault_key(vault_key)

    def decrypt_entry_records(
        self, vault_key: bytearray
    ) -> dict[int, dict[str, int | str | bool | None]]:
        """Decrypt entries keyed by their stable database identifiers."""
        aesgcm = AESGCM(vault_key)
        self.cursor.execute(
            """
            SELECT id, name, name_nonce, encrypted_password, password_nonce,
                   type_entry, type_nonce, favorite, deleted_at,
                   encrypted_service, service_nonce, encrypted_pin, pin_nonce,
                   encrypted_expiry, expiry_nonce
            FROM passwords
            """
        )
        records = {}
        for (
            entry_id,
            name,
            name_nonce,
            encrypted_password,
            password_nonce,
            type_entry,
            type_nonce,
            favorite,
            deleted_at,
            encrypted_service,
            service_nonce,
            encrypted_pin,
            pin_nonce,
            encrypted_expiry,
            expiry_nonce,
        ) in self.cursor.fetchall():
            decrypted_name = aesgcm.decrypt(
                bytes(name_nonce), bytes(name), None
            ).decode("utf-8")
            decrypted_password = aesgcm.decrypt(
                bytes(password_nonce), bytes(encrypted_password), None
            ).decode("utf-8")
            try:
                decrypted_type = aesgcm.decrypt(
                    bytes(type_nonce), bytes(type_entry), None
                ).decode("utf-8")
            except (TypeError, UnicodeDecodeError, ValueError):
                decrypted_type = "Vault entry"

            records[entry_id] = {
                "id": entry_id,
                "name": decrypted_name,
                "password": decrypted_password,
                "type": decrypted_type,
                "service": self._decrypt_optional_entry_field(
                    aesgcm, encrypted_service, service_nonce
                ),
                "pin": self._decrypt_optional_entry_field(
                    aesgcm, encrypted_pin, pin_nonce
                ),
                "expiry": self._decrypt_optional_entry_field(
                    aesgcm, encrypted_expiry, expiry_nonce
                ),
                "favorite": bool(favorite),
                "deleted_at": deleted_at,
            }
        return records

    def decrypt_entries(
        self, vault_key: bytearray
    ) -> dict[str, dict[str, str]]:
        """Return the legacy name-keyed entry mapping."""
        return {
            str(entry["name"]): {
                "password": str(entry["password"]),
                "type": str(entry["type"]),
            }
            for entry in self.decrypt_entry_records(vault_key).values()
            if entry["deleted_at"] is None
        }

    def decrypt_passwords(
        self, vault_key: bytearray
    ) -> dict[str, str] | None:
        return {
            name: entry["password"]
            for name, entry in self.decrypt_entries(vault_key).items()
        }
