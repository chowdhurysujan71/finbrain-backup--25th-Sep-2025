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

    // Handle guest data merging if guest ID exists
    const guestId = localStorage.getItem('GUEST_ID');
    if (guestId) {
      try {
        const linkRes = await fetch('/api/auth/link-guest', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          credentials: 'include',
          body: JSON.stringify({ guest_id: guestId })
        });
        
        if (linkRes.ok) {
          const linkData = await linkRes.json().catch(() => ({}));
          console.log('Guest data merged:', linkData);
          // Remove guest ID after successful linking
          localStorage.removeItem('GUEST_ID');
        } else {
          console.warn('Failed to merge guest data, but login successful');
        }
      } catch (linkError) {
        console.warn('Error merging guest data:', linkError);
      }
    }

    location.href = '/chat';
  });
});