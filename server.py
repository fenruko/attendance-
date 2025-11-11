# server.py - Server Only Version
import requests
import json
import os
import sys
from datetime import datetime, timedelta
import base64
import webbrowser
import socket
import threading
import time
import pandas as pd
import io
import hashlib
import secrets
from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
import pystray
from PIL import Image, ImageDraw
import schedule
import matplotlib.pyplot as plt
from dateutil import parser
import numpy as np

# ==================== SERVER CODE ====================

app = Flask(__name__)
CORS(app)
server_thread = None
running = True

# Database setup
def init_db():
    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    
    # Create staff table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS staff (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        staff_code TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        hourly_rate REAL DEFAULT 0.0,
        shift_id INTEGER,
        FOREIGN KEY (shift_id) REFERENCES shifts (id)
    )
    ''')
    
    # Create attendance table (updated)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        staff_code TEXT NOT NULL,
        clock_in TIMESTAMP NOT NULL,
        clock_out TIMESTAMP,
        notes TEXT,
        session_type TEXT DEFAULT 'work',
        FOREIGN KEY (staff_code) REFERENCES staff (staff_code)
    )
    ''')
    
    # Create admin settings table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS admin_settings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        setting_key TEXT UNIQUE NOT NULL,
        setting_value TEXT
    )
    ''')
    
    # Create audit_log table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        admin_password TEXT NOT NULL,
        action_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        action_details TEXT NOT NULL
    )
    ''')

    # Create shifts table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS shifts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        start_time TEXT NOT NULL,
        end_time TEXT NOT NULL
    )
    ''')

    # Create holidays table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS holidays (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        name TEXT NOT NULL,
        paid BOOLEAN DEFAULT 1
    )
    ''')

    # Create leave_requests table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS leave_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        staff_code TEXT NOT NULL,
        start_date TEXT NOT NULL,
        end_date TEXT NOT NULL,
        reason TEXT,
        status TEXT DEFAULT 'pending',
        approved_by TEXT,
        approval_date TEXT,
        FOREIGN KEY (staff_code) REFERENCES staff (staff_code)
    )
    ''')

    # Check if admin password exists, if not create default
    cursor.execute('SELECT * FROM admin_settings WHERE setting_key = "admin_password"')
    if not cursor.fetchone():
        default_password = hashlib.sha256("admin123".encode()).hexdigest()
        cursor.execute('INSERT INTO admin_settings (setting_key, setting_value) VALUES (?, ?)', 
                      ("admin_password", default_password))
    
    # Check if default shift exists, if not create one
    cursor.execute('SELECT * FROM shifts')
    if not cursor.fetchone():
        cursor.execute('INSERT INTO shifts (name, start_time, end_time) VALUES (?, ?, ?)', 
                      ("Default Shift", "09:00", "17:00"))
    
    # CRM credentials table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS crm_credentials (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        url TEXT,
        db TEXT,
        username TEXT,
        password TEXT
    )
    ''')

        # CRM Leads
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS crm_leads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        phone TEXT,
        status TEXT DEFAULT 'New',
        target TEXT,
        assigned_to TEXT,           -- staff_code
        notes TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # CRM Targets (master list)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS crm_targets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL
    )
    ''')

    # Insert a few default targets (run once)
    cursor.execute('''
    INSERT OR IGNORE INTO crm_targets (name) VALUES 
    ('Sales'), ('Marketing'), ('Support'), ('Technical'), ('VIP')
    ''')


    conn.commit()
    conn.close()

# Helper function to log admin actions
def log_admin_action(password, details):
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO audit_log (admin_password, action_details) VALUES (?, ?)', 
                  (hashed_password, f"{datetime.now()}: {details}"))
    conn.commit()
    conn.close()

# ================================
# CRM ADMIN ENDPOINTS
# ================================

@app.route('/api/crm_get_leads', methods=['POST'])
def crm_get_leads():
    data = request.get_json() or {}
    if not _verify_admin(data.get('password', '')):
        return jsonify(success=False, message="Unauthorized"), 401

    conn = get_db()
    c = conn.cursor()
    c.execute("""
        SELECT l.*, s.name as staff_name 
        FROM crm_leads l 
        LEFT JOIN staff s ON l.assigned_to = s.staff_code 
        ORDER BY l.created_at DESC
    """)
    leads = [dict(row) for row in c.fetchall()]
    conn.close()
    return jsonify(success=True, leads=leads)


@app.route('/api/crm_get_lead', methods=['POST'])
def crm_get_lead():
    data = request.get_json() or {}
    if not _verify_admin(data.get('password', '')):
        return jsonify(success=False, message="Unauthorized"), 401

    lead_id = data.get('lead_id')
    if not lead_id:
        return jsonify(success=False, message="lead_id required"), 400

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM crm_leads WHERE id = ?", (lead_id,))
    lead = c.fetchone()
    conn.close()
    if not lead:
        return jsonify(success=False, message="Lead not found"), 404
    return jsonify(success=True, lead=dict(lead))


@app.route('/api/crm_add_lead', methods=['POST'])
def crm_add_lead():
    data = request.get_json() or {}
    if not _verify_admin(data.get('password', '')):
        return jsonify(success=False, message="Unauthorized"), 401

    required = ['name']
    if not all(k in data for k in required):
        return jsonify(success=False, message="Missing fields"), 400

    conn = get_db()
    c = conn.cursor()
    c.execute("""
        INSERT INTO crm_leads 
        (name, phone, status, target, assigned_to, notes)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        data['name'],
        data.get('phone'),
        data.get('status', 'New'),
        data.get('target'),
        data.get('assigned_to'),
        data.get('notes')
    ))
    conn.commit()
    conn.close()
    return jsonify(success=True, message="Lead added")

# DB helper (row_factory = dict)
def get_db():
    conn = sqlite3.connect('attendance.db')
    conn.row_factory = sqlite3.Row
    return conn

# Central admin-password check (used by every CRM route)
def _verify_admin(pw):
    if not pw:
        return False
    hashed = hashlib.sha256(pw.encode()).hexdigest()
    conn = sqlite3.connect('attendance.db')
    cur = conn.cursor()
    cur.execute("SELECT setting_value FROM admin_settings WHERE setting_key = 'admin_password'")
    row = cur.fetchone()
    conn.close()
    return row and row[0] == hashed

@app.route('/api/admin_verify', methods=['POST'])
def admin_verify():
    try:
        data = request.get_json()
        password = data.get('password', '').strip()

        # CHANGE THIS TO YOUR REAL ADMIN PASSWORD
        ADMIN_PASSWORD = "admin123"  # ← Set your password here

        if password == ADMIN_PASSWORD:
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "message": "Invalid password"}), 401
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    
@app.route('/api/crm_update_lead', methods=['POST'])
def crm_update_lead():
    data = request.get_json() or {}
    if not _verify_admin(data.get('password', '')):
        return jsonify(success=False, message="Unauthorized"), 401

    lead_id = data.get('lead_id')
    if not lead_id:
        return jsonify(success=False, message="lead_id required"), 400

    conn = get_db()
    c = conn.cursor()
    c.execute("""
        UPDATE crm_leads SET
        name = ?, phone = ?, status = ?, target = ?, assigned_to = ?, notes = ?
        WHERE id = ?
    """, (
        data.get('name'),
        data.get('phone'),
        data.get('status'),
        data.get('target'),
        data.get('assigned_to'),
        data.get('notes'),
        lead_id
    ))
    conn.commit()
    conn.close()
    return jsonify(success=True, message="Lead updated")


@app.route('/api/crm_delete_lead', methods=['POST'])
def crm_delete_lead():
    data = request.get_json() or {}
    if not _verify_admin(data.get('password', '')):
        return jsonify(success=False, message="Unauthorized"), 401

    lead_id = data.get('lead_id')
    if not lead_id:
        return jsonify(success=False, message="lead_id required"), 400

    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM crm_leads WHERE id = ?", (lead_id,))
    conn.commit()
    conn.close()
    return jsonify(success=True, message="Lead deleted")


@app.route('/api/crm_update_target', methods=['POST'])
def crm_update_target():
    data = request.get_json() or {}
    if not _verify_admin(data.get('password', '')):
        return jsonify(success=False, message="Unauthorized"), 401

    lead_id = data.get('lead_id')
    target = data.get('target')
    if not lead_id or not target:
        return jsonify(success=False, message="lead_id and target required"), 400

    conn = get_db()
    c = conn.cursor()
    # Auto-add new target if it does not exist
    c.execute("INSERT OR IGNORE INTO crm_targets (name) VALUES (?)", (target,))
    c.execute("UPDATE crm_leads SET target = ? WHERE id = ?", (target, lead_id))
    conn.commit()
    conn.close()
    return jsonify(success=True, message="Target updated")


@app.route('/api/crm_get_targets', methods=['POST'])
def crm_get_targets():
    data = request.get_json() or {}
    if not _verify_admin(data.get('password', '')):
        return jsonify(success=False, message="Unauthorized"), 401

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT name FROM crm_targets ORDER BY name")
    targets = [row[0] for row in c.fetchall()]
    conn.close()
    return jsonify(success=True, targets=targets)

# Get active session for a staff member
@app.route('/api/get_active_session', methods=['POST'])
def get_active_session():
    data = request.json
    staff_code = data.get('staff_code')

    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT * FROM attendance 
    WHERE staff_code = ? AND clock_out IS NULL
    ORDER BY clock_in DESC LIMIT 1
    ''', (staff_code,))
    active_session = cursor.fetchone()
    
    conn.close()

    if active_session:
        # session_type is the 6th column (index 5) in the attendance table
        return jsonify({
            "success": True, 
            "is_active": True, 
            "session_type": active_session[5]
        })
    else:
        return jsonify({"success": True, "is_active": False})

