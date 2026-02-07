"""
REST API for PiServer Attendance System
Provides endpoints for external integrations
"""

from flask import Blueprint, jsonify, request, g
from functools import wraps
from datetime import datetime, date, timedelta
import secrets

from db import get_conn
from authz import login_required

bp = Blueprint("api", __name__, url_prefix="/api/v1")


# =============================================================================
# API Key Authentication
# =============================================================================

def api_key_required(f):
    """Decorator to require API key authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        
        if not api_key:
            return jsonify({"error": "API key required"}), 401
        
        conn = get_conn()
        cur = conn.cursor()
        
        # Check if API key exists and is active
        key_data = cur.execute(
            "SELECT * FROM api_keys WHERE key = ? AND active = 1",
            (api_key,)
        ).fetchone()
        
        conn.close()
        
        if not key_data:
            return jsonify({"error": "Invalid API key"}), 401
        
        # Store key info in g for use in endpoint
        g.api_key = dict(key_data)
        
        return f(*args, **kwargs)
    return decorated_function


# =============================================================================
# API Endpoints
# =============================================================================

@bp.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    })


@bp.route("/users", methods=["GET"])
@api_key_required
def get_users():
    """Get all users"""
    conn = get_conn()
    cur = conn.cursor()
    
    users = cur.execute("""
        SELECT 
            employee_id,
            name,
            email,
            is_active,
            schedule_template_id
        FROM users
        WHERE is_active = 1
        ORDER BY name
    """).fetchall()
    
    conn.close()
    
    return jsonify({
        "users": [dict(u) for u in users],
        "count": len(users)
    })


@bp.route("/users/<employee_id>", methods=["GET"])
@api_key_required
def get_user(employee_id):
    """Get specific user details"""
    conn = get_conn()
    cur = conn.cursor()
    
    user = cur.execute("""
        SELECT 
            employee_id,
            name,
            email,
            is_active,
            schedule_template_id
        FROM users
        WHERE employee_id = ?
    """, (employee_id,)).fetchone()
    
    if not user:
        conn.close()
        return jsonify({"error": "User not found"}), 404
    
    # Get user's attendance for today
    today = date.today().isoformat()
    events = cur.execute("""
        SELECT timestamp, direction
        FROM events
        WHERE employee_id = ? AND DATE(timestamp) = ?
        ORDER BY timestamp
    """, (employee_id, today)).fetchall()
    
    conn.close()
    
    return jsonify({
        "user": dict(user),
        "today_events": [dict(e) for e in events]
    })


@bp.route("/attendance/today", methods=["GET"])
@api_key_required
def get_today_attendance():
    """Get today's attendance summary"""
    today = date.today().isoformat()
    
    conn = get_conn()
    cur = conn.cursor()
    
    # Get total employees
    total = cur.execute("SELECT COUNT(*) as count FROM users WHERE is_active = 1").fetchone()["count"]
    
    # Get employees who clocked in today
    attended = cur.execute("""
        SELECT DISTINCT employee_id
        FROM events
        WHERE DATE(timestamp) = ?
    """, (today,)).fetchall()
    
    attended_count = len(attended)
    
    # Get detailed attendance
    attendance_data = cur.execute("""
        SELECT
            e.employee_id,
            u.name,
            MIN(e.timestamp) as first_in,
            MAX(e.timestamp) as last_out,
            COUNT(*) as event_count
        FROM events e
        LEFT JOIN users u ON u.employee_id = e.employee_id
        WHERE DATE(e.timestamp) = ?
        GROUP BY e.employee_id
        ORDER BY u.name
    """, (today,)).fetchall()
    
    conn.close()
    
    return jsonify({
        "date": today,
        "summary": {
            "total_employees": total,
            "present": attended_count,
            "absent": total - attended_count,
            "attendance_rate": round((attended_count / total * 100), 2) if total > 0 else 0
        },
        "attendance": [dict(a) for a in attendance_data]
    })


