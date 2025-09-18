// static/js/register.js
document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('register-form');
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
    
    // Basic client-side password confirmation
    if (form.password.value !== form.confirm.value) {
      if (err) { 
        err.textContent = 'Passwords do not match'; 
        err.style.display = 'block'; 
      }
      return;
    }

    err && (err.style.display = 'none');
    spin && (spin.style.display = 'inline-block');

    let res, data;
    try {
      res = await fetch('/auth/register', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        credentials: 'include',
        body: JSON.stringify({ 
          name: form.name.value,
          email: form.email.value, 
          password: form.password.value,
          confirm: form.confirm.value,
          captcha_answer: form.captcha.value
        })
      });
      data = await res.json().catch(() => ({}));
    } catch (e) {
      spin && (spin.style.display = 'none');
      if (err) { err.textContent = 'Network error'; err.style.display = 'block'; }
      return;
    }
    spin && (spin.style.display = 'none');

    if (!res.ok) {
      const msg = data.error || data.message || 'Account already exists';
      if (err) { err.textContent = msg; err.style.display = 'block'; }
      return;
    }

    // Clean up any old guest data from localStorage
    localStorage.removeItem('finbrain_user_id');
    localStorage.removeItem('finbrain_link_token');
    
    console.log('Registration successful - cleaned up old guest data');

    location.href = '/chat';
  });
});