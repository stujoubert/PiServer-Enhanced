"""
Department Schedule Assignment Routes
Allows bulk assignment of schedules to entire departments
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, g
from db import get_conn
from authz import login_required

bp = Blueprint("department_schedules", __name__, url_prefix="/departments")


@bp.route("/<int:dept_id>/schedules", methods=["GET"])
@login_required
def view_schedules(dept_id):
    """View schedules assigned to a department"""
    conn = get_conn()
    cur = conn.cursor()
    
    # Get department info
    department = cur.execute("""
        SELECT id, name, code, description
        FROM departments
        WHERE id = ? AND is_active = 1
    """, (dept_id,)).fetchone()
    
    if not department:
        flash("Department not found", "danger")
        conn.close()
        return redirect(url_for('departments.departments_list'))
    
    # Get assigned schedules
    assigned_schedules = cur.execute("""
        SELECT 
            ds.id,
            ds.schedule_id,
            s.name AS schedule_name,
            s.description AS schedule_description,
            ds.effective_date,
            ds.end_date,
            ds.is_active,
            COUNT(DISTINCT u.employee_id) AS affected_employees
        FROM department_schedules ds
        JOIN schedules s ON s.id = ds.schedule_id
        LEFT JOIN users u ON u.department_id = ? AND u.is_active = 1
        WHERE ds.department_id = ?
        GROUP BY ds.id
        ORDER BY ds.effective_date DESC
    """, (dept_id, dept_id)).fetchall()
    
    # Get available schedules (not yet assigned)
    available_schedules = cur.execute("""
        SELECT s.id, s.name, s.description
        FROM schedules s
        WHERE s.id NOT IN (
            SELECT schedule_id 
            FROM department_schedules 
            WHERE department_id = ? AND is_active = 1
        )
        ORDER BY s.name
    """, (dept_id,)).fetchall()
    
    # Get employees in this department
    employees = cur.execute("""
        SELECT employee_id, name, job_title
        FROM users
        WHERE department_id = ? AND is_active = 1
        ORDER BY name
    """, (dept_id,)).fetchall()
    
    conn.close()
    
    return render_template("departments/schedules.html",
                          department=department,
                          assigned_schedules=assigned_schedules,
                          available_schedules=available_schedules,
                          employees=employees)


@bp.route("/<int:dept_id>/schedules/assign", methods=["POST"])
@login_required
def assign_schedule(dept_id):
    """Assign a schedule to a department"""
    if g.account.get('role') not in ['admin', 'manager']:
        return jsonify({"error": "Permission denied"}), 403
    
    schedule_id = request.form.get("schedule_id", type=int)
    effective_date = request.form.get("effective_date")
    end_date = request.form.get("end_date")
    
    if not schedule_id:
        flash("Please select a schedule", "danger")
        return redirect(url_for('department_schedules.view_schedules', dept_id=dept_id))
    
    conn = get_conn()
    cur = conn.cursor()
    
    try:
        # Assign schedule to department
        cur.execute("""
            INSERT INTO department_schedules (
                department_id, schedule_id, effective_date, end_date, is_active
            ) VALUES (?, ?, ?, ?, 1)
        """, (dept_id, schedule_id, effective_date or None, end_date or None))
        
        conn.commit()
        
        # Get counts
        emp_count = cur.execute("""
            SELECT COUNT(*) as cnt FROM users 
            WHERE department_id = ? AND is_active = 1
        """, (dept_id,)).fetchone()['cnt']
        
        schedule_name = cur.execute("""
            SELECT name FROM schedules WHERE id = ?
        """, (schedule_id,)).fetchone()['name']
        
        flash(f"Schedule '{schedule_name}' assigned to department. {emp_count} employees affected.", "success")
        
    except Exception as e:
        conn.rollback()
        flash(f"Error assigning schedule: {str(e)}", "danger")
    finally:
        conn.close()
    
    return redirect(url_for('department_schedules.view_schedules', dept_id=dept_id))


@bp.route("/<int:dept_id>/schedules/<int:assignment_id>/remove", methods=["POST"])
@login_required
def remove_schedule(dept_id, assignment_id):
    """Remove a schedule assignment from a department"""
    if g.account.get('role') not in ['admin', 'manager']:
        return jsonify({"error": "Permission denied"}), 403
    
    conn = get_conn()
    cur = conn.cursor()
    
    try:
        # Deactivate the assignment
        cur.execute("""
            UPDATE department_schedules
            SET is_active = 0, end_date = date('now')
            WHERE id = ? AND department_id = ?
        """, (assignment_id, dept_id))
        
        conn.commit()
        flash("Schedule assignment removed", "success")
        
    except Exception as e:
        conn.rollback()
        flash(f"Error removing schedule: {str(e)}", "danger")
    finally:
        conn.close()
    
    return redirect(url_for('department_schedules.view_schedules', dept_id=dept_id))


@bp.route("/<int:dept_id>/schedules/apply-to-employees", methods=["POST"])
@login_required
def apply_to_employees(dept_id):
    """Apply department schedule to all employees in the department"""
    if g.account.get('role') not in ['admin', 'manager']:
        return jsonify({"error": "Permission denied"}), 403
    
    schedule_id = request.form.get("schedule_id", type=int)
    
    if not schedule_id:
        return jsonify({"error": "No schedule selected"}), 400
    
    conn = get_conn()
    cur = conn.cursor()
    
    try:
        # Get all employees in department
        employees = cur.execute("""
            SELECT employee_id FROM users
            WHERE department_id = ? AND is_active = 1
        """, (dept_id,)).fetchall()
        
        employee_ids = [emp['employee_id'] for emp in employees]
        
        if not employee_ids:
            return jsonify({"error": "No active employees in department"}), 400
        
        # Apply schedule to each employee
        # This depends on your schedule assignment structure
        # Adjust based on your schema
        
        updated_count = 0
        for emp_id in employee_ids:
            # Example: Update user's default schedule
            # Adjust this based on your actual schema
            cur.execute("""
                UPDATE users
                SET schedule_id = ?
                WHERE employee_id = ?
            """, (schedule_id, emp_id))
            updated_count += 1
        
        conn.commit()
        
        schedule_name = cur.execute("""
            SELECT name FROM schedules WHERE id = ?
        """, (schedule_id,)).fetchone()['name']
        
        return jsonify({
            "success": True,
            "message": f"Schedule '{schedule_name}' applied to {updated_count} employees"
        })
        
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


@bp.route("/api/department/<int:dept_id>/schedule-options", methods=["GET"])
@login_required
def api_schedule_options(dept_id):
    """API endpoint to get schedule options for a department"""
    conn = get_conn()
    cur = conn.cursor()
    
    schedules = cur.execute("""
        SELECT id, name, description
        FROM schedules
        ORDER BY name
    """, ).fetchall()
    
    conn.close()
    
    return jsonify([dict(s) for s in schedules])
