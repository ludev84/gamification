# Gamification — current state

As-built reference for the XP, level, streak, and badge systems running in the project today. Source files referenced inline.

---

## 1. Overview

| Element | Where it lives |
|---|---|
| XP awards & streak/badge logic | [soft_skills/services/gamification.py](../soft_skills/services/gamification.py) |
| XP, level, streak fields on the user | `UserProfile` in [soft_skills/models.py](../soft_skills/models.py) |
| Level definitions | `LEVEL_THRESHOLDS` in [soft_skills/models.py](../soft_skills/models.py) |
| Badges schema | `Badge` + `UserBadge` + `BADGE_CONDITION_CHOICES` in [soft_skills/models.py](../soft_skills/models.py) |
| Daily activity counters | `DailyActivity` in [soft_skills/models.py](../soft_skills/models.py) |
| Hook points (when XP/streak/badges fire) | `module_view`, `submit_answer` in [soft_skills/views.py](../soft_skills/views.py) |
| Template-wide level/badge context | `gamification_context` in [soft_skills/context_processors.py](../soft_skills/context_processors.py) |

`UserProfile` is auto-created via the `post_save` signal in [soft_skills/signals.py](../soft_skills/signals.py), so any authenticated user is guaranteed to have one.

---

## 2. XP — how it is earned

All XP constants live at the top of [soft_skills/services/gamification.py](../soft_skills/services/gamification.py). XP is added to `UserProfile.total_xp` via `UserProfile.add_xp()`.

| Trigger | XP | Constant | Notes |
|---|---|---|---|
| Answering a question correctly (first attempt) | **+10** | `XP_CORRECT` | First attempt only — retries don't award XP. |
| Answering a question incorrectly (first attempt) | **+5** | `XP_INCORRECT` | Consolation XP; awarded once per question. |
| Starting a new module | **+30** | `XP_MODULE_STARTED` | Awarded on first visit to the module page (`is_started` flips to true). |
| Completing a lesson | **+15** | `XP_LESSON_FINISHED` | Idempotent — `award_lesson_complete_xp` no-ops if `xp_earned > 0` on `UserLessonProgress`. |
| Completing a module | **+50** | `XP_MODULE_FINISHED` | Awarded when every published lesson in the module is completed. |
| Module high-score bonus | **+25** | `XP_HIGH_SCORE_BONUS` | Added on top of `XP_MODULE_FINISHED` when `score_percent >= 80`. |

**Streaks no longer award XP.** Streak counters and `DailyActivity` are still maintained (see §4), but `update_streak` does not touch `total_xp`.

### Per-attempt accounting on `UserResponse`

`UserResponse` carries `is_correct` (locked at first-attempt result, never changes) and `is_completed` (flips to `True` once the user eventually gets it right, even on retry). XP on `UserResponse.xp_earned` is whatever was paid on the first attempt (`XP_CORRECT` or `XP_INCORRECT`).

---

## 3. Level system

### 3.1 Levels & thresholds

Defined in [soft_skills/models.py](../soft_skills/models.py) as `LEVEL_THRESHOLDS = [(level, pct_of_xp_max, name), …]`:

| Level | Name | Threshold (% of XP_max) |
|---|---|---|
| 1 | Explorador Interpersonal | 0 % |
| 2 | Comunicador Asertivo | 15 % |
| 3 | Colaborador Clave | 40 % |
| 4 | Líder Empático | 65 % |
| 5 | Estratega Humano | 85 % |

### 3.2 Dynamic XP_max

The ceiling against which levels are measured is **per-user** and recomputed on every read (`UserProfile.compute_xp_max()`):

```
XP_max = (M × 80) + (L × 15) + (P × 10)
```

where, restricted to published content **assigned** to the user (i.e., reachable via `UserModuleProgress`):

- `M` = number of modules
- `L` = number of lessons across those modules
- `P` = number of MCQs across those lessons

Implications:

- A user's level boundaries shift if admins publish more content or assign/unassign modules.
- The formula represents the XP earnable from one full pass through assigned content. The +25 high-score bonus is *not* included in `XP_max`, so a user who consistently scores ≥80 % can reach the level-5 threshold before finishing all content.
- If `XP_max == 0` (e.g. no modules assigned), the user stays at level 1 and `xp_progress_percent` returns 0.

### 3.3 Reading current level info

Use `GamificationService.get_level_info(user)` (called by the context processor) — it returns:

```
{
  'level':            int,           # current level number
  'name':             str,           # current level name
  'total_xp':         int,           # total XP earned
  'xp_max':           int,           # dynamic ceiling
  'next_threshold':   int | None,    # XP needed for next level, None at max
  'next_name':        str | None,
  'progress_percent': int            # 0–100 within the current band
}
```

