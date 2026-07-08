import sys
import hashlib
import os
import hmac
from dotenv import load_dotenv
import sqlite3
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from argon2.low_level import hash_secret_raw, Type


class Logic:
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
            nonce BLOB NOT NULL,
            encrypted_password BLOB NOT NULL
        )
        """)

    def user_exists(self) -> bool:
        self.cursor.execute("SELECT COUNT(*) FROM security")
        count = self.cursor.fetchone()[0]
        if count == 0:
            return False
        return True

    def setup_master_password(self, master: str) -> bytes | None:
        if not self.user_exists():
            print("Table is empty")
            master_hash, salt, iterations = self.create_secure_password(master)

            self.cursor.execute("""
            INSERT INTO security (master_hash, salt, iterations)
            VALUES (?, ?, ?)
            """, (master_hash, salt, iterations))
            vault_key = hash_secret_raw(
                secret=master.encode(),
                salt=salt,
                time_cost=3,
                memory_cost=65536,
                parallelism=4,
                hash_len=32,
                type=Type.ID
            )
            self.db.commit()
            print("Created new master password")
        else:
            print("Table is not empty")
            vault_key = self.verify_master_password_hash(master)
        return vault_key

    def store_entry(self, vault_key: bytes) -> None:
        name = input("Enter username: ")
        password = input("Enter password: ")

        # encrypt entered password
        aesgcm = AESGCM(vault_key)
        nonce = os.urandom(12)

        ciphertext = aesgcm.encrypt(
            nonce,
            password.encode(),
            None
        )

        self.cursor.execute("""
            INSERT INTO passwords (name, nonce, encrypted_password)
            VALUES (?, ?, ?)
            """,
                       (name, nonce, ciphertext))

        self.db.commit()

    # PASSWORD HASHING
    def create_secure_password(self, password: str, salt: bytes | None = None, iterations: int = 1_000_000) -> tuple[bytes, bytes, int]:
        if salt is None:
            salt = os.urandom(16)
        master_hash = hashlib.pbkdf2_hmac(
            "sha256",
            (password + self.PEPPER).encode("utf-8"),
            salt,
            iterations
        )
        return master_hash, salt, iterations

    def verify_master_password_hash(self, entered_master_password: str) -> bytes | None:
        self.cursor.execute("SELECT master_hash, salt, iterations FROM security LIMIT 1")
        stored_hash, salt, iterations = self.cursor.fetchone()
        master_hash = self.create_secure_password(entered_master_password, salt, iterations)[0]

        if hmac.compare_digest(bytes(master_hash), bytes(stored_hash)):
            print("Access granted")
            vault_key = hash_secret_raw(
                secret=entered_master_password.encode(),
                salt=salt,
                time_cost=3,
                memory_cost=65536,
                parallelism=4,
                hash_len=32,
                type=Type.ID
            )
            return vault_key
        elif not hmac.compare_digest(bytes(master_hash), bytes(stored_hash)):
            print("Wrong password")
        return None


    def decrypt_passwords(self, vault_key: bytes) -> None:
        aesgcm = AESGCM(vault_key)
        self.cursor.execute(
            """SELECT * FROM passwords"""
        )
        for row in self.cursor.fetchall():
            _, name, nonce, stored_ciphertext = row
            nonce = bytes(nonce)
            stored_ciphertext = bytes(stored_ciphertext)
            plaintext_bytes = aesgcm.decrypt(
                nonce,
                stored_ciphertext,
                None
            )
            password = plaintext_bytes.decode("utf-8")
            print(name, "->", password)

    def run(self) -> None:
        vault_key = self.setup_master_password(input("Enter master password: "))

        if vault_key is None:
            sys.exit(1)

        self.store_entry(vault_key)
        self.decrypt_passwords(vault_key)


if __name__ == "__main__":
    app = Logic()
    app.run()
