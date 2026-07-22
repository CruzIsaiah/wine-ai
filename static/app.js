const tabs = document.querySelectorAll(".tab");
const panels = document.querySelectorAll(".finder-form");
const resultsSection = document.querySelector("#results");
const resultsGrid = document.querySelector("#results-grid");
const status = document.querySelector("#status");
let chatSessionId = null;
let currentWines = [];
let savedWines = JSON.parse(localStorage.getItem("winepair_saved_wines") || "[]");
let triedWines = JSON.parse(localStorage.getItem("winepair_tried_wines") || "[]");
const chatWineResults = new Map();

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

function saveTastingJournal() {
  localStorage.setItem("winepair_tried_wines", JSON.stringify(triedWines));
  document.querySelector("#tried-count").textContent = triedWines.length;
  renderTastingJournal();
}

function renderTastingJournal() {
  const container = document.querySelector("#tried-wines");
  if (!triedWines.length) {
    container.innerHTML = '<div class="empty-list">No tasting notes yet.<br>Add a wine after you try it.</div>';
    return;
  }
  container.innerHTML = triedWines.map((entry, index) => `
    <article class="tasting-entry">
      <h3>${escapeHtml(entry.wine_name)}</h3>
      <span class="tasting-stars">${"★".repeat(entry.rating)}${"☆".repeat(5 - entry.rating)}</span>
      <span class="tasting-date">${escapeHtml(entry.date_tried)}</span>
      ${entry.attributes?.length ? `<div class="entry-attributes">${entry.attributes.map((attribute) => `<span>${escapeHtml(attribute)}</span>`).join("")}</div>` : ""}
      ${entry.notes ? `<p>${escapeHtml(entry.notes)}</p>` : ""}
      <button class="delete-tasting" data-tasting-index="${index}" aria-label="Delete tasting note for ${escapeHtml(entry.wine_name)}">×</button>
    </article>
  `).join("");
}

function showCellarPanel(name) {
  document.querySelectorAll(".cellar-tab").forEach((tab) => tab.classList.toggle("active", tab.dataset.cellarTab === name));
  document.querySelectorAll(".cellar-panel").forEach((panel) => panel.classList.toggle("active", panel.dataset.cellarPanel === name));
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
  const formattedText = escapeHtml(text)
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\n/g, "<br>");
  message.innerHTML = role === "assistant"
    ? `<span class="chat-avatar">W</span><p>${formattedText}</p>`
    : `<p>${formattedText}</p>`;
  if (role === "assistant" && wines.length) {
    const options = document.createElement("div");
    options.className = "chat-wine-options";
    options.innerHTML = wines.map((wine) => {
      const wineId = `${Date.now()}-${Math.random()}`;
      chatWineResults.set(wineId, wine);
      const isSaved = savedWines.some((saved) => saved.Title === wine.Title);
      return `<div class="chat-wine-option"><strong>${escapeHtml(wine.Title)}</strong><span>${escapeHtml(wine.Price || "Price varies")}</span><button class="chat-save-wine ${isSaved ? "saved" : ""}" data-chat-wine-id="${wineId}">${isSaved ? "✓ Saved" : "+ Save"}</button></div>`;
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
    const form = document.querySelector("#tasting-form");
    form.elements.wine_name.value = triedButton.dataset.triedTitle;
    form.elements.source_title.value = triedButton.dataset.triedTitle;
    form.elements.date_tried.value = new Date().toISOString().slice(0, 10);
    showCellarPanel("tried");
    form.elements.rating.focus();
    return;
  }
  const button = event.target.closest(".remove-wine");
  if (!button) return;
  savedWines.splice(Number(button.dataset.savedIndex), 1);
  saveWineList();
  renderWines(currentWines, {});
});

document.querySelectorAll(".cellar-tab").forEach((tab) => {
  tab.addEventListener("click", () => showCellarPanel(tab.dataset.cellarTab));
});

document.querySelector("#tasting-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const values = Object.fromEntries(new FormData(form));
  triedWines.unshift({
    wine_name: values.wine_name.trim(),
    rating: Number(values.rating),
    date_tried: values.date_tried,
    notes: values.notes.trim(),
  });
  if (values.source_title) {
    savedWines = savedWines.filter((wine) => wine.Title !== values.source_title);
    saveWineList();
  }
  saveTastingJournal();
  form.reset();
  form.elements.date_tried.value = new Date().toISOString().slice(0, 10);
});

document.querySelector("#tried-wines").addEventListener("click", (event) => {
  const button = event.target.closest(".delete-tasting");
  if (!button) return;
  triedWines.splice(Number(button.dataset.tastingIndex), 1);
  saveTastingJournal();
});

document.querySelector("#open-wine-list").addEventListener("click", openWineList);
document.querySelector("#close-wine-list").addEventListener("click", closeWineList);
document.querySelector("#list-backdrop").addEventListener("click", closeWineList);
document.addEventListener("keydown", (event) => { if (event.key === "Escape") closeWineList(); });

saveWineList();
document.querySelector("#tasting-form").elements.date_tried.value = new Date().toISOString().slice(0, 10);
saveTastingJournal();
