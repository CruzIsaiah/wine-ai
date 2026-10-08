const test = require('node:test');
const assert = require('node:assert/strict');
const { readJournalRatings, saveRecommendedWines } = require('../static/personalization.js');

function storage(initial = {}) {
  const data = new Map(Object.entries(initial));
  return { getItem: (key) => data.get(key) ?? null, setItem: (key, value) => data.set(key, value) };
}

test('journal payload contains actual valid ratings without notes or dates', () => {
  const store = storage({ winepair_tried_wines: JSON.stringify([
    { wine_name: ' Favorite ', rating: 5, notes: 'private prose', date_tried: '2026-10-07' },
    { wine_name: 'favorite', rating: 1 },
    { wine_name: 'Disliked', rating: 2 },
    { wine_name: '', rating: 5 },
    { wine_name: 'Unrated', rating: 0 },
  ]) });
  assert.deepEqual(readJournalRatings(store), [{ wine_name: 'Favorite', rating: 5 }, { wine_name: 'Disliked', rating: 2 }]);
  assert.deepEqual(readJournalRatings(storage()), []);
});

test('chat save persists actual wine metadata and does not duplicate repeated requests', () => {
  const store = storage({ winepair_saved_wines: JSON.stringify([{ Title: 'Existing', Price: '$10' }]) });
  const wine = { Title: 'Recommended', Price: '$18.99', Grape: 'Riesling' };
  const result = saveRecommendedWines(store, [wine, wine]);
  assert.deepEqual(result.added, ['Recommended']);
  assert.equal(result.wines.length, 2);
  assert.deepEqual(JSON.parse(store.getItem('winepair_saved_wines'))[1], wine);
  assert.deepEqual(saveRecommendedWines(store, [wine]).added, []);
  assert.equal(saveRecommendedWines(store, [wine]).wines.length, 2);
});

test('saving reads fresh storage so another tab’s saved wines are preserved', () => {
  const store = storage();
  saveRecommendedWines(store, [{ Title: 'First' }]);
  store.setItem('winepair_saved_wines', JSON.stringify([{ Title: 'First' }, { Title: 'Other tab' }]));
  assert.equal(saveRecommendedWines(store, [{ Title: 'Third' }]).wines.length, 3);
});

test('storage failure never returns a successful save or replaces existing data', () => {
  const store = storage({ winepair_saved_wines: '[{"Title":"Existing"}]' });
  store.setItem = () => { throw new Error('Storage blocked'); };
  assert.throws(() => saveRecommendedWines(store, [{ Title: 'New' }]), /Storage blocked/);
  assert.equal(store.getItem('winepair_saved_wines'), '[{"Title":"Existing"}]');
});

test('malformed stored data is preserved instead of silently overwritten', () => {
  const store = storage({ winepair_saved_wines: 'broken' });
  assert.throws(() => saveRecommendedWines(store, [{ Title: 'New' }]));
  assert.equal(store.getItem('winepair_saved_wines'), 'broken');
});

const { saveJournalEntries } = require('../static/personalization.js');

test('unrated journal entries persist; a later rating updates without duplicates or lost notes', () => {
  const store = storage();
  const entry = { id: 'entry-1', wine_name: 'A favorite', date_tried: '2026-10-07', rating: null, notes: 'Citrus', attributes: [] };
  saveJournalEntries(store, [entry]);
  assert.equal(JSON.parse(store.getItem('winepair_tried_wines'))[0].rating, null);
  assert.deepEqual(readJournalRatings(store), []);
  saveJournalEntries(store, [{ ...entry, id: 'retry', rating: 4, notes: '' }]);
  const entries = JSON.parse(store.getItem('winepair_tried_wines'));
  assert.equal(entries.length, 1);
  assert.equal(entries[0].rating, 4);
  assert.equal(entries[0].notes, 'Citrus');
  assert.deepEqual(readJournalRatings(store), [{ wine_name: 'A favorite', rating: 4 }]);
});

test('journal storage failure does not return success', () => {
  const store = storage();
  store.setItem = () => { throw new Error('Storage blocked'); };
  assert.throws(() => saveJournalEntries(store, [{ wine_name: 'Wine', date_tried: '2026-10-07', rating: null }]), /Storage blocked/);
});