`UserProfile` also exposes equivalent properties directly: `.level`, `.level_name`, `.xp_for_next_level`, `.xp_progress_percent`.

---

## 4. Streaks

Two independent counters live on `UserProfile`.

### 4.1 Daily streak (lesson-completion streak)

| Field | Meaning |
|---|---|
| `current_streak` | Consecutive calendar days on which the user completed at least one lesson. |
| `longest_streak` | All-time max of `current_streak`. |
| `last_activity_date` | Date of the most recent lesson completion (local time, `America/Merida`). |

Updated by `GamificationService.update_streak`, called from `submit_answer` whenever a lesson is freshly completed:

- Same-day re-completions don't bump the streak.
- Gap of exactly 1 day → `current_streak += 1`.
- Gap > 1 day → `current_streak = 1` (reset).
- Awards no XP.

### 4.2 Answer streak (cross-lesson correctness streak)

| Field | Meaning |
|---|---|
| `current_answer_streak` | Consecutive *first-attempt-correct* answers across all lessons and modules. |
| `longest_answer_streak` | All-time max. |

Updated inline in `submit_answer` ([soft_skills/views.py](../soft_skills/views.py)):

- Increments on a correct first attempt.
- Resets to 0 on an incorrect first attempt.
- Retries do **not** affect it (the comment on the field documents this guarantee).
- Surfaced in the navbar chip in [templates/base.html](../templates/base.html); the SPA controller in [question.html](../soft_skills/templates/soft_skills/question.html) re-syncs it from a hidden `.streak-sync` marker after each AJAX swap.

---

## 5. Badges

### 5.1 Schema

`Badge` (admin-authored) has:

- `slug`, `name`, `description`, `icon`
- `condition_type` (one of the 8 below)
- `condition_value` (int — interpretation depends on the type)
- `condition_module` (FK, used only for module-specific types)

`UserBadge` is the join row, unique per `(user, badge)`. The badge count in the gamification bar comes from `gam_badge_count` (context processor).

### 5.2 Condition types

All evaluated in `GamificationService.check_and_award_badges`, called after every answer submission.

| `condition_type` | Earned when … | Uses `condition_value` | Uses `condition_module` |
|---|---|---|---|
| `streak` | `profile.current_streak >= condition_value` | yes (days) | no |
| `questions_answered` | total `UserResponse` rows ≥ value | yes (count) | no |
| `questions_correct` | total `UserResponse` rows with `is_correct=True` ≥ value | yes (count) | no |
| `lessons_completed` | total completed `UserLessonProgress` ≥ value | yes (count) | no |
| `modules_completed` | total completed `UserModuleProgress` ≥ value | yes (count) | no |
| `all_modules` | every assigned `UserModuleProgress` is completed (and ≥1 is assigned) | no | no |
| `module_complete` | the specified module is completed | no | **yes** |
| `module_high_score` | the specified module is completed *and* `score_percent >= condition_value` | yes (pct, e.g. 80) | **yes** |

Badges are not retroactive in code, but the check runs on every submission, so any condition that becomes true will be picked up on the next answer. Badges themselves grant no XP.

Adding a new condition type means extending both `BADGE_CONDITION_CHOICES` in [models.py](../soft_skills/models.py) **and** adding a branch in `check_and_award_badges`.

---

## 6. Daily activity

`DailyActivity` (one row per user per date, `America/Merida`) tracks:

- `questions_answered` — incremented in `submit_answer` on each first-attempt response.
- `lessons_completed` — incremented in `update_streak` on each freshly completed lesson.

Currently used to drive streak detection; no UI surfaces these counts directly yet.

---

## 7. End-to-end example

A user is assigned one module with 3 lessons and 18 questions total.

- `XP_max = 1·80 + 3·15 + 18·10 = 305`.
- Level thresholds for this user: L2 at 46 XP (`0.15·305`), L3 at 122, L4 at 198, L5 at 259.
- Day 1, opens the module → **+30** (start). Answers 6 questions correct, 0 wrong, finishes lesson 1 → **6·10 + 15 = 75**. Total: **105 XP** → level 2.
- Day 2, finishes lesson 2 (6 correct) → **75 more**. Total: **180 XP** → level 3. Daily streak = 2.
- Day 3, finishes lesson 3 (6 correct), completes the module with 100 % score → **75 + 50 + 25 = 150**. Total: **330 XP**. Streak = 3. Capped at level 5; `xp_progress_percent` returns 100.

Note that **the user crossed `XP_max` (330 > 305)** purely from the high-score bonus, because that bonus is not part of the `XP_max` formula. This is by design today; flag it if you want strict alignment.
