from datetime import datetime, timedelta, date
import json

from flask import render_template, request, redirect, url_for, flash, g


def ensure_shift_tables(cur):
    """
    Create shift-related tables and defaults.
    This is called from server.ensure_db().
    """
    # Master list of types of shifts
    cur.execute("""
        CREATE TABLE IF NOT EXISTS shift_types (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time   TEXT NOT NULL,
            break_minutes INTEGER NOT NULL DEFAULT 0,
            overnight   INTEGER NOT NULL DEFAULT 0
        )
    """)

    # Rotation pattern (weekly or cycle) stored as JSON
    cur.execute("""
        CREATE TABLE IF NOT EXISTS shift_rotations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            pattern_type TEXT NOT NULL,
            pattern_json TEXT NOT NULL
        )
    """)

    # Which employee uses which rotation in which date range
    cur.execute("""
        CREATE TABLE IF NOT EXISTS employee_shift_assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id TEXT NOT NULL,
            rotation_id INTEGER NOT NULL,
            start_date TEXT NOT NULL,
            end_date   TEXT,
            FOREIGN KEY(rotation_id) REFERENCES shift_rotations(id)
        )
    """)

    # Per-day overrides (including "day off")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS employee_shift_overrides (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id  TEXT NOT NULL,
            date         TEXT NOT NULL,
            shift_type_id INTEGER,
            note         TEXT,
            FOREIGN KEY(shift_type_id) REFERENCES shift_types(id)
        )
    """)

    # Default shift type (Standard Day Shift)
    cur.execute("""
        INSERT OR IGNORE INTO shift_types (id, name, start_time, end_time, break_minutes, overnight)
        VALUES (1, 'Standard Day Shift', '08:00', '17:00', 60, 0)
    """)

    default_pattern = {
        "type": "weekly",
        "mon": 1,
        "tue": 1,
        "wed": 1,
        "thu": 1,
        "fri": 1,
        "sat": None,
        "sun": None,
    }
    cur.execute("""
        INSERT OR IGNORE INTO shift_rotations (id, name, pattern_type, pattern_json)
        VALUES (1, 'Standard Mon–Fri 08:00–17:00', 'weekly', ?)
    """, (json.dumps(default_pattern),))


def get_expected_shift(get_conn, employee_id, day: date):
    """
    Returns a dict like:
    {
        "shift_type_id": 1,
        "name": "Morning",
        "start_time": "08:00",
        "end_time": "16:00",
        "break_minutes": 30,
        "overnight": 0
    }
    or None if no shift is assigned.
    """
    if not employee_id:
        return None

    conn = get_conn()
    cur = conn.cursor()

    day_str = day.strftime("%Y-%m-%d")

    # 1) Check for explicit override
    cur.execute("""
        SELECT st.id, st.name, st.start_time, st.end_time, st.break_minutes, st.overnight
        FROM employee_shift_overrides o
        LEFT JOIN shift_types st ON o.shift_type_id = st.id
        WHERE o.employee_id = ? AND o.date = ?
    """, (employee_id, day_str))
    row = cur.fetchone()

    if row:
        if row[0] is None:
            conn.close()
            return None
        shift = {
            "shift_type_id": row[0],
            "name": row[1],
            "start_time": row[2],
            "end_time": row[3],
            "break_minutes": row[4],
            "overnight": row[5],
        }
        conn.close()
        return shift

    # 2) Find the rotation assignment that's active for that day
    cur.execute("""
        SELECT r.id, r.pattern_json
        FROM employee_shift_assignments a
        JOIN shift_rotations r ON a.rotation_id = r.id
        WHERE a.employee_id = ?
          AND a.start_date <= ?
          AND (a.end_date IS NULL OR a.end_date >= ?)
        ORDER BY a.start_date DESC
        LIMIT 1
    """, (employee_id, day_str, day_str))

    row = cur.fetchone()
    if not row:
        conn.close()
        return None

    rotation_id, pattern_json = row
    pattern = json.loads(pattern_json)

    weekday = day.weekday()  # Monday=0
    day_key = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"][weekday]

    shift_type_id = None

    if pattern.get("type") == "weekly":
        shift_type_id = pattern.get(day_key)
    elif pattern.get("type") == "cycle":
        start_str = pattern.get("start_date")
        if not start_str:
            conn.close()
            return None
        start_dt = datetime.strptime(start_str, "%Y-%m-%d").date()
        days_diff = (day - start_dt).days
        if days_diff < 0:
            conn.close()
            return None
        idx = days_diff % pattern["length"]
        shift_type_id = pattern["days"][idx]

    if not shift_type_id:
        conn.close()
        return None  # day off

    # 3) Load shift info
    cur.execute("""
        SELECT id, name, start_time, end_time, break_minutes, overnight
        FROM shift_types
        WHERE id = ?
    """, (shift_type_id,))
    st = cur.fetchone()
    conn.close()

    if not st:
        return None

    return {
        "shift_type_id": st[0],
        "name": st[1],
        "start_time": st[2],
        "end_time": st[3],
        "break_minutes": st[4],
        "overnight": st[5],
    }


def register_shift_routes(app, get_conn, get_all_employees):
    """
    Attach all /shifts/* routes to the given Flask app.
    Uses get_conn() + get_all_employees() from server.py.
    """

    @app.route("/shifts/types")
    def shift_types_list():
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT id, name, start_time, end_time, break_minutes, overnight FROM shift_types ORDER BY id")
        rows = cur.fetchall()
        conn.close()
        return render_template("shift_types.html", rows=rows)

    @app.route("/shifts/types/add", methods=["POST"])
    def shift_types_add():
        name = request.form.get("name")
        start = request.form.get("start_time")
        end = request.form.get("end_time")
        break_min = int(request.form.get("break_minutes", 0))
        overnight = int(request.form.get("overnight", 0))

        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO shift_types (name, start_time, end_time, break_minutes, overnight)
            VALUES (?, ?, ?, ?, ?)
        """, (name, start, end, break_min, overnight))
        conn.commit()
        conn.close()
        return redirect(url_for("shift_types_list", lang=g.lang))

    @app.route("/shifts/types/<int:id>/delete", methods=["POST"])
    def shift_types_delete(id):
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("DELETE FROM shift_types WHERE id=?", (id,))
        conn.commit()
        conn.close()
        return redirect(url_for("shift_types_list", lang=g.lang))

    @app.route("/shifts/rotations")
    def shift_rotations_list():
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT id, name, pattern_json FROM shift_rotations ORDER BY id")
        rows = cur.fetchall()
        conn.close()

        parsed = []
        for r in rows:
            pid = r[0]
            name = r[1]
            pattern = json.loads(r[2])
            parsed.append({"id": pid, "name": name, "pattern": pattern})

        return render_template("shift_rotations.html", rows=parsed)

    @app.route("/shifts/rotations/add", methods=["POST"])
    def shift_rotations_add():
        name = request.form.get("name")
        ptype = request.form.get("pattern_type")

        pattern = {}

        if ptype == "weekly":
            pattern = {
                "type": "weekly",
                "mon": request.form.get("mon") or None,
                "tue": request.form.get("tue") or None,
                "wed": request.form.get("wed") or None,
                "thu": request.form.get("thu") or None,
                "fri": request.form.get("fri") or None,
                "sat": request.form.get("sat") or None,
                "sun": request.form.get("sun") or None,
            }

        elif ptype == "cycle":
            length = int(request.form.get("cycle_length"))
            days_list = []
            for i in range(length):
                val = request.form.get(f"cycle_{i}") or None
                days_list.append(val)
            pattern = {
                "type": "cycle",
                "length": length,
                "start_date": request.form.get("cycle_start"),
                "days": days_list
            }

        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO shift_rotations (name, pattern_type, pattern_json)
            VALUES (?, ?, ?)
        """, (name, ptype, json.dumps(pattern)))
        conn.commit()
        conn.close()

        return redirect(url_for("shift_rotations_list", lang=g.lang))

    @app.route("/shifts/rotations/<int:rotation_id>/delete", methods=["POST"])
    def shifts_rotation_delete(rotation_id):
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("DELETE FROM shift_rotations WHERE id=?", (rotation_id,))
        conn.commit()
        conn.close()
        flash("Shift rotation deleted.", "success")
        return redirect(url_for("shift_rotations_list", lang=g.lang))

    @app.route("/shifts/assignments", methods=["GET", "POST"], endpoint="shift_assignments")
    def shifts_assignments_ui():
        """
        Assistant-style UI:
          - Left: list of employees
          - Right: selected employee details, history, assignment form, 7-day preview
        """
        T = g.T

        # -------------------------------
        #  POST: save new assignment
        # -------------------------------
        if request.method == "POST":
            employee_id = request.form.get("employee_id", "").strip()
            rotation_id = request.form.get("rotation_id") or None
            start_date  = request.form.get("start_date") or datetime.now().date().isoformat()
            end_date    = request.form.get("end_date") or None

            if employee_id and rotation_id:
                conn = get_conn()
                cur = conn.cursor()

                # Close any overlapping/open assignments for this employee
                cur.execute("""
                    UPDATE employee_shift_assignments
                    SET end_date = ?
                    WHERE employee_id = ?
                      AND (end_date IS NULL OR end_date >= ?)
                """, (start_date, employee_id, start_date))

                # Insert new assignment
                cur.execute("""
                    INSERT INTO employee_shift_assignments (employee_id, rotation_id, start_date, end_date)
                    VALUES (?, ?, ?, ?)
                """, (employee_id, rotation_id, start_date, end_date))
                conn.commit()
                conn.close()

                flash("Shift assignment saved.", "success")
            else:
                flash("Employee and rotation are required.", "error")

            return redirect(url_for("shift_assignments", lang=g.lang, employee_id=employee_id))

        # -------------------------------
        #  GET: render UI
        # -------------------------------
        employees = get_all_employees()  # list of (emp_id, name)
        selected_id = request.args.get("employee_id")

        # Default to first employee if none selected
        if not selected_id and employees:
            selected_id = employees[0][0]

        # Lookup selected employee name
        selected_name = None
        for emp_id, name in employees:
            if emp_id == selected_id:
                selected_name = name
                break

        conn = get_conn()
        cur = conn.cursor()

        # Load available rotations
        cur.execute("SELECT id, name FROM shift_rotations ORDER BY name")
        rotations = cur.fetchall()

        history = []
        preview_days = []
        current_rotation = None

        if selected_id:
            # Assignment history for this employee
            cur.execute("""
                SELECT a.id, a.rotation_id, r.name, a.start_date, a.end_date
                FROM employee_shift_assignments a
                LEFT JOIN shift_rotations r ON r.id = a.rotation_id
                WHERE a.employee_id = ?
                ORDER BY a.start_date DESC, a.id DESC
            """, (selected_id,))
            history = cur.fetchall()

            # Current (latest) rotation
            if history:
                rec = history[0]
                current_rotation = {
                    "name": rec[2],
                    "start_date": rec[3],
                    "end_date": rec[4],
                }

            # 7-day preview using get_expected_shift()
            today = datetime.now().date()
            for i in range(7):
                d = today + timedelta(days=i)
                shift = get_expected_shift(get_conn, selected_id, d)
                if shift:
                    label = f"{shift['name']} {shift['start_time']}–{shift['end_time']}"
                else:
                    label = "Day off"
                preview_days.append({"date": d.isoformat(), "label": label})

        conn.close()

        return render_template(
            "shifts_assignments.html",
            employees=employees,
            selected_employee_id=selected_id,
            selected_employee_name=selected_name,
            rotations=rotations,
            history=history,
            preview_days=preview_days,
            current_rotation=current_rotation,
        )

    @app.route("/shifts/assignments/<int:assign_id>/delete", methods=["POST"])
    def shifts_assignment_delete(assign_id):
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("DELETE FROM employee_shift_assignments WHERE id=?", (assign_id,))
        conn.commit()
        conn.close()
        flash("Assignment deleted.", "success")
        return redirect(url_for("shift_assignments", lang=g.lang))

    @app.route("/shifts/assign/bulk", methods=["GET", "POST"])
    def shifts_assign_bulk():
        """
        Bulk-assign a rotation to many employees at once,
        using employees from device_users.
        """
        conn = get_conn()
        cur = conn.cursor()

        if request.method == "POST":
            rotation_id = request.form.get("rotation_id")
            start_date = request.form.get("start_date")
            selected_emps = request.form.getlist("employee_id")

            if not rotation_id or not start_date or not selected_emps:
                conn.close()
                flash("Please select at least one employee, a rotation and a start date.", "error")
                return redirect(url_for("shifts_assign_bulk", lang=g.lang))

            rotation_id = int(rotation_id)

            # Close any open assignments that overlap this new start date,
            # then insert the new assignment.
            try:
                start_dt = datetime.fromisoformat(start_date).date()
            except Exception:
                conn.close()
                flash("Invalid start date.", "error")
                return redirect(url_for("shifts_assign_bulk", lang=g.lang))

            prev_end = (start_dt - timedelta(days=1)).isoformat()

            for emp_id in selected_emps:
                emp_id = emp_id.strip()
                if not emp_id:
                    continue

                # Close existing open assignment (if any)
                cur.execute("""
                    SELECT id
                    FROM employee_shift_assignments
                    WHERE employee_id = ?
                      AND (end_date IS NULL OR end_date >= ?)
                    ORDER BY start_date DESC
                    LIMIT 1
                """, (emp_id, start_date))
                row = cur.fetchone()
                if row:
                    assign_id = row[0]
                    cur.execute(
                        "UPDATE employee_shift_assignments SET end_date=? WHERE id=?",
                        (prev_end, assign_id),
                    )

                # Insert new assignment
                cur.execute("""
                    INSERT INTO employee_shift_assignments (employee_id, rotation_id, start_date, end_date)
                    VALUES (?, ?, ?, NULL)
                """, (emp_id, rotation_id, start_date))

            conn.commit()
            conn.close()
            flash(f"Assigned rotation to {len(selected_emps)} employees.", "success")
            return redirect(url_for("shift_assignments", lang=g.lang))

        # GET: list device users + rotations
        cur.execute("""
            SELECT du.employee_id, du.name, du.device_id,
                   COALESCE(d.name, '') AS device_name
            FROM device_users du
            LEFT JOIN devices d ON d.id = du.device_id
            ORDER BY du.name COLLATE NOCASE, du.employee_id
        """)
        users = cur.fetchall()

        cur.execute("SELECT id, name FROM shift_rotations ORDER BY name")
        rotations = cur.fetchall()
        conn.close()

        return render_template(
            "shifts_assign_bulk.html",
            users=users,
            rotations=rotations,
        )

    @app.route("/shifts/overrides", methods=["GET", "POST"], endpoint="shift_overrides")
    def shifts_overrides():
        """
        UI for creating per-day (or per-range) overrides:
          - Change shift for specific day(s)
          - Mark day(s) as day off
        Stored internally as one row per day in employee_shift_overrides.
        """
        conn = get_conn()
        cur = conn.cursor()

        if request.method == "POST":
            employee_id = request.form.get("employee_id", "").strip()
            start_str = request.form.get("start_date") or request.form.get("date")
            end_str = request.form.get("end_date") or start_str
            shift_type_id_raw = request.form.get("shift_type_id")
            note = request.form.get("note", "").strip()

            if not employee_id or not start_str:
                flash("Employee and date are required.", "error")
            else:
                # Day off = no shift_type_id
                if shift_type_id_raw == "off":
                    shift_type_id = None
                else:
                    shift_type_id = int(shift_type_id_raw) if shift_type_id_raw else None

                try:
                    start_dt = datetime.fromisoformat(start_str).date()
                    end_dt = datetime.fromisoformat(end_str).date()
                    if end_dt < start_dt:
                        end_dt = start_dt
                except Exception:
                    start_dt = end_dt = None

                if not start_dt:
                    flash("Invalid date format.", "error")
                else:
                    d = start_dt
                    while d <= end_dt:
                        day_str = d.isoformat()
                        cur.execute("""
                            INSERT INTO employee_shift_overrides (employee_id, date, shift_type_id, note)
                            VALUES (?, ?, ?, ?)
                        """, (employee_id, day_str, shift_type_id, note))
                        d += timedelta(days=1)

                    conn.commit()
                    flash("Override(s) created.", "success")

        # shift types for dropdown
        cur.execute("SELECT id, name FROM shift_types ORDER BY name")
        shift_types = cur.fetchall()

        # recent overrides
        cur.execute("""
            SELECT o.id, o.employee_id, o.date, o.shift_type_id, o.note, st.name
            FROM employee_shift_overrides o
            LEFT JOIN shift_types st ON o.shift_type_id = st.id
            ORDER BY o.date DESC, o.id DESC
            LIMIT 200
        """)
        overrides = cur.fetchall()
        conn.close()

        return render_template(
            "shifts_overrides.html",
            shift_types=shift_types,
            overrides=overrides,
        )

    @app.route("/shifts/overrides/add", methods=["POST"])
    def shift_overrides_add():
        emp = request.form.get("employee_id")
        date_str = request.form.get("date")
        stype = request.form.get("shift_type_id")
        if stype == "none":
            stype = None

        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO employee_shift_overrides (employee_id, date, shift_type_id)
            VALUES (?, ?, ?)
        """, (emp, date_str, stype))
        conn.commit()
        conn.close()

        return redirect(url_for("shift_overrides", lang=g.lang))

    @app.route("/shifts/overrides/<int:override_id>/delete", methods=["POST"])
    def shifts_override_delete(override_id):
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("DELETE FROM employee_shift_overrides WHERE id=?", (override_id,))
        conn.commit()
        conn.close()
        flash("Override deleted.", "success")
        return redirect(url_for("shift_overrides", lang=g.lang))

    @app.route("/shifts/users", methods=["GET"])
    def shifts_users_page():
        conn = get_conn()
        cur = conn.cursor()

        # Load all device users
        cur.execute("""
            SELECT device_id, employee_id, name
            FROM device_users
            ORDER BY name
        """)
        users = cur.fetchall()

        # Load all available rotations
        cur.execute("""
            SELECT id, name
            FROM shift_rotations
            ORDER BY name
        """)
        rotations = cur.fetchall()

        # Load existing assignments (most recent)
        cur.execute("""
            SELECT employee_id, rotation_id
            FROM employee_shift_assignments
            WHERE end_date IS NULL
        """)
        assigned = {row[0]: row[1] for row in cur.fetchall()}

        conn.close()

        user_rows = []
        for device_id, emp_id, name in users:
            current_rot = assigned.get(emp_id)
            user_rows.append({
                "device_id": device_id,
                "employee_id": emp_id,
                "name": name,
                "rotation_id": current_rot
            })

        return render_template(
            "shifts_users.html",
            users=user_rows,
            rotations=rotations
        )

    @app.route("/shifts/users/assign", methods=["POST"])
    def shifts_users_assign():
        employee_id = request.form.get("employee_id")
        rotation_id = request.form.get("rotation_id")

        if not employee_id or not rotation_id:
            flash("Missing fields", "error")
            return redirect(url_for("shifts_users_page"))

        today = datetime.now().strftime("%Y-%m-%d")

        conn = get_conn()
        cur = conn.cursor()

        # Close any existing assignment
        cur.execute("""
            UPDATE employee_shift_assignments
            SET end_date = ?
            WHERE employee_id = ? AND end_date IS NULL
        """, (today, employee_id))

        # Insert new one
        cur.execute("""
            INSERT INTO employee_shift_assignments (employee_id, rotation_id, start_date, end_date)
            VALUES (?, ?, ?, NULL)
        """, (employee_id, rotation_id, today))

        conn.commit()
        conn.close()

        flash("Shift updated.", "success")
        return redirect(url_for("shifts_users_page"))
