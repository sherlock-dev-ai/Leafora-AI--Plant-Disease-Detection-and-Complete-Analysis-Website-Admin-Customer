// Leafora AI - Modern UI JavaScript
// Handles sidebar interactions, animations, and UI enhancements

document.addEventListener('DOMContentLoaded', function() {
    // Sidebar hover behavior (for desktop)
    const sidebar = document.getElementById('sidebar');
    if (sidebar && window.innerWidth > 768) {
        // Sidebar expands on hover automatically via CSS
        // This is just for any additional interactions if needed
    }

    // Mobile sidebar toggle
    if (window.innerWidth <= 768) {
        // ... (existing mobile menu logic)
    }

    // Custom Cursor Animation
    const dot = document.createElement('div');
    const circle1 = document.createElement('div');
    const circle2 = document.createElement('div');
    const circle2Inner = document.createElement('div');
    
    dot.className = 'cursor-dot';
    circle1.className = 'cursor-circle';
    circle2.className = 'cursor-circle-2';
    circle2Inner.className = 'cursor-circle-2-inner';
    
    circle2.appendChild(circle2Inner);
    document.body.appendChild(dot);
    document.body.appendChild(circle1);
    document.body.appendChild(circle2);

    let mouseX = -100, mouseY = -100; // Start off-screen
    let dotX = -100, dotY = -100;
    let circle1X = -100, circle1Y = -100;
    let circle2X = -100, circle2Y = -100;
    let hasMoved = false;

    document.addEventListener('mousemove', (e) => {
        mouseX = e.clientX;
        mouseY = e.clientY;
        
        if (!hasMoved) {
            hasMoved = true;
            dot.style.display = 'block';
            circle1.style.display = 'block';
            circle2.style.display = 'block';
            
            // Snap to initial position
            dotX = circle1X = circle2X = mouseX;
            dotY = circle1Y = circle2Y = mouseY;
        }
    });

    let isVisible = true;
    document.addEventListener('visibilitychange', () => {
        isVisible = document.visibilityState === 'visible';
        if (!isVisible) {
            dot.style.display = 'none';
            circle1.style.display = 'none';
            circle2.style.display = 'none';
        } else if (hasMoved) {
            dot.style.display = 'block';
            circle1.style.display = 'block';
            circle2.style.display = 'block';
        }
    });

    // Handle mouse leaving the window
    document.addEventListener('mouseleave', () => {
        dot.style.display = 'none';
        circle1.style.display = 'none';
        circle2.style.display = 'none';
    });

    document.addEventListener('mouseenter', () => {
        if (hasMoved) {
            dot.style.display = 'block';
            circle1.style.display = 'block';
            circle2.style.display = 'block';
        }
    });

    // Smooth following animation using transform for performance
    function animateCursor() {
        if (!isVisible || !hasMoved) {
            requestAnimationFrame(animateCursor);
            return;
        }

        // Dot follows mouse immediately but through RAF
        dotX = mouseX;
        dotY = mouseY;
        dot.style.transform = `translate3d(${dotX}px, ${dotY}px, 0) translate(-50%, -50%)`;

        // Circle 1 follows mouse with some delay (lerp)
        circle1X += (mouseX - circle1X) * 0.2;
        circle1Y += (mouseY - circle1Y) * 0.2;
        circle1.style.transform = `translate3d(${circle1X}px, ${circle1Y}px, 0) translate(-50%, -50%)`;

        // Circle 2 follows mouse with more delay
        circle2X += (mouseX - circle2X) * 0.1;
        circle2Y += (mouseY - circle2Y) * 0.1;
        circle2.style.transform = `translate3d(${circle2X}px, ${circle2Y}px, 0) translate(-50%, -50%)`;

        requestAnimationFrame(animateCursor);
    }
    animateCursor();

    // Hover effect on clickables
    const clickables = 'a, button, .btn, .upload-area, input[type="submit"], input[type="button"], .sidebar-item, .nav-link, .form-check-input';
    
    document.addEventListener('mouseover', (e) => {
        if (e.target.closest(clickables)) {
            document.body.classList.add('cursor-hover');
        }
    });

    document.addEventListener('mouseout', (e) => {
        if (e.target.closest(clickables)) {
            document.body.classList.remove('cursor-hover');
        }
    });

    // Click animation
    window.addEventListener('mousedown', (e) => {
        const clickAnim = document.createElement('div');
        clickAnim.className = 'cursor-click-anim';
        // Set initial position using top/left since the animation includes transform translate(-50%, -50%)
        clickAnim.style.left = `${e.clientX}px`;
        clickAnim.style.top = `${e.clientY}px`;
        document.body.appendChild(clickAnim);
        
        // Remove after animation completes
        setTimeout(() => {
            clickAnim.remove();
        }, 600);
    }, true);

    // Theme Toggle Logic
    const themeToggleBtn = document.getElementById('themeToggle');
    const themeIcon = document.getElementById('themeIcon');
    const htmlElement = document.documentElement;

    // Force dark mode if on dashboard or if user hasn't set preference
    const isDashboard = window.location.pathname.includes('/dashboard') || 
                       document.getElementById('sidebar') !== null;
    
    let savedTheme = localStorage.getItem('theme');
    if (isDashboard) {
        savedTheme = 'dark'; // Force dark for premium dashboard look
    } else if (!savedTheme) {
        savedTheme = 'dark'; // Default to dark
    }
    
    htmlElement.setAttribute('data-theme', savedTheme);
    updateThemeIcon(savedTheme);

    // Re-initialize hero canvas for background animations
    if (typeof initHeroCanvas === 'function') {
        initHeroCanvas();
    } else {
        // Fallback: If initHeroCanvas is not defined, we'll wait for landing.js to load
        // This is important for dashboard where landing.js is loaded in extra_js
        window.addEventListener('load', function() {
            if (typeof initHeroCanvas === 'function') {
                initHeroCanvas();
            }
        });
    }

    if (themeToggleBtn) {
        themeToggleBtn.addEventListener('click', () => {
            const currentTheme = htmlElement.getAttribute('data-theme');
            const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
            
            htmlElement.setAttribute('data-theme', newTheme);
            localStorage.setItem('theme', newTheme);
            updateThemeIcon(newTheme);
        });
    }

    function updateThemeIcon(theme) {
        if (!themeIcon) return;
        if (theme === 'dark') {
            themeIcon.classList.remove('bi-sun-fill');
            themeIcon.classList.add('bi-moon-fill');
        } else {
            themeIcon.classList.remove('bi-moon-fill');
            themeIcon.classList.add('bi-sun-fill');
        }
    }

    // Smooth scroll for anchor links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            const href = this.getAttribute('href');
            if (href !== '#' && href.length > 1) {
                e.preventDefault();
                const target = document.querySelector(href);
                if (target) {
                    target.scrollIntoView({
                        behavior: 'smooth',
                        block: 'start'
                    });
                }
            }
        });
    });

    // Form validation enhancement
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            if (!form.checkValidity()) {
                e.preventDefault();
                e.stopPropagation();
            }
            form.classList.add('was-validated');
        });
    });

    // Auto-hide flash messages after 5 seconds
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            alert.style.transition = 'opacity 0.5s';
            alert.style.opacity = '0';
            setTimeout(() => alert.remove(), 500);
        }, 5000);
    });

    // Initialize tooltips
    document.querySelectorAll('[data-tooltip]').forEach(element => {
        element.addEventListener('mouseenter', function() {
            // Tooltip is handled by CSS
        });
    });

    // Image preview enhancement
    const imagePreviews = document.querySelectorAll('img[onerror]');
    imagePreviews.forEach(img => {
        img.addEventListener('error', function() {
            if (!this.dataset.errorHandled) {
                this.dataset.errorHandled = 'true';
                // Error handler already in onerror attribute
            }
        });
    });

    // Card hover effects
    const cards = document.querySelectorAll('.card');
    cards.forEach(card => {
        card.addEventListener('mouseenter', function() {
            this.style.transform = 'translateY(-4px)';
        });
        card.addEventListener('mouseleave', function() {
            this.style.transform = 'translateY(0)';
        });
    });

    // Responsive adjustments
    window.addEventListener('resize', function() {
        if (window.innerWidth <= 768) {
            if (sidebar) sidebar.classList.remove('mobile-open');
        }
    });

    const modelToggles = document.querySelectorAll('.model-toggle');
    modelToggles.forEach(function(toggle) {
        // Styling handled by CSS; no JS animation
    });

    document.body.classList.add('page-loaded');
});

