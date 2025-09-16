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

  // Generate consistent user ID for session
  function getUserId() {
    let userId = localStorage.getItem('chat-user-id');
    if (!userId) {
      userId = 'pwa_user_' + Date.now() + '_' + Math.random().toString(36).substring(7);
      localStorage.setItem('chat-user-id', userId);
    }
    return userId;
  }

  async function sendMessage(text) {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), 30000); // 30s hard timeout

    try {
      const res = await fetch("/ai-chat", {
        method: "POST",
        headers: { 
          "Content-Type": "application/json",
          "X-User-ID": getUserId() // Send consistent user ID
        },
        body: JSON.stringify({ text }),
        signal: ctrl.signal
      });

      if (!res.ok) {
        // Handle HTTP errors with enhanced error handling
        const errorResponse = {
          success: false,
          code: res.status >= 500 ? 'SERVER_ERROR' : 'CLIENT_ERROR',
          message: `Request failed with status ${res.status}`,
          trace_id: `chat_${Date.now()}`
        };
        
        // Use standardized error handling if available
        if (typeof window.handleStandardizedResponse === 'function') {
          window.handleStandardizedResponse(errorResponse, {
            form: form,
            onError: (error) => {
              console.error('Chat API error:', error);
            }
          });
        } else {
          // Fallback to legacy error handling
          console.error('API error:', errorResponse.message);
          if (typeof window.showToast === 'function') {
            window.showToast(errorResponse.message, 'error');
          }
        }
        
        return { error: errorResponse.message };
      }
      
      const data = await res.json();
      
      // Handle standardized responses if the backend sends them
      if (data.hasOwnProperty('success')) {
        if (typeof window.handleStandardizedResponse === 'function') {
          const success = window.handleStandardizedResponse(data, {
            form: form,
            onSuccess: (response) => {
              // Success handling is done by the toast system
              console.log('Chat message sent successfully');
            },
            onError: (response) => {
              console.error('Chat error response:', response);
            }
          });
          
          if (!success) {
            return { error: data.message || 'An error occurred' };
          }
        }
        
        // Extract reply from standardized response
        return { reply: data.reply || data.message || 'Success' };
      }
      
      // Handle legacy response format
      if (data.error) {
        if (typeof window.handleLegacyResponse === 'function') {
          window.handleLegacyResponse(data, form);
        } else if (typeof window.showToast === 'function') {
          window.showToast(data.error, 'error');
        }
        return { error: data.error };
      }
      
      return data;
    } catch (e) {
      console.error("Fetch failed:", e);
      
      // Handle network errors with enhanced error handling
      const networkError = {
        success: false,
        code: 'NETWORK_ERROR',
        message: 'Network error. Please check your connection and try again.',
        trace_id: `chat_network_${Date.now()}`
      };
      
      if (typeof window.handleStandardizedResponse === 'function') {
        window.handleStandardizedResponse(networkError, {
          form: form,
          toastOptions: { persistent: true }
        });
      } else if (typeof window.showToast === 'function') {
        window.showToast(networkError.message, 'error');
      }
      
      return { error: networkError.message };
    } finally {
      clearTimeout(t);
    }
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const text = (input.value || "").trim();
    if (!text) {
      // Clear any existing field errors for empty input
      if (typeof window.clearFieldErrors === 'function') {
        window.clearFieldErrors(form);
      }
      
      // Show validation error for empty input
      if (typeof window.displayFieldErrors === 'function') {
        window.displayFieldErrors({ 'text': 'Please enter a message' }, form);
      } else if (typeof window.showToast === 'function') {
        window.showToast('Please enter a message', 'warning');
      }
      return;
    }

    // Clear any previous field errors
    if (typeof window.clearFieldErrors === 'function') {
      window.clearFieldErrors(form);
    }

    addBubble("user", text);
    input.value = "";
    sendBtn && (sendBtn.disabled = true);

    const response = await sendMessage(text);
    
    // Handle response appropriately
    if (response.error) {
      // Error was already handled by sendMessage, just show a generic bot response
      addBubble("bot", "I'm having trouble processing your message right now. Please try again.");
    } else {
      addBubble("bot", response.reply || "(no reply)");
    }

    sendBtn && (sendBtn.disabled = false);
    input.focus();
  });
})();