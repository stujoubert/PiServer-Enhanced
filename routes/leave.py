"""
Leave Management Routes
Handles leave requests, approvals, and balance tracking
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, g
from db import get_conn
from authz import login_required
from datetime import datetime, timedelta
import json

bp = Blueprint("leave", __name__, url_prefix="/leave")


@bp.route("/", methods=["GET"])
@login_required
def my_leave():
    """Employee's leave dashboard"""
    employee_id = request.args.get('employee_id', g.account.get('employee_id'))
    
    # Only admins/managers can view other employees' leave
    if employee_id != g.account.get('employee_id') and g.account.get('role') not in ['admin', 'manager']:
        flash("You can only view your own leave", "danger")
        employee_id = g.account.get('employee_id')
    
    conn = get_conn()
    cur = conn.cursor()
    
    # Get current year balances
    current_year = datetime.now().year
    balances = cur.execute("""
        SELECT 
            lt.name AS leave_type,
            lt.code,
            lt.color_code,
            lb.allocated_days,
            lb.used_days,
            lb.pending_days,
            (lb.allocated_days - lb.used_days - lb.pending_days) AS available_days
        FROM leave_balances lb
        JOIN leave_types lt ON lt.id = lb.leave_type_id
        WHERE lb.employee_id = ? AND lb.year = ?
        ORDER BY lt.name
    """, (employee_id, current_year)).fetchall()
    
    # Get recent requests
    requests = cur.execute("""
        SELECT 
            lr.id,
            lr.start_date,
            lr.end_date,
            lr.days,
            lr.reason,
            lr.status,
            lr.created_at,
            lr.approved_by,
            lr.approved_at,
            lr.rejection_reason,
            lt.name AS leave_type,
            lt.color_code,
            a.name AS approver_name
        FROM leave_requests lr
        JOIN leave_types lt ON lt.id = lr.leave_type_id
        LEFT JOIN users a ON a.employee_id = lr.approved_by
        WHERE lr.employee_id = ?
        ORDER BY lr.created_at DESC
        LIMIT 20
    """, (employee_id,)).fetchall()
    
    # Get upcoming leave
    upcoming = cur.execute("""
        SELECT 
            lr.start_date,
            lr.end_date,
            lr.days,
            lt.name AS leave_type,
            lt.color_code
        FROM leave_requests lr
        JOIN leave_types lt ON lt.id = lr.leave_type_id
        WHERE lr.employee_id = ? 
          AND lr.status = 'approved'
          AND lr.start_date >= date('now')
        ORDER BY lr.start_date
        LIMIT 5
    """, (employee_id,)).fetchall()
    
    conn.close()
    
    return render_template("leave/dashboard.html",
                          balances=balances,
                          requests=requests,
                          upcoming=upcoming,
                          employee_id=employee_id)


@bp.route("/request", methods=["GET", "POST"])
@login_required
def request_leave():
    """Submit new leave request"""
    if request.method == "POST":
        leave_type_id = request.form.get("leave_type_id", type=int)
        start_date = request.form.get("start_date")
        end_date = request.form.get("end_date")
        reason = request.form.get("reason", "")
        employee_id = g.account.get('employee_id')
        
        if not all([leave_type_id, start_date, end_date]):
            flash("Please fill all required fields", "danger")
            return redirect(request.url)
        
        # Calculate days
        start = datetime.fromisoformat(start_date)
        end = datetime.fromisoformat(end_date)
        
        if end < start:
            flash("End date must be after start date", "danger")
            return redirect(request.url)
        
        # Simple calculation (business days)
        days = (end - start).days + 1
        # TODO: Subtract weekends and holidays
        
        conn = get_conn()
        cur = conn.cursor()
        
        try:
            # Check available balance
            balance = cur.execute("""
                SELECT 
                    (allocated_days - used_days - pending_days) AS available
                FROM leave_balances
                WHERE employee_id = ? 
                  AND leave_type_id = ? 
                  AND year = ?
            """, (employee_id, leave_type_id, datetime.now().year)).fetchone()
            
            if balance and balance['available'] < days:
                flash(f"Insufficient leave balance. Available: {balance['available']} days", "danger")
                conn.close()
                return redirect(request.url)
            
            # Insert request
            cur.execute("""
                INSERT INTO leave_requests (
                    employee_id, leave_type_id, start_date, end_date,
                    days, reason, status
                ) VALUES (?, ?, ?, ?, ?, ?, 'pending')
            """, (employee_id, leave_type_id, start_date, end_date, days, reason))
            
            # Update pending balance
            cur.execute("""
                UPDATE leave_balances
                SET pending_days = pending_days + ?
                WHERE employee_id = ? AND leave_type_id = ? AND year = ?
            """, (days, employee_id, leave_type_id, datetime.now().year))
            
            # Create notification for supervisor/manager
            supervisor_id = cur.execute(
                "SELECT supervisor_employee_id FROM users WHERE employee_id = ?",
                (employee_id,)
            ).fetchone()
            
            if supervisor_id and supervisor_id['supervisor_employee_id']:
                employee_name = cur.execute(
                    "SELECT name FROM users WHERE employee_id = ?",
                    (employee_id,)
                ).fetchone()['name']
                
                cur.execute("""
                    INSERT INTO notifications (
                        employee_id, type, title, message, related_id, priority
                    ) VALUES (?, 'leave_request', 'New Leave Request',
                             ?, ?, 'high')
                """, (
                    supervisor_id['supervisor_employee_id'],
                    f"{employee_name} requested {days} days of leave",
                    cur.lastrowid
                ))
            
            conn.commit()
            flash("Leave request submitted successfully", "success")
            return redirect(url_for('leave.my_leave'))
            
        except Exception as e:
            conn.rollback()
            flash(f"Error submitting leave request: {str(e)}", "danger")
        finally:
            conn.close()
    
    # GET - show form
    conn = get_conn()
    cur = conn.cursor()
    
    leave_types = cur.execute("""
        SELECT id, name, code, is_paid, max_days_per_year
        FROM leave_types
        WHERE is_active = 1
        ORDER BY name
    """).fetchall()
    
    conn.close()
    
    return render_template("leave/request.html", leave_types=leave_types)


