import {
  state,
  isFavDestination,
  isFavHotel,
  toggleFavoriteDestination,
  toggleFavoriteHotel,
  favoritesCount,
  destKey,
  hotelKey,
} from "./state.js";
import { formatPrice } from "./api.js";

function esc(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function updateFavBadge() {
  const badge = document.getElementById("countFav");
  const n = favoritesCount();
  if (!badge) return;
  if (n > 0) {
    badge.hidden = false;
    badge.textContent = String(n);
  } else {
    badge.hidden = true;
  }
}

/**
 * @param {{ onSelectDestination: Function, onSelectHotel: Function, onChange: Function }} handlers
 */
function renderFavorites(handlers) {
  const empty = document.getElementById("favEmpty");
  const root = document.getElementById("favRoot");
  if (!root) return;

  updateFavBadge();

  const dests = state.favorites.destinations || [];
  const hotels = state.favorites.hotels || [];
  const total = dests.length + hotels.length;

  if (!total) {
    if (empty) empty.hidden = false;
    root.innerHTML = "";
    return;
  }
  if (empty) empty.hidden = true;

  let html = "";

  if (dests.length) {
    html += `<div class="fav-section"><h4 class="fav-section__title">Направления · ${dests.length}</h4><div class="fav-list">`;
    for (const d of dests) {
      const id = destKey(d);
      html += `
        <div class="fav-item" data-type="destination" data-id="${esc(id)}">
          <div class="fav-item__body">
            <div class="fav-item__title">${esc(d.name)}</div>
            <div class="fav-item__meta">
              ${d.avg_temp_c != null ? d.avg_temp_c + "°C" : ""}
              ${d.flight_hours != null ? " · ~" + d.flight_hours + " ч" : ""}
              ${d.price_from != null ? " · от " + formatPrice(d.price_from) : ""}
            </div>
          </div>
          <div class="fav-item__actions">
            <button type="button" class="btn btn--primary btn--sm" data-action="select">Выбрать</button>
            <button type="button" class="btn btn--ghost btn--sm" data-action="remove" title="Убрать">♡</button>
          </div>
        </div>`;
    }
    html += `</div></div>`;
  }

  if (hotels.length) {
    html += `<div class="fav-section"><h4 class="fav-section__title">Отели · ${hotels.length}</h4><div class="fav-list">`;
    for (const h of hotels) {
      const id = hotelKey(h);
      const price = h.price_total ?? h.price;
      html += `
        <div class="fav-item" data-type="hotel" data-id="${esc(id)}">
          <div class="fav-item__body">
            <div class="fav-item__title">${esc(h.name)}</div>
            <div class="fav-item__meta">
              ${esc(h.city || "")}
              ${price != null ? " · " + formatPrice(price) : ""}
              ${h.nights ? " / " + h.nights + " ноч." : ""}
            </div>
          </div>
          <div class="fav-item__actions">
            <button type="button" class="btn btn--primary btn--sm" data-action="select">Выбрать</button>
            <button type="button" class="btn btn--ghost btn--sm" data-action="remove" title="Убрать">♡</button>
          </div>
        </div>`;
    }
    html += `</div></div>`;
  }

  root.innerHTML = html;

  root.querySelectorAll(".fav-item").forEach((row) => {
    const type = row.dataset.type;
    const id = row.dataset.id;
    row.querySelector('[data-action="select"]')?.addEventListener("click", () => {
      if (type === "destination") {
        const d = dests.find((x) => destKey(x) === id);
        if (d) handlers.onSelectDestination(d);
      } else {
        const h = hotels.find((x) => hotelKey(x) === id);
        if (h) handlers.onSelectHotel(h);
      }
    });
    row.querySelector('[data-action="remove"]')?.addEventListener("click", () => {
      if (type === "destination") {
        const d = dests.find((x) => destKey(x) === id);
        if (d) toggleFavoriteDestination(d);
      } else {
        const h = hotels.find((x) => hotelKey(x) === id);
        if (h) toggleFavoriteHotel(h);
      }
      handlers.onChange?.();
    });
  });
}

export { renderFavorites, updateFavBadge };
