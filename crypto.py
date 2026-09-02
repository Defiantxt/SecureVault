import hashlib
import hmac
import os
import secrets
import sqlite3

import keyring
from argon2.low_level import Type, hash_secret_raw
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

ARGON2_TIME_COST = 3
ARGON2_MEMORY_COST = 65536
ARGON2_PARALLELISM = 4
MASTER_VERIFIER_CONTEXT = b"SecureVault:master-verifier:v1"


def zero_vault_key(vault_key: bytearray) -> None:
    """Overwrite mutable vault-key material in place."""
    vault_key[:] = b"\x00" * len(vault_key)


class Crypto:
    def __init__(self) -> None:
        self.service_name = "SecureVault"
        self.pepper_account = "vault_pepper"

        self.db = sqlite3.connect("vault.db")
        self.cursor = self.db.cursor()

        self.cursor.execute("PRAGMA secure_delete = ON")
        self.create_tables()
        self.setup_pepper()

    def setup_pepper(self) -> None:
        stored_pepper = keyring.get_password(
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

            keyring.set_password(
                self.service_name,
                self.pepper_account,
                stored_pepper,
            )

        self.PEPPER = stored_pepper
    
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
            favorite INTEGER NOT NULL DEFAULT 0
        )
        """)

        self.cursor.execute("PRAGMA table_info(passwords)")
        password_columns = {row[1] for row in self.cursor.fetchall()}
        if "favorite" not in password_columns:
            self.cursor.execute(
                "ALTER TABLE passwords "
                "ADD COLUMN favorite INTEGER NOT NULL DEFAULT 0"
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

    def store_entry(self, vault_key: bytearray, entry_name: str, entry_password: str, type_entry: str) -> None:
        aesgcm = AESGCM(vault_key)

        name_nonce = os.urandom(12)
        password_nonce = os.urandom(12)
        type_nonce = os.urandom(12)

        name_ciphertext = aesgcm.encrypt(name_nonce, entry_name.encode(), None)
        password_ciphertext = aesgcm.encrypt(password_nonce, entry_password.encode(), None)
        type_ciphertext = aesgcm.encrypt(type_nonce, type_entry.encode(), None)

        self.cursor.execute("""
            INSERT INTO passwords (name, name_nonce, encrypted_password, password_nonce, type_entry, type_nonce)
            VALUES (?, ?, ?, ?, ?, ?)
            """, (
                name_ciphertext, name_nonce,
                password_ciphertext, password_nonce,
                type_ciphertext, type_nonce
            ))

        self.db.commit()

    def update_entry(
        self,
        vault_key: bytearray,
        entry_id: int,
        entry_name: str,
        entry_password: str,
        type_entry: str,
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

        self.cursor.execute(
            """
            UPDATE passwords
            SET name = ?, name_nonce = ?,
                encrypted_password = ?, password_nonce = ?,
                type_entry = ?, type_nonce = ?
            WHERE id = ?
            """,
            (
                name_ciphertext,
                name_nonce,
                password_ciphertext,
                password_nonce,
                type_ciphertext,
                type_nonce,
                entry_id,
            ),
        )
        updated = self.cursor.rowcount > 0
        self.db.commit()
        return updated

    def delete_entry(self, entry_id: int) -> bool:
        """Delete one entry by its stable database identifier."""
        self.cursor.execute("DELETE FROM passwords WHERE id = ?", (entry_id,))
        deleted = self.cursor.rowcount > 0
        self.db.commit()
        return deleted

    def set_favorite(self, entry_id: int, favorite: bool) -> bool:
        """Set an entry's favorite state."""
        self.cursor.execute(
            "UPDATE passwords SET favorite = ? WHERE id = ?",
            (int(bool(favorite)), entry_id),
        )
        updated = self.cursor.rowcount > 0
        self.db.commit()
        return updated

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
    ) -> dict[int, dict[str, int | str | bool]]:
        """Decrypt entries keyed by their stable database identifiers."""
        aesgcm = AESGCM(vault_key)
        self.cursor.execute(
            """
            SELECT id, name, name_nonce, encrypted_password, password_nonce,
                   type_entry, type_nonce, favorite
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
                "favorite": bool(favorite),
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
        }

    def decrypt_passwords(
        self, vault_key: bytearray
    ) -> dict[str, str] | None:
        return {
            name: entry["password"]
            for name, entry in self.decrypt_entries(vault_key).items()
        }