@bp.route("/approvals", methods=["GET"])
@login_required
def approvals():
    """View pending leave requests for approval (managers/admins)"""
    if g.account.get('role') not in ['admin', 'manager']:
        flash("Access denied", "danger")
        return redirect(url_for('leave.my_leave'))
    
    conn = get_conn()
    cur = conn.cursor()
    
    # Get employees reporting to this manager
    if g.account.get('role') == 'manager':
        # Managers see their direct reports
        pending = cur.execute("""
            SELECT 
                lr.id,
                lr.employee_id,
                u.name AS employee_name,
                u.job_title,
                d.name AS department,
                lt.name AS leave_type,
                lt.color_code,
                lr.start_date,
                lr.end_date,
                lr.days,
                lr.reason,
                lr.created_at
            FROM leave_requests lr
            JOIN users u ON u.employee_id = lr.employee_id
            JOIN leave_types lt ON lt.id = lr.leave_type_id
            LEFT JOIN departments d ON d.id = u.department_id
            WHERE lr.status = 'pending'
              AND u.supervisor_employee_id = ?
            ORDER BY lr.created_at ASC
        """, (g.account.get('employee_id'),)).fetchall()
    else:
        # Admins see all pending
        pending = cur.execute("""
            SELECT 
                lr.id,
                lr.employee_id,
                u.name AS employee_name,
                u.job_title,
                d.name AS department,
                lt.name AS leave_type,
                lt.color_code,
                lr.start_date,
                lr.end_date,
                lr.days,
                lr.reason,
                lr.created_at
            FROM leave_requests lr
            JOIN users u ON u.employee_id = lr.employee_id
            JOIN leave_types lt ON lt.id = lr.leave_type_id
            LEFT JOIN departments d ON d.id = u.department_id
            WHERE lr.status = 'pending'
            ORDER BY lr.created_at ASC
        """).fetchall()
    
    conn.close()
    
    return render_template("leave/approvals.html", pending=pending)


