# Лицензии сторонних компонентов (THIRD_PARTY_NOTICES)

Проект «ФСП Талант» распространяется по лицензии MIT (`LICENSE`). Ниже перечислены сторонние компоненты, которые попадают в рабочую сборку, и их лицензии. Права на компоненты принадлежат их авторам; тексты лицензий входят в пакеты.

Как получен список (11.10.2026):
- backend: зависимости `[project].dependencies` из `backend/pyproject.toml` с транзитивными, `pip-licenses` (53 пакета; extras вроде `fastapi[standard]` раскрыты не полностью, dev-зависимости не входят);
- frontend: `npm ls --omit=dev --all` по `frontend/package.json` и поле `license` каждого пакета (235 пакетов).

## Итог проверки на copyleft

- **GPL/AGPL: нет** ни в backend, ни во frontend.
- **LGPL-3.0-only: `fpdf2`** (генерация PDF). Библиотека используется без изменений, как отдельный пакет Python, поэтому условия LGPL выполняются: пользователь может заменить её своей версией. Исходный код проекта открыт по MIT.
- **MPL-2.0** (`axe-core`): слабый copyleft на уровне файла, файлы пакета не изменялись.
- **CC-BY-4.0** (`caniuse-lite`, данные о браузерах) и **OFL-1.1** (шрифты Golos Text, JetBrains Mono): атрибуция сохраняется в пакетах.

Сводка frontend по лицензиям: MIT — 205, ISC — 11, Apache-2.0 — 8, MIT-0 — 2, OFL-1.1 — 2, BSD-2-Clause — 2, BSD-3-Clause — 2, MPL-2.0 — 1, CC-BY-4.0 — 1, CC0-1.0 — 1.

## Backend (Python)

