# Notas de integración: platform → psicometric-FRONT

## What was built

**Backend (this repo)** — a new [soft_skills/api/](../soft_skills/api/) package that byte-for-byte mirrors the psychometric backend's conventions, so `soft_skills` can later be mounted into that project with zero frontend changes:

- **Auth shim** at `/users/login|logout|profile/` — DRF token carried in an httpOnly `auth_token` cookie ([authentication.py](../soft_skills/api/authentication.py)), envelope responses ([envelope.py](../soft_skills/api/envelope.py)). This shim is dropped at merge time; the portable API lives at `/learning/*`.
- **Learning endpoints** ([api/views.py](../soft_skills/api/views.py)): dashboard (level info, UI flags, streak week, badges, module cards, level selector with `is_recommended`), module lesson-path, lesson detail, answer submission, gamification-level pick, plus completion-gated summary/review endpoints. The anti-spoiler rule holds everywhere: the correct answer is never serialized until the user earns it (a mastered-question resubmit returns 409).
- **OCEAN ingestion** at `POST /learning/ocean-scores/` guarded by an `X-Internal-Api-Key` header or staff token: maps Spanish/English trait names accent-insensitively, normalizes to 0–100 from Likert bounds, runs the fuzzy system into the *recommended* level, and never touches the user's own pick ([services/ocean.py](../soft_skills/services/ocean.py)).
- **Shared-logic refactor**: the whole `submit_answer` flow moved into [services/answers.py](../soft_skills/services/answers.py) (now in a transaction) and dashboard builders into [services/dashboard.py](../soft_skills/services/dashboard.py), so the Django templates and the API run the same code — template behavior verified unchanged by new smoke tests.

**Frontend (psicometric-FRONT)** — new `/learning` section styled with their theme variables (white-label safe):

- Plumbing: `/platform-api → :8001` Vite proxy with `cookiePathRewrite` (so both backends' `auth_token` cookies coexist), [platformApiClient.ts](../psicometric-FRONT/src/lib/platformApiClient.ts), [types/learning.ts](../psicometric-FRONT/src/types/learning.ts), [learningMappers.ts](../psicometric-FRONT/src/lib/learningMappers.ts) with unit tests, and two services.
- Pages under [src/pages/learning/](../psicometric-FRONT/src/pages/learning/): gamified dashboard (level bar, streak week, badges, module grid, level selector tagged "· recomendado"), Duolingo-style module path with SVG progress rings, and the lesson player (one question at a time, feedback modal that only reveals the answer when correct, retry/wrap-around, XP pill/toast and CSS confetti scaled by the user's gamification flags, completion screens).
- Interim auth: `PlatformAuthGate` probes the platform session on entry and shows an inline login (or a friendly "no disponible" card if `:8001` is down) — the rest of the SPA is unaffected. "Aprendizaje" nav item added, and `LearningModuleCard` now renders internal router links when a rule's `moduleUrl` points at `#/learning/...`.

## To run it locally

```bash
python manage.py runserver 8001        # this repo (psychometric backend owns :8000)
cd psicometric-FRONT && npm run dev    # then open http://localhost:5173/#/learning
```

During the interim, a learner must exist in **both** databases with the same email. The full merge recipe (mount `soft_skills`, `backfill_profiles`, drop the shim, point `VITE_PLATFORM_API_URL` at the shared base) is in [Docs/api-integration-guide.md](api-integration-guide.md), including the exact OCEAN curl the psychometric backend should send.

Two notes: `PLATFORM_INTERNAL_API_KEY` in [settings.py](../django_project/settings.py) has a dev placeholder — change it before exposing the endpoint; and nothing has been committed in either repo (psicometric-FRONT is its own git repo on branch `gamification`).

## Verification (2026-07-12)

- 35 backend tests (`python manage.py test soft_skills`) — API auth/answers/OCEAN + template parity smoke tests.
- Frontend: `npm run typecheck`, 21 vitest tests, production build — all passing.
- Live E2E through the Vite proxy with both servers running: 12/12 checks (login + cookie path rewrite, dashboard, anti-spoiler on lesson GET and wrong answers, retry without XP, 409 on mastered question, lesson/module completion XP, OCEAN ingestion → fuzzy level 3 → "recomendado" updated, user level pick persisted).
