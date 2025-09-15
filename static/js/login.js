// static/js/login.js
document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('login-form');
  const err  = document.getElementById('auth-error');
  const spin = document.getElementById('auth-spinner');

  form?.addEventListener('submit', async (e) => {
    e.preventDefault();
    err && (err.style.display = 'none');
    spin && (spin.style.display = 'inline-block');

    let res, data;
    try {
      res = await fetch('/auth/login', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        credentials: 'include',
        body: JSON.stringify({ email: form.email.value, password: form.password.value })
      });
      data = await res.json().catch(() => ({}));
    } catch (e) {
      spin && (spin.style.display = 'none');
      if (err) { err.textContent = 'Network error'; err.style.display = 'block'; }
      return;
    }
    spin && (spin.style.display = 'none');

    if (!res.ok) {
      const msg = data.error || data.message || 'Invalid email or password';
      if (err) { err.textContent = msg; err.style.display = 'block'; }
      return;
    }
    location.href = '/chat';
  });
});