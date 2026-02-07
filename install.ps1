# =============================================================================
# PiServer Attendance System - Windows Installer
# =============================================================================
# Run as Administrator: powershell -ExecutionPolicy Bypass -File install.ps1
# =============================================================================

# Require Administrator
#Requires -RunAsAdministrator

Write-Host "============================================" -ForegroundColor Blue
Write-Host "  PiServer Attendance System - Installer" -ForegroundColor Blue
Write-Host "============================================" -ForegroundColor Blue
Write-Host ""

# Configuration
$InstallDir = "C:\PiServer"
$DataDir = "C:\ProgramData\PiServer"
$ServiceName = "PiServerAttendance"

# =============================================================================
# Functions
# =============================================================================

function Write-Step {
    param($Message)
    Write-Host "[*] $Message" -ForegroundColor Green
}

function Write-Info {
    param($Message)
    Write-Host "    $Message" -ForegroundColor Cyan
}

function Write-Error {
    param($Message)
    Write-Host "[!] $Message" -ForegroundColor Red
}

function Test-Command {
    param($Command)
    try {
        if (Get-Command $Command -ErrorAction Stop) {
            return $true
        }
    }
    catch {
        return $false
    }
    return $false
}

# =============================================================================
# Check Requirements
# =============================================================================

Write-Step "Checking requirements..."

# Check Python
if (-not (Test-Command "python")) {
    Write-Error "Python not found!"
    Write-Info "Please install Python 3.11+ from https://www.python.org/downloads/"
    Write-Info "Make sure to check 'Add Python to PATH' during installation"
    exit 1
}

$pythonVersion = python --version
Write-Info "Found $pythonVersion"

# Check Git
if (-not (Test-Command "git")) {
    Write-Error "Git not found!"
    Write-Info "Please install Git from https://git-scm.com/download/win"
    exit 1
}

Write-Info "Found Git $(git --version)"

# =============================================================================
# Create Directories
# =============================================================================

Write-Step "Creating directories..."

if (-not (Test-Path $InstallDir)) {
    New-Item -ItemType Directory -Path $InstallDir | Out-Null
    Write-Info "Created $InstallDir"
}

if (-not (Test-Path $DataDir)) {
    New-Item -ItemType Directory -Path $DataDir | Out-Null
    Write-Info "Created $DataDir"
}

if (-not (Test-Path "$DataDir\faces")) {
    New-Item -ItemType Directory -Path "$DataDir\faces" | Out-Null
    Write-Info "Created $DataDir\faces"
}

# =============================================================================
# Clone Repository
# =============================================================================

Write-Step "Cloning repository..."

if (Test-Path "$InstallDir\.git") {
    Write-Info "Repository exists, pulling updates..."
    Set-Location $InstallDir
    git pull
} else {
    git clone https://github.com/stujoubert/PiServer.git $InstallDir
}

Set-Location $InstallDir

# =============================================================================
# Setup Virtual Environment
# =============================================================================

Write-Step "Setting up Python virtual environment..."

if (-not (Test-Path "venv")) {
    python -m venv venv
    Write-Info "Virtual environment created"
}

# Activate venv and install packages
& ".\venv\Scripts\Activate.ps1"
python -m pip install --upgrade pip
pip install -r requirements.txt

Write-Info "Python packages installed"

# =============================================================================
# Create Configuration
# =============================================================================

Write-Step "Creating configuration..."

# Generate secret key
$SecretKey = -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 32 | ForEach-Object {[char]$_})

# Prompt for port
$Port = Read-Host "Enter port number (default: 5000)"
if ([string]::IsNullOrWhiteSpace($Port)) {
    $Port = "5000"
}

# Create env file
$EnvContent = @"
# PiServer Attendance Configuration
# Generated on $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")

ATT_ENV=prod
ATT_DB=$DataDir\attendance.db
ATT_PORT=$Port
SECRET_KEY=$SecretKey
"@

$EnvContent | Out-File -FilePath "$DataDir\attendance.env" -Encoding UTF8
Write-Info "Configuration created at $DataDir\attendance.env"

# =============================================================================
# Create Windows Service
# =============================================================================

Write-Step "Creating Windows Service..."

# Create service wrapper script
$ServiceScript = @"
import os
import sys

# Load environment
with open(r'$DataDir\attendance.env', 'r') as f:
    for line in f:
        if line.strip() and not line.startswith('#'):
            key, value = line.strip().split('=', 1)
            os.environ[key] = value

# Change to install directory
os.chdir(r'$InstallDir')
sys.path.insert(0, r'$InstallDir')

# Import and run
from server import app
app.run(host='0.0.0.0', port=int(os.environ.get('ATT_PORT', 5000)))
"@

