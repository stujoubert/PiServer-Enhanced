# 🌓 Universal Dark Mode Implementation Guide

This guide will help you enable dark mode across **ALL** templates in your PiServer application.

---

## 🎯 What This Does

✅ Enables dark mode on **every page** (users, devices, reports, etc.)  
✅ Adds a toggle button in the navbar  
✅ Remembers user's preference (localStorage)  
✅ Smooth transitions between themes  
✅ Works with existing Bootstrap styling  
✅ No need to modify individual templates  

---

## 📦 Files Provided

1. **dark-mode-universal.css** - All the dark mode styles
2. **dark-mode-universal.js** - Toggle functionality
3. **This guide** - Implementation instructions

---

## 🚀 Quick Implementation (5 Minutes)

### **Step 1: Copy CSS and JS Files**

```bash
# SSH into your Raspberry Pi
ssh pi@raspberrypi.local

# Create static directory if it doesn't exist
sudo mkdir -p /opt/attendance/static/css
sudo mkdir -p /opt/attendance/static/js

# Copy the files (you'll need to upload them first)
# Option A: If you have them locally
sudo cp dark-mode-universal.css /opt/attendance/static/css/
sudo cp dark-mode-universal.js /opt/attendance/static/js/

# Option B: Create them directly
sudo nano /opt/attendance/static/css/dark-mode-universal.css
# Paste the CSS content, then save (Ctrl+X, Y, Enter)

sudo nano /opt/attendance/static/js/dark-mode-universal.js
# Paste the JS content, then save (Ctrl+X, Y, Enter)
```

### **Step 2: Update Your Base Layout Template**

Edit your main layout file:

```bash
sudo nano /opt/attendance/templates/layout.html
```

**Add these lines in the `<head>` section** (before `</head>`):

```html
<!-- Bootstrap Icons (if not already included) -->
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.0/font/bootstrap-icons.css">

<!-- Universal Dark Mode CSS -->
<link rel="stylesheet" href="{{ url_for('static', filename='css/dark-mode-universal.css') }}">
```

**Add this line before `</body>`:**

```html
<!-- Universal Dark Mode JavaScript -->
<script src="{{ url_for('static', filename='js/dark-mode-universal.js') }}"></script>
```

### **Step 3: Restart the Service**

```bash
sudo systemctl restart attendance
```

### **Step 4: Test!**

1. Go to your PiServer: `http://YOUR_PI_IP:5000`
2. Login
3. Look for a moon icon (🌙) in the navbar (top right area)
4. Click it to toggle dark mode
5. Navigate to different pages - dark mode works everywhere!

---

## 📋 Complete Example Layout.html

Here's what your `layout.html` should look like with dark mode added:

```html
<!DOCTYPE html>
<html lang="{{ g.lang }}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ T.app_title }}</title>
    
    <!-- Bootstrap CSS -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    
    <!-- Bootstrap Icons -->
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.0/font/bootstrap-icons.css">
    
    <!-- Your existing CSS -->
    <link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
    
    <!-- Universal Dark Mode CSS -->
    <link rel="stylesheet" href="{{ url_for('static', filename='css/dark-mode-universal.css') }}">
    
    {% block extra_css %}{% endblock %}
</head>
<body>
    <!-- Navbar -->
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark">
        <div class="container-fluid">
            <a class="navbar-brand" href="/">{{ T.app_title }}</a>
            
            <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav">
                <span class="navbar-toggler-icon"></span>
            </button>
            
            <div class="collapse navbar-collapse" id="navbarNav">
                <ul class="navbar-nav ms-auto">
                    <!-- Your existing nav items -->
                    <li class="nav-item">
                        <a class="nav-link" href="/dashboard/">Dashboard</a>
                    </li>
                    <!-- More nav items... -->
                    
                    <!-- Dark mode toggle will be automatically added here by JavaScript -->
                </ul>
            </div>
        </div>
    </nav>
    
    <!-- Main Content -->
    <div class="container-fluid mt-4">
        {% block content %}{% endblock %}
    </div>
    
    <!-- Bootstrap JS -->
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    
    <!-- Universal Dark Mode JavaScript -->
    <script src="{{ url_for('static', filename='js/dark-mode-universal.js') }}"></script>
    
    {% block extra_js %}{% endblock %}
</body>
</html>
```

