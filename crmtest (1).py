import tkinter as tk
from tkinter import ttk, messagebox
import xmlrpc.client
import json
import requests

class OdooConnector:
    """Handles the connection and API calls to the Odoo server."""
    def __init__(self):
        self.url = None
        self.db = None
        self.username = None
        self.password = None
        self.uid = None
        self.models = None

    def set_credentials(self, url, db, username, password):
        self.url = url
        self.db = db
        self.username = username
        self.password = password

    def connect(self):
        if not all([self.url, self.db, self.username, self.password]):
            raise ValueError("All credentials must be set.")
        
        common = xmlrpc.client.ServerProxy(f'{self.url}/xmlrpc/2/common')
        self.uid = common.authenticate(self.db, self.username, self.password, {})
        if not self.uid:
            raise Exception("Authentication failed.")
        self.models = xmlrpc.client.ServerProxy(f'{self.url}/xmlrpc/2/object')
        return True

    def get_stages(self):
        return self.models.execute_kw(self.db, self.uid, self.password,
            'crm.stage', 'search_read', [[]], {'fields': ['id', 'name', 'sequence']})

    def get_leads(self):
        return self.models.execute_kw(self.db, self.uid, self.password,
            'crm.lead', 'search_read', [[]],
            {'fields': ['id', 'name', 'partner_name', 'email_from', 'phone', 'stage_id']})

    def create_lead(self, lead_data):
        return self.models.execute_kw(self.db, self.uid, self.password, 'crm.lead', 'create', [lead_data])

class CrmFrame(ttk.Frame):
    """Embeddable CRM frame inside Attendance Client."""
    def __init__(self, parent, server_url=None):
        super().__init__(parent)
        self.connector = OdooConnector()
        self.server_url = server_url
        self.create_login_ui()

    def create_login_ui(self):
        for w in self.winfo_children(): w.destroy()
        frame = ttk.Frame(self, padding="20")
        frame.pack(expand=True, fill="both")

        ttk.Label(frame, text="Odoo CRM Login", font=("Helvetica", 16, "bold")).grid(row=0, column=0, columnspan=2, pady=10)
        ttk.Label(frame, text="URL:").grid(row=1, column=0, sticky="w"); self.url = ttk.Entry(frame, width=40); self.url.grid(row=1, column=1)
        ttk.Label(frame, text="Database:").grid(row=2, column=0, sticky="w"); self.db = ttk.Entry(frame, width=40); self.db.grid(row=2, column=1)
        ttk.Label(frame, text="Username:").grid(row=3, column=0, sticky="w"); self.user = ttk.Entry(frame, width=40); self.user.grid(row=3, column=1)
        ttk.Label(frame, text="Password:").grid(row=4, column=0, sticky="w"); self.passw = ttk.Entry(frame, width=40, show="*"); self.passw.grid(row=4, column=1)
        ttk.Button(frame, text="Login", command=self.login).grid(row=5, column=0, columnspan=2, pady=15)

        # Try auto-load saved credentials from server
        if self.server_url:
            try:
                r = requests.get(f"{self.server_url}/api/get_crm_credentials", timeout=5)
                data = r.json()
                if data.get("success"):
                    creds = data.get("credentials")
                    self.url.insert(0, creds["url"])
                    self.db.insert(0, creds["db"])
                    self.user.insert(0, creds["username"])
                    self.passw.insert(0, creds["password"])
                    self.login()  # auto login
            except:
                pass

    def login(self):
        url, db, user, pw = self.url.get(), self.db.get(), self.user.get(), self.passw.get()
        try:
            self.connector.set_credentials(url, db, user, pw)
            self.connector.connect()
            messagebox.showinfo("Connected", "Connected to Odoo CRM.")
            if self.server_url:
                requests.post(f"{self.server_url}/api/save_crm_credentials",
                              json={"url": url, "db": db, "username": user, "password": pw})
            self.create_main_ui()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def create_main_ui(self):
        for w in self.winfo_children(): w.destroy()
        notebook = ttk.Notebook(self); notebook.pack(fill="both", expand=True)

        leads_tab = ttk.Frame(notebook); stages_tab = ttk.Frame(notebook)
        notebook.add(leads_tab, text="Leads / Orders"); notebook.add(stages_tab, text="Pipelines")

        self.create_leads_tab(leads_tab)
        self.create_stages_tab(stages_tab)

    def create_leads_tab(self, frame):
        top = ttk.LabelFrame(frame, text="Create New Lead", padding=10)
        top.pack(fill="x", padx=10, pady=10)
        self.name = ttk.Entry(top, width=50); ttk.Label(top, text="اسم الدواء:").grid(row=0, column=0); self.name.grid(row=0, column=1)
        self.email = ttk.Entry(top, width=50); ttk.Label(top, text="اسم العميل:").grid(row=1, column=0); self.email.grid(row=1, column=1)
        self.phone = ttk.Entry(top, width=50); ttk.Label(top, text="رقم الموبايل:").grid(row=2, column=0); self.phone.grid(row=2, column=1)
        ttk.Button(top, text="Create Lead", command=self.create_lead).grid(row=3, column=1, sticky="e", pady=5)

        self.tree = ttk.Treeview(frame, columns=("id", "name", "email", "phone", "stage"), show="headings")
        for c in ("id", "name", "email", "phone", "stage"): self.tree.heading(c, text=c.title())
        self.tree.pack(fill="both", expand=True, padx=10, pady=10)
        ttk.Button(frame, text="Refresh", command=self.load_leads).pack(pady=5)
        self.load_leads()

    def create_stages_tab(self, frame):
        self.stage_tree = ttk.Treeview(frame, columns=("id", "name", "sequence"), show="headings")
        for c in ("id", "name", "sequence"): self.stage_tree.heading(c, text=c.title())
        self.stage_tree.pack(fill="both", expand=True, padx=10, pady=10)
        ttk.Button(frame, text="Refresh", command=self.load_stages).pack(pady=5)
        self.load_stages()

    def create_lead(self):
        try:
            lead_id = self.connector.create_lead({
                'name': self.name.get(),
                'email_from': self.email.get(),
                'phone': self.phone.get()
            })
            messagebox.showinfo("Success", f"Lead created (ID: {lead_id})")
            self.load_leads()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def load_leads(self):
        for i in self.tree.get_children(): self.tree.delete(i)
        try:
            for lead in self.connector.get_leads():
                stage = lead['stage_id'][1] if lead['stage_id'] else "N/A"
                self.tree.insert("", "end", values=(lead['id'], lead['name'], lead['email_from'], lead['phone'], stage))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def load_stages(self):
        for i in self.stage_tree.get_children(): self.stage_tree.delete(i)
        try:
            for stage in self.connector.get_stages():
                self.stage_tree.insert("", "end", values=(stage['id'], stage['name'], stage['sequence']))
        except Exception as e:
            messagebox.showerror("Error", str(e))
