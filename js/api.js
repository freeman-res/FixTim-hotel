/**
 * API client aligned with backend ChatRequest / ChatResponse.
 * POST /api/v1/chat  { session_id?, message }
 * Response excludes updated_state (backend stores it).
 */
import { state } from "./state.js";

const API_BASE = localStorage.getItem("ostrovok_api_base") || "http://localhost:8000";

function formatPrice(n) {
  if (n == null || Number.isNaN(Number(n))) return "нет данных";
  return new Intl.NumberFormat("ru-RU").format(Math.round(Number(n))) + " ₽";
}

async function postChat(message) {
  if (state.isMock) return mockChat(message);

  const body = { message };
  if (state.sessionId) body.session_id = state.sessionId;

  const res = await fetch(`${API_BASE}/api/v1/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${text || res.statusText}`);
  }
  return res.json();
}

async function confirmCheckout() {
  if (state.isMock) {
    await delay(700);
    return {
      status: "ok",
      is_demo: true,
      booking_id: "DEMO-" + Math.random().toString(36).slice(2, 8).toUpperCase(),
      message: "Демонстрационное бронирование создано. Реальной оплаты нет.",
    };
  }
  const res = await fetch(`${API_BASE}/api/v1/checkout/confirm`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: state.sessionId }),
  });
  if (!res.ok) throw new Error(`Checkout failed: ${res.status}`);
  return res.json();
}

