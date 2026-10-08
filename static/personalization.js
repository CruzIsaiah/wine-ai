/* Shared browser-storage operations; journal prose stays on this device. */
(function () {
  function readArray(storage, key) {
    const value = JSON.parse(storage.getItem(key) || "[]");
    if (!Array.isArray(value)) throw new Error("Stored wine data is not a list.");
    return value;
  }

  function readJournalRatings(storage) {
    const latest = new Map();
    for (const entry of readArray(storage, "winepair_tried_wines")) {
      const name = typeof entry?.wine_name === "string" ? entry.wine_name.trim() : "";
      const rating = Number(entry?.rating);
      if (!name || name.length > 200 || !Number.isInteger(rating) || rating < 1 || rating > 5) continue;
      const key = name.toLowerCase();
      if (!latest.has(key)) latest.set(key, { wine_name: name, rating });
      if (latest.size === 100) break;
    }
    return [...latest.values()];
  }

  function saveRecommendedWines(storage, additions) {
    const wines = readArray(storage, "winepair_saved_wines");
    const existing = new Set(wines.map((wine) => String(wine.Title || "").trim().toLowerCase()));
    const added = [];
    for (const wine of additions) {
      if (typeof wine?.Title !== "string" || !wine.Title.trim()) throw new Error("A wine title is missing.");
      const key = wine.Title.trim().toLowerCase();
      if (!existing.has(key)) {
        wines.push(wine);
        added.push(wine.Title);
        existing.add(key);
      }
    }
    // Commit before returning success; storage errors must not produce a confirmation.
    if (added.length) storage.setItem("winepair_saved_wines", JSON.stringify(wines));
    return { wines, added };
  }

  function localDate() {
    const now = new Date();
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
  }

  function saveJournalEntries(storage, additions) {
    const entries = readArray(storage, "winepair_tried_wines");
    const saved = [];
    for (const entry of additions) {
      if (typeof entry.wine_name !== "string" || !entry.wine_name.trim()
          || (entry.rating != null && (!Number.isInteger(entry.rating) || entry.rating < 1 || entry.rating > 5))
          || !/^\d{4}-\d{2}-\d{2}$/.test(entry.date_tried)) throw new Error("Invalid journal entry.");
      const index = entries.findIndex((existing) =>
        (entry.id && existing.id === entry.id) ||
        (existing.wine_name.trim().toLowerCase() === entry.wine_name.trim().toLowerCase() && existing.date_tried === entry.date_tried));
      if (index < 0) {
        entries.unshift({ ...entry, rating: entry.rating ?? null, notes: entry.notes || "", attributes: entry.attributes || [] });
      } else {
        // Retries and same-day rating updates preserve previously recorded notes.
        const previous = entries[index];
        entries[index] = { ...previous, rating: entry.rating ?? previous.rating ?? null,
          notes: entry.notes || previous.notes || "" };
      }
      saved.push(entry.wine_name);
    }
    if (saved.length) storage.setItem("winepair_tried_wines", JSON.stringify(entries));
    return { entries, saved };
  }

  const api = { readJournalRatings, saveRecommendedWines, saveJournalEntries, localDate };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else globalThis.WinePairPersonal = api;
})();
