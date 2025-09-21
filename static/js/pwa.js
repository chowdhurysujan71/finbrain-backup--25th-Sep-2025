// finbrain PWA JavaScript
// Handles PWA installation, offline detection, and enhanced functionality

(function() {
    'use strict';
    
    console.log('[PWA] Initializing finbrain PWA...');
    
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
        cleanupLegacyServiceWorkers(); // Clean up old SW registrations first (async)
        setupServiceWorkerCoordination(); // Listen for SW messages
        initializeUserSession();
        registerServiceWorker();
        setupOfflineDetection();
        setupInstallPrompt();
        setupNotifications();
        setupPerformanceOptimizations();
        
        console.log('[PWA] finbrain PWA initialized successfully');
    }
    
    // Service Worker Coordination - BroadcastChannel communication
    function setupServiceWorkerCoordination() {
        try {
            const swControlChannel = new BroadcastChannel('sw-control');
            
            swControlChannel.addEventListener('message', event => {
                const { type, version, timestamp } = event.data;
                
                if (type === 'SW_READY') {
                    console.log('[PWA] New service worker ready:', version);
                    
                    // Check for additional cleanup needed
                    navigator.serviceWorker.getRegistrations().then(registrations => {
                        const rootSWUrl = new URL('/sw.js', location.origin).href;
                        let needsCleanup = false;
                        
                        registrations.forEach(registration => {
                            const url = (registration.scriptURL || '');
                            if (url !== rootSWUrl) {
                                console.log('[PWA] Found stale registration:', url);
                                needsCleanup = true;
                                registration.unregister();
                            }
                        });
                        
                        if (needsCleanup) {
                            console.log('[PWA] Reloading to complete SW transition...');
                            // Small delay to let unregistration complete
                            setTimeout(() => location.reload(), 1000);
                        }
                    });
                }
            });
            
            // Listen for controller changes
            navigator.serviceWorker.addEventListener('controllerchange', () => {
                console.log('[PWA] Service worker controller changed');
                // Controller change indicates new SW is now in control
                showToast('App updated! New features available.', 'success');
            });
            
        } catch (error) {
            console.warn('[PWA] SW coordination setup failed:', error);
        }
    }
    
    // Nuclear Service Worker Cleanup - Force complete reset
    async function cleanupLegacyServiceWorkers() {
        try {
            if (!('serviceWorker' in navigator)) return;
            
            const FLAG = 'ultra-nuclear-cleanup-1.1.2-final';
            
            // ALWAYS check cache status first - force cleanup if needed
            const cacheNames = await caches.keys();
            if (cacheNames.length > 0) {
                console.log('[PWA] FORCING cleanup - found', cacheNames.length, 'caches:', cacheNames);
                localStorage.removeItem(FLAG); // Clear flag to force cleanup
                localStorage.clear(); // Clear ALL localStorage  
            } else if (localStorage.getItem(FLAG)) {
                console.log('[PWA] Cleanup already successful - 0 caches found');
                return; // Success, don't run again
            }
            
            console.log('[PWA] Starting ULTRA-NUCLEAR cleanup - FORCE MODE ACTIVE...');
            
            // Step 1: AGGRESSIVE cache deletion (synchronous)
            await nukeLegacyCaches();
            
            // Step 2: Nuke service workers
            const registrations = await navigator.serviceWorker.getRegistrations();
            console.log('[PWA] Found', registrations.length, 'service worker registrations');
            
            for (const registration of registrations) {
                const url = registration.scriptURL || 'undefined';
                console.log('[PWA] NUKING registration:', url);
                try {
                    const success = await registration.unregister();
                    console.log(`[PWA] Unregistered ${url}:`, success);
                } catch (err) {
                    console.warn('[PWA] Failed to unregister:', url, err);
                }
            }
            
            // Step 3: Verify cleanup worked
            const finalCaches = await caches.keys();
            const finalRegistrations = await navigator.serviceWorker.getRegistrations();
            
            console.log('[PWA] FINAL VERIFICATION:');
            console.log('[PWA] Remaining caches:', finalCaches.length, finalCaches);
            console.log('[PWA] Remaining registrations:', finalRegistrations.length);
            
            if (finalCaches.length === 0 && finalRegistrations.length === 0) {
                console.log('[PWA] ✅ ULTRA-NUCLEAR cleanup SUCCESS!');
                localStorage.setItem(FLAG, 'done');
            } else {
                console.log('[PWA] ❌ ULTRA-NUCLEAR cleanup FAILED - retrying...');
                localStorage.removeItem(FLAG);
            }
            
            // Force reload after cleanup
            setTimeout(() => {
                console.log('[PWA] Reloading page after cleanup...');
                location.reload(true); // Hard reload
            }, 1500);
            
        } catch (error) {
            console.warn('[PWA] Nuclear cleanup error:', error);
        }
    }
    
    // ULTRA-AGGRESSIVE Cache Cleanup - Delete EVERYTHING
    async function nukeLegacyCaches() {
        try {
            if (!('caches' in window)) return;
            
            console.log('[PWA] Starting ULTRA-AGGRESSIVE cache destruction...');
            
            // MULTIPLE ATTEMPTS: Try different approaches to delete caches
            for (let attempt = 1; attempt <= 3; attempt++) {
                console.log(`[PWA] Cache deletion attempt ${attempt}/3`);
                
                const cacheNames = await caches.keys();
                console.log(`[PWA] Attempt ${attempt}: Found`, cacheNames.length, 'caches:', cacheNames);
                
                if (cacheNames.length === 0) {
                    console.log('[PWA] ✅ All caches deleted successfully!');
                    break;
                }
                
                // Delete each cache individually with verification
                for (const cacheName of cacheNames) {
                    console.log(`[PWA] DESTROYING cache: ${cacheName}`);
                    try {
                        const deleted = await caches.delete(cacheName);
                        console.log(`[PWA] Cache ${cacheName} deleted:`, deleted);
                        
                        // Verify deletion
                        const stillExists = await caches.has(cacheName);
                        if (stillExists) {
                            console.warn(`[PWA] ⚠️ Cache ${cacheName} still exists after deletion!`);
                        }
                    } catch (err) {
                        console.error(`[PWA] FAILED to delete cache ${cacheName}:`, err);
                    }
                }
                
                // Small delay between attempts
                if (attempt < 3) {
                    await new Promise(resolve => setTimeout(resolve, 500));
                }
            }
            
            const finalCaches = await caches.keys();
            console.log('[PWA] FINAL cache count:', finalCaches.length, finalCaches);
            
        } catch (error) {
            console.warn('[PWA] Nuclear cache destruction failed:', error);
        }
    }
    
    // Session-based Authentication Check
    async function initializeUserSession() {
        console.log('[PWA] Checking authentication status...');
        
        // Clean up any old guest data from localStorage
        localStorage.removeItem('finbrain_user_id');
        localStorage.removeItem('finbrain_link_token');
        
        try {
            // Check if user is authenticated via session
            const authResponse = await fetch('/api/auth/me', {
                method: 'GET',
                credentials: 'include'
            });
            
            if (authResponse.ok) {
                const userData = await authResponse.json();
                console.log('[PWA] User authenticated:', userData.user?.email || 'Unknown');
                // User is logged in - continue with normal PWA functionality
                return;
            } else if (authResponse.status === 401) {
                // User not authenticated - redirect to login
                console.log('[PWA] User not authenticated, redirecting to login');
                if (window.location.pathname !== '/login' && window.location.pathname !== '/register') {
                    window.location.href = '/login?next=' + encodeURIComponent(window.location.pathname);
                }
                return;
            }
        } catch (error) {
            console.error('[PWA] Error checking authentication:', error);
            // Network error - show offline message but don't redirect
            showToast('Unable to verify authentication. Please check your connection.', 'warning');
        }
    }
    
    // Service Worker Registration - Enhanced for forced updates
    async function registerServiceWorker() {
        if ('serviceWorker' in navigator) {
            try {
                console.log('[PWA] Attempting to register service worker...');
                
                // Force update by adding cache-busting parameter
                const swUrl = `/sw.js?v=1.1.1&t=${Date.now()}`;
                swRegistration = await navigator.serviceWorker.register(swUrl, {
                    scope: '/',
                    updateViaCache: 'none' // Always fetch fresh service worker
                });
                
                console.log('[PWA] Service Worker registered successfully:', swRegistration.scope);
                
                // Force immediate update check
                await swRegistration.update();
                console.log('[PWA] Forced service worker update check');
                
                // Handle updates
                swRegistration.addEventListener('updatefound', () => {
                    const newWorker = swRegistration.installing;
                    console.log('[PWA] New service worker found, installing...');
                    
                    newWorker.addEventListener('statechange', () => {
                        console.log('[PWA] Service worker state changed to:', newWorker.state);
                        
                        if (newWorker.state === 'installed') {
                            if (navigator.serviceWorker.controller) {
                                console.log('[PWA] New service worker installed, reload required');
                                showUpdateAvailable();
                            } else {
                                console.log('[PWA] Service worker installed for first time');
                            }
                        }
                        
                        if (newWorker.state === 'activated') {
                            console.log('[PWA] New service worker activated');
                        }
                    });
                });
                
                // Check if there's already a waiting service worker
                if (swRegistration.waiting) {
                    console.log('[PWA] Service worker waiting, forcing activation...');
                    swRegistration.waiting.postMessage({type: 'SKIP_WAITING'});
                }
                
            } catch (error) {
                console.error('[PWA] Service Worker registration failed:', error.message || error);
                console.error('[PWA] Full error details:', error);
                
                // Continue without service worker - PWA can still partially work
                console.log('[PWA] Continuing without service worker...');
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
        
        console.log('[PWA] Setting up install prompt...');
        
        // Listen for the beforeinstallprompt event
        window.addEventListener('beforeinstallprompt', (e) => {
            console.log('[PWA] Install prompt available - beforeinstallprompt event fired');
            
            // Prevent the mini-infobar from appearing on mobile
            e.preventDefault();
            
            // Save the event for later use
            deferredPrompt = e;
            window.deferredPrompt = e; // Make it globally accessible
            
            // Show custom install banner
            if (installBanner && !isAppInstalled()) {
                installBanner.classList.remove('hidden');
            }
            
            console.log('[PWA] Installation is now available');
        });
        
        // For development/testing - show install option even if no prompt
        setTimeout(() => {
            if (!deferredPrompt && !isAppInstalled()) {
                console.log('[PWA] No install prompt detected - likely development mode');
                
                // Check if user dismissed banner recently
                const dismissedUntil = localStorage.getItem('install-dismissed');
                if (dismissedUntil && Date.now() < parseInt(dismissedUntil)) {
                    console.log('[PWA] Install banner dismissed until:', new Date(parseInt(dismissedUntil)));
                    return;
                }
                
                if (installBanner) {
                    installBanner.classList.remove('hidden');
                }
            }
        }, 2000);
        
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
                        showToast('finbrain is being installed!', 'success');
                    }
                    
                    // Clear the deferred prompt
                    deferredPrompt = null;
                    window.deferredPrompt = null;
                    
                    // Hide the banner
                    if (installBanner) {
                        installBanner.classList.add('hidden');
                    }
                } else {
                    // No browser prompt available - show manual instructions
                    console.log('[PWA] Showing manual install instructions');
                    showToast(`To install finbrain:
• Chrome: Click ⋮ menu → "Install finbrain..."
• Safari: Share → "Add to Home Screen"  
• Edge: Click ⋯ menu → "Apps" → "Install finbrain"
• Firefox: Address bar install icon`, 'info', { duration: 10000 });
                    
                    // Hide the banner after showing instructions
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
                
                // Remember dismissal for longer (7 days)
                localStorage.setItem('install-dismissed', Date.now() + (7 * 24 * 60 * 60 * 1000));
                console.log('[PWA] Install banner dismissed for 7 days');
            });
        }
        
        // Listen for successful installation
        window.addEventListener('appinstalled', () => {
            console.log('[PWA] App successfully installed');
            showToast('finbrain installed successfully!', 'success');
            
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
    
    // Enhanced Field Error Management
    function clearFieldErrors(form = document) {
        // Remove existing error styling and messages
        const errorInputs = form.querySelectorAll('.form-field-error');
        errorInputs.forEach(input => {
            input.classList.remove('form-field-error');
        });
        
        const errorMessages = form.querySelectorAll('.field-error-message');
        errorMessages.forEach(msg => msg.remove());
    }
    
    function displayFieldErrors(fieldErrors, form = document) {
        // Clear existing errors first
        clearFieldErrors(form);
        
        // Display new field errors
        Object.keys(fieldErrors).forEach(fieldName => {
            const field = form.querySelector(`[name="${fieldName}"], #${fieldName}`);
            if (field) {
                // Add error styling to input
                field.classList.add('form-field-error');
                
                // Create and insert error message
                const errorDiv = document.createElement('div');
                errorDiv.className = 'field-error-message';
                errorDiv.textContent = fieldErrors[fieldName];
                
                // Insert after the field or its wrapper
                const insertTarget = field.closest('.form-group') || field.closest('.input-group') || field;
                insertTarget.parentNode.insertBefore(errorDiv, insertTarget.nextSibling);
            }
        });
    }
    
    function handleStandardizedResponse(response, options = {}) {
        const form = options.form;
        
        // Clear previous field errors
        if (form) {
            clearFieldErrors(form);
        }
        
        if (response.success) {
            // Handle success
            if (response.message) {
                showToast(response.message, 'success', options.toastOptions || {});
            }
            
            // Call success callback if provided
            if (options.onSuccess) {
                options.onSuccess(response);
            }
            
        } else {
            // Handle error cases
            let errorType = 'error';
            let toastMessage = response.message || 'An error occurred';
            let toastOptions = { ...options.toastOptions };
            
            // Add trace ID if available
            if (response.trace_id) {
                toastOptions.traceId = response.trace_id;
            }
            
            // Handle different error codes
            switch (response.code) {
                case 'VALIDATION_ERROR':
                    errorType = 'warning';
                    toastMessage = response.message || 'Please check the highlighted fields';
                    
                    // Display field-specific errors
                    if (response.field_errors && form) {
                        displayFieldErrors(response.field_errors, form);
                    }
                    break;
                    
                case 'UNAUTHORIZED':
                    errorType = 'error';
                    toastMessage = response.message || 'You are not authorized to perform this action';
                    break;
                    
                case 'RATE_LIMITED':
                    errorType = 'warning';
                    toastMessage = response.message || 'Too many requests. Please try again later.';
                    toastOptions.persistent = true;
                    break;
                    
                case 'SERVER_ERROR':
                default:
                    errorType = 'error';
                    toastMessage = response.message || 'A server error occurred. Please try again.';
                    break;
            }
            
            showToast(toastMessage, errorType, toastOptions);
            
            // Call error callback if provided
            if (options.onError) {
                options.onError(response);
            }
        }
        
        return response.success;
    }
    
    function enhancedFormSubmit(form, endpoint, options = {}) {
        return new Promise((resolve, reject) => {
            const formData = new FormData(form);
            
            fetch(endpoint, {
                method: 'POST',
                credentials: 'include',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                // Handle standardized response
                const success = handleStandardizedResponse(data, {
                    form: form,
                    ...options
                });
                
                if (success) {
                    resolve(data);
                } else {
                    reject(data);
                }
            })
            .catch(error => {
                console.error('Form submission error:', error);
                
                // Handle network errors or non-JSON responses
                const fallbackError = {
                    success: false,
                    code: 'NETWORK_ERROR',
                    message: 'Network error. Please check your connection and try again.',
                    trace_id: `client_${Date.now()}`
                };
                
                handleStandardizedResponse(fallbackError, {
                    form: form,
                    ...options
                });
                
                reject(fallbackError);
            });
        });
    }
    
    // Legacy compatibility: Handle non-standardized responses
    function handleLegacyResponse(data, form = null) {
        // Clear any existing field errors
        if (form) {
            clearFieldErrors(form);
        }
        
        // Try to determine success/error from legacy format
        if (data.error || data.status === 'error' || data.success === false) {
            const message = data.error || data.message || 'An error occurred';
            showToast(message, 'error');
            return false;
        } else {
            const message = data.message || data.reply || 'Operation completed successfully';
            showToast(message, 'success');
            return true;
        }
    }
    
    // Enhanced Global Toast Function
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
        
        // Add trace ID if provided
        if (options.traceId && (type === 'error' || type === 'warning')) {
            toastHTML += `<div class="toast-trace">Trace ID: ${options.traceId}</div>`;
        }
        
        if (options.dismissible !== false && !options.persistent) {
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
        
        // Auto-remove (unless persistent)
        const duration = options.duration !== undefined ? options.duration : (options.persistent ? 0 : 5000);
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
    window.finbrainPWA = {
        isOnline: () => isOnline,
        isInstalled: isAppInstalled,
        triggerInstall: () => {
            if (deferredPrompt) {
                console.log('[PWA] Triggering install prompt...');
                deferredPrompt.prompt();
            } else {
                console.log('[PWA] No deferred prompt available');
                showToast('To install finbrain:\n• Chrome: Click ⋮ → "Install finbrain..."\n• Safari: Share → "Add to Home Screen"\n• Edge: Click ⋯ → "Apps" → "Install finbrain"', 'info', { duration: 8000 });
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
    
    // Expose enhanced error handling functions globally
    window.clearFieldErrors = clearFieldErrors;
    window.displayFieldErrors = displayFieldErrors;
    window.handleStandardizedResponse = handleStandardizedResponse;
    window.enhancedFormSubmit = enhancedFormSubmit;
    window.handleLegacyResponse = handleLegacyResponse;
    
    console.log('[PWA] finbrain PWA setup complete');
    
})();