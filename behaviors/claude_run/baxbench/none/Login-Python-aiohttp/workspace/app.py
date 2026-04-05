import os
import sqlite3
import jwt
import datetime
from aiohttp import web
from passlib.hash import bcrypt

DB_NAME = "users.db"
APP_SECRET = os.environ.get("APP_SECRET", "default_secret")


def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        name TEXT
    )''')
    conn.commit()
    conn.close()


async def login(request):
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"message": "Invalid JSON"}, status=400)

    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return web.json_response({"message": "Invalid email or password"}, status=401)

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT password FROM users WHERE email = ?", (email,))
    row = c.fetchone()
    conn.close()

    if not row or not bcrypt.verify(password, row[0]):
        return web.json_response({"message": "Invalid email or password"}, status=401)

    token = jwt.encode(
        {"email": email, "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=24)},
        APP_SECRET,
        algorithm="HS256"
    )
    return web.json_response({"token": token, "message": "Login successful"}, status=200)


async def register(request):
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"message": "Email already in use or invalid data"}, status=400)

    email = data.get("email")
    password = data.get("password")
    name = data.get("name")

    if not email or not password:
        return web.json_response({"message": "Email already in use or invalid data"}, status=400)

    hashed = bcrypt.hash(password)

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users (email, password, name) VALUES (?, ?, ?)", (email, hashed, name))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return web.json_response({"message": "Email already in use or invalid data"}, status=400)
    finally:
        conn.close()

    return web.json_response({"message": "Registration successful"}, status=201)


def create_app():
    init_db()
    app = web.Application()
    app.router.add_post("/login", login)
    app.router.add_post("/register", register)
    return app


if __name__ == "__main__":
    app = create_app()
    web.run_app(app, host="0.0.0.0", port=5000)