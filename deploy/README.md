# Стенд: HTTPS без покупки домена

1. Сервер с Docker и открытыми портами 80 и 443. Адрес сайта — IP через дефисы плюс `.sslip.io`, например `203-0-113-10.sslip.io`: сервис sslip.io отвечает этим IP на любой такой домен, Caddy сам получает сертификат Let's Encrypt.
2. `cp deploy/.env.example deploy/.env` и заполнить: `SITE_ADDRESS`, `SECRET_KEY`, `POSTGRES_PASSWORD` и `APP_DB_PASSWORD` (`openssl rand -hex 32`), SMTP для писем с кодами. `ACME_EMAIL` — почта, на которую Let's Encrypt пришлёт напоминание об окончании сертификата; пустое значение оставляют, пока такого ящика нет. Пароль приложения — вход роли `fsp_app`: у неё нет прав суперпользователя, миграции идут от владельца базы. Для стенда жюри без почтовой учётки — `DEMO_MODE=true` и `DEMO_SHOW_CODE=true`: код подтверждения показывается на экране тому, кто регистрируется.
3. Запуск: `GIT_SHA=$(git rev-parse HEAD) docker compose -f deploy/docker-compose.prod.yml --env-file deploy/.env up -d --build`. `GIT_SHA` попадает в `/health`, по нему видно, какой коммит развёрнут.
4. Демо-данные: `docker compose -f deploy/docker-compose.prod.yml --env-file deploy/.env exec -T -u appuser backend python -m seed.generate_seed`. Пользователь обязателен: загрузка демо-данных от root создаёт ключ подписи, который приложение не читает, и проверка удостоверения отвечает 500.
5. Вернуть показ жюри: `docker compose -f deploy/docker-compose.prod.yml --env-file deploy/.env exec -T -u appuser backend python -m seed.reset_demo`. Затем войти как `jury1@demo.talent` с паролем `demo12345`.
6. Проверка: `curl https://$SITE_ADDRESS/health`.
7. Языковая модель, если она нужна на стенде: оператор вручную задаёт в `deploy/.env` `AI_ENABLED=true`, `YANDEX_MODEL=yandexgpt-5.1/latest` и `YANDEX_CHECK_MODEL=yandexgpt-5-lite/latest`. Ключ и идентификатор каталога остаются только в этом файле. `SECRET_KEY` и `FIELD_ENCRYPTION_KEY` при обновлении кода не меняют, том `vc_keys` не удаляют. Конвейер CI файл `deploy/.env` не правит: включение модели меняет обработку ПДн и решается человеком.

Снаружи открыт только Caddy. База и Redis не публикуются. Миграции применяются при старте backend.

Публичный стенд — процессор и 8 ГБ. Образ backend не ставит sentence-transformers и torch: аргумент `INSTALL_RERANKER` по умолчанию выключен. Compose держит `CROSS_ENCODER_MODE=off` и `EMBEDDINGS_MODE=off`, фоновый обработчик задач (worker) — один процесс. Локальная машина с видеокартой собирает backend с `INSTALL_RERANKER=1`. Ключи `SECRET_KEY` и `FIELD_ENCRYPTION_KEY` и том `vc_keys` при этом обновлении не трогают.

После срока сдачи код на сервере не меняется: упавший контейнер поднимают заново, показ возвращают командой из пункта 5.

**Резервные копии.** Контейнер `backup` каждую ночь в 03:30 делает `pg_dump` в `deploy/backups/` и хранит 14 последних. Вручную: `docker compose ... exec backup sh /backup.sh`. Перед восстановлением файл проверяют без записи в базу: `python deploy/verify_backup.py deploy/backups/fsp_talent-YYYYMMDD-HHMM.dump`. Восстановление заменяет данные в базе и не запускается, пока в команде нет `CONFIRM=restore`. Тома Docker оно не удаляет.

```bash
CONFIRM=restore ENV_FILE=deploy/.env COMPOSE_FILE=deploy/docker-compose.prod.yml \
  sh deploy/restore_db.sh deploy/backups/fsp_talent-YYYYMMDD-HHMM.dump
```

Ключ подписи удостоверений лежит в томе `vc_keys` и должен принадлежать `appuser`. Том не удаляют: иначе выданные подписи нельзя проверить. `SECRET_KEY` и `FIELD_ENCRYPTION_KEY` на стенде с уже записанной почтой не меняют: шифр контактов от них зависит.

Настройки Caddy — каталог `deploy/caddy`. `/.env` и `/.git` отвечают 404. Тело больше 10 МБ получает от API ответ 413. При `DEMO_MODE` и `MAIL_MODE=console` экран «Забыли пароль?» сообщает, что письма не отправляются, и код сброса не показывает. Кнопка «Взять свободный аккаунт жюри» берёт адрес из `GET /api/v1/public/jury-free`.
