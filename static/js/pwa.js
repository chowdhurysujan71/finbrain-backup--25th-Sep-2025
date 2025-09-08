// FinBrain PWA JavaScript
// Handles PWA installation, offline detection, and enhanced functionality

(function() {
    'use strict';
    
    console.log('[PWA] Initializing FinBrain PWA...');
    
    // Global state
    let deferredPrompt;
    let isOnline = navigator.onLine;
    let swRegistration = null;
    
    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initPWA);
    } else {
        initPWA();
    }
    
    function initPWA() {
        initializeUserSession();
        registerServiceWorker();
        setupOfflineDetection();
        setupInstallPrompt();
        setupNotifications();
        setupPerformanceOptimizations();
        
        console.log('[PWA] FinBrain PWA initialized successfully');
    }
    
    // User Session Management for PWA
    function initializeUserSession() {
        // Get or create persistent user ID for anonymous PWA users
        let userId = localStorage.getItem('finbrain_user_id');
        if (!userId) {
            userId = `pwa_user_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
            localStorage.setItem('finbrain_user_id', userId);
            console.log('[PWA] Created new user ID:', userId);
        } else {
            console.log('[PWA] Using existing user ID:', userId);
        }
        
        // Set up HTMX to send user ID with all requests
        if (typeof htmx !== 'undefined') {
            document.body.addEventListener('htmx:configRequest', (event) => {
                event.detail.headers['X-User-ID'] = userId;
                // User ID successfully attached to all requests
            });
        }
        
        // Also set up for regular form submissions
        const forms = document.querySelectorAll('form');
        forms.forEach(form => {
            // Add user ID as hidden field
            if (!form.querySelector('input[name="user_id"]')) {
                const hiddenInput = document.createElement('input');
                hiddenInput.type = 'hidden';
                hiddenInput.name = 'user_id';
                hiddenInput.value = userId;
                form.appendChild(hiddenInput);
            }
        });
        
        // Store user ID globally for other functions to use
        window.finbrainUserId = userId;
    }
    
    // Service Worker Registration
    async function registerServiceWorker() {
        if ('serviceWorker' in navigator) {
            try {
                swRegistration = await navigator.serviceWorker.register('/static/js/sw.js', {
                    scope: '/'
                });
                
                console.log('[PWA] Service Worker registered:', swRegistration.scope);
                
                // Handle updates
                swRegistration.addEventListener('updatefound', () => {
                    const newWorker = swRegistration.installing;
                    
                    newWorker.addEventListener('statechange', () => {
                        if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
                            showUpdateAvailable();
                        }
                    });
                });
                
            } catch (error) {
                console.error('[PWA] Service Worker registration failed:', error);
            }
        }
    }
    
    // Offline/Online Detection
    function setupOfflineDetection() {
        const offlineBanner = document.getElementById('offline-banner');
        
        function updateOnlineStatus() {
            const wasOnline = isOnline;
            isOnline = navigator.onLine;
            
            if (offlineBanner) {
                if (isOnline) {
                    offlineBanner.classList.add('hidden');
                    if (!wasOnline) {
                        showToast('Connection restored! Syncing data...', 'success');
                    }
                } else {
                    offlineBanner.classList.remove('hidden');
                    showToast('You\'re now offline. Limited functionality available.', 'warning');
                }
            }
            
            // Update UI elements based on connection status
            updateUIForConnection(isOnline);
        }
        
        window.addEventListener('online', updateOnlineStatus);
        window.addEventListener('offline', updateOnlineStatus);
        
        // Initial status
        updateOnlineStatus();
    }
    
    // PWA Install Prompt
    function setupInstallPrompt() {
        const installBanner = document.getElementById('install-banner');
        const installButton = document.getElementById('install-button');
        const dismissButton = document.getElementById('install-dismiss');
        
        // Listen for the beforeinstallprompt event
        window.addEventListener('beforeinstallprompt', (e) => {
            console.log('[PWA] Install prompt available');
            
            // Prevent the mini-infobar from appearing on mobile
            e.preventDefault();
            
            // Save the event for later use
            deferredPrompt = e;
            window.deferredPrompt = e; // Make it globally accessible
            
            // Show custom install banner
            if (installBanner && !isAppInstalled()) {
                installBanner.classList.remove('hidden');
            }
        });
        
        // Handle install button click
        if (installButton) {
            installButton.addEventListener('click', async () => {
                if (deferredPrompt) {
                    // Show the install prompt
                    deferredPrompt.prompt();
                    
                    // Wait for the user to respond
                    const { outcome } = await deferredPrompt.userChoice;
                    
                    console.log('[PWA] Install prompt outcome:', outcome);
                    
                    if (outcome === 'accepted') {
                        showToast('FinBrain is being installed!', 'success');
                    }
                    
                    // Clear the deferred prompt
                    deferredPrompt = null;
                    window.deferredPrompt = null;
                    
                    // Hide the banner
                    if (installBanner) {
                        installBanner.classList.add('hidden');
                    }
                }
            });
        }
        
        // Handle dismiss button click
        if (dismissButton) {
            dismissButton.addEventListener('click', () => {
                if (installBanner) {
                    installBanner.classList.add('hidden');
                }
                
                // Remember dismissal for this session
                sessionStorage.setItem('install-dismissed', 'true');
            });
        }
        
        // Listen for successful installation
        window.addEventListener('appinstalled', () => {
            console.log('[PWA] App successfully installed');
            showToast('FinBrain installed successfully!', 'success');
            
            // Hide install banner
            if (installBanner) {
                installBanner.classList.add('hidden');
            }
            
            // Clear the deferred prompt
            deferredPrompt = null;
            window.deferredPrompt = null;
        });
    }
    
    // Notification Setup
    function setupNotifications() {
        // Request notification permission if supported
        if ('Notification' in window && 'serviceWorker' in navigator) {
            // Don't request immediately - wait for user interaction
            console.log('[PWA] Notifications supported');
        }
    }
    
    // Performance Optimizations
    function setupPerformanceOptimizations() {
        // Preload critical pages
        if ('serviceWorker' in navigator && swRegistration) {
            preloadCriticalPages();
        }
        
        // Setup HTMX optimizations
        setupHTMXOptimizations();
        
        // Setup image lazy loading
        setupLazyLoading();
    }
    
    // Helper Functions
    function isAppInstalled() {
        // Check if app is running in standalone mode
        return window.matchMedia && 
               window.matchMedia('(display-mode: standalone)').matches ||
               window.navigator.standalone === true;
    }
    
    function updateUIForConnection(online) {
        // Update form submit buttons
        const submitButtons = document.querySelectorAll('button[type="submit"]');
        submitButtons.forEach(button => {
            if (online) {
                button.disabled = false;
                button.textContent = button.textContent.replace(' (Offline)', '');
            } else {
                button.textContent = button.textContent + ' (Offline)';
            }
        });
        
        // Update navigation items
        const navItems = document.querySelectorAll('.nav-item');
        navItems.forEach(item => {
            if (online) {
                item.classList.remove('offline');
            } else {
                item.classList.add('offline');
            }
        });
    }
    
    function showUpdateAvailable() {
        const updateToast = showToast(
            'A new version is available! Tap to update.',
            'info',
            { 
                duration: 0, // Don't auto-dismiss
                dismissible: false 
            }
        );
        
        // Add update button
        const updateButton = document.createElement('button');
        updateButton.textContent = 'Update';
        updateButton.className = 'btn btn-primary btn-sm';
        updateButton.onclick = () => {
            if (swRegistration && swRegistration.waiting) {
                swRegistration.waiting.postMessage({ type: 'SKIP_WAITING' });
                window.location.reload();
            }
        };
        
        updateToast.querySelector('.toast-content').appendChild(updateButton);
    }
    
    function preloadCriticalPages() {
        const criticalPages = ['/chat', '/report'];
        
        criticalPages.forEach(page => {
            const link = document.createElement('link');
            link.rel = 'prefetch';
            link.href = page;
            document.head.appendChild(link);
        });
    }
    
    function setupHTMXOptimizations() {
        // HTMX error handling
        document.body.addEventListener('htmx:responseError', (event) => {
            console.error('[PWA] HTMX error:', event.detail);
            
            if (!isOnline) {
                showToast('Action saved for when you\'re back online', 'info');
            } else {
                showToast('Something went wrong. Please try again.', 'error');
            }
        });
        
        // HTMX loading states
        document.body.addEventListener('htmx:beforeRequest', (event) => {
            const target = event.target;
            if (target.classList.contains('btn')) {
                target.disabled = true;
                target.textContent = 'Loading...';
            }
        });
        
        document.body.addEventListener('htmx:afterRequest', (event) => {
            const target = event.target;
            if (target.classList.contains('btn')) {
                target.disabled = false;
                target.textContent = target.dataset.originalText || 'Submit';
            }
        });
    }
    
    function setupLazyLoading() {
        // Intersection Observer for lazy loading images
        if ('IntersectionObserver' in window) {
            const lazyImages = document.querySelectorAll('img[data-src]');
            
            const imageObserver = new IntersectionObserver((entries, observer) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        const img = entry.target;
                        img.src = img.dataset.src;
                        img.classList.remove('lazy');
                        observer.unobserve(img);
                    }
                });
            });
            
            lazyImages.forEach(img => imageObserver.observe(img));
        }
    }
    
    // Global Toast Function (Enhanced)
    window.showToast = function(message, type = 'info', options = {}) {
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.setAttribute('role', 'alert');
        toast.setAttribute('aria-live', 'assertive');
        toast.setAttribute('aria-atomic', 'true');
        
        let toastHTML = '<div class="toast-content">';
        
        // Icons
        const icons = {
            'success': '✅',
            'error': '❌', 
            'warning': '⚠️',
            'info': 'ℹ️'
        };
        
        if (options.icon || icons[type]) {
            toastHTML += `<span class="toast-icon">${options.icon || icons[type]}</span>`;
        }
        
        toastHTML += `<span class="toast-message">${message}</span>`;
        
        if (options.dismissible !== false) {
            toastHTML += `
                <button class="toast-close" onclick="this.parentElement.parentElement.remove()" aria-label="Close">
                    &times;
                </button>
            `;
        }
        
        toastHTML += '</div>';
        toast.innerHTML = toastHTML;
        
        // Container
        let container = document.getElementById('toast-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'toast-container';
            container.className = 'toast-container';
            container.setAttribute('aria-live', 'polite');
            document.body.appendChild(container);
        }
        
        container.appendChild(toast);
        
        // Animation
        setTimeout(() => {
            toast.style.opacity = '1';
            toast.style.transform = 'translateX(0)';
        }, 10);
        
        // Auto-remove
        const duration = options.duration !== undefined ? options.duration : 5000;
        if (duration > 0) {
            setTimeout(() => {
                if (toast.parentElement) {
                    toast.style.opacity = '0';
                    toast.style.transform = 'translateX(100%)';
                    setTimeout(() => toast.remove(), 300);
                }
            }, duration);
        }
        
        return toast;
    };
    
    // Expose useful PWA functions globally
    window.FinBrainPWA = {
        isOnline: () => isOnline,
        isInstalled: isAppInstalled,
        triggerInstall: () => {
            if (deferredPrompt) {
                deferredPrompt.prompt();
            } else {
                showToast('Install FinBrain from your browser menu for the best experience!', 'info');
            }
        },
        requestNotificationPermission: async () => {
            if ('Notification' in window) {
                const permission = await Notification.requestPermission();
                console.log('[PWA] Notification permission:', permission);
                return permission;
            }
            return 'denied';
        }
    };
    
    console.log('[PWA] FinBrain PWA setup complete');
    
})();