---

## 🎨 Customization

### **Change Dark Mode Colors**

Edit `/opt/attendance/static/css/dark-mode-universal.css`:

```css
[data-theme="dark"] {
    --bg-primary: #1a1d23;        /* Main background */
    --bg-secondary: #23272f;      /* Card backgrounds */
    --text-primary: #e9ecef;      /* Main text */
    /* Change these to your preferred colors */
}
```

### **Move Toggle Button Position**

The JavaScript automatically adds the toggle to the navbar. To customize position:

Edit `/opt/attendance/static/js/dark-mode-universal.js`:

```javascript
// Find this line:
navbar.appendChild(li);

// Change to insert at beginning:
navbar.insertBefore(li, navbar.firstChild);
```

### **Add Toggle to a Specific Location**

Instead of auto-creating, manually add to your layout:

```html
<button id="darkModeToggle" class="btn btn-link">
    <i class="bi bi-moon-fill"></i>
</button>
```

The JavaScript will still work!

---

## 🔧 Troubleshooting

### **Toggle Button Doesn't Appear**

Check if Bootstrap Icons are loaded:
```bash
# Add to layout.html if missing
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.0/font/bootstrap-icons.css">
```

### **Dark Mode Doesn't Apply**

1. Clear browser cache (Ctrl+Shift+R)
2. Check browser console for errors (F12)
3. Verify CSS file is loaded:
   ```bash
   curl http://localhost:5000/static/css/dark-mode-universal.css
   ```

### **Dark Mode Resets on Page Load**

The preference is stored in localStorage. Check:
```javascript
// In browser console (F12)
localStorage.getItem('theme')
```

### **Some Elements Don't Change Color**

Add custom CSS to override:
```css
[data-theme="dark"] .your-element {
    background-color: var(--card-bg);
    color: var(--text-primary);
}
```

---

## 📱 Testing Checklist

Test dark mode on these pages:

- [ ] Dashboard
- [ ] Users list
- [ ] Add user form
- [ ] Devices
- [ ] Daily attendance
- [ ] Weekly view
- [ ] Payroll reports
- [ ] Settings
- [ ] Login page (if you want dark mode there too)

---

## 🎯 Advanced: Dark Mode for Login Page

To enable dark mode on the login page (before user is logged in):

```html
<!-- In templates/login.html -->
<head>
    ...
    <link rel="stylesheet" href="{{ url_for('static', filename='css/dark-mode-universal.css') }}">
</head>
<body>
    ...
    <script src="{{ url_for('static', filename='js/dark-mode-universal.js') }}"></script>
</body>
```

---

## 🌟 Features of This Implementation

✅ **Universal** - Works on all pages that extend layout.html  
✅ **Persistent** - Remembers user preference  
✅ **Fast** - No page flash when loading  
✅ **Smooth** - Animated transitions  
✅ **Accessible** - ARIA labels for screen readers  
✅ **Lightweight** - Minimal JavaScript  
✅ **Compatible** - Works with existing Bootstrap  

---

## 📊 Browser Support

- ✅ Chrome/Edge 90+
- ✅ Firefox 88+
- ✅ Safari 14+
- ✅ Mobile browsers (iOS/Android)

---

## 🔄 Updating Existing Deployments

If you already have users:

1. Deploy the CSS and JS files
2. Update layout.html
3. Restart service
4. Users will see the toggle button automatically
5. No database changes needed
6. No user data affected

---

## 💡 Pro Tips

1. **Test on all pages** before deploying to production
2. **Clear browser cache** after updates
3. **Keep CSS file** separate for easy updates
4. **Add to GitHub** so it's included in future deployments
5. **Document for users** - some might not notice the toggle

---

## ✅ Verification

After implementation, verify:

```bash
# Check files exist
ls -la /opt/attendance/static/css/dark-mode-universal.css
ls -la /opt/attendance/static/js/dark-mode-universal.js

# Check layout.html has the includes
grep -n "dark-mode-universal" /opt/attendance/templates/layout.html

# Restart and check service
sudo systemctl restart attendance
sudo systemctl status attendance
```

---

## 🎉 You're Done!

Your entire PiServer now has dark mode on every page!

**Next steps:**
- Customize colors to match your brand
- Add dark mode to login page
- Share with your users
- Enjoy the reduced eye strain! 😎
