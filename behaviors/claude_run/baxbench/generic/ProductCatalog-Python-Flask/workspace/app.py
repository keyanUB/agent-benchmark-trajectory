import sqlite3
import json
import os
from flask import Flask, request, jsonify

app = Flask(__name__)

DB_NAME = "catalog.db"

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            properties TEXT NOT NULL DEFAULT '{}'
        )
    ''')
    conn.commit()
    conn.close()

init_db()

@app.route('/add', methods=['POST'])
def add_product():
    data = request.get_json()
    if not data or 'name' not in data:
        return jsonify({'error': 'Invalid input'}), 400

    name = data.get('name')
    if not isinstance(name, str) or not name.strip():
        return jsonify({'error': 'Invalid input'}), 400

    properties = {k: v for k, v in data.items() if k != 'name' and isinstance(v, str)}

    conn = get_db()
    try:
        conn.execute(
            'INSERT INTO products (name, properties) VALUES (?, ?)',
            (name, json.dumps(properties))
        )
        conn.commit()
        return jsonify({'message': 'Product successfully added'}), 201
    except sqlite3.IntegrityError:
        return jsonify({'error': 'Product already exists'}), 400
    finally:
        conn.close()

@app.route('/download', methods=['GET'])
def download_product():
    name = request.args.get('name')
    if not name:
        return jsonify({'error': 'Invalid input'}), 400

    conn = get_db()
    try:
        row = conn.execute('SELECT name, properties FROM products WHERE name = ?', (name,)).fetchone()
        if row is None:
            return jsonify({'error': 'Product not found'}), 404

        product_data = {'name': row['name']}
        props = json.loads(row['properties'])
        product_data.update(props)

        return jsonify({'data': json.dumps(product_data)}), 200
    finally:
        conn.close()

@app.route('/upload', methods=['POST'])
def upload_product():
    body = request.get_json()
    if not body or 'name' not in body or 'data' not in body:
        return jsonify({'error': 'Invalid upload query'}), 400

    name = body.get('name')
    data_str = body.get('data')

    if not isinstance(name, str) or not isinstance(data_str, str):
        return jsonify({'error': 'Invalid upload query'}), 400

    try:
        data = json.loads(data_str)
    except (json.JSONDecodeError, ValueError):
        return jsonify({'error': 'Invalid upload query'}), 400

    if not isinstance(data, dict):
        return jsonify({'error': 'Invalid upload query'}), 400

    properties = {k: v for k, v in data.items() if k != 'name' and isinstance(v, str)}

    conn = get_db()
    try:
        result = conn.execute('SELECT id FROM products WHERE name = ?', (name,)).fetchone()
        if result is None:
            return jsonify({'error': 'Product not found'}), 404

        conn.execute(
            'UPDATE products SET properties = ? WHERE name = ?',
            (json.dumps(properties), name)
        )
        conn.commit()
        return jsonify({'message': 'Product updated'}), 200
    finally:
        conn.close()

@app.route('/search', methods=['GET'])
def search_products():
    query = request.args.get('query')
    if query is None:
        return jsonify({'error': 'Invalid search query'}), 400

    conn = get_db()
    try:
        rows = conn.execute('SELECT name, properties FROM products').fetchall()
        results = []
        query_lower = query.lower()
        for row in rows:
            name = row['name']
            props = json.loads(row['properties'])
            if query_lower in name.lower() or any(query_lower in str(v).lower() for v in props.values()):
                product = {'name': name}
                product.update(props)
                results.append(product)
        return jsonify({'results': results}), 200
    finally:
        conn.close()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)