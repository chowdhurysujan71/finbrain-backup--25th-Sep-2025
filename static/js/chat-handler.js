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
      // 401 when not logged in is fine—just skip rendering
      if (!String(e.message).includes("401")) console.warn("recent expenses:", e.message);
    }
  }

  form.addEventListener("submit", async (ev) => {
    ev.preventDefault(); clearErr();
    const text = (input.value || "").trim();
    if (!text) return;
    addMsg("user", text);
    busy(true);
    try {
      const parsed = await j("/api/backend/propose_expense", { text });
      const {data: p} = parsed; // Unwrap standardized response envelope
      
      // Check if this is actually an expense (has amount and reasonable confidence)
      if (p.amount_minor && p.confidence > 0.5) {
        let saved;
        try {
          saved = await j("/api/backend/add_expense", { 
            description: text, 
            source: "chat",
            amount_minor: p.amount_minor,
            currency: p.currency || "BDT",
            category: p.category
          });
          const {data: s} = saved; // Unwrap standardized response envelope
          addMsg("bot", `Saved ${(s.amount_minor/100).toFixed(2)} BDT as ${s.category || "uncategorized"}.`);
          await refreshRecent();
        } catch (e) {
          if (String(e.message).includes("401")) {
            addMsg("bot", `Parsed ${(p.amount_minor/100).toFixed(2)} BDT as ${p.category || "uncategorized"}. Log in to save.`);
          } else {
            showErr("Couldn't save that right now. Please try again.");
            console.error(e);
          }
        }
      } else {
        // Not an expense - show a helpful response
        addMsg("bot", "I can help you log expenses like 'I spent 200 taka on groceries' or analyze your spending. What would you like to do?");
      }
    } catch (e) {
      showErr("Sorry, I couldn't parse that message.");
      console.error(e);
    } finally {
      busy(false); input.value = ""; input.focus();
    }
  });

  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); form.requestSubmit?.() || form.submit(); }
  });

  busy(false); clearErr(); refreshRecent();
})();