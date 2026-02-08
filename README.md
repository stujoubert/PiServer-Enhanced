# 🎯 PiServer - Complete Enterprise Time & Attendance System

**Version:** 2.1.0 Complete | **Status:** Production Ready ✅

A comprehensive workforce management system with Hikvision integration, department management, leave tracking, and advanced analytics.

---

## 🚀 Quick Start

### Docker (Recommended)
```bash
docker-compose up -d
# Access: http://localhost:5000
```

### Linux/macOS
```bash
chmod +x install.sh && sudo ./install.sh
```

### Windows
```powershell
./install.ps1  # Run as Administrator
```

---

## 📦 What's Included

✅ **Core Features**: Attendance tracking, device integration, facial recognition  
✅ **Modern UI**: Dark mode, charts, mobile responsive  
✅ **REST API**: Complete API with authentication  
✅ **Departments**: Hierarchical structure with managers  
✅ **Leave/PTO**: Request workflows and approvals  
✅ **Overtime**: Policies and tracking  
✅ **Reporting**: Advanced analytics and exports  
✅ **Security**: Role-based access, audit logging  

---

## 📚 Documentation

- **QUICKSTART.md** - 5-minute setup
- **IMPLEMENTATION_GUIDE.md** - Detailed instructions
- **ADDITIONAL_FEATURES_GUIDE.md** - Advanced features
- **GITHUB_SETUP.md** - Upload to GitHub

---

## 🛠️ Setup

1. **Database**: `sqlite3 $ATT_DB < schema.sql && sqlite3 $ATT_DB < schema_enhancements.sql`
2. **Initialize**: `python3 setup_features.py`
3. **Configure**: Edit `.env` file
4. **Deploy**: Choose method above

---

## 📊 Features

- Multi-device support
- Department hierarchy
- Leave management
- Overtime tracking
- Shift templates
- Approval workflows
- Real-time notifications
- Complete audit trail
- Export to PDF/Excel
- REST API

---

## 🔐 Default Login

Username: `admin`  
Password: Set during installation

**⚠️ Change immediately after first login!**

---

## 📞 Support

- Documentation: See .md files
- Issues: GitHub Issues
- License: MIT

---

**Ready to deploy!** See documentation for full details.

## 🔧 Troubleshooting

### Database Issues

If you encounter database errors after installation, run the repair script:
```bash
cd /opt/attendance
sudo ./repair-database.sh
```

This will:
- Create a backup of your database
- Add any missing columns
- Verify table structure
- Create admin account if missing
- Restart the service