$ServiceScript | Out-File -FilePath "$InstallDir\service.py" -Encoding UTF8

# Install NSSM (Non-Sucking Service Manager)
$NssmUrl = "https://nssm.cc/release/nssm-2.24.zip"
$NssmZip = "$env:TEMP\nssm.zip"
$NssmDir = "$env:TEMP\nssm"

Write-Info "Downloading NSSM..."
Invoke-WebRequest -Uri $NssmUrl -OutFile $NssmZip
Expand-Archive -Path $NssmZip -DestinationPath $NssmDir -Force

# Use 64-bit NSSM
$NssmExe = "$NssmDir\nssm-2.24\win64\nssm.exe"

# Remove existing service if present
& $NssmExe stop $ServiceName 2>&1 | Out-Null
& $NssmExe remove $ServiceName confirm 2>&1 | Out-Null

# Install service
& $NssmExe install $ServiceName "$InstallDir\venv\Scripts\python.exe" "$InstallDir\service.py"
& $NssmExe set $ServiceName AppDirectory $InstallDir
& $NssmExe set $ServiceName DisplayName "PiServer Attendance System"
& $NssmExe set $ServiceName Description "Time and attendance management system"
& $NssmExe set $ServiceName Start SERVICE_AUTO_START

Write-Info "Service installed"

# =============================================================================
# Create Admin Account
# =============================================================================

Write-Step "Creating admin account..."

$AdminUser = Read-Host "Enter admin username (default: admin)"
if ([string]::IsNullOrWhiteSpace($AdminUser)) {
    $AdminUser = "admin"
}

$AdminPass = Read-Host "Enter admin password" -AsSecureString
$AdminPassText = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
    [Runtime.InteropServices.Marshal]::SecureStringToBSTR($AdminPass)
)

# Create admin account
$CreateAdminScript = @"
from werkzeug.security import generate_password_hash
import sqlite3
import os

db_path = r'$DataDir\attendance.db'
conn = sqlite3.connect(db_path)
cur = conn.cursor()

# Create accounts table
cur.execute('''
    CREATE TABLE IF NOT EXISTS accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('admin','manager','viewer')),
        active INTEGER NOT NULL DEFAULT 1
    )
''')

# Insert admin
password_hash = generate_password_hash('$AdminPassText')
try:
    cur.execute(
        'INSERT INTO accounts (username, password_hash, role) VALUES (?, ?, ?)',
        ('$AdminUser', password_hash, 'admin')
    )
    conn.commit()
    print('Admin account created')
except Exception as e:
    print(f'Error: {e}')
finally:
    conn.close()
"@

$CreateAdminScript | python

# =============================================================================
# Start Service
# =============================================================================

Write-Step "Starting service..."

Start-Service $ServiceName
Start-Sleep -Seconds 3

$ServiceStatus = Get-Service $ServiceName
if ($ServiceStatus.Status -eq "Running") {
    Write-Info "Service started successfully"
} else {
    Write-Error "Service failed to start. Check Windows Event Viewer for details."
}

# =============================================================================
# Firewall Rule
# =============================================================================

Write-Step "Configuring firewall..."

$FirewallRule = Get-NetFirewallRule -DisplayName "PiServer Attendance" -ErrorAction SilentlyContinue

if (-not $FirewallRule) {
    New-NetFirewallRule -DisplayName "PiServer Attendance" `
                        -Direction Inbound `
                        -LocalPort $Port `
                        -Protocol TCP `
                        -Action Allow | Out-Null
    Write-Info "Firewall rule created"
} else {
    Write-Info "Firewall rule already exists"
}

# =============================================================================
# Create Desktop Shortcut
# =============================================================================

Write-Step "Creating desktop shortcut..."

$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("$env:USERPROFILE\Desktop\PiServer Attendance.url")
$Shortcut.TargetPath = "http://localhost:$Port"
$Shortcut.Save()

Write-Info "Desktop shortcut created"

# =============================================================================
# Completion
# =============================================================================

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "  Installation Complete!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
Write-Host "Access the application at: http://localhost:$Port" -ForegroundColor Cyan
Write-Host ""
Write-Host "Useful commands:" -ForegroundColor Yellow
Write-Host "  - View service status: Get-Service $ServiceName"
Write-Host "  - Stop service:        Stop-Service $ServiceName"
Write-Host "  - Start service:       Start-Service $ServiceName"
Write-Host "  - Restart service:     Restart-Service $ServiceName"
Write-Host ""
Write-Host "Configuration: $DataDir\attendance.env" -ForegroundColor Yellow
Write-Host "Database:      $DataDir\attendance.db" -ForegroundColor Yellow
Write-Host ""

# Open browser
Start-Process "http://localhost:$Port"
