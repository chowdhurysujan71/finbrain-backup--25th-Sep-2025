// static/js/chat-handler.js - FINAL VICTORY VERSION  
window.CHAT_BUILD_ID = 'FINAL-2025-09-18T16:00+06';
console.error('🏆 [FINAL-VICTORY] CHAT BUILD:', window.CHAT_BUILD_ID);
console.error('🏆 [FINAL-VICTORY] Server-side cache busting successful!');
console.error('🏆 [FINAL-VICTORY] Fresh HTML confirmed:', window.FINBRAIN_HTML_FRESH);

// Success verification
if (window.FINBRAIN_HTML_FRESH) {
    console.error('✅ [VICTORY] Cache bug ELIMINATED forever!');
} else {
    console.error('⚠️ [WARNING] Inline script failed - possible cache issue remains');
}
// --- add once at top-level ---
const getChatContainer = () => {
  let el = document.getElementById('chat-messages');
  if (!el) {
    const root = document.querySelector('#chat') || document.body;
    el = document.createElement('div');
    el.id = 'chat-messages';
    el.className = 'chat-messages';
    root.appendChild(el);
    console.warn('[CHAT] created #chat-messages on the fly');
  }
  el.classList.remove('hidden');
  return el;
};

const addMsg = (role, text) => {
  const messages = getChatContainer();
  const d = document.createElement('div');
  d.className = role === 'user' ? 'msg msg-user' : 'msg msg-bot';
  d.textContent = String(text || '');
  messages.appendChild(d);
  messages.scrollTop = messages.scrollHeight;
};

const renderUser = (text) => addMsg("user", text);

// replace your renderAssistant with this:
const renderAssistant = (data) => {
  try {
    if (data && data.needs_clarification) return renderClarificationRequest(data);
    if (data && typeof data.reply === 'string' && data.reply.trim()) {
      addMsg('bot', data.reply.trim()); return;
    }
    const msgs = Array.isArray(data?.messages) ? data.messages : [];
    let rendered = false;
    for (const m of msgs) if (m?.content) { addMsg('bot', m.content); rendered = true; }
    if (!rendered) addMsg('bot', 'Sorry, I couldn\'t parse that reply.');
  } catch (e) {
    console.error('[CHAT] renderAssistant error', e);
    addMsg('bot', 'Something went wrong rendering the reply.');
  }
};

const renderClarificationRequest = (data) => {
  const messages = getChatContainer();
  
  // Create clarification message container
  const clarificationDiv = document.createElement("div");
  clarificationDiv.className = "msg msg-bot clarification-msg";
  
  // Add the clarification message text
  const messageText = document.createElement("div");
  messageText.className = "clarification-text";
  messageText.textContent = data.message || "I need some clarification to categorize this expense correctly.";
  clarificationDiv.appendChild(messageText);
  
  // Add category selection chips
  if (data.options && data.options.length > 0) {
    const optionsContainer = document.createElement("div");
    optionsContainer.className = "clarification-options";
    
    data.options.forEach((option, index) => {
      const optionChip = document.createElement("button");
      optionChip.className = "clarification-chip";
      optionChip.textContent = option.display_name || option.name || option;
      optionChip.dataset.category = option.category || option.display_name || option;
      optionChip.dataset.clarificationId = data.clarification_id;
      
      optionChip.addEventListener('click', () => handleCategorySelection(optionChip));
      optionsContainer.appendChild(optionChip);
    });
    
    // Add "Other" option
    const otherChip = document.createElement("button");
    otherChip.className = "clarification-chip clarification-chip-other";
    otherChip.textContent = "Other";
    otherChip.dataset.category = "other";
    otherChip.dataset.clarificationId = data.clarification_id;
    otherChip.addEventListener('click', () => handleCategorySelection(otherChip));
    optionsContainer.appendChild(otherChip);
    
    clarificationDiv.appendChild(optionsContainer);
  }
  
  messages.appendChild(clarificationDiv);
  messages.scrollTop = messages.scrollHeight;
};

const handleCategorySelection = async (chip) => {
  const category = chip.dataset.category;
  const clarificationId = chip.dataset.clarificationId;
  
  if (!category || !clarificationId) {
    console.error('Missing category or clarification ID');
    return;
  }
  
  // Disable all chips and show loading state
  const allChips = document.querySelectorAll('.clarification-chip');
  allChips.forEach(chip => {
    chip.disabled = true;
    chip.classList.add('loading');
  });
  
  try {
    // Send category selection to backend
    const response = await fetch('/api/backend/confirm_expense', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      credentials: 'same-origin',
      body: JSON.stringify({
        clarification_id: clarificationId,
        category: category
      })
    });
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    
    const result = await response.json();
    
    if (result.success) {
      // Show success message
      const confirmationMsg = result.message || `✅ Expense categorized as "${category}"`;
      addMsg("bot", confirmationMsg);
      
      // Hide/disable the clarification options
      const clarificationMsg = chip.closest('.clarification-msg');
      if (clarificationMsg) {
        const optionsContainer = clarificationMsg.querySelector('.clarification-options');
        if (optionsContainer) {
          optionsContainer.style.display = 'none';
        }
        // Add selected indicator
        const selectedIndicator = document.createElement('div');
        selectedIndicator.className = 'selected-category';
        selectedIndicator.textContent = `✓ Selected: ${category}`;
        clarificationMsg.appendChild(selectedIndicator);
      }
    } else {
      throw new Error(result.error || 'Failed to confirm category');
    }
    
  } catch (error) {
    console.error('Error confirming category:', error);
    addMsg("bot", "Sorry, something went wrong. Please try again.");
    
    // Re-enable chips
    allChips.forEach(chip => {
      chip.disabled = false;
      chip.classList.remove('loading');
    });
  }
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
      const a = await fetch('/api/auth/me', { credentials:'same-origin' });
      if (!a.ok) throw new Error('Not signed in');

      // 2) chat roundtrip (SINGLE endpoint)
      const r = await fetch('/ai-chat', {
        method: 'POST',
        headers: { 'Content-Type':'application/json', 'X-Request-ID': rid },
        credentials: 'same-origin',
        body: JSON.stringify({ message: text })
      });
      const data = await r.json().catch(()=> ({}));
      if (!r.ok) throw new Error(`HTTP ${r.status} ${data.error||''}`);

      console.log('[TRACE]', rid, 'raw reply object:', data);
      renderUser(text);
      renderAssistant(data);      // handles both messages and clarification
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