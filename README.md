# База объектов (CRM Phoenix)

Внутренняя база арендной недвижимости: поиск и редактирование карточек, фото и
видео, полная история изменений. Документы проекта: `PRD.md`, `DATA_MODEL.md`,
`API.md`, `ARCHITECTURE.md`, принятые решения — `DECISIONS.md`.

Состав: `db` (PostgreSQL 16), `api` (FastAPI), `nginx` (фронтенд, прокси, отдача
медиа), `backup` (ночной дамп базы). Всё запускается через Docker Compose одинаково
на своём сервере агентства и на VPS.

## Установка на сервер (свой сервер агентства или VPS)

Подходит Ubuntu 22.04/24.04 или Debian 12. Нужно 2 ГБ памяти, место на диске под
фото и видео.

1. Установите Docker и плагин Compose:

   ```bash
   curl -fsSL https://get.docker.com | sudo sh
   sudo usermod -aG docker "$USER"   # затем перелогиньтесь
   ```

2. Скопируйте проект на сервер, например в `/opt/crm`:

   ```bash
   sudo mkdir -p /opt/crm && sudo chown "$USER" /opt/crm
   git clone <адрес репозитория> /opt/crm
   cd /opt/crm
   ```

3. Создайте `.env` из примера и заполните его:

   ```bash
   cp .env.example .env
   python3 -c "import secrets; print(secrets.token_urlsafe(64))"   # → JWT_SECRET
   python3 -c "import secrets; print(secrets.token_urlsafe(24))"   # → пароль базы
   nano .env
   ```

   - `POSTGRES_PASSWORD` и пароль внутри `DATABASE_URL` должны совпадать.
   - `JWT_SECRET` — сгенерированная строка. Никому не передавайте.
   - `CORS_ORIGINS` — адрес, по которому откроют систему, например
     `http://192.168.1.10` или `https://crm.agency.uz`.
   - `UZS_PER_UE` — курс: сколько сум в 1 у.е. (сейчас 12000).
   - `HTTP_PORT` — порт на сервере (по умолчанию 80).

4. Запустите:

   ```bash
   docker compose up -d --build
   docker compose ps          # api и db должны стать healthy
   curl http://localhost/api/v1/health
   ```

   Миграции базы применяются автоматически при старте `api`.

5. Создайте первого администратора и справочник районов Ташкента:

   ```bash
   docker compose exec api python -m app.cli create-admin --username admin --full-name "Администратор"
   docker compose exec api python -m app.cli seed-districts
   ```

   Пароль спросят интерактивно (не короче 8 символов). Остальных пользователей
   создаёт администратор в разделе «Администрирование».

### Отличия для VPS

- Откройте в файрволе только 80/443 и SSH: `sudo ufw allow OpenSSH && sudo ufw allow 80,443/tcp && sudo ufw enable`.
  Порт базы наружу не публикуется.
- Для HTTPS поставьте перед системой обратный прокси с сертификатом (например,
  Caddy или nginx с certbot на хосте) и переведите `HTTP_PORT` на внутренний порт,
  например `8080`. `CORS_ORIGINS` укажите с `https://`.
- Копируйте `./backups` на другой сервер или в облако (например, `rclone` по cron):
  бэкап на том же диске не спасёт при потере сервера.

## Обновление

```bash
cd /opt/crm
git pull
docker compose up -d --build
```

Перед обновлением сделайте внеплановый бэкап (см. ниже).

## Бэкапы

Сервис `backup` каждую ночь в 02:00 по Ташкенту делает дамп базы в
`./backups/crm_ГГГГММДД_ЧЧММСС.dump` и удаляет дампы старше 14 дней.

Внеплановый бэкап:

```bash
docker compose exec backup backup-once.sh
```

Файлы фото и видео лежат в Docker-томе `media`. Архив тома:

```bash
docker run --rm -v crm_media:/data -v "$PWD/backups":/out debian:bookworm-slim \
  tar czf /out/media_$(date +%Y%m%d).tar.gz -C /data .
```

(Имя тома — `<папка проекта>_media`; посмотреть: `docker volume ls`.)

## Восстановление из бэкапа

Процедура проверена: дамп формата `custom` восстановлен в пустую базу, совпали
количество карточек, файлов, записей аудита, пользователей, ревизия миграций,
триггеры и расширение `pg_trgm`.

1. Остановите приложение, чтобы никто не писал в базу:

   ```bash
   docker compose stop nginx api
   ```

2. Пересоздайте базу и восстановите дамп (подставьте нужный файл):

   ```bash
   DUMP=backups/crm_20260915_020000.dump
   docker compose exec -T db sh -c 'dropdb -U "$POSTGRES_USER" --if-exists "$POSTGRES_DB" && createdb -U "$POSTGRES_USER" -T template0 -E UTF8 "$POSTGRES_DB"'
   docker compose exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner' < "$DUMP"
   ```

3. Если нужно, восстановите файлы медиа из архива:

   ```bash
   docker run --rm -v crm_media:/data -v "$PWD/backups":/in debian:bookworm-slim \
     sh -c 'rm -rf /data/* && tar xzf /in/media_20260915.tar.gz -C /data'
   ```

4. Запустите приложение и проверьте:

   ```bash
   docker compose up -d
   curl http://localhost/api/v1/health
   ```

   Откройте систему, найдите знакомую карточку и её историю.

## Логи

```bash
docker compose logs -f api      # JSON, одна строка на событие
docker compose logs -f nginx
docker compose logs backup
```

## Разработка

Нужны Python 3.12+, Node.js 20+, PostgreSQL 16 (или Docker).

```bash
cd backend
python -m venv .venv
.venv/Scripts/pip install -e ".[dev]"      # на Linux: .venv/bin/pip
```

Файл `backend/.env` с теми же переменными, что в `.env.example`, но
`DATABASE_URL` указывает на локальную базу, а `MEDIA_ROOT` — на локальную папку.

```bash
cd backend && .venv/Scripts/alembic upgrade head
cd backend && .venv/Scripts/uvicorn app.main:create_app --factory --port 8000
cd frontend && npm ci && npm run dev        # http://localhost:5173, /api проксируется
```

Чтобы в dev были видны фото, задайте `VITE_DEV_MEDIA_ROOT` равным `MEDIA_ROOT`:
dev-сервер Vite заменяет nginx и отдаёт файл по заголовку `X-Accel-Redirect`.

### Проверки

```bash
cd backend && .venv/Scripts/ruff check . && .venv/Scripts/black --check . && .venv/Scripts/pytest
cd frontend && npm run build
```

Тесты используют настоящий PostgreSQL: через testcontainers, если есть Docker, или
через локальный сервер, если задан `TEST_DATABASE_ADMIN_URL` (переменная окружения
или файл `backend/.env.test`). Для каждого прогона создаётся отдельная база.

### Нагрузочная проверка поиска

```bash
cd backend
.venv/Scripts/python scripts/seed_benchmark.py --database-url postgresql+asyncpg://.../crm_bench --count 100000
.venv/Scripts/python scripts/explain_search.py --database-url postgresql+asyncpg://.../crm_bench
```

Только на отдельной пустой базе: скрипт пишет данные в обход аудита.