@bp.route("/attendance/range", methods=["GET"])
@api_key_required
def get_attendance_range():
    """Get attendance for a date range"""
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    if not start_date or not end_date:
        return jsonify({"error": "start_date and end_date parameters required"}), 400
    
    try:
        # Validate dates
        datetime.fromisoformat(start_date)
        datetime.fromisoformat(end_date)
    except ValueError:
        return jsonify({"error": "Invalid date format. Use YYYY-MM-DD"}), 400
    
    conn = get_conn()
    cur = conn.cursor()
    
    attendance_data = cur.execute("""
        SELECT
            DATE(e.timestamp) as date,
            e.employee_id,
            u.name,
            MIN(e.timestamp) as first_in,
            MAX(e.timestamp) as last_out,
            COUNT(*) as event_count
        FROM events e
        LEFT JOIN users u ON u.employee_id = e.employee_id
        WHERE DATE(e.timestamp) BETWEEN ? AND ?
        GROUP BY date, e.employee_id
        ORDER BY date, u.name
    """, (start_date, end_date)).fetchall()
    
    conn.close()
    
    return jsonify({
        "start_date": start_date,
        "end_date": end_date,
        "attendance": [dict(a) for a in attendance_data],
        "count": len(attendance_data)
    })


@bp.route("/events", methods=["POST"])
@api_key_required
def create_event():
    """Create a new attendance event (clock in/out)"""
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "JSON body required"}), 400
    
    required_fields = ['employee_id', 'timestamp', 'direction']
    for field in required_fields:
        if field not in data:
            return jsonify({"error": f"Missing required field: {field}"}), 400
    
    # Validate direction
    if data['direction'] not in ['in', 'out']:
        return jsonify({"error": "direction must be 'in' or 'out'"}), 400
    
    # Validate timestamp
    try:
        datetime.fromisoformat(data['timestamp'])
    except ValueError:
        return jsonify({"error": "Invalid timestamp format"}), 400
    
    conn = get_conn()
    cur = conn.cursor()
    
    # Check if user exists
    user = cur.execute(
        "SELECT name FROM users WHERE employee_id = ?",
        (data['employee_id'],)
    ).fetchone()
    
    if not user:
        conn.close()
        return jsonify({"error": "User not found"}), 404
    
    # Insert event
    try:
        cur.execute("""
            INSERT INTO events (employee_id, name, timestamp, direction, device_id)
            VALUES (?, ?, ?, ?, ?)
        """, (
            data['employee_id'],
            user['name'],
            data['timestamp'],
            data['direction'],
            data.get('device_id', 0)
        ))
        
        conn.commit()
        event_id = cur.lastrowid
        conn.close()
        
        return jsonify({
            "success": True,
            "event_id": event_id,
            "message": "Event created successfully"
        }), 201
        
    except Exception as e:
        conn.close()
        return jsonify({"error": str(e)}), 500


@bp.route("/reports/monthly", methods=["GET"])
@api_key_required
def get_monthly_report():
    """Get monthly attendance report"""
    year = request.args.get('year', date.today().year)
    month = request.args.get('month', date.today().month)
    
    try:
        year = int(year)
        month = int(month)
        
        if not (1 <= month <= 12):
            raise ValueError("Month must be between 1 and 12")
            
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    
    # Calculate date range
    from calendar import monthrange
    days_in_month = monthrange(year, month)[1]
    start_date = f"{year}-{month:02d}-01"
    end_date = f"{year}-{month:02d}-{days_in_month}"
    
    conn = get_conn()
    cur = conn.cursor()
    
    # Get all employees
    employees = cur.execute("""
        SELECT employee_id, name
        FROM users
        WHERE is_active = 1
        ORDER BY name
    """).fetchall()
    
    # Get attendance data
    attendance = cur.execute("""
        SELECT
            employee_id,
            DATE(timestamp) as date,
            MIN(timestamp) as first_in,
            MAX(timestamp) as last_out,
            COUNT(*) as events
        FROM events
        WHERE DATE(timestamp) BETWEEN ? AND ?
        GROUP BY employee_id, date
    """, (start_date, end_date)).fetchall()
    
    conn.close()
    
    # Organize data by employee
    report_data = {}
    for emp in employees:
        emp_id = emp['employee_id']
        report_data[emp_id] = {
            "employee_id": emp_id,
            "name": emp['name'],
            "days_attended": 0,
            "days_absent": 0,
            "attendance": []
        }
    
    for att in attendance:
        emp_id = att['employee_id']
        if emp_id in report_data:
            report_data[emp_id]['days_attended'] += 1
            report_data[emp_id]['attendance'].append(dict(att))
    
    # Calculate absences
    for emp_id in report_data:
        report_data[emp_id]['days_absent'] = days_in_month - report_data[emp_id]['days_attended']
        report_data[emp_id]['attendance_rate'] = round(
            (report_data[emp_id]['days_attended'] / days_in_month * 100), 2
        )
    
    return jsonify({
        "year": year,
        "month": month,
        "total_days": days_in_month,
        "employees": list(report_data.values())
    })


