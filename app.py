from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3

# Hàm kết nối cơ sở dữ liệu
def get_db_connection():
    conn = sqlite3.connect('/home/trungdt2/Thuchanh/website-datloa/database/orders.db')
    conn.row_factory = sqlite3.Row  # Trả về dữ liệu dạng dictionary
    return conn


# Khởi tạo ứng dụng Flask
app = Flask(__name__)
app.secret_key = 'your_secret_key'

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

        conn = get_db_connection()
        
        # Kiểm tra trong bảng branch_users
        branch_user = conn.execute(
            'SELECT * FROM branch_users WHERE branch_code = ? AND password = ?',
            (username, password)
        ).fetchone()

        # Kiểm tra trong bảng admin_users
        admin_user = conn.execute(
            'SELECT * FROM admin_users WHERE username = ? AND password = ?',
            (username, password)
        ).fetchone()

        conn.close()

        if branch_user:
            session['username'] = username
            session['role'] = 'Branch User'
            session['branch_code'] = branch_user['branch_code']
            return redirect(url_for('dashboard'))
        elif admin_user:
            session['username'] = username
            session['role'] = 'Admin'
            session['branch_code'] = None  # Admin không có branch_code
            return redirect(url_for('dashboard'))
        else:
            return "Invalid username or password!", 401

    return render_template('login.html')



# Route Dashboard: Hiển thị danh sách đơn hàng
@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    if session['role'] == "Branch User":
        # Lọc đơn hàng theo branch_code cho Branch User
        orders = conn.execute('SELECT * FROM orders WHERE branch_code = ?', (session['branch_code'],)).fetchall()
    elif session['role'] == "Admin":
        # Admin có thể xem tất cả đơn hàng
        orders = conn.execute('SELECT * FROM orders').fetchall()
    conn.close()

    return render_template('dashboard.html', orders=orders)


# Route xử lý đăng xuất
@app.route('/logout')
def logout():
    session.clear()  # Xóa toàn bộ session khi đăng xuất
    return redirect(url_for('login'))

@app.route('/create', methods=['GET', 'POST'])
def create_order():
    if 'username' not in session or 'branch_code' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        customer = request.form['customer']
        product = request.form['product']
        status = request.form['status']
        branch_code = session['branch_code']
        
        conn = get_db_connection()
        try:
            conn.execute('INSERT INTO orders (customer, product, status, branch_code) VALUES (?, ?, ?, ?)',
                        (customer, product, status, branch_code))
            conn.commit()
        finally:
            conn.close()

        return redirect(url_for('dashboard'))

    return render_template('create_order.html')

@app.route('/edit/<int:order_id>', methods=['GET', 'POST'])
def edit_order(order_id):
    if 'username' not in session or 'branch_code' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    try:
        order = conn.execute('SELECT * FROM orders WHERE id = ?', (order_id,)).fetchone()

        if not order:
            return "Order not found", 404

        # Kiểm tra quyền sửa
        if session['role'] == 'Branch User' and order['branch_code'] != session['branch_code']:
            return "You do not have permission to edit this order", 403

        if request.method == 'POST':
            customer = request.form['customer']
            product = request.form['product']
            status = request.form['status']
            
            conn.execute('UPDATE orders SET customer = ?, product = ?, status = ? WHERE id = ?',
                        (customer, product, status, order_id))
            conn.commit()
            return redirect(url_for('dashboard'))
    finally:
        conn.close()

    return render_template('edit_order.html', order=order)

@app.route('/delete/<int:order_id>', methods=['POST'])
def delete_order(order_id):
    if 'username' not in session or 'branch_code' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    try:
        order = conn.execute('SELECT * FROM orders WHERE id = ?', (order_id,)).fetchone()

        if not order:
            return "Order not found", 404

        # Kiểm tra quyền xóa
        if session['role'] == 'Branch User' and order['branch_code'] != session['branch_code']:
            return "You do not have permission to delete this order", 403

        conn.execute('DELETE FROM orders WHERE id = ?', (order_id,))
        conn.commit()
    finally:
        conn.close()

    return redirect(url_for('dashboard'))

# Chạy Flask server
if __name__ == '__main__':
    app.run(debug=True)