// --- Moving Dots Background (Shared Implementation) ---
/**
 * Background Animation Controller
 * Handles different animation styles for different pages
 */
window.LeaforaAnimations = {
    currentFrameId: null,
    currentType: null,
    
    stopAll: function() {
        if (this.currentFrameId) {
            cancelAnimationFrame(this.currentFrameId);
            this.currentFrameId = null;
        }
        this.currentType = null;
    }
};

window.initMovingDots = function(canvasId = 'heroCanvas', forceGreen = false) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    
    window.LeaforaAnimations.stopAll();
    window.LeaforaAnimations.currentType = 'movingDots';
    
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let width, height;
    let particles = [];
    let rareCircles = [];

    function resize() {
        width = canvas.width = window.innerWidth;
        height = canvas.height = window.innerHeight;
        initParticles();
    }

    function initParticles() {
        particles = [];
        rareCircles = [];
        const count = forceGreen ? 40 : 60; 
        for(let i=0; i<count; i++) {
            particles.push({
                x: Math.random() * width,
                y: Math.random() * height,
                vx: (Math.random() - 0.5) * 0.4,
                vy: (Math.random() - 0.5) * 0.4,
                size: Math.random() * 1.5 + 0.5,
                blinkTimer: Math.random() * 100,
                isGreen: forceGreen ? true : false,
                greenDuration: forceGreen ? Infinity : 0
            });
        }

        if (!forceGreen) {
            const circleCount = 6;
            for(let i=0; i<circleCount; i++) {
                rareCircles.push({
                    x: Math.random() * width,
                    y: Math.random() * height,
                    vx: (Math.random() - 0.5) * 0.2,
                    vy: (Math.random() - 0.5) * 0.2,
                    radius: 15 + Math.random() * 25,
                    opacity: 0.1 + Math.random() * 0.2,
                    pulse: Math.random() * Math.PI
                });
            }
        }
    }

    let isVisible = true;
    document.addEventListener('visibilitychange', () => {
        isVisible = document.visibilityState === 'visible';
    });

    function animate() {
        if (window.LeaforaAnimations.currentType !== 'movingDots') return;

        if (!isVisible) {
            requestAnimationFrame(animate);
            return;
        }
        
        ctx.fillStyle = '#000000';
        ctx.fillRect(0, 0, width, height);
        
        const time = Date.now() * 0.001;

        if (!forceGreen) {
            rareCircles.forEach(c => {
                c.x += c.vx;
                c.y += c.vy;
                if(c.x < -50) c.x = width + 50;
                if(c.x > width + 50) c.x = -50;
                if(c.y < -50) c.y = height + 50;
                if(c.y > height + 50) c.y = -50;

                const pulseRadius = c.radius + Math.sin(time + c.pulse) * 5;
                ctx.beginPath();
                ctx.strokeStyle = `rgba(255, 255, 255, ${c.opacity})`;
                ctx.lineWidth = 1;
                ctx.arc(c.x, c.y, pulseRadius, 0, Math.PI * 2);
                ctx.stroke();
            });
        }

        particles.forEach((p, index) => {
            p.x += p.vx;
            p.y += p.vy;
            
            if(p.x < 0) p.x = width;
            if(p.x > width) p.x = 0;
            if(p.y < 0) p.y = height;
            if(p.y > height) p.y = 0;
            
            if (!forceGreen) {
                p.blinkTimer++;
                if (p.blinkTimer > 200) {
                    if (Math.random() < 0.05) {
                        p.isGreen = true;
                        p.greenDuration = 30 + Math.random() * 50;
                        p.blinkTimer = 0;
                    }
                }
            }
            
            if (forceGreen) {
                ctx.fillStyle = '#4ade80';
                ctx.shadowBlur = 10;
                ctx.shadowColor = '#4ade80';
            } else if (p.isGreen) {
                ctx.fillStyle = '#4ade80';
                ctx.shadowBlur = 10;
                ctx.shadowColor = '#4ade80';
                p.greenDuration--;
                if (p.greenDuration <= 0) p.isGreen = false;
            } else {
                ctx.fillStyle = 'rgba(255, 255, 255, 0.5)';
                ctx.shadowBlur = 0;
            }
            
            ctx.beginPath();
            ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
            ctx.fill();
            ctx.shadowBlur = 0;

            // Skip lines if forceGreen is true (for login page specific look)
            if (forceGreen) return;

            for (let j = index + 1; j < particles.length; j++) {
                const p2 = particles[j];
                const dx = p.x - p2.x;
                const dy = p.y - p2.y;
                const dist = Math.sqrt(dx*dx + dy*dy);
                
                if (dist < 130 && (index + j) % 18 === 0) {
                    const isGlow = p.isGreen || p2.isGreen || (index + j) % 40 === 0;
                    const opacity = (1 - dist/130) * (isGlow ? 0.8 : 0.2);
                    
                    ctx.beginPath();
                    if (isGlow) {
                        ctx.strokeStyle = `rgba(74, 222, 128, ${opacity})`;
                        ctx.lineWidth = 1.5;
                        ctx.shadowBlur = 12;
                        ctx.shadowColor = '#4ade80';
                    } else {
                        ctx.strokeStyle = `rgba(255, 255, 255, ${opacity})`;
                        ctx.lineWidth = 0.5;
                        ctx.shadowBlur = 0;
                    }

                    const bendX = (p.x + p2.x) / 2 + Math.sin(time + index) * 40;
                    const bendY = (p.y + p2.y) / 2 + Math.cos(time + j) * 40;
                    
                    ctx.moveTo(p.x, p.y);
                    ctx.quadraticCurveTo(bendX, bendY, p2.x, p2.y);
                    ctx.stroke();
                    ctx.shadowBlur = 0;
                }
            }
        });
        window.LeaforaAnimations.currentFrameId = requestAnimationFrame(animate);
    }

    let resizeTimeout;
    window.addEventListener('resize', () => {
        clearTimeout(resizeTimeout);
        resizeTimeout = setTimeout(resize, 200);
    });
    resize();
    animate();
}

