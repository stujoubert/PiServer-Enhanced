/* =============================================================================
   Universal Dark Mode JavaScript for PiServer
   ============================================================================= */

(function() {
    'use strict';
    
    const currentTheme = localStorage.getItem('theme') || 'light';
    document.documentElement.setAttribute('data-theme', currentTheme);
    
    document.addEventListener('DOMContentLoaded', function() {
        createToggleButton();
        updateToggleIcon(currentTheme);
        
        const toggleBtn = document.getElementById('darkModeToggle');
        if (toggleBtn) {
            toggleBtn.addEventListener('click', toggleTheme);
        }
    });
    
    function createToggleButton() {
        if (document.getElementById('darkModeToggle')) {
            return;
        }
        
        const navbar = document.querySelector('.navbar-nav');
        if (!navbar) {
            console.warn('Navbar not found, cannot add dark mode toggle');
            return;
        }
        
        const li = document.createElement('li');
        li.className = 'nav-item';
        
        const button = document.createElement('button');
        button.id = 'darkModeToggle';
        button.className = 'nav-link btn btn-link';
        button.setAttribute('aria-label', 'Toggle dark mode');
        button.innerHTML = '<i class="bi bi-moon-fill"></i>';
        
        li.appendChild(button);
        navbar.appendChild(li);
    }
    
    function updateToggleIcon(theme) {
        const toggleBtn = document.getElementById('darkModeToggle');
        if (!toggleBtn) return;
        
        if (theme === 'dark') {
            toggleBtn.innerHTML = '<i class="bi bi-sun-fill"></i>';
            toggleBtn.setAttribute('aria-label', 'Switch to light mode');
        } else {
            toggleBtn.innerHTML = '<i class="bi bi-moon-fill"></i>';
            toggleBtn.setAttribute('aria-label', 'Switch to dark mode');
        }
    }
    
    function toggleTheme() {
        const currentTheme = document.documentElement.getAttribute('data-theme');
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        
        document.documentElement.setAttribute('data-theme', newTheme);
        localStorage.setItem('theme', newTheme);
        updateToggleIcon(newTheme);
        
        const event = new CustomEvent('themeChanged', { detail: { theme: newTheme } });
        document.dispatchEvent(event);
    }
    
    window.toggleDarkMode = toggleTheme;
    
})();