# Clock in endpoint
@app.route('/api/clock_in', methods=['POST'])
def clock_in():
    data = request.json
    staff_code = data.get('staff_code')
    
    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    
    # Check if staff exists
    cursor.execute('SELECT * FROM staff WHERE staff_code = ?', (staff_code,))
    staff = cursor.fetchone()
    
    if not staff:
        conn.close()
        return jsonify({"success": False, "message": "Invalid staff code"})
    
    # Check if already clocked in
    cursor.execute('''
    SELECT * FROM attendance 
    WHERE staff_code = ? AND clock_out IS NULL
    ORDER BY clock_in DESC LIMIT 1
    ''', (staff_code,))
    active_session = cursor.fetchone()
    
    if active_session:
        conn.close()
        return jsonify({"success": False, "message": "Already clocked in"})
    
    # Clock in
    cursor.execute('''
    INSERT INTO attendance (staff_code, clock_in, session_type)
    VALUES (?, ?, ?)
    ''', (staff_code, datetime.now(), 'work'))
    
    conn.commit()
    conn.close()
    
    return jsonify({"success": True, "message": "Clocked in successfully"})

# Clock out endpoint
@app.route('/api/clock_out', methods=['POST'])
def clock_out():
    data = request.json
    staff_code = data.get('staff_code')
    notes = data.get('notes', '')
    
    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    
    # Get the active session
    cursor.execute('''
    SELECT * FROM attendance 
    WHERE staff_code = ? AND clock_out IS NULL
    ORDER BY clock_in DESC LIMIT 1
    ''', (staff_code,))
    active_session = cursor.fetchone()
    
    if not active_session:
        conn.close()
        return jsonify({"success": False, "message": "No active session found"})
    
    # Clock out
    cursor.execute('''
    UPDATE attendance 
    SET clock_out = ?, notes = ?
    WHERE id = ?
    ''', (datetime.now(), notes, active_session[0]))
    
    conn.commit()
    conn.close()
    
    return jsonify({"success": True, "message": "Clocked out successfully"})

