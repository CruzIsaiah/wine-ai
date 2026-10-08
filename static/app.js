const resultsSection = document.querySelector("#results");
const resultsGrid = document.querySelector("#results-grid");
const status = document.querySelector("#status");
let chatSessionId = null;
let currentWines = [];
let visibleWineTitles = [];
let savedWines = JSON.parse(localStorage.getItem("winepair_saved_wines") || "[]");
const chatWineResults = new Map();
let detailsWine = null;
const DEFAULT_API_TOKEN = "winepair-demo-token-2026";

function getApiToken() {
  const storedToken = localStorage.getItem("winepair_api_token");
  if (storedToken) return storedToken;
  const token = DEFAULT_API_TOKEN;
  localStorage.setItem("winepair_api_token", token);
  return token;
}

getApiToken();
document.querySelectorAll(".choice").forEach((choice) => choice.setAttribute("aria-pressed", String(choice.classList.contains("selected"))));

function updateHeaderAppearance() {
  document.querySelector(".site-header").classList.toggle("scrolled", window.scrollY > 24);
}

window.addEventListener("scroll", updateHeaderAppearance, { passive: true });
updateHeaderAppearance();

document.querySelectorAll("[data-choice]").forEach((group) => {
  group.addEventListener("click", (event) => {
    const choice = event.target.closest(".choice");
    if (!choice) return;
    group.querySelectorAll(".choice").forEach((item) => {
      item.classList.toggle("selected", item === choice);
      item.setAttribute("aria-pressed", String(item === choice));
    });
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
  visibleWineTitles = wines.map((wine) => wine.Title);
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
  renderWineListState();
}

function renderWineListState() {
  document.querySelector("#wine-list-count").textContent = savedWines.length;
  document.querySelector("#saved-count").textContent = savedWines.length;
  renderSavedWines();
  document.querySelectorAll(".chat-save-wine, .save-wine").forEach((button) => {
    const wine = button.dataset.chatWineId
      ? chatWineResults.get(button.dataset.chatWineId)
      : currentWines[Number(button.dataset.wineIndex)];
    if (!wine) return;
    const saved = savedWines.some((entry) => entry.Title.toLowerCase() === wine.Title.toLowerCase());
    button.classList.toggle("saved", saved);
    button.textContent = button.classList.contains("chat-save-wine")
      ? (saved ? "✓ Saved" : "+ Save")
      : (saved ? "✓ Saved to my list" : "+ Add to my list");
  });
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
      headers: {
        "Content-Type": "application/json",
        "x-api-token": getApiToken(),
      },
      body: JSON.stringify(payload),
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      if (response.status === 429) throw new Error("The cellar is busy. Please wait a moment and try again.");
      if (response.status === 404) throw new Error("We couldn't find that bottle. Try a shorter part of its name.");
      if (response.status === 401) throw new Error("The site is missing its API token. Please refresh the page and try again.");
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

function addChatMessage(text, role, wines = [], preferences = null, receipt = {}) {
  const messages = document.querySelector("#chat-messages");
  const message = document.createElement("div");
  message.className = `chat-message ${role}`;
  message.innerHTML = role === "assistant"
    ? `<span class="chat-avatar">W</span><div class="chat-bubble">${renderMarkdown(text)}</div>`
    : `<div class="chat-bubble"><p>${escapeHtml(text)}</p></div>`;
  if (role === "assistant") message.insertAdjacentHTML("beforeend", actionLinks(receipt));
  if (role === "assistant" && preferences) {
    const profile = document.createElement("div");
    profile.className = "interpreted-preferences";
    const currency = preferences.currency || "USD";
    const price = (value) => new Intl.NumberFormat("en", { style: "currency", currency, maximumFractionDigits: 2 }).format(value);
    const budget = preferences.max_price != null
      ? `${preferences.min_price != null ? price(preferences.min_price) + "–" : "Up to "}${price(preferences.max_price)}`
      : preferences.min_price != null ? `From ${price(preferences.min_price)}` : "";
    const labels = [preferences.type, preferences.sweetness, preferences.body, preferences.flavor_notes, preferences.region, budget].filter((value) => value && value !== "any");
    if (labels.length) {
      profile.innerHTML = `<span class="profile-label">Matching your taste</span>${labels.map((label) => `<span class="profile-chip">${escapeHtml(label)}</span>`).join("")}`;
      message.appendChild(profile);
    }
  }
  if (role === "assistant" && wines.length) {
    visibleWineTitles = wines.map((wine) => wine.Title);
    const options = document.createElement("div");
    options.className = "chat-recommendation-cards";
    options.innerHTML = wines.map((wine, index) => {
      const wineId = `${Date.now()}-${Math.random()}-${index}`;
      chatWineResults.set(wineId, wine);
      const isSaved = savedWines.some((saved) => saved.Title === wine.Title);
      const title = escapeHtml(wine.Title || "Wine recommendation");
      const vintage = wine.Vintage ? `<div class="chat-card-vintage">${escapeHtml(wine.Vintage)}</div>` : "";
      const region = [wine.Region, wine.Country].filter(Boolean).join(", ");
      const regionLine = region ? `<div class="chat-card-meta">${escapeHtml(region)}</div>` : "";
      const styleLine = wine.Style ? `<div class="chat-card-style">${escapeHtml(wine.Style)}</div>` : "";
      const priceLine = wine.Price ? `<div class="chat-card-price">${escapeHtml(wine.Price)}</div>` : `<div class="chat-card-price">Price varies</div>`;
      const topPick = index === 0 ? '<span class="chat-card-top-pick">01 · Your closest match</span>' : `<span class="chat-card-rank">${String(index + 1).padStart(2, "0")} · Also worth a taste</span>`;
      return `
        <article class="chat-recommendation-card">
          ${topPick}
          <div class="chat-card-title">${title}</div>
          ${vintage}
          <div class="chat-card-details">
            ${regionLine}
            ${styleLine}
          </div>
          <div class="chat-card-footer">
            ${priceLine}
            <div class="chat-card-actions">
              <button class="chat-ask-wine" data-chat-wine-id="${wineId}">Explore</button>
              <button class="chat-save-wine ${isSaved ? "saved" : ""}" data-chat-wine-id="${wineId}">${isSaved ? "✓ Saved" : "+ Save"}</button>
            </div>
          </div>
        </article>
      `;
    }).join("");
    message.appendChild(options);
  }
  messages.appendChild(message);
  if (role === "assistant") {
    messages.scrollTop += message.getBoundingClientRect().top - messages.getBoundingClientRect().top - 16;
  } else {
    messages.scrollTop = messages.scrollHeight;
  }
}

function actionLinks(receipt) {
  const links = [];
  if (receipt.listSaved) links.push('<button type="button" data-open-saved-list>View My List →</button>');
  if (receipt.journalSaved) links.push('<a href="/journal">View journal →</a>');
  return links.length ? `<div class="chat-action-links">${links.join("")}</div>` : "";
}

function applyChatActions(body) {
  const messages = [];
  const receipt = { listSaved: false, journalSaved: false };
  if (body.list_additions?.length) {
    try {
      const result = WinePairPersonal.saveRecommendedWines(localStorage, body.list_additions);
      savedWines = result.wines;
      receipt.listSaved = true;
      messages.push(result.added.length ? `Saved to My List: ${result.added.join("; ")}.` : "Those bottles are already in My List.");
    } catch {
      messages.push("I couldn’t save to My List in this browser. Please try the wine card’s Save button.");
    }
  }
  if (body.journal_additions?.length) {
    try {
      const result = WinePairPersonal.saveJournalEntries(localStorage, body.journal_additions);
      receipt.journalSaved = true;
      messages.push(`Saved to your journal: ${result.saved.join("; ")}.`);
      if (body.journal_additions.some((entry) => entry.rating == null)) messages.push("You can add a rating in your journal whenever you’re ready.");
    } catch {
      messages.push("I couldn’t save the journal entry in this browser. Please try again or open your Journal.");
    }
  }
  if (receipt.listSaved) renderWineListState();
  return { ...receipt, message: messages.join("\n\n") || body.message };
}

function chatPayload(message, selectedWine = null) {
  return {
    message, session_id: chatSessionId,
    journal_ratings: WinePairPersonal.readJournalRatings(localStorage),
    visible_wine_titles: visibleWineTitles,
    selected_wine_title: selectedWine?.Title || "",
    local_date: WinePairPersonal.localDate(),
  };
}

let chatPending = false;

async function sendChatMessage(message, intent = "chat") {
  const trimmed = message.trim();
  if (!trimmed || chatPending || detailPending) return;
  chatPending = true;
  const input = document.querySelector("#chat-input");
  input.value = "";
  document.querySelector("#chat-panel").classList.add("has-conversation");
  document.querySelectorAll("#chat-form button, .chat-suggestions button").forEach((button) => { button.disabled = true; });
  addChatMessage(trimmed, "user");
  const messages = document.querySelector("#chat-messages");
  const typing = document.createElement("div");
  typing.className = "chat-typing";
  typing.setAttribute("role", "status");
  typing.textContent = "Your sommelier is thinking…";
  messages.appendChild(typing);
  messages.scrollTop = messages.scrollHeight;
  try {
    let journalRatings;
    try {
      journalRatings = WinePairPersonal.readJournalRatings(localStorage);
    } catch {
      throw new Error("I couldn’t read your journal in this browser. Open your Journal to check it, or tell me a bottle you love.");
    }
    if (intent === "journal" && !journalRatings.some((entry) => entry.rating >= 4)) {
      typing.remove();
      addChatMessage(journalRatings.length
        ? "You haven’t rated any wines 4 or 5 stars yet. Rate a bottle you enjoyed in your Journal, or tell me the name of a wine you love."
        : "You don’t have any rated wines in your journal yet. Rate a bottle in your Journal, or tell me the name of a wine you love.", "assistant");
      return;
    }
    const response = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json", "x-api-token": getApiToken() },
      body: JSON.stringify(chatPayload(trimmed)),
      signal: AbortSignal.timeout(65000),
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      if (response.status === 429) throw new Error("The cellar is busy. Please wait a moment and try again.");
      throw new Error(typeof body.detail === "string" ? body.detail : "Your sommelier couldn’t connect. Try again or set your preferences below.");
    }
    chatSessionId = body.session_id;
    typing.remove();
    const receipt = applyChatActions(body);
    addChatMessage(receipt.message, "assistant", body.recommendations || [], body.preferences, receipt);
  } catch (error) {
    typing.remove();
    addChatMessage(error.name === "TimeoutError" ? "That took a little too long. Try again or set your preferences below." : error.message || "Your sommelier couldn’t connect. Please try again.", "assistant");
    if (!input.value) input.value = trimmed;
  } finally {
    chatPending = false;
    document.querySelectorAll("#chat-form button, .chat-suggestions button").forEach((button) => { button.disabled = false; });
  }
}

document.querySelector("#chat-form").addEventListener("submit", (event) => {
  event.preventDefault();
  sendChatMessage(document.querySelector("#chat-input").value);
});

document.querySelectorAll(".chat-suggestions button").forEach((button) => {
  button.addEventListener("click", () => sendChatMessage(button.dataset.message, button.dataset.intent));
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
  document.querySelector("#manual-preferences").open = true;
  document.querySelector("#manual-preferences").scrollIntoView({ behavior: "smooth", block: "start" });
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

function addDetailMessage(text, role="assistant", receipt={}) {
  const conversation = document.querySelector("#detail-conversation");
  const message = document.createElement("div");
  message.className = `detail-message ${role}`;
  message.innerHTML = `<div class="detail-bubble">${role === "assistant" ? renderMarkdown(text) : `<p>${escapeHtml(text)}</p>`}</div>`;
  message.insertAdjacentHTML("beforeend", actionLinks(receipt));
  conversation.appendChild(message);
  conversation.scrollTop = conversation.scrollHeight;
}

let detailPending = false;
async function askWineQuestion(question) {
  if (!detailsWine || !question.trim() || detailPending || chatPending) return;
  detailPending = true;
  const selectedWine = detailsWine;
  document.querySelectorAll("#wine-detail-form button, .detail-suggestions button").forEach((button) => { button.disabled = true; });
  addDetailMessage(question.trim(), "user");
  const conversation = document.querySelector("#detail-conversation");
  const thinking = document.createElement("div");
  thinking.className = "detail-thinking";
  thinking.textContent = "Sommelier is thinking…";
  conversation.appendChild(thinking);
  try {
    const response = await fetch("/chat", {
      method:"POST",
      headers:{
        "Content-Type":"application/json",
        "x-api-token": getApiToken(),
      },
      body:JSON.stringify(chatPayload(question.trim(), selectedWine)),
      signal: AbortSignal.timeout(65000),
    });
    const body = await response.json().catch(() => ({}));
    thinking.remove();
    if (!response.ok) throw new Error(body.detail || "I couldn't answer that right now.");
    chatSessionId = body.session_id;
    const receipt = applyChatActions(body);
    addDetailMessage(receipt.message, "assistant", receipt);
  } catch (error) {
    thinking.remove();
    addDetailMessage(error.message);
  } finally {
    detailPending = false;
    document.querySelectorAll("#wine-detail-form button, .detail-suggestions button").forEach((button) => { button.disabled = false; });
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

renderWineListState();
window.addEventListener("storage", (event) => {
  if (event.key === "winepair_saved_wines") {
    try {
      const latest = JSON.parse(event.newValue || "[]");
      if (Array.isArray(latest)) { savedWines = latest; renderWineListState(); }
    } catch { /* Keep the last valid visible list. */ }
  }
});

document.addEventListener("click", (event) => {
  if (event.target.closest("[data-open-saved-list]")) {
    closeWineDetails();
    openWineList();
  }
});
