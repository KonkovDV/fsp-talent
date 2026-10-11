# Доступность и производительность UI

Прогон на локальном production-сборке (`vite build` + `vite preview`), 2026-10-11 (МСК).
Инструменты: `@axe-core/playwright` 4.13.0 (теги wcag2a/aa, wcag21aa, wcag22aa), Lighthouse 12 (mobile + desktop).
Скрипт: `frontend/scripts/measure-a11y-perf.mjs` (нужны `lighthouse` и `chrome-launcher` в node_modules).

## Страницы

Главная, вход, жюри, методика, кабинет кандидата (пример), тест (мок active), потребности (пример + подборка), поиск с карточками.

Темы: светлая и тёмная. Авторизованные экраны — режим «пример» (`fsp-auth.example`).

## axe-core

| Тема | Экранов | critical | serious | moderate | minor | всего |
|---|---:|---:|---:|---:|---:|---:|
| light | 8 | 0 | 0 | 0 | 0 | 0 |
| dark | 8 | 0 | 0 | 0 | 0 | 0 |

До фикса этого прогона `/employer/needs` в режиме «пример» падал (в фикстуре не было `params`) — страница без `<main>` и заголовка. После починки фикстуры и защиты рендера axe по потребностям тоже 0.

`lang="ru"` на `<html>`, skip-link «Перейти к содержимому», `<main id="main">`, видимый `:focus-visible`, `aria-label` у ThemeToggle и мобильного меню — на месте.

## Lighthouse (публичные URL)

| Страница | Форм-фактор | Perf | A11y | Best practices | SEO | LCP (мс) |
|---|---|---:|---:|---:|---:|---:|
| landing | mobile | 93 | 100 | 100 | 91 | 2662 |
| login | mobile | 91 | 100 | 96 | 91 | 2984 |
| jury | mobile | 93 | 100 | 100 | 91 | 2721 |
| method | mobile | 92 | 100 | 96 | 91 | 2762 |
| landing | desktop | 72 | 100 | 100 | 91 | 2610 |
| login | desktop | 69 | 100 | 96 | 91 | 2969 |
| jury | desktop | 72 | 100 | 100 | 91 | 2612 |
| method | desktop | 71 | 100 | 96 | 91 | 2761 |

CLS ≈ 0; TBT ≈ 0–14 мс. Desktop-оценка Perf ниже при сходном LCP — кривая скоуринга Lighthouse для desktop строже.

## Что сделано в этом прогоне

- Фикстура примера потребностей (`demoFallback`) с `params`, survey-options и подборкой — кабинет работодателя не падает без API.
- Защита рендера потребностей при отсутствии `params`.
- `PageHeader` выставляет `document.title` вида «… — ФСП Талант»; длинные заголовки с `overflow-wrap:anywhere`.
- `preview.proxy` для `/api` в `vite.config.ts` (удобство локального прогона).

Маршруты уже разбиты через `React.lazy` — дополнительных ленивых чанков не добавляли.
