(() => {
  const chatFeed = document.querySelector("[data-chat-feed]");
  if (!chatFeed) return;

  const chatList = chatFeed.querySelector("[data-chat-list]");
  const status = document.querySelector("[data-chat-status]");
  const chatForm = document.querySelector("[data-chat-form]");
  const chatInput = chatForm ? chatForm.querySelector("textarea") : null;
  const liveIndicator = document.querySelector("[data-live-status]");
  const exchangeId = chatFeed.dataset.exchangeId;

  let lastId = Number.parseInt(chatFeed.dataset.lastId || "0", 10);
  let polling = false;
  let socket = null;
  let useWebSocket = false;

  const appendMessage = (message) => {
    if (!message || (message.id && message.id <= lastId)) return;
    const empty = chatList.querySelector("[data-chat-empty]");
    if (empty) empty.remove();

    // Check if element with this messageId already in DOM
    if (message.id && chatList.querySelector(`[data-message-id="${message.id}"]`)) return;

    const item = document.createElement("li");
    item.className = `chat-message${message.is_mine ? " chat-message-mine" : ""}`;
    if (message.id) {
      item.dataset.messageId = String(message.id);
      lastId = Math.max(lastId, message.id);
      chatFeed.dataset.lastId = String(lastId);
    }

    const meta = document.createElement("div");
    meta.className = "chat-message-meta";
    const author = document.createElement("strong");
    author.textContent = message.author;
    const time = document.createElement("time");
    time.dateTime = message.created_at || new Date().toISOString();
    const date = new Date(time.dateTime);
    time.textContent = Number.isNaN(date.valueOf())
      ? "Just now"
      : new Intl.DateTimeFormat(undefined, {
          month: "short",
          day: "numeric",
          hour: "numeric",
          minute: "2-digit",
        }).format(date);
    meta.append(author, time);

    const content = document.createElement("p");
    content.textContent = message.content;
    item.append(meta, content);
    chatList.append(item);
    chatFeed.scrollTop = chatFeed.scrollHeight;
  };

  const connectWebSocket = () => {
    if (!exchangeId || !window.WebSocket) return;
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/ws/exchanges/${exchangeId}/chat/`;

    try {
      socket = new WebSocket(wsUrl);

      socket.onopen = () => {
        useWebSocket = true;
        if (liveIndicator) {
          liveIndicator.innerHTML = "<i></i> Live (real-time)";
          liveIndicator.style.color = "#28623a";
        }
      };

      socket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          appendMessage(data);
        } catch (err) {
          console.error("Error parsing WebSocket message:", err);
        }
      };

      socket.onclose = () => {
        useWebSocket = false;
        if (liveIndicator) {
          liveIndicator.innerHTML = "<i></i> Live";
        }
        // Try reconnecting after 3 seconds
        setTimeout(connectWebSocket, 3000);
      };

      socket.onerror = () => {
        useWebSocket = false;
        if (socket) socket.close();
      };
    } catch (e) {
      useWebSocket = false;
    }
  };

  // If chat form is present, intercept submit for instant WebSocket dispatch
  if (chatForm && chatInput) {
    chatForm.addEventListener("submit", (e) => {
      if (useWebSocket && socket && socket.readyState === WebSocket.OPEN) {
        e.preventDefault();
        const content = chatInput.value.trim();
        if (!content) return;
        socket.send(JSON.stringify({ content }));
        chatInput.value = "";
        chatInput.focus();
      }
    });

    // Also support Ctrl+Enter or Cmd+Enter to send
    chatInput.addEventListener("keydown", (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
        e.preventDefault();
        chatForm.dispatchEvent(new Event("submit", { cancelable: true }));
      }
    });
  }

  const pollMessages = async () => {
    // Only poll if WebSocket is not active or document just became visible
    if (polling || document.hidden || (useWebSocket && socket && socket.readyState === WebSocket.OPEN)) return;
    polling = true;
    try {
      const url = new URL(chatFeed.dataset.pollUrl, window.location.origin);
      url.searchParams.set("after", String(lastId));
      const response = await fetch(url, {
        headers: { Accept: "application/json" },
        credentials: "same-origin",
      });
      if (!response.ok) throw new Error(`Chat refresh returned ${response.status}.`);
      const payload = await response.json();
      if (!Array.isArray(payload.messages)) throw new Error("Chat refresh returned an invalid response.");
      payload.messages.forEach(appendMessage);
      status.textContent = "";
    } catch (error) {
      if (!useWebSocket) {
        status.textContent = "Updates paused. Refresh page if needed.";
      }
    } finally {
      polling = false;
    }
  };

  connectWebSocket();
  window.setInterval(pollMessages, 4000);
  document.addEventListener("visibilitychange", pollMessages);
  chatFeed.scrollTop = chatFeed.scrollHeight;
})();
