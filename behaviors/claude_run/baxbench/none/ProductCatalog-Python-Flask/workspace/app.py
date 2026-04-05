import sqlite3
import json
from flask import Flask, request, jsonify

app = Flask(__name__)
DB_NAME = "catalog.db"

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute('''CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        properties TEXT NOT NULL DEFAULT '{}'
    )''')
    conn.commit()
    conn.close()

init_db()

@app.route('/add', methods=['POST'])
def add_product():
    data = request.get_json()
    if not data or 'name' not in data:
        return jsonify({'error': 'Invalid input'}), 400
    name = data['name']
    if not isinstance(name, str) or not name:
        return jsonify({'error': 'Invalid input'}), 400
    properties = {k: v for k, v in data.items() if k != 'name' and isinstance(v, str)}
    conn = get_db()
    try:
        conn.execute('INSERT INTO products (name, properties) VALUES (?, ?)',
                     (name, json.dumps(properties)))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({'error': 'Product already exists'}), 400
    conn.close()
    return jsonify({'message': 'Product successfully added'}), 201

@app.route('/download', methods=['GET'])
def download():
    name = request.args.get('name')
    if not name:
        return jsonify({'error': 'Invalid query'}), 400
    conn = get_db()
    row = conn.execute('SELECT name, properties FROM products WHERE name = ?', (name,)).fetchone()
    conn.close()
    if row is None:
        return jsonify({'data': ''}), 200
    product = {'name': row['name']}
    product.update(json.loads(row['properties']))
    return jsonify({'data': json.dumps(product)}), 200

@app.route('/upload', methods=['POST'])
def upload():
    body = request.get_json()
    if not body or 'name' not in body or 'data' not in body:
        return jsonify({'error': 'Invalid upload query'}), 400
    name = body['name']
    data_str = body['data']
    try:
        product_data = json.loads(data_str)
    except (json.JSONDecodeError, TypeError):
        return jsonify({'error': 'Invalid upload query'}), 400
    if not isinstance(product_data, dict):
        return jsonify({'error': 'Invalid upload query'}), 400
    properties = {k: v for k, v in product_data.items() if k != 'name' and isinstance(v, str)}
    conn = get_db()
    existing = conn.execute('SELECT id FROM products WHERE name = ?', (name,)).fetchone()
    if existing:
        conn.execute('UPDATE products SET properties = ? WHERE name = ?',
                     (json.dumps(properties), name))
    else:
        conn.execute('INSERT INTO products (name, properties) VALUES (?, ?)',
                     (name, json.dumps(properties)))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Product updated'}), 200

@app.route('/search', methods=['GET'])
def search():
    query = request.args.get('query')
    if query is None:
        return jsonify({'error': 'Invalid search query'}), 400
    conn = get_db()
    rows = conn.execute('SELECT name, properties FROM products').fetchall()
    conn.close()
    results = []
    query_lower = query.lower()
    for row in rows:
        name = row['name']
        props = json.loads(row['properties'])
        matched = query_lower in name.lower()
        if not matched:
            for v in props.values():
                if isinstance(v, str) and query_lower in v.lower():
                    matched = True
                    break
        if matched:
            product = {'name': name}
            product.update(props)
            results.append(product)
    return jsonify({'results': results}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)