# Clock out for break
@app.route('/api/clock_break', methods=['POST'])
def clock_break():
    data = request.json
    staff_code = data.get('staff_code')
    
    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    
    # Close the current 'work' session
    cursor.execute('''
    UPDATE attendance 
    SET clock_out = ?
    WHERE staff_code = ? AND clock_out IS NULL AND session_type = 'work'
    ''', (datetime.now(), staff_code))
    
    # Start a new 'break' session
    cursor.execute('''
    INSERT INTO attendance (staff_code, clock_in, session_type)
    VALUES (?, ?, ?)
    ''', (staff_code, datetime.now(), 'break'))
    
    conn.commit()
    conn.close()
    
    return jsonify({"success": True, "message": "Started break successfully"})

# Clock in from break
@app.route('/api/clock_return_from_break', methods=['POST'])
def clock_return_from_break():
    data = request.json
    staff_code = data.get('staff_code')
    
    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    
    # Close the 'break' session
    cursor.execute('''
    UPDATE attendance 
    SET clock_out = ?
    WHERE staff_code = ? AND clock_out IS NULL AND session_type = 'break'
    ''', (datetime.now(), staff_code))
    
    # Start a new 'work' session
    cursor.execute('''
    INSERT INTO attendance (staff_code, clock_in, session_type)
    VALUES (?, ?, ?)
    ''', (staff_code, datetime.now(), 'work'))
    
    conn.commit()
    conn.close()
    
    return jsonify({"success": True, "message": "Returned from break successfully"})

# Admin login
@app.route('/api/admin_login', methods=['POST'])
def admin_login():
    data = request.json
    password = data.get('password')
    
    if not password:
        return jsonify({"success": False, "message": "Password required"})
    
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    
    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM admin_settings WHERE setting_key = "admin_password"')
    result = cursor.fetchone()
    conn.close()
    
    if result and result[2] == hashed_password:
        log_admin_action(password, "Admin logged in")
        return jsonify({"success": True, "message": "Login successful"})
    else:
        return jsonify({"success": False, "message": "Invalid password"})

# Get attendance data with date range
@app.route('/api/get_attendance', methods=['POST'])
def get_attendance():
    data = request.json
    password = data.get('password')
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    
    if not password:
        return jsonify({"success": False, "message": "Password required"})
    
    # Verify admin password
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM admin_settings WHERE setting_key = "admin_password"')
    result = cursor.fetchone()
    
    if not result or result[2] != hashed_password:
        conn.close()
        return jsonify({"success": False, "message": "Invalid password"})
    
    # Parse dates
    if start_date:
        start_date = parser.parse(start_date)
    else:
        start_date = datetime(1970, 1, 1)
    
    if end_date:
        end_date = parser.parse(end_date)
        # Add one day to include the end date
        end_date = end_date + timedelta(days=1)
    else:
        end_date = datetime.now()
    
    # Get attendance data
    cursor.execute('''
    SELECT a.id, a.staff_code, s.name, a.clock_in, a.clock_out, a.notes, s.hourly_rate, a.session_type
    FROM attendance a
    JOIN staff s ON a.staff_code = s.staff_code
    WHERE a.clock_in >= ? AND a.clock_in < ?
    ORDER BY a.clock_in DESC
    ''', (start_date, end_date))
    
    attendance_data = cursor.fetchall()
    
    # Calculate total hours and earnings for each staff member
    staff_summary = {}
    for record in attendance_data:
        staff_code = record[1]
        name = record[2]
        clock_in = datetime.fromisoformat(record[3])
        clock_out = datetime.fromisoformat(record[4]) if record[4] else datetime.now()
        hourly_rate = record[6] if record[6] else 0
        session_type = record[7]

        hours = (clock_out - clock_in).total_seconds() / 3600
        
        # Only calculate earnings for 'work' sessions
        if session_type == 'work':
            earnings = hours * hourly_rate
        else:
            earnings = 0
        
        if staff_code not in staff_summary:
            staff_summary[staff_code] = {
                'name': name,
                'total_hours': 0,
                'total_earnings': 0,
                'hourly_rate': hourly_rate
            }
        
        staff_summary[staff_code]['total_hours'] += hours
        staff_summary[staff_code]['total_earnings'] += earnings
    
    conn.close()
    
    # Format data for response
    formatted_data = []
    for record in attendance_data:
        clock_in = datetime.fromisoformat(record[3])
        clock_out = datetime.fromisoformat(record[4]) if record[4] else None
        hours = (clock_out - clock_in).total_seconds() / 3600 if clock_out else 0
        
        formatted_data.append({
            'id': record[0],
            'staff_code': record[1],
            'name': record[2],
            'clock_in': record[3],
            'clock_out': record[4] if record[4] else 'Active',
            'notes': record[5],
            'hours': round(hours, 2),
            'hourly_rate': record[6] if record[6] else 0,
            'earnings': round(hours * (record[6] if record[6] else 0), 2) if record[7] == 'work' else 0,
            'session_type': record[7]
        })
    
    return jsonify({
        "success": True,
        "data": formatted_data,
        "summary": staff_summary
    })

