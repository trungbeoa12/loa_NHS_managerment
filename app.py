from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
from datetime import datetime, timedelta

# Hàm kết nối cơ sở dữ liệu
import os

def get_db_connection():
    db_path = os.path.join(os.path.dirname(__file__), 'database', 'orders.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

# Khởi tạo ứng dụng Flask
app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Bạn nên sử dụng một khóa bí mật mạnh hơn và bảo mật

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
    status_filter = request.args.get('status', None)

    # Lấy thông tin trang và số bản ghi mỗi trang từ query string
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)

    # Xây dựng truy vấn cơ bản
    base_query = """SELECT id, customer, product, status, branch_code, created_at, updated_at,
                           deadline, delivery_time, sla_status, customer_contact
                    FROM orders"""
    params = []

    conditions = []

    if session['role'] == "Branch User":
        # Branch User chỉ xem đơn hàng thuộc branch_code của họ
        conditions.append("branch_code = ?")
        params.append(session['branch_code'])

        if status_filter:
            conditions.append("status = ?")
            params.append(status_filter)

    elif session['role'] == "Admin":
        # Admin xem tất cả đơn hàng
        if status_filter:
            conditions.append("status = ?")
            params.append(status_filter)

    else:
        # Role không hợp lệ
        conn.close()
        return redirect(url_for('login'))

    if conditions:
        base_query += " WHERE " + " AND ".join(conditions)

    # Tạo truy vấn COUNT riêng biệt
    count_query = "SELECT COUNT(*) as count FROM orders"
    if conditions:
        count_query += " WHERE " + " AND ".join(conditions)

    # Thực hiện truy vấn COUNT
    try:
        result = conn.execute(count_query, tuple(params)).fetchone()
        total_count = result['count'] if result and 'count' in result else 0
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        total_count = 0

    # Tính toán offset
    offset = (page - 1) * per_page

    # Thêm LIMIT và OFFSET vào truy vấn để lấy dữ liệu cho trang hiện tại
    paginated_query = base_query + " LIMIT ? OFFSET ?"
    params_paginated = params + [per_page, offset]

    try:
        orders = conn.execute(paginated_query, tuple(params_paginated)).fetchall()
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        orders = []
    finally:
        conn.close()

    # Tính tổng số trang
    total_pages = (total_count + per_page - 1) // per_page

    return render_template(
        'dashboard.html',
        orders=orders,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
        total_count=total_count,
        status_filter=status_filter,
        role=session['role']  # để hiển thị role nếu cần
    )

# Route xử lý đăng xuất
@app.route('/logout')
def logout():
    session.clear()  # Xóa toàn bộ session khi đăng xuất
    return redirect(url_for('login'))

