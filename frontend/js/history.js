import {
  state,
  clearPurchaseHistory,
  purchaseHistoryCount,
} from "./state.js";
import { formatPrice } from "./api.js";

function esc(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function formatDate(iso) {
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return "Дата неизвестна";
    return d.toLocaleString("ru-RU", {
      day: "numeric",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return "Дата неизвестна";
  }
}

function updateHistoryBadge() {
  const n = purchaseHistoryCount();
  const el = document.getElementById("countHistory");
  if (el) {
    if (n > 0) {
      el.hidden = false;
      el.textContent = String(n);
    } else {
      el.hidden = true;
    }
  }
}

function renderHistory() {
  const empty = document.getElementById("historyEmpty");
  const root = document.getElementById("historyRoot");
  if (!root) return;

  updateHistoryBadge();
  const list = state.purchaseHistory || [];

  if (!list.length) {
    if (empty) empty.hidden = false;
    root.innerHTML = "";
    return;
  }
  if (empty) empty.hidden = true;

  let html = `<div class="history-list">`;
  for (const p of list) {
    const items = (p.items || [])
      .map(
        (it) =>
          `<div class="history-item__row"><span>${esc(it.name || it.type)}</span><span>${
            it.price != null ? formatPrice(it.price, it.currency || "RUB") : ""
          }</span></div>`
      )
      .join("");
    html += `
      <article class="card history-card">
        <div class="card__body">
          <div class="history-card__top">
            <div>
              <div class="card__title">${esc(p.destination || "Поездка")}</div>
              <div class="card__meta">${esc(formatDate(p.created_at))}</div>
            </div>
            <div class="card__price">${p.total != null ? formatPrice(p.total, p.currency || "RUB") : ""}</div>
          </div>
          ${p.hotel ? `<div class="history-card__hotel">🏨 ${esc(p.hotel)}</div>` : ""}
          <div class="history-card__id">№ ${esc(p.id)}</div>
          ${items ? `<div class="history-card__items">${items}</div>` : ""}
          ${p.scope === "outbound_transport_and_hotel_only" ? '<div class="history-card__scope">Только дорога туда и проживание</div>' : ""}
          <span class="tag tag--demo">Демо, без оплаты</span>
        </div>
      </article>`;
  }
  html += `</div>
    <button type="button" class="btn btn--ghost btn--block" id="btnClearHistory" style="margin-top:12px">
      Очистить историю
    </button>`;

  root.innerHTML = html;

  document.getElementById("btnClearHistory")?.addEventListener("click", () => {
    if (!confirm("Удалить историю демо-заказов с этого устройства?")) return;
    clearPurchaseHistory();
    renderHistory();
  });
}

export { renderHistory, updateHistoryBadge };
