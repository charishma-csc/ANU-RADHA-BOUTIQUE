import os
import sqlite3
from datetime import datetime
from flask import Flask, request, render_template, redirect, session, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)
app.secret_key = 'tailor_shop_super_secret_key'

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

SHOP_PIN = "1234"  # Desired 4-digit PIN

# Helper function to get SQLite connection with dictionary row access
def get_db():
    conn = sqlite3.connect('tailor_shop.db')
    conn.row_factory = sqlite3.Row
    return conn

# Database Initialization
def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    # 1. Customers Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS customer_measurements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT UNIQUE NOT NULL,
            length REAL,
            width REAL,
            back_neck REAL,
            hand_height REAL,
            front_neck REAL
        )
    """)
    
    # 2. Orders Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT NOT NULL,
            length TEXT,
            width TEXT,
            back_neck TEXT,
            hand_height TEXT,
            front_neck TEXT,
            hemming_required TEXT,
            hemming_worker TEXT,
            cloth_photo TEXT,
            design_photo TEXT,
            delivered_photo TEXT,
            order_date DATE
        )
    """)

    # 3. Stock Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stock (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_name TEXT NOT NULL,
            category TEXT,
            quantity INTEGER DEFAULT 0
        )
    """)

    # 4. Order Materials Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS order_materials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER,
            item_id INTEGER,
            required_quantity INTEGER,
            FOREIGN KEY(order_id) REFERENCES orders(id),
            FOREIGN KEY(item_id) REFERENCES stock(id)
        )
    """)

    # 5. Design Gallery Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS design_gallery (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            category TEXT,
            image_url TEXT,
            tags TEXT
        )
    """)
    
    # Seed initial customer data
    cursor.execute("SELECT COUNT(*) FROM customer_measurements")
    if cursor.fetchone()[0] == 0:
        cursor.executemany("""
            INSERT OR IGNORE INTO customer_measurements (customer_name, length, width, back_neck, hand_height, front_neck)
            VALUES (?, ?, ?, ?, ?, ?)
        """, [
            ('Chittakka Chanti', 16.0, 11.5, 9.0, 10.0, 7.0),
            ('Ammulakka Mouni', 15.5, 12.5, 9.0, 10.5, 7.5),
            ('Bujjaiah Garu', 17.5, 13.5, 6.0, 11.0, 6.5),
            ('Chantathaiah Garu', 16.0, 11.5, 8.5, 10.0, 6.0),
            ('UPP', 16.0, 11.0, 10.0, 10.5, 6.0),
            ('Sunala Pedhamma', 15.5, 12.5, 8.5, 10.5, 6.0),
            ('Jeeva', 15.5, 11.0, 6.0, 11.0, 6.0),
            ('Kittaiah Lakshmi', 15.5, 12.5, 10.0, 8.0, 6.0),
            ('Lakshmakka Vadicharla', 17.5, 12.5, 10.5, 10.0, 8.0),
            ('Erammakka', 15.0, 11.0, 8.0, 9.5, 5.0),
            ('Enkayamma Garu', 14.0, 11.5, 7.0, 9.0, 6.0),
            ('Swarnamma Garu', 15.5, 11.5, 8.5, 10.0, 6.5),
            ('Koppaka Papamma Garu', 14.5, 12.0, 7.0, 9.5, 6.0),
            ('Jabbari Seshaiah Garu', 15.5, 11.0, 10.0, 10.0, 7.0),
            ('Ammamma', 14.5, 11.5, 6.5, 9.5, 6.0),
            ('Sudheer Mom', 13.5, 10.8, 8.0, 9.0, 6.0),
            ('Spandhana Sudheer', 15.0, 11.0, 7.5, 7.0, 6.5),
            ('Sharani Bhavani', 13.5, 10.5, 8.0, 8.0, 6.5),
            ('Amma', 15.5, 12.5, 12.0, 11.5, 6.5),
            ('Pushpa Garu', 15.5, 10.0, 10.0, 11.0, 7.5),
            ('Madhavi Garu', 16.5, 13.0, 9.5, 11.0, 6.5),
            ('Jyotsna Madhavi', 17.0, 13.0, 10.0, 9.5, 7.0),
            ('Suri Sai', 15.5, 11.0, 10.0, 7.5, 6.5),
            ('Lakshmakka Latha', 16.5, 12.5, 9.5, 10.0, 7.0),
            ('Chakali Seetha', 14.5, 11.0, 11.5, 11.0, 6.5),
            ('Hema Garu', 17.5, 13.0, 8.0, 10.0, 6.5)
        ])

    # Seed initial stock inventory
    cursor.execute("SELECT COUNT(*) FROM stock")
    if cursor.fetchone()[0] == 0:
        cursor.executemany("""
            INSERT INTO stock (item_name, category, quantity) VALUES (?, ?, ?)
        """, [
            ('Blouse Hooks (A-1 Grade)', 'Fasteners', 100),
            ('Keshar Sewing Thread', 'Threads', 50),
            ('2x2 Rubia Cotton Fabric', 'Lining Material', 20),
            ('Meghana Saree Falls (ART C800)', 'Accessories', 0)
        ])
        
    conn.commit()
    conn.close()

# Initialize Database
init_db()


# ---------------------------------------------------------------------------
# AUTHENTICATION & SECURITY MIDDLEWARE
# ---------------------------------------------------------------------------

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user_pin = request.form.get('pin')
        if user_pin == SHOP_PIN:
            session['authenticated'] = True
            return redirect('/')
        return render_template('login.html', error="చెల్లని PIN (Invalid PIN)")
    return render_template('login.html')

@app.before_request
def require_login():
    public_endpoints = ['login', 'static']
    if request.endpoint not in public_endpoints and not session.get('authenticated'):
        return redirect('/login')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')


# ---------------------------------------------------------------------------
# ROUTES & API ENDPOINTS
# ---------------------------------------------------------------------------

@app.route('/')
def new_order_page():
    conn = get_db()
    cursor = conn.cursor()
    
    # Fetch customers for dropdown
    cursor.execute("SELECT customer_name FROM customer_measurements ORDER BY customer_name ASC")
    customers = cursor.fetchall()
    
    # Fetch stock items dynamically
    cursor.execute("SELECT id, item_name, quantity FROM stock")
    stock_items = cursor.fetchall()
    
    conn.close()
    return render_template('new_order.html', customers=customers, stock_items=stock_items)


@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


@app.route('/api/customers/measurements', methods=['GET'])
def get_customer_measurements():
    customer_name = request.args.get('name')
    if not customer_name:
        return jsonify({"success": False, "message": "Customer name is required"}), 400

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM customer_measurements WHERE customer_name = ?", (customer_name,))
    row = cursor.fetchone()
    conn.close()

    if row:
        measurements = {
            "length": row["length"],
            "width": row["width"],
            "back_neck": row["back_neck"],
            "hand_height": row["hand_height"],
            "front_neck": row["front_neck"]
        }
        return jsonify({"success": True, "measurements": measurements})
    
    return jsonify({"success": True, "measurements": None})


@app.route('/api/orders/history-photos', methods=['GET'])
def get_customer_history_photos():
    customer_name = request.args.get('customer')
    if not customer_name:
        return jsonify({"success": False, "photos": []})

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT delivered_photo 
        FROM orders 
        WHERE customer_name = ? AND delivered_photo IS NOT NULL AND delivered_photo != ''
        ORDER BY id DESC
    """, (customer_name,))
    
    records = cursor.fetchall()
    conn.close()

    photos = [{"delivered_photo": row["delivered_photo"]} for row in records]
    return jsonify({"success": True, "photos": photos})


