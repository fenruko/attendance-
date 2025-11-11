# client.py
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
import requests
import json
import os
import io  # Added this import
from datetime import datetime, timedelta
import base64
import webbrowser
import socket
import threading
import time
from tkcalendar import DateEntry
import pandas as pd
import arabic_reshaper  
from bidi.algorithm import get_display
import re
import textwrap
from PIL import Image, ImageDraw, ImageFont
from PIL import ImageTk



class QuestionsDialog(tk.Toplevel):
    def __init__(self, parent, questions, staff_code, next_staff_name=""):
        super().__init__(parent)
        self.title("الانصراف")
        self.geometry("800x600")
        self.resizable(True, True)

        self.staff_code = staff_code
        self.next_staff_name = next_staff_name
        self.result = {}
        self.questions = questions

        # ---------- scrollable canvas ----------
        canvas = tk.Canvas(self)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # ---------- mouse-wheel ----------
        self.canvas = canvas

        def on_mousewheel(event):
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind("<MouseWheel>", on_mousewheel)
        self.bind("<MouseWheel>", on_mousewheel)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # ---------- questions ----------
        self.entries = {}
        for q in questions:
            qf = ttk.Frame(scrollable_frame)
            qf.pack(fill=tk.X, pady=8, padx=10)

            lbl = ttk.Label(qf, text=q, font=("Arial", 11, "bold"), wraplength=700)
            lbl.pack(anchor=tk.W)

            ent = ttk.Entry(qf, width=80, font=("Arial", 10))
            ent.pack(fill=tk.X, pady=2)
            self.entries[q] = ent

        # ---------- bottom names ----------
        bottom_frame = ttk.Frame(scrollable_frame)
        bottom_frame.pack(fill=tk.X, pady=15, padx=10)

        ttk.Label(bottom_frame, text="اسم المسلم:", font=("Arial", 11, "bold")).grid(row=0, column=0, sticky=tk.W, padx=5)
        ttk.Label(bottom_frame, text=staff_code, font=("Arial", 11)).grid(row=0, column=1, sticky=tk.W)

        ttk.Label(bottom_frame, text="اسم المستلم:", font=("Arial", 11, "bold")).grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Label(bottom_frame, text=next_staff_name or "غير معروف", font=("Arial", 11)).grid(row=1, column=1, sticky=tk.W, pady=5)

        # ---------- preview ----------
        submit_btn = ttk.Button(self, text="Generate Preview", command=self._generate_preview)
        submit_btn.pack(pady=10)

        self.preview_label = ttk.Label(self)
        self.preview_label.pack(pady=5)

        copy_btn = ttk.Button(self, text="Copy Image", command=self._copy_image_to_clipboard)
        copy_btn.pack(pady=5)

        # close behavior
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_close(self):
        self.result = None
        self.destroy()

    def _generate_preview(self):
        # collect results
        for q, e in self.entries.items():
            self.result[q] = e.get().strip()

        img = self._create_preview_image()
        self.photo = ImageTk.PhotoImage(img)
        self.preview_label.config(image=self.photo)

    def _copy_image_to_clipboard(self):
        try:
            img = self._create_preview_image()
            img_bytes = io.BytesIO()
            img.save(img_bytes, format="PNG")
            data = base64.b64encode(img_bytes.getvalue()).decode()
            self.clipboard_clear()
            self.clipboard_append(f"data:image/png;base64,{data}")
            messagebox.showinfo("Done", "Image copied to clipboard!")
        except Exception as e:
            messagebox.showerror("Error", f"Copy failed:\n{e}")

    def _create_preview_image(self):
        # layout calculation
        y = 40
        for q, a in self.result.items():
            y += 28
            wrapped = textwrap.wrap(a or "(لا يوجد إجابة)", 80)
            y += len(wrapped) * 28
            y += 15
        y += 120

        width, height = 750, max(600, y)
        img = Image.new("RGB", (width, height), "white")
        draw = ImageDraw.Draw(img)

        try:
            font_q = ImageFont.truetype("arial.ttf", 20)
            font_a = ImageFont.truetype("arial.ttf", 22)
            font_bold = ImageFont.truetype("arialbd.ttf", 24)
        except:
            font_q = font_a = font_bold = ImageFont.load_default()

        def draw_safe_arabic(text, xy, font, fill="black"):
            cleaned = re.sub(r'[\x00-\x1F\x7F-\x9F]', '', text)
            try:
                reshaped = arabic_reshaper.reshape(cleaned)
                bidi_text = get_display(reshaped)
            except:
                bidi_text = cleaned
            bbox = draw.textbbox((0, 0), bidi_text, font=font)
            x = width - 50 - (bbox[2] - bbox[0])
            draw.text((x, xy[1]), bidi_text, fill=fill, font=font)

        y = 20
        draw_safe_arabic("ملخص الانصراف", (0, y), font_bold)
        y += 40

        for q, a in self.result.items():
            draw_safe_arabic(q, (0, y), font_q)
            y += 28
            wrapped = textwrap.wrap(a or "(لا يوجد إجابة)", 80)
            for line in wrapped:
                draw_safe_arabic(line, (0, y), font_a, fill="blue")
                y += 28
            y += 15

        draw_safe_arabic(f"اسم المسلم: {self.staff_code}", (0, y), font_bold)
        y += 35
        draw_safe_arabic(f"اسم المستلم: {self.next_staff_name or 'غير معروف'}", (0, y), font_bold)

        return img

    # In the QuestionsDialog __init__ method, add these elements after the bottom names section:

    # ----- preview button -----
    submit_btn = ttk.Button(self, text="Generate Preview", command=self._generate_preview)
    submit_btn.pack(pady=10)

    self.preview_label = ttk.Label(self)
    self.preview_label.pack(pady=5)

    # Also add this button in the __init__ method:
    copy_btn = ttk.Button(self, text="Copy Image", command=self._copy_image_to_clipboard)
    copy_btn.pack(pady=5)

class LeaveRequestDialog(tk.Toplevel):
    def __init__(self, parent, staff_code):
        super().__init__(parent)
        self.title("Submit Leave Request")
        self.geometry("400x300")
        self.resizable(False, False)
        
        self.staff_code = staff_code
        self.result = {}
        
        # Create frames
        info_frame = ttk.Frame(self)
        info_frame.pack(fill=tk.X, padx=10, pady=5)
        
        start_frame = ttk.Frame(self)
        start_frame.pack(fill=tk.X, padx=10, pady=5)
        
        end_frame = ttk.Frame(self)
        end_frame.pack(fill=tk.X, padx=10, pady=5)
        
        reason_frame = ttk.Frame(self)
        reason_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        button_frame = ttk.Frame(self)
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Staff info
        ttk.Label(info_frame, text=f"Staff Code: {staff_code}").pack(anchor=tk.W)
        
        # Start date
        ttk.Label(start_frame, text="Start Date:").pack(side=tk.LEFT, padx=5)
        self.start_date_var = tk.StringVar()
        self.start_date_entry = ttk.Entry(start_frame, textvariable=self.start_date_var, width=15)
        self.start_date_entry.pack(side=tk.LEFT, padx=5)
        
        # Add calendar button for start date
        ttk.Button(start_frame, text="📅", command=self.pick_start_date).pack(side=tk.LEFT)
        
        # End date
        ttk.Label(end_frame, text="End Date:").pack(side=tk.LEFT, padx=5)
        self.end_date_var = tk.StringVar()
        self.end_date_entry = ttk.Entry(end_frame, textvariable=self.end_date_var, width=15)
        self.end_date_entry.pack(side=tk.LEFT, padx=5)
        
        # Add calendar button for end date
        ttk.Button(end_frame, text="📅", command=self.pick_end_date).pack(side=tk.LEFT)
        
        # Reason
        ttk.Label(reason_frame, text="Reason:").pack(anchor=tk.W)
        self.reason_text = tk.Text(reason_frame, height=5, width=40)
        self.reason_text.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Buttons
        ttk.Button(button_frame, text="Submit", command=self.submit).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.cancel).pack(side=tk.RIGHT, padx=5)
        
        # Set default values
        today = datetime.now().strftime('%Y-%m-%d')
        self.start_date_var.set(today)
        self.end_date_var.set(today)
    
    def pick_start_date(self):
        top = tk.Toplevel(self)
        top.title("Select Start Date")
        cal = DateEntry(top, width=12, background='darkblue',
                        foreground='white', borderwidth=2)
        cal.pack(padx=10, pady=10)
        
        def set_date():
            self.start_date_var.set(cal.get_date().strftime('%Y-%m-%d'))
            top.destroy()
        
        ttk.Button(top, text="OK", command=set_date).pack(pady=5)
    
    def pick_end_date(self):
        top = tk.Toplevel(self)
        top.title("Select End Date")
        cal = DateEntry(top, width=12, background='darkblue',
                        foreground='white', borderwidth=2)
        cal.pack(padx=10, pady=10)
        
        def set_date():
            self.end_date_var.set(cal.get_date().strftime('%Y-%m-%d'))
            top.destroy()
        
        ttk.Button(top, text="OK", command=set_date).pack(pady=5)
    
    def submit(self):
        self.result = {
            'staff_code': self.staff_code,
            'start_date': self.start_date_var.get(),
            'end_date': self.end_date_var.get(),
            'reason': self.reason_text.get("1.0", tk.END).strip()
        }
        self.destroy()
    
    def cancel(self):
        self.result = None
        self.destroy()

