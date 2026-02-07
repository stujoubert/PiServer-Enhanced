"""
Department Management Routes
Handles department CRUD, hierarchy, and employee assignments
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, g
from db import get_conn
from authz import login_required
import json

bp = Blueprint("departments", __name__, url_prefix="/departments")


@bp.route("/", methods=["GET"])
@login_required
def departments_list():
    """List all departments with employee counts"""
    conn = get_conn()
    cur = conn.cursor()
    
    departments = cur.execute("""
        SELECT 
            d.id,
            d.name,
            d.code,
            d.description,
            d.manager_employee_id,
            m.name AS manager_name,
            d.parent_department_id,
            p.name AS parent_name,
            d.cost_center,
            d.is_active,
            COUNT(u.id) AS employee_count
        FROM departments d
        LEFT JOIN users m ON m.employee_id = d.manager_employee_id
        LEFT JOIN departments p ON p.id = d.parent_department_id
        LEFT JOIN users u ON u.department_id = d.id AND u.is_active = 1
        GROUP BY d.id
        ORDER BY d.name
    """).fetchall()
    
    conn.close()
    
    return render_template("departments/list.html", departments=departments)


@bp.route("/create", methods=["GET", "POST"])
@login_required
def create_department():
    """Create new department"""
    if g.account.get('role') != 'admin':
        flash("Admin access required", "danger")
        return redirect(url_for('departments.departments_list'))
    
    if request.method == "POST":
        name = request.form.get("name")
        code = request.form.get("code")
        description = request.form.get("description")
        manager_id = request.form.get("manager_employee_id")
        parent_id = request.form.get("parent_department_id")
        cost_center = request.form.get("cost_center")
        
        if not name:
            flash("Department name is required", "danger")
            return redirect(request.url)
        
        conn = get_conn()
        cur = conn.cursor()
        
        try:
            cur.execute("""
                INSERT INTO departments (
                    name, code, description, manager_employee_id, 
                    parent_department_id, cost_center
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (name, code, description, manager_id or None, 
                  parent_id or None, cost_center))
            
            conn.commit()
            flash(f"Department '{name}' created successfully", "success")
            return redirect(url_for('departments.departments_list'))
            
        except Exception as e:
            conn.rollback()
            flash(f"Error creating department: {str(e)}", "danger")
        finally:
            conn.close()
    
    # GET - show form
    conn = get_conn()
    cur = conn.cursor()
    
    # Get potential managers
    managers = cur.execute("""
        SELECT employee_id, name, job_title
        FROM users
        WHERE is_active = 1
        ORDER BY name
    """).fetchall()
    
    # Get parent departments
    parent_depts = cur.execute("""
        SELECT id, name
        FROM departments
        WHERE is_active = 1
        ORDER BY name
    """).fetchall()
    
    conn.close()
    
    return render_template("departments/create.html", 
                          managers=managers, 
                          parent_depts=parent_depts)


