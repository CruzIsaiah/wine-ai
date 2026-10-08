const journalKey = "winepair_tried_wines";
let entries = JSON.parse(localStorage.getItem(journalKey) || "[]");
let savedWines = JSON.parse(localStorage.getItem("winepair_saved_wines") || "[]");
const form = document.querySelector("#full-tasting-form");
const selectedAttributes = new Set();
const ratingInputs = [...document.querySelectorAll('input[name="rating"]')];
const ratingDescriptions = ["Not rated yet", "Disliked it", "Not for me", "Enjoyed it", "Really liked it", "Loved it"];

function renderStarRating(preview = null) {
  const selected = Number(form.elements.rating.value) || 0;
  ratingInputs.forEach((input) => input.closest(".star-option").classList.toggle("filled", Number(input.value) <= (preview ?? selected)));
  document.querySelector("#rating-description").textContent = selected
    ? `${selected}/5 · ${ratingDescriptions[selected]}` : ratingDescriptions[0];
  document.querySelector("#clear-rating").hidden = selected === 0;
}

ratingInputs.forEach((input) => {
  input.addEventListener("change", () => renderStarRating());
  input.closest(".star-option").addEventListener("pointerenter", (event) => {
    if (event.pointerType === "mouse") renderStarRating(Number(input.value));
  });
});
document.querySelector(".star-options").addEventListener("pointerleave", () => renderStarRating());
document.querySelector("#clear-rating").addEventListener("click", () => {
  ratingInputs.forEach((input) => { input.checked = false; });
  renderStarRating();
  ratingInputs[0].focus();
});
renderStarRating();


function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>'"]/g, (character) => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"})[character]);
}

function saveEntries() {
  localStorage.setItem(journalKey, JSON.stringify(entries));
  renderEntries();
}

function renderEntries() {
  const filter = document.querySelector("#journal-filter").value;
  const visible = filter === "all" ? entries : entries.filter((entry) => entry.rating === Number(filter));
  document.querySelector("#journal-total").textContent = entries.length;
  const rated = entries.filter((entry) => Number.isInteger(entry.rating) && entry.rating >= 1 && entry.rating <= 5);
  document.querySelector("#journal-average").textContent = rated.length ? (rated.reduce((sum, entry) => sum + entry.rating, 0) / rated.length).toFixed(1) : "—";
  document.querySelector("#journal-entries").innerHTML = visible.length ? visible.map((entry) => {
    const originalIndex = entries.indexOf(entry);
    return `<article class="journal-entry-card"><h3>${escapeHtml(entry.wine_name)}</h3><div class="journal-card-meta"><span class="journal-card-stars">${entry.rating ? "★".repeat(entry.rating) + "☆".repeat(5-entry.rating) : "Not rated yet"}</span><span class="journal-card-date">${escapeHtml(entry.date_tried)}</span></div>${entry.attributes?.length ? `<div class="journal-tags">${entry.attributes.map((tag)=>`<span>${escapeHtml(tag)}</span>`).join("")}</div>`:""}${entry.notes?`<p>${escapeHtml(entry.notes)}</p>`:""}<button class="journal-edit" data-entry-index="${originalIndex}">Edit</button><button class="journal-delete" data-entry-index="${originalIndex}" aria-label="Delete ${escapeHtml(entry.wine_name)}">×</button></article>`;
  }).join("") : '<div class="journal-empty">No tasting notes here yet.<br>Your next bottle can be the first.</div>';
}

function renderSavedToRate() {
  document.querySelector("#saved-to-rate").innerHTML = savedWines.length ? savedWines.map((wine, index) => `<article class="rate-list-item"><strong>${escapeHtml(wine.Title)}</strong><span>${escapeHtml(wine.Price || "Price varies")}</span><button type="button" data-rate-index="${index}">Rate this wine</button></article>`).join("") : '<div class="rate-list-empty">Your Want to Try list is empty.</div>';
  document.querySelector("#saved-wine-options").innerHTML = savedWines.map((wine) => `<option value="${escapeHtml(wine.Title)}"></option>`).join("");
}

