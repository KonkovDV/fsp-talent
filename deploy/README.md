# Стенд: HTTPS без покупки домена

1. Сервер с Docker и открытыми портами 80 и 443. Адрес сайта — IP через дефисы плюс `.sslip.io`, например `203-0-113-10.sslip.io`: сервис sslip.io отвечает этим IP на любой такой домен, Caddy сам получает сертификат Let's Encrypt.
2. `cp deploy/.env.example deploy/.env` и заполнить: `SITE_ADDRESS`, `SECRET_KEY` и `POSTGRES_PASSWORD` (`openssl rand -hex 32`), SMTP для писем с кодами. Для стенда жюри без почтовой учётки — `DEMO_MODE=true` и `DEMO_SHOW_CODE=true`: код подтверждения показывается на экране тому, кто регистрируется.
3. Запуск: `docker compose -f deploy/docker-compose.prod.yml --env-file deploy/.env up -d --build`.
4. Демо-данные: `docker compose -f deploy/docker-compose.prod.yml --env-file deploy/.env exec backend python -m seed.generate_seed`.
5. Вернуть показ жюри: `docker compose -f deploy/docker-compose.prod.yml --env-file deploy/.env exec -T backend python -m seed.reset_demo`. Затем войти как `jury1@demo.talent` с паролем `demo12345`.
6. Проверка: `curl https://$SITE_ADDRESS/health`.

Снаружи открыт только Caddy. База и Redis не публикуются. Миграции применяются при старте backend.

Выкладка из GitHub идёт только после зелёных проверок стиля, тестов, сквозного сценария и сборки образов. После дедлайна владелец ставит переменную репозитория `DEPLOY_FROZEN=true` (Settings → Secrets and variables → Actions → Variables): шаг выкладки пропускается, код на сервере не меняется. Пока переменная не равна `true`, пуш в `main` по-прежнему выкладывает стенд, если задан `DEPLOY_HOST`.

**Бэкап.** Контейнер `backup` каждую ночь в 03:30 делает `pg_dump` в `deploy/backups/` и хранит 14 последних. Вручную: `docker compose ... exec backup sh /backup.sh`. Восстановление:

```bash
docker compose -f deploy/docker-compose.prod.yml --env-file deploy/.env exec -T postgres \
  pg_restore -U fsp -d fsp_talent --clean --if-exists < deploy/backups/fsp_talent-YYYYMMDD-HHMM.dump
```

Ключ подписи удостоверений лежит в томе `vc_keys`; его тоже нужно сохранить, иначе выданные удостоверения нельзя будет перевыпустить тем же ключом.