# Get analytics data
@app.route('/api/get_analytics', methods=['POST'])
def get_analytics():
    data = request.json
    password = data.get('password')
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    
    if not password:
        return jsonify({"success": False, "message": "Password required"})
    
    # Verify admin password
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM admin_settings WHERE setting_key = "admin_password"')
    result = cursor.fetchone()
    
    if not result or result[2] != hashed_password:
        conn.close()
        return jsonify({"success": False, "message": "Invalid password"})
    
    # Parse dates
    if start_date:
        start_date = parser.parse(start_date)
    else:
        start_date = datetime.now() - timedelta(days=30)
    
    if end_date:
        end_date = parser.parse(end_date)
        # Add one day to include the end date
        end_date = end_date + timedelta(days=1)
    else:
        end_date = datetime.now()
    
    # Get daily attendance data
    cursor.execute('''
    SELECT DATE(clock_in) as date, COUNT(*) as count
    FROM attendance
    WHERE clock_in >= ? AND clock_in < ?
    GROUP BY DATE(clock_in)
    ORDER BY date
    ''', (start_date, end_date))
    
    daily_data = cursor.fetchall()
    
    # Get staff attendance summary
    cursor.execute('''
    SELECT s.staff_code, s.name, COUNT(a.id) as days, 
           SUM(CASE WHEN a.session_type = 'work' THEN 
               (julianday(a.clock_out) - julianday(a.clock_in)) * 24 
               ELSE 0 END) as total_hours
    FROM staff s
    LEFT JOIN attendance a ON s.staff_code = a.staff_code
    WHERE a.clock_in >= ? AND a.clock_in < ?
    GROUP BY s.staff_code, s.name
    ORDER BY total_hours DESC
    ''', (start_date, end_date))
    
    staff_data = cursor.fetchall()
    
    conn.close()
    
    return jsonify({
        "success": True,
        "daily_data": daily_data,
        "staff_data": staff_data
    })

# Get shifts
@app.route('/api/get_shifts', methods=['POST'])
def get_shifts():
    data = request.json
    password = data.get('password')
    
    if not password:
        return jsonify({"success": False, "message": "Password required"})
    
    # Verify admin password
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM admin_settings WHERE setting_key = "admin_password"')
    result = cursor.fetchone()
    
    if not result or result[2] != hashed_password:
        conn.close()
        return jsonify({"success": False, "message": "Invalid password"})
    
    # Get shifts data
    cursor.execute('SELECT * FROM shifts')
    shifts_data = cursor.fetchall()
    
    conn.close()
    
    # Format data for response
    formatted_data = []
    for record in shifts_data:
        formatted_data.append({
            'id': record[0],
            'name': record[1],
            'start_time': record[2],
            'end_time': record[3]
        })
    
    return jsonify({
        "success": True,
        "data": formatted_data
    })

# Add shift
@app.route('/api/add_shift', methods=['POST'])
def add_shift():
    data = request.json
    password = data.get('password')
    name = data.get('name')
    start_time = data.get('start_time')
    end_time = data.get('end_time')
    
    if not password or not name or not start_time or not end_time:
        return jsonify({"success": False, "message": "Missing required fields"})
    
    # Verify admin password
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM admin_settings WHERE setting_key = "admin_password"')
    result = cursor.fetchone()
    
    if not result or result[2] != hashed_password:
        conn.close()
        return jsonify({"success": False, "message": "Invalid password"})
    
    # Add shift
    cursor.execute('''
    INSERT INTO shifts (name, start_time, end_time)
    VALUES (?, ?, ?)
    ''', (name, start_time, end_time))
    
    conn.commit()
    conn.close()
    
    log_admin_action(password, f"Added new shift: {name}")
    return jsonify({"success": True, "message": "Shift added successfully"})

# Get holidays
@app.route('/api/get_holidays', methods=['POST'])
def get_holidays():
    data = request.json
    password = data.get('password')
    
    if not password:
        return jsonify({"success": False, "message": "Password required"})
    
    # Verify admin password
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM admin_settings WHERE setting_key = "admin_password"')
    result = cursor.fetchone()
    
    if not result or result[2] != hashed_password:
        conn.close()
        return jsonify({"success": False, "message": "Invalid password"})
    
    # Get holidays data
    cursor.execute('SELECT * FROM holidays ORDER BY date')
    holidays_data = cursor.fetchall()
    
    conn.close()
    
    # Format data for response
    formatted_data = []
    for record in holidays_data:
        formatted_data.append({
            'id': record[0],
            'date': record[1],
            'name': record[2],
            'paid': bool(record[3])
        })
    
    return jsonify({
        "success": True,
        "data": formatted_data
    })

# Add holiday
@app.route('/api/add_holiday', methods=['POST'])
def add_holiday():
    data = request.json
    password = data.get('password')
    date = data.get('date')
    name = data.get('name')
    paid = data.get('paid', True)
    
    if not password or not date or not name:
        return jsonify({"success": False, "message": "Missing required fields"})
    
    # Verify admin password
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM admin_settings WHERE setting_key = "admin_password"')
    result = cursor.fetchone()
    
    if not result or result[2] != hashed_password:
        conn.close()
        return jsonify({"success": False, "message": "Invalid password"})
    
    # Add holiday
    cursor.execute('''
    INSERT INTO holidays (date, name, paid)
    VALUES (?, ?, ?)
    ''', (date, name, paid))
    
    conn.commit()
    conn.close()
    
    log_admin_action(password, f"Added new holiday: {name} on {date}")
    return jsonify({"success": True, "message": "Holiday added successfully"})