| Name                 | Version     | License                              | URL                                                                                |
|----------------------|-------------|--------------------------------------|------------------------------------------------------------------------------------|
| bcrypt               | 5.0.0       | Apache Software License              | https://github.com/pyca/bcrypt/                                                    |
| python-dateutil      | 2.9.0.post0 | Apache Software License; BSD License | https://github.com/dateutil/dateutil                                               |
| asyncpg              | 0.32.0      | Apache-2.0                           | UNKNOWN                                                                            |
| opentelemetry-api    | 1.45.1      | Apache-2.0                           | https://github.com/open-telemetry/opentelemetry-python/tree/main/opentelemetry-api |
| tzdata               | 2026.5      | Apache-2.0                           | https://github.com/python/tzdata                                                   |
| packaging            | 26.3        | Apache-2.0 OR BSD-2-Clause           | https://github.com/pypa/packaging                                                  |
| cryptography         | 50.0.2      | Apache-2.0 OR BSD-3-Clause           | https://github.com/pyca/cryptography                                               |
| amqp                 | 5.4.1       | BSD License                          | http://github.com/celery/py-amqp                                                   |
| billiard             | 4.3.1       | BSD License                          | https://github.com/celery/billiard                                                 |
| click-plugins        | 1.1.1.2     | BSD License                          | https://github.com/click-contrib/click-plugins                                     |
| httpx                | 0.28.1      | BSD License                          | https://github.com/encode/httpx                                                    |
| prompt_toolkit       | 3.0.53      | BSD License                          | https://github.com/prompt-toolkit/python-prompt-toolkit                            |
| vine                 | 5.1.0       | BSD License                          | https://github.com/celery/vine                                                     |
| MarkupSafe           | 3.0.4       | BSD-3-Clause                         | https://github.com/pallets/markupsafe/                                             |
| celery               | 5.6.3       | BSD-3-Clause                         | https://docs.celeryq.dev/                                                          |
| click                | 8.5.0       | BSD-3-Clause                         | https://github.com/pallets/click/                                                  |
| httpcore             | 1.0.9       | BSD-3-Clause                         | https://www.encode.io/httpcore/                                                    |
| idna                 | 3.20        | BSD-3-Clause                         | https://github.com/kjd/idna                                                        |
| kombu                | 5.6.2       | BSD-3-Clause                         | https://kombu.readthedocs.io                                                       |
| pycparser            | 3.11        | BSD-3-Clause                         | https://github.com/eliben/pycparser                                                |
| pypdf                | 6.20.0      | BSD-3-Clause                         | https://github.com/py-pdf/pypdf                                                    |
| python-dotenv        | 1.2.4       | BSD-3-Clause                         | https://github.com/theskumar/python-dotenv                                         |
| starlette            | 1.7.0       | BSD-3-Clause                         | https://github.com/Kludex/starlette                                                |
| uvicorn              | 0.54.0      | BSD-3-Clause                         | https://uvicorn.dev/                                                               |
| fpdf2                | 2.8.9       | LGPL-3.0-only                        | https://py-pdf.github.io/fpdf2/                                                    |
| Mako                 | 1.4.3       | MIT                                  | https://www.makotemplates.org/                                                     |
| PyJWT                | 2.15.1      | MIT                                  | https://github.com/jpadilla/pyjwt                                                  |
| SQLAlchemy           | 2.1.4       | MIT                                  | https://www.sqlalchemy.org                                                         |
| alembic              | 1.20.0      | MIT                                  | https://alembic.sqlalchemy.org                                                     |
| annotated-doc        | 0.0.5       | MIT                                  | https://github.com/fastapi/annotated-doc                                           |
| annotated-types      | 0.8.0       | MIT                                  | https://github.com/annotated-types/annotated-types                                 |
| anyio                | 4.15.1      | MIT                                  | https://anyio.readthedocs.io/en/stable/versionhistory.html                         |
| argon2-cffi          | 25.1.0      | MIT                                  | https://github.com/hynek/argon2-cffi/blob/main/CHANGELOG.md                        |
| argon2-cffi-bindings | 26.1.0      | MIT                                  | https://github.com/hynek/argon2-cffi-bindings/blob/main/CHANGELOG.md               |
| click-repl           | 0.4.1       | MIT                                  | https://github.com/click-contrib/click-repl                                        |
| fastapi              | 0.143.0     | MIT                                  | https://github.com/fastapi/fastapi                                                 |
| fonttools            | 4.66.1      | MIT                                  | http://github.com/fonttools/fonttools                                              |
| pgvector             | 0.5.1       | MIT                                  | https://github.com/pgvector/pgvector-python                                        |
| pydantic             | 2.14.0      | MIT                                  | https://github.com/pydantic/pydantic                                               |
| pydantic-settings    | 2.15.0      | MIT                                  | https://github.com/pydantic/pydantic-settings                                      |
| pydantic_core        | 2.50.0      | MIT                                  | https://github.com/pydantic                                                        |
| redis                | 6.4.0       | MIT                                  | https://github.com/redis/redis-py                                                  |
| typing-inspection    | 0.4.4       | MIT                                  | https://github.com/pydantic/typing-inspection                                      |
| tzlocal              | 5.4.4       | MIT                                  | https://github.com/regebro/tzlocal/blob/master/CHANGES.txt                         |
| click-didyoumean     | 0.3.1       | MIT License                          | https://github.com/click-contrib/click-didyoumean                                  |
| h11                  | 0.16.0      | MIT License                          | https://github.com/python-hyper/h11                                                |
| six                  | 1.17.0      | MIT License                          | https://github.com/benjaminp/six                                                   |
| cffi                 | 2.1.1       | MIT-0                                | https://cffi.readthedocs.io/en/latest/whatsnew.html                                |
| pillow               | 12.3.0      | MIT-CMU                              | https://python-pillow.github.io                                                    |
| certifi              | 2026.7.22   | Mozilla Public License 2.0 (MPL 2.0) | https://github.com/certifi/python-certifi                                          |
| typing_extensions    | 4.16.0      | PSF-2.0                              | https://github.com/python/typing_extensions                                        |
| defusedxml           | 0.7.1       | Python Software Foundation License   | https://github.com/tiran/defusedxml                                                |

## Frontend (npm, production)

