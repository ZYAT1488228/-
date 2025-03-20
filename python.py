import serial
import time
import sqlite3
from datetime import datetime, timedelta
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
import os
import uuid  # Добавим импорт библиотеки uuid

# Database file
DB_FILE = "employees.db"
LOG_FILE = "attendance_log.txt"
REPORT_DIR = "reports"

# Ensure the report directory exists
os.makedirs(REPORT_DIR, exist_ok=True)

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            card_id TEXT UNIQUE,
            employee_id TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id TEXT,
            check_in TEXT,
            check_out TEXT
        )
    """)
    conn.commit()
    conn.close()

def generate_employee_id():
    return str(uuid.uuid4())

def register_card(card_id, employee_id=None):
    if employee_id is None:
        employee_id = generate_employee_id()
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO employees (card_id, employee_id) VALUES (?, ?)", (card_id, employee_id))
        conn.commit()
        messagebox.showinfo("Success", f"Card {card_id} registered to employee {employee_id}")
    except sqlite3.IntegrityError:
        messagebox.showerror("Error", "Card already registered!")
    conn.close()

def get_employee_by_card(card_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT employee_id FROM employees WHERE card_id = ?", (card_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def round_time(time_str):
    t = datetime.strptime(time_str, "%H:%M")
    minute = (t.minute // 15) * 15
    rounded = t.replace(minute=minute, second=0)
    if t.minute % 15 >= 8:
        rounded += timedelta(minutes=15)
    return rounded.strftime("%H:%M"), time_str

def log_entry(employee_id):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    date, time_str = timestamp.split(" ")
    rounded_time, actual_time = round_time(time_str)
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM attendance WHERE employee_id = ? AND check_out IS NULL", (employee_id,))
    result = cursor.fetchone()
    if result:
        cursor.execute("UPDATE attendance SET check_out = ? WHERE id = ?", (rounded_time, result[0]))
    else:
        cursor.execute("INSERT INTO attendance (employee_id, check_in) VALUES (?, ?)", (employee_id, rounded_time))
    conn.commit()
    conn.close()
    
    with open(LOG_FILE, "a") as file:
        file.write(f"{date} {rounded_time} ({actual_time}), {employee_id}\n")
    
    log_text.insert(tk.END, f"Logged: {date} {rounded_time} ({actual_time}), {employee_id}\n")
    log_text.see(tk.END)

def generate_report():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    today = datetime.now().strftime("%Y-%m-%d")
    cursor.execute("SELECT employee_id, check_in, check_out FROM attendance WHERE check_in LIKE ?", (today + "%",))
    data = cursor.fetchall()
    conn.close()
    
    report_file = os.path.join(REPORT_DIR, f"report_{today}.txt")
    with open(report_file, "w") as file:
        file.write("Daily Attendance Report\n")
        file.write("======================\n")
        for row in data:
            emp_id, check_in, check_out = row
            work_time = "--"
            if check_out:
                in_time = datetime.strptime(check_in, "%H:%M")
                out_time = datetime.strptime(check_out, "%H:%M")
                work_time = str(out_time - in_time)
            file.write(f"Employee: {emp_id}, In: {check_in}, Out: {check_out}, Worked: {work_time}\n")
    messagebox.showinfo("Report", f"Daily report generated: {report_file}")

def read_rfid(port="/dev/ttyUSB0", baudrate=9600):
    ser = None  # Initialize ser to None
    try:
        ser = serial.Serial(port, baudrate, timeout=1)
        print("Waiting for RFID scan...")
        while True:
            rfid_data = ser.readline().decode('utf-8').strip()
            if rfid_data:
                employee_id = get_employee_by_card(rfid_data)
                if employee_id:
                    messagebox.showinfo("Access Granted", f"Access granted to Employee ID: {employee_id}")
                    log_entry(employee_id)
                else:
                    messagebox.showwarning("Unregistered Card", "Unregistered card detected! Please register.")
                    register_card(rfid_data)  # Убираем запрос ID сотрудника
    except Exception as e:
        messagebox.showerror("Error", f"Error: {e}")
    finally:
        if ser:  # Check if ser is not None
            ser.close()

def start_rfid_thread():
    import threading
    threading.Thread(target=read_rfid, daemon=True).start()

def show_employee_info():
    emp_id = simpledialog.askstring("Employee Info", "Enter employee ID:")
    if emp_id:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT check_in, check_out FROM attendance WHERE employee_id = ?", (emp_id,))
        data = cursor.fetchall()
        conn.close()
        
        info_window = tk.Toplevel(root)
        info_window.title(f"Employee {emp_id} Info")
        
        text = tk.Text(info_window, wrap=tk.WORD)
        text.pack(expand=True, fill=tk.BOTH)
        
        text.insert(tk.END, f"Attendance for Employee ID: {emp_id}\n")
        text.insert(tk.END, "=============================\n")
        total_hours = timedelta()
        for check_in, check_out in data:
            if check_out:
                in_time = datetime.strptime(check_in, "%H:%M")
                out_time = datetime.strptime(check_out, "%H:%M")
                work_time = out_time - in_time
                total_hours += work_time
                text.insert(tk.END, f"In: {check_in}, Out: {check_out}, Worked: {work_time}\n")
            else:
                text.insert(tk.END, f"In: {check_in}, Out: --, Worked: --\n")
        text.insert(tk.END, f"\nTotal hours worked this month: {total_hours}\n")

def show_today_attendance():
    today = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT employee_id, check_in, check_out FROM attendance WHERE check_in LIKE ?", (today + "%",))
    data = cursor.fetchall()
    conn.close()
    
    attendance_window = tk.Toplevel(root)
    attendance_window.title(f"Attendance for {today}")
    
    text = tk.Text(attendance_window, wrap=tk.WORD)
    text.pack(expand=True, fill=tk.BOTH)
    
    text.insert(tk.END, f"Attendance for {today}\n")
    text.insert(tk.END, "=============================\n")
    for row in data:
        emp_id, check_in, check_out = row
        work_time = "--"
        if check_out:
            in_time = datetime.strptime(check_in, "%H:%M")
            out_time = datetime.strptime(check_out, "%H:%M")
            work_time = str(out_time - in_time)
        text.insert(tk.END, f"Employee: {emp_id}, In: {check_in}, Out: {check_out}, Worked: {work_time}\n")

def main():
    global root, log_text
    init_db()
    
    root = tk.Tk()
    root.title("RFID Attendance System")
    
    tk.Button(root, text="Start RFID Reader", command=start_rfid_thread).pack(pady=10)
    tk.Button(root, text="Generate Report", command=generate_report).pack(pady=10)
    tk.Button(root, text="Employee Info", command=show_employee_info).pack(pady=10)
    
    log_text = tk.Text(root, wrap=tk.WORD, height=10)
    log_text.pack(expand=True, fill=tk.BOTH)
    
    show_today_attendance()  # Вызовем функцию для отображения сегодняшней посещаемости
    
    root.mainloop()

if __name__ == "__main__":
    main()
