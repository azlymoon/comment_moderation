# Comment Moderation Service

FastAPI-проект для модерации пользовательских комментариев. Приложение использует готовую ML-модель `unitary/toxic-bert` для оценки токсичности текста, хранит заявки и результаты в PostgreSQL и включает административный интерфейс для управления пользователями, веб-сервисами и API-ключами.

## Требования

- Python 3.10+
- PostgreSQL 14+
- Доступ в интернет для загрузки ML-весов при первом запуске

## Установка

```bash
python3 -m venv .venv
source .venv/bin/activate             # Windows: .venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
```

### Полный гайд по установке, настройке и запуску PostgreSQL

Следующие инструкции покрывают популярные платформы. Выполните шаги, подходящие вашей ОС.

#### macOS (Homebrew)

```bash
brew update
brew install postgresql@14

# добавляем службу Postgres в автозапуск и запускаем её
brew services start postgresql@14

# проверяем, что сервер отвечает
pg_isready
```

После установки утилиты `psql`, `createdb` и `createuser` находятся в `/opt/homebrew/bin`. При необходимости добавьте этот путь в переменную `PATH`.

#### Ubuntu / Debian

```bash
sudo apt update
sudo apt install -y postgresql postgresql-contrib

sudo systemctl enable postgresql
sudo systemctl start postgresql

sudo systemctl status postgresql
```

Все команды ниже можно выполнять от имени суперпользователя `postgres`: `sudo -u postgres psql`.

#### Windows

1. Скачайте актуальный установщик с https://www.postgresql.org/download/windows/
2. Во время установки укажите порт (по умолчанию 5432) и пароль суперпользователя.
3. После завершения откройте «SQL Shell (psql)», введите сохранённые параметры и убедитесь, что видите приглашение `postgres=#`.
4. Добавьте путь `C:\Program Files\PostgreSQL\14\bin` (или соответствующий вашей версии) в переменную `PATH`, чтобы выполнять `psql` из терминала.

#### Проверка подключения

```bash
psql -U postgres -h localhost -p 5432 -c "SELECT version();"
```

Если требуется пароль, добавьте флаг `-W`, чтобы `psql` запросил его.

#### Создание базы и пользователя проекта

```bash
psql -U postgres -h localhost -p 5432 -c "CREATE USER moderator WITH PASSWORD 'moderator';"
psql -U postgres -h localhost -p 5432 -c "CREATE DATABASE comment_moderation OWNER moderator;"
psql -U postgres -h localhost -p 5432 -c "GRANT ALL PRIVILEGES ON DATABASE comment_moderation TO moderator;"
```

При необходимости настройте удалённый доступ, изменив `postgresql.conf` и `pg_hba.conf`, после чего перезапустите сервер (`brew services restart postgresql@14` или `sudo systemctl restart postgresql`).

#### Настройка переменных окружения

```bash
export DATABASE_URL="postgresql+psycopg://moderator:moderator@localhost:5432/comment_moderation"
```

Теперь приложение сможет подключиться к PostgreSQL. При старте оно автоматически выполняет миграции (`SQLModel.metadata.create_all`) и, если включено, заполняет демо-данными.

### Быстрый старт без PostgreSQL

Если PostgreSQL недоступен, можно использовать встроенный резервный режим на SQLite.
Убедитесь, что установлены переменные:

```bash
export SQLITE_FALLBACK_URL="sqlite+aiosqlite:///./comment_moderation.db"
export ALLOW_SQLITE_FALLBACK=true
```

Файл базы будет создан автоматически в корне проекта, а приложение переключится на него при невозможности подключиться к PostgreSQL.

## Запуск сервиса

```bash
python3 main.py
```

Служба будет доступна на `http://127.0.0.1:8000`. При `GENERATE_DEMO_DATA=true` (значение по умолчанию) создаются:

- супер-администратор `moderator` / `moderator`
- веб-сервис «Demo Service»
- действующий API-ключ (plain-значение выводится в логах при первом запуске)
- базовая категория «Toxic language» с правилом `FLAG_FOR_REVIEW`

## Переменные окружения

| Переменная            | Назначение                                                     | Значение по умолчанию |
|-----------------------|----------------------------------------------------------------|-----------------------|
| `DATABASE_URL`        | Строка подключения к PostgreSQL (psycopg) или SQLite           | `postgresql+psycopg://moderator:moderator@localhost:5432/comment_moderation` |
| `SQLITE_FALLBACK_URL` | Адрес резервной SQLite БД (используется при недоступности PG)  | `sqlite+aiosqlite:///./comment_moderation.db` |
| `ALLOW_SQLITE_FALLBACK`| Разрешить автоматическое переключение на SQLite               | `true`                |
| `GENERATE_DEMO_DATA`  | Включить автогенерацию демо-данных                             | `true`                |
| `ADMIN_DEMO_USERNAME` | Логин демо-админа                                              | `moderator`           |
| `ADMIN_DEMO_PASSWORD` | Пароль демо-админа                                             | `moderator`           |
| `ADMIN_DEMO_EMAIL`    | Почта демо-админа                                              | `moderator@example.com` |
| `SERVICE_DEMO_NAME`   | Имя демо-сервиса                                               | `Demo Service`        |
| `SERVICE_DEMO_CONTACT`| Контакт для демо-сервиса                                       | `demo@example.com`    |

Файл ``.env`` с предустановленными значениями уже добавлен в репозиторий для удобства локального запуска.
При переходе в промышленные окружения обязательно замените пароли и ключи.

## Сценарии использования эндпоинтов

