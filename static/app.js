const tabs = document.querySelectorAll(".tab");
const panels = document.querySelectorAll(".finder-form");
const resultsSection = document.querySelector("#results");
const resultsGrid = document.querySelector("#results-grid");
const status = document.querySelector("#status");
let chatSessionId = null;
let currentWines = [];
let savedWines = JSON.parse(localStorage.getItem("winepair_saved_wines") || "[]");
const chatWineResults = new Map();
let detailsWine = null;

function updateHeaderAppearance() {
  document.querySelector(".site-header").classList.toggle("scrolled", window.scrollY > 24);
}

window.addEventListener("scroll", updateHeaderAppearance, { passive: true });
updateHeaderAppearance();

const chatPanel = document.querySelector("#chat-panel");
const siteHeader = document.querySelector(".site-header");
let chatIsActive = false;
let headerHideTimer;

function revealHeaderDuringChat() {
  if (!chatIsActive) return;
  siteHeader.classList.remove("interaction-hidden");
  window.clearTimeout(headerHideTimer);
  headerHideTimer = window.setTimeout(() => {
    if (chatIsActive) siteHeader.classList.add("interaction-hidden");
  }, 2200);
}

chatPanel.addEventListener("focusin", () => {
  chatIsActive = true;
  siteHeader.classList.add("interaction-hidden");
});
chatPanel.addEventListener("focusout", () => {
  window.setTimeout(() => {
    if (!chatPanel.contains(document.activeElement)) {
      chatIsActive = false;
      window.clearTimeout(headerHideTimer);
      siteHeader.classList.remove("interaction-hidden");
    }
  }, 0);
});
window.addEventListener("pointermove", revealHeaderDuringChat, { passive: true });
window.addEventListener("touchstart", revealHeaderDuringChat, { passive: true });

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