| Пакет | Лицензия |
|---|---|
| @adobe/css-tools@4.5.0 | MIT |
| @alloc/quick-lru@5.3.0 | MIT |
| @asamuzakjp/css-color@5.1.11 | MIT |
| @asamuzakjp/dom-selector@7.1.1 | MIT |
| @asamuzakjp/generational-cache@1.0.1 | MIT |
| @asamuzakjp/nwsapi@2.3.9 | MIT |
| @babel/code-frame@7.29.7 | MIT |
| @babel/compat-data@7.29.7 | MIT |
| @babel/core@7.29.7 | MIT |
| @babel/generator@7.29.8 | MIT |
| @babel/helper-compilation-targets@7.29.7 | MIT |
| @babel/helper-globals@7.29.7 | MIT |
| @babel/helper-module-imports@7.29.7 | MIT |
| @babel/helper-module-transforms@7.29.7 | MIT |
| @babel/helper-plugin-utils@7.29.7 | MIT |
| @babel/helper-string-parser@7.29.7 | MIT |
| @babel/helper-validator-identifier@7.29.7 | MIT |
| @babel/helper-validator-option@7.29.7 | MIT |
| @babel/helpers@7.29.7 | MIT |
| @babel/parser@7.29.9 | MIT |
| @babel/plugin-transform-react-jsx-self@7.29.7 | MIT |
| @babel/plugin-transform-react-jsx-source@7.29.7 | MIT |
| @babel/runtime@7.29.10 | MIT |
| @babel/template@7.29.7 | MIT |
| @babel/traverse@7.29.8 | MIT |
| @babel/types@7.29.8 | MIT |
| @bramus/specificity@2.4.3 | MIT |
| @csstools/color-helpers@6.1.2 | MIT-0 |
| @csstools/css-calc@3.4.3 | MIT |
| @csstools/css-color-parser@4.2.6 | MIT |
| @csstools/css-parser-algorithms@4.0.2 | MIT |
| @csstools/css-syntax-patches-for-csstree@1.1.15 | MIT-0 |
| @csstools/css-tokenizer@4.0.2 | MIT |
| @esbuild/linux-x64@0.25.12 | MIT |
| @exodus/bytes@1.16.0 | MIT |
| @fontsource-variable/golos-text@5.3.0 | OFL-1.1 |
| @fontsource-variable/jetbrains-mono@5.3.0 | OFL-1.1 |
| @hookform/resolvers@3.10.0 | MIT |
| @jridgewell/gen-mapping@0.3.13 | MIT |
| @jridgewell/remapping@2.3.5 | MIT |
| @jridgewell/resolve-uri@3.1.2 | MIT |
| @jridgewell/sourcemap-codec@1.6.0 | MIT |
| @jridgewell/trace-mapping@0.3.31 | MIT |
| @nodelib/fs.scandir@2.1.5 | MIT |
| @nodelib/fs.stat@2.0.5 | MIT |
| @nodelib/fs.walk@1.2.8 | MIT |
| @remix-run/router@1.23.4 | MIT |
| @rolldown/pluginutils@1.0.0-beta.27 | MIT |
| @rollup/rollup-linux-x64-gnu@4.64.0 | MIT |
| @rollup/rollup-linux-x64-musl@4.64.0 | MIT |
| @tanstack/query-core@5.104.1 | MIT |
| @tanstack/react-query@5.104.1 | MIT |
| @testing-library/dom@10.4.2 | MIT |
| @types/aria-query@5.0.4 | MIT |
| @types/babel__core@7.20.5 | MIT |
| @types/babel__generator@7.27.0 | MIT |
| @types/babel__template@7.4.4 | MIT |
| @types/babel__traverse@7.28.0 | MIT |
| @types/chai@5.2.3 | MIT |
| @types/deep-eql@4.0.2 | MIT |
| @types/estree@1.0.9 | MIT |
| @types/prop-types@15.7.15 | MIT |
| @vitest/mocker@5.0.3 | MIT |
| @vitest/spy@5.0.3 | MIT |
| agent-base@6.0.2 | MIT |
| ansi-regex@5.0.1 | MIT |
| ansi-styles@5.2.0 | MIT |
| any-promise@1.3.0 | MIT |
| anymatch@3.1.3 | ISC |
| arg@5.0.2 | MIT |
| aria-query@5.3.0 | Apache-2.0 |
| assertion-error@2.0.1 | MIT |
| asynckit@0.4.0 | MIT |
| axe-core@4.13.0 | MPL-2.0 |
| axios@1.20.0 | MIT |
| baseline-browser-mapping@2.11.27 | Apache-2.0 |
| bidi-js@1.1.0 | MIT |
| binary-extensions@2.3.0 | MIT |
| braces@3.0.3 | MIT |
| browserslist@4.29.3 | MIT |
| call-bind-apply-helpers@1.0.2 | MIT |
| camelcase-css@2.0.1 | MIT |
| caniuse-lite@1.0.30001814 | CC-BY-4.0 |
| chai@6.3.0 | MIT |
| chokidar@3.6.0 | MIT |
| clsx@2.1.1 | MIT |
| combined-stream@1.0.8 | MIT |
| commander@4.1.1 | MIT |
| convert-source-map@2.0.0 | MIT |
| css-tree@3.2.1 | MIT |
| css.escape@1.5.1 | MIT |
| cssesc@3.0.0 | MIT |
| csstype@3.2.3 | MIT |
| data-urls@7.0.0 | MIT |
| date-fns@3.6.0 | MIT |
| debug@4.4.3 | MIT |
| decimal.js@10.6.0 | MIT |
| delayed-stream@1.0.0 | MIT |
| dequal@2.0.3 | MIT |
| didyoumean@1.2.2 | Apache-2.0 |
| dlv@1.1.3 | MIT |
| dom-accessibility-api@0.5.16 | MIT |
| dunder-proto@1.0.1 | MIT |
| electron-to-chromium@1.5.444 | ISC |
| entities@8.1.0 | BSD-2-Clause |
| es-define-property@1.0.1 | MIT |
| es-errors@1.3.0 | MIT |
| es-module-lexer@2.3.2 | MIT |
| es-object-atoms@1.1.2 | MIT |
| es-set-tostringtag@2.1.0 | MIT |
| esbuild@0.25.12 | MIT |
| escalade@3.2.0 | MIT |
| estree-walker@3.0.3 | MIT |
| expect-type@1.4.0 | Apache-2.0 |
| fast-glob@3.3.3 | MIT |
| fastq@1.20.3 | ISC |
| fdir@6.5.0 | MIT |
| fill-range@7.1.1 | MIT |
| follow-redirects@1.16.1 | MIT |
| form-data@4.0.6 | MIT |
| fraction.js@5.3.4 | MIT |
| function-bind@1.1.2 | MIT |
| gensync@1.0.0-beta.2 | MIT |
| get-intrinsic@1.3.0 | MIT |
| get-proto@1.0.1 | MIT |
| glob-parent@5.1.2 | ISC |
| glob-parent@6.0.2 | ISC |
| gopd@1.2.0 | MIT |
| has-symbols@1.1.0 | MIT |
| has-tostringtag@1.0.2 | MIT |
| hasown@2.0.4 | MIT |
| html-encoding-sniffer@6.0.0 | MIT |
| https-proxy-agent@5.0.1 | MIT |
| indent-string@4.0.0 | MIT |
| is-binary-path@2.1.0 | MIT |
| is-core-module@2.17.0 | MIT |
| is-extglob@2.1.1 | MIT |
| is-glob@4.0.3 | MIT |
| is-number@7.0.0 | MIT |
| is-potential-custom-element-name@1.0.1 | MIT |
| jiti@1.21.7 | MIT |
| js-tokens@4.0.0 | MIT |
| jsesc@3.1.0 | MIT |
| json5@2.2.3 | MIT |
| lilconfig@3.1.3 | MIT |
| lines-and-columns@1.2.4 | MIT |
| loose-envify@1.4.0 | MIT |
| lru-cache@5.1.1 | ISC |
| lucide-react@0.447.0 | ISC |
| lz-string@1.5.0 | MIT |
| magic-string@1.4.3 | MIT |
| math-intrinsics@1.1.0 | MIT |
| mdn-data@2.27.1 | CC0-1.0 |
| merge2@1.4.1 | MIT |
| micromatch@4.0.8 | MIT |
| mime-db@1.52.0 | MIT |
| mime-types@2.1.35 | MIT |
| min-indent@1.0.1 | MIT |
| ms@2.1.3 | MIT |
| mz@2.7.0 | MIT |
| nanoid@3.3.19 | MIT |
| node-releases@2.0.57 | MIT |
| normalize-path@3.0.0 | MIT |
| object-assign@4.1.1 | MIT |
| object-hash@3.0.0 | MIT |
| obug@2.2.1 | MIT |
| parse5@8.0.1 | MIT |
| path-parse@1.0.7 | MIT |
| picocolors@1.1.1 | ISC |
| picomatch@2.3.2 | MIT |
| picomatch@4.0.7 | MIT |
| pirates@4.0.7 | MIT |
| playwright-core@1.63.0 | Apache-2.0 |
| playwright@1.63.0 | Apache-2.0 |
| postcss-import@15.1.0 | MIT |
| postcss-js@4.1.0 | MIT |
| postcss-load-config@6.0.1 | MIT |
| postcss-nested@6.2.0 | MIT |
| postcss-selector-parser@6.1.4 | MIT |
| postcss-value-parser@4.2.0 | MIT |
| pretty-format@27.5.1 | MIT |
| proxy-from-env@2.1.0 | MIT |
| punycode@2.3.1 | MIT |
| qrcode-generator@2.0.4 | MIT |
| queue-microtask@1.2.3 | MIT |
| react-dom@18.3.1 | MIT |
| react-hook-form@7.89.0 | MIT |
| react-is@17.0.2 | MIT |
| react-refresh@0.17.0 | MIT |
| react-router-dom@6.30.6 | MIT |
| react-router@6.30.6 | MIT |
| react@18.3.1 | MIT |
| read-cache@1.0.2 | MIT |
| readdirp@3.6.0 | MIT |
| redent@3.0.0 | MIT |
| require-from-string@2.0.2 | MIT |
| resolve@1.22.12 | MIT |
| reusify@1.1.0 | MIT |
| rollup@4.64.0 | MIT |
| run-parallel@1.2.0 | MIT |
| saxes@6.0.0 | ISC |
| scheduler@0.23.2 | MIT |
| semver@6.3.1 | ISC |
| source-map-js@1.2.2 | BSD-3-Clause |
| std-env@4.3.0 | MIT |
| strip-indent@3.0.0 | MIT |
| sucrase@3.35.1 | MIT |
| supports-preserve-symlinks-flag@1.0.0 | MIT |
| symbol-tree@3.2.4 | MIT |
| tailwind-merge@2.6.1 | MIT |
| thenify-all@1.6.0 | MIT |
| thenify@3.3.1 | MIT |
| tinybench@6.2.1 | MIT |
| tinyexec@1.3.1 | MIT |
| tinyglobby@0.2.17 | MIT |
| tldts-core@7.4.16 | MIT |
| tldts@7.4.16 | MIT |
| to-regex-range@5.0.1 | MIT |
| tough-cookie@6.0.2 | BSD-3-Clause |
| tr46@6.0.0 | MIT |
| ts-interface-checker@0.1.13 | Apache-2.0 |
| undici@7.30.0 | MIT |
| update-browserslist-db@1.3.3 | MIT |
| use-sync-external-store@1.7.0 | MIT |
| util-deprecate@1.0.2 | MIT |
| w3c-xmlserializer@5.0.0 | MIT |
| webidl-conversions@8.0.1 | BSD-2-Clause |
| whatwg-mimetype@5.0.0 | MIT |
| whatwg-url@16.0.1 | MIT |
| why-is-node-running@3.2.1 | MIT |
| xml-name-validator@5.0.0 | Apache-2.0 |
| xmlchars@2.2.0 | MIT |
| yallist@3.1.1 | ISC |
| zod@3.25.76 | MIT |
| zustand@4.5.7 | MIT |
