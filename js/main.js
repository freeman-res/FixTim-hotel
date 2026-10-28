/**
 * Ostrovok AI Agent — mobile-first frontend
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
import { renderHistory, updateHistoryBadge } from "./history.js";

const STAGE_ORDER = ["inspiration", "destinations", "hotels", "itinerary", "checkout"];
const TAB_TITLES = {
  destinations: "Направления",
  hotels: "Отели",
  itinerary: "Маршрут",
  cart: "Корзина",
  favorites: "Избранное",
  history: "История",
};

function isMobile() {
  return window.matchMedia("(max-width: 899px)").matches;
}

/* ----- Sheet (mobile results panel) ----- */
const SHEET_SNAPS = { peek: 0.34, mid: 0.55, full: 0.9 };
let sheetHeightRatio = SHEET_SNAPS.mid;

function vh() {
  return window.innerHeight || document.documentElement.clientHeight;
}

function setSheetHeight(px, animate) {
  const side = document.getElementById("panelSide");
  if (!side) return;
  const minH = 160;
  const maxH = Math.round(vh() * 0.94);
  const h = Math.max(minH, Math.min(maxH, Math.round(px)));
  sheetHeightRatio = h / vh();
  if (!animate) side.classList.add("is-dragging");
  else side.classList.remove("is-dragging");
  side.style.setProperty("--sheet-h", h + "px");
  side.style.height = h + "px";
}

function snapSheet(ratio) {
  setSheetHeight(vh() * ratio, true);
  sheetHeightRatio = ratio;
}

function openSheet(tabName) {
  const side = document.getElementById("panelSide");
  const backdrop = document.getElementById("sheetBackdrop");
  if (tabName) switchTab(tabName);
  setSheetHeight(vh() * sheetHeightRatio, true);
  side?.classList.add("is-open");
  side?.setAttribute("aria-hidden", "false");
  if (backdrop) {
    backdrop.hidden = false;
    requestAnimationFrame(() => backdrop.classList.add("is-open"));
  }
  document.body.style.overflow = "hidden";
  updateBottomNav(tabName || currentTab());
  const title = document.getElementById("sheetTitle");
  if (title) title.textContent = TAB_TITLES[tabName || currentTab()] || "Результаты";
}

function closeSheet() {
  const side = document.getElementById("panelSide");
  const backdrop = document.getElementById("sheetBackdrop");
  side?.classList.remove("is-open", "is-dragging");
  side?.setAttribute("aria-hidden", "true");
  backdrop?.classList.remove("is-open");
  setTimeout(() => {
    if (backdrop && !side?.classList.contains("is-open")) backdrop.hidden = true;
  }, 280);
  document.body.style.overflow = "";
  updateBottomNav("chat");
}

function currentTab() {
  return document.querySelector(".tab.is-active")?.dataset.tab || "destinations";
}

function initSheet() {
  document.getElementById("btnCloseSheet")?.addEventListener("click", closeSheet);
  document.getElementById("sheetBackdrop")?.addEventListener("click", closeSheet);
  document.getElementById("btnResults")?.addEventListener("click", () => {
    const side = document.getElementById("panelSide");
    if (side?.classList.contains("is-open")) closeSheet();
    else openSheet();
  });

  const handle = document.getElementById("sheetHandle");
  const side = document.getElementById("panelSide");
  if (!handle || !side) return;

  let dragging = false;
  let startY = 0;
  let startH = 0;

  function onStart(clientY) {
    if (!side.classList.contains("is-open")) return;
    dragging = true;
    startY = clientY;
    startH = side.getBoundingClientRect().height;
    side.classList.add("is-dragging");
  }

  function onMove(clientY) {
    if (!dragging) return;
    const dy = startY - clientY; // up = positive = taller
    setSheetHeight(startH + dy, false);
  }

  function onEnd() {
    if (!dragging) return;
    dragging = false;
    side.classList.remove("is-dragging");
    const h = side.getBoundingClientRect().height;
    const ratio = h / vh();
    // close if pulled down hard
    if (ratio < 0.2) {
      closeSheet();
      sheetHeightRatio = SHEET_SNAPS.mid;
      return;
    }
    // snap to nearest
    const snaps = [SHEET_SNAPS.peek, SHEET_SNAPS.mid, SHEET_SNAPS.full];
    let best = snaps[0];
    let bestDist = Math.abs(ratio - best);
    for (const s of snaps) {
      const d = Math.abs(ratio - s);
      if (d < bestDist) {
        best = s;
        bestDist = d;
      }
    }
    snapSheet(best);
  }

  handle.addEventListener(
    "touchstart",
    (e) => {
      onStart(e.touches[0].clientY);
    },
    { passive: true }
  );
  handle.addEventListener(
    "touchmove",
    (e) => {
      if (!dragging) return;
      e.preventDefault();
      onMove(e.touches[0].clientY);
    },
    { passive: false }
  );
  handle.addEventListener("touchend", onEnd, { passive: true });
  handle.addEventListener("touchcancel", onEnd, { passive: true });

  // mouse for desktop devtools device mode
  handle.addEventListener("mousedown", (e) => {
    e.preventDefault();
    onStart(e.clientY);
    const move = (ev) => onMove(ev.clientY);
    const up = () => {
      onEnd();
      window.removeEventListener("mousemove", move);
      window.removeEventListener("mouseup", up);
    };
    window.addEventListener("mousemove", move);
    window.addEventListener("mouseup", up);
  });
}