Ниже перечислены типичные flow с примерами запросов.

### 1. Авторизация администратора

```bash
curl -X POST http://127.0.0.1:8000/auth/login \
     -H "Content-Type: application/json" \
     -d '{"username":"moderator","password":"moderator"}'
```

Ответ:

```json
{
  "token": "X-Admin-Token-value",
  "expires_at": "2025-10-08T12:34:56.123456"
}
```

Все админ-эндпоинты требуют заголовок `X-Admin-Token: <token>`.

### 2. Управление администраторами (только SUPER_ADMIN)

- Список:
  ```bash
  curl http://127.0.0.1:8000/admin/users \
       -H "X-Admin-Token: <token>"
  ```
- Создание:
  ```bash
  curl -X POST http://127.0.0.1:8000/admin/users \
       -H "Content-Type: application/json" \
       -H "X-Admin-Token: <token>" \
       -d '{"username":"analyst","email":"analyst@example.com","password":"StrongPass!","role":"ANALYST"}'
  ```

### 3. Управление веб-сервисами и API-ключами

- Создать сервис:
  ```bash
  curl -X POST http://127.0.0.1:8000/admin/services \
       -H "Content-Type: application/json" \
       -H "X-Admin-Token: <token>" \
       -d '{"name":"News Portal","description":"Public comments","contact_email":"team@news.example"}'
  ```
- Выписать API-ключ (возвращает открытое значение):
  ```bash
  curl -X POST http://127.0.0.1:8000/admin/services/<service_id>/api-keys \
       -H "X-Admin-Token: <token>"
  ```
- Список ключей:
  ```bash
  curl http://127.0.0.1:8000/admin/services/<service_id>/api-keys \
       -H "X-Admin-Token: <token>"
  ```
- Деактивация/активация:
  ```bash
  curl -X PATCH "http://127.0.0.1:8000/admin/api-keys/<key_id>?is_active=false" \
       -H "X-Admin-Token: <token>"
  ```

### 4. Отправка текста на модерацию (используется веб-сервисом)

```bash
curl -X POST http://127.0.0.1:8000/api/v1/moderation/text \
     -H "Content-Type: application/json" \
     -H "X-API-Key: <plain_api_key>" \
     -d '{"service_id":"<service_id>","content_text":"I hate this movie"}'
```

Ответ содержит заявку, решение и вероятности по всем меткам модели.

### 5. Работа модераторов

- Список заявок:
  ```bash
  curl http://127.0.0.1:8000/admin/requests \
       -H "X-Admin-Token: <token>"
  ```
- Получение конкретной заявки:
  ```bash
  curl http://127.0.0.1:8000/admin/requests/<request_id> \
       -H "X-Admin-Token: <token>"
  ```
- Обновление решения (например, отправить на дорассмотрение):
  ```bash
  curl -X PATCH http://127.0.0.1:8000/admin/requests/<request_id> \
       -H "Content-Type: application/json" \
       -H "X-Admin-Token: <token>" \
       -d '{"decision":"HUMAN_REVIEW"}'
  ```

### 6. Управление категориями и правилами

- Список категорий:
  ```bash
  curl http://127.0.0.1:8000/admin/categories \
       -H "X-Admin-Token: <token>"
  ```
- Создание/обновление категории:
  ```bash
  curl -X POST http://127.0.0.1:8000/admin/categories \
       -H "Content-Type: application/json" \
       -H "X-Admin-Token: <token>" \
       -d '{"type":"TOXICITY","name":"Abuse","description":"General abuse","auto_reject_threshold":0.95,"human_review_threshold":0.6,"is_enabled":true}'
  ```
- Добавление правил:
  ```bash
  curl -X POST http://127.0.0.1:8000/admin/rules \
       -H "Content-Type: application/json" \
       -H "X-Admin-Token: <token>" \
       -d '{"category_id":"<category_id>","action":"FLAG_FOR_REVIEW","priority":50,"conditions":["contains:abuse"]}'
  ```

### 7. Статистика по сервису

```bash
curl http://127.0.0.1:8000/admin/statistics/<service_id> \
     -H "X-Admin-Token: <token>"
```

Ответ возвращает агрегированную статистику (всего запросов, одобренных/отклонённых, число ручных проверок и количество ожиданий).

## Проверка end-to-end

1. Авторизуйтесь и получите `X-Admin-Token`.
2. Создайте веб-сервис и ключ (или возьмите демо-значения из логов старта).
3. Отправьте один токсичный и один нормальный комментарий с помощью `POST /api/v1/moderation/text`.
4. Проверьте списки заявок, статистику и при необходимости скорректируйте решения вручную.

## Структура проекта

```
app/
  api/               # FastAPI-роутеры (auth, admin, moderation)
  core/              # Доменные модели, бизнес-операции, зависимости
  db/                # SQLModel-модели и управление сессиями БД
  services/          # ML-логика текстовой модерации
docs/                # Sphinx-документация (источники)
main.py              # Точка входа и запуск uvicorn
requirements.txt
README.md
```

## Документация

Полная документация (инструкция по установке, пользовательское и разработческое руководство)
оформлена с помощью Sphinx и находится в каталоге `docs/`. Собрать HTML-версию можно командой:

```bash
sphinx-build -b html docs docs/_build/html
```

После успешной сборки откройте файл `docs/_build/html/index.html` в браузере.

## Дальнейшее развитие

- Добавить очередь задач и асинхронную обработку модерации.
- Расширить поддержку мультимедийных форматов (изображения, видео).
- Интегрировать полноценную систему отчётности и дашборды.
