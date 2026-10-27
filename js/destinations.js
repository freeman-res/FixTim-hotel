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
    const card = document.createElement("article");
    card.className = "card dest-card" + (selected ? " is-selected" : "");
    card.innerHTML = `
      <div class="dest-card__cover ${cover}">
        <button type="button" class="fav-btn${fav ? " is-active" : ""}" data-action="fav" title="${fav ? "Убрать из избранного" : "В избранное"}" aria-label="Избранное">
          ${fav ? "♥" : "♡"}
        </button>
        <span class="dest-card__cover-emoji">${emojiFor(id)}</span>
        <span class="dest-card__temp">${d.avg_temp_c != null ? d.avg_temp_c + "°C" : "—"}</span>
      </div>
      <div class="card__body">
        <div class="card__title">${esc(d.name)}</div>
        <div class="card__meta">${esc(d.country || "")}</div>
        <div class="dest-card__stats">
          <div class="dest-card__stat">
            <strong>${d.flight_hours != null ? d.flight_hours + " ч" : "—"}</strong>
            <span>в пути</span>
          </div>
          <div class="dest-card__stat">
            <strong>${d.price_from != null ? "от " + formatPrice(d.price_from) : "нет данных"}</strong>
            <span>ориентир</span>
          </div>
        </div>
        <div class="card__tags">
          ${(d.tags || []).map((t) => `<span class="tag">${esc(t)}</span>`).join("")}
          ${d.is_demo ? '<span class="tag tag--demo">синтетика</span>' : ""}
        </div>
        ${d.why ? `<div class="card__why">${esc(d.why)}</div>` : ""}
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

export { renderDestinations };
