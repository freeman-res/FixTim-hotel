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
    return d.toLocaleString("ru-RU", {
      day: "numeric",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso || "";
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
            it.price != null ? formatPrice(it.price) : "—"
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
            <div class="card__price">${p.total != null ? formatPrice(p.total) : "—"}</div>
          </div>
          ${p.hotel ? `<div class="history-card__hotel">🏨 ${esc(p.hotel)}</div>` : ""}
          <div class="history-card__id">№ ${esc(p.id)}</div>
          ${items ? `<div class="history-card__items">${items}</div>` : ""}
          ${p.is_demo ? '<span class="tag tag--demo">демо</span>' : ""}
        </div>
      </article>`;
  }
  html += `</div>
    <button type="button" class="btn btn--ghost btn--block" id="btnClearHistory" style="margin-top:12px">
      Очистить историю
    </button>`;

  root.innerHTML = html;

  document.getElementById("btnClearHistory")?.addEventListener("click", () => {
    if (!confirm("Удалить всю историю покупок с этого устройства?")) return;
    clearPurchaseHistory();
    renderHistory();
  });
}

export { renderHistory, updateHistoryBadge };