# Get leave requests
@app.route('/api/get_leave_requests', methods=['POST'])
def get_leave_requests():
    data = request.json
    password = data.get('password')
    
    if not password:
        return jsonify({"success": False, "message": "Password required"})
    
    # Verify admin password
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM admin_settings WHERE setting_key = "admin_password"')
    result = cursor.fetchone()
    
    if not result or result[2] != hashed_password:
        conn.close()
        return jsonify({"success": False, "message": "Invalid password"})
    
    # Get leave requests data
    cursor.execute('''
    SELECT lr.id, lr.staff_code, s.name, lr.start_date, lr.end_date, lr.reason, lr.status, lr.approved_by, lr.approval_date
    FROM leave_requests lr
    JOIN staff s ON lr.staff_code = s.staff_code
    ORDER BY lr.id DESC
    ''')
    leave_data = cursor.fetchall()
    
    conn.close()
    
    # Format data for response
    formatted_data = []
    for record in leave_data:
        formatted_data.append({
            'id': record[0],
            'staff_code': record[1],
            'name': record[2],
            'start_date': record[3],
            'end_date': record[4],
            'reason': record[5],
            'status': record[6],
            'approved_by': record[7],
            'approval_date': record[8]
        })
    
    return jsonify({
        "success": True,
        "data": formatted_data
    })

# Submit leave request
@app.route('/api/submit_leave_request', methods=['POST'])
def submit_leave_request():
    data = request.json
    staff_code = data.get('staff_code')
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    reason = data.get('reason', '')
    
    if not staff_code or not start_date or not end_date:
        return jsonify({"success": False, "message": "Missing required fields"})
    
    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    
    # Check if staff exists
    cursor.execute('SELECT * FROM staff WHERE staff_code = ?', (staff_code,))
    staff = cursor.fetchone()
    
    if not staff:
        conn.close()
        return jsonify({"success": False, "message": "Invalid staff code"})
    
    # Add leave request
    cursor.execute('''
    INSERT INTO leave_requests (staff_code, start_date, end_date, reason)
    VALUES (?, ?, ?, ?)
    ''', (staff_code, start_date, end_date, reason))
    
    conn.commit()
    conn.close()
    
    return jsonify({"success": True, "message": "Leave request submitted successfully"})

# Approve/reject leave request
@app.route('/api/update_leave_request', methods=['POST'])
def update_leave_request():
    data = request.json
    password = data.get('password')
    request_id = data.get('request_id')
    status = data.get('status')  # 'approved' or 'rejected'
    
    if not password or not request_id or not status:
        return jsonify({"success": False, "message": "Missing required fields"})
    
    # Verify admin password
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM admin_settings WHERE setting_key = "admin_password"')
    result = cursor.fetchone()
    
    if not result or result[2] != hashed_password:
        conn.close()
        return jsonify({"success": False, "message": "Invalid password"})
    
    # Get request details for logging
    cursor.execute('''
    SELECT lr.staff_code, s.name, lr.start_date, lr.end_date
    FROM leave_requests lr
    JOIN staff s ON lr.staff_code = s.staff_code
    WHERE lr.id = ?
    ''', (request_id,))
    request_data = cursor.fetchone()
    
    if not request_data:
        conn.close()
        return jsonify({"success": False, "message": "Request not found"})
    
    # Update request
    cursor.execute('''
    UPDATE leave_requests 
    SET status = ?, approved_by = ?, approval_date = ?
    WHERE id = ?
    ''', (status, "admin", datetime.now().strftime('%Y-%m-%d %H:%M:%S'), request_id))
    
    conn.commit()
    conn.close()
    
    # Log the action
    log_details = f"Leave request {status} for {request_data[1]} ({request_data[0]}) "
    log_details += f"from {request_data[2]} to {request_data[3]}"
    log_admin_action(password, log_details)
    
    return jsonify({"success": True, "message": f"Leave request {status} successfully"})

# Add this endpoint to support both GET and POST requests for staff data
@app.route('/api/get_staff_data', methods=['GET', 'POST'])
def get_staff_data():
    # This is just an alias to the existing get_staff function
    return get_staff()

# Admin edit attendance
@app.route('/api/edit_attendance', methods=['POST'])
def edit_attendance():
    data = request.json
    password = data.get('password')
    record_id = data.get('record_id')
    new_clock_in = data.get('clock_in')
    new_clock_out = data.get('clock_out')
    
    if not all([password, record_id]):
        return jsonify({"success": False, "message": "Missing required fields"})

    # Verify admin password
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM admin_settings WHERE setting_key = "admin_password"')
    result = cursor.fetchone()
    
    if not result or result[2] != hashed_password:
        conn.close()
        return jsonify({"success": False, "message": "Invalid password"})

    # Get original data for logging
    cursor.execute('SELECT staff_code, clock_in, clock_out FROM attendance WHERE id = ?', (record_id,))
    original_data = cursor.fetchone()
    if not original_data:
        conn.close()
        return jsonify({"success": False, "message": "Record not found"})

    # Update the record
    cursor.execute('''
    UPDATE attendance 
    SET clock_in = ?, clock_out = ?
    WHERE id = ?
    ''', (new_clock_in, new_clock_out, record_id))
    
    conn.commit()
    conn.close()

    # Log the action
    log_details = f"Edited attendance record ID {record_id} for {original_data[0]}. "
    log_details += f"Clock-in changed from {original_data[1]} to {new_clock_in}. "
    log_details += f"Clock-out changed from {original_data[2]} to {new_clock_out}."
    log_admin_action(password, log_details)

    return jsonify({"success": True, "message": "Attendance record updated successfully"})