function renderMarkdown(value) {
  const inline = (text) => escapeHtml(text)
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/(^|[^*])\*([^*]+?)\*/g, "$1<em>$2</em>");
  const lines = String(value ?? "").split(/\r?\n/);
  const output = [];
  let listItems = [];
  const closeList = () => {
    if (!listItems.length) return;
    output.push(`<ul>${listItems.map((item) => `<li>${inline(item)}</li>`).join("")}</ul>`);
    listItems = [];
  };

  lines.forEach((line) => {
    const trimmed = line.trim();
    const listMatch = trimmed.match(/^[-*]\s+(.+)/);
    if (listMatch) {
      listItems.push(listMatch[1]);
      return;
    }
    closeList();
    if (!trimmed) return;
    if (/^---+$/.test(trimmed)) output.push("<hr>");
    else if (/^###\s+/.test(trimmed)) output.push(`<h4>${inline(trimmed.replace(/^###\s+/, ""))}</h4>`);
    else if (/^##\s+/.test(trimmed)) output.push(`<h3>${inline(trimmed.replace(/^##\s+/, ""))}</h3>`);
    else if (/^#\s+/.test(trimmed)) output.push(`<h2>${inline(trimmed.replace(/^#\s+/, ""))}</h2>`);
    else output.push(`<p>${inline(trimmed)}</p>`);
  });
  closeList();
  return output.join("");
}

function scoreLabel(score, bestScore) {
  if (typeof score !== "number" || bestScore <= 0) return "Great match";
  return `${Math.max(1, Math.round((score / bestScore) * 100))}% relative match`;
}

function renderWines(wines, body) {
  currentWines = wines;
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
      <button class="ask-wine" data-wine-index="${index}">Ask about this wine</button>
      <button class="save-wine ${savedWines.some((saved) => saved.Title === wine.Title) ? "saved" : ""}" data-wine-index="${index}">${savedWines.some((saved) => saved.Title === wine.Title) ? "✓ Saved to my list" : "+ Add to my list"}</button>
    </article>
  `).join("");
}

function saveWineList() {
  localStorage.setItem("winepair_saved_wines", JSON.stringify(savedWines));
  document.querySelector("#wine-list-count").textContent = savedWines.length;
  document.querySelector("#saved-count").textContent = savedWines.length;
  renderSavedWines();
}

function renderSavedWines() {
  const container = document.querySelector("#saved-wines");
  if (!savedWines.length) {
    container.innerHTML = '<div class="empty-list">Your list is waiting for its first bottle.<br>Save any recommendation to add it here.</div>';
    return;
  }
  container.innerHTML = savedWines.map((wine, index) => `
    <article class="saved-wine">
      <h3>${escapeHtml(wine.Title)}</h3>
      <p>${escapeHtml(wine.Grape || "Distinctive blend")} · ${escapeHtml([wine.Region, wine.Country].filter(Boolean).join(", "))}</p>
      <strong>${escapeHtml(wine.Price || "Price varies")}</strong>
      <button class="tried-wine-action" data-tried-title="${escapeHtml(wine.Title)}">I tried this →</button>
      <button class="remove-wine" data-saved-index="${index}" aria-label="Remove ${escapeHtml(wine.Title)}">×</button>
    </article>
  `).join("");
}

function openWineList() {
  document.querySelector("#wine-list-drawer").classList.add("open");
  document.querySelector("#wine-list-drawer").setAttribute("aria-hidden", "false");
  document.querySelector("#list-backdrop").hidden = false;
}

function closeWineList() {
  document.querySelector("#wine-list-drawer").classList.remove("open");
  document.querySelector("#wine-list-drawer").setAttribute("aria-hidden", "true");
  document.querySelector("#list-backdrop").hidden = true;
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

function getPreferencePayload() {
  const preferences = Object.fromEntries(
    new FormData(document.querySelector("#preferences-form"))
  );
  preferences.min_price = preferences.min_price ? Number(preferences.min_price) : null;
  preferences.max_price = preferences.max_price ? Number(preferences.max_price) : null;
  return preferences;
}

document.querySelector("#preferences-form").addEventListener("submit", (event) => {
  event.preventDefault();
  requestRecommendations("/recommend/preferences", getPreferencePayload());
});

document.querySelector('#preferences-form select[name="currency"]').addEventListener("change", () => {
  if (currentWines.length) {
    requestRecommendations("/recommend/preferences", getPreferencePayload());
  }
});

function addChatMessage(text, role, wines = []) {
  const messages = document.querySelector("#chat-messages");
  const message = document.createElement("div");
  message.className = `chat-message ${role}`;
  message.innerHTML = role === "assistant"
    ? `<span class="chat-avatar">W</span><div class="chat-bubble">${renderMarkdown(text)}</div>`
    : `<div class="chat-bubble"><p>${escapeHtml(text)}</p></div>`;
  if (role === "assistant" && wines.length) {
    const options = document.createElement("div");
    options.className = "chat-wine-options";
    options.innerHTML = wines.map((wine) => {
      const wineId = `${Date.now()}-${Math.random()}`;
      chatWineResults.set(wineId, wine);
      const isSaved = savedWines.some((saved) => saved.Title === wine.Title);
      return `<div class="chat-wine-option"><strong>${escapeHtml(wine.Title)}</strong><span>${escapeHtml(wine.Price || "Price varies")}</span><div class="chat-wine-actions"><button class="chat-ask-wine" data-chat-wine-id="${wineId}">Ask</button><button class="chat-save-wine ${isSaved ? "saved" : ""}" data-chat-wine-id="${wineId}">${isSaved ? "✓ Saved" : "+ Save"}</button></div></div>`;
    }).join("");
    message.appendChild(options);
  }
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
    addChatMessage(body.message, "assistant", body.recommendations || []);
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

document.querySelector("#chat-messages").addEventListener("click", (event) => {
  const askButton = event.target.closest(".chat-ask-wine");
  if (askButton) {
    const wine = chatWineResults.get(askButton.dataset.chatWineId);
    if (wine) openWineDetails(wine);
    return;
  }
  const button = event.target.closest(".chat-save-wine");
  if (!button) return;
  const wine = chatWineResults.get(button.dataset.chatWineId);
  if (!wine) return;
  const existingIndex = savedWines.findIndex((saved) => saved.Title === wine.Title);
  if (existingIndex >= 0) savedWines.splice(existingIndex, 1);
  else savedWines.push(wine);
  saveWineList();
  button.classList.toggle("saved", existingIndex < 0);
  button.textContent = existingIndex < 0 ? "✓ Saved" : "+ Save";
});

document.querySelector("#start-over").addEventListener("click", () => {
  document.querySelector("#finder").scrollIntoView({ behavior: "smooth" });
});

document.querySelector("#results-grid").addEventListener("click", (event) => {
  const askButton = event.target.closest(".ask-wine");
  if (askButton) {
    const wine = currentWines[Number(askButton.dataset.wineIndex)];
    if (wine) openWineDetails(wine);
    return;
  }
  const button = event.target.closest(".save-wine");
  if (!button) return;
  const wine = currentWines[Number(button.dataset.wineIndex)];
  if (!wine) return;
  const existingIndex = savedWines.findIndex((saved) => saved.Title === wine.Title);
  if (existingIndex >= 0) savedWines.splice(existingIndex, 1);
  else savedWines.push(wine);
  saveWineList();
  button.classList.toggle("saved", existingIndex < 0);
  button.textContent = existingIndex < 0 ? "✓ Saved to my list" : "+ Add to my list";
});

document.querySelector("#saved-wines").addEventListener("click", (event) => {
  const triedButton = event.target.closest(".tried-wine-action");
  if (triedButton) {
    window.location.href = `/journal?wine=${encodeURIComponent(triedButton.dataset.triedTitle)}`;
    return;
  }
  const button = event.target.closest(".remove-wine");
  if (!button) return;
  savedWines.splice(Number(button.dataset.savedIndex), 1);
  saveWineList();
  renderWines(currentWines, {});
});

document.querySelector("#open-wine-list").addEventListener("click", openWineList);
document.querySelector("#close-wine-list").addEventListener("click", closeWineList);
document.querySelector("#list-backdrop").addEventListener("click", closeWineList);
document.addEventListener("keydown", (event) => { if (event.key === "Escape") { closeWineList(); closeWineDetails(); } });

function openWineDetails(wine) {
  detailsWine = wine;
  document.querySelector("#wine-detail-title").textContent = wine.Title;
  document.querySelector("#wine-detail-meta").textContent = [wine.Grape, wine.Style, wine.Region || wine.Country].filter(Boolean).join(" · ");
  document.querySelector("#detail-conversation").innerHTML = '<div class="detail-message"><p>What would you like to know about this wine? I can explain its flavor, grape, pairing, serving style, or catalog details.</p></div>';
  document.querySelector("#wine-detail-panel").classList.add("open");
  document.querySelector("#wine-detail-panel").setAttribute("aria-hidden", "false");
  document.querySelector("#wine-detail-backdrop").hidden = false;
}

function closeWineDetails() {
  document.querySelector("#wine-detail-panel").classList.remove("open");
  document.querySelector("#wine-detail-panel").setAttribute("aria-hidden", "true");
  document.querySelector("#wine-detail-backdrop").hidden = true;
}

function addDetailMessage(text, role="assistant") {
  const conversation = document.querySelector("#detail-conversation");
  const message = document.createElement("div");
  message.className = `detail-message ${role}`;
  message.innerHTML = `<div class="detail-bubble">${role === "assistant" ? renderMarkdown(text) : `<p>${escapeHtml(text)}</p>`}</div>`;
  conversation.appendChild(message);
  conversation.scrollTop = conversation.scrollHeight;
}

async function askWineQuestion(question) {
  if (!detailsWine || !question.trim()) return;
  addDetailMessage(question.trim(), "user");
  const conversation = document.querySelector("#detail-conversation");
  const thinking = document.createElement("div");
  thinking.className = "detail-thinking";
  thinking.textContent = "Sommelier is thinking…";
  conversation.appendChild(thinking);
  try {
    const response = await fetch("/wine-details", {
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body:JSON.stringify({wine:detailsWine,question:question.trim()}),
    });
    const body = await response.json();
    thinking.remove();
    if (!response.ok) throw new Error(body.detail || "I couldn't answer that right now.");
    addDetailMessage(body.answer);
  } catch (error) {
    thinking.remove();
    addDetailMessage(error.message);
  }
}

document.querySelector("#wine-detail-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const input = document.querySelector("#wine-detail-question");
  const question = input.value;
  input.value = "";
  askWineQuestion(question);
});
document.querySelectorAll(".detail-suggestions button").forEach((button) => button.addEventListener("click", () => askWineQuestion(button.textContent)));
document.querySelector("#close-wine-details").addEventListener("click", closeWineDetails);
document.querySelector("#wine-detail-backdrop").addEventListener("click", closeWineDetails);

saveWineList();