@bp.route("/<int:dept_id>/edit", methods=["GET", "POST"])
@login_required
def edit_department(dept_id):
    """Edit department details"""
    if g.account.get('role') != 'admin':
        flash("Admin access required", "danger")
        return redirect(url_for('departments.departments_list'))
    
    conn = get_conn()
    cur = conn.cursor()
    
    if request.method == "POST":
        name = request.form.get("name")
        code = request.form.get("code")
        description = request.form.get("description")
        manager_id = request.form.get("manager_employee_id")
        parent_id = request.form.get("parent_department_id")
        cost_center = request.form.get("cost_center")
        is_active = 1 if request.form.get("is_active") else 0
        
        try:
            cur.execute("""
                UPDATE departments
                SET name = ?, code = ?, description = ?, 
                    manager_employee_id = ?, parent_department_id = ?,
                    cost_center = ?, is_active = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (name, code, description, manager_id or None, 
                  parent_id or None, cost_center, is_active, dept_id))
            
            conn.commit()
            flash("Department updated successfully", "success")
            return redirect(url_for('departments.departments_list'))
            
        except Exception as e:
            conn.rollback()
            flash(f"Error updating department: {str(e)}", "danger")
        finally:
            conn.close()
    
    # GET - load department
    department = cur.execute("""
        SELECT * FROM departments WHERE id = ?
    """, (dept_id,)).fetchone()
    
    if not department:
        conn.close()
        flash("Department not found", "danger")
        return redirect(url_for('departments.departments_list'))
    
    # Get potential managers
    managers = cur.execute("""
        SELECT employee_id, name, job_title
        FROM users
        WHERE is_active = 1
        ORDER BY name
    """).fetchall()
    
    # Get parent departments (excluding self)
    parent_depts = cur.execute("""
        SELECT id, name
        FROM departments
        WHERE is_active = 1 AND id != ?
        ORDER BY name
    """, (dept_id,)).fetchall()
    
    conn.close()
    
    return render_template("departments/edit.html", 
                          department=department,
                          managers=managers,
                          parent_depts=parent_depts)


@bp.route("/<int:dept_id>", methods=["GET"])
@login_required
def view_department(dept_id):
    """View department details and employees"""
    conn = get_conn()
    cur = conn.cursor()
    
    department = cur.execute("""
        SELECT 
            d.*,
            m.name AS manager_name,
            p.name AS parent_name
        FROM departments d
        LEFT JOIN users m ON m.employee_id = d.manager_employee_id
        LEFT JOIN departments p ON p.id = d.parent_department_id
        WHERE d.id = ?
    """, (dept_id,)).fetchone()
    
    if not department:
        conn.close()
        flash("Department not found", "danger")
        return redirect(url_for('departments.departments_list'))
    
    # Get employees in this department
    employees = cur.execute("""
        SELECT 
            u.employee_id,
            u.name,
            u.email,
            u.job_title,
            u.employee_type,
            u.hire_date,
            s.name AS supervisor_name
        FROM users u
        LEFT JOIN users s ON s.employee_id = u.supervisor_employee_id
        WHERE u.department_id = ? AND u.is_active = 1
        ORDER BY u.name
    """, (dept_id,)).fetchall()
    
    # Get subdepartments
    subdepts = cur.execute("""
        SELECT id, name, code, manager_employee_id,
               (SELECT name FROM users WHERE employee_id = manager_employee_id) AS manager_name,
               (SELECT COUNT(*) FROM users WHERE department_id = departments.id) AS emp_count
        FROM departments
        WHERE parent_department_id = ? AND is_active = 1
    """, (dept_id,)).fetchall()
    
    conn.close()
    
    return render_template("departments/view.html",
                          department=department,
                          employees=employees,
                          subdepts=subdepts)


@bp.route("/<int:dept_id>/employees/assign", methods=["POST"])
@login_required
def assign_employees(dept_id):
    """Bulk assign employees to department"""
    if g.account.get('role') != 'admin':
        return jsonify({"error": "Admin access required"}), 403
    
    employee_ids = request.json.get('employee_ids', [])
    
    if not employee_ids:
        return jsonify({"error": "No employees selected"}), 400
    
    conn = get_conn()
    cur = conn.cursor()
    
    try:
        placeholders = ','.join(['?' for _ in employee_ids])
        cur.execute(f"""
            UPDATE users
            SET department_id = ?
            WHERE employee_id IN ({placeholders})
        """, [dept_id] + employee_ids)
        
        conn.commit()
        
        return jsonify({
            "success": True,
            "message": f"{len(employee_ids)} employees assigned to department"
        })
        
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


@bp.route("/hierarchy", methods=["GET"])
@login_required
def department_hierarchy():
    """View department hierarchy tree"""
    conn = get_conn()
    cur = conn.cursor()
    
    # Get all departments
    departments = cur.execute("""
        SELECT 
            d.id,
            d.name,
            d.code,
            d.parent_department_id,
            m.name AS manager_name,
            COUNT(u.id) AS employee_count
        FROM departments d
        LEFT JOIN users m ON m.employee_id = d.manager_employee_id
        LEFT JOIN users u ON u.department_id = d.id AND u.is_active = 1
        WHERE d.is_active = 1
        GROUP BY d.id
        ORDER BY d.name
    """).fetchall()
    
    conn.close()
    
    # Build tree structure
    dept_dict = {d['id']: dict(d) for d in departments}
    for dept in dept_dict.values():
        dept['children'] = []
    
    root_depts = []
    for dept in dept_dict.values():
        if dept['parent_department_id']:
            parent = dept_dict.get(dept['parent_department_id'])
            if parent:
                parent['children'].append(dept)
        else:
            root_depts.append(dept)
    
    return render_template("departments/hierarchy.html", departments=root_depts)


@bp.route("/api/tree", methods=["GET"])
@login_required
def api_tree():
    """API endpoint for department tree (for JS visualization)"""
    conn = get_conn()
    cur = conn.cursor()
    
    departments = cur.execute("""
        SELECT 
            id, name, code, parent_department_id,
            manager_employee_id,
            (SELECT name FROM users WHERE employee_id = manager_employee_id) AS manager_name,
            (SELECT COUNT(*) FROM users WHERE department_id = departments.id) AS employee_count
        FROM departments
        WHERE is_active = 1
    """).fetchall()
    
    conn.close()
    
    return jsonify([dict(d) for d in departments])