class AttendanceClient:

    def __init__(self, root):
        self.root = root
        self.root.title("⏰الحضور و الانصراف")
        # Make window expandable and start maximized
        self.root.state('zoomed') # This maximizes the window on Windows
        self.root.resizable(True, True)
        
        # Server configuration
        self.server_url = None
        self.connected = False
        
        # Create main frame with padding and make it expandable
        self.main_frame = ttk.Frame(root, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Status display at the top
        self.status_frame = ttk.LabelFrame(self.main_frame, text="Connection Status", padding="10")
        self.status_frame.pack(fill=tk.X, pady=5)
        
        self.connection_status = ttk.Label(self.status_frame, text="Searching for server...", foreground="orange")
        self.connection_status.pack()
        
        # Manual server connection
        manual_frame = ttk.Frame(self.status_frame)
        manual_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(manual_frame, text="Or enter server IP:").pack(side=tk.LEFT, padx=5)
        self.server_ip_entry = ttk.Entry(manual_frame, width=15)
        self.server_ip_entry.pack(side=tk.LEFT, padx=5)
        self.server_ip_entry.insert(0, "localhost")
        
        ttk.Button(manual_frame, text="Connect", command=self.manual_connect).pack(side=tk.LEFT, padx=5)
        
        # Create notebook for tabs
        self.notebook = ttk.Notebook(self.main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # Create tabs
        self.attendance_tab = ttk.Frame(self.notebook)
        self.admin_tab = ttk.Frame(self.notebook)
        
        self.notebook.add(self.attendance_tab, text="Attendance")
        self.notebook.add(self.admin_tab, text="Admin")
        
        # Setup attendance tab
        self.setup_attendance_tab()
        
        # Setup admin tab
        self.setup_admin_tab()
        
        # Initially disable admin tab until connected
        self.notebook.tab(1, state="disabled")
        
        # Start server discovery in a separate thread
        threading.Thread(target=self.discover_server, daemon=True).start()
    
    def manual_connect(self):
        """Manually connect to a server IP"""
        ip = self.server_ip_entry.get().strip()
        if not ip:
            messagebox.showerror("Error", "Please enter a server IP address")
            return
        
        try:
            response = requests.get(f"http://{ip}:5000/api/server_info", timeout=5)
            if response.status_code == 200:
                try:
                    data = response.json()
                    if data.get('success'):
                        self.server_url = f"http://{ip}:5000"
                        self.on_server_found()
                    else:
                        messagebox.showerror("Error", "Server not responding correctly")
                except json.JSONDecodeError:
                    messagebox.showerror("Error", "Server returned invalid response")
            elif response.status_code == 404:
                messagebox.showerror("Error", "API endpoint not found (404). The server might be running an older version or missing the /api/server_info endpoint.")
            elif response.status_code == 405:
                messagebox.showerror("Error", "Method not allowed (405). The server might be running an older version or not supporting GET requests for this endpoint.")
            else:
                messagebox.showerror("Error", f"Server returned status code: {response.status_code}")
        except requests.exceptions.RequestException as e:
            messagebox.showerror("Error", f"Failed to connect to server: {str(e)}")
    
    def discover_server(self):
        """Discover the server on the local network"""
        # Get local IP and subnet
        try:
            # Connect to an external host to find local IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            
            # Extract subnet
            subnet = '.'.join(local_ip.split('.')[:-1]) + '.'
            
            
            # Then try the local IP
            try:
                response = requests.get(f"http://{local_ip}:5000/api/server_info", timeout=3)
                if response.status_code == 200:
                    try:
                        data = response.json()
                        if data.get('success'):
                            self.server_url = f"http://{local_ip}:5000"
                            self.on_server_found()
                            return
                    except json.JSONDecodeError:
                        pass
            except:
                pass
            
            # Try common network IPs if local subnet scan fails
            common_ips = [
                "192.168.1.130", "192.168.1.6", "192.168.1.101", "192.168.1.102",
                "192.168.0.1", "192.168.0.100", "192.168.0.101", "192.168.0.102",
                "10.0.0.1", "10.0.0.100", "10.0.0.101", "10.0.0.102"
            ]
            
            for ip in common_ips:
                try:
                    response = requests.get(f"http://{ip}:5000/api/server_info", timeout=1)
                    if response.status_code == 200:
                        try:
                            data = response.json()
                            if data.get('success'):
                                self.server_url = f"http://{ip}:5000"
                                self.on_server_found()
                                return
                        except json.JSONDecodeError:
                            pass
                except:
                    pass
            
            # If still not found, try limited subnet scan
            for i in range(1, 255):
                if i == int(local_ip.split('.')[-1]):  # Skip our own IP
                    continue
                    
                try:
                    ip = subnet + str(i)
                    response = requests.get(f"http://{ip}:5000/api/server_info", timeout=0.5)
                    if response.status_code == 200:
                        try:
                            data = response.json()
                            if data.get('success'):
                                self.server_url = f"http://{ip}:5000"
                                self.on_server_found()
                                return
                        except json.JSONDecodeError:
                            pass
                except:
                    pass
            
            # If server not found, update status
            self.root.after(0, lambda: self.connection_status.config(text="Server not found. Please enter IP manually.", foreground="red"))
            
        except Exception as e:
            self.root.after(0, lambda: self.connection_status.config(text=f"Error searching for server: {str(e)}", foreground="red"))
    
    def on_server_found(self):
        self.connected = True
        self.root.after(0, lambda: self.connection_status.config(
            text=f"Connected to server at {self.server_url}", foreground="green"))
        self.root.after(0, lambda: self.notebook.tab(1, state="normal"))

        # Now that we know the server, embed CRM
        if not hasattr(self, 'crm_frame'):
            from crmtest import CrmFrame
            self.crm_section = ttk.LabelFrame(self.attendance_tab, text="CRM", padding=10)
            self.crm_section.pack(fill="both", expand=True, padx=10, pady=10)
            self.crm_frame = CrmFrame(self.crm_section, server_url=self.server_url)
            self.crm_frame.pack(fill="both", expand=True)
            refresh_frame = ttk.Frame(self.crm_section)
            refresh_frame.pack(fill=tk.X, pady=5)
            ttk.Button(refresh_frame, text="Refresh", command=self.refresh_crm).pack(side=tk.RIGHT)
    
    def refresh_crm(self):
        if hasattr(self, 'crm_frame'):
            self.crm_frame.destroy()
        from crmtest import CrmFrame
        self.crm_frame = CrmFrame(self.crm_section, server_url=self.server_url)
        self.crm_frame.pack(fill="both", expand=True)

    def setup_attendance_tab(self):
        # Title
        title_label = ttk.Label(self.attendance_tab, text="الحضور و الانصراف⏰", font=("Arial", 16, "bold"))
        title_label.pack(pady=10)
        
        # Status Display
        self.status_display = ttk.Label(self.attendance_tab, text="Please enter your code", font=("Arial", 12), foreground="blue")
        self.status_display.pack(pady=5)
        
        # Staff code
        code_frame = ttk.Frame(self.attendance_tab)
        code_frame.pack(fill=tk.X, pady=5)
        ttk.Label(code_frame, text="Staff Code:").pack(side=tk.LEFT, padx=5)
        self.code_entry = ttk.Entry(code_frame, width=20, font=("Arial", 12))
        self.code_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.code_entry.bind('<KeyRelease>', self.check_staff_status)

        # Action Buttons Frame
        self.action_frame = ttk.Frame(self.attendance_tab)
        self.action_frame.pack(pady=10)
        
        # Main action button (Clock In/Out)
        self.main_action_button = ttk.Button(self.action_frame, text="Clock In", command=self.main_action, state="disabled")
        self.main_action_button.pack(side=tk.LEFT, padx=5)
        
        # Break and Return buttons
        self.break_button = ttk.Button(self.action_frame, text="Start Break", command=self.start_break, state="disabled")
        self.break_button.pack(side=tk.LEFT, padx=5)
        
        self.return_button = ttk.Button(self.action_frame, text="End Break", command=self.end_break, state="disabled")
        self.return_button.pack(side=tk.LEFT, padx=5)
        
        # Leave request button
        self.leave_button = ttk.Button(self.action_frame, text="Request Leave", command=self.request_leave, state="disabled")
        self.leave_button.pack(side=tk.LEFT, padx=5)
        
        # Status message
        self.attendance_status = ttk.Label(self.attendance_tab, text="", foreground="green")
        self.attendance_status.pack(pady=10)

    def setup_admin_tab(self):
        # Title
        title_label = ttk.Label(self.admin_tab, text="Admin", font=("Arial", 16, "bold"))
        title_label.pack(pady=10)
        
        # Password
        password_frame = ttk.Frame(self.admin_tab)
        password_frame.pack(fill=tk.X, pady=5)
        ttk.Label(password_frame, text="Admin Password:").pack(side=tk.LEFT, padx=5)
        self.password_entry = ttk.Entry(password_frame, width=20, show="*")
        self.password_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # Login button
        login_button = ttk.Button(self.admin_tab, text="Login", command=self.admin_login)
        login_button.pack(pady=5)
        
        # Admin status
        self.admin_status = ttk.Label(self.admin_tab, text="Not logged in", foreground="red")
        self.admin_status.pack(pady=5)
        
        # Create notebook for admin sub-tabs
        self.admin_notebook = ttk.Notebook(self.admin_tab)
        self.admin_notebook.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Create admin sub-tabs
        self.attendance_data_tab = ttk.Frame(self.admin_notebook)
        self.staff_management_tab = ttk.Frame(self.admin_notebook)
        self.shift_management_tab = ttk.Frame(self.admin_notebook)
        self.holiday_management_tab = ttk.Frame(self.admin_notebook)
        self.leave_management_tab = ttk.Frame(self.admin_notebook)
        self.dashboard_tab = ttk.Frame(self.admin_notebook)
        self.settings_tab = ttk.Frame(self.admin_notebook)
        self.audit_log_tab = ttk.Frame(self.admin_notebook)
        self.detailed_report_tab = ttk.Frame(self.admin_notebook)
        self.notes_export_tab = ttk.Frame(self.admin_notebook) # Notes Export Tab
        
        self.admin_notebook.add(self.attendance_data_tab, text="Attendance Data")
        self.admin_notebook.add(self.staff_management_tab, text="Staff")
        self.admin_notebook.add(self.shift_management_tab, text="Shifts")
        self.admin_notebook.add(self.holiday_management_tab, text="Holidays")
        self.admin_notebook.add(self.leave_management_tab, text="Leave Requests")
        self.admin_notebook.add(self.dashboard_tab, text="Dashboard")
        self.admin_notebook.add(self.settings_tab, text="Settings")
        self.admin_notebook.add(self.audit_log_tab, text="Audit")
        self.admin_notebook.add(self.detailed_report_tab, text="payroll & attendance ")
        self.admin_notebook.add(self.notes_export_tab, text="Notes Export")
        # ------------------------------------------------------------------
        # Inside AttendanceClient.setup_admin_tab()  (add after the other tabs)
        # ------------------------------------------------------------------
        # --- CRM Admin Tab (single, clean version) ---
        self.crm_admin_tab = ttk.Frame(self.admin_notebook)
        self.admin_notebook.add(self.crm_admin_tab, text="CRM Admin")
        self.admin_notebook.tab(self.crm_admin_tab, state="disabled")  # hidden until login
        self.setup_crm_admin_tab()

        # Tab-change listener – refresh CRM when the tab becomes visible
        def on_admin_tab_changed(event):
            try:
                selected = self.admin_notebook.select()
                if not selected:
                    return
                tab_text = self.admin_notebook.tab(selected, "text")
                if tab_text == "CRM Admin":
                    self.root.after(100, self.crm_refresh_leads)  # Delay to avoid race
            except tk.TclError:
                pass  # Ignore if notebook is not ready

        self.admin_notebook.bind("<<NotebookTabChanged>>", on_admin_tab_changed)
        # Inside setup_admin_tab()
        self.crm_admin_tab = ttk.Frame(self.admin_notebook)
        self.admin_notebook.add(self.crm_admin_tab, text="CRM Admin")
        self.admin_notebook.tab(self.crm_admin_tab, state="disabled")  # hidden until login
        self.setup_crm_admin_tab()


        # Initially disable admin sub-tabs
        for i in range(10):
            self.admin_notebook.tab(i, state="disabled")
        
        # Setup attendance data tab
        self.setup_attendance_data_tab()
        
        # Setup staff management tab
        self.setup_staff_management_tab()
        
        # Setup shift management tab
        self.setup_shift_management_tab()
        
        # Setup holiday management tab
        self.setup_holiday_management_tab()
        
        # Setup leave management tab
        self.setup_leave_management_tab()
        
        # Setup dashboard tab
        self.setup_dashboard_tab()
        
        # Setup settings tab
        self.setup_settings_tab()
        self.setup_audit_log_tab()
        self.setup_detailed_report_tab()
        self.setup_notes_export_tab()
    

    class CrmLeadDialog(tk.Toplevel):
        def __init__(self, parent, title, server_url, admin_pw, lead_data=None):
            super().__init__(parent)
            self.title(title)
            self.geometry("520x460")
            self.resizable(False, False)
            self.result = None
            self.server_url = server_url
            self.admin_pw = admin_pw

            # Fetch dropdown data
            self.targets = self._get_targets()
            self.staff   = self._get_staff()

            # UI
            pad = dict(padx=8, pady=4)

            # Name
            f = ttk.Frame(self); f.pack(fill=tk.X, **pad)
            ttk.Label(f, text="Name:").pack(side=tk.LEFT)
            self.e_name = ttk.Entry(f, width=40)
            self.e_name.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

            # Phone
            f = ttk.Frame(self); f.pack(fill=tk.X, **pad)
            ttk.Label(f, text="Phone:").pack(side=tk.LEFT)
            self.e_phone = ttk.Entry(f, width=40)
            self.e_phone.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

            # Status
            f = ttk.Frame(self); f.pack(fill=tk.X, **pad)
            ttk.Label(f, text="Status:").pack(side=tk.LEFT)
            self.cb_status = ttk.Combobox(f, values=["New","Contacted","Qualified","Lost","Won"],
                                        state="readonly", width=37)
            self.cb_status.pack(side=tk.LEFT, padx=5)
            self.cb_status.set("New")

            # Target
            f = ttk.Frame(self); f.pack(fill=tk.X, **pad)
            ttk.Label(f, text="Target:").pack(side=tk.LEFT)
            self.cb_target = ttk.Combobox(f, values=self.targets,
                                        state="readonly", width=37)
            self.cb_target.pack(side=tk.LEFT, padx=5)

            # Assigned To
            f = ttk.Frame(self); f.pack(fill=tk.X, **pad)
            ttk.Label(f, text="Assigned:").pack(side=tk.LEFT)
            self.cb_assign = ttk.Combobox(f, values=self.staff,
                                        state="readonly", width=37)
            self.cb_assign.pack(side=tk.LEFT, padx=5)

            # Notes
            f = ttk.Frame(self); f.pack(fill=tk.BOTH, expand=True, **pad)
            ttk.Label(f, text="Notes:").pack(anchor=tk.W)
            self.t_notes = tk.Text(f, height=8, wrap=tk.WORD)
            self.t_notes.pack(fill=tk.BOTH, expand=True)

            # Buttons
            f = ttk.Frame(self); f.pack(fill=tk.X, **pad)
            ttk.Button(f, text="Save", command=self._save).pack(side=tk.RIGHT, padx=5)
            ttk.Button(f, text="Cancel", command=self.destroy).pack(side=tk.RIGHT)

            # Fill if editing
            if lead_data:
                self.lead_id = lead_data.get('id')
                self.e_name.insert(0, lead_data.get('name',''))
                self.e_phone.insert(0, lead_data.get('phone',''))
                self.cb_status.set(lead_data.get('status','New'))
                self.cb_target.set(lead_data.get('target',''))
                self.cb_assign.set(lead_data.get('assigned_to',''))
                self.t_notes.insert('1.0', lead_data.get('notes',''))
            else:
                self.lead_id = None

    def _get_targets(self):
        try:
            r = requests.post(f"{self.server_url}/api/crm_get_targets",
                              json={"password": self.admin_pw}, timeout=5)
            return r.json().get('targets', [])
        except: return []

    def _get_staff(self):
        try:
            r = requests.post(f"{self.server_url}/api/get_staff",
                              json={"password": self.admin_pw}, timeout=5)
            data = r.json().get('data', [])
            return [f"{s['staff_code']} - {s['name']}" for s in data]
        except: return []

    def _save(self):
        payload = {
            "password": self.admin_pw,
            "name": self.e_name.get().strip(),
            "phone": self.e_phone.get().strip(),
            "status": self.cb_status.get(),
            "target": self.cb_target.get(),
            "assigned_to": self.cb_assign.get().split(' - ')[0] if self.cb_assign.get() else "",
            "notes": self.t_notes.get('1.0', tk.END).strip()
        }
        if self.lead_id:
            payload["lead_id"] = self.lead_id
            endpoint = "/api/crm_update_lead"
        else:
            endpoint = "/api/crm_add_lead"

        try:
            r = requests.post(f"{self.server_url}{endpoint}",
                              json=payload, timeout=8)
            resp = r.json()
            if resp.get('success'):
                self.result = True
                self.destroy()
            else:
                messagebox.showerror("Error", resp.get('message','Save failed'))
        except Exception as e:
            messagebox.showerror("Error", f"Save failed: {e}")
    def setup_crm_admin_tab(self):
        """Live CRM Admin – auto-syncs with DB"""
        container = ttk.Frame(self.crm_admin_tab, padding=10)
        container.pack(fill=tk.BOTH, expand=True)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        # Toolbar
        toolbar = ttk.Frame(container)
        toolbar.grid(row=0, column=0, sticky='ew', pady=4)
        toolbar.grid_columnconfigure(0, weight=1)

        ttk.Button(toolbar, text="Add Lead",   command=self.crm_add_lead).grid(row=0, column=0, padx=2, sticky='w')
        ttk.Button(toolbar, text="Edit Lead",  command=self.crm_edit_lead).grid(row=0, column=1, padx=2)
        ttk.Button(toolbar, text="Delete Lead",command=self.crm_delete_lead).grid(row=0, column=2, padx=2)
        ttk.Button(toolbar, text="Change Target", command=self.crm_change_target).grid(row=0, column=3, padx=2)
        ttk.Button(toolbar, text="Refresh",    command=self.crm_refresh_leads).grid(row=0, column=4, padx=2, sticky='e')

        # Treeview
        tree_frame = ttk.Frame(container)
        tree_frame.grid(row=1, column=0, sticky='nsew', pady=4)
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        cols = ('ID', 'Name', 'Phone', 'Status', 'Target', 'Assigned', 'Notes', 'Created')
        self.crm_tree = ttk.Treeview(tree_frame, columns=cols, show='headings', selectmode='browse')
        for c, w in zip(cols, (50, 150, 110, 80, 100, 100, 200, 130)):
            self.crm_tree.heading(c, text=c)
            self.crm_tree.column(c, width=w, anchor='w')

        vbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL,   command=self.crm_tree.yview)
        hbar = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self.crm_tree.xview)
        self.crm_tree.configure(yscrollcommand=vbar.set, xscrollcommand=hbar.set)

        self.crm_tree.grid(row=0, column=0, sticky='nsew')
        vbar.grid(row=0, column=1, sticky='ns')
        hbar.grid(row=1, column=0, sticky='ew')

        # Status
        self.crm_status = ttk.Label(container, text="Loading...", foreground="blue")
        self.crm_status.grid(row=2, column=0, sticky='w', pady=4)

        # === SAFE TAB CHANGE HANDLER ===
        def on_tab_change(event):
            try:
                selected = self.admin_notebook.select()
                if not selected:
                    return
                tab_text = self.admin_notebook.tab(selected, "text")
                if tab_text == "CRM Admin":
                    self.root.after(100, self.crm_refresh_leads)  # Delay to avoid race
            except tk.TclError:
                pass  # Ignore if notebook not ready

        self.admin_notebook.bind("<<NotebookTabChanged>>", on_tab_change)

        # Initial load after login
        self.root.after(1000, self.crm_refresh_leads)
        
    def setup_attendance_data_tab(self):
        """Fully functional Attendance Data tab – live DB sync, edit, search, export"""
        container = ttk.Frame(self.attendance_data_tab, padding=10)
        container.pack(fill=tk.BOTH, expand=True)
        container.grid_rowconfigure(1, weight=1)
        container.grid_columnconfigure(0, weight=1)

        # ---------- Toolbar ----------
        toolbar = ttk.Frame(container)
        toolbar.grid(row=0, column=0, sticky='ew', pady=4)
        toolbar.grid_columnconfigure(0, weight=1)

        # Search
        ttk.Label(toolbar, text="Search:").grid(row=0, column=0, padx=2, sticky='w')
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(toolbar, textvariable=self.search_var, width=25)
        search_entry.grid(row=0, column=1, padx=2, sticky='w')
        search_entry.bind('<KeyRelease>', lambda e: self.filter_attendance())

        # Date filter
        ttk.Label(toolbar, text="Date:").grid(row=0, column=2, padx=2)
        self.date_filter_var = tk.StringVar()
        date_entry = ttk.Entry(toolbar, textvariable=self.date_filter_var, width=12)
        date_entry.grid(row=0, column=3, padx=2)
        ttk.Button(toolbar, text="Calendar", command=self.pick_filter_date).grid(row=0, column=4, padx=2)

        # Buttons
        ttk.Button(toolbar, text="Refresh", command=self.load_attendance_data).grid(row=0, column=5, padx=2)
        ttk.Button(toolbar, text="Export Excel", command=self.export_attendance_excel).grid(row=0, column=6, padx=2, sticky='e')

        # ---------- Treeview ----------
        tree_frame = ttk.Frame(container)
        tree_frame.grid(row=1, column=0, sticky='nsew', pady=4)
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        cols = ('ID', 'Staff Code', 'Name', 'Date', 'Clock In', 'Clock Out', 'Hours', 'Notes')
        self.att_tree = ttk.Treeview(tree_frame, columns=cols, show='headings', selectmode='browse')
        widths = (50, 80, 120, 100, 100, 100, 70, 200)
        for c, w in zip(cols, widths):
            self.att_tree.heading(c, text=c)
            self.att_tree.column(c, width=w, anchor='center' if c in ('ID','Hours') else 'w')

        vbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.att_tree.yview)
        hbar = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self.att_tree.xview)
        self.att_tree.configure(yscrollcommand=vbar.set, xscrollcommand=hbar.set)

        self.att_tree.grid(row=0, column=0, sticky='nsew')
        vbar.grid(row=0, column=1, sticky='ns')
        hbar.grid(row=1, column=0, sticky='ew')

        # Double-click to edit
        self.att_tree.bind('<Double-1>', self.edit_attendance_record)

        # Status
        self.att_status = ttk.Label(container, text="Loading...", foreground="blue")
        self.att_status.grid(row=2, column=0, sticky='w', pady=4)

        # Load data
        self.root.after(500, self.load_attendance_data)
    
        # ================================================
    # ATTENDANCE DATA TAB – FULL FUNCTIONALITY
    # ================================================

    def pick_filter_date(self):
        """Open calendar to pick a date for filtering attendance"""
        top = tk.Toplevel(self.root)
        top.title("Select Date")
        top.geometry("300x250")
        
        cal = DateEntry(top, width=12, background='darkblue', foreground='darkgreen', borderwidth=2)
        cal.pack(padx=20, pady=20)

        def set_date():
            selected_date = cal.get_date().strftime('%Y-%m-%d')
            self.date_filter_var.set(selected_date)
            top.destroy()
            self.filter_attendance()

        def clear_date():
            self.date_filter_var.set("")
            top.destroy()
            self.filter_attendance()

        button_frame = ttk.Frame(top)
        button_frame.pack(pady=10)
        ttk.Button(button_frame, text="OK", command=set_date).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Clear", command=clear_date).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=top.destroy).pack(side=tk.LEFT, padx=5)

    def load_attendance_data(self):
        """Fetch all attendance records from DB"""
        pw = getattr(self, 'password_entry', None)
        if not pw or not pw.get():
            self.att_status.config(text="Admin login required", foreground="red")
            return

        try:
            response = requests.post(f"{self.server_url}/api/get_attendance",
                                    json={"password": pw.get().strip()}, timeout=10)
            response.raise_for_status()  # Raises an error for bad responses (4xx or 5xx)
            resp_data = response.json()

            if not resp_data.get('success'):
                raise ValueError(resp_data.get('message', 'Server returned success=False'))

            # --- KEY FIX HERE ---
            # The server sends the data under the key 'data', not 'records'.
            self.attendance_records = resp_data.get('data', [])
            
            if not self.attendance_records:
                self.att_status.config(text="No attendance records found", foreground="orange")
            else:
                self.att_status.config(text=f"{len(self.attendance_records)} records loaded", foreground="green")

            self.filter_attendance()

        except requests.exceptions.RequestException as e:
            messagebox.showerror("Connection Error", f"Failed to connect to server: {e}")
            self.att_status.config(text="Connection failed", foreground="red")
        except ValueError as e: # Catches JSON errors and our custom ValueError
            messagebox.showerror("Server Error", f"Failed to load data: {e}")
            self.att_status.config(text="Server error", foreground="red")
        except Exception as e:
            messagebox.showerror("Error", f"An unexpected error occurred: {e}")
            self.att_status.config(text="Load failed", foreground="red")

    def filter_attendance(self):
        """Apply search + date filter and populate the treeview"""
        search = self.search_var.get().lower()
        date_filter = self.date_filter_var.get().strip()

        filtered = []
        for rec in self.attendance_records:
            # --- FIX: Extract date from the 'clock_in' timestamp ---
            clock_in_dt = datetime.fromisoformat(rec.get('clock_in'))
            record_date = clock_in_dt.strftime('%Y-%m-%d')

            if search and search not in rec.get('staff_code','').lower() and search not in rec.get('name','').lower():
                continue
            if date_filter and record_date != date_filter:
                continue
            filtered.append(rec)

        # Clear existing data from the tree
        for i in self.att_tree.get_children():
            self.att_tree.delete(i)

        # --- FIX: Populate tree with correctly formatted data ---
        for rec in filtered:
            clock_in_dt = datetime.fromisoformat(rec.get('clock_in'))
            record_date = clock_in_dt.strftime('%Y-%m-%d')
            clock_in_time = clock_in_dt.strftime('%H:%M:%S')

            clock_out_time = ''
            hours = 0.0
            if rec.get('clock_out'):
                clock_out_dt = datetime.fromisoformat(rec.get('clock_out'))
                clock_out_time = clock_out_dt.strftime('%H:%M:%S')
                # --- FIX: Calculate hours if clock_out exists ---
                hours = round((clock_out_dt - clock_in_dt).total_seconds() / 3600, 2)

            notes = (rec.get('notes') or '')[:50] + ('...' if len(rec.get('notes',''))>50 else '')
            
            self.att_tree.insert('', 'end', values=(
                rec.get('id'),
                rec.get('staff_code'),
                rec.get('name'),
                record_date,       # Use the extracted date
                clock_in_time,      # Use the formatted time
                clock_out_time,     # Use the formatted time
                f"{hours:.2f}",    # Use the calculated hours
                notes
            ))

    def edit_attendance_record(self, event=None):
        item = self.att_tree.selection()
        if not item:
            return
        values = self.att_tree.item(item, 'values')
        rec_id = values[0]

        # Find full record
        rec = next((r for r in self.attendance_records if r.get('id') == int(rec_id)), None)
        if not rec:
            return

        # Open edit dialog
        dlg = AttendanceEditDialog(self.root, [
            rec.get('id'), rec.get('staff_code'), rec.get('name'),
            rec.get('date'), rec.get('clock_in'), rec.get('clock_out')
        ])
        self.root.wait_window(dlg)

        if dlg.result:
            payload = {
                "password": getattr(self, 'password_entry', None).get() if hasattr(self, 'password_entry') else "",
                "record_id": rec.get('id'),
                "clock_in": dlg.result['clock_in'],
                "clock_out": dlg.result['clock_out']
            }
            try:
                r = requests.post(f"{self.server_url}/api/edit_attendance", json=payload, timeout=8)
                resp = r.json()
                if resp.get('success'):
                    self.load_attendance_data()
                else:
                    messagebox.showerror("Error", resp.get('message'))
            except Exception as e:
                messagebox.showerror("Error", f"Update failed: {e}")

    def export_attendance_excel(self):
        """Exports the filtered attendance data to an Excel file."""
        # Check if there is any data to export
        if not hasattr(self, 'attendance_records') or not self.attendance_records:
            messagebox.showwarning("No Data", "No attendance records to export.")
            return

        # Use the same filtering logic as the display
        search = self.search_var.get().lower()
        date_filter = self.date_filter_var.get().strip()
        data_to_export = []
        for rec in self.attendance_records:
            # Apply same filters
            clock_in_dt = datetime.fromisoformat(rec.get('clock_in'))
            record_date = clock_in_dt.strftime('%Y-%m-%d')

            if search and search not in rec.get('staff_code','').lower() and search not in rec.get('name','').lower():
                continue
            if date_filter and record_date != date_filter:
                continue
            
            # Prepare data for the DataFrame
            data_to_export.append({
                'ID': rec.get('id'),
                'Staff Code': rec.get('staff_code'),
                'Name': rec.get('name'),
                'Date': record_date,
                'Clock In': clock_in_dt.strftime('%H:%M:%S'),
                'Clock Out': datetime.fromisoformat(rec.get('clock_out')).strftime('%H:%M:%S') if rec.get('clock_out') else 'N/A',
                'Hours Worked': round((datetime.fromisoformat(rec.get('clock_out')) - clock_in_dt).total_seconds() / 3600, 2) if rec.get('clock_out') else 0,
                'Notes': rec.get('notes', '')
            })

        if not data_to_export:
            messagebox.showwarning("No Data", "No records match the current filters to export.")
            return

        # --- Ask user where to save the file ---
        # The 'asksaveasfilename' dialog will handle the file selection.
        file_path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
            title="Save attendance data as...",
            initialfile=f"attendance_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        )

        # If the user cancels the dialog, file_path will be empty. Do nothing.
        if not file_path:
            return

        try:
            # Create a Pandas DataFrame
            df = pd.DataFrame(data_to_export)

            # Use ExcelWriter to create the file
            with pd.ExcelWriter(file_path, engine='xlsxwriter') as writer:
                df.to_excel(writer, sheet_name='Attendance', index=False)
                
                # Get the workbook and worksheet objects for formatting
                workbook = writer.book
                worksheet = writer.sheets['Attendance']
                
                # Add some formatting to the header
                header_format = workbook.add_format({
                    'bold': True,
                    'text_wrap': True,
                    'valign': 'top',
                    'fg_color': '#D7E4BC', # A light green color
                    'border': 1
                })
                
                # Apply the header format to all columns
                for col_num, value in enumerate(df.columns.values):
                    worksheet.write(0, col_num, value, header_format)
                
                # Adjust column widths for better readability
                for i, col in enumerate(df.columns):
                    # Find the maximum length of the data in the column
                    max_len = max(
                        df[col].astype(str).map(len).max(),
                        len(str(col))
                    )
                    # Set the column width, with a maximum of 50
                    worksheet.set_column(i, i, min(max_len + 2, 50))

            # Show a success message
            messagebox.showinfo("Export Successful", f"Data exported successfully to:\n{file_path}")

        except Exception as e:
            # Show an error message if something goes wrong
            messagebox.showerror("Export Failed", f"An error occurred while exporting the file:\n{e}")


    def setup_staff_management_tab(self):
        # Buttons
        button_frame = ttk.Frame(self.staff_management_tab)
        button_frame.pack(fill=tk.X, pady=5)
        
        add_button = ttk.Button(button_frame, text="Add Staff", command=self.add_staff)
        add_button.pack(side=tk.LEFT, padx=5)
        
        update_button = ttk.Button(button_frame, text="Update Staff", command=self.update_staff)
        update_button.pack(side=tk.LEFT, padx=5)
        
        delete_button = ttk.Button(button_frame, text="Delete Staff", command=self.delete_staff)
        delete_button.pack(side=tk.LEFT, padx=5)
        
        refresh_button = ttk.Button(button_frame, text="Refresh", command=self.refresh_staff_data)
        refresh_button.pack(side=tk.LEFT, padx=5)
        
        # Create treeview for staff data
        self.staff_tree = ttk.Treeview(self.staff_management_tab, columns=('ID', 'Staff Code', 'Name', 'Hourly Rate', 'Shift'), show='headings')
        
        # Define headings
        self.staff_tree.heading('ID', text='ID')
        self.staff_tree.heading('Staff Code', text='Staff Code')
        self.staff_tree.heading('Name', text='Name')
        self.staff_tree.heading('Hourly Rate', text='Hourly Rate')
        self.staff_tree.heading('Shift', text='Shift')
        
        # Configure column widths
        self.staff_tree.column('ID', width=40)
        self.staff_tree.column('Staff Code', width=100)
        self.staff_tree.column('Name', width=150)
        self.staff_tree.column('Hourly Rate', width=100)
        self.staff_tree.column('Shift', width=100)
        
        # Add scrollbar
        staff_scrollbar = ttk.Scrollbar(self.staff_management_tab, orient=tk.VERTICAL, command=self.staff_tree.yview)
        self.staff_tree.configure(yscroll=staff_scrollbar.set)
        
        # Pack treeview and scrollbar
        self.staff_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        staff_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    def setup_shift_management_tab(self):
        # Buttons
        button_frame = ttk.Frame(self.shift_management_tab)
        button_frame.pack(fill=tk.X, pady=5)
        
        add_button = ttk.Button(button_frame, text="Add Shift", command=self.add_shift)
        add_button.pack(side=tk.LEFT, padx=5)
        
        refresh_button = ttk.Button(button_frame, text="Refresh", command=self.refresh_shift_data)
        refresh_button.pack(side=tk.LEFT, padx=5)
        
        # Create treeview for shift data
        self.shift_tree = ttk.Treeview(self.shift_management_tab, columns=('ID', 'Name', 'Start Time', 'End Time'), show='headings')
        
        # Define headings
        self.shift_tree.heading('ID', text='ID')
        self.shift_tree.heading('Name', text='Name')
        self.shift_tree.heading('Start Time', text='Start Time')
        self.shift_tree.heading('End Time', text='End Time')
        
        # Configure column widths
        self.shift_tree.column('ID', width=40)
        self.shift_tree.column('Name', width=150)
        self.shift_tree.column('Start Time', width=100)
        self.shift_tree.column('End Time', width=100)
        
        # Add scrollbar
        shift_scrollbar = ttk.Scrollbar(self.shift_management_tab, orient=tk.VERTICAL, command=self.shift_tree.yview)
        self.shift_tree.configure(yscroll=shift_scrollbar.set)
        
        # Pack treeview and scrollbar
        self.shift_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        shift_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    def setup_holiday_management_tab(self):
        # Buttons
        button_frame = ttk.Frame(self.holiday_management_tab)
        button_frame.pack(fill=tk.X, pady=5)
        
        add_button = ttk.Button(button_frame, text="Add Holiday", command=self.add_holiday)
        add_button.pack(side=tk.LEFT, padx=5)
        
        refresh_button = ttk.Button(button_frame, text="Refresh", command=self.refresh_holiday_data)
        refresh_button.pack(side=tk.LEFT, padx=5)
        
        # Create treeview for holiday data
        self.holiday_tree = ttk.Treeview(self.holiday_management_tab, columns=('ID', 'Date', 'Name', 'Paid'), show='headings')
        
        # Define headings
        self.holiday_tree.heading('ID', text='ID')
        self.holiday_tree.heading('Date', text='Date')
        self.holiday_tree.heading('Name', text='Name')
        self.holiday_tree.heading('Paid', text='Paid')
        
        # Configure column widths
        self.holiday_tree.column('ID', width=40)
        self.holiday_tree.column('Date', width=100)
        self.holiday_tree.column('Name', width=200)
        self.holiday_tree.column('Paid', width=60)
        
        # Add scrollbar
        holiday_scrollbar = ttk.Scrollbar(self.holiday_management_tab, orient=tk.VERTICAL, command=self.holiday_tree.yview)
        self.holiday_tree.configure(yscroll=holiday_scrollbar.set)
        
        # Pack treeview and scrollbar
        self.holiday_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        holiday_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    def setup_leave_management_tab(self):
        # Buttons
        button_frame = ttk.Frame(self.leave_management_tab)
        button_frame.pack(fill=tk.X, pady=5)
        
        approve_button = ttk.Button(button_frame, text="Approve", command=self.approve_leave_request)
        approve_button.pack(side=tk.LEFT, padx=5)
        
        reject_button = ttk.Button(button_frame, text="Reject", command=self.reject_leave_request)
        reject_button.pack(side=tk.LEFT, padx=5)
        
        refresh_button = ttk.Button(button_frame, text="Refresh", command=self.refresh_leave_data)
        refresh_button.pack(side=tk.LEFT, padx=5)
        
        # Create treeview for leave data
        self.leave_tree = ttk.Treeview(self.leave_management_tab, columns=('ID', 'Staff Code', 'Name', 'Start Date', 'End Date', 'Reason', 'Status'), show='headings')
        
        # Define headings
        self.leave_tree.heading('ID', text='ID')
        self.leave_tree.heading('Staff Code', text='Staff Code')
        self.leave_tree.heading('Name', text='Name')
        self.leave_tree.heading('Start Date', text='Start Date')
        self.leave_tree.heading('End Date', text='End Date')
        self.leave_tree.heading('Reason', text='Reason')
        self.leave_tree.heading('Status', text='Status')
        
        # Configure column widths
        self.leave_tree.column('ID', width=40)
        self.leave_tree.column('Staff Code', width=100)
        self.leave_tree.column('Name', width=150)
        self.leave_tree.column('Start Date', width=100)
        self.leave_tree.column('End Date', width=100)
        self.leave_tree.column('Reason', width=200)
        self.leave_tree.column('Status', width=80)
        
        # Add scrollbar
        leave_scrollbar = ttk.Scrollbar(self.leave_management_tab, orient=tk.VERTICAL, command=self.leave_tree.yview)
        self.leave_tree.configure(yscroll=leave_scrollbar.set)
        
        # Pack treeview and scrollbar
        self.leave_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        leave_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    def setup_dashboard_tab(self):
        # Controls
        controls_frame = ttk.Frame(self.dashboard_tab)
        controls_frame.pack(fill=tk.X, pady=5, padx=10)
        
        ttk.Label(controls_frame, text="Date Range:").pack(side=tk.LEFT, padx=5)
        self.dashboard_start_date_var = tk.StringVar()
        self.dashboard_start_date_entry = ttk.Entry(controls_frame, textvariable=self.dashboard_start_date_var, width=12)
        self.dashboard_start_date_entry.pack(side=tk.LEFT, padx=2)
        
        ttk.Button(controls_frame, text="📅", command=self.pick_dashboard_start_date).pack(side=tk.LEFT)
        
        ttk.Label(controls_frame, text="to").pack(side=tk.LEFT, padx=5)
        
        self.dashboard_end_date_var = tk.StringVar()
        self.dashboard_end_date_entry = ttk.Entry(controls_frame, textvariable=self.dashboard_end_date_var, width=12)
        self.dashboard_end_date_entry.pack(side=tk.LEFT, padx=2)
        
        ttk.Button(controls_frame, text="📅", command=self.pick_dashboard_end_date).pack(side=tk.LEFT)
        
        ttk.Button(controls_frame, text="Generate Dashboard", command=self.generate_dashboard).pack(side=tk.LEFT, padx=10)
        
        # Set default values
        today = datetime.now().strftime('%Y-%m-%d')
        thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        self.dashboard_start_date_var.set(thirty_days_ago)
        self.dashboard_end_date_var.set(today)
        
        # Dashboard frame with loading label
        self.dashboard_frame = ttk.Frame(self.dashboard_tab)
        self.dashboard_frame.pack(fill=tk.BOTH, expand=True, pady=5, padx=10)
        
        # Add a label for loading/status messages
        self.dashboard_status_label = ttk.Label(self.dashboard_frame, text="")
        self.dashboard_status_label.pack(pady=10)
    
    def setup_settings_tab(self):
        # Change password
        password_frame = ttk.LabelFrame(self.settings_tab, text="Change Admin Password", padding="10")
        password_frame.pack(fill=tk.X, pady=10)
        
        current_password_frame = ttk.Frame(password_frame)
        current_password_frame.pack(fill=tk.X, pady=5)
        ttk.Label(current_password_frame, text="Current Password:").pack(side=tk.LEFT, padx=5)
        self.current_password_entry = ttk.Entry(current_password_frame, width=20, show="*")
        self.current_password_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        new_password_frame = ttk.Frame(password_frame)
        new_password_frame.pack(fill=tk.X, pady=5)
        ttk.Label(new_password_frame, text="New Password:").pack(side=tk.LEFT, padx=5)
        self.new_password_entry = ttk.Entry(new_password_frame, width=20, show="*")
        self.new_password_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        change_password_button = ttk.Button(password_frame, text="Change Password", command=self.change_admin_password)
        change_password_button.pack(pady=5)
        
        # Server info
        info_frame = ttk.LabelFrame(self.settings_tab, text="Server Information", padding="10")
        info_frame.pack(fill=tk.X, pady=10)
        
        self.server_info_label = ttk.Label(info_frame, text="Click 'Get Server Info' to retrieve information")
        self.server_info_label.pack(pady=5)
        
        get_info_button = ttk.Button(info_frame, text="Get Server Info", command=self.get_server_info)
        get_info_button.pack(pady=5)

    def setup_audit_log_tab(self):
        refresh_button = ttk.Button(self.audit_log_tab, text="Refresh Log", command=self.refresh_audit_log)
        refresh_button.pack(pady=5)

        self.audit_tree = ttk.Treeview(self.audit_log_tab, columns=('Timestamp', 'Details'), show='headings')
        self.audit_tree.heading('Timestamp', text='Timestamp')
        self.audit_tree.heading('Details', text='Action Details')
        self.audit_tree.column('Timestamp', width=180)
        self.audit_tree.column('Details', width=400)

        audit_scrollbar = ttk.Scrollbar(self.audit_log_tab, orient=tk.VERTICAL, command=self.audit_tree.yview)
        self.audit_tree.configure(yscroll=audit_scrollbar.set)

        self.audit_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        audit_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def setup_detailed_report_tab(self):
        # Main controls frame
        controls_frame = ttk.LabelFrame(self.detailed_report_tab, text="Report Controls", padding="10")
        controls_frame.pack(fill=tk.X, pady=5, padx=10)

        # Staff selection
        staff_select_frame = ttk.Frame(controls_frame)
        staff_select_frame.pack(fill=tk.X, pady=5)
        ttk.Label(staff_select_frame, text="Select Staff:").pack(side=tk.LEFT, padx=5)
        
        self.staff_list_var = tk.StringVar()
        self.staff_dropdown = ttk.Combobox(staff_select_frame, textvariable=self.staff_list_var, width=20, state="readonly")
        self.staff_dropdown.pack(side=tk.LEFT, padx=5)
        self.staff_dropdown.bind("<<ComboboxSelected>>", self.on_staff_selected)

        ttk.Label(staff_select_frame, text="or enter code:").pack(side=tk.LEFT, padx=5)
        self.staff_code_entry = ttk.Entry(staff_select_frame, width=15)
        self.staff_code_entry.pack(side=tk.LEFT, padx=5)
        self.staff_code_entry.bind('<KeyRelease>', self.on_code_typed)

        # Date range selection
        date_frame = ttk.Frame(controls_frame)
        date_frame.pack(fill=tk.X, pady=5)
        ttk.Label(date_frame, text="Date Range:").pack(side=tk.LEFT, padx=5)
        
        self.report_start_date_var = tk.StringVar()
        self.report_start_date_entry = ttk.Entry(date_frame, textvariable=self.report_start_date_var, width=12)
        self.report_start_date_entry.pack(side=tk.LEFT, padx=2)
        
        ttk.Button(date_frame, text="📅", command=self.pick_report_start_date).pack(side=tk.LEFT)
        
        ttk.Label(date_frame, text="to").pack(side=tk.LEFT, padx=5)
        
        self.report_end_date_var = tk.StringVar()
        self.report_end_date_entry = ttk.Entry(date_frame, textvariable=self.report_end_date_var, width=12)
        self.report_end_date_entry.pack(side=tk.LEFT, padx=2)
        
        ttk.Button(date_frame, text="📅", command=self.pick_report_end_date).pack(side=tk.LEFT)
        
        # Set default values
        today = datetime.now().strftime('%Y-%m-%d')
        thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        self.report_start_date_var.set(thirty_days_ago)
        self.report_end_date_var.set(today)

        # Buttons
        button_frame = ttk.Frame(controls_frame)
        button_frame.pack(fill=tk.X, pady=10)
        ttk.Button(button_frame, text="Generate Report", command=self.generate_detailed_report).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Export User Report", command=self.export_single_user_report).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Export All Staff", command=self.export_all_staff_report).pack(side=tk.LEFT, padx=5)

        # Report display frame
        report_frame = ttk.LabelFrame(self.detailed_report_tab, text="Report Data", padding="10")
        report_frame.pack(fill=tk.BOTH, expand=True, pady=5, padx=10)

        # Create a frame for the treeview and scrollbars
        detail_tree_frame = ttk.Frame(report_frame)
        detail_tree_frame.pack(fill=tk.BOTH, expand=True)

        # Create treeview for detailed report
        self.detail_report_tree = ttk.Treeview(detail_tree_frame, columns=('ID', 'Clock In', 'Clock Out', 'Type', 'Hours', 'Earnings'), show='headings')
        
        self.detail_report_tree.heading('ID', text='ID')
        self.detail_report_tree.heading('Clock In', text='Clock In')
        self.detail_report_tree.heading('Clock Out', text='Clock Out')
        self.detail_report_tree.heading('Type', text='Type')
        self.detail_report_tree.heading('Hours', text='Hours')
        self.detail_report_tree.heading('Earnings', text='Earnings')

        self.detail_report_tree.column('ID', width=40)
        self.detail_report_tree.column('Clock In', width=150)
        self.detail_report_tree.column('Clock Out', width=150)
        self.detail_report_tree.column('Type', width=60)
        self.detail_report_tree.column('Hours', width=60)
        self.detail_report_tree.column('Earnings', width=80)

        # Add scrollbars
        detail_v_scrollbar = ttk.Scrollbar(detail_tree_frame, orient=tk.VERTICAL, command=self.detail_report_tree.yview)
        detail_h_scrollbar = ttk.Scrollbar(detail_tree_frame, orient=tk.HORIZONTAL, command=self.detail_report_tree.xview)
        self.detail_report_tree.configure(yscrollcommand=detail_v_scrollbar.set, xscrollcommand=detail_h_scrollbar.set)

        # Pack treeview and scrollbars
        self.detail_report_tree.grid(row=0, column=0, sticky='nsew')
        detail_v_scrollbar.grid(row=0, column=1, sticky='ns')
        detail_h_scrollbar.grid(row=1, column=0, sticky='ew')

        detail_tree_frame.grid_rowconfigure(0, weight=1)
        detail_tree_frame.grid_columnconfigure(0, weight=1)

        # Summary label
        self.detail_summary_label = ttk.Label(report_frame, text="", font=("Arial", 10, "bold"))
        self.detail_summary_label.pack(pady=5)

    def setup_notes_export_tab(self):
        # Main controls frame
        controls_frame = ttk.LabelFrame(self.notes_export_tab, text="Notes Export Controls", padding="10")
        controls_frame.pack(fill=tk.X, pady=5, padx=10)

        # Staff selection
        staff_select_frame = ttk.Frame(controls_frame)
        staff_select_frame.pack(fill=tk.X, pady=5)
        ttk.Label(staff_select_frame, text="Select Staff:").pack(side=tk.LEFT, padx=5)
        
        self.notes_staff_list_var = tk.StringVar()
        self.notes_staff_dropdown = ttk.Combobox(staff_select_frame, textvariable=self.notes_staff_list_var, width=20, state="readonly")
        self.notes_staff_dropdown.pack(side=tk.LEFT, padx=5)
        self.notes_staff_dropdown.bind("<<ComboboxSelected>>", self.on_notes_staff_selected)

        ttk.Label(staff_select_frame, text="or enter code:").pack(side=tk.LEFT, padx=5)
        self.notes_staff_code_entry = ttk.Entry(staff_select_frame, width=15)
        self.notes_staff_code_entry.pack(side=tk.LEFT, padx=5)
        self.notes_staff_code_entry.bind('<KeyRelease>', self.on_notes_code_typed)

        # Date range selection
        date_frame = ttk.Frame(controls_frame)
        date_frame.pack(fill=tk.X, pady=5)
        ttk.Label(date_frame, text="Date Range:").pack(side=tk.LEFT, padx=5)
        
        self.notes_start_date_var = tk.StringVar()
        self.notes_start_date_entry = ttk.Entry(date_frame, textvariable=self.notes_start_date_var, width=12)
        self.notes_start_date_entry.pack(side=tk.LEFT, padx=2)
        
        ttk.Button(date_frame, text="📅", command=self.pick_notes_start_date).pack(side=tk.LEFT)
        
        ttk.Label(date_frame, text="to").pack(side=tk.LEFT, padx=5)
        
        self.notes_end_date_var = tk.StringVar()
        self.notes_end_date_entry = ttk.Entry(date_frame, textvariable=self.notes_end_date_var, width=12)
        self.notes_end_date_entry.pack(side=tk.LEFT, padx=2)
        
        ttk.Button(date_frame, text="📅", command=self.pick_notes_end_date).pack(side=tk.LEFT)
        
        # Set default values
        today = datetime.now().strftime('%Y-%m-%d')
        thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        self.notes_start_date_var.set(thirty_days_ago)
        self.notes_end_date_var.set(today)

        # Question selection
        question_frame = ttk.Frame(controls_frame)
        question_frame.pack(fill=tk.X, pady=5)
        ttk.Label(question_frame, text="Questions to Include:").pack(side=tk.LEFT, padx=5)
        
        self.question_vars = {}
        questions = [
            "⚠ ملاحظات/فواتير",
            "⿢ فواتير الشراء:",
            "⿣ حسابات التعاقدات (Pending):",
            "⿤ طلبات العملاء الخاصة:",
            "💬 ⿥ رسائل WhatsApp",
            "⿦ المصاريف والدرات:",
            "🧠 ملاحظات عامة"
        ]
        
        for i, question in enumerate(questions):
            var = tk.BooleanVar(value=True)
            self.question_vars[question] = var
            cb = ttk.Checkbutton(question_frame, text=question, variable=var)
            cb.pack(side=tk.LEFT, padx=5, anchor='w')

        # Buttons
        button_frame = ttk.Frame(controls_frame)
        button_frame.pack(fill=tk.X, pady=10)
        ttk.Button(button_frame, text="Generate Notes Report", command=self.generate_notes_report).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Export Notes to Excel", command=self.export_notes_to_excel).pack(side=tk.LEFT, padx=5)

        # Report display frame
        report_frame = ttk.LabelFrame(self.notes_export_tab, text="Notes Data", padding="10")
        report_frame.pack(fill=tk.BOTH, expand=True, pady=5, padx=10)

        # Create a frame for the treeview and scrollbars
        notes_tree_frame = ttk.Frame(report_frame)
        notes_tree_frame.pack(fill=tk.BOTH, expand=True)

        # Create treeview for notes report
        self.notes_tree = ttk.Treeview(notes_tree_frame, columns=('ID', 'Staff Code', 'Name', 'Clock In', 'Clock Out', 'Question', 'Answer'), show='headings')
        
        self.notes_tree.heading('ID', text='ID')
        self.notes_tree.heading('Staff Code', text='Staff Code')
        self.notes_tree.heading('Name', text='Name')
        self.notes_tree.heading('Clock In', text='Clock In')
        self.notes_tree.heading('Clock Out', text='Clock Out')
        self.notes_tree.heading('Question', text='Question')
        self.notes_tree.heading('Answer', text='Answer')

        self.notes_tree.column('ID', width=40)
        self.notes_tree.column('Staff Code', width=100)
        self.notes_tree.column('Name', width=150)
        self.notes_tree.column('Clock In', width=150)
        self.notes_tree.column('Clock Out', width=150)
        self.notes_tree.column('Question', width=150)
        self.notes_tree.column('Answer', width=200)

        # Add scrollbars
        notes_v_scrollbar = ttk.Scrollbar(notes_tree_frame, orient=tk.VERTICAL, command=self.notes_tree.yview)
        notes_h_scrollbar = ttk.Scrollbar(notes_tree_frame, orient=tk.HORIZONTAL, command=self.notes_tree.xview)
        self.notes_tree.configure(yscrollcommand=notes_v_scrollbar.set, xscrollcommand=notes_h_scrollbar.set)

        # Pack treeview and scrollbars
        self.notes_tree.grid(row=0, column=0, sticky='nsew')
        notes_v_scrollbar.grid(row=0, column=1, sticky='ns')
        notes_h_scrollbar.grid(row=1, column=0, sticky='ew')

        notes_tree_frame.grid_rowconfigure(0, weight=1)
        notes_tree_frame.grid_columnconfigure(0, weight=1)

        # Summary label
        self.notes_summary_label = ttk.Label(report_frame, text="", font=("Arial", 10, "bold"))
        self.notes_summary_label.pack(pady=5)

    # Date picker methods
    def pick_start_date(self):
        top = tk.Toplevel(self.root)
        top.title("Select Start Date")
        cal = DateEntry(top, width=12, background='darkblue',
                        foreground='white', borderwidth=2)
        cal.pack(padx=10, pady=10)
        
        def set_date():
            self.date_filter_var.get().set(cal.get_date().strftime('%Y-%m-%d'))
            top.destroy()
        
        ttk.Button(top, text="OK", command=set_date).pack(pady=5)
    
    def pick_end_date(self):
        top = tk.Toplevel(self.root)
        top.title("Select End Date")
        cal = DateEntry(top, width=12, background='darkblue',
                        foreground='white', borderwidth=2)
        cal.pack(padx=10, pady=10)
        
        def set_date():
            self.end_date_var.set(cal.get_date().strftime('%Y-%m-%d'))
            top.destroy()
        
        ttk.Button(top, text="OK", command=set_date).pack(pady=5)
    
    def pick_dashboard_start_date(self):
        top = tk.Toplevel(self.root)
        top.title("Select Start Date")
        cal = DateEntry(top, width=12, background='darkblue',
                        foreground='white', borderwidth=2)
        cal.pack(padx=10, pady=10)
        
        def set_date():
            self.dashboard_start_date_var.set(cal.get_date().strftime('%Y-%m-%d'))
            top.destroy()
        
        ttk.Button(top, text="OK", command=set_date).pack(pady=5)
    
    def pick_dashboard_end_date(self):
        top = tk.Toplevel(self.root)
        top.title("Select End Date")
        cal = DateEntry(top, width=12, background='darkblue',
                        foreground='white', borderwidth=2)
        cal.pack(padx=10, pady=10)
        
        def set_date():
            self.dashboard_end_date_var.set(cal.get_date().strftime('%Y-%m-%d'))
            top.destroy()
        
        ttk.Button(top, text="OK", command=set_date).pack(pady=5)
    
    def pick_report_start_date(self):
        top = tk.Toplevel(self.root)
        top.title("Select Start Date")
        cal = DateEntry(top, width=12, background='darkblue',
                        foreground='white', borderwidth=2)
        cal.pack(padx=10, pady=10)
        
        def set_date():
            self.report_start_date_var.set(cal.get_date().strftime('%Y-%m-%d'))
            top.destroy()
        
        ttk.Button(top, text="OK", command=set_date).pack(pady=5)
    
    def pick_report_end_date(self):
        top = tk.Toplevel(self.root)
        top.title("Select End Date")
        cal = DateEntry(top, width=12, background='darkblue',
                        foreground='white', borderwidth=2)
        cal.pack(padx=10, pady=10)
        
        def set_date():
            self.report_end_date_var.set(cal.get_date().strftime('%Y-%m-%d'))
            top.destroy()
        
        ttk.Button(top, text="OK", command=set_date).pack(pady=5)
    
    def pick_notes_start_date(self):
        top = tk.Toplevel(self.root)
        top.title("Select Start Date")
        cal = DateEntry(top, width=12, background='darkblue',
                        foreground='white', borderwidth=2)
        cal.pack(padx=10, pady=10)
        
        def set_date():
            self.notes_start_date_var.set(cal.get_date().strftime('%Y-%m-%d'))
            top.destroy()
        
        ttk.Button(top, text="OK", command=set_date).pack(pady=5)
    
    def pick_notes_end_date(self):
        top = tk.Toplevel(self.root)
        top.title("Select End Date")
        cal = DateEntry(top, width=12, background='darkblue',
                        foreground='white', borderwidth=2)
        cal.pack(padx=10, pady=10)
        
        def set_date():
            self.notes_end_date_var.set(cal.get_date().strftime('%Y-%m-%d'))
            top.destroy()
        
        ttk.Button(top, text="OK", command=set_date).pack(pady=5)

    def check_staff_status(self, event=None):
        if not self.connected:
            return
            
        staff_code = self.code_entry.get().strip()
        if len(staff_code) < 3:
            self.reset_attendance_ui()
            return

        try:
            response = requests.post(
                f"{self.server_url}/api/get_active_session",
                json={"staff_code": staff_code},
                timeout=5
            )
            if response.status_code == 200:
                try:
                    data = response.json()
                    if data.get('success'):
                        if data.get('is_active'):
                            session_type = data.get('session_type')
                            if session_type == 'work':
                                self.status_display.config(text=f"Clocked In ({staff_code})", foreground="green")
                                self.main_action_button.config(text="Clock Out", state="normal")
                                self.break_button.config(state="normal")
                                self.return_button.config(state="disabled")
                                self.leave_button.config(state="disabled")
                            elif session_type == 'break':
                                self.status_display.config(text=f"On Break ({staff_code})", foreground="orange")
                                self.main_action_button.config(state="disabled")
                                self.break_button.config(state="disabled")
                                self.return_button.config(state="normal")
                                self.leave_button.config(state="disabled")
                        else:
                            self.status_display.config(text=f"Not clocked in ({staff_code})", foreground="blue")
                            self.main_action_button.config(text="Clock In", state="normal")
                            self.break_button.config(state="disabled")
                            self.return_button.config(state="disabled")
                            self.leave_button.config(state="normal")
                    else:
                        self.reset_attendance_ui()
                except json.JSONDecodeError:
                    self.reset_attendance_ui()
            else:
                self.reset_attendance_ui()
        except requests.exceptions.RequestException:
            self.reset_attendance_ui()

    def reset_attendance_ui(self):
        self.status_display.config(text="Please enter your code", foreground="blue")
        self.main_action_button.config(text="Clock In", state="disabled")
        self.break_button.config(state="disabled")
        self.return_button.config(state="disabled")
        self.leave_button.config(state="disabled")

    def main_action(self):
        staff_code = self.code_entry.get().strip()
        if not staff_code:
            messagebox.showerror("Error", "Please enter a staff code")
            return
        
        button_text = self.main_action_button.cget("text")
        
        if button_text == "Clock In":
            self.clock_in(staff_code)
        elif button_text == "Clock Out":
            self.clock_out(staff_code)

    def clock_in(self, staff_code):
        try:
            response = requests.post(
                f"{self.server_url}/api/clock_in",
                json={"staff_code": staff_code},
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    self.attendance_status.config(text=data.get('message', "Clocked in successfully"), foreground="green")
                    self.check_staff_status()
                else:
                    messagebox.showerror("Error", data.get('message', "Clock in failed"))
            else:
                messagebox.showerror("Error", f"Server returned status code: {response.status_code}")
        except requests.exceptions.RequestException as e:
            messagebox.showerror("Error", f"Failed to connect to server: {str(e)}")

    def clock_out(self, staff_code):
        # Show questions dialog
        dialog = QuestionsDialog(self.root)
        self.root.wait_window(dialog)
        
        if dialog.result is None:
            return  # User cancelled
        
        notes = json.dumps(dialog.result)
        
        try:
            response = requests.post(
                f"{self.server_url}/api/clock_out",
                json={"staff_code": staff_code, "notes": notes},
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    self.attendance_status.config(text=data.get('message', "Clocked out successfully"), foreground="green")
                    self.check_staff_status()
                else:
                    messagebox.showerror("Error", data.get('message', "Clock out failed"))
            else:
                messagebox.showerror("Error", f"Server returned status code: {response.status_code}")
        except requests.exceptions.RequestException as e:
            messagebox.showerror("Error", f"Failed to connect to server: {str(e)}")

    def start_break(self, staff_code):
        try:
            response = requests.post(
                f"{self.server_url}/api/clock_break",
                json={"staff_code": staff_code},
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    self.attendance_status.config(text=data.get('message', "Break started successfully"), foreground="green")
                    self.check_staff_status()
                else:
                    messagebox.showerror("Error", data.get('message', "Failed to start break"))
            else:
                messagebox.showerror("Error", f"Server returned status code: {response.status_code}")
        except requests.exceptions.RequestException as e:
            messagebox.showerror("Error", f"Failed to connect to server: {str(e)}")

    def end_break(self, staff_code):
        try:
            response = requests.post(
                f"{self.server_url}/api/clock_return_from_break",
                json={"staff_code": staff_code},
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    self.attendance_status.config(text=data.get('message', "Returned from break successfully"), foreground="green")
                    self.check_staff_status()
                else:
                    messagebox.showerror("Error", data.get('message', "Failed to return from break"))
            else:
                messagebox.showerror("Error", f"Server returned status code: {response.status_code}")
        except requests.exceptions.RequestException as e:
            messagebox.showerror("Error", f"Failed to connect to server: {str(e)}")

    def request_leave(self):
        staff_code = self.code_entry.get().strip()
        if not staff_code:
            messagebox.showerror("Error", "Please enter a staff code")
            return
        
        dialog = LeaveRequestDialog(self.root, staff_code)
        self.root.wait_window(dialog)
        
        if dialog.result is None:
            return  # User cancelled
        
        try:
            response = requests.post(
                f"{self.server_url}/api/submit_leave_request",
                json=dialog.result,
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    messagebox.showinfo("Success", data.get('message', "Leave request submitted successfully"))
                else:
                    messagebox.showerror("Error", data.get('message', "Failed to submit leave request"))
            else:
                messagebox.showerror("Error", f"Server returned status code: {response.status_code}")
        except requests.exceptions.RequestException as e:
            messagebox.showerror("Error", f"Failed to connect to server: {str(e)}")


    def admin_login(self):
        """Handles the admin login process."""
        password = self.password_entry.get().strip()

        if not password:
            self.admin_status.config(text="Password cannot be empty.", foreground="red")
            return

        try:
            response = requests.post(f"{self.server_url}/api/admin_login", json={"password": password}, timeout=5)

            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    # Login successful
                    self.admin_status.config(text="Login successful", foreground="green")

                    # --- ROBUST FIX ---
                    # Enable all admin sub-tabs by iterating over their IDs, not their numeric indices.
                    # This prevents "out of bounds" errors.
                    for tab_id in self.admin_notebook.tabs():
                        self.admin_notebook.tab(tab_id, state="normal")
                    # --- END OF FIX ---

                    # Load initial data for the tabs
                    self.refresh_staff_data()
                    self.refresh_shift_data()
                    self.refresh_holiday_data()
                    self.refresh_leave_data()
                    self.refresh_audit_log()
                    # Add other refresh calls as needed

                else:
                    self.admin_status.config(text="Invalid password", foreground="red")
            else:
                self.admin_status.config(text=f"Server error: {response.status_code}", foreground="red")

        except requests.exceptions.RequestException as e:
            self.admin_status.config(text="Connection error", foreground="red")
            messagebox.showerror("Connection Error", f"Could not connect to the server: {e}")
        except Exception as e:
            self.admin_status.config(text="An unexpected error occurred", foreground="red")
            messagebox.showerror("Error", f"An error occurred during login: {e}")


    def _admin_pw(self):
        pw = self.password_entry.get().strip()
        if not pw:
            messagebox.showerror("Error", "Admin password required")
            return None
        return pw

    def crm_refresh_leads(self):
        """Pull ALL leads from SQLite DB via server and fill the tree."""
        pw = self.password_entry.get().strip()
        if not pw:
            messagebox.showerror("Error", "Admin password required")
            return

        try:
            r = requests.post(f"{self.server_url}/api/crm_get_leads",
                            json={"password": pw}, timeout=8)
            r.raise_for_status()
            data = r.json()
            if not data.get('success'):
                raise ValueError(data.get('message', 'Unknown error'))

            # clear
            for i in self.crm_tree.get_children():
                self.crm_tree.delete(i)

            # fill
            for lead in data.get('leads', []):
                self.crm_tree.insert('', 'end', values=(
                    lead.get('id'),
                    lead.get('name'),
                    lead.get('phone'),
                    lead.get('status'),
                    lead.get('target'),
                    lead.get('assigned_to'),
                    (lead.get('notes') or '')[:50] + ('...' if len(lead.get('notes',''))>50 else ''),
                    lead.get('created_at','')[:19].replace('T',' ')
                ))

            self.crm_status.config(text=f"{len(data.get('leads',[]))} leads – up to date")
        except Exception as e:
            messagebox.showerror("CRM Error", f"Refresh failed: {e}")
            self.crm_status.config(text="Refresh failed", foreground="red")

    def crm_add_lead(self):
        dlg = CrmLeadDialog(self.root, title="Add Lead", server_url=self.server_url,
                            admin_pw=self._admin_pw())
        self.root.wait_window(dlg)
        if dlg.result:
            self.crm_refresh_leads()

    def crm_edit_lead(self):
        sel = self.crm_tree.selection()
        if not sel:
            messagebox.showwarning("Select", "Please select a lead")
            return
        item = self.crm_tree.item(sel[0])['values']
        lead_id = item[0]

        # fetch full record (notes can be long)
        pw = self._admin_pw()
        if not pw: return
        try:
            r = requests.post(f"{self.server_url}/api/crm_get_lead",
                            json={"password": pw, "lead_id": lead_id}, timeout=5)
            lead = r.json().get('lead')
        except:
            messagebox.showerror("Error", "Could not fetch lead data")
            return

        dlg = CrmLeadDialog(self.root, title="Edit Lead", server_url=self.server_url,
                            admin_pw=pw, lead_data=lead)
        self.root.wait_window(dlg)
        if dlg.result:
            self.crm_refresh_leads()

    def crm_delete_lead(self):
        sel = self.crm_tree.selection()
        if not sel:
            messagebox.showwarning("Select", "Please select a lead")
            return
        lead_id = self.crm_tree.item(sel[0])['values'][0]

        if not messagebox.askyesno("Delete", "Delete this lead permanently?"):
            return

        pw = self._admin_pw()
        if not pw: return
        try:
            r = requests.post(f"{self.server_url}/api/crm_delete_lead",
                            json={"password": pw, "lead_id": lead_id}, timeout=5)
            resp = r.json()
            if resp.get('success'):
                self.crm_status.config(text="Lead deleted")
                self.crm_refresh_leads()
            else:
                raise ValueError(resp.get('message'))
        except Exception as e:
            messagebox.showerror("Error", f"Delete failed: {e}")

    def crm_change_target(self):
        sel = self.crm_tree.selection()
        if not sel:
            messagebox.showwarning("Select", "Please select a lead")
            return
        lead_id = self.crm_tree.item(sel[0])['values'][0]

        # fetch current target list
        pw = self._admin_pw()
        if not pw: return
        try:
            r = requests.post(f"{self.server_url}/api/crm_get_targets",
                            json={"password": pw}, timeout=5)
            targets = r.json().get('targets', [])
        except:
            targets = []

        target = simpledialog.askstring(
            "Change Target",
            "New target (choose from list or type):",
            initialvalue=self.crm_tree.item(sel[0])['values'][4])
        if target is None: return
        if target not in targets:
            if not messagebox.askyesno("New Target", f"'{target}' is not in the master list. Add it?"):
                return

        try:
            r = requests.post(f"{self.server_url}/api/crm_update_target",
                            json={"password": pw, "lead_id": lead_id, "target": target}, timeout=5)
            if r.json().get('success'):
                self.crm_status.config(text=f"Target → {target}")
                self.crm_refresh_leads()
        except Exception as e:
            messagebox.showerror("Error", f"Target update failed: {e}")
    
    

    def refresh_attendance_data(self):
        """Fetch attendance records for the selected date range and populate the tree."""
        pw = self.password_entry.get().strip()
        if not pw:
            messagebox.showerror("Error", "Admin password required")
            return

        start = self.att_start_date.get_date().strftime('%Y-%m-%d')
        end = self.att_end_date.get_date().strftime('%Y-%m-%d')

        try:
            r = requests.post(f"{self.server_url}/api/get_attendance",
                            json={"password": pw, "start_date": start, "end_date": end}, timeout=10)
            r.raise_for_status()
            data = r.json()
            if not data.get('success'):
                raise ValueError(data.get('message', 'Unknown error'))

            # Clear tree
            for i in self.attendance_tree.get_children():
                self.attendance_tree.delete(i)

            # Fill tree with proper handling of 'Active' clock_out values
            for rec in data.get('data', []):
                clock_out = rec['clock_out'] if rec['clock_out'] != 'Active' else 'Active'
                
                # Only calculate hours and earnings if clock_out is not 'Active'
                if rec['clock_out'] != 'Active':
                    hours = rec['hours']
                    earnings = rec['earnings']
                else:
                    hours = 0.0
                    earnings = 0.0
                    
                self.attendance_tree.insert('', 'end', values=(
                    rec['id'],
                    rec['staff_code'],
                    rec['name'],
                    rec['clock_in'],
                    clock_out,
                    f"{hours:.2f}",
                    f"{earnings:.2f}",
                    rec.get('notes') or '',
                    rec['session_type']
                ))

            self.attendance_status.config(text=f"{len(data.get('data',[]))} records – up to date", foreground="green")
        except Exception as e:
            messagebox.showerror("Refresh Error", f"Failed to load data:\n{e}")
            self.attendance_status.config(text="Refresh failed", foreground="red")

    def refresh_staff_data(self):
        if not self.connected:
            messagebox.showerror("Error", "Not connected to server")
            return
        
        password = self.password_entry.get()
        if not password:
            messagebox.showerror("Error", "Please enter admin password")
            return
        
        try:
            response = requests.post(
                f"{self.server_url}/api/get_staff",  # Fixed: Changed from get_staff_data to get_staff
                json={"password": password},
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    # Clear existing data
                    for item in self.staff_tree.get_children():
                        self.staff_tree.delete(item)
                    
                    # Add new data
                    for record in data.get('data', []):
                        self.staff_tree.insert('', 'end', values=(
                            record.get('id'),
                            record.get('staff_code'),
                            record.get('name'),
                            record.get('hourly_rate'),
                            record.get('shift_name')
                        ))
                    
                    # Update staff dropdowns in detailed report and notes export tabs
                    staff_list = [(record.get('staff_code'), record.get('name')) for record in data.get('data', [])]
                    self.staff_dropdown['values'] = [f"{code} - {name}" for code, name in staff_list]
                    self.notes_staff_dropdown['values'] = [f"{code} - {name}" for code, name in staff_list]
                else:
                    messagebox.showerror("Error", data.get('message', "Failed to get staff data"))
            else:
                messagebox.showerror("Error", f"Server returned status code: {response.status_code}")
        except requests.exceptions.RequestException as e:
            messagebox.showerror("Error", f"Failed to connect to server: {str(e)}")

    def refresh_shift_data(self):
        if not self.connected:
            messagebox.showerror("Error", "Not connected to server")
            return
        
        password = self.password_entry.get()
        if not password:
            messagebox.showerror("Error", "Please enter admin password")
            return
        
        try:
            response = requests.post(
                f"{self.server_url}/api/get_shifts",
                json={"password": password},
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    # Clear existing data
                    for item in self.shift_tree.get_children():
                        self.shift_tree.delete(item)
                    
                    # Add new data
                    for record in data.get('data', []):
                        self.shift_tree.insert('', 'end', values=(
                            record.get('id'),
                            record.get('name'),
                            record.get('start_time'),
                            record.get('end_time')
                        ))
                else:
                    messagebox.showerror("Error", data.get('message', "Failed to get shift data"))
            else:
                messagebox.showerror("Error", f"Server returned status code: {response.status_code}")
        except requests.exceptions.RequestException as e:
            messagebox.showerror("Error", f"Failed to connect to server: {str(e)}")

    def refresh_holiday_data(self):
        if not self.connected:
            messagebox.showerror("Error", "Not connected to server")
            return
        
        password = self.password_entry.get()
        if not password:
            messagebox.showerror("Error", "Please enter admin password")
            return
        
        try:
            response = requests.post(
                f"{self.server_url}/api/get_holidays",
                json={"password": password},
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    # Clear existing data
                    for item in self.holiday_tree.get_children():
                        self.holiday_tree.delete(item)
                    
                    # Add new data
                    for record in data.get('data', []):
                        self.holiday_tree.insert('', 'end', values=(
                            record.get('id'),
                            record.get('date'),
                            record.get('name'),
                            "Yes" if record.get('paid') else "No"
                        ))
                else:
                    messagebox.showerror("Error", data.get('message', "Failed to get holiday data"))
            else:
                messagebox.showerror("Error", f"Server returned status code: {response.status_code}")
        except requests.exceptions.RequestException as e:
            messagebox.showerror("Error", f"Failed to connect to server: {str(e)}")

    def refresh_leave_data(self):
        if not self.connected:
            messagebox.showerror("Error", "Not connected to server")
            return
        
        password = self.password_entry.get()
        if not password:
            messagebox.showerror("Error", "Please enter admin password")
            return
        
        try:
            response = requests.post(
                f"{self.server_url}/api/get_leave_requests",
                json={"password": password},
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    # Clear existing data
                    for item in self.leave_tree.get_children():
                        self.leave_tree.delete(item)
                    
                    # Add new data
                    for record in data.get('data', []):
                        self.leave_tree.insert('', 'end', values=(
                            record.get('id'),
                            record.get('staff_code'),
                            record.get('name'),
                            record.get('start_date'),
                            record.get('end_date'),
                            record.get('reason'),
                            record.get('status')
                        ))
                else:
                    messagebox.showerror("Error", data.get('message', "Failed to get leave data"))
            else:
                messagebox.showerror("Error", f"Server returned status code: {response.status_code}")
        except requests.exceptions.RequestException as e:
            messagebox.showerror("Error", f"Failed to connect to server: {str(e)}")

    def approve_leave_request(self):
        selected_item = self.leave_tree.selection()
        if not selected_item:
            messagebox.showerror("Error", "Please select a leave request to approve")
            return
        
        item = self.leave_tree.item(selected_item[0])
        request_id = item['values'][0]
        
        password = self.password_entry.get()
        if not password:
            messagebox.showerror("Error", "Please enter admin password")
            return
        
        try:
            response = requests.post(
                f"{self.server_url}/api/update_leave_request",
                json={
                    "password": password,
                    "request_id": request_id,
                    "status": "approved"
                },
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    messagebox.showinfo("Success", data.get('message', "Leave request approved"))
                    self.refresh_leave_data()
                else:
                    messagebox.showerror("Error", data.get('message', "Failed to approve leave request"))
            else:
                messagebox.showerror("Error", f"Server returned status code: {response.status_code}")
        except requests.exceptions.RequestException as e:
            messagebox.showerror("Error", f"Failed to connect to server: {str(e)}")

    def reject_leave_request(self):
        selected_item = self.leave_tree.selection()
        if not selected_item:
            messagebox.showerror("Error", "Please select a leave request to reject")
            return
        
        item = self.leave_tree.item(selected_item[0])
        request_id = item['values'][0]
        
        password = self.password_entry.get()
        if not password:
            messagebox.showerror("Error", "Please enter admin password")
            return
        
        try:
            response = requests.post(
                f"{self.server_url}/api/update_leave_request",
                json={
                    "password": password,
                    "request_id": request_id,
                    "status": "rejected"
                },
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    messagebox.showinfo("Success", data.get('message', "Leave request rejected"))
                    self.refresh_leave_data()
                else:
                    messagebox.showerror("Error", data.get('message', "Failed to reject leave request"))
            else:
                messagebox.showerror("Error", f"Server returned status code: {response.status_code}")
        except requests.exceptions.RequestException as e:
            messagebox.showerror("Error", f"Failed to connect to server: {str(e)}")

    def add_staff(self):
        dialog = StaffDialog(self.root)
        self.root.wait_window(dialog)
        
        if dialog.result is None:
            return  # User cancelled
        
        password = self.password_entry.get()
        if not password:
            messagebox.showerror("Error", "Please enter admin password")
            return
        
        try:
            response = requests.post(
                f"{self.server_url}/api/add_staff",
                json={
                    "password": password,
                    **dialog.result
                },
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    messagebox.showinfo("Success", data.get('message', "Staff added successfully"))
                    self.refresh_staff_data()
                else:
                    messagebox.showerror("Error", data.get('message', "Failed to add staff"))
            else:
                messagebox.showerror("Error", f"Server returned status code: {response.status_code}")
        except requests.exceptions.RequestException as e:
            messagebox.showerror("Error", f"Failed to connect to server: {str(e)}")

    def update_staff(self):
        selected_item = self.staff_tree.selection()
        if not selected_item:
            messagebox.showerror("Error", "Please select a staff member to update")
            return
        
        item = self.staff_tree.item(selected_item[0])
        staff_code = item['values'][1]
        
        dialog = StaffDialog(self.root, staff_code)
        self.root.wait_window(dialog)
        
        if dialog.result is None:
            return  # User cancelled
        
        password = self.password_entry.get()
        if not password:
            messagebox.showerror("Error", "Please enter admin password")
            return
        
        try:
            response = requests.post(
                f"{self.server_url}/api/update_staff",
                json={
                    "password": password,
                    "staff_code": staff_code,
                    **dialog.result
                },
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    messagebox.showinfo("Success", data.get('message', "Staff updated successfully"))
                    self.refresh_staff_data()
                else:
                    messagebox.showerror("Error", data.get('message', "Failed to update staff"))
            else:
                messagebox.showerror("Error", f"Server returned status code: {response.status_code}")
        except requests.exceptions.RequestException as e:
            messagebox.showerror("Error", f"Failed to connect to server: {str(e)}")

    def delete_staff(self):
        selected_item = self.staff_tree.selection()
        if not selected_item:
            messagebox.showerror("Error", "Please select a staff member to delete")
            return
        
        item = self.staff_tree.item(selected_item[0])
        staff_code = item['values'][1]
        name = item['values'][2]
        
        if not messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete {name} ({staff_code})?"):
            return
        
        password = self.password_entry.get()
        if not password:
            messagebox.showerror("Error", "Please enter admin password")
            return
        
        try:
            response = requests.post(
                f"{self.server_url}/api/delete_staff",
                json={
                    "password": password,
                    "staff_code": staff_code
                },
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    messagebox.showinfo("Success", data.get('message', "Staff deleted successfully"))
                    self.refresh_staff_data()
                else:
                    messagebox.showerror("Error", data.get('message', "Failed to delete staff"))
            else:
                messagebox.showerror("Error", f"Server returned status code: {response.status_code}")
        except requests.exceptions.RequestException as e:
            messagebox.showerror("Error", f"Failed to connect to server: {str(e)}")

    def add_shift(self):
        dialog = ShiftDialog(self.root)
        self.root.wait_window(dialog)
        
        if dialog.result is None:
            return  # User cancelled
        
        password = self.password_entry.get()
        if not password:
            messagebox.showerror("Error", "Please enter admin password")
            return
        
        try:
            response = requests.post(
                f"{self.server_url}/api/add_shift",
                json={
                    "password": password,
                    **dialog.result
                },
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    messagebox.showinfo("Success", data.get('message', "Shift added successfully"))
                    self.refresh_shift_data()
                else:
                    messagebox.showerror("Error", data.get('message', "Failed to add shift"))
            else:
                messagebox.showerror("Error", f"Server returned status code: {response.status_code}")
        except requests.exceptions.RequestException as e:
            messagebox.showerror("Error", f"Failed to connect to server: {str(e)}")

    def add_holiday(self):
        dialog = HolidayDialog(self.root)
        self.root.wait_window(dialog)
        
        if dialog.result is None:
            return  # User cancelled
        
        password = self.password_entry.get()
        if not password:
            messagebox.showerror("Error", "Please enter admin password")
            return
        
        try:
            response = requests.post(
                f"{self.server_url}/api/add_holiday",
                json={
                    "password": password,
                    **dialog.result
                },
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    messagebox.showinfo("Success", data.get('message', "Holiday added successfully"))
                    self.refresh_holiday_data()
                else:
                    messagebox.showerror("Error", data.get('message', "Failed to add holiday"))
            else:
                messagebox.showerror("Error", f"Server returned status code: {response.status_code}")
        except requests.exceptions.RequestException as e:
            messagebox.showerror("Error", f"Failed to connect to server: {str(e)}")

    def generate_dashboard(self):
        """Generate dashboard with better error handling"""
        if not self.connected:
            messagebox.showerror("Error", "Not connected to server")
            return
        
        password = self.password_entry.get()
        if not password:
            messagebox.showerror("Error", "Please enter admin password")
            return
        
        try:
            # Show loading message using the label
            self.dashboard_status_label.config(text="Loading dashboard...")
            self.root.update()
            
            response = requests.post(
                f"{self.server_url}/api/get_analytics",
                json={
                    "password": password,
                    "start_date": self.dashboard_start_date_var.get(),
                    "end_date": self.dashboard_end_date_var.get()
                },
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    # Clear existing dashboard (except the status label)
                    for widget in self.dashboard_frame.winfo_children():
                        if widget != self.dashboard_status_label:
                            widget.destroy()
                    
                    # Hide the status label
                    self.dashboard_status_label.pack_forget()
                    
                    # Create charts
                    daily_data = data.get('daily_data', [])
                    staff_data = data.get('staff_data', [])
                    
                    if not daily_data and not staff_data:
                        ttk.Label(self.dashboard_frame, text="No data available for selected date range", font=("Arial", 12)).pack(pady=20)
                        return
                    
                    # Daily attendance chart
                    if daily_data:
                        try:
                            import matplotlib.pyplot as plt
                            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
                            
                            fig, ax = plt.subplots(figsize=(10, 4))
                            dates = [item[0] for item in daily_data]
                            counts = [item[1] for item in daily_data]
                            
                            ax.plot(dates, counts, marker='o')
                            ax.set_title('Daily Attendance')
                            ax.set_xlabel('Date')
                            ax.set_ylabel('Number of Staff')
                            ax.grid(True)
                            
                            # Rotate x-axis labels for better readability
                            plt.xticks(rotation=45)
                            plt.tight_layout()
                            
                            canvas = FigureCanvasTkAgg(fig, master=self.dashboard_frame)
                            canvas.draw()
                            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
                        except ImportError:
                            ttk.Label(self.dashboard_frame, text="Matplotlib not installed. Cannot display charts.", foreground="red").pack(pady=10)
                    
                    # Staff attendance summary
                    if staff_data:
                        staff_frame = ttk.LabelFrame(self.dashboard_frame, text="Staff Attendance Summary")
                        staff_frame.pack(fill=tk.BOTH, expand=True, pady=10)
                        
                        # Create treeview
                        cols = ('Staff Code', 'Name', 'Days', 'Total Hours')
                        staff_tree = ttk.Treeview(staff_frame, columns=cols, show='headings')
                        
                        for col in cols:
                            staff_tree.heading(col, text=col)
                            staff_tree.column(col, width=100)
                        
                        # Add data
                        for record in staff_data:
                            staff_tree.insert('', 'end', values=(
                                record[0],  # staff_code
                                record[1],  # name
                                record[2],  # days
                                f"{record[3]:.2f}"  # total_hours
                            ))
                        
                        # Add scrollbar
                        scrollbar = ttk.Scrollbar(staff_frame, orient=tk.VERTICAL, command=staff_tree.yview)
                        staff_tree.configure(yscrollcommand=scrollbar.set)
                        
                        staff_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
                else:
                    messagebox.showerror("Error", data.get('message', "Failed to generate dashboard"))
            else:
                messagebox.showerror("Error", f"Server returned status code: {response.status_code}")
        except requests.exceptions.RequestException as e:
            messagebox.showerror("Error", f"Failed to connect to server: {str(e)}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate dashboard: {str(e)}")
        finally:
            # Clear loading message
            self.dashboard_status_label.config(text="")

    def change_admin_password(self):
        current_password = self.current_password_entry.get()
        new_password = self.new_password_entry.get()
        
        if not current_password or not new_password:
            messagebox.showerror("Error", "Please enter both current and new passwords")
            return
        
        try:
            response = requests.post(
                f"{self.server_url}/api/change_admin_password",
                json={
                    "current_password": current_password,
                    "new_password": new_password
                },
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    messagebox.showinfo("Success", data.get('message', "Password changed successfully"))
                    self.current_password_entry.delete(0, tk.END)
                    self.new_password_entry.delete(0, tk.END)
                else:
                    messagebox.showerror("Error", data.get('message', "Failed to change password"))
            else:
                messagebox.showerror("Error", f"Server returned status code: {response.status_code}")
        except requests.exceptions.RequestException as e:
            messagebox.showerror("Error", f"Failed to connect to server: {str(e)}")

    def get_server_info(self):
        try:
            response = requests.get(
                f"{self.server_url}/api/server_info",
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    info_text = f"Server Version: {data.get('version', 'Unknown')}\n"
                    info_text += f"Message: {data.get('message', 'No message')}"
                    self.server_info_label.config(text=info_text)
                else:
                    messagebox.showerror("Error", "Server returned an error response")
            else:
                messagebox.showerror("Error", f"Server returned status code: {response.status_code}")
        except requests.exceptions.RequestException as e:
            messagebox.showerror("Error", f"Failed to connect to server: {str(e)}")

    def refresh_audit_log(self):
        if not self.connected:
            messagebox.showerror("Error", "Not connected to server")
            return
        
        password = self.password_entry.get()
        if not password:
            messagebox.showerror("Error", "Please enter admin password")
            return
        
        try:
            response = requests.post(
                f"{self.server_url}/api/get_audit_log",
                json={"password": password},
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    # Clear existing data
                    for item in self.audit_tree.get_children():
                        self.audit_tree.delete(item)
                    
                    # Add new data
                    for record in data.get('data', []):
                        self.audit_tree.insert('', 'end', values=(
                            record.get('timestamp'),
                            record.get('details')
                        ))
                else:
                    messagebox.showerror("Error", data.get('message', "Failed to get audit log"))
            else:
                messagebox.showerror("Error", f"Server returned status code: {response.status_code}")
        except requests.exceptions.RequestException as e:
            messagebox.showerror("Error", f"Failed to connect to server: {str(e)}")

    def edit_attendance(self):
        selected_item = self.attendance_tree.selection()
        if not selected_item:
            messagebox.showerror("Error", "Please select an attendance record to edit")
            return
        
        item = self.attendance_tree.item(selected_item[0])
        record_id = item['values'][0]
        
        dialog = AttendanceEditDialog(self.root, item['values'])
        self.root.wait_window(dialog)
        
        if dialog.result is None:
            return  # User cancelled
        
        password = self.password_entry.get()
        if not password:
            messagebox.showerror("Error", "Please enter admin password")
            return
        
        try:
            response = requests.post(
                f"{self.server_url}/api/edit_attendance",
                json={
                    "password": password,
                    "record_id": record_id,
                    **dialog.result
                },
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    messagebox.showinfo("Success", data.get('message', "Attendance record updated successfully"))
                    self.refresh_attendance_data()
                else:
                    messagebox.showerror("Error", data.get('message', "Failed to update attendance record"))
            else:
                messagebox.showerror("Error", f"Server returned status code: {response.status_code}")
        except requests.exceptions.RequestException as e:
            messagebox.showerror("Error", f"Failed to connect to server: {str(e)}")

    def close_open_session(self):
        staff_code = simpledialog.askstring("Close Open Session", "Enter staff code:")
        if not staff_code:
            return
        
        clock_out_time = simpledialog.askstring("Close Open Session", "Enter clock out time (YYYY-MM-DD HH:MM:SS):")
        if not clock_out_time:
            return
        
        password = self.password_entry.get()
        if not password:
            messagebox.showerror("Error", "Please enter admin password")
            return
        
        try:
            response = requests.post(
                f"{self.server_url}/api/close_open_session",
                json={
                    "password": password,
                    "staff_code": staff_code,
                    "clock_out_time": clock_out_time
                },
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    messagebox.showinfo("Success", data.get('message', "Open session closed successfully"))
                    self.refresh_attendance_data()
                else:
                    messagebox.showerror("Error", data.get('message', "Failed to close open session"))
            else:
                messagebox.showerror("Error", f"Server returned status code: {response.status_code}")
        except requests.exceptions.RequestException as e:
            messagebox.showerror("Error", f"Failed to connect to server: {str(e)}")

    def export_to_excel(self, selected_only=False):
        password = self.password_entry.get()
        if not password:
            messagebox.showerror("Error", "Please enter admin password")
            return
        
        selected_ids = []
        if selected_only:
            selected_items = self.attendance_tree.selection()
            if not selected_items:
                messagebox.showerror("Error", "Please select records to export")
                return
            
            for item in selected_items:
                selected_ids.append(self.attendance_tree.item(item)['values'][0])
        
        try:
            response = requests.post(
                f"{self.server_url}/api/generate_excel",
                json={
                    "password": password,
                    "start_date": self.start_date_var.get(),
                    "end_date": self.end_date_var.get(),
                    "selected_ids": selected_ids
                },
                timeout=30  # Increased timeout for large data
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    # Decode base64 data
                    excel_data = base64.b64decode(data.get('excel_data'))
                    filename = data.get('filename', 'attendance_report.xlsx')
                    
                    # Save to file
                    file_path = filedialog.asksaveasfilename(
                        defaultextension=".xlsx",
                        filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
                        initialfile=filename
                    )
                    
                    if file_path:
                        with open(file_path, 'wb') as f:
                            f.write(excel_data)
                        messagebox.showinfo("Success", f"Excel file saved to {file_path}")
                else:
                    messagebox.showerror("Error", data.get('message', "Failed to generate Excel file"))
            else:
                messagebox.showerror("Error", f"Server returned status code: {response.status_code}")
        except requests.exceptions.RequestException as e:
            messagebox.showerror("Error", f"Failed to connect to server: {str(e)}")

    def on_staff_selected(self, event):
        selection = self.staff_list_var.get()
        if selection:
            staff_code = selection.split(' - ')[0]
            self.staff_code_entry.delete(0, tk.END)
            self.staff_code_entry.insert(0, staff_code)

    def on_code_typed(self, event):
        code = self.staff_code_entry.get().strip()
        if code:
            # Find matching staff in dropdown
            for value in self.staff_dropdown['values']:
                if value.startswith(code + " - "):
                    self.staff_list_var.set(value)
                    break

    def on_notes_staff_selected(self, event):
        selection = self.notes_staff_list_var.get()
        if selection:
            staff_code = selection.split(' - ')[0]
            self.notes_staff_code_entry.delete(0, tk.END)
            self.notes_staff_code_entry.insert(0, staff_code)

    def on_notes_code_typed(self, event):
        code = self.notes_staff_code_entry.get().strip()
        if code:
            # Find matching staff in dropdown
            for value in self.notes_staff_dropdown['values']:
                if value.startswith(code + " - "):
                    self.notes_staff_list_var.set(value)
                    break

    def generate_detailed_report(self):
        if not self.connected:
            messagebox.showerror("Error", "Not connected to server")
            return
        
        password = self.password_entry.get()
        if not password:
            messagebox.showerror("Error", "Please enter admin password")
            return
        
        staff_code = self.staff_code_entry.get().strip()
        if not staff_code:
            messagebox.showerror("Error", "Please enter a staff code")
            return
        
        try:
            response = requests.post(
                f"{self.server_url}/api/get_attendance",
                json={
                    "password": password,
                    "start_date": self.report_start_date_var.get(),
                    "end_date": self.report_end_date_var.get()
                },
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    # Clear existing data
                    for item in self.detail_report_tree.get_children():
                        self.detail_report_tree.delete(item)
                    
                    # Filter data for selected staff
                    filtered_data = [record for record in data.get('data', []) if record.get('staff_code') == staff_code]
                    
                    # Add new data
                    total_hours = 0
                    total_earnings = 0
                    
                    for record in filtered_data:
                        hours = record.get('hours', 0)
                        earnings = record.get('earnings', 0)
                        total_hours += hours
                        total_earnings += earnings
                        
                        self.detail_report_tree.insert('', 'end', values=(
                            record.get('id'),
                            record.get('clock_in'),
                            record.get('clock_out'),
                            record.get('session_type'),
                            f"{hours:.2f}",
                            f"${earnings:.2f}"
                        ))
                    
                    # Update summary
                    summary_text = f"Total Hours: {total_hours:.2f}\n"
                    summary_text += f"Total Earnings: ${total_earnings:.2f}"
                    self.detail_summary_label.config(text=summary_text)
                else:
                    messagebox.showerror("Error", data.get('message', "Failed to get attendance data"))
            else:
                messagebox.showerror("Error", f"Server returned status code: {response.status_code}")
        except requests.exceptions.RequestException as e:
            messagebox.showerror("Error", f"Failed to connect to server: {str(e)}")

    def export_single_user_report(self):
        staff_code = self.staff_code_entry.get().strip()
        if not staff_code:
            messagebox.showerror("Error", "Please enter a staff code")
            return
        
        password = self.password_entry.get()
        if not password:
            messagebox.showerror("Error", "Please enter admin password")
            return
        
        try:
            response = requests.post(
                f"{self.server_url}/api/generate_excel",
                json={
                    "password": password,
                    "start_date": self.report_start_date_var.get(),
                    "end_date": self.report_end_date_var.get(),
                    "staff_code": staff_code  # This would need to be implemented in the server
                },
                timeout=30
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    # Decode base64 data
                    excel_data = base64.b64decode(data.get('excel_data'))
                    filename = data.get('filename', 'attendance_report.xlsx')
                    
                    # Save to file
                    file_path = filedialog.asksaveasfilename(
                        defaultextension=".xlsx",
                        filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
                        initialfile=f"{staff_code}_{filename}"
                    )
                    
                    if file_path:
                        with open(file_path, 'wb') as f:
                            f.write(excel_data)
                        messagebox.showinfo("Success", f"Excel file saved to {file_path}")
                else:
                    messagebox.showerror("Error", data.get('message', "Failed to generate Excel file"))
            else:
                messagebox.showerror("Error", f"Server returned status code: {response.status_code}")
        except requests.exceptions.RequestException as e:
            messagebox.showerror("Error", f"Failed to connect to server: {str(e)}")

    def export_all_staff_report(self):
        password = self.password_entry.get()
        if not password:
            messagebox.showerror("Error", "Please enter admin password")
            return
        
        try:
            response = requests.post(
                f"{self.server_url}/api/generate_excel",
                json={
                    "password": password,
                    "start_date": self.report_start_date_var.get(),
                    "end_date": self.report_end_date_var.get()
                },
                timeout=30
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    # Decode base64 data
                    excel_data = base64.b64decode(data.get('excel_data'))
                    filename = data.get('filename', 'attendance_report.xlsx')
                    
                    # Save to file
                    file_path = filedialog.asksaveasfilename(
                        defaultextension=".xlsx",
                        filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
                        initialfile=f"all_staff_{filename}"
                    )
                    
                    if file_path:
                        with open(file_path, 'wb') as f:
                            f.write(excel_data)
                        messagebox.showinfo("Success", f"Excel file saved to {file_path}")
                else:
                    messagebox.showerror("Error", data.get('message', "Failed to generate Excel file"))
            else:
                messagebox.showerror("Error", f"Server returned status code: {response.status_code}")
        except requests.exceptions.RequestException as e:
            messagebox.showerror("Error", f"Failed to connect to server: {str(e)}")

    def generate_notes_report(self):
        """Generate notes report with better error handling"""
        if not self.connected:
            messagebox.showerror("Error", "Not connected to server")
            return
        
        password = self.password_entry.get()
        if not password:
            messagebox.showerror("Error", "Please enter admin password")
            return
        
        staff_code = self.notes_staff_code_entry.get().strip()
        if not staff_code:
            messagebox.showerror("Error", "Please enter a staff code")
            return
        
        # Get selected questions
        selected_questions = [q for q, var in self.question_vars.items() if var.get()]
        if not selected_questions:
            messagebox.showerror("Error", "Please select at least one question")
            return
        
        try:
            response = requests.post(
                f"{self.server_url}/api/get_attendance",
                json={
                    "password": password,
                    "start_date": self.notes_start_date_var.get(),
                    "end_date": self.notes_end_date_var.get()
                },
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    # Clear existing data
                    for item in self.notes_tree.get_children():
                        self.notes_tree.delete(item)
                    
                    # Filter data for selected staff
                    filtered_data = [record for record in data.get('data', []) if record.get('staff_code') == staff_code]
                    
                    # Add new data
                    for record in filtered_data:
                        notes = record.get('notes', '')
                        if notes:
                            try:
                                notes_data = json.loads(notes)
                                for question in selected_questions:
                                    if question in notes_data:
                                        self.notes_tree.insert('', 'end', values=(
                                            record.get('id'),
                                            record.get('staff_code'),
                                            record.get('name'),
                                            record.get('clock_in'),
                                            record.get('clock_out'),
                                            question,
                                            notes_data.get(question, '')
                                        ))
                            except json.JSONDecodeError:
                                # Skip if notes are not valid JSON
                                pass
                    
                    # Update summary
                    count = len(self.notes_tree.get_children())
                    self.notes_summary_label.config(text=f"Found {count} notes entries")
                    
                    if count == 0:
                        messagebox.showinfo("Info", "No notes found for the selected criteria")
                else:
                    messagebox.showerror("Error", data.get('message', "Failed to get attendance data"))
            else:
                messagebox.showerror("Error", f"Server returned status code: {response.status_code}")
        except requests.exceptions.RequestException as e:
            messagebox.showerror("Error", f"Failed to connect to server: {str(e)}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate notes report: {str(e)}")

    def export_notes_to_excel(self):
        """Export notes to Excel with better error handling"""
        password = self.password_entry.get()
        if not password:
            messagebox.showerror("Error", "Please enter admin password")
            return
        
        staff_code = self.notes_staff_code_entry.get().strip()
        if not staff_code:
            messagebox.showerror("Error", "Please enter a staff code")
            return
        
        # Get selected questions
        selected_questions = [q for q, var in self.question_vars.items() if var.get()]
        if not selected_questions:
            messagebox.showerror("Error", "Please select at least one question")
            return
        
        try:
            response = requests.post(
                f"{self.server_url}/api/get_attendance",
                json={
                    "password": password,
                    "start_date": self.notes_start_date_var.get(),
                    "end_date": self.notes_end_date_var.get()
                },
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    # Filter data for selected staff
                    filtered_data = [record for record in data.get('data', []) if record.get('staff_code') == staff_code]
                    
                    # Create DataFrame
                    notes_data = []
                    for record in filtered_data:
                        notes = record.get('notes', '')
                        if notes:
                            try:
                                notes_json = json.loads(notes)
                                for question in selected_questions:
                                    if question in notes_json:
                                        notes_data.append({
                                            'ID': record.get('id'),
                                            'Staff Code': record.get('staff_code'),
                                            'Name': record.get('name'),
                                            'Clock In': record.get('clock_in'),
                                            'Clock Out': record.get('clock_out'),
                                            'Question': question,
                                            'Answer': notes_json.get(question, '')
                                        })
                            except json.JSONDecodeError:
                                # Skip if notes are not valid JSON
                                pass
                    
                    if not notes_data:
                        messagebox.showerror("Error", "No notes data found for the selected criteria")
                        return
                    
                    # Create DataFrame
                    df = pd.DataFrame(notes_data)
                    
                    # Create Excel file in memory
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                        df.to_excel(writer, sheet_name='Notes', index=False)
                        
                        # Get the workbook and worksheet objects
                        workbook = writer.book
                        worksheet = writer.sheets['Notes']
                        
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
                    
                    output.seek(0)
                    
                    # Convert to base64 for sending
                    excel_data = base64.b64encode(output.read()).decode('utf-8')
                    
                    # Save to file
                    file_path = filedialog.asksaveasfilename(
                        defaultextension=".xlsx",
                        filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
                        initialfile=f"notes_{staff_code}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                    )
                    
                    if file_path:
                        with open(file_path, 'wb') as f:
                            f.write(base64.b64decode(excel_data))
                        messagebox.showinfo("Success", f"Excel file saved to {file_path}")
                else:
                    messagebox.showerror("Error", data.get('message', "Failed to get attendance data"))
            else:
                messagebox.showerror("Error", f"Server returned status code: {response.status_code}")
        except requests.exceptions.RequestException as e:
            messagebox.showerror("Error", f"Failed to connect to server: {str(e)}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export notes: {str(e)}")


class StaffDialog(tk.Toplevel):
    def __init__(self, parent, staff_code=None):
        super().__init__(parent)
        self.title("Add Staff" if not staff_code else "Update Staff")
        self.geometry("400x300")
        self.resizable(False, False)
        
        self.result = {}
        
        # Create frames
        code_frame = ttk.Frame(self)
        code_frame.pack(fill=tk.X, padx=10, pady=5)
        
        name_frame = ttk.Frame(self)
        name_frame.pack(fill=tk.X, padx=10, pady=5)
        
        rate_frame = ttk.Frame(self)
        rate_frame.pack(fill=tk.X, padx=10, pady=5)
        
        shift_frame = ttk.Frame(self)
        shift_frame.pack(fill=tk.X, padx=10, pady=5)
        
        button_frame = ttk.Frame(self)
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Staff code
        ttk.Label(code_frame, text="Staff Code:").pack(side=tk.LEFT, padx=5)
        self.code_var = tk.StringVar()
        self.code_entry = ttk.Entry(code_frame, textvariable=self.code_var, width=20)
        self.code_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # Name
        ttk.Label(name_frame, text="Name:").pack(side=tk.LEFT, padx=5)
        self.name_var = tk.StringVar()
        self.name_entry = ttk.Entry(name_frame, textvariable=self.name_var, width=20)
        self.name_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # Hourly rate
        ttk.Label(rate_frame, text="Hourly Rate:").pack(side=tk.LEFT, padx=5)
        self.rate_var = tk.StringVar()
        self.rate_entry = ttk.Entry(rate_frame, textvariable=self.rate_var, width=20)
        self.rate_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # Shift
        ttk.Label(shift_frame, text="Shift:").pack(side=tk.LEFT, padx=5)
        self.shift_var = tk.StringVar()
        self.shift_dropdown = ttk.Combobox(shift_frame, textvariable=self.shift_var, width=18)
        self.shift_dropdown.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # Buttons
        ttk.Button(button_frame, text="Submit", command=self.submit).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.cancel).pack(side=tk.RIGHT, padx=5)
        
        # Load shifts
        self.load_shifts()
        
        # If updating staff, load existing data
        if staff_code:
            self.load_staff_data(staff_code)
            self.code_entry.config(state='readonly')

    def load_shifts(self):
        try:
            # Get parent's server_url and password
            parent = self.master
            while not hasattr(parent, 'server_url'):
                parent = parent.master
            
            response = requests.post(
                f"{parent.server_url}/api/get_shifts",
                json={"password": parent.password_entry.get()},
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    shifts = data.get('data', [])
                    self.shift_dropdown['values'] = [shift.get('name') for shift in shifts]
        except:
            pass

    def load_staff_data(self, staff_code):
        try:
            # Get parent's server_url and password
            parent = self.master
            while not hasattr(parent, 'server_url'):
                parent = parent.master
            
            response = requests.post(
                f"{parent.server_url}/api/get_staff",
                json={"password": parent.password_entry.get()},
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    for staff in data.get('data', []):
                        if staff.get('staff_code') == staff_code:
                            self.code_var.set(staff.get('staff_code'))
                            self.name_var.set(staff.get('name'))
                            self.rate_var.set(staff.get('hourly_rate'))
                            self.shift_var.set(staff.get('shift_name'))
                            break
        except:
            pass

    def submit(self):
        self.result = {
            'staff_code': self.code_var.get(),
            'name': self.name_var.get(),
            'hourly_rate': float(self.rate_var.get() or 0),
            'shift_name': self.shift_var.get()
        }
        self.destroy()

    def cancel(self):
        self.result = None
        self.destroy()

class CrmLeadDialog(tk.Toplevel):
    def __init__(self, parent, title, server_url, admin_pw, lead_data=None):
        super().__init__(parent)
        self.title(title)
        self.geometry("520x460")
        self.resizable(False, False)
        self.result = None
        self.server_url = server_url
        self.admin_pw = admin_pw

        # Fetch dropdown data
        self.targets = self._get_targets()
        self.staff   = self._get_staff()

        # UI
        pad = dict(padx=8, pady=4)

        # Name
        f = ttk.Frame(self); f.pack(fill=tk.X, **pad)
        ttk.Label(f, text="Name:").pack(side=tk.LEFT)
        self.e_name = ttk.Entry(f, width=40)
        self.e_name.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        # Phone
        f = ttk.Frame(self); f.pack(fill=tk.X, **pad)
        ttk.Label(f, text="Phone:").pack(side=tk.LEFT)
        self.e_phone = ttk.Entry(f, width=40)
        self.e_phone.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        # Status
        f = ttk.Frame(self); f.pack(fill=tk.X, **pad)
        ttk.Label(f, text="Status:").pack(side=tk.LEFT)
        self.cb_status = ttk.Combobox(f, values=["New","Contacted","Qualified","Lost","Won"],
                                      state="readonly", width=37)
        self.cb_status.pack(side=tk.LEFT, padx=5)
        self.cb_status.set("New")

        # Target
        f = ttk.Frame(self); f.pack(fill=tk.X, **pad)
        ttk.Label(f, text="Target:").pack(side=tk.LEFT)
        self.cb_target = ttk.Combobox(f, values=self.targets,
                                      state="readonly", width=37)
        self.cb_target.pack(side=tk.LEFT, padx=5)

        # Assigned To
        f = ttk.Frame(self); f.pack(fill=tk.X, **pad)
        ttk.Label(f, text="Assigned:").pack(side=tk.LEFT)
        self.cb_assign = ttk.Combobox(f, values=self.staff,
                                      state="readonly", width=37)
        self.cb_assign.pack(side=tk.LEFT, padx=5)

        # Notes
        f = ttk.Frame(self); f.pack(fill=tk.BOTH, expand=True, **pad)
        ttk.Label(f, text="Notes:").pack(anchor=tk.W)
        self.t_notes = tk.Text(f, height=8, wrap=tk.WORD)
        self.t_notes.pack(fill=tk.BOTH, expand=True)

        # Buttons
        f = ttk.Frame(self); f.pack(fill=tk.X, **pad)
        ttk.Button(f, text="Save", command=self._save).pack(side=tk.RIGHT, padx=5)
        ttk.Button(f, text="Cancel", command=self.destroy).pack(side=tk.RIGHT)

        # Fill if editing
        if lead_data:
            self.lead_id = lead_data.get('id')
            self.e_name.insert(0, lead_data.get('name',''))
            self.e_phone.insert(0, lead_data.get('phone',''))
            self.cb_status.set(lead_data.get('status','New'))
            self.cb_target.set(lead_data.get('target',''))
            self.cb_assign.set(lead_data.get('assigned_to',''))
            self.t_notes.insert('1.0', lead_data.get('notes',''))
        else:
            self.lead_id = None

    def _get_targets(self):
        try:
            r = requests.post(f"{self.server_url}/api/crm_get_targets",
                              json={"password": self.admin_pw}, timeout=5)
            return r.json().get('targets', [])
        except: return []

    def _get_staff(self):
        try:
            r = requests.post(f"{self.server_url}/api/get_staff",
                              json={"password": self.admin_pw}, timeout=5)
            data = r.json().get('data', [])
            return [f"{s['staff_code']} - {s['name']}" for s in data]
        except: return []

    def _save(self):
        payload = {
            "password": self.admin_pw,
            "name": self.e_name.get().strip(),
            "phone": self.e_phone.get().strip(),
            "status": self.cb_status.get(),
            "target": self.cb_target.get(),
            "assigned_to": self.cb_assign.get().split(' - ')[0] if self.cb_assign.get() else "",
            "notes": self.t_notes.get('1.0', tk.END).strip()
        }
        if self.lead_id:
            payload["lead_id"] = self.lead_id
            endpoint = "/api/crm_update_lead"
        else:
            endpoint = "/api/crm_add_lead"

        try:
            r = requests.post(f"{self.server_url}{endpoint}",
                              json=payload, timeout=8)
            resp = r.json()
            if resp.get('success'):
                self.result = True
                self.destroy()
            else:
                messagebox.showerror("Error", resp.get('message','Save failed'))
        except Exception as e:
            messagebox.showerror("Error", f"Save failed: {e}")

class ShiftDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Add Shift")
        self.geometry("400x200")
        self.resizable(False, False)
        
        self.result = {}
        
        # Create frames
        name_frame = ttk.Frame(self)
        name_frame.pack(fill=tk.X, padx=10, pady=5)
        
        start_frame = ttk.Frame(self)
        start_frame.pack(fill=tk.X, padx=10, pady=5)
        
        end_frame = ttk.Frame(self)
        end_frame.pack(fill=tk.X, padx=10, pady=5)
        
        button_frame = ttk.Frame(self)
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Name
        ttk.Label(name_frame, text="Shift Name:").pack(side=tk.LEFT, padx=5)
        self.name_var = tk.StringVar()
        self.name_entry = ttk.Entry(name_frame, textvariable=self.name_var, width=20)
        self.name_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # Start time
        ttk.Label(start_frame, text="Start Time:").pack(side=tk.LEFT, padx=5)
        self.start_var = tk.StringVar()
        self.start_entry = ttk.Entry(start_frame, textvariable=self.start_var, width=20)
        self.start_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # End time
        ttk.Label(end_frame, text="End Time:").pack(side=tk.LEFT, padx=5)
        self.end_var = tk.StringVar()
        self.end_entry = ttk.Entry(end_frame, textvariable=self.end_var, width=20)
        self.end_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # Buttons
        ttk.Button(button_frame, text="Submit", command=self.submit).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.cancel).pack(side=tk.RIGHT, padx=5)
        
        # Set default values
        self.start_var.set("09:00")
        self.end_var.set("17:00")

    def submit(self):
        self.result = {
            'name': self.name_var.get(),
            'start_time': self.start_var.get(),
            'end_time': self.end_var.get()
        }
        self.destroy()

    def cancel(self):
        self.result = None
        self.destroy()


class HolidayDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Add Holiday")
        self.geometry("400x250")
        self.resizable(False, False)
        
        self.result = {}
        
        # Create frames
        date_frame = ttk.Frame(self)
        date_frame.pack(fill=tk.X, padx=10, pady=5)
        
        name_frame = ttk.Frame(self)
        name_frame.pack(fill=tk.X, padx=10, pady=5)
        
        paid_frame = ttk.Frame(self)
        paid_frame.pack(fill=tk.X, padx=10, pady=5)
        
        button_frame = ttk.Frame(self)
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Date
        ttk.Label(date_frame, text="Date:").pack(side=tk.LEFT, padx=5)
        self.date_var = tk.StringVar()
        self.date_entry = ttk.Entry(date_frame, textvariable=self.date_var, width=20)
        self.date_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # Name
        ttk.Label(name_frame, text="Holiday Name:").pack(side=tk.LEFT, padx=5)
        self.name_var = tk.StringVar()
        self.name_entry = ttk.Entry(name_frame, textvariable=self.name_var, width=20)
        self.name_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # Paid
        self.paid_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(paid_frame, text="Paid Holiday", variable=self.paid_var).pack(side=tk.LEFT, padx=5)
        
        # Buttons
        ttk.Button(button_frame, text="Submit", command=self.submit).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.cancel).pack(side=tk.RIGHT, padx=5)
        
        # Set default values
        today = datetime.now().strftime('%Y-%m-%d')
        self.date_var.set(today)

    def submit(self):
        self.result = {
            'date': self.date_var.get(),
            'name': self.name_var.get(),
            'paid': self.paid_var.get()
        }
        self.destroy()

    def cancel(self):
        self.result = None
        self.destroy()


class AttendanceEditDialog(tk.Toplevel):
    def __init__(self, parent, record_data):
        super().__init__(parent)
        self.title("Edit Attendance Record")
        self.geometry("400x250")
        self.resizable(False, False)
        
        self.result = {}
        
        # Create frames
        clock_in_frame = ttk.Frame(self)
        clock_in_frame.pack(fill=tk.X, padx=10, pady=5)
        
        clock_out_frame = ttk.Frame(self)
        clock_out_frame.pack(fill=tk.X, padx=10, pady=5)
        
        button_frame = ttk.Frame(self)
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Clock in
        ttk.Label(clock_in_frame, text="Clock In:").pack(side=tk.LEFT, padx=5)
        self.clock_in_var = tk.StringVar()
        self.clock_in_entry = ttk.Entry(clock_in_frame, textvariable=self.clock_in_var, width=20)
        self.clock_in_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # Clock out
        ttk.Label(clock_out_frame, text="Clock Out:").pack(side=tk.LEFT, padx=5)
        self.clock_out_var = tk.StringVar()
        self.clock_out_entry = ttk.Entry(clock_out_frame, textvariable=self.clock_out_var, width=20)
        self.clock_out_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # Buttons
        ttk.Button(button_frame, text="Submit", command=self.submit).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.cancel).pack(side=tk.RIGHT, padx=5)
        
        # Set default values
        self.clock_in_var.set(record_data[3])  # Clock In is at index 3
        self.clock_out_var.set(record_data[4])  # Clock Out is at index 4

    def submit(self):
        self.result = {
            'clock_in': self.clock_in_var.get(),
            'clock_out': self.clock_out_var.get()
        }
        self.destroy()

    def cancel(self):
        self.result = None
        self.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = AttendanceClient(root)
    root.mainloop()
