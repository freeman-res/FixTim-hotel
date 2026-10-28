import { state, addPurchase } from "./state.js";
import { formatPrice, confirmCheckout } from "./api.js";

function renderCart(onConfirmed) {
  const empty = document.getElementById("cartEmpty");
  const root = document.getElementById("cartRoot");
  const count = document.getElementById("countCart");

  if (state.demoBooking) {
    if (empty) empty.hidden = true;
    if (count) count.hidden = false;
    root.innerHTML = `
      <div class="cart__success">
        <div class="cart__success-icon">✅</div>
        <h3>Демо-бронирование создано</h3>
        <p>${esc(state.demoBooking.message || "Реальной оплаты не было. Это имитация для хакатона.")}</p>
        <div class="cart__booking-id">${esc(state.demoBooking.booking_id || "DEMO")}</div>
      </div>`;
    return;
  }

  const cart = state.cart;
  if (!cart || !cart.items || !cart.items.length) {
    if (empty) empty.hidden = false;
    if (count) count.hidden = true;
    root.innerHTML = "";
    return;
  }

  if (empty) empty.hidden = true;
  if (count) count.hidden = false;

  let html = `<div class="cart">`;
  html += `<div class="cart__demo-banner">
    <strong>⚠️ Демонстрационное бронирование</strong>
    Реальной оплаты и бронирования не происходит. Данные могут быть синтетическими.
  </div>`;
  html += `<div class="cart__items">`;
  for (const item of cart.items) {
    html += `
      <div class="cart-item">
        <div>
          <div class="cart-item__label">${esc(item.type)}</div>
          <div class="cart-item__name">${esc(item.name)}</div>
        </div>
        <div class="cart-item__price">${item.price != null ? formatPrice(item.price) : "—"}</div>
      </div>`;
  }
  html += `</div>`;
  html += `
    <div class="cart__total">
      <div class="cart__total-label">Итого (известные статьи)</div>
      <div class="cart__total-sum">${formatPrice(cart.total)}</div>
    </div>
    <div class="cart__actions">
      <button type="button" class="btn btn--secondary cart__confirm" id="btnConfirmCheckout">
        Подтвердить демо-бронирование
      </button>
    </div>
  </div>`;

  root.innerHTML = html;

  document.getElementById("btnConfirmCheckout")?.addEventListener("click", async () => {
    const btn = document.getElementById("btnConfirmCheckout");
    if (btn) {
      btn.disabled = true;
      btn.textContent = "Оформляем…";
    }
    try {
      const result = await confirmCheckout();
      state.demoBooking = result;
      try { addPurchase(result); } catch (_) {}
      renderCart(onConfirmed);
      onConfirmed?.(result);
    } catch (err) {
      if (btn) {
        btn.disabled = false;
        btn.textContent = "Подтвердить демо-бронирование";
      }
      alert("Ошибка: " + err.message);
    }
  });
}

function esc(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

export { renderCart };
