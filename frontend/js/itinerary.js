import { state } from "./state.js";
import { formatPrice } from "./api.js";

function transportFacts(option) {
  if (option.record_kind === "live_offer" &&
      typeof option.price?.amount_min_rub === "number") {
    return { amount: option.price.amount_min_rub, label: "", isOffer: true };
  }
  const amount = option.price_estimate?.amount_rub ?? option.price?.amount_min_rub ?? null;
  return { amount: typeof amount === "number" ? amount : null, label: "", isOffer: false };
}

const DATA_CAVEAT = /не\s+подтвержд|подтвержд[её]н\w*\s+(?:вариант|цен|налич|распис|рейс|билет)|(?:цен|стоимост|налич|расписан|доступност)\w*.{0,60}(?:не\s+указ|не\s+подтвержд|пока\s+нет|требует\s+провер)|(?:примерн|расч[её]тн|справочн)\w*.{0,30}(?:цен|стоимост)|(?:цен|стоимост)\w*.{0,30}(?:оценк|примерн)|датасет\w*.{0,40}(?:провер|актуальн)|проверьте\s+итогов\w*.{0,50}(?:перед\s+покупк|перед\s+бронир)/i;

function displayableWarnings(warnings = []) {
  return warnings.filter((item) => {
    const level = typeof item === "object" ? item.level : "info";
    const text = typeof item === "string" ? item : item?.text || "";
    return ["warning", "danger"].includes(level) && !DATA_CAVEAT.test(text);
  });
}

function renderItinerary(onSelectTransport) {
  const empty = document.getElementById("itinEmpty");
  const root = document.getElementById("itineraryRoot");
  const itin = state.itinerary;
  const transport = state.transportOptions || [];

  if (!itin?.legs?.length && !transport.length) {
    if (empty) empty.hidden = false;
    root.innerHTML = "";
    return;
  }
  if (empty) empty.hidden = true;

  const typeLabel = {
    flight: "Перелёт",
    transfer: "Трансфер",
    hotel: "Отель",
    train: "Поезд",
  };

  let html = `<div class="itin">`;
  for (const leg of itin?.legs || []) {
    html += `
      <div class="itin__leg">
        <div class="itin__dot"></div>
        <div class="itin__body">
          <div class="itin__type">${esc(typeLabel[leg.type] || leg.type)}</div>
          <div class="itin__title">${esc(leg.title)}</div>
          <div class="itin__detail">${esc(leg.detail || "")}</div>
          ${leg.time ? `<div class="itin__time">${esc(leg.time)}</div>` : ""}
        </div>
      </div>`;
  }
  html += `</div>`;

  if (transport.length) {
    html += `<div class="transport-results"><h3>${transport.some((item) => item.trip_leg === "return") ? "Обратная дорога" : "Варианты дороги"}</h3>`;
    const typeNames = { plane: "Самолёт", train: "Поезд", bus: "Автобус" };
    for (const option of transport) {
      const facts = transportFacts(option);
      const from = option.from?.city || "Отправление";
      const to = option.to?.city || "прибытие";
      const day = option.schedule_date || "";
      const timing = [day, option.departure_utc].filter(Boolean).join(" · ");
      const url = typeof option.booking_url === "string" &&
        option.booking_url.startsWith("https://") && facts.isOffer ? option.booking_url : null;
      const selected = option.trip_leg === "return"
        ? state.selected.returnTransportId === option.transport_id
        : state.selected.transportId === option.transport_id;
      html += `<article class="transport-card">
        <div class="transport-card__type">${esc(typeNames[option.type] || option.type || "Транспорт")}</div>
        <strong>${esc(from)} → ${esc(to)}</strong>
        ${timing ? `<div class="transport-card__meta">${esc(timing)}</div>` : ""}
        ${facts.amount != null ? `<div class="transport-card__price">${formatPrice(facts.amount)}</div>` : ""}
        ${url ? `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">Проверить у источника</a>` : ""}
        ${option.transport_id ? `<button type="button" class="btn btn--primary btn--sm" data-action="select-transport" data-transport-id="${esc(option.transport_id)}">${selected ? "Добавлено ✓" : option.trip_leg === "return" ? "Выбрать обратный билет" : "Добавить в маршрут"}</button>` : ""}
      </article>`;
    }
    html += `</div>`;
  }

  const warnings = displayableWarnings(state.warnings || []);
  if (warnings.length) {
    html += `<div class="warnings">`;
    for (const w of warnings) {
      const text = typeof w === "string" ? w : w.text || "";
      const level = typeof w === "object" ? w.level : "info";
      const cls = level === "danger" ? "warning warning--danger" : "warning";
      html += `<div class="${cls}"><strong>Внимание</strong>${esc(text)}</div>`;
    }
    html += `</div>`;
  }
  root.innerHTML = html;
  root.querySelectorAll('[data-action="select-transport"]').forEach((button) => {
    button.addEventListener("click", () => {
      const option = transport.find((item) => item.transport_id === button.dataset.transportId);
      if (option) onSelectTransport?.(option);
    });
  });
}

function esc(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

export { renderItinerary, transportFacts, displayableWarnings };
