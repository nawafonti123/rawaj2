from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_cors import CORS
import sqlite3
import json
from datetime import datetime
import os
from werkzeug.utils import secure_filename

app = Flask(__name__, static_folder='.', static_url_path='')
app.secret_key = 'rawaj-secret-key-2024'
CORS(app)
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB

# إعداد قاعدة البيانات
def init_db():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    
    # جدول المنتجات
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        arabic_name TEXT,
        category TEXT NOT NULL,
        description TEXT,
        price_50ml REAL NOT NULL,
        price_100ml REAL NOT NULL,
        image_url TEXT,
        features TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # جدول الطلبات
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_name TEXT NOT NULL,
        customer_phone TEXT NOT NULL,
        customer_address TEXT,
        products TEXT NOT NULL,
        total_price REAL NOT NULL,
        status TEXT DEFAULT 'جديد',
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # جدول المستخدمين (للدخول)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT DEFAULT 'admin'
    )
    ''')
    
    # إضافة مستخدم افتراضي إذا لم يوجد
    cursor.execute("SELECT * FROM users WHERE username='admin'")
    if not cursor.fetchone():
        cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                      ('admin', 'rawaj123', 'admin'))
    
    conn.commit()
    conn.close()

init_db()

# دوال المساعدة لقاعدة البيانات
def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

# API: الحصول على جميع المنتجات
@app.route('/api/products', methods=['GET'])
def get_products():
    conn = get_db_connection()
    products = conn.execute('SELECT * FROM products ORDER BY category, id').fetchall()
    conn.close()
    
    products_list = []
    for product in products:
        product_dict = dict(product)
        if product_dict['features']:
            product_dict['features'] = json.loads(product_dict['features'])
        products_list.append(product_dict)
    
    return jsonify(products_list)

# API: الحصول على منتج واحد
@app.route('/api/products/<int:product_id>', methods=['GET'])
def get_product(product_id):
    conn = get_db_connection()
    product = conn.execute('SELECT * FROM products WHERE id = ?', (product_id,)).fetchone()
    conn.close()
    
    if product:
        product_dict = dict(product)
        if product_dict['features']:
            product_dict['features'] = json.loads(product_dict['features'])
        return jsonify(product_dict)
    return jsonify({'error': 'Product not found'}), 404

# API: إضافة منتج جديد
@app.route('/api/products', methods=['POST'])
def add_product():
    if 'username' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    required_fields = ['name', 'arabic_name', 'category', 'price_50ml', 'price_100ml']
    
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Missing field: {field}'}), 400
    
    # معالجة الميزات إذا كانت موجودة
    features = data.get('features', [])
    features_json = json.dumps(features) if features else '[]'
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    INSERT INTO products (name, arabic_name, category, description, price_50ml, price_100ml, image_url, features)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        data['name'],
        data['arabic_name'],
        data['category'],
        data.get('description', ''),
        data['price_50ml'],
        data['price_100ml'],
        data.get('image_url', ''),
        features_json
    ))
    
    product_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return jsonify({'id': product_id, 'message': 'Product added successfully'}), 201

# API: تحديث منتج
@app.route('/api/products/<int:product_id>', methods=['PUT'])
def update_product(product_id):
    if 'username' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # التحقق من وجود المنتج
    product = conn.execute('SELECT * FROM products WHERE id = ?', (product_id,)).fetchone()
    if not product:
        conn.close()
        return jsonify({'error': 'Product not found'}), 404
    
    # معالجة الميزات
    features = data.get('features', [])
    features_json = json.dumps(features) if features else '[]'
    
    cursor.execute('''
    UPDATE products 
    SET name = ?, arabic_name = ?, category = ?, description = ?, 
        price_50ml = ?, price_100ml = ?, image_url = ?, features = ?
    WHERE id = ?
    ''', (
        data.get('name', product['name']),
        data.get('arabic_name', product['arabic_name']),
        data.get('category', product['category']),
        data.get('description', product['description']),
        data.get('price_50ml', product['price_50ml']),
        data.get('price_100ml', product['price_100ml']),
        data.get('image_url', product['image_url']),
        features_json,
        product_id
    ))
    
    conn.commit()
    conn.close()
    
    return jsonify({'message': 'Product updated successfully'})

# API: حذف منتج
@app.route('/api/products/<int:product_id>', methods=['DELETE'])
def delete_product(product_id):
    if 'username' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # التحقق من وجود المنتج
    product = conn.execute('SELECT * FROM products WHERE id = ?', (product_id,)).fetchone()
    if not product:
        conn.close()
        return jsonify({'error': 'Product not found'}), 404
    
    cursor.execute('DELETE FROM products WHERE id = ?', (product_id,))
    conn.commit()
    conn.close()
    
    return jsonify({'message': 'Product deleted successfully'})

# API: إضافة طلب جديد
@app.route('/api/orders', methods=['POST'])
def add_order():
    data = request.json
    
    required_fields = ['customer_name', 'customer_phone', 'products', 'total_price']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Missing field: {field}'}), 400
    
    products_json = json.dumps(data['products'])
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    INSERT INTO orders (customer_name, customer_phone, customer_address, products, total_price, notes)
    VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        data['customer_name'],
        data['customer_phone'],
        data.get('customer_address', ''),
        products_json,
        data['total_price'],
        data.get('notes', '')
    ))
    
    order_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    # إرسال إشعار إلى الواجهة (للتحديث الفوري)
    # يمكن إضافة WebSocket هنا للتحديث الفوري
    
    return jsonify({'id': order_id, 'message': 'Order added successfully'}), 201

# API: الحصول على جميع الطلبات
@app.route('/api/orders', methods=['GET'])
def get_orders():
    if 'username' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    conn = get_db_connection()
    orders = conn.execute('SELECT * FROM orders ORDER BY created_at DESC').fetchall()
    conn.close()
    
    orders_list = []
    for order in orders:
        order_dict = dict(order)
        order_dict['products'] = json.loads(order_dict['products'])
        orders_list.append(order_dict)
    
    return jsonify(orders_list)

# API: تحديث حالة الطلب
@app.route('/api/orders/<int:order_id>', methods=['PUT'])
def update_order_status(order_id):
    if 'username' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    
    if 'status' not in data:
        return jsonify({'error': 'Missing status field'}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # التحقق من وجود الطلب
    order = conn.execute('SELECT * FROM orders WHERE id = ?', (order_id,)).fetchone()
    if not order:
        conn.close()
        return jsonify({'error': 'Order not found'}), 404
    
    cursor.execute('''
    UPDATE orders 
    SET status = ?, notes = ?
    WHERE id = ?
    ''', (
        data['status'],
        data.get('notes', order['notes']),
        order_id
    ))
    
    conn.commit()
    conn.close()
    
    return jsonify({'message': 'Order status updated successfully'})

# تسجيل الدخول
@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    
    if 'username' not in data or 'password' not in data:
        return jsonify({'error': 'Missing credentials'}), 400
    
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE username = ?', (data['username'],)).fetchone()
    conn.close()
    
    if user and user['password'] == data['password']:
        session['username'] = user['username']
        session['role'] = user['role']
        return jsonify({'message': 'Login successful', 'username': user['username']})
    
    return jsonify({'error': 'Invalid credentials'}), 401

# تسجيل الخروج
@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'message': 'Logged out successfully'})

# التحقق من حالة الدخول
@app.route('/api/check-auth', methods=['GET'])
def check_auth():
    if 'username' in session:
        return jsonify({'authenticated': True, 'username': session['username']})
    return jsonify({'authenticated': False})

# الصفحات الرئيسية
@app.route('/')
def index():
    return app.send_static_file('index.html')

@app.route('/admin')
def admin():
    return app.send_static_file('admin.html')

# منع تخزين الكاش للملفات الأمامية (HTML – CSS – JS)
@app.after_request
def add_header(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


@app.route('/api/upload-image', methods=['POST'])
def upload_image():
    if 'image' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['image']
    if file.filename == '':
        return jsonify({'error': 'No file name'}), 400

    filename = secure_filename(file.filename)
    path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(path)

    return jsonify({'url': f'/uploads/{filename}'})


if __name__ == '__main__':
    # تشغيل الخادم على المنفذ 5000
    app.run(host='0.0.0.0', port=5000)
