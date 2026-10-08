// Exercise the actual app request/response handlers with an in-memory DOM and storage.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const personal = require('../static/personalization.js');

function client(response, failWrites = false) {
  const nodes = new Map();
  const data = new Map([['winepair_api_token', 'test-token']]);
  const element = () => ({
    value: '', textContent: '', innerHTML: '', children: [], dataset: {}, scrollTop: 0, scrollHeight: 0,
    classList: { add() {}, remove() {}, toggle() {}, contains() { return false; } },
    addEventListener() {}, setAttribute() {}, scrollIntoView() {}, remove() {},
    appendChild(node) { this.children.push(node); },
    insertAdjacentHTML(_, html) { this.innerHTML += html; },
    getBoundingClientRect() { return { top: 0 }; },
  });
  const document = {
    querySelector(selector) { if (!nodes.has(selector)) nodes.set(selector, element()); return nodes.get(selector); },
    querySelectorAll() { return []; }, createElement: element, addEventListener() {},
  };
  const requests = [];
  const context = vm.createContext({
    document, window: { addEventListener() {}, scrollY: 0 },
    localStorage: {
      getItem: (key) => data.get(key) ?? null,
      setItem(key, value) { if (failWrites) throw new Error('Storage blocked'); data.set(key, value); },
    },
    WinePairPersonal: personal, AbortSignal,
    fetch: async (url, options) => {
      requests.push({ url, body: JSON.parse(options.body) });
      return { ok: true, json: async () => response };
    },
  });
  vm.runInContext(fs.readFileSync('static/app.js', 'utf8'), context);
  return { context, data, nodes, requests };
}

const wine = { Title: "Cooper's Hawk White", Price: '$18.99' };
const entry = { id: 'test-entry', wine_name: wine.Title, rating: null, date_tried: '2026-10-07', notes: '', attributes: [] };
const reply = { session_id: 'test-session', message: 'Prepared.', recommendations: [], list_additions: [wine], journal_additions: [entry] };

test('main chat applies both actions from the API response and renders actual save receipts', async () => {
  const app = client(reply);
  await vm.runInContext('sendChatMessage("Add this to my list and journal")', app.context);
  assert.equal(app.requests[0].url, '/chat');
  assert.deepEqual(JSON.parse(app.data.get('winepair_saved_wines')), [wine]);
  assert.deepEqual(JSON.parse(app.data.get('winepair_tried_wines')), [entry]);
  assert.equal(app.nodes.get('#wine-list-count').textContent, 1);
  const html = app.nodes.get('#chat-messages').children.map((node) => node.innerHTML).join('');
  assert.match(html, /Saved to My List/);
  assert.match(html, /Saved to your journal/);
  assert.match(html, /View journal/);
});

test('Explore uses the actionable endpoint with the selected wine, and persists both results', async () => {
  const app = client(reply);
  vm.runInContext(`detailsWine = ${JSON.stringify(wine)}`, app.context);
  await vm.runInContext('askWineQuestion("Add this to my list and journal")', app.context);
  assert.equal(app.requests[0].url, '/chat');
  assert.equal(app.requests[0].body.selected_wine_title, wine.Title);
  assert.deepEqual(JSON.parse(app.data.get('winepair_saved_wines')), [wine]);
  assert.deepEqual(JSON.parse(app.data.get('winepair_tried_wines')), [entry]);
  const html = app.nodes.get('#detail-conversation').children.map((node) => node.innerHTML).join('');
  assert.match(html, /Saved to My List/);
  assert.match(html, /Saved to your journal/);
});

test('failed persistence in Explore shows errors rather than AI success text', async () => {
  const app = client({ ...reply, message: 'I saved both!' }, true);
  vm.runInContext(`detailsWine = ${JSON.stringify(wine)}`, app.context);
  await vm.runInContext('askWineQuestion("Save this")', app.context);
  assert.equal(app.data.has('winepair_saved_wines'), false);
  assert.equal(app.data.has('winepair_tried_wines'), false);
  const html = app.nodes.get('#detail-conversation').children.map((node) => node.innerHTML).join('');
  assert.match(html, /couldn’t save/);
  assert.doesNotMatch(html, /I saved both!/);
});
