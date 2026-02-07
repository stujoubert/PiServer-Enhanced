# 🚀 Quick Start Guide

Get PiServer running in under 5 minutes!

## Method 1: Docker (Easiest) ⭐

```bash
# 1. Clone repository
git clone https://github.com/stujoubert/PiServer.git
cd PiServer

# 2. Start with Docker
docker-compose up -d

# 3. Access at http://localhost:5000
# Default login: admin / admin (change immediately!)
```

## Method 2: Linux Auto-Install

```bash
# One command installation
curl -sSL https://raw.githubusercontent.com/stujoubert/PiServer/main/install.sh | sudo bash

# Follow prompts for:
# - Port number (default: 5000)
# - Admin username
# - Admin password

# Access at http://localhost:5000
```

## Method 3: Windows

```powershell
# 1. Download install.ps1

# 2. Run as Administrator
powershell -ExecutionPolicy Bypass -File install.ps1

# 3. Follow prompts

# 4. Access at http://localhost:5000
```

## First Steps After Installation

### 1. Login
- Navigate to `http://localhost:5000`
- Use admin credentials you created

### 2. Configure Company Settings
- Go to Management → Company Settings
- Upload logo
- Set company name
- Configure timezone

### 3. Add Devices
- Go to Management → Devices
- Click "Add Device"
- Enter Hikvision device details:
  - Name
  - IP Address
  - Username
  - Password

### 4. Add Users
- Go to Management → Users
- Click "Add User"
- Fill in employee details:
  - Name
  - Employee ID
  - Email (optional)
  - Schedule template

### 5. Set Up Schedules
- Go to Management → Schedule Templates
- Create schedule (e.g., "9-5 Weekdays")
- Assign to users

## Testing

### Test Device Connection
```bash
# From Devices page, click "Test Connection"
# Should show green if successful
```

### Test Clock In/Out
```bash
# Via API
curl -X POST http://localhost:5000/api/v1/events \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{
    "employee_id": "12345",
    "timestamp": "2026-02-07T09:00:00",
    "direction": "in"
  }'
```

## Troubleshooting

### Can't Access Web Interface
```bash
# Check if service is running
systemctl status attendance  # Linux
Get-Service PiServerAttendance  # Windows

# Check firewall
sudo ufw allow 5000  # Linux
```

### Database Errors
```bash
# Check database file exists
ls -la /var/lib/attendance/attendance.db

# Check permissions
sudo chown -R attendance:attendance /var/lib/attendance
```

### Device Connection Fails
- Verify device IP is reachable: `ping device-ip`
- Check device credentials
- Ensure device API is enabled
- Review firewall rules

## Need Help?

- 📖 [Full Documentation](README.md)
- 🐛 [Report Issues](https://github.com/stujoubert/PiServer/issues)
- 💬 [Discord Community](https://discord.gg/piserver)
- 📧 [Email Support](mailto:support@piserver.dev)

## What's Next?

- ✅ Set up email notifications
- ✅ Generate API keys for integrations
- ✅ Configure automated backups
- ✅ Enable HTTPS
- ✅ Customize dashboard
- ✅ Train your team

**Enjoy PiServer! ⭐**
