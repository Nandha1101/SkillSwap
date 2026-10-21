(() => {
  const chatFeed = document.querySelector("[data-chat-feed]");
  if (chatFeed) {
    const chatList = chatFeed.querySelector("[data-chat-list]");
    const status = document.querySelector("[data-chat-status]");
    let lastId = Number.parseInt(chatFeed.dataset.lastId || "0", 10);
    let polling = false;

    const appendMessage = (message) => {
      if (!Number.isSafeInteger(message.id) || message.id <= lastId) return;
      const empty = chatList.querySelector("[data-chat-empty]");
      if (empty) empty.remove();

      const item = document.createElement("li");
      item.className = `chat-message${message.is_mine ? " chat-message-mine" : ""}`;
      item.dataset.messageId = String(message.id);

      const meta = document.createElement("div");
      meta.className = "chat-message-meta";
      const author = document.createElement("strong");
      author.textContent = message.author;
      const time = document.createElement("time");
      time.dateTime = message.created_at;
      const date = new Date(message.created_at);
      time.textContent = Number.isNaN(date.valueOf())
        ? ""
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
      lastId = message.id;
      chatFeed.dataset.lastId = String(lastId);
      chatFeed.scrollTop = chatFeed.scrollHeight;
    };

    const pollMessages = async () => {
      if (polling || document.hidden) return;
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
        status.textContent = "Chat updates paused. Refresh this page to try again.";
        console.error("Exchange chat refresh failed:", error);
      } finally {
        polling = false;
      }
    };

    window.setInterval(pollMessages, 5000);
    document.addEventListener("visibilitychange", pollMessages);
    chatFeed.scrollTop = chatFeed.scrollHeight;
  }

  const joinButton = document.querySelector("[data-video-join]");
  if (!joinButton) return;

  const status = document.querySelector("[data-video-status]");
  const roomContainer = document.querySelector("[data-video-container]");
  let api;

  const startCall = () => {
    if (api) return;
    const { domain, room, displayName } = joinButton.dataset;
    if (!domain || !room || !window.JitsiMeetExternalAPI) {
      throw new Error("The video service did not load. Check your connection and try again.");
    }
    api = new window.JitsiMeetExternalAPI(domain, {
      roomName: room,
      parentNode: roomContainer,
      width: "100%",
      height: "100%",
      userInfo: { displayName },
      configOverwrite: {
        startWithAudioMuted: true,
        startWithVideoMuted: true,
        prejoinPageEnabled: true,
        disableDeepLinking: true,
      },
    });
    api.addEventListener("readyToClose", () => {
      api = null;
      roomContainer.replaceChildren();
      joinButton.disabled = false;
      status.textContent = "You left the video room.";
    });
    joinButton.disabled = true;
    status.textContent = "Video room loaded. Review your camera and microphone before joining.";
  };

  joinButton.addEventListener("click", () => {
    joinButton.disabled = true;
    status.textContent = "Connecting to Jitsi Meet…";
    if (window.JitsiMeetExternalAPI) {
      try {
        startCall();
      } catch (error) {
        joinButton.disabled = false;
        status.textContent = error.message;
      }
      return;
    }

    const script = document.createElement("script");
    script.src = `https://${joinButton.dataset.domain}/external_api.js`;
    script.async = true;
    script.onload = () => {
      try {
        startCall();
      } catch (error) {
        joinButton.disabled = false;
        status.textContent = error.message;
      }
    };
    script.onerror = () => {
      joinButton.disabled = false;
      status.textContent = "Could not connect to the video service. Please try again.";
    };
    document.head.append(script);
  });
})();
