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

    try {
      const res = await fetch('/api/backend/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ message: text })
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      renderUser(text);
      renderAssistant(data); // expects data.messages[]
      input.value = '';
    } catch (err) {
      console.error(err);
      alert(`Chat failed: ${err.message}`);
    } finally {
      sendBtn.disabled = false;
      input.focus();
    }
  }

  if (!window.__chatBound) {
    form.addEventListener('submit', onSubmit);
    window.__chatBound = true; // prevent duplicate bindings
  }
});