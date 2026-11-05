import test from 'node:test';
import assert from 'node:assert/strict';

globalThis.localStorage = { getItem: () => null, setItem: () => {} };
globalThis.window = { location: { origin: 'http://127.0.0.1:8000' } };

test('destination card reads actual climate and transport fields', async () => {
  const { destinationFacts } = await import('../js/destinations.js');
  assert.deepEqual(destinationFacts({
    climate: { temp_mean_c: 3.4 },
    transport_available: { types: ['plane'], min_transport_price_rub: 3200 },
  }), { tempC: 3.4, transportTypes: ['plane'] });
});

test('route card separates a live ticket from a route price estimate', async () => {
  const { transportFacts } = await import('../js/itinerary.js');
  assert.deepEqual(transportFacts({
    type: 'plane', record_kind: 'live_offer',
    price: { amount_min_rub: 4500, currency: 'RUB' },
  }), { amount: 4500, label: '', isOffer: true });
  assert.deepEqual(transportFacts({
    type: 'plane', record_kind: 'route_price_estimate',
    price_estimate: { amount_rub: 4200 },
  }), { amount: 4200, label: '', isOffer: false });
});

test('missing hotel category is not displayed as zero stars', async () => {
  const { hotelStarLabel } = await import('../js/hotels.js');
  assert.equal(hotelStarLabel({ stars: null }), '');
  assert.equal(hotelStarLabel({ stars: 4 }), '★★★★☆');
});

test('hotel card omits data-confidence caveats from its reasons', async () => {
  const { displayHotelReason } = await import('../js/hotels.js');
  assert.equal(displayHotelReason('Близко к центру; наличие и тариф не подтверждены'), 'Близко к центру');
  assert.equal(displayHotelReason('Цена не указана; соответствие бюджету не подтверждено'), '');
});

test('itinerary hides data-confidence notices but keeps actionable warnings', async () => {
  const { displayableWarnings } = await import('../js/itinerary.js');
  const warnings = [
    { level: 'warning', text: 'Наличие номера и итоговая стоимость не подтверждены.' },
    { level: 'warning', text: 'Проверьте сбор за перевозку питомца.' },
  ];
  assert.deepEqual(displayableWarnings(warnings), [warnings[1]]);
});
