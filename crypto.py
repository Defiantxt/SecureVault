import hashlib
import hmac
import os
import sqlite3

from argon2.low_level import Type, hash_secret_raw
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from dotenv import load_dotenv

ARGON2_TIME_COST = 3
ARGON2_MEMORY_COST = 65536
ARGON2_PARALLELISM = 4
MASTER_VERIFIER_CONTEXT = b"SecureVault:master-verifier:v1"


class Crypto:
    def __init__(self) -> None:
        load_dotenv()
        self.PEPPER = os.environ["SECRET_KEY"]
        self.db = sqlite3.connect("vault.db")
        self.cursor = self.db.cursor()
        self.create_tables()

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
            type_nonce BLOB NOT NULL
        )
        """)

    def user_exists(self) -> bool:
        self.cursor.execute("SELECT COUNT(*) FROM security")
        count = self.cursor.fetchone()[0]
        return count != 0

    def setup_master_password(self, master: str) -> bytes | None:
        if not self.user_exists():
            print("Table is empty")
            salt = os.urandom(16)
            vault_key = self.derive_vault_key(master, salt, ARGON2_TIME_COST)
            master_hash = self.create_master_verifier(vault_key)

            self.cursor.execute("""
            INSERT INTO security (master_hash, salt, iterations)
            VALUES (?, ?, ?)
            """, (master_hash, salt, ARGON2_TIME_COST))
            self.db.commit()
            print("Created new master password")
        else:
            print("Table is not empty")
            vault_key = self.verify_master_password_hash(master)
        return vault_key

    def store_entry(self, vault_key: bytes, entry_name: str, entry_password: str, type_entry: str) -> None:
        # encrypt entered password
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

    @staticmethod
    def create_master_verifier(vault_key: bytes) -> bytes:
        """Create a verifier without storing the vault key itself."""
        return hmac.new(vault_key, MASTER_VERIFIER_CONTEXT, hashlib.sha256).digest()

    def derive_vault_key(
        self,
        password: str,
        salt: bytes,
        time_cost: int = ARGON2_TIME_COST,
    ) -> bytes:
        """Derive the encryption key from the password and secret pepper."""
        peppered_password = hmac.new(
            self.PEPPER.encode("utf-8"),
            password.encode("utf-8"),
            hashlib.sha256,
        ).digest()

        return hash_secret_raw(
            secret=peppered_password,
            salt=salt,
            time_cost=time_cost,
            memory_cost=ARGON2_MEMORY_COST,
            parallelism=ARGON2_PARALLELISM,
            hash_len=32,
            type=Type.ID,
        )

    def verify_master_password_hash(self, entered_master_password: str) -> bytes | None:
        self.cursor.execute("SELECT master_hash, salt, iterations FROM security LIMIT 1")
        stored_hash, salt, time_cost = self.cursor.fetchone()
        vault_key = self.derive_vault_key(entered_master_password, salt, time_cost)
        master_hash = self.create_master_verifier(vault_key)

        if hmac.compare_digest(bytes(master_hash), bytes(stored_hash)):
            print("Access granted")
            return vault_key
        print("Wrong password")
        return None


    def decrypt_passwords(self, vault_key: bytes) -> dict[str, str] | None:
        aesgcm = AESGCM(vault_key)
        self.cursor.execute(
            """SELECT * FROM passwords"""
        )
        data = {}
        for row in self.cursor.fetchall():
            _, name, name_nonce, encrypted_password, password_nonce, type_entry, type_nonce = row
            name_nonce = bytes(name_nonce)
            password_nonce = bytes(password_nonce)

            stored_password_ciphertext = bytes(encrypted_password)
            stored_name_ciphertext = bytes(name)

            plaintext_bytes_name = aesgcm.decrypt(name_nonce, stored_name_ciphertext, None)
            plaintext_bytes_password = aesgcm.decrypt(password_nonce, stored_password_ciphertext, None)
            name = plaintext_bytes_name.decode("utf-8")
            password = plaintext_bytes_password.decode("utf-8")

            data[name] = password
        return data
