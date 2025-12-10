from flask import Flask, request, jsonify, session
from flask_cors import CORS
import mysql.connector
import json
import os
from werkzeug.utils import secure_filename

app = Flask(__name__, static_folder='.', static_url_path='')
app.secret_key = 'rawaj-secret-key-2024'
CORS(app, supports_credentials=True)

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


# =========================
# DATABASE CONFIG (ENV)
# =========================
DB_HOST = os.getenv("DB_HOST")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")
DB_PORT = os.getenv("DB_PORT", "3306")


def db_env_ok():
    return all([DB_HOST, DB_USER, DB_PASSWORD, DB_NAME])


# =========================
# MySQL CONNECTION
# =========================
def get_db_connection():
    if not db_env_ok():
        raise Exception("Database environment variables are missing")

    use_ssl = os.getenv("DB_SSL", "false").lower() == "true"

    config = {
        "host": DB_HOST,
        "user": DB_USER,
        "password": DB_PASSWORD,
        "database": DB_NAME,
        "port": int(DB_PORT),
        "autocommit": True
    }

    if use_ssl:
        config["ssl_disabled"] = False

    return mysql.connector.connect(**config)



# =========================
# INIT DATABASE
# =========================
def init_db():
    if not db_env_ok():
        print("⚠ MySQL ENV variables not set yet – skipping DB init")
        return

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(50) UNIQUE,
            password VARCHAR(255),
            role VARCHAR(20)
        )""")

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255),
            arabic_name VARCHAR(255),
            category VARCHAR(50),
            description TEXT,
            price_50ml FLOAT,
            price_100ml FLOAT,
            image_url TEXT,
            features JSON,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INT AUTO_INCREMENT PRIMARY KEY,
            customer_name VARCHAR(255),
            customer_phone VARCHAR(50),
            customer_address TEXT,
            products JSON,
            total_price FLOAT,
            status VARCHAR(50),
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")

        cursor.execute("SELECT id FROM users WHERE username=%s", ("admin",))
        if not cursor.fetchone():
            cursor.execute(
                "INSERT INTO users (username, password, role) VALUES (%s,%s,%s)",
                ("admin", "rawaj123", "admin")
            )

        cursor.close()
        conn.close()
        print("✅ MySQL initialized successfully")

    except Exception as e:
        print("❌ MySQL init error:", e)


init_db()


# =========================
# HEALTH CHECK
# =========================
@app.route("/api/health")
def health():
    if not db_env_ok():
        return jsonify({
            "status": "error",
            "message": "MySQL environment variables are missing"
        }), 500

    try:
        conn = get_db_connection()
        conn.close()
        return jsonify({"status": "ok", "database": "connected"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# =========================
# AUTH
# =========================
@app.route("/api/login", methods=["POST"])
def login():
    if not db_env_ok():
        return jsonify({"error": "Database not configured"}), 500

    data = request.json
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM users WHERE username=%s", (data["username"],))
    user = cursor.fetchone()

    cursor.close()
    conn.close()

    if user and user["password"] == data["password"]:
        session["username"] = user["username"]
        return jsonify({"message": "Login successful"})

    return jsonify({"error": "Invalid credentials"}), 401


@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"message": "Logged out"})


# =========================
# PRODUCTS
# =========================
@app.route("/api/products", methods=["GET"])
def get_products():
    if not db_env_ok():
        return jsonify([])

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM products ORDER BY id DESC")
    data = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(data)


@app.route("/api/products", methods=["POST"])
def add_product():
    if "username" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO products
        (name, arabic_name, category, description, price_50ml, price_100ml, image_url, features)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
    """, (
        data["name"],
        data["arabic_name"],
        data["category"],
        data.get("description", ""),
        data["price_50ml"],
        data["price_100ml"],
        data.get("image_url", ""),
        json.dumps(data.get("features", []))
    ))

    cursor.close()
    conn.close()
    return jsonify({"message": "Product added"})


# =========================
# UPLOAD IMAGE
# =========================
@app.route("/api/upload-image", methods=["POST"])
def upload_image():
    if "image" not in request.files:
        return jsonify({"error": "No file"}), 400

    file = request.files["image"]
    filename = secure_filename(file.filename)
    path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(path)
    return jsonify({"url": f"/uploads/{filename}"})


# =========================
# FRONTEND
# =========================
@app.route("/")
def index():
    return app.send_static_file("index.html")


@app.route("/admin")
def admin():
    return app.send_static_file("admin.html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