/**
 * Bio-Nodes Animation for Login Page
 * A different but similar organic background with pulsing green nodes
 */
window.initBioNodes = function(canvasId = 'heroCanvas') {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    
    window.LeaforaAnimations.stopAll();
    window.LeaforaAnimations.currentType = 'bioNodes';
    
    const ctx = canvas.getContext('2d');
    let width, height, nodes = [];
    
    function resize() {
        width = canvas.width = window.innerWidth;
        height = canvas.height = window.innerHeight;
        initNodes();
    }

    function initNodes() {
        nodes = [];
        const count = 40;
        for(let i=0; i<count; i++) {
            nodes.push({
                x: Math.random() * width,
                y: Math.random() * height,
                vx: (Math.random() - 0.5) * 0.5,
                vy: (Math.random() - 0.5) * 0.5,
                baseSize: Math.random() * 3 + 2,
                size: 0,
                angle: Math.random() * Math.PI * 2,
                speed: 0.02 + Math.random() * 0.03,
                opacity: 0.2 + Math.random() * 0.5
            });
        }
    }

    function animate() {
        if (window.LeaforaAnimations.currentType !== 'bioNodes') return;
        
        // Slight trail effect
        ctx.fillStyle = 'rgba(0, 0, 0, 0.1)';
        ctx.fillRect(0, 0, width, height);
        
        nodes.forEach(n => {
            n.x += n.vx;
            n.y += n.vy;
            n.angle += n.speed;
            
            // Pulse size
            n.size = n.baseSize + Math.sin(n.angle) * 2;
            
            if(n.x < -20) n.x = width + 20;
            if(n.x > width + 20) n.x = -20;
            if(n.y < -20) n.y = height + 20;
            if(n.y > height + 20) n.y = -20;
            
            const glow = ctx.createRadialGradient(n.x, n.y, 0, n.x, n.y, n.size * 4);
            glow.addColorStop(0, `rgba(74, 222, 128, ${n.opacity})`);
            glow.addColorStop(1, 'rgba(74, 222, 128, 0)');
            
            ctx.beginPath();
            ctx.fillStyle = glow;
            ctx.arc(n.x, n.y, n.size * 4, 0, Math.PI * 2);
            ctx.fill();
            
            ctx.beginPath();
            ctx.fillStyle = `rgba(187, 247, 208, ${n.opacity + 0.2})`;
            ctx.arc(n.x, n.y, n.size / 2, 0, Math.PI * 2);
            ctx.fill();
        });
        
        window.LeaforaAnimations.currentFrameId = requestAnimationFrame(animate);
    }

    window.addEventListener('resize', resize);
    resize();
    animate();
}