# Route xử lý tạo đơn hàng mới
@app.route('/create', methods=['GET', 'POST'])
def create_order():
    if 'username' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        customer = request.form.get('customer')
        product = request.form.get('product')
        status = request.form.get('status')
        customer_contact = request.form.get('customer_contact')
        sla_status = request.form.get('sla_status')
        branch_code = session.get('branch_code', None)
        created_by = session['username']
        created_at = datetime.now()

        # Tính Deadline là ngày hiện tại + 5 ngày
        deadline = created_at + timedelta(days=5)

        # Xác định SLA Status dựa trên status khi tạo đơn hàng
        # Bạn có thể điều chỉnh logic này theo yêu cầu cụ thể
        if status == 'Delivered':
            sla_status = 'On Time'  # Hoặc bất kỳ logic nào khác
        else:
            sla_status = 'Pending'

        # Chuyển định dạng created_at và deadline cho SQLite
        created_at_str = created_at.strftime('%Y-%m-%d %H:%M:%S')
        deadline_str = deadline.strftime('%Y-%m-%d %H:%M:%S')

        conn = get_db_connection()
        try:
            conn.execute('''
                INSERT INTO orders (
                    customer, product, status, branch_code, created_by, created_at, 
                    customer_contact, deadline, delivery_time, sla_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                customer, product, status, branch_code, created_by, created_at_str,
                customer_contact, deadline_str, None, sla_status
            ))
            conn.commit()
        except sqlite3.Error as e:
            # Xử lý lỗi, ví dụ: ghi log hoặc thông báo cho người dùng
            print(f"Database error: {e}")
            return "An error occurred while creating the order.", 500
        finally:
            conn.close()

        return redirect(url_for('dashboard'))

    return render_template('create_order.html')

# Route sửa đơn hàng
@app.route('/edit/<int:order_id>', methods=['GET', 'POST'])
def edit_order(order_id):
    if 'username' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    order = conn.execute('SELECT * FROM orders WHERE id = ?', (order_id,)).fetchone()

    if not order:
        conn.close()
        return "Order not found", 404

    # Kiểm tra quyền của Branch User
    if session['role'] == 'Branch User':
        # Nếu trạng thái không phải Pending hoặc Delivered, chặn sửa
        if order['status'] not in ['Pending', 'Delivered']:
            conn.close()
            return "Bạn không thể sửa đơn hàng này vì trạng thái không phù hợp", 403

        # Kiểm tra xem có đúng chi nhánh không (nếu cần)
        if 'branch_code' in session and order['branch_code'] != session['branch_code']:
            conn.close()
            return "Bạn không có quyền sửa đơn hàng này", 403

    # Nếu là Admin hoặc Branch User đủ điều kiện (order còn ở Pending hoặc Delivered), cho phép sửa
    if request.method == 'POST':
        customer = request.form.get('customer')
        product = request.form.get('product')
        status = request.form.get('status')
        customer_contact = request.form.get('customer_contact')
        sla_status = request.form.get('sla_status')
        delivery_time = request.form.get('delivery_time')  # Có thể để trống

        updated_at = datetime.now()

        # Tính toán Deadline không thay đổi khi chỉnh sửa
        deadline_str = order['deadline']

        # Nếu status được cập nhật thành Delivered, yêu cầu nhập Delivery Time
        if status == 'Delivered':
            if not delivery_time:
                conn.close()
                return "Delivery Time is required when status is Delivered.", 400
            try:
                # Chuyển định dạng từ 'YYYY-MM-DDTHH:MM' sang 'YYYY-MM-DD HH:MM:SS'
                delivery_time_dt = datetime.strptime(delivery_time, '%Y-%m-%dT%H:%M')
                delivery_time_str = delivery_time_dt.strftime('%Y-%m-%d %H:%M:%S')
            except ValueError:
                conn.close()
                return "Invalid delivery time format.", 400

            # Tính SLA Status dựa trên chênh lệch giữa Delivery Time và Updated At
            sla_difference = (delivery_time_dt - updated_at).days
            if sla_difference <= 5:
                sla_status = 'On Time'
            else:
                sla_status = 'Delayed'
        else:
            delivery_time_str = order['delivery_time']  # Không thay đổi
            sla_status = 'Pending'  # Hoặc theo logic khác

        # Nếu Branch User không được phép đổi status, giữ nguyên status cũ
        if session['role'] == 'Branch User':
            status = order['status']

        try:
            conn.execute('''
                UPDATE orders 
                SET customer = ?, product = ?, status = ?, customer_contact = ?, 
                    delivery_time = ?, sla_status = ?, updated_at = ?
                WHERE id = ?
            ''', (
                customer, product, status, customer_contact,
                delivery_time_str, sla_status, updated_at.strftime('%Y-%m-%d %H:%M:%S'), order_id
            ))
            conn.commit()
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            conn.close()
            return "An error occurred while updating the order.", 500
        finally:
            conn.close()

        return redirect(url_for('dashboard'))

    conn.close()
    return render_template('edit_order.html', order=order)

# Route xác nhận đơn hàng
@app.route('/confirm/<int:order_id>', methods=['POST'])
def confirm_order(order_id):
    if 'username' not in session or session['role'] != 'Admin':
        return redirect(url_for('login'))

    conn = get_db_connection()
    try:
        updated_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        conn.execute('UPDATE orders SET status = "confirmed", updated_at = ? WHERE id = ?', 
                     (updated_at, order_id))
        conn.commit()
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        conn.close()
        return "An error occurred while confirming the order.", 500
    finally:
        conn.close()

    return redirect(url_for('dashboard'))

# Route xóa đơn hàng
@app.route('/delete/<int:order_id>', methods=['POST'])
def delete_order(order_id):
    if 'username' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    order = conn.execute('SELECT * FROM orders WHERE id = ?', (order_id,)).fetchone()

    if not order:
        conn.close()
        return "Order not found", 404

    # Nếu là Branch User và trạng thái không phải Pending thì không cho xóa
    if session['role'] == 'Branch User' and order['status'] != 'Pending':
        conn.close()
        return "Bạn không được phép xóa đơn hàng này vì trạng thái không phải Pending", 403

    # Nếu qua được điều kiện trên thì cho xóa
    try:
        conn.execute('DELETE FROM orders WHERE id = ?', (order_id,))
        conn.commit()
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        conn.close()
        return "An error occurred while deleting the order.", 500
    finally:
        conn.close()

    return redirect(url_for('dashboard'))

# Route xem đơn hàng theo chi nhánh
@app.route('/branch_orders', methods=['GET'])
def branch_orders():
    if 'username' not in session or session['role'] != 'Branch User':
        return redirect(url_for('login'))

    conn = get_db_connection()
    status_filter = request.args.get('status', None)

    if status_filter:
        orders = conn.execute(
            'SELECT * FROM orders WHERE branch_code = ? AND status = ?',
            (session['branch_code'], status_filter)
        ).fetchall()
    else:
        orders = conn.execute(
            'SELECT * FROM orders WHERE branch_code = ?',
            (session['branch_code'],)
        ).fetchall()

    conn.close()
    return render_template('branch_orders.html', orders=orders)

# Route xử lý hành động hàng loạt
@app.route('/bulk_action', methods=['POST'])
def bulk_action():
    if 'username' not in session or session['role'] != 'Admin':
        return redirect(url_for('login'))

    order_ids = request.form.getlist('order_ids[]')
    bulk_action = request.form.get('bulk_action')

    if not order_ids:
        return "No orders selected", 400

    conn = get_db_connection()

    try:
        updated_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        if bulk_action == 'update_status_pending':
            conn.executemany('UPDATE orders SET status = "Pending", updated_at = ? WHERE id = ?', 
                            [(updated_at, order_id) for order_id in order_ids])
        elif bulk_action == 'update_status_confirmed':
            conn.executemany('UPDATE orders SET status = "confirmed", updated_at = ? WHERE id = ?', 
                            [(updated_at, order_id) for order_id in order_ids])
        elif bulk_action == 'update_status_completed':
            conn.executemany('UPDATE orders SET status = "Completed", updated_at = ? WHERE id = ?', 
                            [(updated_at, order_id) for order_id in order_ids])
        elif bulk_action == 'update_status_danggiao':
            conn.executemany('UPDATE orders SET status = "Đang giao", updated_at = ? WHERE id = ?', 
                            [(updated_at, order_id) for order_id in order_ids])
        elif bulk_action == 'update_status_doitra':
            conn.executemany('UPDATE orders SET status = "Đổi trả", updated_at = ? WHERE id = ?', 
                            [(updated_at, order_id) for order_id in order_ids])
        else:
            conn.close()
            return "Invalid action", 400

        conn.commit()
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        conn.close()
        return "An error occurred while performing bulk action.", 500
    finally:
        conn.close()

    return redirect(url_for('dashboard'))

# Chạy Flask server
if __name__ == '__main__':
    app.run(debug=True)

