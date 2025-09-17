// static/js/chat-handler.js
(() => {
  const must = id => { const el = document.getElementById(id); if (!el) throw new Error(`#${id} missing`); return el; };
  const get  = id => document.getElementById(id);

  const form = must("chat-form");
  const input = must("chat-input");
  const messages = must("chat-messages");
  const btn = get("chat-send");
  const spin = get("chat-spinner");
  const err = get("chat-error");

  const busy = v => { if (btn) btn.disabled = v; if (spin) spin.style.display = v ? "inline-block" : "none"; };
  const showErr = m => { if (err){ err.textContent = m; err.style.display = "block"; } else console.error(m); };
  const clearErr = () => { if (err){ err.textContent = ""; err.style.display = "none"; } };

  const addMsg = (role, text) => {
    const d = document.createElement("div");
    d.className = role === "user" ? "msg msg-user" : "msg msg-bot";
    d.textContent = text;
    messages.appendChild(d);
    messages.scrollTop = messages.scrollHeight;
  };

  const j = async (url, body) => {
    const r = await fetch(url, {method:"POST", credentials:"include",
      headers:{ "Content-Type":"application/json" },
      body: JSON.stringify(body||{})});
    let data; try { data = await r.json(); } catch { throw new Error(`Bad JSON (${r.status})`); }
    if (!r.ok) throw new Error(data?.message || data?.error || `HTTP ${r.status}`);
    return data;
  };

  async function refreshRecent() {
    try {
      const res = await j("/api/backend/get_recent_expenses", { limit: 10 });
      const list = get("recent-expenses-list"); if (!list) return;
      list.innerHTML = "";
      (res.data?.expenses || []).forEach(e => {
        const li = document.createElement("div");
        li.className = "expense-row";
        li.textContent = `${(e.amount_minor/100).toFixed(2)} ${e.currency||"BDT"} • ${e.category} • ${e.description||""}`;
        list.appendChild(li);
      });
    } catch (e) {
      if (String(e.message).includes("401")) {
        // User not authenticated - redirect to login
        window.location.href = '/login?next=' + encodeURIComponent(window.location.pathname);
        return;
      }
      console.warn("recent expenses:", e.message);
    }
  }

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

  async function onSubmit(e) {
    e.preventDefault();
    const text = (input.value || '').trim();
    if (!text || btn?.disabled) return;
    if (btn) btn.disabled = true;

    try {
      // quick auth check (optional)
      const me = await fetch('/api/backend/ping', { credentials:'include' });
      if (!me.ok) throw new Error('Not signed in');

      const res = await fetch('/api/backend/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',                // <-- CRITICAL
        body: JSON.stringify({ message: text })
      });
      if (!res.ok) {
        const err = await res.json().catch(()=>({}));
        throw new Error(`HTTP ${res.status} ${err.error||''}`);
      }
      const data = await res.json();
      renderUser(text);
      renderAssistant(data);                  // expect {"messages":[...]}
      input.value = '';
    } catch (err) {
      console.error(err);
      alert(`Chat failed: ${err.message}`);
    } finally {
      if (btn) btn.disabled = false;
      input.focus();
    }
  }

  // Prevent double event bindings after re-renders
  if (!window.__chatBound) {
    form.addEventListener('submit', onSubmit);

    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); form.requestSubmit?.() || form.submit(); }
    });
    
    window.__chatBound = true;
  }

  busy(false); clearErr(); refreshRecent();
})();