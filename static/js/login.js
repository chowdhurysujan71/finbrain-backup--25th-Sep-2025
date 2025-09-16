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
    const guestId = localStorage.getItem('finbrain_user_id');
    const linkToken = localStorage.getItem('finbrain_link_token');
    if (guestId) {
      try {
        // Prepare request payload with both guest_id and link_token for security
        const linkPayload = { guest_id: guestId };
        if (linkToken) {
          linkPayload.link_token = linkToken;
        }
        
        const linkRes = await fetch('/api/auth/link-guest', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          credentials: 'include',
          body: JSON.stringify(linkPayload)
        });
        
        if (linkRes.ok) {
          const linkData = await linkRes.json().catch(() => ({}));
          console.log('Guest data merged:', linkData);
          // Remove both guest ID and link token after successful linking
          localStorage.removeItem('finbrain_user_id');
          localStorage.removeItem('finbrain_link_token');
        } else {
          const errorData = await linkRes.json().catch(() => ({}));
          if (linkRes.status === 401) {
            console.warn('Guest data merge failed due to expired or invalid token. Continuing with login.');
          } else {
            console.warn('Failed to merge guest data, but login successful:', errorData.error || 'Unknown error');
          }
        }
      } catch (linkError) {
        console.warn('Error merging guest data:', linkError);
      }
    }

    location.href = '/chat';
  });
});