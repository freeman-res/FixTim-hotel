import { state } from "./state.js";
import { formatPrice } from "./api.js";

function hotelId(h) {
  return h.hotel_id || h.id;
}

function renderHotels(onSelect) {
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
    const stars = "★".repeat(h.stars || 0) + "☆".repeat(Math.max(0, 5 - (h.stars || 0)));
    const price = h.price_total ?? h.price;
    const card = document.createElement("article");
    card.className = "card hotel-card" + (selected ? " is-selected" : "");
    card.innerHTML = `
      <div class="card__body">
        <div class="hotel-card__header">
          <div class="hotel-card__thumb">🏨</div>
          <div class="hotel-card__info">
            <div class="card__title">${esc(h.name)}</div>
            <div class="hotel-card__stars">${stars}</div>
            <div class="card__meta">${esc(h.city || "")}${h.rating != null ? " · " + h.rating : ""}</div>
            <div class="hotel-card__amenities">
              ${(h.amenities || []).slice(0, 5).map((a) => `<span class="tag">${esc(a)}</span>`).join("")}
            </div>
          </div>
        </div>
        ${h.why ? `<div class="card__why">${esc(h.why)}</div>` : ""}
        <div class="hotel-card__footer">
          <div class="card__price">
            ${price != null ? formatPrice(price) : "нет данных"}
            <span>${h.nights ? " / " + h.nights + " ноч." : ""}</span>
          </div>
          <div class="card__tags">
            ${h.is_demo ? '<span class="tag tag--demo">синтетика</span>' : ""}
          </div>
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
    root.appendChild(card);
  }
}

function esc(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

export { renderHotels, hotelId };