@bp.route("/devices", methods=["GET"])
@api_key_required
def get_devices():
    """Get all registered devices"""
    conn = get_conn()
    cur = conn.cursor()
    
    devices = cur.execute("""
        SELECT
            id,
            name,
            ip,
            active,
            last_fetch_at,
            last_fetch_count
        FROM devices
        ORDER BY name
    """).fetchall()
    
    conn.close()
    
    return jsonify({
        "devices": [dict(d) for d in devices],
        "count": len(devices)
    })


# =============================================================================
# API Key Management Endpoints (Admin only)
# =============================================================================

@bp.route("/admin/api-keys", methods=["GET"])
@login_required
def list_api_keys():
    """List all API keys (admin only)"""
    if g.account.get('role') != 'admin':
        return jsonify({"error": "Admin access required"}), 403
    
    conn = get_conn()
    cur = conn.cursor()
    
    keys = cur.execute("""
        SELECT id, name, key, active, created_at, last_used
        FROM api_keys
        ORDER BY created_at DESC
    """).fetchall()
    
    conn.close()
    
    return jsonify({"api_keys": [dict(k) for k in keys]})


@bp.route("/admin/api-keys", methods=["POST"])
@login_required
def create_api_key():
    """Create new API key (admin only)"""
    if g.account.get('role') != 'admin':
        return jsonify({"error": "Admin access required"}), 403
    
    data = request.get_json()
    name = data.get('name', 'API Key')
    
    # Generate secure random key
    api_key = secrets.token_urlsafe(32)
    
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute("""
        INSERT INTO api_keys (name, key, created_at)
        VALUES (?, ?, ?)
    """, (name, api_key, datetime.now().isoformat()))
    
    conn.commit()
    key_id = cur.lastrowid
    conn.close()
    
    return jsonify({
        "id": key_id,
        "name": name,
        "key": api_key,
        "message": "API key created. Save this key - it won't be shown again!"
    }), 201


@bp.route("/admin/api-keys/<int:key_id>", methods=["DELETE"])
@login_required
def delete_api_key(key_id):
    """Delete API key (admin only)"""
    if g.account.get('role') != 'admin':
        return jsonify({"error": "Admin access required"}), 403
    
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute("DELETE FROM api_keys WHERE id = ?", (key_id,))
    conn.commit()
    
    if cur.rowcount == 0:
        conn.close()
        return jsonify({"error": "API key not found"}), 404
    
    conn.close()
    
    return jsonify({"message": "API key deleted"})


# =============================================================================
# Database Schema for API Keys
# =============================================================================
"""
Add this to schema.sql:

CREATE TABLE IF NOT EXISTS api_keys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    key TEXT UNIQUE NOT NULL,
    active INTEGER DEFAULT 1,
    created_at TEXT NOT NULL,
    last_used TEXT
);

CREATE INDEX idx_api_keys_key ON api_keys(key);
"""