@bp.route("/<int:request_id>/approve", methods=["POST"])
@login_required
def approve_leave(request_id):
    """Approve a leave request"""
    if g.account.get('role') not in ['admin', 'manager']:
        return jsonify({"error": "Access denied"}), 403
    
    conn = get_conn()
    cur = conn.cursor()
    
    try:
        # Get request details
        leave_req = cur.execute("""
            SELECT employee_id, leave_type_id, days, start_date, end_date
            FROM leave_requests
            WHERE id = ? AND status = 'pending'
        """, (request_id,)).fetchone()
        
        if not leave_req:
            conn.close()
            return jsonify({"error": "Request not found or already processed"}), 404
        
        # Update request status
        cur.execute("""
            UPDATE leave_requests
            SET status = 'approved',
                approved_by = ?,
                approved_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (g.account.get('employee_id'), request_id))
        
        # Update balances
        cur.execute("""
            UPDATE leave_balances
            SET used_days = used_days + ?,
                pending_days = pending_days - ?
            WHERE employee_id = ? 
              AND leave_type_id = ? 
              AND year = ?
        """, (
            leave_req['days'], 
            leave_req['days'],
            leave_req['employee_id'],
            leave_req['leave_type_id'],
            datetime.now().year
        ))
        
        # Notify employee
        approver_name = cur.execute(
            "SELECT name FROM users WHERE employee_id = ?",
            (g.account.get('employee_id'),)
        ).fetchone()['name']
        
        cur.execute("""
            INSERT INTO notifications (
                employee_id, type, title, message, related_id, priority
            ) VALUES (?, 'leave_approved', 'Leave Request Approved',
                     ?, ?, 'normal')
        """, (
            leave_req['employee_id'],
            f"Your leave request from {leave_req['start_date']} to {leave_req['end_date']} was approved by {approver_name}",
            request_id
        ))
        
        conn.commit()
        
        return jsonify({"success": True, "message": "Leave request approved"})
        
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


@bp.route("/<int:request_id>/reject", methods=["POST"])
@login_required
def reject_leave(request_id):
    """Reject a leave request"""
    if g.account.get('role') not in ['admin', 'manager']:
        return jsonify({"error": "Access denied"}), 403
    
    reason = request.json.get('reason', 'No reason provided')
    
    conn = get_conn()
    cur = conn.cursor()
    
    try:
        # Get request details
        leave_req = cur.execute("""
            SELECT employee_id, leave_type_id, days
            FROM leave_requests
            WHERE id = ? AND status = 'pending'
        """, (request_id,)).fetchone()
        
        if not leave_req:
            conn.close()
            return jsonify({"error": "Request not found or already processed"}), 404
        
        # Update request status
        cur.execute("""
            UPDATE leave_requests
            SET status = 'rejected',
                approved_by = ?,
                approved_at = CURRENT_TIMESTAMP,
                rejection_reason = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (g.account.get('employee_id'), reason, request_id))
        
        # Update pending balance
        cur.execute("""
            UPDATE leave_balances
            SET pending_days = pending_days - ?
            WHERE employee_id = ? 
              AND leave_type_id = ? 
              AND year = ?
        """, (
            leave_req['days'],
            leave_req['employee_id'],
            leave_req['leave_type_id'],
            datetime.now().year
        ))
        
        # Notify employee
        cur.execute("""
            INSERT INTO notifications (
                employee_id, type, title, message, related_id, priority
            ) VALUES (?, 'leave_rejected', 'Leave Request Rejected',
                     ?, ?, 'high')
        """, (
            leave_req['employee_id'],
            f"Your leave request was rejected. Reason: {reason}",
            request_id
        ))
        
        conn.commit()
        
        return jsonify({"success": True, "message": "Leave request rejected"})
        
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


@bp.route("/calendar", methods=["GET"])
@login_required
def calendar():
    """Calendar view of leave across team/department"""
    # Get date range
    month = request.args.get('month', datetime.now().strftime('%Y-%m'))
    
    conn = get_conn()
    cur = conn.cursor()
    
    # Get approved leave for the month
    leave_data = cur.execute("""
        SELECT 
            lr.employee_id,
            u.name AS employee_name,
            lr.start_date,
            lr.end_date,
            lr.days,
            lt.name AS leave_type,
            lt.color_code
        FROM leave_requests lr
        JOIN users u ON u.employee_id = lr.employee_id
        JOIN leave_types lt ON lt.id = lr.leave_type_id
        WHERE lr.status = 'approved'
          AND strftime('%Y-%m', lr.start_date) = ?
        ORDER BY lr.start_date
    """, (month,)).fetchall()
    
    # Get holidays
    holidays = cur.execute("""
        SELECT name, date
        FROM holidays
        WHERE strftime('%Y-%m', date) = ?
          AND is_paid = 1
        ORDER BY date
    """, (month,)).fetchall()
    
    conn.close()
    
    return render_template("leave/calendar.html",
                          leave_data=leave_data,
                          holidays=holidays,
                          month=month)


@bp.route("/team", methods=["GET"])
@login_required
def team_overview():
    """Overview of team leave balances and usage"""
    if g.account.get('role') not in ['admin', 'manager']:
        flash("Access denied", "danger")
        return redirect(url_for('leave.my_leave'))
    
    conn = get_conn()
    cur = conn.cursor()
    
    # Get team members
    if g.account.get('role') == 'manager':
        team_members = cur.execute("""
            SELECT employee_id FROM users
            WHERE supervisor_employee_id = ? AND is_active = 1
        """, (g.account.get('employee_id'),)).fetchall()
        team_ids = [m['employee_id'] for m in team_members]
    else:
        # Admins see all
        team_members = cur.execute("""
            SELECT employee_id FROM users WHERE is_active = 1
        """).fetchall()
        team_ids = [m['employee_id'] for m in team_members]
    
    if not team_ids:
        conn.close()
        return render_template("leave/team_overview.html", team_summary=[])
    
    # Get summary for each team member
    placeholders = ','.join(['?' for _ in team_ids])
    team_summary = cur.execute(f"""
        SELECT 
            u.employee_id,
            u.name,
            u.job_title,
            d.name AS department,
            SUM(lb.allocated_days) AS total_allocated,
            SUM(lb.used_days) AS total_used,
            SUM(lb.pending_days) AS total_pending,
            SUM(lb.allocated_days - lb.used_days - lb.pending_days) AS total_available
        FROM users u
        LEFT JOIN departments d ON d.id = u.department_id
        LEFT JOIN leave_balances lb ON lb.employee_id = u.employee_id 
            AND lb.year = ?
        WHERE u.employee_id IN ({placeholders})
        GROUP BY u.employee_id
        ORDER BY u.name
    """, [datetime.now().year] + team_ids).fetchall()
    
    conn.close()
    
    return render_template("leave/team_overview.html", team_summary=team_summary)
