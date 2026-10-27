/**
 * Ostrovok AI Agent — Frontend
 * Contract: POST /api/v1/chat → ChatResponse (session_id, status, reply, hotels,
 * stage, destinations, itinerary, cart, warnings, is_demo)
 */
import { state, resetState } from "./state.js";
import { postChat, API_BASE, formatPrice } from "./api.js";
import {
  renderWelcome,
  renderMessages,
  showTyping,
  hideTyping,
  setLoading,
  initComposer,
} from "./chat.js";
import { renderDestinations } from "./destinations.js";
import { renderHotels, hotelId } from "./hotels.js";
import { renderItinerary } from "./itinerary.js";
import { renderCart } from "./checkout.js";
import { renderFavorites, updateFavBadge } from "./favorites.js";

const STAGE_ORDER = ["inspiration", "destinations", "hotels", "itinerary", "checkout"];

function initTabs() {
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach((t) => t.classList.remove("is-active"));
      document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("is-active"));
      tab.classList.add("is-active");
      document.getElementById("panel-" + tab.dataset.tab)?.classList.add("is-active");
    });
  });
}

function switchTab(name) {
  document.querySelector(`.tab[data-tab="${name}"]`)?.click();
}

function updateStepper() {
  const stage = state.stage || "inspiration";
  const idx = STAGE_ORDER.indexOf(stage);
  document.querySelectorAll(".step").forEach((el) => {
    const s = el.dataset.stage;
    const i = STAGE_ORDER.indexOf(s);
    el.classList.remove("is-active", "is-done");
    if (i === idx) el.classList.add("is-active");
    else if (i >= 0 && i < idx) el.classList.add("is-done");
  });
}

function updateTripSummary() {
  const el = document.getElementById("tripSummary");
  const place = state.selected.destinationName;
  const hasCart = state.cart?.total != null;
  if (!place && !hasCart) {
    if (el) el.hidden = true;
    return;
  }
  if (el) el.hidden = false;
  const placeEl = document.getElementById("summaryPlace");
  const metaEl = document.getElementById("summaryMeta");
  const priceEl = document.getElementById("summaryPrice");
  if (placeEl) placeEl.textContent = place || "Куда";
  if (metaEl) {
    const hotel = state.selected.hotelName;
    metaEl.textContent =
      hotel ||
      (state.stage === "destinations" ? "Когда" : state.stage === "hotels" ? "Жильё" : "Маршрут");
  }
  if (priceEl) {
    priceEl.textContent = hasCart ? formatPrice(state.cart.total) : "Сколько";
  }
}

let toastTimer;
function toast(text) {
  const el = document.getElementById("toast");
  if (!el) return;
  el.textContent = text;
  el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    el.hidden = true;
  }, 3200);
}

function normalizeHotels(list) {
  return (list || []).map((h) => ({
    ...h,
    id: h.hotel_id || h.id,
    hotel_id: h.hotel_id || h.id,
    price_total: h.price_total ?? h.price,
  }));
}

function applyResponse(data) {
  if (data.session_id) state.sessionId = data.session_id;
  if (data.status) state.status = data.status;
  if (data.stage) state.stage = data.stage;
  if (data.destinations) state.destinations = data.destinations;
  if (data.hotels) state.hotels = normalizeHotels(data.hotels);
  if (data.transport_options) state.transportOptions = data.transport_options;
  if (data.itinerary) state.itinerary = data.itinerary;
  if (data.cart) state.cart = data.cart;
  if (data.warnings) {
    state.warnings = (data.warnings || []).map((w) =>
      typeof w === "string" ? { level: "info", text: w } : w
    );
  }

  updateStepper();
  updateTripSummary();
  renderAll();

  if (data.cart?.items?.length) switchTab("cart");
  else if (data.itinerary?.legs?.length) switchTab("itinerary");
  else if (data.hotels?.length) switchTab("hotels");
  else if (data.destinations?.length) switchTab("destinations");
}

