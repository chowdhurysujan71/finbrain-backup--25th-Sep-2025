// static/js/login.js
document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('login-form');
  const err  = document.getElementById('auth-error');
  const captchaQuestion = document.getElementById('captcha-question');
  
  // Store CAPTCHA nonce
  let captchaNonce = null;

  // Load CAPTCHA on page load
  async function loadCaptcha() {
    try {
      const res = await fetch('/api/auth/captcha');
      const data = await res.json();
      if (data.success && captchaQuestion) {
        captchaQuestion.textContent = data.question;
        captchaNonce = data.nonce; // Store the nonce
      }
    } catch (e) {
      console.error('Failed to load CAPTCHA:', e);
      if (captchaQuestion) {
        captchaQuestion.textContent = 'What is 2 + 2?';
        captchaNonce = 'fallback_nonce'; // Fallback nonce
      }
    }
  }

  loadCaptcha();

  form?.addEventListener('submit', async (e) => {
    e.preventDefault();
    err && (err.style.display = 'none');
    
    // Handle button loading state
    const loginBtn = document.getElementById('login-btn');
    const originalText = loginBtn?.textContent;
    if (loginBtn) {
      loginBtn.textContent = 'Signing in...';
      loginBtn.disabled = true;
    }

    let res, data;
    try {
      res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        credentials: 'include',
        body: JSON.stringify({ 
          email: form.email.value, 
          password: form.password.value,
          captcha_answer: form.captcha.value,
          captcha_nonce: captchaNonce
        })
      });
      data = await res.json().catch(() => ({}));
    } catch (e) {
      // Restore button state on error
      if (loginBtn) {
        loginBtn.textContent = originalText;
        loginBtn.disabled = false;
      }
      if (err) { err.textContent = 'Network error'; err.style.display = 'block'; }
      return;
    }
    
    // Restore button state
    if (loginBtn) {
      loginBtn.textContent = originalText;
      loginBtn.disabled = false;
    }

    if (!res.ok) {
      const msg = data.error || data.message || 'Invalid email or password';
      if (err) { err.textContent = msg; err.style.display = 'block'; }
      return;
    }

    // Clean up any old guest data from localStorage
    localStorage.removeItem('finbrain_user_id');
    localStorage.removeItem('finbrain_link_token');
    
    console.log('Login successful - cleaned up old guest data');

    location.href = '/chat';
  });
});