@app.route('/api/orders/create', methods=['POST'])
def create_order():
    save_mode = request.form.get('save_mode')  # 'order_only' or 'update_profile'
    customer_name = request.form.get('customer_name')
    length = request.form.get('length')
    width = request.form.get('width')
    back_neck = request.form.get('back_neck')
    hand_height = request.form.get('hand_height')
    front_neck = request.form.get('front_neck')

    hemming_required = request.form.get('hemming_required', 'No')
    hemming_worker = request.form.get('hemming_worker', '')

    cloth_photo_path = None
    if 'cloth_photo' in request.files:
        file = request.files['cloth_photo']
        if file and file.filename != '':
            filename = secure_filename(f"cloth_{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}")
            cloth_photo_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(cloth_photo_path)

    design_photo_path = None
    if 'design_photo' in request.files:
        file = request.files['design_photo']
        if file and file.filename != '':
            filename = secure_filename(f"design_{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}")
            design_photo_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(design_photo_path)

    conn = get_db()
    cursor = conn.cursor()

    # 1. Update customer profile defaults if requested
    if save_mode == 'update_profile':
        cursor.execute("""
            INSERT INTO customer_measurements (customer_name, length, width, back_neck, hand_height, front_neck)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(customer_name) DO UPDATE SET
                length=excluded.length,
                width=excluded.width,
                back_neck=excluded.back_neck,
                hand_height=excluded.hand_height,
                front_neck=excluded.front_neck
        """, (customer_name, length, width, back_neck, hand_height, front_neck))

    # 2. Save main order entry
    cursor.execute("""
        INSERT INTO orders (
            customer_name, length, width, back_neck, hand_height, front_neck, 
            hemming_required, hemming_worker, cloth_photo, design_photo, order_date
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, DATE('now'))
    """, (
        customer_name, length, width, back_neck, hand_height, front_neck, 
        hemming_required, hemming_worker, cloth_photo_path, design_photo_path
    ))
    order_id = cursor.lastrowid

    # 3. Save selected inventory materials & deduct stock
    material_id = request.form.get('material_id')
    material_qty = request.form.get('material_qty')

    if material_id and material_qty:
        try:
            qty_val = int(material_qty)
            cursor.execute("""
                INSERT INTO order_materials (order_id, item_id, required_quantity)
                VALUES (?, ?, ?)
            """, (order_id, material_id, qty_val))
            
            cursor.execute("""
                UPDATE stock SET quantity = quantity - ? WHERE id = ?
            """, (qty_val, material_id))
        except ValueError:
            pass

    conn.commit()
    conn.close()

    return redirect('/')


# ---------------------------------------------------------------------------
# AUTOMATED DATABASE BACKUP SYSTEM
# ---------------------------------------------------------------------------

def run_database_backup():
    if not os.path.exists('backups'):
        os.makedirs('backups')
        
    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    backup_filename = f"backups/tailor_shop_backup_{timestamp}.db"
    
    src_conn = sqlite3.connect('tailor_shop.db')
    dest_conn = sqlite3.connect(backup_filename)
    
    with dest_conn:
        src_conn.backup(dest_conn)
        
    src_conn.close()
    dest_conn.close()

scheduler = BackgroundScheduler()
scheduler.add_job(func=run_database_backup, trigger="cron", hour=0, minute=0)
scheduler.start()


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)