function onFavChange(nowFav) {
  toast(nowFav ? "Добавлено в избранное" : "Убрано из избранного");
  updateFavBadge();
  renderFavorites({
    onSelectDestination,
    onSelectHotel,
    onChange: () => {
      toast("Убрано из избранного");
      renderAll();
    },
  });
  // refresh hearts on current lists
  renderDestinations(onSelectDestination, onFavChange);
  renderHotels(onSelectHotel, onFavChange);
}

function renderAll() {
  if (state.messages.length === 0) {
    renderWelcome(sendMessage);
  } else {
    renderMessages();
  }
  renderDestinations(onSelectDestination, onFavChange);
  renderHotels(onSelectHotel, onFavChange);
  renderItinerary();
  renderCart(onCheckoutConfirmed);
  renderFavorites({
    onSelectDestination,
    onSelectHotel,
    onChange: () => {
      toast("Убрано из избранного");
      renderAll();
    },
  });
}

function onSelectDestination(dest) {
  const id = dest.id || dest.destination_id;
  state.selected.destinationId = id;
  state.selected.destinationName = dest.name;
  updateTripSummary();
  renderDestinations(onSelectDestination, onFavChange);
  sendMessage(`Выбираю направление: ${dest.name}`);
}

function onSelectHotel(hotel) {
  const id = hotelId(hotel);
  state.selected.hotelId = id;
  state.selected.hotelName = hotel.name;
  updateTripSummary();
  renderHotels(onSelectHotel, onFavChange);
  sendMessage(`Выбираю отель: ${hotel.name}`);
}

function onCheckoutConfirmed(result) {
  toast("Демо-бронирование: " + (result.booking_id || "OK"));
  state.messages.push({
    role: "agent",
    text: result.message || "Демонстрационное бронирование создано. Реальной оплаты нет.",
  });
  state.stage = "checkout";
  updateStepper();
  renderMessages();
}

async function sendMessage(text) {
  if (state.isLoading) return;

  state.messages.push({ role: "user", text });
  renderMessages();
  setLoading(true);
  showTyping();

  try {
    const data = await postChat(text);
    hideTyping();
    const reply = data.reply || data.message || "Готово.";
    state.messages.push({ role: "agent", text: reply });
    applyResponse(data);
  } catch (err) {
    hideTyping();
    state.messages.push({
      role: "agent",
      text:
        "Не удалось получить ответ.\n\n" +
        err.message +
        (state.isMock
          ? ""
          : "\n\nПроверьте backend на " +
            API_BASE +
            " или включите Mock API в меню ⋯"),
    });
    renderMessages();
    toast("Ошибка запроса");
  } finally {
    setLoading(false);
  }
}

function initMenu() {
  const btn = document.getElementById("btnMenu");
  const menu = document.getElementById("menu");
  const mockToggle = document.getElementById("mockToggle");
  const apiLabel = document.getElementById("apiBaseLabel");

  if (apiLabel) apiLabel.textContent = API_BASE.replace(/^https?:\/\//, "");

  btn?.addEventListener("click", (e) => {
    e.stopPropagation();
    if (menu) menu.hidden = !menu.hidden;
  });
  document.addEventListener("click", () => {
    if (menu) menu.hidden = true;
  });
  menu?.addEventListener("click", (e) => e.stopPropagation());

  if (mockToggle) {
    mockToggle.checked = state.isMock;
    mockToggle.addEventListener("change", () => {
      state.isMock = mockToggle.checked;
      toast(state.isMock ? "Mock API включён" : "Реальный API: " + API_BASE);
    });
  }

  document.getElementById("btnNewSession")?.addEventListener("click", () => {
    const keepMock = state.isMock;
    resetState(); // favorites preserved
    state.isMock = keepMock;
    updateStepper();
    updateTripSummary();
    renderAll();
    toast("Новая сессия · избранное сохранено");
    if (menu) menu.hidden = true;
  });
}

function boot() {
  initTabs();
  initMenu();
  initComposer(sendMessage);
  updateStepper();
  updateTripSummary();
  updateFavBadge();
  renderAll();
}

boot();
