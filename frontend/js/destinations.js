import {
  state,
  isFavDestination,
  toggleFavoriteDestination,
} from "./state.js";
import { formatPrice } from "./api.js";

const COVER = {
  sochi: "cover-sochi",
  kaliningrad: "cover-kaliningrad",
  mineralnye: "cover-mineralnye",
  spb: "cover-spb",
};

function destinationFacts(destination) {
  const transport = destination.transport_available || {};
  return {
    tempC: destination.climate?.temp_mean_c ?? destination.avg_temp_c ?? null,
    transportTypes: Array.isArray(transport.types) ? transport.types : [],
  };
}

function renderDestinations(onSelect, onFavChange) {
  const empty = document.getElementById("destEmpty");
  const root = document.getElementById("destCards");
  const count = document.getElementById("countDest");
  const list = state.destinations || [];

  if (count) {
    if (list.length) {
      count.hidden = false;
      count.textContent = String(list.length);
    } else count.hidden = true;
  }

  if (!list.length) {
    if (empty) empty.hidden = false;
    root.innerHTML = "";
    return;
  }
  if (empty) empty.hidden = true;
  root.innerHTML = "";

  for (const d of list) {
    const id = d.id || d.destination_id;
    const cover = COVER[id] || "cover-default";
    const selected = state.selected.destinationId === id;
    const fav = isFavDestination(d);
    const facts = destinationFacts(d);
    const transportLabels = { plane: "самолёт", train: "поезд", bus: "автобус" };
    const transportText = facts.transportTypes.map((item) => transportLabels[item] || item).join(", ") ||
      (d.flight_hours != null ? `${d.flight_hours} ч` : "");
    const card = document.createElement("article");
    card.className = "card dest-card" + (selected ? " is-selected" : "");
    card.innerHTML = `
      <div class="dest-card__cover ${cover}">
        <button type="button" class="fav-btn${fav ? " is-active" : ""}" data-action="fav" title="${fav ? "Убрать из избранного" : "В избранное"}" aria-label="Избранное">
          ${fav ? "♥" : "♡"}
        </button>
        <span class="dest-card__cover-emoji">${emojiFor(id)}</span>
        ${facts.tempC != null ? `<span class="dest-card__temp">${facts.tempC}°C</span>` : ""}
      </div>
      <div class="card__body">
        <div class="card__title">${esc(d.name)}</div>
        <div class="card__meta">${esc(d.region || d.country || "")}</div>
        ${transportText ? `<div class="dest-card__stats"><div class="dest-card__stat"><strong>${esc(transportText)}</strong><span>транспорт</span></div></div>` : ""}
        <div class="card__tags">
          ${(d.tags || []).map((t) => `<span class="tag">${esc(t)}</span>`).join("")}
        </div>
        ${d.why ? `<div class="card__why">${esc(d.why)}</div>` : ""}
        ${d.climate?.temp_mean_c != null ? '<div class="card__why">Средняя температура за месяц</div>' : ""}
        <div class="card__actions">
          <button type="button" class="btn btn--primary btn--sm" data-action="select">
            ${selected ? "Выбрано ✓" : "Выбрать"}
          </button>
        </div>
      </div>
    `;
    card.querySelector('[data-action="select"]').addEventListener("click", (e) => {
      e.stopPropagation();
      onSelect(d);
    });
    card.querySelector('[data-action="fav"]').addEventListener("click", (e) => {
      e.stopPropagation();
      const nowFav = toggleFavoriteDestination(d);
      onFavChange?.(nowFav);
    });
    root.appendChild(card);
  }
}

function emojiFor(id) {
  return { sochi: "🌊", kaliningrad: "🏰", mineralnye: "⛰", spb: "🏛" }[id] || "📍";
}

function esc(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

export { renderDestinations, destinationFacts };
