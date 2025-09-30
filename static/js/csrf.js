// CSRF Token Management Utility
// Automatically fetches and manages CSRF tokens for all POST requests

class CSRFManager {
  constructor() {
    this.token = null;
    this.fetchPromise = null;
  }

  async getToken() {
    // If token already exists and is valid, return it
    if (this.token) {
      return this.token;
    }

    // If already fetching, wait for that fetch to complete
    if (this.fetchPromise) {
      return this.fetchPromise;
    }

    // Start fetching token
    this.fetchPromise = this.fetchTokenFromServer();
    
    try {
      this.token = await this.fetchPromise;
      return this.token;
    } finally {
      this.fetchPromise = null;
    }
  }

  async fetchTokenFromServer() {
    try {
      // Try to get from meta tag first (if rendered in HTML)
      const metaTag = document.querySelector('meta[name="csrf-token"]');
      if (metaTag && metaTag.content) {
        return metaTag.content;
      }

      // Otherwise fetch from API endpoint
      const response = await fetch('/api/auth/csrf-token', {
        method: 'GET',
        credentials: 'same-origin'
      });

      if (!response.ok) {
        throw new Error(`Failed to fetch CSRF token: ${response.status}`);
      }

      const data = await response.json();
      return data.csrf_token;
    } catch (error) {
      console.error('CSRF token fetch error:', error);
      // Return null and let the request fail with proper 403
      return null;
    }
  }

  invalidateToken() {
    this.token = null;
  }

  async wrapFetch(url, options = {}) {
    // Only add CSRF token for state-changing methods
    const method = (options.method || 'GET').toUpperCase();
    if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(method)) {
      const token = await this.getToken();
      
      if (!token) {
        console.warn('CSRF token not available, request may fail');
      }

      // Add CSRF token to headers
      options.headers = options.headers || {};
      if (typeof options.headers === 'object' && !Array.isArray(options.headers)) {
        options.headers['X-CSRFToken'] = token;
      }
    }

    return fetch(url, options);
  }
}

// Create global CSRF manager instance
window.csrfManager = new CSRFManager();

// Provide a global fetch wrapper that automatically includes CSRF tokens
window.csrfFetch = (url, options) => window.csrfManager.wrapFetch(url, options);