function delay(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

/* ---------- Mock agent (full scenario) ---------- */

const MOCK_DESTINATIONS = [
  {
    id: "sochi",
    name: "Сочи",
    country: "Россия",
    why: "Тёплое море ещё возможно, короткий перелёт из Москвы, много отелей у воды.",
    flight_hours: 2.5,
    avg_temp_c: 16,
    price_from: 42000,
    currency: "RUB",
    tags: ["море", "короткий перелёт"],
    is_demo: true,
  },
  {
    id: "kaliningrad",
    name: "Калининград",
    country: "Россия",
    why: "Европейская атмосфера и янтарь. Чуть дешевле Сочи при похожем перелёте.",
    flight_hours: 2.2,
    avg_temp_c: 8,
    price_from: 35000,
    currency: "RUB",
    tags: ["город", "история"],
    is_demo: true,
  },
  {
    id: "mineralnye",
    name: "Кисловодск",
    country: "Россия",
    why: "Горы и воздух. Если море не критично — спокойный отдых и природа.",
    flight_hours: 2.5,
    avg_temp_c: 10,
    price_from: 28000,
    currency: "RUB",
    tags: ["горы", "оздоровление"],
    is_demo: true,
  },
];

const MOCK_HOTELS = {
  sochi: [
    {
      hotel_id: "h_sochi_1",
      id: "h_sochi_1",
      name: "Palm Beach Resort",
      stars: 4,
      city: "Сочи",
      price: 28500,
      price_total: 28500,
      currency: "RUB",
      nights: 5,
      amenities: ["бассейн", "завтрак", "wi-fi", "парковка"],
      rating: 4.6,
      why: "Близко к морю, хороший завтрак. Компромисс — шумнее вечером у бара.",
      is_demo: true,
    },
    {
      hotel_id: "h_sochi_2",
      id: "h_sochi_2",
      name: "Riviera Guest House",
      stars: 3,
      city: "Сочи",
      price: 18900,
      price_total: 18900,
      currency: "RUB",
      nights: 5,
      amenities: ["завтрак", "wi-fi", "pet-friendly"],
      rating: 4.3,
      why: "Дешевле и тише. ~15 мин до пляжа. Подходит при ограниченном бюджете и с питомцем.",
      is_demo: true,
    },
  ],
  kaliningrad: [
    {
      hotel_id: "h_kld_1",
      id: "h_kld_1",
      name: "Amber Hotel",
      stars: 4,
      city: "Калининград",
      price: 22000,
      price_total: 22000,
      currency: "RUB",
      nights: 5,
      amenities: ["завтрак", "wi-fi", "центр"],
      rating: 4.7,
      why: "В центре, рядом с островом Канта. Сильный завтрак по отзывам.",
      is_demo: true,
    },
  ],
  mineralnye: [
    {
      hotel_id: "h_min_1",
      id: "h_min_1",
      name: "Park Hotel Kislovodsk",
      stars: 4,
      city: "Кисловодск",
      price: 19500,
      price_total: 19500,
      currency: "RUB",
      nights: 5,
      amenities: ["спа", "завтрак", "парк"],
      rating: 4.5,
      why: "Рядом с курортным парком. Тихо, для спокойного отдыха.",
      is_demo: true,
    },
  ],
  spb: [
    {
      hotel_id: "h_spb_1",
      id: "h_spb_1",
      name: "Nevsky Central",
      stars: 4,
      city: "Санкт-Петербург",
      price: 12400,
      price_total: 12400,
      currency: "RUB",
      nights: 2,
      amenities: ["завтрак", "wi-fi", "центр"],
      rating: 4.5,
      why: "Рядом с Невским. Удобно без машины на выходные.",
      is_demo: true,
    },
  ],
};

function detectIntent(text) {
  const t = text.toLowerCase();
  if (/позже|сдвин|перенес|на два дня|на 2 дня/.test(t)) return "reschedule";
  if (/собак|питомц|с нами собака/.test(t)) return "pets";
  if (/бюджет|дешевле|меньше денег|уреза/.test(t)) return "budget";
  if (/питер|санкт|спб/.test(t)) return "spb";
  if (/море|сочи|пляж|тёпл|тепл/.test(t)) return "sea";
  if (/калининград|янтар/.test(t)) return "kld";
  if (/гор|кисловодск|минерал/.test(t)) return "mountains";
  if (/выбр|беру|этот отель|этот вариант|давай так|направление/.test(t)) return "select";
  if (/купи|оплат|бронир|оформ|корзин/.test(t)) return "checkout";
  return "general";
}

function buildItinerary(destId, shifted) {
  const offset = shifted ? 2 : 0;
  const names = {
    sochi: "Сочи",
    kaliningrad: "Калининград",
    mineralnye: "Кисловодск",
    spb: "Санкт-Петербург",
  };
  const city = names[destId] || "Сочи";
  return {
    legs: [
      { type: "flight", title: `Вылет Москва → ${city}`, detail: "Прямой рейс · ~2.5 ч", time: `${10 + offset} ноя, 08:40` },
      { type: "transfer", title: "Трансфер аэропорт → отель", detail: "Такси / шаттл · ~40 мин", time: `${10 + offset} ноя, ~12:00` },
      { type: "hotel", title: `Заселение · ${city}`, detail: "Check-in с 14:00", time: `${10 + offset} ноя, 14:00` },
      { type: "hotel", title: "Выезд", detail: "Check-out до 12:00", time: `${15 + offset} ноя, 12:00` },
      { type: "flight", title: `Обратный рейс ${city} → Москва`, detail: "Прямой рейс · ~2.5 ч", time: `${15 + offset} ноя, 16:20` },
    ],
  };
}

function buildCart(hotelId, shifted) {
  const all = Object.values(MOCK_HOTELS).flat();
  const hotel = all.find((h) => (h.id || h.hotel_id) === hotelId) || all[0];
  const flight = shifted ? 12500 : 11800;
  const transfer = 1800;
  const hotelPrice = hotel ? Math.round((hotel.price_total || hotel.price || 20000) * (shifted ? 1.04 : 1)) : 20000;
  return {
    items: [
      { type: "flight", name: "Авиабилеты туда-обратно (2 взр.)", price: flight * 2, currency: "RUB" },
      { type: "hotel", name: hotel ? hotel.name : "Отель", price: hotelPrice, currency: "RUB" },
      { type: "transfer", name: "Трансферы (2)", price: transfer * 2, currency: "RUB" },
    ],
    total: flight * 2 + hotelPrice + transfer * 2,
    currency: "RUB",
    is_demo: true,
  };
}

async function mockChat(message) {
  await delay(800 + Math.random() * 500);
  if (!state.sessionId) state.sessionId = "mock_" + Date.now().toString(36);

  const intent = detectIntent(message);

  if (intent === "reschedule") {
    const destId = state.selected.destinationId || "sochi";
    const hotelId = state.selected.hotelId || "h_sochi_1";
    return {
      session_id: state.sessionId,
      status: "results",
      stage: "itinerary",
      reply:
        "Сдвинул поездку на два дня позже.\n\n• Вылет: было 10 ноя → стало 12 ноя\n• Заселение: 12 ноя\n• Выезд: 17 ноя\n\nОтель и трансфер пересчитаны. Цена выросла ≈4% из‑за выходных. Состыковки в порядке.",
      hotels: state.hotels,
      destinations: state.destinations,
      itinerary: buildItinerary(destId, true),
      cart: buildCart(hotelId, true),
      warnings: [{ level: "info", text: "Цена на отель выросла из‑за сдвига на выходные (+≈4%)." }],
      is_demo: true,
    };
  }

  if (intent === "pets") {
    return {
      session_id: state.sessionId,
      status: "results",
      stage: "hotels",
      reply:
        "Учёл, что с вами собака.\n\nОставил только pet-friendly варианты. В Сочи — Riviera Guest House (доплата за питомца обычно ~1500 ₽/сутки на месте).\n\nРиск: не все пляжи допускают животных.",
      hotels: (MOCK_HOTELS.sochi || []).filter((h) => h.id === "h_sochi_2"),
      destinations: state.destinations.length ? state.destinations : MOCK_DESTINATIONS.slice(0, 1),
      warnings: [{ level: "warning", text: "Pet-fee обычно не входит в цену отеля и оплачивается на месте." }],
      is_demo: true,
    };
  }

  if (intent === "budget") {
    return {
      session_id: state.sessionId,
      status: "results",
      stage: "hotels",
      reply:
        "Уменьшил бюджет и пересобрал варианты.\n\n• Убрал 4★ у моря\n• Оставил 3★ чуть дальше от пляжа\n• Известная стоимость ниже ~25%\n\nКомпромисс: меньше удобств, дольше до моря.",
      hotels: (MOCK_HOTELS.sochi || []).filter((h) => (h.price_total || h.price) < 20000),
      destinations: state.destinations,
      is_demo: true,
    };
  }

  if (intent === "spb") {
    return {
      session_id: state.sessionId,
      status: "results",
      stage: "hotels",
      reply:
        "Питер на выходные — хороший выбор.\n\nПредлагаю 2 ночи в центре. Ниже отель с сильными отзывами. Данные синтетические (демо).",
      destinations: [
        {
          id: "spb",
          name: "Санкт-Петербург",
          country: "Россия",
          why: "Культура, прогулки, рестораны. Удобно на 2–3 дня.",
          flight_hours: 1.5,
          avg_temp_c: 4,
          price_from: 18000,
          currency: "RUB",
          tags: ["город", "выходные"],
          is_demo: true,
        },
      ],
      hotels: MOCK_HOTELS.spb,
      is_demo: true,
    };
  }

  if (intent === "select" || intent === "checkout") {
    const hotelId = state.selected.hotelId || (state.hotels[0] && (state.hotels[0].id || state.hotels[0].hotel_id)) || "h_sochi_1";
    const destId = state.selected.destinationId || "sochi";
    return {
      session_id: state.sessionId,
      status: "results",
      stage: "checkout",
      reply:
        "Собрал поездку в корзину.\n\nПроверил состыковки: прилёт → трансфер → заселение — без разрывов.\nМожно подтвердить демонстрационное бронирование (реальной оплаты не будет).",
      itinerary: buildItinerary(destId, false),
      cart: buildCart(hotelId, false),
      hotels: state.hotels,
      destinations: state.destinations,
      is_demo: true,
    };
  }

  // Destination pick by name in message
  const pickDest = /сочи/i.test(message)
    ? "sochi"
    : /калининград/i.test(message)
      ? "kaliningrad"
      : /кисловодск|минерал/i.test(message)
        ? "mineralnye"
        : null;

  if (pickDest && (intent === "select" || /выбир|выбираю|беру/i.test(message))) {
    const hotels = MOCK_HOTELS[pickDest] || [];
    return {
      session_id: state.sessionId,
      status: "results",
      stage: "hotels",
      reply: `Отлично, смотрим ${MOCK_DESTINATIONS.find((d) => d.id === pickDest)?.name || pickDest}.\n\nПодобрал отели с объяснением выбора. Можно выбрать карточку справа или написать название.`,
      destinations: MOCK_DESTINATIONS.filter((d) => d.id === pickDest),
      hotels,
      is_demo: true,
    };
  }

  const dests =
    intent === "kld"
      ? MOCK_DESTINATIONS.filter((d) => d.id === "kaliningrad")
      : intent === "mountains"
        ? MOCK_DESTINATIONS.filter((d) => d.id === "mineralnye")
        : MOCK_DESTINATIONS;

  return {
    session_id: state.sessionId,
    status: "results",
    stage: "destinations",
    reply:
      "Понял запрос. Вот направления, которые хорошо ложатся на ваши условия:\n\n" +
      dests
        .map(
          (d, i) =>
            `${i + 1}. ${d.name} — от ${formatPrice(d.price_from)} · перелёт ~${d.flight_hours} ч · ${d.avg_temp_c}°C`
        )
        .join("\n") +
      "\n\nПочему именно они: короткий перелёт, адекватный бюджет, сезонные плюсы.\nВыберите направление справа или напишите название — подберу отели и соберу маршрут.\n\n⚠️ Данные синтетические (демо хакатона).",
    destinations: dests,
    hotels: [],
    is_demo: true,
  };
}

export { postChat, confirmCheckout, API_BASE, formatPrice };
