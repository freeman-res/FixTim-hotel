import test from 'node:test';
import assert from 'node:assert/strict';

const storage = new Map();
globalThis.localStorage = {
  getItem: (key) => storage.get(key) ?? null,
  setItem: (key, value) => storage.set(key, String(value)),
};
globalThis.window = { location: { origin: 'http://127.0.0.1:8000' } };
storage.set('ostrovok_api_base', 'http://127.0.0.1:9999');

const { state } = await import('../js/state.js');
const { API_BASE, postChat } = await import('../js/api.js');

test('real API is selected by default and uses the site origin even with an old browser setting', () => {
  assert.equal(state.isMock, false);
  assert.equal(API_BASE, 'http://127.0.0.1:8000');
});

test('card selection posts a structured action and current session', async () => {
  state.isMock = false;
  state.sessionId = 'session-1';
  let request;
  globalThis.fetch = async (url, options) => {
    request = { url, options };
    return { ok: true, json: async () => ({ status: 'results', reply: 'ok' }) };
  };
  await postChat('Выбираю Казань', {
    action: 'select_destination', target_id: 'dest_kazan',
  });
  assert.equal(request.url, 'http://127.0.0.1:8000/api/v1/chat');
  assert.deepEqual(JSON.parse(request.options.body), {
    message: 'Выбираю Казань', session_id: 'session-1',
    action: 'select_destination', target_id: 'dest_kazan',
  });
});

test('hotel price label distinguishes synthetic nightly estimate from live total', async () => {
  const { hotelDisplayPrice } = await import('../js/hotels.js');
  assert.deepEqual(hotelDisplayPrice({
    total_price: null,
    price_estimate: { amount_rub: 4500, unit: 'per_night' },
  }), { amount: 4500, currency: 'RUB', label: 'за ночь' });
  assert.deepEqual(hotelDisplayPrice({
    total_price: 18000, currency: 'RUB', record_kind: 'live_offer',
  }), { amount: 18000, currency: 'RUB', label: 'за проживание' });
});
