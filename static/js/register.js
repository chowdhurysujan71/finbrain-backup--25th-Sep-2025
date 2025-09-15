// static/js/register.js
document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('register-form');
  const err  = document.getElementById('auth-error');
  const spin = document.getElementById('auth-spinner');

  form?.addEventListener('submit', async (e) => {
    e.preventDefault();
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
          confirm: form.confirm.value
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
    location.href = '/chat';
  });
});