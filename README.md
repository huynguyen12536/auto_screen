# Browser Automation Tool

Python desktop-automation foundation for Windows. This setup phase only
boots configuration, logging, and runtime folders. It does **not** open a
browser, log in, or capture screenshots.

## Requirements

- Windows
- Python 3.10+ (3.11 or 3.12 recommended)
- Google Chrome (used in a later phase)
- VS Code / Cursor

## Python version

```powershell
python --version
```

## Create virtual environment

Open this folder in a terminal:

```powershell
cd auto_screeen_shoot

python -m venv .venv

.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.venv\Scripts\Activate.ps1
```

## Install dependencies

Always install **inside the activated venv**.

```powershell
python -m pip install --upgrade pip

pip install -r requirements.txt
```

## Configure .env

```powershell
Copy-Item .env.example .env
```

Fill in values later. Do not commit `.env`. Do not put real credentials in
git. This setup phase does not use login values.

## Run project

```powershell
python main.py
```

Expected output:

```text
Browser Automation Tool
Environment: development
Configuration loaded successfully
Runtime directories ready
OpenCV configured: 5.0.0
Opening: https://www.facebook.com/
Screenshot saved: runtime\screenshots\facebook_login_YYYYMMDD_HHMMSS.png
```

The script opens Chrome in guest mode so Facebook shows the login page,
then captures that browser window into `runtime/screenshots/`.

## Run tests

```powershell
python -m pytest
```

## Debug in Cursor / VS Code

1. Open the `auto_screeen_shoot` folder as the workspace.
2. Select the `.venv` interpreter: `.venv\Scripts\python.exe`
3. Run **Debug Python main.py** from the Run and Debug view.

Tasks available in Terminal > Run Task:

- Create venv
- Install requirements
- Run app
- Run tests
- Format code
- Lint code

## Folder structure

```text
auto_screeen_shoot/
├── main.py
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
├── config/
│   ├── config.yaml
│   └── feature/
│       ├── capture.yaml
│       └── opencv.yaml
├── automation/
├── feature/
│   ├── capture/
│   └── opencv/
├── vision/
├── services/
├── utils/
├── runtime/
├── tests/
└── .vscode/
```

Generated files (screenshots, logs, temp) stay under `runtime/`.
