"""
Service Worker Diagnostics Endpoint
Provides client-side diagnostics for service worker registrations and cache states
"""
from flask import Blueprint, render_template_string

sw_diagnostics = Blueprint('sw_diagnostics', __name__)

DIAGNOSTICS_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Service Worker Diagnostics - FinBrain</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 2rem; }
        .status { padding: 1rem; margin: 1rem 0; border-radius: 8px; }
        .pass { background: #d4edda; border: 1px solid #c3e6cb; color: #155724; }
        .fail { background: #f8d7da; border: 1px solid #f5c6cb; color: #721c24; }
        .warning { background: #fff3cd; border: 1px solid #ffeaa7; color: #856404; }
        .details { margin: 1rem 0; padding: 1rem; background: #f8f9fa; border-radius: 4px; }
        pre { white-space: pre-wrap; word-break: break-all; }
        button { background: #007bff; color: white; border: none; padding: 0.5rem 1rem; border-radius: 4px; cursor: pointer; }
        button:hover { background: #0056b3; }
        .refresh-note { color: #6c757d; font-size: 0.9em; margin-top: 1rem; }
    </style>
</head>
<body>
    <h1>🔧 Service Worker Diagnostics</h1>
    <p>This page checks service worker registrations and cache states for security compliance.</p>
    
    <div id="loading" class="status warning">
        🔄 Running diagnostics...
    </div>
    
    <div id="results" style="display: none;">
        <div id="overall-status" class="status"></div>
        
        <h2>Service Worker Registrations</h2>
        <div id="sw-status" class="details"></div>
        
        <h2>Cache Storage</h2>
        <div id="cache-status" class="details"></div>
        
        <h2>Security Checks</h2>
        <div id="security-status" class="details"></div>
        
        <h2>Raw Data</h2>
        <button onclick="exportDiagnostics()">📥 Export JSON Report</button>
        <div id="raw-data" class="details" style="display: none;">
            <pre id="raw-json"></pre>
        </div>
    </div>
    
    <div class="refresh-note">
        💡 If you see multiple service workers or old caches, hard refresh (Ctrl+F5) and run diagnostics again.
    </div>

    <script>
        let diagnosticsData = {};
        
        async function runDiagnostics() {
            try {
                console.log('[Diagnostics] Starting service worker diagnostics...');
                
                // Check service worker registrations
                const registrations = await navigator.serviceWorker.getRegistrations();
                const swData = registrations.map(reg => ({
                    scriptURL: reg.scriptURL,
                    scope: reg.scope,
                    state: reg.installing ? 'installing' : 
                           reg.waiting ? 'waiting' : 
                           reg.active ? 'active' : 'unknown'
                }));
                
                // Check cache storage
                const cacheNames = await caches.keys();
                const cacheData = {};
                
                for (const cacheName of cacheNames) {
                    const cache = await caches.open(cacheName);
                    const keys = await cache.keys();
                    cacheData[cacheName] = {
                        entryCount: keys.length,
                        entries: keys.map(req => req.url).slice(0, 20) // First 20 entries
                    };
                }
                
                // Build diagnostics report
                diagnosticsData = {
                    timestamp: new Date().toISOString(),
                    serviceWorkers: swData,
                    caches: cacheData,
                    checks: {}
                };
                
                // Run security checks
                const checks = diagnosticsData.checks;
                
                // Check 1: Single SW registration ending with /sw.js
                const rootSWUrl = new URL('/sw.js', location.origin).href;
                const validSWs = swData.filter(sw => sw.scriptURL === rootSWUrl);
                checks.singleValidSW = {
                    pass: swData.length === 1 && validSWs.length === 1,
                    details: `Found ${swData.length} registrations, ${validSWs.length} valid (/sw.js)`
                };
                
                // Check 2: Only v1.1.0-auth-fix caches
                const validCachePattern = /finbrain-.*-v1\.1\.0-auth-fix$/;
                const invalidCaches = cacheNames.filter(name => !validCachePattern.test(name));
                checks.validCacheVersions = {
                    pass: invalidCaches.length === 0,
                    details: invalidCaches.length > 0 ? 
                        `Invalid caches: ${invalidCaches.join(', ')}` : 
                        `All ${cacheNames.length} caches have valid versions`
                };
                
                // Check 3: No authenticated pages in cache
                const authPaths = ['/chat', '/report', '/profile', '/challenge'];
                const cachedAuthPages = [];
                
                for (const cacheName of cacheNames) {
                    const entries = cacheData[cacheName].entries;
                    for (const entry of entries) {
                        const url = new URL(entry);
                        if (authPaths.some(path => url.pathname === path)) {
                            cachedAuthPages.push(`${url.pathname} in ${cacheName}`);
                        }
                    }
                }
                
                checks.noAuthPagesCached = {
                    pass: cachedAuthPages.length === 0,
                    details: cachedAuthPages.length > 0 ? 
                        `Cached auth pages: ${cachedAuthPages.join(', ')}` : 
                        'No authenticated pages found in cache'
                };
                
                // Check 4: No HTML entries in cache (additional safety)
                const htmlEntries = [];
                for (const cacheName of cacheNames) {
                    const cache = await caches.open(cacheName);
                    const requests = await cache.keys();
                    
                    for (const request of requests) {
                        try {
                            const response = await cache.match(request);
                            const contentType = response.headers.get('content-type') || '';
                            if (contentType.includes('text/html')) {
                                htmlEntries.push(`${request.url} in ${cacheName}`);
                            }
                        } catch (e) {
                            // Skip if can't read response
                        }
                    }
                }
                
                checks.noHTMLCached = {
                    pass: htmlEntries.length === 0,
                    details: htmlEntries.length > 0 ? 
                        `Cached HTML: ${htmlEntries.slice(0, 5).join(', ')}${htmlEntries.length > 5 ? '...' : ''}` : 
                        'No HTML found in cache'
                };
                
                // Overall pass/fail
                const allPassed = Object.values(checks).every(check => check.pass);
                
                // Update UI
                updateDiagnosticsUI(allPassed);
                
                console.log('[Diagnostics] Completed successfully:', diagnosticsData);
                
            } catch (error) {
                console.error('[Diagnostics] Failed:', error);
                document.getElementById('loading').innerHTML = '❌ Diagnostics failed: ' + error.message;
                document.getElementById('loading').className = 'status fail';
            }
        }
        
        function updateDiagnosticsUI(allPassed) {
            document.getElementById('loading').style.display = 'none';
            document.getElementById('results').style.display = 'block';
            
            const overallEl = document.getElementById('overall-status');
            overallEl.className = `status ${allPassed ? 'pass' : 'fail'}`;
            overallEl.innerHTML = allPassed ? 
                '✅ PASS - Service Worker configuration is secure' : 
                '❌ FAIL - Service Worker issues detected';
            
            // Service worker status
            const swEl = document.getElementById('sw-status');
            swEl.innerHTML = `
                <strong>Registrations:</strong> ${diagnosticsData.serviceWorkers.length}<br>
                ${diagnosticsData.serviceWorkers.map(sw => 
                    `• ${sw.scriptURL} (${sw.scope}) - ${sw.state}`
                ).join('<br>')}
            `;
            
            // Cache status  
            const cacheEl = document.getElementById('cache-status');
            const cacheNames = Object.keys(diagnosticsData.caches);
            cacheEl.innerHTML = `
                <strong>Cache Names:</strong> ${cacheNames.length}<br>
                ${cacheNames.map(name => 
                    `• ${name} (${diagnosticsData.caches[name].entryCount} entries)`
                ).join('<br>')}
            `;
            
            // Security checks
            const securityEl = document.getElementById('security-status');
            const checks = diagnosticsData.checks;
            securityEl.innerHTML = Object.entries(checks).map(([key, check]) => 
                `<div class="${check.pass ? 'pass' : 'fail'}" style="margin: 0.5rem 0; padding: 0.5rem;">
                    ${check.pass ? '✅' : '❌'} <strong>${key}:</strong> ${check.details}
                </div>`
            ).join('');
            
            // Raw data
            document.getElementById('raw-json').textContent = JSON.stringify(diagnosticsData, null, 2);
        }
        
        function exportDiagnostics() {
            const blob = new Blob([JSON.stringify(diagnosticsData, null, 2)], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `sw-diagnostics-${new Date().toISOString().slice(0, 19)}.json`;
            a.click();
            URL.revokeObjectURL(url);
        }
        
        // Toggle raw data visibility
        document.getElementById('raw-data').addEventListener('click', function() {
            const pre = document.getElementById('raw-json');
            pre.style.display = pre.style.display === 'none' ? 'block' : 'none';
        });
        
        // Run diagnostics on page load
        runDiagnostics();
    </script>
</body>
</html>
'''

@sw_diagnostics.route('/ops/sw-diagnostics')
def service_worker_diagnostics():
    """
    Service Worker diagnostics page with client-side checks
    Validates single SW registration, cache versions, and security compliance
    """
    return render_template_string(DIAGNOSTICS_TEMPLATE)