// Utility function for toast notifications (if needed)
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `alert alert-${type} glass`;
    toast.style.position = 'fixed';
    toast.style.top = '20px';
    toast.style.right = '20px';
    toast.style.zIndex = '10000';
    toast.style.minWidth = '300px';
    toast.innerHTML = `<strong><i class="bi bi-${type === 'success' ? 'check-circle' : type === 'danger' ? 'exclamation-triangle' : 'info-circle'}"></i></strong> ${message}`;
    
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.style.transition = 'opacity 0.5s';
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 500);
    }, 3000);
}

// Notification system
function safeJson(response) {
    const ct = response.headers.get('content-type') || '';
    if (!ct.includes('application/json')) {
        throw new Error('Non-JSON response');
    }
    return response.json();
}

function loadNotifications() {
    const isAuth = document.body && document.body.dataset && document.body.dataset.auth === '1';
    if (!isAuth) {
        const badge = document.getElementById('notificationBadge');
        if (badge) badge.style.display = 'none';
        return;
    }
    fetch('/notifications/count', { headers: { 'Accept': 'application/json' } })
        .then(safeJson)
        .then(data => {
            const badge = document.getElementById('notificationBadge');
            if (badge && data.count > 0) {
                badge.textContent = data.count > 99 ? '99+' : data.count;
                badge.style.display = 'block';
            } else if (badge) {
                badge.style.display = 'none';
            }
        })
        .catch(() => {
            const badge = document.getElementById('notificationBadge');
            if (badge) badge.style.display = 'none';
        });
}

