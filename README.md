# Островок — планировщик поездок

[Видео работы проекта](https://drive.google.com/drive/folders/1STzCI9ytR_NwF074z9fv4EKW6lyjgFDE?usp=sharing) — запись появится в этой папке после съёмки.

Сайт помогает выбрать направление, дорогу туда и обратно, отель и трансфер, а затем собирает расходы в демо-корзину. Диалог ведёт локальная Llama; варианты поступают из каталога и подключённых сервисов поиска.

## Быстрый старт

```bash
git clone https://github.com/freeman-res/FixTim-hotel.git
cd FixTim-hotel
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
tar -xzf data/catalog_bundle.tar.gz -C data
ollama pull llama3.1:8b
ollama pull bge-m3
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8080
```

Запустите Ollama отдельно перед приложением. На Windows активируйте окружение командой `.venv\Scripts\Activate.ps1`, а `cp` замените на `Copy-Item .env.example .env`. Откройте http://localhost:8080. `GET /` отдаёт сайт, `GET /health` возвращает `{"status":"ok"}`. Сжатый пакет содержит нормализованный каталог из 49 315 отелей и транспортные данные. Индекс BGE-M3 строится отдельно командой `python scripts/build_rag_index.py`.

## Модель LLM

Провайдер — Ollama, модель диалога — `llama3.1:8b` (Meta Llama 3.1 8B). Для поиска по описаниям отелей используется модель эмбеддингов `bge-m3`.

## Переменные окружения

| Имя | Дефолт | Назначение |
| --- | --- | --- |
| `APP_NAME` | `Hotel AI Agent Backend` | Название API |
| `APP_VERSION` | `0.1.0` | Версия API |
| `DEBUG` | `false` | Диагностика |
| `DATABASE_URL` | `sqlite:///./hotel_agent.db` | Хранение сессий |
| `OLLAMA_URL` | `http://127.0.0.1:11434` | Адрес локального Ollama |
| `OLLAMA_MODEL` | `llama3.1:8b` | Модель диалога |
| `OLLAMA_EMBED_MODEL` | `bge-m3` | Модель эмбеддингов RAG |
| `OLLAMA_NUM_CTX` | `8192` | Размер контекста |
| `CATALOG_PROVIDER` | `json` | Источник каталога |
| `CATALOG_DATA_DIR` | `./data/catalog` | Нормализованные данные |
| `CATALOG_RAG_INDEX_DIR` | `./data/vector_index` | Индекс поиска отелей |
| `CATALOG_SOURCE_DIR` | `./datasets` | Исходные данные для импорта |
| `CATALOG_CLIMATE_ENABLED` | `1` | Погодные данные |
| `TUTU_MCP_ENABLED` | `true` | Живой поиск Туту MCP |
| `TUTU_MCP_URL` | `https://mcp.tutu.ru/mcp` | Адрес Туту MCP |
| `TUTU_MCP_TIMEOUT` | `20` | Ожидание Туту, секунды |
| `OSRM_URL` | `https://router.project-osrm.org` | Маршруты трансфера |
| `RZD_CONNECT_TIMEOUT` | `3` | Подключение к РЖД, секунды |
| `RZD_READ_TIMEOUT` | `12` | Ответ РЖД, секунды |
| `RZD_RETRY_TOTAL` | `0` | Повторы РЖД |
| `RZD_CA_BUNDLE` | пусто | Дополнительный доверенный сертификат для РЖД |
| `WEATHERBIT_KEY` | пусто | Ключ Weatherbit, пока не используется |
| `WEATHERAPI_KEY` | пусто | Ключ WeatherAPI, пока не используется |

Ключи `WEATHERBIT_KEY` и `WEATHERAPI_KEY` хранятся в `secrets.env.age`; текущий погодный модуль использует Open-Meteo и не требует их. Приватный ключ age в Git не входит. Туту MCP включён через `.env`, работает по HTTPS и не требует токена.

## Архитектура

```text
Сайт → FastAPI → агент (Ollama, Llama 3.1 8B) → каталог → JSON / Туту MCP / OSRM / RAG
```

Агент сохраняет условия поездки в сессии, ищет варианты и собирает выбранные части маршрута. RAG использует BGE-M3 для поиска по описаниям из карточек отелей; это не отзывы гостей. OSRM даёт расстояние и время, стоимость трансфера рассчитывает приложение.

## Погода и источники данных

Погода берётся из Open-Meteo. Для дат в пределах пяти дней показывается прогноз; **более пяти дней — климатическая оценка, не прогноз**. Лимиты бесплатных тарифов других провайдеров: [Weatherbit — 50 запросов в день](https://cdn.weatherbit.io/pricing), [WeatherAPI — 100 000 запросов в месяц](https://www.weatherapi.com/pricing.aspx). Сейчас эти два провайдера в коде не вызываются.

Каталог отелей основан на OpenStreetMap, исторические сведения об авиамаршрутах — на ADS-B, автобусы — на открытом реестре. Исторический авиамаршрут не считается билетом на будущую дату. Для живых предложений приложение пробует Туту MCP; при отсутствии ответа использует каталог и расчётные цены. **Островок не скрапили.** Полный каталог хранится в Git как сжатый пакет `data/catalog_bundle.tar.gz`.

## Что не подключено

Реальное бронирование номера, покупка билета и оплата: кнопка подтверждения создаёт демо-заказ. Отзывы гостей отсутствуют. Для поездов без координат вокзала трансфер не рассчитывается. Weatherbit и WeatherAPI пока не подключены. Из внешних MCP подключён только Туту; TRVL, Russia Travel MCP и RollingGo MCP в сборку не входят. Публичные Туту MCP и OSRM могут быть недоступны; приложение не создаёт маршрут OSRM из выдуманного расстояния.

