# Changelog

All notable changes are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
Versioning: [SemVer](https://semver.org/)

---

## [0.3.0] — 2026-10-04 (branch: fix/p0-p1-full-audit)

### Fixed — P0 (critical)

#### `backend/app/services/ai/assistant.py` — GigaChat SDK contract
- **Bug:** `giga.achat(dict)` is not a valid call in `gigachat>=0.1.0`.
  The SDK method signature is `achat(Chat)`, not `achat(dict)`.
  A plain dict was silently coerced in some versions but raises
  `ValidationError` in others, breaking AI resume parsing entirely.
- **Fix:** Replace dict payload with proper `gigachat.models.Chat` +
  `Messages` + `MessagesRole` objects.
- **Fix:** Replace manual `aclose()` teardown with `async with GigaChat(...)`,
  which correctly handles OAuth token refresh and connection lifecycle.

### Fixed — P1 (high)

#### `backend/app/services/search/pipeline.py` — vector type mismatch
- **Bug:** `ProfileEmbedding.embedding.cosine_distance(vec)` received a Python
  `list[float]`.  Without an explicit PostgreSQL `CAST`, pgvector may:
  - raise `operator does not exist: vector <=> bytea` (pgvector <0.6)
  - fall back to a sequential scan, silently returning wrong results
- **Fix:** `cast(vec, Vector(EMBEDDING_DIM))` added before every cosine call.

#### `backend/app/services/search/pipeline.py` — FTS query construction
- **Bug:** `" or ".join(text.split())` produced malformed tsquery strings
  for multi-word phrases and failed on PostgreSQL stopwords.
- **Fix:** Use `func.websearch_to_tsquery("simple", query)` which handles
  quoted phrases, negation (-word), OR, and stopword stripping correctly.

#### `backend/app/api/v1/offers.py` — ambiguous minor guard
- **Bug:** `discoverable` property check returned a generic 404 for both
  “not visible” and “minor without consent”, making the error indistinguishable
  and forcing client-side guessing.
- **Fix:** Two explicit guards:
  1. `is_visible=False` → HTTP 404 (candidate not in pool)
  2. `is_minor=True and consent=False` → HTTP 403 with clear explanation
- **Fix:** Added duplicate-offer guard (HTTP 409) to prevent employer spam.

#### `backend/app/api/v1/candidates.py` — missing reject consent log
- **Bug:** `ConsentLog` was written only on offer acceptance. Rejection was
  not logged, violating GDPR audit-trail requirements (right to know).
- **Fix:** `ConsentLog(action="offer_rejected")` added to the reject branch.

#### `backend/app/services/scoring/engine.py` — missing `classify_grade` export
- **Bug:** The search pipeline referenced `classify_grade` and `DisciplineScore`
  but these were not exported from the engine module.
- **Fix:**
  - `DisciplineScore` promoted to a proper `@dataclass(slots=True)`.
  - `classify_grade(lcb: float) -> str` added and exported.
  - `GRADE_LCB_THRESHOLDS` constant documented (lead≥85%, senior≥65%,
    middle≥40%, junior<40%).
  - `fsp_level_from_rank()` helper added for FSP→HR label mapping.

### Added — P2 (medium)

#### `backend/app/main.py` — infrastructure improvements
- **Added:** `RequestIDMiddleware` — reads `X-Request-ID` header or generates
  UUID4; echoes it back in the response. Enables distributed tracing.
- **Added:** SlowAPI rate limiting:
  - Default: 60 requests/minute per IP
  - Auth endpoints: 10 requests/minute (brute-force protection)
- **Added:** `GET /health` endpoint returning `{status, version, timestamp}`
  (no auth; suitable for load-balancer liveness probes).
- **Added:** Structured startup/shutdown log lines.

#### `backend/pyproject.toml` — dependency hygiene
- Added `slowapi>=0.1.9` to base dependencies.
- Added `fastapi[standard]` (includes uvicorn) for clearer install surface.
- Added `[security]` optional group with `argon2-cffi>=23.1`.
- Documented `gigachat` as intentionally optional (lazy import).

### Added — Tests

#### `backend/tests/unit/test_scoring.py` (expanded)
- LCB monotonicity: more events ⇒ higher LCB for equal quality
- `classify_grade()` boundary tests at exact thresholds
- `fsp_level_from_rank()` round-trip parametrised test
- `percentile()` edge cases: single-participant field, zero total
- `event_weight()` half-life and team-discount precision tests
- `compute_discipline_score()` TypeError for wrong date type
- Bayesian shrinkage: score stays away from 0.0 and 1.0 extremes

#### `backend/tests/unit/test_security.py` (NEW)
- JWT encode/decode round-trip with `HS256`
- Expired token detection (`jwt.ExpiredSignatureError`)
- Wrong-secret detection (`jwt.InvalidSignatureError`)
- Tampered payload detection (`jwt.DecodeError`)
- `bcrypt.hashpw` never stores plaintext; output is always 60 bytes
- Correct vs wrong password verification
- Same password always produces different hashes (random salt)
- `Participant.discoverable` property: all four visibility/minor combos

#### `backend/tests/unit/test_offers_flow.py` (NEW)
- Guard logic unit tests (all four participant visibility states)
- Offer status transitions: pending→accepted, pending→rejected
- Terminal states cannot transition (409 guard)
- Expired offer triggers HTTP 410 path
- ConsentLog action string correctness
- Regression: rejection action is logged (was missing pre-fix)
- Lazy expiry marks stale offers correctly

---

## [0.2.0] — 2026-09 (initial public release)

- Privacy-first hybrid search (FTS + ANN, anonymised cards)
- Bayesian scoring engine with EVSK, half-life decay, LCB ranking
- W3C Verifiable Credentials 2.0 with EdDSA / JCS-2022
- Offer lifecycle with consent logging
- FSP mock data for demo mode
- React 18 + Vite 6 frontend
