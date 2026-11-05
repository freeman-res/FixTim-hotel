
const FAV_STORAGE_KEY = "ostrovok_favorites_v1";
const PURCHASE_HISTORY_KEY = "ostrovok_demo_history_v1";

const state = {
  sessionId: null,
  trip: {},
  messages: [],
  stage: "inspiration",
  status: null,
  destinations: [],
  hotels: [],
  transportOptions: [],
  itinerary: null,
  cart: null,
  warnings: [],
  selected: {
    destinationId: null,
    destinationName: null,
    hotelId: null,
    hotelName: null,
    transportId: null,
    returnTransportId: null,
  },

  favorites: {
    destinations: [],
    hotels: [],
  },
  isLoading: false,
  isMock: false,
  demoBooking: null,
  purchaseHistory: [],
};

function loadPurchaseHistory() {
  try {
    const parsed = JSON.parse(localStorage.getItem(PURCHASE_HISTORY_KEY) || "[]");
    state.purchaseHistory = Array.isArray(parsed) ? parsed : [];
  } catch {
    state.purchaseHistory = [];
  }
}

function savePurchaseHistory() {
  try {
    localStorage.setItem(PURCHASE_HISTORY_KEY, JSON.stringify(state.purchaseHistory));
  } catch {

  }
}

function addPurchase(bookingResult) {
  if (bookingResult?.status !== "ok" || bookingResult?.is_demo !== true ||
      !bookingResult?.booking_id || !state.cart?.items?.length) {
    return null;
  }
  const entry = {
    id: bookingResult.booking_id,
    created_at: new Date().toISOString(),
    is_demo: true,
    destination: state.selected.destinationName || null,
    hotel: state.selected.hotelName || null,
    total: state.cart.total ?? null,
    currency: state.cart.currency || "RUB",
    scope: state.cart.scope || null,
    has_estimates: Boolean(state.cart.has_estimates),
    items: state.cart.items.map((item) => ({
      type: item.type, name: item.name, price: item.price,
      currency: item.currency || "RUB", estimated: Boolean(item.estimated),
    })),
  };
  state.purchaseHistory = [entry, ...state.purchaseHistory.filter((item) => item.id !== entry.id)].slice(0, 50);
  savePurchaseHistory();
  return entry;
}

function clearPurchaseHistory() {
  state.purchaseHistory = [];
  savePurchaseHistory();
}

function purchaseHistoryCount() {
  return state.purchaseHistory.length;
}

function loadFavorites() {
  try {
    const raw = localStorage.getItem(FAV_STORAGE_KEY);
    if (!raw) return;
    const parsed = JSON.parse(raw);
    state.favorites = {
      destinations: Array.isArray(parsed.destinations) ? parsed.destinations : [],
      hotels: Array.isArray(parsed.hotels) ? parsed.hotels : [],
    };
  } catch {

  }
}

function saveFavorites() {
  try {
    localStorage.setItem(FAV_STORAGE_KEY, JSON.stringify(state.favorites));
  } catch {

  }
}

function destKey(d) {
  return String(d?.id || d?.destination_id || "");
}

function hotelKey(h) {
  return String(h?.hotel_id || h?.id || "");
}

function isFavDestination(d) {
  const id = destKey(d);
  return state.favorites.destinations.some((x) => destKey(x) === id);
}

function isFavHotel(h) {
  const id = hotelKey(h);
  return state.favorites.hotels.some((x) => hotelKey(x) === id);
}

function toggleFavoriteDestination(d) {
  const id = destKey(d);
  if (!id) return false;
  const idx = state.favorites.destinations.findIndex((x) => destKey(x) === id);
  if (idx >= 0) {
    state.favorites.destinations.splice(idx, 1);
    saveFavorites();
    return false;
  }
  state.favorites.destinations.push({
    id,
    destination_id: id,
    name: d.name,
    country: d.country,
    avg_temp_c: d.avg_temp_c,
    flight_hours: d.flight_hours,
    price_from: d.price_from,
    tags: d.tags || [],
    why: d.why,
    is_demo: d.is_demo,
  });
  saveFavorites();
  return true;
}

function toggleFavoriteHotel(h) {
  const id = hotelKey(h);
  if (!id) return false;
  const idx = state.favorites.hotels.findIndex((x) => hotelKey(x) === id);
  if (idx >= 0) {
    state.favorites.hotels.splice(idx, 1);
    saveFavorites();
    return false;
  }
  state.favorites.hotels.push({
    id,
    hotel_id: id,
    name: h.name,
    city: h.city,
    stars: h.stars,
    rating: h.rating,
    price_total: h.price_total ?? h.price,
    price: h.price_total ?? h.price,
    price_estimate: h.price_estimate || null,
    nights: h.nights,
    amenities: h.amenities || [],
    why: h.why,
    is_demo: h.is_demo,
  });
  saveFavorites();
  return true;
}

function favoritesCount() {
  return state.favorites.destinations.length + state.favorites.hotels.length;
}

function createSessionId() {
  return "sess_" + Math.random().toString(36).slice(2, 10) + Date.now().toString(36);
}


function resetState() {
  state.sessionId = null;
  state.messages = [];
  state.stage = "inspiration";
  state.status = null;
  state.destinations = [];
  state.hotels = [];
  state.transportOptions = [];
  state.itinerary = null;
  state.cart = null;
  state.warnings = [];
  state.selected = {
    destinationId: null,
    destinationName: null,
    hotelId: null,
    hotelName: null,
    transportId: null,
  };
  state.isLoading = false;
  state.demoBooking = null;

}

loadFavorites();
loadPurchaseHistory();

export {
  state,
  resetState,
  createSessionId,
  isFavDestination,
  isFavHotel,
  toggleFavoriteDestination,
  toggleFavoriteHotel,
  favoritesCount,
  destKey,
  hotelKey,
  saveFavorites,
  addPurchase,
  clearPurchaseHistory,
  purchaseHistoryCount,
};
