// static/js/login.js
document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('login-form');
  const err  = document.getElementById('auth-error');
  const spin = document.getElementById('auth-spinner');
  const captchaQuestion = document.getElementById('captcha-question');

  // Load CAPTCHA on page load
  async function loadCaptcha() {
    try {
      const res = await fetch('/api/auth/captcha');
      const data = await res.json();
      if (data.success && captchaQuestion) {
        captchaQuestion.textContent = data.question;
      }
    } catch (e) {
      console.error('Failed to load CAPTCHA:', e);
      if (captchaQuestion) {
        captchaQuestion.textContent = 'What is 2 + 2?';
      }
    }
  }

  loadCaptcha();

  form?.addEventListener('submit', async (e) => {
    e.preventDefault();
    console.log('LOGIN FORM SUBMIT TRIGGERED'); // DEBUG
    err && (err.style.display = 'none');
    
    // Handle button loading state
    const loginBtn = document.getElementById('login-btn');
    const btnText = loginBtn?.querySelector('.btn-text');
    const btnLoading = loginBtn?.querySelector('.btn-loading');
    if (btnText) btnText.style.display = 'none';
    if (btnLoading) btnLoading.style.display = 'inline';
    if (loginBtn) loginBtn.disabled = true;

    let res, data;
    try {
      res = await fetch('/auth/login', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        credentials: 'include',
        body: JSON.stringify({ 
          email: form.email.value, 
          password: form.password.value,
          captcha_answer: form.captcha.value
        })
      });
      data = await res.json().catch(() => ({}));
    } catch (e) {
      // Restore button state on error
      if (btnText) btnText.style.display = 'inline';
      if (btnLoading) btnLoading.style.display = 'none';
      if (loginBtn) loginBtn.disabled = false;
      if (err) { err.textContent = 'Network error'; err.style.display = 'block'; }
      return;
    }
    
    // Restore button state
    if (btnText) btnText.style.display = 'inline';
    if (btnLoading) btnLoading.style.display = 'none';
    if (loginBtn) loginBtn.disabled = false;

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