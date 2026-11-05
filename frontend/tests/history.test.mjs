import assert from 'node:assert/strict';
import test from 'node:test';

const values = new Map();
globalThis.localStorage = {
  getItem: (key) => values.get(key) ?? null,
  setItem: (key, value) => values.set(key, value),
};
const { state, addPurchase, clearPurchaseHistory, purchaseHistoryCount, resetState } =
  await import('../js/state.js');

test('only confirmed demo checkout is saved with estimate labels across session reset', () => {
  clearPurchaseHistory();
  state.selected.destinationName = 'Казань';
  state.selected.hotelName = 'Отель';
  state.cart = {
    total: 15000, currency: 'RUB', scope: 'outbound_transport_and_hotel_only',
    has_estimates: true,
    items: [{ type: 'hotel', name: 'Отель, 2 ночи', price: 9000,
              currency: 'RUB', estimated: true }],
  };
  assert.equal(addPurchase({ status: 'error', booking_id: 'BAD', is_demo: true }), null);
  assert.equal(purchaseHistoryCount(), 0);
  const saved = addPurchase({ status: 'ok', booking_id: 'DEMO-123', is_demo: true });
  assert.equal(saved.destination, 'Казань');
  assert.equal(saved.scope, 'outbound_transport_and_hotel_only');
  assert.equal(saved.items[0].estimated, true);
  assert.equal(purchaseHistoryCount(), 1);
  resetState();
  assert.equal(purchaseHistoryCount(), 1);
  assert.match(values.get('ostrovok_demo_history_v1'), /DEMO-123/);
  clearPurchaseHistory();
  assert.equal(purchaseHistoryCount(), 0);
});
