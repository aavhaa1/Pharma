# PharmaCare - Pharmacy Management System

A Django web application for pharmacy inventory, point-of-sale (POS), purchasing, supplier management, and reporting.

---

## 🚀 Quick Setup Instructions for Teammates / Partners

When you pull this project for the first time or pull new updates from GitHub, follow these simple steps to run the app:

### 1. Clone or Pull the Latest Code
```bash
git pull origin main
```

### 2. Set Up Virtual Environment & Install Dependencies
```bash
# Create virtual environment (if not already created)
python -m venv venv

# Activate virtual environment
# Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# Windows (CMD):
.\venv\Scripts\activate.bat
# macOS/Linux:
source venv/bin/activate

# Install required packages
pip install -r requirements.txt
```

### 3. Run Database Migrations
```bash
python manage.py migrate
```

### 4. Create an Admin Account (Optional)
If you need a superuser account to log into the application:
```bash
python manage.py createsuperuser
```

### 5. Run the Server
```bash
python manage.py runserver
```

Open your browser and visit: `http://127.0.0.1:8000/`

---

## 🛠️ Requirements
- Python 3.10+
- Dependencies listed in `requirements.txt` (Django, openpyxl, reportlab, Pillow, etc.)
