// static/js/chat-handler.js
(() => {
  const must = id => { const el = document.getElementById(id); if (!el) throw new Error(`#${id} missing`); return el; };
  const get  = id => document.getElementById(id);

  const form = must("chat-form");
  const input = must("chat-input");
  const messages = must("chat-messages");
  const sendBtn = get("chat-send");
  const spin = get("chat-spinner");
  const err = get("chat-error");

  const busy = v => { if (sendBtn) sendBtn.disabled = v; if (spin) spin.style.display = v ? "inline-block" : "none"; };
  const showErr = m => { if (err){ err.textContent = m; err.style.display = "block"; } else console.error(m); };
  const clearErr = () => { if (err){ err.textContent = ""; err.style.display = "none"; } };
  const toast = m => { if (window.showToast) window.showToast(m, 'error'); else console.error(m); };

  const addMsg = (role, text) => {
    const d = document.createElement("div");
    d.className = role === "user" ? "msg msg-user" : "msg msg-bot";
    d.textContent = text;
    messages.appendChild(d);
    messages.scrollTop = messages.scrollHeight;
  };

  // Helper functions for rendering messages
  const renderUser = (text) => addMsg("user", text);
  const renderAssistant = (data) => {
    // Handle the expected {"messages": [...]} format
    const messages = data.messages || [];
    messages.forEach(msg => {
      if (msg.type === "text" && msg.content) {
        addMsg("bot", msg.content);
      }
    });
  };
  
  const renderRecent = (recentData) => {
    const list = get("recent-expenses-list"); 
    if (!list) return;
    list.innerHTML = "";
    (recentData || []).forEach(e => {
      const li = document.createElement("div");
      li.className = "expense-row";
      li.textContent = `${(e.amount_minor/100).toFixed(2)} ${e.currency||"BDT"} • ${e.category} • ${e.description||""}`;
      list.appendChild(li);
    });
  };

  // Unified submit handler - only calls chat endpoint
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const text = (input.value || '').trim();
    if (!text || sendBtn?.disabled) return;
    if (sendBtn) sendBtn.disabled = true;

    try {
      const res = await fetch('/api/backend/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ message: text })
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();          // unified reply
      renderUser(text);
      renderAssistant(data);                   // expects data.messages[]
      if (data.recent) renderRecent(data.recent);
    } catch (err) {
      toast(`Chat failed: ${err.message}`);
    } finally {
      if (sendBtn) sendBtn.disabled = false;
      input.value = '';
      input.focus();
    }
  });

  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { 
      e.preventDefault(); 
      form.requestSubmit?.() || form.submit(); 
    }
  });

  busy(false); clearErr();
})();