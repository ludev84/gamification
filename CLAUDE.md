# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Gamified soft-skills learning platform for TecNM (Instituto Tecnológico de Mérida). Duolingo-style sequential lessons of multiple-choice questions, with XP, dynamic levels, daily streaks, and badges. All UI/content is in Mexican Spanish (`LANGUAGE_CODE = 'es-mx'`, timezone `America/Merida`).

The current specification is [Docs/new_specs.md](Docs/new_specs.md) — admin-managed content, no LLM, no fuzzy logic. [Docs/specs.md](Docs/specs.md) is an older spec that described an LLM-generated MCQ + scikit-fuzzy distribution flow; that direction was abandoned. `scikit-fuzzy`, `scipy`, `numpy`, and `networkx` are still in [requirements.txt](requirements.txt) and [Docs/fuzzy-system-soft-skills.py](Docs/fuzzy-system-soft-skills.py) is a vestigial reference, but no app code depends on them.

## Common Commands

Always activate the local venv first (`.venv/`, gitignored — create with `python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt` if missing).

```bash
python manage.py runserver              # dev server
python manage.py makemigrations         # after model changes
python manage.py migrate
python manage.py createsuperuser        # admin access — required to author content
python manage.py shell
```

There is no test suite (`soft_skills/tests.py` is empty), no linter config, and no Docker/CI. SQLite DB lives at `db.sqlite3` (gitignored).

## Architecture

### Single-app layout

One Django project (`django_project/`) with one app (`soft_skills/`). All domain logic lives in [soft_skills/](soft_skills/). Project-level templates and the login page are in [templates/](templates/).

### Content hierarchy (admin-authored)

`Module` → `Lesson` → `MCQuestion`, each with `order` and `is_published`. Defined in [soft_skills/models.py](soft_skills/models.py). Content is created and assigned entirely through Django Admin ([soft_skills/admin.py](soft_skills/admin.py)) — there is no content-management UI for end users.

### Assignment doubles as progress

`UserModuleProgress` is the join row that **both** grants a user access to a module and tracks their progress on it. A user only sees a module if a `UserModuleProgress` row exists. Admins create these rows individually, or in bulk via the `assign_to_all_users` admin action on `ModuleAdmin`. Every access-checking view does `get_object_or_404(UserModuleProgress, user=request.user, module=...)` — preserve that pattern for new views.

### Gamification service

All XP / streak / badge / level rules live in [soft_skills/services/gamification.py](soft_skills/services/gamification.py) as `GamificationService` static methods. Views call it; do not duplicate XP/streak math elsewhere. XP constants are module-level in that file.

Levels are **dynamic** — computed as a percentage of `XP_max` for each user's *assigned* modules (`UserProfile.compute_xp_max()`), using `LEVEL_THRESHOLDS` in [models.py](soft_skills/models.py). `XP_max = M·80 + L·15 + P·10`. This means level boundaries shift as content is published or modules are (un)assigned.

Lesson XP is awarded **once** — `award_lesson_complete_xp` is a no-op if `xp_earned > 0`. Module-completion bonus +25 XP requires `score_percent >= 80`.

Lessons unlock sequentially within a module via `GamificationService.is_lesson_unlocked` — every prior published lesson must be completed.

An app-wide **`GAMIFICATION_LEVEL` setting (0–3)** in [settings.py](django_project/settings.py) controls how gamified the app is (see [gamification-tiers.md](gamification-tiers.md)). It selects the `LEVEL_THRESHOLDS` preset in [models.py](soft_skills/models.py), applies a ×1.5 XP multiplier at level 3 (`_scaled_xp` in the service), disables badge awarding below level 2 (`check_and_award_badges` returns early), and drives per-element UI flags (`gam_show_*`, `gam_confetti_level`, `gam_sound_level`, `gam_xp_feedback_level`) injected by [context_processors.py](soft_skills/context_processors.py). Level 0 hides all gamification UI but XP/streaks are still tracked in the DB. The setting is read at import time — restart the server after changing it.

### Question flow & AJAX SPA pattern

[soft_skills/views.py](soft_skills/views.py) and [soft_skills/templates/soft_skills/question.html](soft_skills/templates/soft_skills/question.html) implement an SPA-style flow without a JS framework:

- `question_view` and `submit_answer` both check `request.headers.get('X-Requested-With') == 'XMLHttpRequest'`. AJAX requests get the partial [_question_content.html](soft_skills/templates/soft_skills/_question_content.html); regular requests get the full page.
- Client-side JS in [question.html](soft_skills/templates/soft_skills/question.html) intercepts form submits and `data-spa` link clicks, fetches the partial, and swaps it into `#question-slot`.
- Classic non-AJAX fallback works via `request.session['answer_feedback']` plus a redirect — keep both paths working when modifying these views.

### Auth & profile bootstrap

[soft_skills/signals.py](soft_skills/signals.py) creates a `UserProfile` on `User` post-save (registered in [apps.py](soft_skills/apps.py) `ready()`). Code can rely on `request.user.profile` existing for any authenticated user. Login/logout views are wired in [django_project/urls.py](django_project/urls.py); the login template is at [templates/registration/login.html](templates/registration/login.html).

### Template context globals

[soft_skills/context_processors.py](soft_skills/context_processors.py) injects `gam_profile`, `gam_level_info`, and `gam_badge_count` into every template (registered in [settings.py](django_project/settings.py)). The top gamification bar in [base.html](templates/base.html) and elsewhere relies on these — don't pass them again from individual views.

### URL & language conventions

Routes use Spanish path segments: `/modulo/<id>/`, `/leccion/<id>/`, `/pregunta/<n>/`, `/responder/`, `/retroalimentacion/`, `/resumen/`. Match this when adding routes. Model `verbose_name` and admin labels are also in Spanish — keep that consistent for the admin UX.

### Badges

Badge conditions are evaluated in `GamificationService.check_and_award_badges`, called from `submit_answer` after every response. Adding a new badge type means: extend `BADGE_CONDITION_CHOICES` in [models.py](soft_skills/models.py) **and** add a branch to `check_and_award_badges`. `module_complete` / `module_high_score` use the optional `condition_module` FK; the others use `condition_value`.

Auto-award is **gated per user** by `BadgeAssignment`: `check_and_award_badges` only evaluates badges assigned to the user, so a user must have a badge assigned (by an admin, via the inline on the user's admin page) before they can see or earn it. Assigning an already-qualified badge earns it immediately, and unassigning removes the earned `UserBadge` — both wired in [signals.py](soft_skills/signals.py). `UserBadge` still records *earned* badges (drives `gam_badge_count`).

## Authoring MCQ content

Reference question format and example data are in [Docs/mcqs-empathy/](Docs/mcqs-empathy/) (`MCQs-format.json` is the canonical shape). Each question has a scenario, the question text, four options, the correct letter, and a per-option explanation (A/B/C/D). The MCQ JSON files there are not auto-loaded — there is no management command for ingestion yet; content is entered via Django Admin.
