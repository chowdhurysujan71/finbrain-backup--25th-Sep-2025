// Chat Handler with Guaranteed No-Hang Promise
// Implements 25s hard timeout + visible fallback + no caching

(function() {
    'use strict';
    
    console.log('[CHAT] Initializing robust chat handler...');
    
    // Get or create user ID
    function getOrCreateUserId() {
        return window.finbrainUserId || 
               localStorage.getItem('finbrain_user_id') || 
               `anon_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    }
    
    // Send chat message with guaranteed completion
    async function sendChatMessage(messageText, outputElement) {
        if (!messageText || !messageText.trim()) return;
        
        const text = messageText.trim();
        const uid = getOrCreateUserId();
        
        // Show immediate feedback
        const bubble = document.createElement('div');
        bubble.className = 'msg bot typing';
        bubble.innerHTML = '<span class="typing-indicator"><span></span><span></span><span></span></span> thinking...';
        if (outputElement) {
            outputElement.appendChild(bubble);
            outputElement.scrollTop = outputElement.scrollHeight;
        }
        
        // Hard timeout controller - NEVER exceeds 25 seconds
        const ctrl = new AbortController();
        const timeoutId = setTimeout(() => {
            console.warn('[CHAT] Hard timeout triggered at 25s');
            ctrl.abort();
        }, 25000);
        
        try {
            console.log('[CHAT] Sending message:', text.substring(0, 50) + '...');
            
            const response = await fetch('/ai-chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-User-ID': uid
                },
                body: JSON.stringify({ message: text }),
                signal: ctrl.signal,
                cache: 'no-store',     // NEVER cache chat responses
                credentials: 'omit'    // No cookies to avoid auth confusion
            });
            
            // Handle rate limiting gracefully
            if (response.status === 429) {
                const retryAfter = parseInt(response.headers.get('Retry-After') || '15', 10);
                bubble.className = 'msg bot error';
                bubble.innerHTML = `⏱️ Too many requests — try again in ${retryAfter}s`;
                return;
            }
            
            // Handle other HTTP errors
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            // Parse JSON response
            const data = await response.json();
            
            // Display the response
            bubble.className = 'msg bot success';
            bubble.innerHTML = data?.reply || 'I received your message but couldn\\'t form a reply.';
            
            console.log('[CHAT] Response received successfully');
            
        } catch (error) {
            console.error('[CHAT] Request failed:', error);
            
            // Determine error type and show appropriate message
            bubble.className = 'msg bot error';
            
            if (error.name === 'AbortError') {
                bubble.innerHTML = '⏱️ Response taking too long — please try a shorter message';
            } else if (error.message.includes('fetch')) {
                bubble.innerHTML = '🌐 Connection issue — check your internet and try again';
            } else {
                bubble.innerHTML = '⚠️ Something went wrong — please try again in a moment';
            }
            
        } finally {
            clearTimeout(timeoutId);
            
            // Scroll to show the response
            if (outputElement) {
                outputElement.scrollTop = outputElement.scrollHeight;
            }
        }
    }
    
    // Initialize chat interface when DOM is ready
    function initializeChat() {
        // Find chat input and output elements
        const chatInput = document.querySelector('#chat-input, [data-chat-input]');
        const chatOutput = document.querySelector('#chat-output, [data-chat-output]');
        const sendButton = document.querySelector('#send-btn, [data-chat-send]');
        
        if (!chatInput) {
            console.log('[CHAT] No chat input found, skipping initialization');
            return;
        }
        
        console.log('[CHAT] Chat interface found, setting up handlers');
        
        // Send button handler
        if (sendButton) {
            sendButton.addEventListener('click', (e) => {
                e.preventDefault();
                const message = chatInput.value;
                if (message.trim()) {
                    sendChatMessage(message, chatOutput);
                    chatInput.value = '';
                }
            });
        }
        
        // Enter key handler
        chatInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                const message = chatInput.value;
                if (message.trim()) {
                    sendChatMessage(message, chatOutput);
                    chatInput.value = '';
                }
            }
        });
        
        // Form submission handler (if chat is in a form)
        const chatForm = chatInput.closest('form');
        if (chatForm) {
            chatForm.addEventListener('submit', (e) => {
                e.preventDefault();
                const message = chatInput.value;
                if (message.trim()) {
                    sendChatMessage(message, chatOutput);
                    chatInput.value = '';
                }
            });
        }
    }
    
    // Expose globally for testing and manual use
    window.sendChatMessage = sendChatMessage;
    
    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initializeChat);
    } else {
        initializeChat();
    }
    
    console.log('[CHAT] Robust chat handler ready');
    
})();