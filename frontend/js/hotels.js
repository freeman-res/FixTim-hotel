import {
  state,
  isFavHotel,
  toggleFavoriteHotel,
} from "./state.js";
import { formatPrice } from "./api.js";

function hotelId(h) {
  return h.hotel_id || h.id;
}

function hotelDisplayPrice(h) {
  const total = h.total_price ?? h.price_total ??
    (typeof h.price === "number" ? h.price : null);
  if (typeof total === "number" && Number.isFinite(total)) {
    return { amount: total, currency: h.currency || "RUB", label: "за проживание" };
  }
  const amount = h.price_estimate?.amount_rub ?? h.price_estimate?.amount ?? null;
  if (typeof amount === "number" && Number.isFinite(amount)) {
    return { amount, currency: "RUB",
      label: h.price_estimate?.unit === "per_night" ? "за ночь" : "" };
  }
  return { amount: null, currency: h.currency || "RUB", label: "" };
}

function hotelStarLabel(h) {
  if (!Number.isInteger(h.stars) || h.stars < 1 || h.stars > 5) {
    return "";
  }
  return "★".repeat(h.stars) + "☆".repeat(5 - h.stars);
}

function displayHotelReason(text) {
  const caveat = /не\s+подтвержд|не\s+указан|нет\s+данных|не\s+проверен|примерн|средним\s+данным|наличи[ея]|тариф\w*|актуальн\w*/i;
  return String(text || "").split(";").map((part) => part.trim())
    .filter((part) => part && !caveat.test(part)).join("; ");
}

function renderHotels(onSelect, onFavChange) {
  const empty = document.getElementById("hotelsEmpty");
  const root = document.getElementById("hotelCards");
  const count = document.getElementById("countHotels");
  const list = state.hotels || [];

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

  for (const h of list) {
    const id = hotelId(h);
    const selected = state.selected.hotelId === id;
    const fav = isFavHotel(h);
    const stars = hotelStarLabel(h);
    const price = hotelDisplayPrice(h);
    const card = document.createElement("article");
    card.className = "card hotel-card" + (selected ? " is-selected" : "");
    card.innerHTML = `
      <div class="card__body">
        <div class="hotel-card__header">
          <div class="hotel-card__thumb">🏨</div>
          <div class="hotel-card__info">
            <div class="card__title-row">
              <div class="card__title">${esc(h.name)}</div>
              <button type="button" class="fav-btn fav-btn--inline${fav ? " is-active" : ""}" data-action="fav" title="${fav ? "Убрать из избранного" : "В избранное"}" aria-label="Избранное">
                ${fav ? "♥" : "♡"}
              </button>
            </div>
            <div class="hotel-card__stars">${stars}</div>
            <div class="card__meta">${esc(h.city || "")}${h.rating != null ? " · " + h.rating : ""}</div>
            <div class="hotel-card__amenities">
              ${(h.amenities || []).slice(0, 5).map((a) => `<span class="tag">${esc(a)}</span>`).join("")}
            </div>
          </div>
        </div>
        ${displayHotelReason(h.reason || h.why) ? `<div class="card__why">${esc(displayHotelReason(h.reason || h.why))}</div>` : ""}
        <div class="hotel-card__footer">
          ${price.amount != null ? `<div class="card__price">${formatPrice(price.amount, price.currency)}<span> ${esc(price.label)}</span></div>` : ""}
        </div>
        <div class="card__actions">
          <button type="button" class="btn btn--primary btn--sm" data-action="select">
            ${selected ? "Выбрано ✓" : "Выбрать"}
          </button>
        </div>
      </div>
    `;
    card.querySelector('[data-action="select"]').addEventListener("click", (e) => {
      e.stopPropagation();
      onSelect(h);
    });
    card.querySelector('[data-action="fav"]').addEventListener("click", (e) => {
      e.stopPropagation();
      const nowFav = toggleFavoriteHotel(h);
      onFavChange?.(nowFav);
    });
    root.appendChild(card);
  }
}

function esc(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

export { renderHotels, hotelId, hotelDisplayPrice, hotelStarLabel, displayHotelReason };
