


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
import { applyServerResponse } from "./response.js";

const STAGE_ORDER = ["inspiration", "destinations", "hotels", "itinerary", "checkout"];
const TAB_TITLES = {
  destinations: "Направления",
  hotels: "Отели",
  itinerary: "Маршрут",
  cart: "Корзина",
  favorites: "Избранное",
  history: "История демо-заказов",
};

function isMobile() {
  return window.matchMedia("(max-width: 899px)").matches;
}


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
    const dy = startY - clientY;
    setSheetHeight(startH + dy, false);
  }

  function onEnd() {
    if (!dragging) return;
    dragging = false;
    side.classList.remove("is-dragging");
    const h = side.getBoundingClientRect().height;
    const ratio = h / vh();

    if (ratio < 0.2) {
      closeSheet();
      sheetHeightRatio = SHEET_SNAPS.mid;
      return;
    }

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


function initTabs() {
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach((t) => t.classList.remove("is-active"));
      document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("is-active"));
      tab.classList.add("is-active");
      tab.scrollIntoView({ block: "nearest", inline: "nearest", behavior: "auto" });
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
  if (priceEl) {
    priceEl.textContent = hasCart ? formatPrice(state.cart.total) : "";
    priceEl.title = hasCart && !state.cart.complete ? "Сумма известных расходов" : "";
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
  }, 2800);
}

function applyResponse(data, { openResults = true } = {}) {
  const tab = applyServerResponse(state, data);

  updateStepper();
  updateTripSummary();
  updateNavDots();
  renderAll();


  if (tab && openResults) {
    if (isMobile()) openSheet(tab);
    else switchTab(tab);
  }
}

function favHandlers() {
  return {
    onSelectDestination,
    onSelectHotel,
    onSearchFavoriteHotel,
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
  renderItinerary(onSelectTransport);
  renderCart(onCheckoutConfirmed, onSearchReturn);
  try {
    renderFavorites?.(favHandlers());
  } catch (_) {}
  renderHistory();
  updateHistoryBadge();
  updateNavDots();
}

function onSelectDestination(dest) {
  const id = dest.id || dest.destination_id;
  if (state.isMock) {
    state.selected.destinationId = id;
    state.selected.destinationName = dest.name;
    updateTripSummary();
    renderDestinations(onSelectDestination, onFavChange);
  }
  if (isMobile()) closeSheet();
  sendMessage(`Выбираю направление: ${dest.name}`,
    state.isMock ? null : { action: "select_destination", target_id: id });
}

function onSelectHotel(hotel) {
  const id = hotelId(hotel);
  if (state.isMock) {
    state.selected.hotelId = id;
    state.selected.hotelName = hotel.name;
    updateTripSummary();
    renderHotels(onSelectHotel, onFavChange);
  }
  if (isMobile()) closeSheet();
  sendMessage(`Выбираю отель: ${hotel.name}`,
    state.isMock ? null : { action: "select_hotel", target_id: id });
}

function onSearchFavoriteHotel(hotel) {
  if (isMobile()) closeSheet();
  const city = hotel.city || hotel.location?.city;
  sendMessage(city ? `Найди отели в ${city}. Интересует «${hotel.name}».` :
    `Найди отель «${hotel.name}».`);
}

function onSelectTransport(option) {
  if (isMobile()) closeSheet();
  sendMessage(`Выбираю дорогу: ${(option.from || {}).city || ""} — ${(option.to || {}).city || ""}`,
    { action: option.trip_leg === "return" ? "select_return_transport" : "select_transport",
      target_id: option.transport_id });
}

function onSearchReturn(day) {
  sendMessage(`Найди обратную дорогу на ${day}`,
    { action: "search_return_transport", target_id: day });
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
  renderHistory();
  updateHistoryBadge();
}

async function sendMessage(text, selection = null) {
  if (state.isLoading) return;
  state.messages.push({ role: "user", text });
  renderMessages();
  setLoading(true);
  showTyping();
  try {
    const data = await postChat(text, selection);
    hideTyping();
    state.messages.push({ role: "agent", text: data.reply || data.message || "Готово." });
    applyResponse(data, { openResults: selection?.action !== "select_hotel" });
  } catch (err) {
    hideTyping();
    state.messages.push({
      role: "agent",
      text:
        "Не удалось получить ответ.\n\n" +
        (state.isMock ? err.message : "Сервис сейчас недоступен. Попробуйте повторить запрос."),
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
      resetState();
      state.isMock = mockToggle.checked;
      closeSheet();
      updateStepper();
      updateTripSummary();
      renderAll();
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
  document.getElementById("btnHistory")?.addEventListener("click", () => {
    if (isMobile()) openSheet("history");
    else switchTab("history");
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
