(() => {
  // ---------- tiny helpers ----------
  const mustGet = (id) => {
    const el = document.getElementById(id);
    if (!el) throw new Error(`Missing DOM element: #${id}`);
    return el;
  };
  const softGet = (id) => document.getElementById(id) || null;
  const safeText = (v) => (typeof v === "string" ? v : JSON.stringify(v ?? ""));
  const sleep = (ms) => new Promise(r => setTimeout(r, ms));

  // ---------- cache DOM (throws if core nodes are missing) ----------
  const form = mustGet("chat-form");
  const input = mustGet("chat-input");
  const messages = mustGet("chat-messages");

  // optional nodes (null-safe)
  const sendBtn = softGet("chat-send");
  const spinner = softGet("chat-spinner");
  const errorBox = softGet("chat-error");

  // ---------- config ----------
  const ENDPOINTS = {
    propose: "/api/backend/propose_expense",   // public (parse only)
    add:     "/api/backend/add_expense",       // session write
  };

  // ---------- UI helpers ----------
  const setBusy = (busy) => {
    if (sendBtn) sendBtn.disabled = busy;
    if (spinner) spinner.style.display = busy ? "inline-block" : "none";
  };

  const showError = (msg) => {
    if (errorBox) {
      errorBox.textContent = msg;
      errorBox.style.display = "block";
    } else {
      console.error("[chat] ", msg);
    }
  };

  const clearError = () => {
    if (errorBox) {
      errorBox.textContent = "";
      errorBox.style.display = "none";
    }
  };

  const appendMsg = (role, text) => {
    const item = document.createElement("div");
    item.className = role === "user" ? "msg msg-user" : "msg msg-bot";
    item.textContent = text;
    messages.appendChild(item);
    messages.scrollTop = messages.scrollHeight;
  };

  // ---------- safe fetch wrapper ----------
  const safeFetchJSON = async (url, options) => {
    const res = await fetch(url, {
      credentials: "include",           // IMPORTANT for session auth
      headers: { "Content-Type": "application/json" },
      ...options,
    });
    // Try to parse JSON; if it fails, surface a readable error
    let data = null;
    try {
      data = await res.json();
    } catch (e) {
      const text = await res.text().catch(() => "");
      throw new Error(`Bad JSON from ${url} (status ${res.status}) ${text?.slice(0, 200)}`);
    }
    if (!res.ok) {
      // server provided JSON error; extract common fields
      const msg = data?.message || data?.error || `HTTP ${res.status}`;
      const trace = data?.trace_id ? ` (trace: ${data.trace_id})` : "";
      throw new Error(`${msg}${trace}`);
    }
    return data;
  };

  // ---------- main submit handler ----------
  form.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    clearError();

    const text = (input.value || "").trim();
    if (!text) return;

    // Display user message immediately
    appendMsg("user", text);

    setBusy(true);
    try {
      // 1) propose parse (public, no write)
      const parsed = await safeFetchJSON(ENDPOINTS.propose, {
        method: "POST",
        body: JSON.stringify({ text }),
      });

      // Parsed result (defensive defaults)
      const amountMinor = Number(parsed?.amount_minor ?? 0);
      const category = (parsed?.category || "uncategorized").toString();
      const confidence = Number(parsed?.confidence ?? 0);

      // 2) if we have a session, try to write via add_expense
      // (If not logged in, backend will 401; we handle that gracefully)
      let added = null;
      try {
        added = await safeFetchJSON(ENDPOINTS.add, {
          method: "POST",
          body: JSON.stringify({
            description: text,   // keep the raw user text as description
            source: "chat",      // frozen contract: 'chat'|'form'|'messenger'
          }),
        });
      } catch (e) {
        // If unauthorized, just show the parse result and prompt login
        if (String(e.message).includes("401") || String(e.message).toLowerCase().includes("unauthorized")) {
          appendMsg(
            "bot",
            `I parsed **${amountMinor/100}** BDT as *${category}* (confidence ${Math.round(confidence*100)}%). ` +
            `Log in to save this expense and see it in your totals.`
          );
          throw e; // still surface to console for devs
        }
        // Other errors bubble up after showing a friendly message
        showError("Sorry, I couldn't save that just now. Please try again.");
        throw e;
      }

      // 3) success path: reflect write + idempotency status
      const status = (added?.status || "created").toString();
      const savedMinor = Number(added?.amount_minor ?? amountMinor);
      appendMsg(
        "bot",
        status === "idempotent_replay"
          ? `Already saved: **${savedMinor/100}** BDT as *${category}* (idempotent).`
          : `Saved **${savedMinor/100}** BDT as *${category}*.`
      );
    } catch (err) {
      // Friendly UI message already shown for common cases;
      // ensure console visibility for debugging
      console.error("[chat] submit error:", err);
    } finally {
      setBusy(false);
      input.value = "";
      await sleep(10);
      input.focus();
    }
  });

  // Optional: enter-to-send without breaking IME
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      form.requestSubmit?.() || form.submit();
    }
  });

  // Initial state
  setBusy(false);
  clearError();
})();