const form = document.getElementById("chatForm");
const input = document.getElementById("chatInput");
const messages = document.getElementById("chatMessages");

function addMessage(role, text) {
  const row = document.createElement("div");
  row.className = `chat-msg ${role}`;

  const bubble = document.createElement("div");

  if (role === "bot") {
    bubble.className = "bubble markdown-content";
    bubble.innerHTML = marked.parse(text);
  } else {
    bubble.className = "bubble";
    bubble.textContent = text;
  }

  row.appendChild(bubble);
  messages.appendChild(row);
  messages.scrollTop = messages.scrollHeight;
  return row;
}

function setTyping(isTyping) {
  const existing = document.getElementById("typingRow");
  if (isTyping) {
    if (existing) return;
    const row = document.createElement("div");
    row.id = "typingRow";
    row.className = "chat-msg bot";
    const bubble = document.createElement("div");
    bubble.className = "bubble";
    bubble.textContent = "Typing…";
    row.appendChild(bubble);
    messages.appendChild(row);
    messages.scrollTop = messages.scrollHeight;
  } else {
    if (existing) existing.remove();
  }
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = input.value.trim();
  if (!text) return;

  addMessage("user", text);
  input.value = "";
  setTyping(true);

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text })
    });

    const data = await res.json();
    setTyping(false);

    if (!res.ok) {
      addMessage("bot", data.error || "Something went wrong.");
      return;
    }

    addMessage("bot", data.reply || "No reply received.");
  } catch (err) {
    setTyping(false);
    addMessage("bot", "Network error. Try again.");
  }
});

// T'S AND C'S - SHOW EACH TIME THE USER IS ON THE PAGE. 
(function () {
  const overlay = document.getElementById("termsOverlay");
  const btnOk = document.getElementById("termsOk");
  const btnClose = document.getElementById("termsClose");

  if (!overlay || !btnOk || !btnClose) return;

  function closeModal() {
    overlay.classList.add("modal-hidden");
  }


  btnOk.addEventListener("click", closeModal);
  btnClose.addEventListener("click", closeModal);

  overlay.addEventListener("click", (e) => {
    if (e.target === overlay) closeModal();
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !overlay.classList.contains("modal-hidden")) {
      closeModal();
    }
  });
})();