#!/usr/bin/env python3
"""
Quick setup script for additional PiServer features
Run this after installing the enhanced schema
"""

import sqlite3
import sys
from datetime import datetime

def get_db_path():
    """Get database path from environment or prompt"""
    import os
    db_path = os.environ.get('ATT_DB', '/var/lib/attendance/attendance.db')
    print(f"Using database: {db_path}")
    return db_path

def initialize_leave_balances(conn):
    """Initialize leave balances for all active employees for current year"""
    cur = conn.cursor()
    year = datetime.now().year
    
    print(f"\n[1/4] Initializing leave balances for {year}...")
    
    # Get all active employees
    employees = cur.execute("""
        SELECT employee_id FROM users WHERE is_active = 1
    """).fetchall()
    
    # Get all leave types
    leave_types = cur.execute("""
        SELECT id, name, max_days_per_year, accrual_rate
        FROM leave_types WHERE is_active = 1
    """).fetchall()
    
    count = 0
    for emp in employees:
        for leave_type in leave_types:
            # Check if balance already exists
            existing = cur.execute("""
                SELECT id FROM leave_balances
                WHERE employee_id = ? AND leave_type_id = ? AND year = ?
            """, (emp['employee_id'], leave_type['id'], year)).fetchone()
            
            if not existing:
                allocated = leave_type['max_days_per_year'] or 0
                cur.execute("""
                    INSERT INTO leave_balances (
                        employee_id, leave_type_id, year, allocated_days
                    ) VALUES (?, ?, ?, ?)
                """, (emp['employee_id'], leave_type['id'], year, allocated))
                count += 1
    
    conn.commit()
    print(f"   ✓ Created {count} leave balance records")

def assign_default_policies(conn):
    """Assign default overtime policy to employees without one"""
    cur = conn.cursor()
    
    print("\n[2/4] Assigning default overtime policies...")
    
    # Get default policy
    default_policy = cur.execute("""
        SELECT id FROM overtime_policies 
        WHERE name = 'Standard Policy'
        LIMIT 1
    """).fetchone()
    
    if not default_policy:
        print("   ⚠ No default policy found, skipping...")
        return
    
    # Update employees without a policy
    result = cur.execute("""
        UPDATE users
        SET overtime_policy_id = ?
        WHERE overtime_policy_id IS NULL AND is_active = 1
    """, (default_policy['id'],))
    
    conn.commit()
    print(f"   ✓ Assigned policy to {result.rowcount} employees")

def create_sample_departments(conn):
    """Ensure basic departments exist"""
    cur = conn.cursor()
    
    print("\n[3/4] Checking departments...")
    
    dept_count = cur.execute("SELECT COUNT(*) as cnt FROM departments").fetchone()['cnt']
    
    if dept_count > 0:
        print(f"   ✓ {dept_count} departments already exist")
    else:
        print("   Creating sample departments...")
        departments = [
            ("Engineering", "ENG", "Engineering and Development"),
            ("Human Resources", "HR", "Human Resources"),
            ("Operations", "OPS", "Operations"),
        ]
        
        for name, code, desc in departments:
            cur.execute("""
                INSERT OR IGNORE INTO departments (name, code, description)
                VALUES (?, ?, ?)
            """, (name, code, desc))
        
        conn.commit()
        print(f"   ✓ Created {len(departments)} sample departments")

def verify_setup(conn):
    """Verify everything is set up correctly"""
    cur = conn.cursor()
    
    print("\n[4/4] Verifying setup...")
    
    checks = [
        ("Leave types", "SELECT COUNT(*) as cnt FROM leave_types WHERE is_active = 1"),
        ("Leave balances", f"SELECT COUNT(*) as cnt FROM leave_balances WHERE year = {datetime.now().year}"),
        ("Overtime policies", "SELECT COUNT(*) as cnt FROM overtime_policies WHERE is_active = 1"),
        ("Departments", "SELECT COUNT(*) as cnt FROM departments WHERE is_active = 1"),
        ("Holidays", "SELECT COUNT(*) as cnt FROM holidays"),
    ]
    
    all_good = True
    for name, query in checks:
        count = cur.execute(query).fetchone()['cnt']
        status = "✓" if count > 0 else "✗"
        print(f"   {status} {name}: {count}")
        if count == 0:
            all_good = False
    
    return all_good

def main():
    """Main setup function"""
    print("=" * 60)
    print("  PiServer Additional Features - Setup Script")
    print("=" * 60)
    
    db_path = get_db_path()
    
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        
        # Check if schema enhancements are installed
        cur = conn.cursor()
        tables = cur.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name IN ('departments', 'leave_types', 'leave_balances')
        """).fetchall()
        
        if len(tables) < 3:
            print("\n❌ ERROR: Enhanced schema not found!")
            print("\nPlease run the schema first:")
            print("  sqlite3 $ATT_DB < schema_enhancements.sql")
            print()
            sys.exit(1)
        
        # Run initialization
        initialize_leave_balances(conn)
        assign_default_policies(conn)
        create_sample_departments(conn)
        
        # Verify
        success = verify_setup(conn)
        
        print("\n" + "=" * 60)
        if success:
            print("✅ Setup completed successfully!")
            print("\nNext steps:")
            print("  1. Add department and leave routes to server.py")
            print("  2. Assign employees to departments")
            print("  3. Test leave request workflow")
            print("  4. Configure holidays for your region")
        else:
            print("⚠️  Setup completed with warnings")
            print("   Please check the items marked with ✗ above")
        print("=" * 60)
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"\n❌ Database error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
