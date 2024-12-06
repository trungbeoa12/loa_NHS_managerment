from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3

# Hàm kết nối cơ sở dữ liệu
def get_db_connection():
    try:
        conn = sqlite3.connect('database/orders.db')
        conn.row_factory = sqlite3.Row  # Trả về dữ liệu dạng dictionary
        return conn
    except sqlite3.Error as e:
        print(f"Database connection error: {e}")
        return None

# Khởi tạo ứng dụng Flask
app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Danh sách người dùng mẫu
users = {
    "branch1": {"password": "password123", "role": "Branch User"},
    "admin1": {"password": "admin123", "role": "Regional Admin"},
}

# Route trang chủ: Hiển thị form đăng nhập
@app.route('/')
def home():
    if 'username' in session:
        return redirect(url_for('dashboard'))
    return render_template('login.html')

# Route xử lý đăng nhập
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = users.get(username)
        if user and user['password'] == password:
            session['username'] = username
            session['role'] = user['role']
            return redirect(url_for('dashboard'))

        return "Invalid username or password!", 401

    return render_template('login.html')

# Route Dashboard: Hiển thị danh sách đơn hàng
@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    if conn is None:
        return "Database connection error", 500

    orders = conn.execute('SELECT * FROM orders').fetchall()
    conn.close()

    return render_template('dashboard.html', orders=orders)

# Route xử lý đăng xuất
@app.route('/logout')
def logout():
    session.pop('username', None)
    session.pop('role', None)
    return redirect(url_for('login'))

@app.route('/create', methods=['GET', 'POST'])
def create_order():
    if 'username' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        customer = request.form['customer']
        product = request.form['product']
        status = request.form['status']
        
        conn = get_db_connection()
        if conn is None:
            return "Database connection error", 500

        conn.execute('INSERT INTO orders (customer, product, status) VALUES (?, ?, ?)',
                     (customer, product, status))
        conn.commit()
        conn.close()

        return redirect(url_for('dashboard'))

    return render_template('create_order.html')

@app.route('/edit/<int:order_id>', methods=['GET', 'POST'])
def edit_order(order_id):
    if 'username' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    if conn is None:
        return "Database connection error", 500

    order = conn.execute('SELECT * FROM orders WHERE id = ?', (order_id,)).fetchone()

    if not order:
        return "Order not found", 404

    if request.method == 'POST':
        customer = request.form['customer']
        product = request.form['product']
        status = request.form['status']
        
        conn.execute('UPDATE orders SET customer = ?, product = ?, status = ? WHERE id = ?',
                     (customer, product, status, order_id))
        conn.commit()
        conn.close()

        return redirect(url_for('dashboard'))

    conn.close()
    return render_template('edit_order.html', order=order)

@app.route('/delete/<int:order_id>', methods=['POST'])
def delete_order(order_id):
    if 'username' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    if conn is None:
        return "Database connection error", 500

    conn.execute('DELETE FROM orders WHERE id = ?', (order_id,))
    conn.commit()
    conn.close()

    return redirect(url_for('dashboard'))

# Chạy Flask server
if __name__ == '__main__':
    app.run(debug=True)

