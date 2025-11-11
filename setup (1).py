import subprocess
import sys
import os

def install_requirements():
    print("Installing required packages...")
    
    packages = [
        "flask",
        "flask-cors",
        "pandas",
        "openpyxl",
        "xlsxwriter",
        "requests",
        "tkcalendar",
        "pystray",
        "pillow",
        "matplotlib",
        "schedule",
        "python-dateutil",
        "arabic-reshaper",
        "python-bidi"
    ]
    
    for package in packages:
        print(f"Installing {package}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
    
    print("All packages installed successfully!")

def create_shortcuts():
    print("Creating desktop shortcuts...")
    
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    
    # Create server shortcut
    server_script = os.path.join(os.getcwd(), "server_gui.py")
    server_shortcut = os.path.join(desktop, "Attendance Server.lnk")
    
    # Create client shortcut
    client_script = os.path.join(os.getcwd(), "client.py")
    client_shortcut = os.path.join(desktop, "Attendance Client.lnk")
    
    # Note: Creating actual shortcuts requires additional libraries
    # For simplicity, we'll just create batch files
    
    # Server batch file
    with open(os.path.join(desktop, "Start Attendance Server.bat"), "w") as f:
        f.write(f"@echo off\n")
        f.write(f"cd /d {os.getcwd()}\n")
        f.write(f"python server_gui.py\n")
        f.write(f"pause\n")
    
    # Client batch file
    with open(os.path.join(desktop, "Start Attendance Client.bat"), "w") as f:
        f.write(f"@echo off\n")
        f.write(f"cd /d {os.getcwd()}\n")
        f.write(f"python client.py\n")
        f.write(f"pause\n")
    
    print("Desktop shortcuts created successfully!")

def main():
    print("Setting up Attendance System...")
    print("This will install the required packages and create desktop shortcuts.")
    
    response = input("Do you want to continue? (y/n): ")
    if response.lower() != 'y':
        print("Setup cancelled.")
        return
    
    try:
        install_requirements()
        create_shortcuts()
        
        print("\nSetup completed successfully!")
        print("\nTo use the system:")
        print("1. Run 'Start Attendance Server' from your desktop to start the server")
        print("2. Run 'Start Attendance Client' on each client computer")
        print("3. Clients will automatically connect to the server when started")
        print("\nDefault admin password: admin123")
        print("\nNote: Make sure all computers are on the same network.")
        
    except Exception as e:
        print(f"Setup failed: {str(e)}")
        input("Press Enter to exit...")

if __name__ == "__main__":
    main()