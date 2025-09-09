(function () {
  const form = document.querySelector("#chat-form");
  const input = document.querySelector("#chat-input");
  const list  = document.querySelector("#chat-list");
  const sendBtn = document.querySelector("#chat-send");

  if (!form || !input || !list || !sendBtn) {
    console.error("Chat elements not found. Check IDs: #chat-form, #chat-input, #chat-list, #chat-send");
    console.error("Found:", {form: !!form, input: !!input, list: !!list, sendBtn: !!sendBtn});
    return;
  }

  function addBubble(role, text) {
    const li = document.createElement("li");
    li.className = role === "user" ? "user" : "bot";
    li.textContent = text;
    list.appendChild(li);
    list.scrollTop = list.scrollHeight;
  }

  async function sendMessage(text) {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), 30000); // 30s hard timeout

    try {
      const res = await fetch("/ai-chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" }, // keep headers simple to avoid CORS preflight
        body: JSON.stringify({ text }),
        signal: ctrl.signal,
      });

      if (!res.ok) {
        const msg = `API error ${res.status}`;
        console.error(msg);
        return { reply: msg };
      }
      return await res.json();
    } catch (e) {
      console.error("Fetch failed:", e);
      return { reply: "Network error. Please try again." };
    } finally {
      clearTimeout(t);
    }
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const text = (input.value || "").trim();
    if (!text) return;

    addBubble("user", text);
    input.value = "";
    sendBtn && (sendBtn.disabled = true);

    const { reply } = await sendMessage(text);
    addBubble("bot", reply || "(no reply)");

    sendBtn && (sendBtn.disabled = false);
    input.focus();
  });
})();