import hashlib
import os
import hmac
from typing import cast
from dotenv import load_dotenv
import mysql.connector
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from argon2.low_level import hash_secret_raw, Type

load_dotenv()

PEPPER = os.environ["SECRET_KEY"]

db = mysql.connector.connect(
    host="localhost",
    user="root",
    password=os.environ["MY_SQL_PASSWORD"],
    database="vault"
)

cursor = db.cursor()


# ---------- PASSWORD HASHING ----------
def create_secure_password(password: str, salt=None, iterations=1_000_000) -> tuple[bytes, bytes, int]:
    if salt is None:
        salt = os.urandom(16)
    hash_value = hashlib.pbkdf2_hmac(
        "sha256",
        (password + PEPPER).encode("utf-8"),
        salt,
        iterations
    )
    return hash_value, salt, iterations


def verify_master_password_hash() -> bytes:
    entered_master_password = input("Enter master password: ")
    cursor.execute("SELECT master_hash, salt, iterations FROM security LIMIT 1")
    row = cursor.fetchone()
    if row is None:
        raise RuntimeError("No master password is set in the security table")
    stored_hash, salt, iterations = cast("tuple[bytes, bytes, int]", row)
    master_hash = create_secure_password(entered_master_password, salt, iterations)[0]

    if hmac.compare_digest(master_hash, stored_hash):
        print("Access granted")
    else:
        print("Wrong password")
    return master_hash

# ---------- TABLES ----------
cursor.execute("""
CREATE TABLE IF NOT EXISTS security (
    id INT AUTO_INCREMENT PRIMARY KEY,
    master_hash BLOB NOT NULL,
    salt BLOB NOT NULL,
    iterations INT NOT NULL
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS passwords (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    encrypted_password BLOB NOT NULL
)
""")


# ---------- MASTER PASSWORD SETUP ----------
cursor.execute("SELECT COUNT(*) FROM security")
count_row = cast("tuple[int] | None", cursor.fetchone())
count = count_row[0] if count_row else 0

if count == 0:
    print("Table is empty")
    master_password = input("Create master password: ")
    master_hash, salt, iterations = create_secure_password(master_password)

    cursor.execute("""
    INSERT INTO security (master_hash, salt, iterations)
    VALUES (%s, %s, %s)
    """, (master_hash, salt, iterations))
else:
    print("Table is not empty")
    verify_master_password_hash()


# ---------- STORE USER PASSWORD ----------
user = input("Enter username: ")
password = input("Enter password: ")

cursor.execute("SELECT salt FROM security LIMIT 1")
salt_row = cursor.fetchone()
if salt_row is None:
    raise RuntimeError("No salt is set in the security table")
salt = cast("tuple[bytes]", salt_row)[0]
key = hash_secret_raw(
    secret=password.encode(),
    salt=salt,
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    type=Type.ID
)

print(key)

db.commit()

# ---------- DISPLAY STORED DATA ----------
cursor.execute("SELECT id, name FROM passwords")
for row in cursor.fetchall():
    print(row)