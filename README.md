# Frontend — Островок! AI-агент поездки

Интерфейс для хакатона «О!дин запрос»: чат с агентом → направления → отели → маршрут → демо-корзина.

**Путь:** `artifacts/frontend/`  
**Стек:** HTML5 + CSS3 (Grid) + Vanilla JS (ES modules), без npm.

---

## Запуск

```bash
cd artifacts/frontend
python3 -m http.server 5500
# → http://localhost:5500
```

По умолчанию включён **Mock API** — полный сценарий без backend.

### Реальный backend

1. Меню **⋯** → снять «Mock API»
2. Backend: `http://localhost:8000` (CORS `*`)
3. Сменить URL:  
   `localStorage.setItem('ostrovok_api_base', 'https://...')`

### Контракт API

```
POST /api/v1/chat
{ "session_id": "...", "message": "..." }

← ChatResponse:
  session_id, status, reply, hotels[],
  stage, destinations[], itinerary, cart, warnings[], is_demo
```

`updated_state` на фронт **не** приходит — backend хранит его по `session_id`.

---

## Структура файлов

```
frontend/
├── index.html                 # оболочка: header, чат, вкладки, composer
├── README.md                  # этот файл
├── assets/                    # картинки welcome-сценариев
│   ├── sea.jpg                # «Море в ноябре»
│   ├── spb.jpg                # «Питер на выходные»
│   └── mountains.jpg          # «Горы и воздух»
├── css/
│   ├── main.css               # токены Островка, header, stepper, layout (Grid), карточки
│   ├── chat.css               # чат, welcome, сценарии, composer
│   ├── destinations.css       # карточки направлений + обложки
│   ├── hotels.css             # карточки отелей
│   ├── itinerary.css          # таймлайн маршрута, warnings
│   ├── checkout.css           # корзина, DEMO-бронирование
│   ├── favorites.css          # (доп.) избранное
│   └── responsive.css         # адаптив на CSS Grid (телефон / планшет / landscape)
└── js/
    ├── main.js                # точка входа, табы, степпер, applyResponse, сессия
    ├── api.js                 # Fetch + Mock-агент (полный сценарий)
    ├── state.js               # sessionId, stage, selected, cart, flags
    ├── chat.js                # сообщения, welcome, typing, composer
    ├── destinations.js        # рендер направлений
    ├── hotels.js              # рендер отелей
    ├── itinerary.js           # рендер маршрута
    ├── checkout.js            # корзина + confirm DEMO
    └── favorites.js           # (доп.) избранное
```

---

## История обновлений (с первого образца)

### v1 — Первый прототип (26.10.2026)

**Где:** `index.html`, `css/*`, `js/*` (базовый набор)

**Что сделано:**
- Единый экран: чат слева, панель справа (Направления / Отели / Маршрут / Корзина)
- Стиль Островка: ультрамарин `#0E41D2`, зелёный «мохито» `#A8E063`, Inter
- `POST /api/v1/chat` + **Mock API** для демо без backend
- Карточки направлений и отелей, таймлайн маршрута, корзина с DEMO-кнопкой
- Подсказки в composer, блокировка повторной отправки
- Базовая адаптивность (`responsive.css`)

**Ограничения v1:** пустой welcome, «иишный» вид, stage только pill-текстом, нет фото, Mock/API на виду в шапке.

---

### v2 — Продуктовый UI (27.10.2026)

**Где изменены файлы:**
| Файл | Изменения |
|------|-----------|
| `index.html` | Степпер 1–5, trip-summary, меню ⋯ (Mock спрятан), richer empty states |
| `css/main.css` | Токены, stepper, trip-summary, menu, wash-фон, карточки |
| `css/chat.css` | Welcome-блок, сценарии-карточки, аватар «О!», тени пузырей |
| `css/destinations.css` | Цветные cover у направлений |
| `js/main.js` | `applyResponse` под ChatResponse, stepper, summary, menu |
| `js/api.js` | Контракт `session_id` + полный mock-сценарий (пересборка, pets, budget) |
| `js/chat.js` | `renderWelcome` + 3 сценария |
| `js/state.js` | `selected.destinationName/hotelName`, без локального updated_state |
| `js/destinations.js` / `hotels.js` / `itinerary.js` / `checkout.js` | Счётчики вкладок, «Выбрано ✓», нормализация `hotel_id` |

**Что добавилось по смыслу:**
1. Welcome: «Спланируем поездку одним запросом» + 3 кликабельных сценария  
2. Степпер этапов: Идея → Куда → Жильё → Маршрут → Оплата  
3. Trip summary в шапке после выбора  
4. Объяснения «почему», тег «синтетика», warnings  
5. Mock/API и «Новая сессия» убраны в меню ⋯  
6. Выравнивание под backend: `session_id`, `stage`, `destinations`, `itinerary`, `cart`, `warnings`

---

### v2.1 — Фото на welcome-плашках (27.10.2026)

**Где:**
| Файл | Изменения |
|------|-----------|
| `assets/sea.jpg` | NEW — фото моря |
| `assets/spb.jpg` | NEW — фото Петербурга |
| `assets/mountains.jpg` | NEW — фото гор |
| `css/chat.css` | `background-image` на `.scenario__cover--sea/city/mount`, градиент-оверлей, высота cover 110px |
| `js/chat.js` | emoji как `scenario__cover-label` поверх фото |

**Карточки:**
- Море в ноябре → `assets/sea.jpg`
- Питер на выходные → `assets/spb.jpg`
- Горы и воздух → `assets/mountains.jpg`

---

### v2.2 — Адаптив на CSS Grid (28.10.2026)

**Где:**
| Файл | Изменения |
|------|-----------|
| `css/responsive.css` | Полная переписка: брейкпоинты 1100 / 900 / 700 / 480 / 360 + landscape + touch + safe-area |
| `css/main.css` | `grid-template-areas: "chat side"` на layout и панелях |
| `index.html` | `viewport-fit=cover` для вырезов экрана |

**Поведение по ширине:**
| Ширина | Сетка |
|--------|--------|
| > 900px | 2 колонки: чат \| сайдбар |
| ≤ 900px | 1 колонка: чат сверху, панель снизу (`grid-areas`) |
| ≤ 700px | сценарии «фото \| текст» в ряд |
| ≤ 480px | только кружки степпера, шрифт input 16px (без зума iOS), hints скрыты |
| ≤ 360px | ещё плотнее |
| landscape + низкая высота | снова 2 колонки |

Дополнительно: `100dvh`, `env(safe-area-inset-*)`, крупные hit-area на `pointer: coarse`.

---

## Что умеет сейчас (чеклист ТЗ №4)

- [x] Разбор запроса и диалог без анкеты из 15 пунктов  
- [x] Направления с объяснением (почему, цена, погода, время в пути)  
- [x] Отели с компромиссами и рисками  
- [x] Сборка маршрута и проверка состыковок (таймлайн + warnings)  
- [x] DEMO-покупка с явным подтверждением  
- [x] Пересборка без старта с нуля («на 2 дня позже», бюджет, собака) — в Mock и через backend  
- [x] Маркировка синтетики  
- [x] Адаптив телефон / планшет / desktop  
- [x] Моковые данные честно обозначены  

---

## Быстрый тест

1. Открыть сайт → клик «Море в ноябре»  
2. Выбрать направление справа → выбрать отель  
3. Написать «На два дня позже» / «С нами собака»  
4. Корзина → «Подтвердить демо-бронирование»  

---

## Зависимости

Frontend **без** npm/package.json.  
Общие Python-зависимости проекта (backend): см. `artifacts/requirements.txt` и `requirements-agent.txt`.
