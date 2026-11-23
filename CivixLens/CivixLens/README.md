# CivixLens – Smart Civic Issue Reporting System

CivixLens is a Streamlit application for citizens to submit civic issue reports with photographic evidence and for municipal authorities to review, track, resolve, and award points.

## Features
- Citizen registration and login
- Civic complaint submission with photo evidence
- Duplicate image detection using SHA-256
- Optional Gemini Vision image classification
- Citizen dashboard with report status and reward points
- Municipal admin dashboard with filters and status controls
- CSV export of complaint records
- SQLite database created automatically

## Requirements
- Python 3.10+
- pip

## Run locally
```bash
python -m venv .venv
source .venv/bin/activate        # macOS/Linux
# .venv\Scripts\activate       # Windows

pip install -r requirements.txt
streamlit run app.py
```

Open the local URL printed in the terminal (usually http://localhost:8501).

## Configure the admin account
Set an admin password before starting the app. The default admin username is `admin`.

macOS/Linux:
```bash
export CIVIXLENS_ADMIN_USER=admin
export CIVIXLENS_ADMIN_PASSWORD='choose-a-strong-password'
streamlit run app.py
```

Windows PowerShell:
```powershell
$env:CIVIXLENS_ADMIN_USER="admin"
$env:CIVIXLENS_ADMIN_PASSWORD="choose-a-strong-password"
streamlit run app.py
```

The admin account is created on first app startup when the environment variables are present. Keep the password secret.

## Optional Gemini Vision integration
Set a Gemini API key to enable image classification. Without it, reports are accepted for manual authority review.

macOS/Linux:
```bash
export GEMINI_API_KEY='your-api-key'
```

Windows PowerShell:
```powershell
$env:GEMINI_API_KEY="your-api-key"
```

Never commit API keys or passwords to GitHub. For Streamlit Community Cloud, add them under **App → Settings → Secrets** and adapt environment-variable access if required.

## Database
The SQLite database is created automatically at `database/civixlens.db` when the app runs. The database file is intentionally excluded from GitHub; each deployment will create its own database.

## GitHub upload
1. Extract `CivixLens.zip`.
2. Create a GitHub repository named `CivixLens`.
3. Upload `app.py`, `requirements.txt`, `README.md`, `.gitignore`, and the `database` folder.
4. For Streamlit Community Cloud, choose `app.py` as the main file.

## Important notes
- This is a starter implementation. Review authentication, data protection, backups, and admin access before using it with real public submissions.
- The Gemini integration is optional and should be tested with your own API key and model availability.
