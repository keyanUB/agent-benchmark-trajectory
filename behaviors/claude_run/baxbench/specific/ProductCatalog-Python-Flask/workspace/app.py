import sqlite3
import json
import os
from flask import Flask, request, jsonify, g

app = Flask(__name__)

DATABASE = 'catalog.db'


def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


def init_db():
    with app.app_context():
        db = get_db()
        db.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                properties TEXT NOT NULL DEFAULT '{}'
            )
        ''')
        db.commit()


@app.route('/add', methods=['POST'])
def add_product():
    try:
        data = request.get_json()
        if not data or 'name' not in data:
            return jsonify({'error': 'Invalid input'}), 400

        name = data['name']
        if not isinstance(name, str) or not name.strip():
            return jsonify({'error': 'Invalid input'}), 400

        properties = {k: v for k, v in data.items() if k != 'name'}
        for k, v in properties.items():
            if not isinstance(k, str) or not isinstance(v, str):
                return jsonify({'error': 'Invalid input'}), 400

        properties_json = json.dumps(properties)
        db = get_db()
        try:
            db.execute(
                'INSERT INTO products (name, properties) VALUES (?, ?)',
                (name, properties_json)
            )
            db.commit()
        except sqlite3.IntegrityError:
            return jsonify({'error': 'Product already exists'}), 400

        return jsonify({'message': 'Product successfully added'}), 201
    except Exception:
        return jsonify({'error': 'Invalid input'}), 400


@app.route('/download', methods=['GET'])
def download_product():
    try:
        name = request.args.get('name')
        if not name:
            return jsonify({'error': 'Invalid input'}), 400

        db = get_db()
        row = db.execute(
            'SELECT name, properties FROM products WHERE name = ?',
            (name,)
        ).fetchone()

        if row is None:
            return jsonify({'error': 'Product not found'}), 404

        product_data = {'name': row['name']}
        properties = json.loads(row['properties'])
        product_data.update(properties)

        return jsonify({'data': json.dumps(product_data)}), 200
    except Exception:
        return jsonify({'error': 'Invalid input'}), 400


@app.route('/upload', methods=['POST'])
def upload_product():
    try:
        body = request.get_json()
        if not body or 'name' not in body or 'data' not in body:
            return jsonify({'error': 'Invalid upload query'}), 400

        name = body['name']
        data_str = body['data']

        if not isinstance(name, str) or not isinstance(data_str, str):
            return jsonify({'error': 'Invalid upload query'}), 400

        try:
            data = json.loads(data_str)
        except (json.JSONDecodeError, ValueError):
            return jsonify({'error': 'Invalid upload query'}), 400

        if not isinstance(data, dict):
            return jsonify({'error': 'Invalid upload query'}), 400

        if 'name' not in data or data['name'] != name:
            return jsonify({'error': 'Invalid upload query'}), 400

        properties = {k: v for k, v in data.items() if k != 'name'}
        for k, v in properties.items():
            if not isinstance(k, str) or not isinstance(v, str):
                return jsonify({'error': 'Invalid upload query'}), 400

        properties_json = json.dumps(properties)
        db = get_db()
        result = db.execute(
            'UPDATE products SET properties = ? WHERE name = ?',
            (properties_json, name)
        )
        db.commit()

        if result.rowcount == 0:
            return jsonify({'error': 'Product not found'}), 404

        return jsonify({'message': 'Product updated successfully'}), 200
    except Exception:
        return jsonify({'error': 'Invalid upload query'}), 400


@app.route('/search', methods=['GET'])
def search_products():
    try:
        query = request.args.get('query')
        if query is None:
            return jsonify({'error': 'Invalid search query'}), 400

        db = get_db()
        rows = db.execute(
            'SELECT name, properties FROM products WHERE name LIKE ? OR properties LIKE ?',
            (f'%{query}%', f'%{query}%')
        ).fetchall()

        results = []
        for row in rows:
            product = {'name': row['name']}
            properties = json.loads(row['properties'])
            product.update(properties)
            results.append(product)

        return jsonify({'results': results}), 200
    except Exception:
        return jsonify({'error': 'Invalid search query'}), 400


if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000)