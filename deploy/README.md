# Стенд: HTTPS без покупки домена

1. Сервер с Docker и открытыми портами 80 и 443. Адрес сайта — IP через дефисы плюс `.sslip.io`, например `203-0-113-10.sslip.io`: сервис sslip.io отвечает этим IP на любой такой домен, Caddy сам получает сертификат Let's Encrypt.
2. `cp deploy/.env.example deploy/.env` и заполнить: `SITE_ADDRESS`, `SECRET_KEY` и `POSTGRES_PASSWORD` (`openssl rand -hex 32`), SMTP для писем с кодами.
3. Запуск: `docker compose -f deploy/docker-compose.prod.yml --env-file deploy/.env up -d --build`.
4. Демо-данные: `docker compose -f deploy/docker-compose.prod.yml --env-file deploy/.env exec backend python -m seed.generate_seed`.
5. Проверка: `curl https://$SITE_ADDRESS/health`.

Снаружи открыт только Caddy. База и Redis не публикуются. Миграции применяются при старте backend.

**Бэкап.** Контейнер `backup` каждую ночь в 03:30 делает `pg_dump` в `deploy/backups/` и хранит 14 последних. Вручную: `docker compose ... exec backup sh /backup.sh`. Восстановление:

```bash
docker compose -f deploy/docker-compose.prod.yml --env-file deploy/.env exec -T postgres \
  pg_restore -U fsp -d fsp_talent --clean --if-exists < deploy/backups/fsp_talent-YYYYMMDD-HHMM.dump
```

Ключ подписи удостоверений лежит в томе `vc_keys`; его тоже нужно сохранить, иначе выданные удостоверения нельзя будет перевыпустить тем же ключом.
