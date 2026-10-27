import { state } from "./state.js";

const messagesEl = () => document.getElementById("messages");
const inputEl = () => document.getElementById("input");
const btnSend = () => document.getElementById("btnSend");

const SCENARIOS = [
  {
    cover: "scenario__cover--sea",
    emoji: "🌊",
    name: "Море в ноябре",
    desc: "5 дней · из Москвы · до 80 000 ₽",
    text: "Хочу на море на 5 дней в ноябре, из Москвы, бюджет до 80 тысяч",
  },
  {
    cover: "scenario__cover--city",
    emoji: "🏛",
    name: "Питер на выходные",
    desc: "2 ночи · на двоих · недорого",
    text: "Выходные в Питере на двоих, интересно и недорого",
  },
  {
    cover: "scenario__cover--mount",
    emoji: "⛰",
    name: "Горы и воздух",
    desc: "Кисловодск · спокойный отдых",
    text: "Хочу в горы, Кисловодск или Минводы, на неделю",
  },
];

function renderWelcome(onScenario) {
  const root = messagesEl();
  root.innerHTML = `
    <div class="welcome">
      <div class="welcome__title">Спланируем поездку<br><span>одним запросом</span></div>
      <p class="welcome__sub">
        Напишите, куда и когда хотите поехать — подберу направления, отели, маршрут
        и доведу до демо-бронирования. Можно без точных дат.
      </p>
      <div class="welcome__grid">
        ${SCENARIOS.map(
          (s, i) => `
          <button type="button" class="scenario" data-idx="${i}">
            <div class="scenario__cover ${s.cover}"><span class="scenario__cover-label">${s.emoji}</span></div>
            <div class="scenario__body">
              <div class="scenario__name">${s.name}</div>
              <div class="scenario__desc">${s.desc}</div>
            </div>
          </button>`
        ).join("")}
      </div>
    </div>
  `;
  root.querySelectorAll(".scenario").forEach((btn) => {
    btn.addEventListener("click", () => {
      const s = SCENARIOS[Number(btn.dataset.idx)];
      if (s) onScenario(s.text);
    });
  });
}

function renderMessages() {
  const root = messagesEl();
  if (state.messages.length === 0) return;

  root.innerHTML = "";
  for (const m of state.messages) {
    const div = document.createElement("div");
    div.className = `msg msg--${m.role}`;
    const avatar = m.role === "agent" ? "О!" : "Вы";
    div.innerHTML = `
      <div class="msg__row">
        <div class="msg__avatar">${avatar}</div>
        <div class="msg__bubble"></div>
      </div>
      <div class="msg__meta">${m.role === "user" ? "вы" : "агент"}</div>
    `;
    div.querySelector(".msg__bubble").textContent = m.text;
    root.appendChild(div);
  }
  root.scrollTop = root.scrollHeight;
}

function showTyping() {
  const root = messagesEl();
  const el = document.createElement("div");
  el.className = "msg msg--agent";
  el.id = "typingIndicator";
  el.innerHTML = `
    <div class="msg__row">
      <div class="msg__avatar">О!</div>
      <div class="typing"><span></span><span></span><span></span></div>
    </div>`;
  root.appendChild(el);
  root.scrollTop = root.scrollHeight;
}

function hideTyping() {
  document.getElementById("typingIndicator")?.remove();
}

function setLoading(loading) {
  state.isLoading = loading;
  const btn = btnSend();
  const input = inputEl();
  if (btn) btn.disabled = loading || !(input?.value || "").trim();
  if (input) input.disabled = loading;
}

function autoResize() {
  const el = inputEl();
  if (!el) return;
  el.style.height = "auto";
  el.style.height = Math.min(el.scrollHeight, 120) + "px";
}

function initComposer(onSubmit) {
  const form = document.getElementById("composer");
  const input = inputEl();
  const btn = btnSend();

  input.addEventListener("input", () => {
    autoResize();
    btn.disabled = state.isLoading || !input.value.trim();
  });

  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (!btn.disabled) form.requestSubmit();
    }
  });

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const text = input.value.trim();
    if (!text || state.isLoading) return;
    input.value = "";
    autoResize();
    btn.disabled = true;
    onSubmit(text);
  });

  document.getElementById("hints")?.addEventListener("click", (e) => {
    const h = e.target.closest(".hint");
    if (!h) return;
    input.value = h.dataset.text || "";
    autoResize();
    btn.disabled = state.isLoading || !input.value.trim();
    input.focus();
  });
}

export {
  renderWelcome,
  renderMessages,
  showTyping,
  hideTyping,
  setLoading,
  initComposer,
};
