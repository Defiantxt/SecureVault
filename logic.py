import hashlib
import os
import hmac
from dotenv import load_dotenv
import mysql.connector

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
def create_secure_password(password: str):
    salt = os.urandom(16)
    iterations = 200_000

    hash_value = hashlib.pbkdf2_hmac(
        "sha256",
        (password + PEPPER).encode("utf-8"),
        salt,
        iterations
    )

    return salt, hash_value, iterations


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
    password_hash BLOB NOT NULL
)
""")


# ---------- MASTER PASSWORD SETUP ----------
cursor.execute("SELECT COUNT(*) FROM security")
count = cursor.fetchone()[0]  # type: ignore[attr-defined]

if count == 0:
    print("Table is empty")
    master_password = input("Create master password: ")
    salt, master_hash, iterations = create_secure_password(master_password)

    cursor.execute("""
    INSERT INTO security (master_hash, salt, iterations)
    VALUES (%s, %s, %s)
    """, (master_hash, salt, iterations))
else:
    print("Table is not empty")

# ---------- STORE USER PASSWORD ----------
user = input("Enter username: ")
password = input("Enter password: ")

salt, hashed_pw, _ = create_secure_password(password)

cursor.execute(
    "INSERT INTO passwords (name, password_hash) VALUES (%s, %s)",
    (user, hashed_pw)
)


db.commit()


# ---------- DISPLAY STORED DATA ----------
cursor.execute("SELECT id, name FROM passwords")
for row in cursor.fetchall():
    print(row)