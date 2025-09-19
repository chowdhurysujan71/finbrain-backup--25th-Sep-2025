// static/js/chat-handler.js
const addMsg = (role, text) => {
  const messages = document.getElementById('chat-messages');
  if (!messages) return;
  
  const messageDiv = document.createElement("div");
  messageDiv.className = role === "user" ? "message user-message" : "message ai-message";
  
  // Create avatar
  const avatar = document.createElement("div");
  avatar.className = "message-avatar";
  avatar.textContent = role === "user" ? "👤" : "🤖";
  
  // Create content with XSS protection
  const content = document.createElement("div");
  content.className = "message-content";
  const paragraph = document.createElement("p");
  paragraph.textContent = text; // textContent prevents XSS
  content.appendChild(paragraph);
  
  messageDiv.appendChild(avatar);
  messageDiv.appendChild(content);
  messages.appendChild(messageDiv);
  messages.scrollTop = messages.scrollHeight;
};

const renderUser = (text) => addMsg("user", text);
const renderAssistant = (data) => {
  // Handle clarification responses
  if (data.needs_clarification) {
    renderClarificationRequest(data);
    return;
  }
  
  // Handle the actual backend response format: {"reply": "text", ...}
  if (data.reply) {
    addMsg("bot", data.reply);
    return;
  }
  
  // Handle the expected {"messages": [...]} format (fallback)
  const messages = data.messages || [];
  messages.forEach(msg => {
    if (msg.content) {
      addMsg("bot", msg.content);
    }
  });
};

const renderClarificationRequest = (data) => {
  const messages = document.getElementById('chat-messages');
  if (!messages) return;
  
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

const handleCategorySelection = async (chipElement) => {
  const category = chipElement.dataset.category;
  const clarificationId = chipElement.dataset.clarificationId;
  
  if (!category || !clarificationId) {
    console.error('Missing category or clarification ID');
    return;
  }
  
  // Disable all chips to prevent double-clicking
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
        'Content-Type': 'application/json'
      },
      credentials: 'same-origin',
      body: JSON.stringify({
        clarification_id: clarificationId,
        selected_category: category
      })
    });
    
    const result = await response.json();
    
    if (response.ok && result.success) {
      // Show success message
      addMsg("bot", result.message || `Great! I've categorized it as ${category}.`);
      
      // Hide the clarification options
      const clarificationMsg = chipElement.closest('.clarification-msg');
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

      console.log('[TRACE]', rid, 'reply:', data);
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