function resetJournalForm() {
  form.reset();
  renderStarRating();
  form.elements.date_tried.value = WinePairPersonal.localDate();
  form.elements.editing_index.value = "";
  form.elements.source_title.value = "";
  selectedAttributes.clear();
  document.querySelectorAll("[data-attribute]").forEach((button)=>button.classList.remove("selected"));
  document.querySelector("#journal-form-eyebrow").lastChild.textContent = " New entry";
  document.querySelector("#journal-form-title").textContent = "What did you try?";
  document.querySelector("#journal-submit").firstChild.textContent = "Save to my journal ";
  document.querySelector("#cancel-edit").hidden = true;
}

function populateJournalForm(entry, editingIndex="") {
  resetJournalForm();
  form.elements.wine_name.value = entry.wine_name;
  form.elements.rating.value = entry.rating || "";
  renderStarRating();
  form.elements.date_tried.value = entry.date_tried || WinePairPersonal.localDate();
  form.elements.notes.value = entry.notes || "";
  form.elements.editing_index.value = editingIndex;
  (entry.attributes || []).forEach((attribute) => selectedAttributes.add(attribute));
  document.querySelectorAll("[data-attribute]").forEach((button)=>button.classList.toggle("selected", selectedAttributes.has(button.dataset.attribute)));
  document.querySelector("#journal-form-eyebrow").lastChild.textContent = editingIndex === "" ? " Rate from My List" : " Editing entry";
  document.querySelector("#journal-form-title").textContent = editingIndex === "" ? "How was this wine?" : "Update your tasting";
  document.querySelector("#journal-submit").firstChild.textContent = editingIndex === "" ? "Save to my journal " : "Update tasting note ";
  document.querySelector("#cancel-edit").hidden = false;
  form.scrollIntoView({behavior:"smooth",block:"start"});
}

form.elements.date_tried.value = WinePairPersonal.localDate();

document.querySelectorAll("[data-attribute]").forEach((button) => button.addEventListener("click", () => {
  const attribute = button.dataset.attribute;
  if (selectedAttributes.has(attribute)) selectedAttributes.delete(attribute); else selectedAttributes.add(attribute);
  button.classList.toggle("selected", selectedAttributes.has(attribute));
}));

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const values = Object.fromEntries(new FormData(form));
  const entry = {wine_name:values.wine_name.trim(),rating:values.rating ? Number(values.rating) : null,date_tried:values.date_tried,attributes:[...selectedAttributes],notes:values.notes.trim()};
  if (values.editing_index !== "") entries[Number(values.editing_index)] = entry;
  else entries.unshift(entry);
  if (values.source_title) {
    savedWines = savedWines.filter((wine) => wine.Title !== values.source_title);
    localStorage.setItem("winepair_saved_wines", JSON.stringify(savedWines));
    renderSavedToRate();
  }
  saveEntries();
  resetJournalForm();
});

document.querySelector("#journal-filter").addEventListener("change", renderEntries);
document.querySelector("#journal-entries").addEventListener("click", (event) => {
  const editButton = event.target.closest(".journal-edit");
  if (editButton) {
    const index = Number(editButton.dataset.entryIndex);
    populateJournalForm(entries[index], String(index));
    return;
  }
  const button = event.target.closest(".journal-delete");
  if (!button) return;
  entries.splice(Number(button.dataset.entryIndex),1);
  saveEntries();
});

document.querySelector("#saved-to-rate").addEventListener("click", (event) => {
  const button = event.target.closest("[data-rate-index]");
  if (!button) return;
  const wine = savedWines[Number(button.dataset.rateIndex)];
  populateJournalForm({wine_name:wine.Title,date_tried:WinePairPersonal.localDate(),attributes:[],notes:""});
  form.elements.source_title.value = wine.Title;
});

document.querySelector("#cancel-edit").addEventListener("click", resetJournalForm);

renderSavedToRate();
renderEntries();

const requestedWine = new URLSearchParams(window.location.search).get("wine");
if (requestedWine) {
  const savedWine = savedWines.find((wine) => wine.Title === requestedWine);
  populateJournalForm({wine_name:requestedWine,date_tried:WinePairPersonal.localDate(),attributes:[],notes:""});
  if (savedWine) form.elements.source_title.value = savedWine.Title;
}

window.addEventListener("storage", (event) => {
  if (event.key === journalKey || event.key === "winepair_saved_wines") {
    try {
      entries = JSON.parse(localStorage.getItem(journalKey) || "[]");
      savedWines = JSON.parse(localStorage.getItem("winepair_saved_wines") || "[]");
      renderEntries();
      renderSavedToRate();
    } catch { /* Leave the current view intact if another tab wrote invalid data. */ }
  }
});
