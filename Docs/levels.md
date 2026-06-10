# Levels & XP

Summary of how user levels and XP work in the gamification system. There are two unrelated things
called "level" — this document covers the **user level system**; the client-side
`GAMIFICATION_LEVEL` visual toggle is noted at the end.

## 1. How user levels work

Levels are **dynamic and computed, never stored**. A user's level is derived on the fly from the
ratio of their `total_xp` to a personalized maximum `XP_max`.

- **`XP_max`** = `(M × 80) + (L × 15) + (P × 10)`, where M/L/P are the count of **published**
  modules, lessons, and questions across the modules **assigned to that user**
  ([UserProfile.compute_xp_max](../soft_skills/models.py)). Because it's based on assigned +
  published content, level boundaries shift as content is published or modules are (un)assigned.
- **Level** = the highest threshold whose percentage `ratio = total_xp / XP_max` has reached
  ([UserProfile.level](../soft_skills/models.py)). If `XP_max` is 0, level is 1.
- **Thresholds** are 5 fixed percentage bands (`LEVEL_THRESHOLDS` in
  [models.py](../soft_skills/models.py)):

| Level | At ≥ % of XP_max | Name |
|---|---|---|
| 1 | 0% | Explorador Interpersonal |
| 2 | 15% | Comunicador Asertivo |
| 3 | 40% | Colaborador Clave |
| 4 | 65% | Líder Empático |
| 5 | 85% | Estratega Humano |

Supporting computed properties on `UserProfile`: `level_name`, `xp_for_next_level`,
`xp_progress_percent` ([models.py](../soft_skills/models.py)). For the UI,
[GamificationService.get_level_info](../soft_skills/services/gamification.py) packages the current
level, name, next threshold, and progress bar percent.

## 2. Where it's defined

- **[soft_skills/models.py](../soft_skills/models.py)** — `LEVEL_THRESHOLDS` constant and all the
  `UserProfile` computation (`compute_xp_max`, `level`, `level_name`, `xp_for_next_level`,
  `xp_progress_percent`, `add_xp`).
- **[soft_skills/services/gamification.py](../soft_skills/services/gamification.py)** — `XP_*`
  award constants, the `award_*` methods, and `get_level_info` (UI-facing level data).
- **[soft_skills/context_processors.py](../soft_skills/context_processors.py)** — injects
  `gam_level_info` into every template so the top gamification bar can render it.

## 3. All the ways a user gains XP

Every XP gain flows through `user.profile.add_xp()` ([models.py](../soft_skills/models.py)), called
only by the `GamificationService.award_*` methods
([gamification.py](../soft_skills/services/gamification.py)). The amounts are the module-level
`XP_*` constants in the same file:

| Method | XP | When |
|---|---|---|
| `award_response_xp` (correct) | **+10** (`XP_CORRECT`) | Answering a question correctly, first attempt |
| `award_response_xp` (incorrect) | **+5** (`XP_INCORRECT`) | Answering incorrectly, first attempt. **Retries award 0** |
| `award_module_start_xp` | **+30** (`XP_MODULE_STARTED`) | Starting a module — granted on the user's **first answer** in it, in `submit_answer` |
| `award_lesson_complete_xp` | **+15** (`XP_LESSON_FINISHED`) | Completing a lesson — awarded **once** (no-op if `xp_earned > 0` already) |
| `award_module_complete_xp` | **+50** (`XP_MODULE_FINISHED`) | Completing all lessons in a module |
| `award_module_complete_xp` (bonus) | **+25** (`XP_HIGH_SCORE_BONUS`) | Same call, *added on top* when module `score_percent ≥ 80` |

All of these are invoked from [submit_answer](../soft_skills/views.py) after an answer is processed
(module-start on first answer; lesson/module completion when the respective thresholds are
reached). Badges grant **no** XP.

---

**Disambiguation:** the `GAMIFICATION_LEVEL` (1–4) in
[question.html](../soft_skills/templates/soft_skills/question.html) is unrelated — it's only a
client-side toggle for how the XP **feedback visuals** (pill/toast) display, and has no effect on
XP amounts or user levels.
