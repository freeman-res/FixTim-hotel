import test from 'node:test';
import assert from 'node:assert/strict';

test('real API response keeps destination cards and updates selected catalog IDs', async () => {
  const { applyServerResponse } = await import('../js/response.js');
  const state = {
    sessionId: 's1', stage: 'destinations', status: null,
    destinations: [{ destination_id: 'dest_kazan', name: 'Казань' }],
    hotels: [], transportOptions: [], itinerary: { legs: [{ title: 'stale' }] },
    cart: { items: [{ name: 'stale' }] }, warnings: [],
    selected: { destinationId: null, destinationName: null, hotelId: null, hotelName: null },
  };
  const tab = applyServerResponse(state, {
    session_id: 's1', status: 'results', stage: 'hotels', destinations: [],
    hotels: [{ hotel_id: 'h1', name: 'Отель', total_price: null,
               price_estimate: { amount_rub: 4500 } }],
    transport_options: [], itinerary: null, cart: null, warnings: [],
    state: { trip: { city: 'Казань', destination_id: 'dest_kazan' },
             selected: { hotel_offer_id: 'h1', hotel_name: 'Отель' } },
  });
  assert.equal(tab, 'hotels');
  assert.equal(state.destinations.length, 1);
  assert.equal(state.hotels[0].price_total, null);
  assert.equal(state.selected.destinationId, 'dest_kazan');
  assert.equal(state.selected.hotelId, 'h1');
  assert.equal(state.cart, null);
  assert.equal(state.itinerary, null);
});

test('transport search selects route tab and clears stale transport on empty result', async () => {
  const { applyServerResponse } = await import('../js/response.js');
  const state = { stage: 'hotels', destinations: [], hotels: [], transportOptions: [],
    warnings: [], selected: {} };
  const first = applyServerResponse(state, {
    status: 'results', stage: 'itinerary', transport_options: [{ transport_id: 't1' }],
  });
  assert.equal(first, 'itinerary');
  assert.equal(state.transportOptions.length, 1);
  applyServerResponse(state, {
    status: 'no_results', transport_options: [], state: { last_intent: 'trip_search' },
  });
  assert.equal(state.transportOptions.length, 0);
});

test('a replanned trip clears the previous demo confirmation', async () => {
  const { applyServerResponse } = await import('../js/response.js');
  const state = { stage: 'checkout', destinations: [], hotels: [], transportOptions: [],
    warnings: [], selected: {}, demoBooking: { booking_id: 'DEMO-OLD' } };
  applyServerResponse(state, { status: 'clarification', itinerary: null, cart: null,
    state: { trip: { city: 'Казань' }, selected: {}, needs_replan: true } });
  assert.equal(state.demoBooking, null);
});
