import test from 'node:test';
import assert from 'node:assert/strict';

globalThis.localStorage = { getItem: () => null, setItem: () => {} };
globalThis.window = { location: { origin: 'http://127.0.0.1:8000' } };

test('checkout shows known prices and keeps the demo action', async () => {
  const { state } = await import('../js/state.js');
  const { renderCart } = await import('../js/checkout.js');
  const button = { addEventListener() {} };
  const elements = {
    cartEmpty: { hidden: false },
    cartRoot: { innerHTML: '' },
    countCart: { hidden: true },
    btnConfirmCheckout: button,
  };
  globalThis.document = { getElementById: (id) => elements[id] || null };
  state.demoBooking = null;
  state.cart = {
    has_estimates: true,
    total: 18450,
    items: [
      { type: 'hotel', name: 'Отель', price: 15450, estimated: true },
      { type: 'transport', name: 'Самолёт', price: 3000, estimated: false },
    ],
  };

  renderCart();

  assert.match(elements.cartRoot.innerHTML, /15.?450/);
  assert.match(elements.cartRoot.innerHTML, /18.?450/);
  assert.doesNotMatch(elements.cartRoot.innerHTML, /примерн|ориентир|оценка/i);
  assert.match(elements.cartRoot.innerHTML, /3.?000/);
  assert.match(elements.cartRoot.innerHTML, /Подтвердить демо-бронирование/);
  assert.match(elements.cartRoot.innerHTML, /Найти обратную дорогу/);
  assert.match(elements.cartRoot.innerHTML, /cart__total/);
});

test('checkout shows the total when all prices are live', async () => {
  const { state } = await import('../js/state.js');
  const { renderCart } = await import('../js/checkout.js');
  const button = { addEventListener() {} };
  const elements = {
    cartEmpty: { hidden: false },
    cartRoot: { innerHTML: '' },
    countCart: { hidden: true },
    btnConfirmCheckout: button,
  };
  globalThis.document = { getElementById: (id) => elements[id] || null };
  state.demoBooking = null;
  state.cart = {
    has_estimates: false,
    total: 9000,
    items: [{ type: 'hotel', name: 'Отель', price: 9000, estimated: false }],
  };

  renderCart();

  assert.match(elements.cartRoot.innerHTML, /9\s?000/);
  assert.match(elements.cartRoot.innerHTML, /cart__total/);
});
