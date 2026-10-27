import { state } from "./state.js";

function renderItinerary() {
  const empty = document.getElementById("itinEmpty");
  const root = document.getElementById("itineraryRoot");
  const itin = state.itinerary;

  if (!itin || !itin.legs || !itin.legs.length) {
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
  for (const leg of itin.legs) {
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

  const warnings = state.warnings || [];
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
}

function esc(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

export { renderItinerary };
