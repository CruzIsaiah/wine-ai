const journalKey = "winepair_tried_wines";
let entries = JSON.parse(localStorage.getItem(journalKey) || "[]");
const savedWines = JSON.parse(localStorage.getItem("winepair_saved_wines") || "[]");
const form = document.querySelector("#full-tasting-form");
const selectedAttributes = new Set();

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
  document.querySelector("#journal-average").textContent = entries.length ? (entries.reduce((sum, entry) => sum + entry.rating, 0) / entries.length).toFixed(1) : "—";
  document.querySelector("#journal-entries").innerHTML = visible.length ? visible.map((entry) => {
    const originalIndex = entries.indexOf(entry);
    return `<article class="journal-entry-card"><h3>${escapeHtml(entry.wine_name)}</h3><div class="journal-card-meta"><span class="journal-card-stars">${"★".repeat(entry.rating)}${"☆".repeat(5-entry.rating)}</span><span class="journal-card-date">${escapeHtml(entry.date_tried)}</span></div>${entry.attributes?.length ? `<div class="journal-tags">${entry.attributes.map((tag)=>`<span>${escapeHtml(tag)}</span>`).join("")}</div>`:""}${entry.notes?`<p>${escapeHtml(entry.notes)}</p>`:""}<button class="journal-delete" data-entry-index="${originalIndex}" aria-label="Delete ${escapeHtml(entry.wine_name)}">×</button></article>`;
  }).join("") : '<div class="journal-empty">No tasting notes here yet.<br>Your next bottle can be the first.</div>';
}

document.querySelector("#saved-wine-options").innerHTML = savedWines.map((wine) => `<option value="${escapeHtml(wine.Title)}"></option>`).join("");
form.elements.date_tried.value = new Date().toISOString().slice(0,10);

document.querySelectorAll("[data-attribute]").forEach((button) => button.addEventListener("click", () => {
  const attribute = button.dataset.attribute;
  if (selectedAttributes.has(attribute)) selectedAttributes.delete(attribute); else selectedAttributes.add(attribute);
  button.classList.toggle("selected", selectedAttributes.has(attribute));
}));

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const values = Object.fromEntries(new FormData(form));
  entries.unshift({wine_name:values.wine_name.trim(),rating:Number(values.rating),date_tried:values.date_tried,attributes:[...selectedAttributes],notes:values.notes.trim()});
  saveEntries();
  form.reset();
  form.elements.date_tried.value = new Date().toISOString().slice(0,10);
  selectedAttributes.clear();
  document.querySelectorAll("[data-attribute]").forEach((button)=>button.classList.remove("selected"));
});

document.querySelector("#journal-filter").addEventListener("change", renderEntries);
document.querySelector("#journal-entries").addEventListener("click", (event) => {
  const button = event.target.closest(".journal-delete");
  if (!button) return;
  entries.splice(Number(button.dataset.entryIndex),1);
  saveEntries();
});

renderEntries();