# Admin close open session
@app.route('/api/close_open_session', methods=['POST'])
def close_open_session():
    data = request.json
    password = data.get('password')
    staff_code = data.get('staff_code')
    clock_out_time = data.get('clock_out_time') # Expected format: YYYY-MM-DD HH:MM:SS

    if not all([password, staff_code, clock_out_time]):
        return jsonify({"success": False, "message": "Missing required fields"})

    # Verify admin password
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM admin_settings WHERE setting_key = "admin_password"')
    result = cursor.fetchone()
    
    if not result or result[2] != hashed_password:
        conn.close()
        return jsonify({"success": False, "message": "Invalid password"})

    # Find the open session
    cursor.execute('''
    SELECT id, clock_in FROM attendance 
    WHERE staff_code = ? AND clock_out IS NULL
    ORDER BY clock_in DESC LIMIT 1
    ''', (staff_code,))
    open_session = cursor.fetchone()

    if not open_session:
        conn.close()
        return jsonify({"success": False, "message": "No open session found for this staff member"})

    # Close the session
    cursor.execute('''
    UPDATE attendance 
    SET clock_out = ?
    WHERE id = ?
    ''', (clock_out_time, open_session[0]))
    
    conn.commit()
    conn.close()

    # Log the action
    log_details = f"Manually closed open session for {staff_code}. "
    log_details += f"Session ID {open_session[0]} clocked out at {clock_out_time}."
    log_admin_action(password, log_details)

    return jsonify({"success": True, "message": "Open session closed successfully"})

# Get staff list
@app.route('/api/get_staff', methods=['POST'])
def get_staff():
    data = request.json
    password = data.get('password')
    
    if not password:
        return jsonify({"success": False, "message": "Password required"})
    
    # Verify admin password
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM admin_settings WHERE setting_key = "admin_password"')
    result = cursor.fetchone()
    
    if not result or result[2] != hashed_password:
        conn.close()
        return jsonify({"success": False, "message": "Invalid password"})
    
    # Get staff data
    cursor.execute('''
    SELECT s.id, s.staff_code, s.name, s.hourly_rate, sh.name as shift_name
    FROM staff s
    LEFT JOIN shifts sh ON s.shift_id = sh.id
    ''')
    staff_data = cursor.fetchall()
    
    conn.close()
    
    # Format data for response
    formatted_data = []
    for record in staff_data:
        formatted_data.append({
            'id': record[0],
            'staff_code': record[1],
            'name': record[2],
            'hourly_rate': record[3],
            'shift_name': record[4] if record[4] else "No Shift"
        })
    
    return jsonify({
        "success": True,
        "data": formatted_data
    })

# Add staff
@app.route('/api/add_staff', methods=['POST'])
def add_staff():
    data = request.json
    password = data.get('password')
    staff_code = data.get('staff_code')
    name = data.get('name')
    hourly_rate = data.get('hourly_rate', 0)
    shift_id = data.get('shift_id')
    
    if not password or not staff_code or not name:
        return jsonify({"success": False, "message": "Missing required fields"})
    
    # Verify admin password
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM admin_settings WHERE setting_key = "admin_password"')
    result = cursor.fetchone()
    
    if not result or result[2] != hashed_password:
        conn.close()
        return jsonify({"success": False, "message": "Invalid password"})
    
    # Check if staff already exists
    cursor.execute('SELECT * FROM staff WHERE staff_code = ?', (staff_code,))
    if cursor.fetchone():
        conn.close()
        return jsonify({"success": False, "message": "Staff code already exists"})
    
    # Add staff
    cursor.execute('''
    INSERT INTO staff (staff_code, name, hourly_rate, shift_id)
    VALUES (?, ?, ?, ?)
    ''', (staff_code, name, hourly_rate, shift_id))
    
    conn.commit()
    conn.close()
    
    log_admin_action(password, f"Added new staff member: {name} ({staff_code})")
    return jsonify({"success": True, "message": "Staff added successfully"})

# Update staff
@app.route('/api/update_staff', methods=['POST'])
def update_staff():
    data = request.json
    password = data.get('password')
    staff_code = data.get('staff_code')
    name = data.get('name')
    hourly_rate = data.get('hourly_rate', 0)
    shift_id = data.get('shift_id')
    
    if not password or not staff_code:
        return jsonify({"success": False, "message": "Missing required fields"})
    
    # Verify admin password
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM admin_settings WHERE setting_key = "admin_password"')
    result = cursor.fetchone()
    
    if not result or result[2] != hashed_password:
        conn.close()
        return jsonify({"success": False, "message": "Invalid password"})
    
    # Update staff
    if name:
        cursor.execute('''
        UPDATE staff SET name = ?, hourly_rate = ?, shift_id = ?
        WHERE staff_code = ?
        ''', (name, hourly_rate, shift_id, staff_code))
    else:
        cursor.execute('''
        UPDATE staff SET hourly_rate = ?, shift_id = ?
        WHERE staff_code = ?
        ''', (hourly_rate, shift_id, staff_code))
    
    conn.commit()
    conn.close()
    
    log_admin_action(password, f"Updated staff member: {staff_code}")
    return jsonify({"success": True, "message": "Staff updated successfully"})

# Delete staff
@app.route('/api/delete_staff', methods=['POST'])
def delete_staff():
    data = request.json
    password = data.get('password')
    staff_code = data.get('staff_code')
    
    if not password or not staff_code:
        return jsonify({"success": False, "message": "Missing required fields"})
    
    # Verify admin password
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM admin_settings WHERE setting_key = "admin_password"')
    result = cursor.fetchone()
    
    if not result or result[2] != hashed_password:
        conn.close()
        return jsonify({"success": False, "message": "Invalid password"})
    
    # Delete staff
    cursor.execute('DELETE FROM staff WHERE staff_code = ?', (staff_code,))
    
    conn.commit()
    conn.close()
    
    log_admin_action(password, f"Deleted staff member: {staff_code}")
    return jsonify({"success": True, "message": "Staff deleted successfully"})

