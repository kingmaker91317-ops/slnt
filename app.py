import os
import sqlite3
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'super-secret-admin-key-123')

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "adminpassword123"

DATABASE = 'users.db'

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                status TEXT DEFAULT 'active',
                created_at TEXT NOT NULL
            )
        ''')
        conn.commit()

init_db()

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

# --- WEB PANEL ROUTES ---

@app.route('/')
def home():
    return redirect(url_for('admin_login'))

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    error = None
    if request.method == 'POST':
        user = request.form.get('username')
        pwd = request.form.get('password')
        if user == ADMIN_USERNAME and pwd == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            error = "Invalid Admin Credentials!"
    return render_template('login.html', error=error)

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin_login'))

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    with get_db() as conn:
        users = conn.execute('SELECT * FROM users ORDER BY id DESC').fetchall()
    return render_template('dashboard.html', users=users)

@app.route('/admin/create_user', methods=['POST'])
@admin_required
def create_user():
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '').strip()
    days = int(request.form.get('days', 30))

    if username and password:
        expires_at = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
        created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        try:
            with get_db() as conn:
                conn.execute(
                    'INSERT INTO users (username, password, expires_at, created_at) VALUES (?, ?, ?, ?)',
                    (username, password, expires_at, created_at)
                )
                conn.commit()
        except sqlite3.IntegrityError:
            pass

    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
@admin_required
def delete_user(user_id):
    with get_db() as conn:
        conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
        conn.commit()
    return redirect(url_for('admin_dashboard'))

# --- API ROUTE FOR APP VERIFICATION ---

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json(silent=True) or request.form
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({"status": "error", "message": "Missing credentials"}), 400

    with get_db() as conn:
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()

    if not user:
        return jsonify({"status": "error", "message": "Account not found"}), 404

    if user['password'] != password:
        return jsonify({"status": "error", "message": "Invalid password"}), 401

    expiry_date = datetime.strptime(user['expires_at'], '%Y-%m-%d %H:%M:%S')
    if datetime.now() > expiry_date:
        return jsonify({"status": "error", "message": "Subscription expired"}), 403

    return jsonify({
        "status": "success",
        "message": "Access Granted",
        "user": {
            "username": user['username'],
            "expires_at": user['expires_at']
        }
    }), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