/* ----- Bottom nav ----- */
function updateBottomNav(_active) {}

function updateNavDots() {
  const d = document.getElementById("navDotDest");
  const h = document.getElementById("navDotHotels");
  const c = document.getElementById("navDotCart");
  if (d) d.hidden = !(state.destinations?.length);
  if (h) h.hidden = !(state.hotels?.length);
  if (c) c.hidden = !(state.cart?.items?.length || state.demoBooking);

  const total =
    (state.destinations?.length || 0) +
    (state.hotels?.length || 0) +
    (state.cart?.items?.length ? 1 : 0);
  const badge = document.getElementById("resultsBadge");
  const btnRes = document.getElementById("btnResults");
  if (badge) badge.textContent = String(total);
  if (btnRes) btnRes.hidden = total === 0;
}

/* ----- Tabs ----- */
function initTabs() {
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach((t) => t.classList.remove("is-active"));
      document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("is-active"));
      tab.classList.add("is-active");
      document.getElementById("panel-" + tab.dataset.tab)?.classList.add("is-active");
      const title = document.getElementById("sheetTitle");
      if (title) title.textContent = TAB_TITLES[tab.dataset.tab] || "Результаты";
      updateBottomNav(tab.dataset.tab);
    });
  });
}

function switchTab(name) {
  const tab = document.querySelector(`.tab[data-tab="${name}"]`);
  if (tab) tab.click();
}

function updateStepper() {
  const stage = state.stage || "inspiration";
  const idx = STAGE_ORDER.indexOf(stage);
  document.querySelectorAll(".step").forEach((el) => {
    const i = STAGE_ORDER.indexOf(el.dataset.stage);
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
    metaEl.textContent =
      state.selected.hotelName ||
      (state.stage === "destinations" ? "выбор" : "сборка");
  }
  if (priceEl) priceEl.textContent = hasCart ? formatPrice(state.cart.total) : "цена";}

let toastTimer;
function toast(text) {
  const el = document.getElementById("toast");
  if (!el) return;
  el.textContent = text;
  el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    el.hidden = true;
  }, 2800);
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
  updateNavDots();
  renderAll();

  // Auto-open relevant results on mobile
  let tab = null;
  if (data.cart?.items?.length) tab = "cart";
  else if (data.itinerary?.legs?.length) tab = "itinerary";
  else if (data.hotels?.length) tab = "hotels";
  else if (data.destinations?.length) tab = "destinations";

  if (tab) {
    if (isMobile()) openSheet(tab);
    else switchTab(tab);
  }
}

function favHandlers() {
  return {
    onSelectDestination,
    onSelectHotel,
    onChange: onFavChange,
  };
}

function onFavChange() {
  try { updateFavBadge?.(); } catch (_) {}
  try { renderFavorites?.(favHandlers()); } catch (_) {}
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
  try {
    renderFavorites?.(favHandlers());
  } catch (_) {}
  try {
    renderHistory();
    updateHistoryBadge();
  } catch (_) {}
  updateNavDots();
}

function onSelectDestination(dest) {
  const id = dest.id || dest.destination_id;
  state.selected.destinationId = id;
  state.selected.destinationName = dest.name;
  updateTripSummary();
  renderDestinations(onSelectDestination, onFavChange);
  if (isMobile()) closeSheet();
  sendMessage(`Выбираю направление: ${dest.name}`);
}

function onSelectHotel(hotel) {
  const id = hotelId(hotel);
  state.selected.hotelId = id;
  state.selected.hotelName = hotel.name;
  updateTripSummary();
  renderHotels(onSelectHotel, onFavChange);
  if (isMobile()) closeSheet();
  sendMessage(`Выбираю отель: ${hotel.name}`);
}

function onCheckoutConfirmed(result) {
  toast("Демо: " + (result.booking_id || "OK"));
  state.messages.push({
    role: "agent",
    text: result.message || "Демонстрационное бронирование создано. Реальной оплаты нет.",
  });
  state.stage = "checkout";
  updateStepper();
  updateNavDots();
  renderMessages();
  try {
    renderHistory();
    updateHistoryBadge();
  } catch (_) {}
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
    state.messages.push({ role: "agent", text: data.reply || data.message || "Готово." });
    applyResponse(data);
  } catch (err) {
    hideTyping();
    state.messages.push({
      role: "agent",
      text:
        "Не удалось получить ответ.\n\n" +
        err.message +
        (state.isMock ? "" : "\n\nВключите Mock API в меню ⋯"),
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
      toast(state.isMock ? "Mock API" : "API: " + API_BASE);
    });
  }

  document.getElementById("btnNewSession")?.addEventListener("click", () => {
    const keepMock = state.isMock;
    resetState();
    state.isMock = keepMock;
    closeSheet();
    updateStepper();
    updateTripSummary();
    renderAll();
    toast("Новая сессия");
    if (menu) menu.hidden = true;
  });
}

function boot() {
  initTabs();
  initSheet();
  initMenu();
  initComposer(sendMessage);
  updateStepper();
  updateTripSummary();
  try {
    updateFavBadge?.();
  } catch (_) {}
  renderAll();
}

boot();