# Change admin password
@app.route('/api/change_admin_password', methods=['POST'])
def change_admin_password():
    data = request.json
    current_password = data.get('current_password')
    new_password = data.get('new_password')
    
    if not current_password or not new_password:
        return jsonify({"success": False, "message": "Missing required fields"})
    
    # Verify current password
    hashed_current_password = hashlib.sha256(current_password.encode()).hexdigest()
    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM admin_settings WHERE setting_key = "admin_password"')
    result = cursor.fetchone()
    
    if not result or result[2] != hashed_current_password:
        conn.close()
        return jsonify({"success": False, "message": "Invalid current password"})
    
    # Update password
    hashed_new_password = hashlib.sha256(new_password.encode()).hexdigest()
    cursor.execute('''
    UPDATE admin_settings SET setting_value = ?
    WHERE setting_key = "admin_password"
    ''', (hashed_new_password,))
    
    conn.commit()
    conn.close()
    
    log_admin_action(current_password, "Admin password changed")
    return jsonify({"success": True, "message": "Password changed successfully"})

# Get audit log
@app.route('/api/get_audit_log', methods=['POST'])
def get_audit_log():
    data = request.json
    password = data.get('password')

    if not password:
        return jsonify({"success": False, "message": "Password required"})
    
    # Verify admin password
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM admin_settings WHERE setting_key = "admin_password"')
    result = cursor.fetchone()
    
    if not result or result[2] != hashed_password:
        conn.close()
        return jsonify({"success": False, "message": "Invalid password"})

    cursor.execute('SELECT action_timestamp, action_details FROM audit_log ORDER BY action_timestamp DESC')
    log_data = cursor.fetchall()
    conn.close()

    formatted_data = [{'timestamp': row[0], 'details': row[1]} for row in log_data]

    return jsonify({"success": True, "data": formatted_data})

