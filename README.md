# PiServer - Enhanced Time & Attendance System

A modern, feature-rich time and attendance management system designed for Hikvision devices with support for facial recognition, scheduling, and comprehensive reporting.

![Version](https://img.shields.io/badge/version-2.0.0-blue)
![Python](https://img.shields.io/badge/python-3.11+-green)
![License](https://img.shields.io/badge/license-MIT-orange)

## ✨ Features

### Core Functionality
- **Multi-Device Support**: Manage multiple Hikvision attendance devices
- **Facial Recognition**: Automatic face capture and storage
- **Real-time Tracking**: Live attendance monitoring
- **Schedule Management**: Flexible shift templates and rotations
- **GPS Geofencing**: Location-based attendance verification
- **Payroll Integration**: Export data for payroll processing

### User Interface
- **Modern Dashboard**: Interactive charts and real-time statistics
- **Dark Mode**: Eye-friendly theme switching
- **Responsive Design**: Works on desktop, tablet, and mobile
- **Multi-language**: English and Spanish support
- **Accessibility**: WCAG 2.2 compliant

### Reports & Analytics
- **Daily Reports**: Detailed attendance logs
- **Weekly Summaries**: 7-day attendance overview
- **Monthly Analytics**: Comprehensive performance metrics
- **Custom Reports**: Flexible date range queries
- **Export Options**: PDF, Excel, CSV formats

### Integration
- **REST API**: Full-featured API for external systems
- **Webhook Support**: Real-time event notifications
- **Email Alerts**: Automated notifications
- **Mobile Ready**: API endpoints for mobile apps

---

## 🚀 Quick Start

### Option 1: Docker (Recommended)

The fastest way to get started:

```bash
# Clone repository
git clone https://github.com/stujoubert/PiServer.git
cd PiServer

# Create environment file
cp .env.example .env
# Edit .env with your settings

# Start with Docker Compose
docker-compose up -d

# Access at http://localhost:5000
```

### Option 2: Automated Install Script

For Linux/macOS systems:

```bash
# Download and run installer
curl -sSL https://raw.githubusercontent.com/stujoubert/PiServer/main/install.sh | sudo bash
```

The installer will:
- ✅ Install system dependencies
- ✅ Set up Python virtual environment
- ✅ Configure database
- ✅ Create systemd service
- ✅ Generate secure credentials
- ✅ Start the application

### Option 3: Manual Installation

```bash
# 1. Install dependencies
sudo apt update
sudo apt install python3 python3-venv python3-pip git sqlite3

# 2. Clone repository
git clone https://github.com/stujoubert/PiServer.git
cd PiServer

# 3. Create virtual environment
python3 -m venv venv
source venv/bin/activate

# 4. Install Python packages
pip install -r requirements.txt

# 5. Configure environment
export ATT_ENV=prod
export ATT_DB=/var/lib/attendance/attendance.db
export ATT_PORT=5000
export SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")

# 6. Create data directories
mkdir -p /var/lib/attendance/faces

# 7. Start server
python server.py
```

---

## 📋 System Requirements

### Minimum Requirements
- **OS**: Ubuntu 20.04+, Debian 11+, CentOS 8+, macOS 12+
- **Python**: 3.11 or higher
- **RAM**: 512 MB
- **Disk**: 1 GB free space
- **Database**: SQLite 3.x

### Recommended for Production
- **RAM**: 2 GB+
- **CPU**: 2+ cores
- **Disk**: 10 GB+ (for face images and logs)
- **Network**: Static IP or domain name

### Browser Support
- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+

---

## 🔧 Configuration

### Environment Variables

Create `/etc/attendance/attendance.env`:

```bash
# Environment
ATT_ENV=prod              # prod or dev
ATT_DB=/var/lib/attendance/attendance.db
ATT_PORT=5000

# Security
SECRET_KEY=your-secret-key-here

# Timezone
TZ=America/New_York

# Email (optional)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
EMAIL_FROM=attendance@yourcompany.com

# API (optional)
API_RATE_LIMIT=100        # Requests per hour
API_TIMEOUT=30            # Seconds
```

### Database Configuration

The application uses SQLite by default. For production with high traffic, consider PostgreSQL:

```bash
# Install PostgreSQL adapter
pip install psycopg2-binary

# Update ATT_DB
ATT_DB=postgresql://user:password@localhost/attendance
```

---

## 👥 User Management

### Creating Admin Account

During installation:
```bash
python -c "
from werkzeug.security import generate_password_hash
import sqlite3

conn = sqlite3.connect('/var/lib/attendance/attendance.db')
cur = conn.cursor()

cur.execute('''
    INSERT INTO accounts (username, password_hash, role)
    VALUES (?, ?, ?)
''', ('admin', generate_password_hash('your-password'), 'admin'))

conn.commit()
conn.close()
"
```

### User Roles

- **Admin**: Full system access
- **Manager**: View reports, manage employees
- **Viewer**: Read-only access

---

## 🔌 API Documentation

### Authentication

All API requests require an API key in the header:

```bash
curl -H "X-API-Key: your-api-key" \
     http://localhost:5000/api/v1/users
```

### Generate API Key

1. Log in as admin
2. Navigate to Settings → API Keys
3. Click "Generate New Key"
4. Save the key securely

### Endpoints

#### Get Today's Attendance
```bash
GET /api/v1/attendance/today
```

Response:
```json
{
  "date": "2026-02-07",
  "summary": {
    "total_employees": 50,
    "present": 45,
    "absent": 5,
    "attendance_rate": 90.0
  },
  "attendance": [...]
}
```

#### Create Event
```bash
POST /api/v1/events
Content-Type: application/json

{
  "employee_id": "12345",
  "timestamp": "2026-02-07T09:00:00",
  "direction": "in"
}
```

#### Get Monthly Report
```bash
GET /api/v1/reports/monthly?year=2026&month=2
```

[Full API documentation](docs/API.md)

---

## 📱 Mobile App Integration

### QR Code Check-in

Generate QR codes for employees:

```python
import qrcode

# Generate QR with employee ID
qr = qrcode.make(f"ATT:{employee_id}")
qr.save(f"employee_{employee_id}.png")
```

### Mobile API Example

```javascript
// Clock in
fetch('https://your-server.com/api/v1/events', {
  method: 'POST',
  headers: {
    'X-API-Key': 'your-key',
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    employee_id: '12345',
    timestamp: new Date().toISOString(),
    direction: 'in',
    latitude: 40.7128,
    longitude: -74.0060
  })
});
```

---

## 🎨 Customization

### Company Branding

1. Upload logo via Settings → Company
2. Supported formats: PNG, JPG, SVG
3. Recommended size: 200x50 pixels

### Theme Customization

Edit `/static/style.css`:

```css
:root {
    --accent-color: #4da3ff;  /* Primary brand color */
    --navbar-bg: #1b1d21;     /* Navigation bar */
}
```

### Email Templates

Templates are located in `/templates/emails/`
- `welcome.html` - New user welcome
- `attendance_reminder.html` - Daily reminders
- `report_weekly.html` - Weekly reports

---

## 🐛 Troubleshooting

### Common Issues

**Issue**: Service fails to start
```bash
# Check logs
journalctl -u attendance -f

# Verify database permissions
ls -la /var/lib/attendance/

# Test manually
cd /opt/attendance
source venv/bin/activate
python server.py
```

**Issue**: Device connection fails
- Verify network connectivity
- Check device IP address
- Ensure device credentials are correct
- Review firewall rules

**Issue**: Face images not syncing
```bash
# Check storage permissions
ls -la /var/lib/attendance/faces/

# Verify disk space
df -h

# Test device API
curl http://device-ip/ISAPI/System/deviceInfo
```

### Debug Mode

Enable debugging:
```bash
export ATT_ENV=dev
export FLASK_DEBUG=1
python server.py
```

---

## 📊 Performance Optimization

### Database Optimization

```sql
-- Create indexes
CREATE INDEX idx_events_timestamp ON events(timestamp);
CREATE INDEX idx_events_employee ON events(employee_id);
CREATE INDEX idx_users_active ON users(is_active);

-- Vacuum database
VACUUM;
ANALYZE;
```

### Caching

Enable Redis caching:

```bash
pip install redis

# Update config
REDIS_URL=redis://localhost:6379/0
CACHE_ENABLED=true
```

### Nginx Reverse Proxy

```nginx
server {
    listen 80;
    server_name attendance.yourcompany.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /static {
        alias /opt/attendance/static;
        expires 30d;
    }
}
```

---

## 🔐 Security Best Practices

1. **Change default credentials** immediately
2. **Use HTTPS** in production (Let's Encrypt)
3. **Regular backups** of database
4. **Update dependencies** monthly
5. **Enable firewall** rules
6. **Rotate API keys** quarterly
7. **Monitor logs** for suspicious activity

### Backup Script

```bash
#!/bin/bash
# /etc/cron.daily/attendance-backup

DATE=$(date +%Y%m%d)
BACKUP_DIR=/backups/attendance

mkdir -p $BACKUP_DIR

# Backup database
sqlite3 /var/lib/attendance/attendance.db ".backup '$BACKUP_DIR/db_$DATE.db'"

# Backup faces
tar -czf $BACKUP_DIR/faces_$DATE.tar.gz /var/lib/attendance/faces/

# Keep only last 30 days
find $BACKUP_DIR -mtime +30 -delete
```

---

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md)

### Development Setup

```bash
# Fork and clone
git clone https://github.com/YOUR-USERNAME/PiServer.git
cd PiServer

# Create branch
git checkout -b feature/your-feature

# Install dev dependencies
pip install -r requirements-dev.txt

# Run tests
pytest

# Submit pull request
```

---

## 📝 License

This project is licensed under the MIT License - see [LICENSE](LICENSE) file.

---

## 🆘 Support

- **Documentation**: [docs.piserver.dev](https://docs.piserver.dev)
- **Issues**: [GitHub Issues](https://github.com/stujoubert/PiServer/issues)
- **Email**: support@piserver.dev
- **Community**: [Discord Server](https://discord.gg/piserver)

---

## 🌟 Acknowledgments

- Hikvision for device API documentation
- Flask community for the excellent framework
- Contributors and users for feedback

---

## 📈 Roadmap

- [ ] Mobile apps (iOS/Android)
- [ ] Biometric integration (fingerprint)
- [ ] Advanced analytics with ML
- [ ] Multi-company support
- [ ] Cloud sync option
- [ ] Voice commands
- [ ] Blockchain attendance verification

---

**Made with ❤️ for better workforce management**