function loadNotificationDropdown() {
    const notificationsList = document.getElementById('notificationsList');
    if (!notificationsList) return;
    const isAuth = document.body && document.body.dataset && document.body.dataset.auth === '1';
    if (!isAuth) {
        notificationsList.innerHTML = '<li><div class="px-3 py-2 notification-empty text-center"><i class="bi bi-lock"></i> Login to view notifications</div></li>';
        return;
    }
    
    // Show loading state
    notificationsList.innerHTML = '<li><div class="px-3 py-2 notification-loading text-center"><i class="bi bi-hourglass-split"></i> Loading...</div></li>';
    
    fetch('/notifications/list', { headers: { 'Accept': 'application/json' } })
        .then(safeJson)
        .then(data => {
            if (data.notifications && data.notifications.length > 0) {
                let html = '';
                data.notifications.forEach(notif => {
                    const typeClass = notif.type || 'info';
                    const typeIcon = typeClass === 'success' ? 'check-circle' : 
                                   typeClass === 'warning' ? 'exclamation-triangle' : 
                                   typeClass === 'danger' ? 'x-circle' : 'info-circle';
                    html += `
                        <li>
                            <a class="dropdown-item notification-item" href="#" onclick="markNotificationRead(${notif.id}); return false;">
                                <div class="d-flex justify-content-between align-items-start">
                                    <div class="flex-grow-1">
                                        <div class="d-flex align-items-center gap-2 mb-1">
                                            <i class="bi bi-${typeIcon} text-${typeClass}"></i>
                                            <strong class="notification-title text-${typeClass}">${escapeHtml(notif.title)}</strong>
                                        </div>
                                        <div class="notification-message">${escapeHtml(notif.message)}</div>
                                        <div class="notification-time">${notif.created_at}</div>
                                    </div>
                                </div>
                            </a>
                        </li>
                    `;
                });
                notificationsList.innerHTML = html;
            } else {
                notificationsList.innerHTML = '<li><div class="px-3 py-2 notification-empty text-center"><i class="bi bi-inbox"></i> No new notifications</div></li>';
            }
            // Update badge count
            loadNotifications();
        })
        .catch(error => {
            notificationsList.innerHTML = '<li><div class="px-3 py-2 notification-error text-center"><i class="bi bi-exclamation-triangle"></i> Error loading notifications</div></li>';
        });
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function markNotificationRead(notificationId) {
    fetch(`/notifications/mark-read/${notificationId}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        }
    })
    .then(safeJson)
    .then(data => {
        if (data.success) {
            // Reload notifications list and count
            loadNotificationDropdown();
            loadNotifications();
        }
    })
    .catch(error => console.error('Error marking notification as read:', error));
}

function markAllNotificationsRead() {
    fetch('/notifications/mark-all-read', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        }
    })
    .then(safeJson)
    .then(data => {
        if (data.success) {
            // Reload notifications list and count
            loadNotificationDropdown();
            loadNotifications();
            const badge = document.getElementById('notificationBadge');
            if (badge) badge.style.display = 'none';
        }
    })
    .catch(error => console.error('Error marking all as read:', error));
}

// Load notifications on page load
document.addEventListener('DOMContentLoaded', function() {
    loadNotifications();
    
    const markAllBtn = document.getElementById('markAllReadBtn');
    if (markAllBtn) {
        markAllBtn.addEventListener('click', function(e) {
            e.preventDefault();
            markAllNotificationsRead();
        });
    }
    
    // Load notifications when dropdown is shown (Bootstrap event)
    const notificationsDropdown = document.getElementById('notificationsDropdown');
    if (notificationsDropdown) {
        // Use Bootstrap's show.bs.dropdown event on the trigger element
        notificationsDropdown.addEventListener('show.bs.dropdown', function() {
            loadNotificationDropdown();
        });
        
        // Also load on click as fallback
        notificationsDropdown.addEventListener('click', function() {
            // Small delay to ensure dropdown is opening
            setTimeout(loadNotificationDropdown, 100);
        });
    }
    
    // Refresh notification count every 30 seconds
    setInterval(loadNotifications, 30000);

    // Handle notification read buttons
    document.addEventListener('click', function(e) {
        if (e.target.matches('button[data-notification-id]')) {
            const id = e.target.dataset.notificationId;
            markNotificationRead(id);
        }
    });
});