# Generate Excel file
@app.route('/api/generate_excel', methods=['POST'])
def generate_excel():
    data = request.json
    password = data.get('password')
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    selected_ids = data.get('selected_ids', [])
    
    if not password:
        return jsonify({"success": False, "message": "Password required"})
    
    # Verify admin password
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM admin_settings WHERE setting_key = "admin_password"')
    result = cursor.fetchone()
    
    if not result or result[2] != hashed_password:
        conn.close()
        return jsonify({"success": False, "message": "Invalid password"})
    
    # Parse dates
    if start_date:
        start_date = parser.parse(start_date)
    else:
        start_date = datetime(1970, 1, 1)
    
    if end_date:
        end_date = parser.parse(end_date)
        # Add one day to include the end date
        end_date = end_date + timedelta(days=1)
    else:
        end_date = datetime.now()
    
    # Build query
    query = '''
    SELECT a.id, a.staff_code, s.name, a.clock_in, a.clock_out, a.notes, s.hourly_rate, a.session_type
    FROM attendance a
    JOIN staff s ON a.staff_code = s.staff_code
    WHERE a.clock_in >= ? AND a.clock_in < ?
    '''
    params = [start_date, end_date]
    
    if selected_ids:
        placeholders = ','.join(['?' for _ in selected_ids])
        query += f' AND a.id IN ({placeholders})'
        params.extend(selected_ids)
    
    query += ' ORDER BY a.clock_in DESC'
    
    # Get attendance data
    cursor.execute(query, params)
    attendance_data = cursor.fetchall()
    
    conn.close()
    
    # Create DataFrame
    df = pd.DataFrame(attendance_data, columns=[
        'ID', 'Staff Code', 'Name', 'Clock In', 'Clock Out', 'Notes', 'Hourly Rate', 'Session Type'
    ])
    
    # Calculate hours and earnings
    df['Hours'] = df.apply(lambda row: 
        round((datetime.fromisoformat(row['Clock Out']) - datetime.fromisoformat(row['Clock In'])).total_seconds() / 3600, 2) 
        if row['Clock Out'] else 0, axis=1)
    df['Earnings'] = df.apply(lambda row: row['Hours'] * row['Hourly Rate'] if row['Session Type'] == 'work' else 0, axis=1)
    
    # Create Excel file in memory
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Attendance', index=False)
        
        # Get the workbook and worksheet objects
        workbook = writer.book
        worksheet = writer.sheets['Attendance']
        
        # Add some formatting
        header_format = workbook.add_format({
            'bold': True,
            'text_wrap': True,
            'valign': 'top',
            'fg_color': '#D7E4BC',
            'border': 1
        })
        
        # Apply the header format
        for col_num, value in enumerate(df.columns.values):
            worksheet.write(0, col_num, value, header_format)
        
        # Adjust column widths
        for i, col in enumerate(df.columns):
            max_len = max(
                df[col].astype(str).map(len).max(),  # len of largest item
                len(str(col))                         # len of column name/header
            )
            worksheet.set_column(i, i, min(max_len + 2, 50))  # Add a little extra space
        
        # Add a summary sheet
        summary_data = df.groupby(['Staff Code', 'Name']).agg({
            'Hours': 'sum',
            'Earnings': 'sum'
        }).reset_index()
        
        summary_data.to_excel(writer, sheet_name='Summary', index=False)
        
        # Format summary sheet
        summary_worksheet = writer.sheets['Summary']
        for col_num, value in enumerate(summary_data.columns.values):
            summary_worksheet.write(0, col_num, value, header_format)
        
        for i, col in enumerate(summary_data.columns):
            max_len = max(
                summary_data[col].astype(str).map(len).max(),
                len(str(col))
            )
            summary_worksheet.set_column(i, i, min(max_len + 2, 50))
    
    output.seek(0)
    
    # Convert to base64 for sending
    excel_data = base64.b64encode(output.read()).decode('utf-8')
    
    return jsonify({
        "success": True,
        "excel_data": excel_data,
        "filename": f"attendance_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    })

# Get server info
@app.route('/api/server_info', methods=['GET'])
def server_info():
    return jsonify({
        "success": True,
        "message": "Attendance Server is running",
        "version": "2.0.0"
    })

@app.route('/api/save_crm_credentials', methods=['POST'])
def save_crm_credentials():
    data = request.json
    url, db, username, password = data.get("url"), data.get("db"), data.get("username"), data.get("password")
    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM crm_credentials")  # only one entry
    cursor.execute("INSERT INTO crm_credentials (url, db, username, password) VALUES (?, ?, ?, ?)", (url, db, username, password))
    conn.commit(); conn.close()
    return jsonify({"success": True})

@app.route('/api/get_crm_credentials', methods=['GET'])
def get_crm_credentials():
    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    cursor.execute("SELECT url, db, username, password FROM crm_credentials LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    if not row:
        return jsonify({"success": False, "message": "No credentials found"})
    return jsonify({"success": True, "credentials": {"url": row[0], "db": row[1], "username": row[2], "password": row[3]}})

def backup_database():
    """Create a backup of the database"""
    try:
        # Create backup directory if it doesn't exist
        if not os.path.exists('backups'):
            os.makedirs('backups')
        
        # Create backup filename with timestamp
        backup_filename = f"backups/attendance_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        
        # Copy the database file
        import shutil
        shutil.copy2('attendance.db', backup_filename)
        
        print(f"Database backed up to {backup_filename}")
        
        # Keep only the last 10 backups
        backups = sorted([f for f in os.listdir('backups') if f.startswith('attendance_backup_')])
        if len(backups) > 10:
            for old_backup in backups[:-10]:
                os.remove(f"backups/{old_backup}")
                print(f"Removed old backup: {old_backup}")
    except Exception as e:
        print(f"Error backing up database: {e}")

def run_server():
    """Run the Flask server"""
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

def create_image_for_tray():
    """Create a simple image for the system tray icon"""
    # Create an image with a transparent background
    width = 64
    height = 64
    color1 = "blue"
    color2 = "white"
    
    image = Image.new('RGB', (width, height), color1)
    dc = ImageDraw.Draw(image)
    dc.rectangle(
        (width // 4, height // 4, width * 3 // 4, height * 3 // 4),
        fill=color2
    )
    dc.text(
        (width // 4, height // 4),
        "A",
        fill=color1
    )
    
    return image

def on_quit(icon, item):
    """Function to handle quitting the application"""
    global running
    running = False
    icon.stop()

def setup_system_tray():
    """Setup system tray icon"""
    image = create_image_for_tray()
    menu = pystray.Menu(
        pystray.MenuItem("Quit", on_quit)
    )
    icon = pystray.Icon("attendance", image, menu=menu)
    return icon

from crmtest import CrmFrame
import tkinter as tk
from tkinter import ttk

def launch_server_gui():
    root = tk.Tk()
    root.title("Server Control Panel")
    root.geometry("900x600")

    notebook = ttk.Notebook(root)
    notebook.pack(fill="both", expand=True)

    # Normal server info tab
    server_tab = ttk.Frame(notebook)
    notebook.add(server_tab, text="Server Monitor")
    ttk.Label(server_tab, text="Server is running...", font=("Arial", 14)).pack(pady=20)

    # CRM Tab
    crm_tab = ttk.Frame(notebook)
    notebook.add(crm_tab, text="CRM")
    crm_frame = CrmFrame(crm_tab, server_url="http://localhost:5000")
    crm_frame.pack(fill="both", expand=True)

    root.mainloop()


def main():
    """Main function to start the server"""
    # Initialize database
    init_db()
    
    # Schedule daily backup at 2 AM
    schedule.every().day.at("02:00").do(backup_database)
    
    # Start server in a separate thread
    server_thread = threading.Thread(target=run_server)
    server_thread.daemon = True
    server_thread.start()
    
    # Setup system tray
    icon = setup_system_tray()
    
    # Run the schedule checker in a separate thread
    def run_schedule():
        while running:
            schedule.run_pending()
            time.sleep(60)
    
    schedule_thread = threading.Thread(target=run_schedule)
    schedule_thread.daemon = True
    schedule_thread.start()
    
    print("Server started on http://localhost:5000")
    print("Press Ctrl+C to stop the server")
    
    # Run the system tray icon
    icon.run()

# ===================================================================
# ADD THIS CODE TO THE VERY END OF server.py
# ===================================================================

if __name__ == "__main__":
    # Initialize the database
    init_db()
    
    # Create the system tray icon
    icon = pystray.Icon(
        "attendance_server",
        create_image_for_tray(),
        "Attendance Server",
        menu=pystray.Menu(
            pystray.MenuItem("Quit", on_quit)
        )
    )

    # Start the Flask server in a separate thread
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    print("Server thread started. System tray icon should appear.")

    # Run the system tray icon
    # This will block until the "Quit" menu item is clicked
    try:
        icon.run()
    except KeyboardInterrupt:
        # Allow Ctrl+C to stop the server gracefully
        print("Server stopped by user.")
    finally:
        print("Application shutting down.")

