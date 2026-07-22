const tabs = document.querySelectorAll(".tab");
const panels = document.querySelectorAll(".finder-form");
const resultsSection = document.querySelector("#results");
const resultsGrid = document.querySelector("#results-grid");
const status = document.querySelector("#status");
let chatSessionId = null;

tabs.forEach((tab) => {
  tab.addEventListener("click", () => {
    tabs.forEach((item) => {
      const active = item === tab;
      item.classList.toggle("active", active);
      item.setAttribute("aria-selected", String(active));
    });
    panels.forEach((panel) => panel.classList.toggle("active", panel.dataset.panel === tab.dataset.tab));
  });
});

document.querySelectorAll("[data-choice]").forEach((group) => {
  group.addEventListener("click", (event) => {
    const choice = event.target.closest(".choice");
    if (!choice) return;
    group.querySelectorAll(".choice").forEach((item) => item.classList.toggle("selected", item === choice));
    group.parentElement.querySelector(`input[name="${group.dataset.choice}"]`).value = choice.dataset.value;
  });
});

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>'"]/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;"
  })[character]);
}

function scoreLabel(score, bestScore) {
  if (typeof score !== "number" || bestScore <= 0) return "Great match";
  return `${Math.max(1, Math.round((score / bestScore) * 100))}% relative match`;
}

function renderWines(wines, body) {
  if (body.source === "grounded_search" && body.reference_wine) {
    const reference = body.reference_wine;
    status.innerHTML = `<p class="search-note"><strong>Found online:</strong> ${escapeHtml(reference.Title)} · ${escapeHtml(reference.Grape)} · ${escapeHtml(reference.Region || reference.Country)}. These catalog wines share its profile.</p>`;
  } else {
    status.innerHTML = "";
  }
  if (!wines.length) {
    resultsGrid.innerHTML = '<div class="empty-state"><strong>No exact matches yet.</strong><br>Try broadening the region or choosing “Surprise me.”</div>';
    return;
  }
  const bestScore = Math.max(...wines.map((wine) => Number(wine.similarity_score) || 0));
  resultsGrid.innerHTML = wines.map((wine, index) => `
    <article class="wine-card">
      <span class="card-rank">No. ${String(index + 1).padStart(2, "0")}</span>
      <div class="card-bottle" aria-hidden="true"></div>
      <h3>${escapeHtml(wine.Title || "Curated wine")}</h3>
      <p class="wine-meta">${escapeHtml(wine.Grape || "Distinctive blend")} · ${escapeHtml(wine.Style || "Classic style")}</p>
      <p class="wine-meta">${escapeHtml([wine.Region, wine.Country].filter(Boolean).join(", ") || "Selected region")}</p>
      <div class="card-bottom">
        <span class="price">${escapeHtml(wine.Price || "Price varies")}</span>
        <span class="score">${scoreLabel(wine.similarity_score, bestScore)}</span>
      </div>
    </article>
  `).join("");
}

async function requestRecommendations(path, payload) {
  resultsSection.hidden = false;
  status.innerHTML = '<div class="loading" aria-label="Finding your wines"></div><p>Exploring the cellar for your best matches…</p>';
  resultsGrid.innerHTML = "";
  resultsSection.scrollIntoView({ behavior: "smooth", block: "start" });

  try {
    const response = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const body = await response.json();
    if (!response.ok) {
      if (response.status === 429) throw new Error("The cellar is busy. Please wait a moment and try again.");
      if (response.status === 404) throw new Error("We couldn't find that bottle. Try a shorter part of its name.");
      throw new Error(typeof body.detail === "string" ? body.detail : "We couldn't complete that tasting. Please try again.");
    }
    renderWines(body.recommendations || [], body);
  } catch (error) {
    status.innerHTML = `<p>${escapeHtml(error.message)}</p>`;
  }
}

document.querySelector("#preferences-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const preferences = Object.fromEntries(new FormData(event.currentTarget));
  preferences.min_price = preferences.min_price ? Number(preferences.min_price) : null;
  preferences.max_price = preferences.max_price ? Number(preferences.max_price) : null;
  requestRecommendations("/recommend/preferences", preferences);
});

function addChatMessage(text, role) {
  const messages = document.querySelector("#chat-messages");
  const message = document.createElement("div");
  message.className = `chat-message ${role}`;
  const formattedText = escapeHtml(text)
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\n/g, "<br>");
  message.innerHTML = role === "assistant"
    ? `<span class="chat-avatar">W</span><p>${formattedText}</p>`
    : `<p>${formattedText}</p>`;
  messages.appendChild(message);
  messages.scrollTop = messages.scrollHeight;
}

async function sendChatMessage(message) {
  const trimmed = message.trim();
  if (!trimmed) return;
  addChatMessage(trimmed, "user");
  const messages = document.querySelector("#chat-messages");
  const typing = document.createElement("div");
  typing.className = "chat-typing";
  typing.textContent = "Searching the cellar…";
  messages.appendChild(typing);
  messages.scrollTop = messages.scrollHeight;
  try {
    const response = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: trimmed, session_id: chatSessionId }),
    });
    const body = await response.json();
    if (!response.ok) throw new Error(body.detail || "The sommelier is unavailable.");
    chatSessionId = body.session_id;
    typing.remove();
    addChatMessage(body.message, "assistant");
  } catch (error) {
    typing.remove();
    addChatMessage(error.message, "assistant");
  }
}

document.querySelector("#chat-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const input = document.querySelector("#chat-input");
  const message = input.value;
  input.value = "";
  sendChatMessage(message);
});

document.querySelectorAll(".chat-suggestions button").forEach((button) => {
  button.addEventListener("click", () => sendChatMessage(button.textContent));
});

document.querySelector("#start-over").addEventListener("click", () => {
  document.querySelector("#finder").scrollIntoView({ behavior: "smooth" });
});
