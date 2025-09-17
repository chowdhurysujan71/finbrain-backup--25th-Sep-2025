// static/js/chat-handler.js
const addMsg = (role, text) => {
  const messages = document.getElementById('chat-messages');
  if (!messages) return;
  
  const d = document.createElement("div");
  d.className = role === "user" ? "msg msg-user" : "msg msg-bot";
  d.textContent = text;
  messages.appendChild(d);
  messages.scrollTop = messages.scrollHeight;
};

const renderUser = (text) => addMsg("user", text);
const renderAssistant = (data) => {
  // Handle the expected {"messages": [...]} format
  const messages = data.messages || [];
  messages.forEach(msg => {
    if (msg.content) {
      addMsg("bot", msg.content);
    }
  });
};

document.addEventListener('DOMContentLoaded', () => {
  const form = document.querySelector('#chat-form');
  const input = document.querySelector('#chat-input');
  const sendBtn = document.querySelector('#chat-send');

  async function onSubmit(e) {
    e.preventDefault();
    const text = (input.value || '').trim();
    if (!text || sendBtn.disabled) return;
    sendBtn.disabled = true;

    const rid = Math.random().toString(36).slice(2, 10); // client trace id

    try {
      // 1) auth
      const a = await fetch('/api/backend/diag/auth', { credentials:'same-origin' });
      if (!a.ok) throw new Error('Not signed in');

      // 2) chat roundtrip (SINGLE endpoint)
      const r = await fetch('/api/backend/chat', {
        method: 'POST',
        headers: { 'Content-Type':'application/json', 'X-Request-ID': rid },
        credentials: 'same-origin',
        body: JSON.stringify({ message: text })
      });
      const data = await r.json().catch(()=> ({}));
      if (!r.ok) throw new Error(`HTTP ${r.status} ${data.error||''}`);

      console.log('[TRACE]', rid, 'reply:', data);
      renderUser(text);
      renderAssistant(data);      // expects {messages:[...]} etc.
      input.value = '';
    } catch (err) {
      console.error('[TRACE] fail', err);
      alert(`Chat failed: ${err.message}`);
    } finally {
      sendBtn.disabled = false;
      input.focus();
    }
  }

  if (!window.__chatBound) {
    form.addEventListener('submit', onSubmit);
    window.__chatBound = true;
  }
});