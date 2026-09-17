import os
import sqlite3
import random
import string
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_file, abort, flash
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'super-secret-admin-key-123')

ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'adminpassword123')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, 'users.db')
SERVER_DOMAIN = os.environ.get('SERVER_DOMAIN', 'slnt-0w1p.onrender.com')
APK_FILE_PATH = os.path.join(BASE_DIR, 'sc_update.apk')


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
                created_at TEXT NOT NULL,
                hwid TEXT DEFAULT NULL,
                mode TEXT DEFAULT 'safe'
            )
        ''')
        cursor = conn.execute("PRAGMA table_info(users)")
        columns = [row['name'] for row in cursor.fetchall()]
        if 'hwid' not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN hwid TEXT DEFAULT NULL")
        if 'mode' not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN mode TEXT DEFAULT 'safe'")
        conn.commit()


init_db()


def parse_expiry_date(date_str):
    if not date_str:
        return None
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%Y-%m-%dT%H:%M:%S'):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            pass
    return None


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
        user = request.form.get('username', '').strip()
        pwd = request.form.get('password', '').strip()
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


@app.route('/admin/create_user', methods=['GET', 'POST'])
@admin_required
def create_user():
    if request.method == 'GET':
        return redirect(url_for('admin_dashboard'))

    username = request.form.get('username', '').strip()
    password = request.form.get('password', '').strip()

    try:
        days = int(request.form.get('days', 30))
    except (ValueError, TypeError):
        days = 30

    mode = request.form.get('mode', 'safe').strip()
    if mode not in ('brutal', 'safe'):
        mode = 'safe'

    if username and password:
        expires_at = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
        created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        try:
            with get_db() as conn:
                conn.execute(
                    'INSERT INTO users (username, password, expires_at, status, created_at, mode) VALUES (?, ?, ?, ?, ?, ?)',
                    (username, password, expires_at, 'active', created_at, mode)
                )
                conn.commit()
        except sqlite3.IntegrityError:
            flash("Username already exists!")

    return redirect(url_for('admin_dashboard'))


@app.route('/admin/generate_keys', methods=['POST'])
@admin_required
def generate_keys():
    try:
        days = int(request.form.get('days', 30))
        count = int(request.form.get('count', 1))
    except (ValueError, TypeError):
        days, count = 30, 1

    created_count = 0
    expires_at = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    mode = request.form.get('mode', 'safe').strip()
    if mode not in ('brutal', 'safe'):
        mode = 'safe'

    with get_db() as conn:
        for _ in range(count):
            rnd = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            username = f"KEY-{rnd}"
            password = rnd[:6]
            try:
                conn.execute(
                    'INSERT INTO users (username, password, expires_at, status, created_at, mode) VALUES (?, ?, ?, ?, ?, ?)',
                    (username, password, expires_at, 'active', created_at, mode)
                )
                created_count += 1
            except sqlite3.IntegrityError:
                pass
        conn.commit()

    flash(f"Successfully generated {created_count} keys ({mode} mode)!")
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/reset_hwid/<int:user_id>', methods=['POST'])
@admin_required
def reset_hwid(user_id):
    with get_db() as conn:
        conn.execute('UPDATE users SET hwid = NULL WHERE id = ?', (user_id,))
        conn.commit()
    flash("HWID reset successfully!")
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/toggle_status/<int:user_id>', methods=['POST'])
@admin_required
def toggle_status(user_id):
    with get_db() as conn:
        user = conn.execute('SELECT status FROM users WHERE id = ?', (user_id,)).fetchone()
        if user:
            new_status = 'banned' if user['status'] == 'active' else 'active'
            conn.execute('UPDATE users SET status = ? WHERE id = ?', (new_status, user_id))
            conn.commit()
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/set_mode/<int:user_id>', methods=['POST'])
@admin_required
def set_mode(user_id):
    mode = request.form.get('mode', 'safe').strip()
    if mode not in ('brutal', 'safe'):
        mode = 'safe'
    with get_db() as conn:
        conn.execute('UPDATE users SET mode = ? WHERE id = ?', (mode, user_id))
        conn.commit()
    flash(f"Mode changed to {mode.upper()} for user #{user_id}")
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/delete_user/<int:user_id>', methods=['GET', 'POST'])
@admin_required
def delete_user(user_id):
    if request.method == 'POST':
        with get_db() as conn:
            conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
            conn.commit()
    return redirect(url_for('admin_dashboard'))


# --- API ROUTES FOR APP VERIFICATION ---

@app.route('/api/auth/login.php', methods=['POST', 'GET'])
@app.route('/api/auth/login', methods=['POST', 'GET'])
@app.route('/api/login', methods=['POST', 'GET'])
def api_login():
    data = request.get_json(silent=True) or request.form or request.args or {}
    username = (data.get('u') or data.get('username') or '').strip()
    password = (data.get('p') or data.get('password') or '').strip()
    hwid = (data.get('hwid') or data.get('device_id') or data.get('d') or '').strip()

    if not username or not password:
        return jsonify({
            "status": "error",
            "r": 0,
            "msg": "Missing credentials",
            "message": "Missing credentials"
        }), 400

    with get_db() as conn:
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()

    if not user:
        return jsonify({
            "status": "error",
            "r": 0,
            "msg": "Account not found",
            "message": "Account not found"
        }), 404

    if user['password'] != password:
        return jsonify({
            "status": "error",
            "r": 0,
            "msg": "Invalid password",
            "message": "Invalid password"
        }), 401

    if user['status'] != 'active':
        return jsonify({
            "status": "error",
            "r": 0,
            "msg": f"Account is {user['status']}",
            "message": f"Account is {user['status']}"
        }), 403

    # HWID Handling
    user_keys = user.keys()
    user_hwid = user['hwid'] if 'hwid' in user_keys else None
    if hwid:
        if not user_hwid:
            with get_db() as conn:
                conn.execute('UPDATE users SET hwid = ? WHERE id = ?', (hwid, user['id']))
                conn.commit()
            user_hwid = hwid
        elif user_hwid != hwid:
            return jsonify({
                "status": "error",
                "r": 0,
                "msg": "HWID Mismatch! Device limit reached.",
                "message": "HWID Mismatch! Device limit reached."
            }), 403

    expiry_date = parse_expiry_date(user['expires_at'])
    if not expiry_date or datetime.now() > expiry_date:
        return jsonify({
            "status": "error",
            "r": 0,
            "msg": "Subscription expired",
            "message": "Subscription expired",
            "subscription": {
                "active": False,
                "level": "free",
                "expires": user['expires_at'],
                "trial": False
            }
        }), 403

    user_mode = user['mode'] if 'mode' in user.keys() else 'safe'
    if user_mode not in ('brutal', 'safe'):
        user_mode = 'safe'

    return jsonify({
        "status": "success",
        "r": 1,
        "msg": "Access Granted",
        "message": "Access Granted",
        "username": user['username'],
        "hwid": user_hwid or hwid or "",
        "seller": "SilentCheats",
        "theme": user_mode,
        "mode": user_mode,
        "subscription": {
            "active": True,
            "level": "vip",
            "expires": user['expires_at'],
            "expires_at": user['expires_at'],
            "trial": False
        },
        "expires": user['expires_at'],
        "expires_at": user['expires_at'],
        "user": {
            "username": user['username'],
            "expires": user['expires_at'],
            "expires_at": user['expires_at'],
            "hwid": user_hwid or hwid or "",
            "mode": user_mode
        },
        "server": f"https://{SERVER_DOMAIN}"
    }), 200


@app.route('/api/auth/reset_hwid', methods=['POST', 'GET'])
def api_reset_hwid():
    data = request.get_json(silent=True) or request.form or request.args or {}
    username = (data.get('u') or data.get('username') or '').strip()
    password = (data.get('p') or data.get('password') or '').strip()

    if not username or not password:
        return jsonify({"status": "error", "r": 0, "msg": "Missing credentials"}), 400

    with get_db() as conn:
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()

    if not user or user['password'] != password:
        return jsonify({"status": "error", "r": 0, "msg": "Invalid credentials"}), 401

    with get_db() as conn:
        conn.execute('UPDATE users SET hwid = NULL WHERE id = ?', (user['id'],))
        conn.commit()

    return jsonify({"status": "success", "r": 1, "msg": "HWID reset successfully!"}), 200


@app.route('/api/config', methods=['GET'])
def api_config():
    return jsonify({
        "status": "success",
        "r": 1,
        "app_name": "SC Mod Menu",
        "version": "30.0",
        "min_version": "1.0.0",
        "maintenance": False,
        "maintenance_message": "Server is online.",
        "notice": "Welcome to SC Mod Menu! Play safe.",
        "update_url": f"https://{SERVER_DOMAIN}/sc_update.apk"
    }), 200


@app.route('/api/features', methods=['GET'])
def api_features():
    return jsonify({
        "status": "success",
        "r": 1,
        "features": {
            "esp": True,
            "esp_box": True,
            "esp_line": True,
            "esp_health": True,
            "aimbot": True,
            "memory_hacks": True,
            "root_mode": True
        },
        "safe_status": "SAFE"
    }), 200


# --- APK DOWNLOAD & UPDATE ROUTES ---

@app.route('/sc_update.apk', methods=['GET'])
def download_apk():
    if not os.path.exists(APK_FILE_PATH):
        abort(404)
    return send_file(APK_FILE_PATH, as_attachment=True, download_name='sc_update.apk')


@app.route('/api/update', methods=['GET'])
def api_update():
    return jsonify({
        "status": "success",
        "update_url": f"https://{SERVER_DOMAIN}/sc_update.apk",
        "version": "1.0.0"
    }), 200


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
