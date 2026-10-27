# Frontend — Островок! AI-агент поездки

Максимально удобный интерфейс под контракт backend:

```
POST /api/v1/chat
{ "session_id": "...", "message": "..." }

→ ChatResponse:
  session_id, status, reply, hotels[],
  stage, destinations[], itinerary, cart, warnings[], is_demo
```

`updated_state` **не** приходит на фронт — его хранит backend по `session_id`.

## Запуск

```bash
cd frontend
python3 -m http.server 5500
# → http://localhost:5500
```

По умолчанию **Mock API** — полный сценарий без backend.

## Реальный backend

1. Меню **⋯** → снять «Mock API»
2. Backend на `http://localhost:8000` (CORS уже `*`)
3. Сменить URL: `localStorage.setItem('ostrovok_api_base', 'https://...')`

## UX

- Welcome с 3 сценариями-карточками
- Степпер: Идея → Куда → Жильё → Маршрут → Оплата
- Trip summary в шапке после выбора
- Карточки направлений с обложкой, погодой, «почему»
- Отели с рейтингом, удобствами, объяснением
- Таймлайн маршрута + предупреждения
- Корзина и явное DEMO-подтверждение
- Пересборка: «на 2 дня позже», бюджет, собака

## Структура

```
frontend/
├── index.html
├── css/   main, chat, destinations, hotels, itinerary, checkout, responsive
└── js/    main, api, state, chat, destinations, hotels, itinerary, checkout
```
