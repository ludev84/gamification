# Gamification Tiers — Level Thresholds

> **Implementation note:** the app-wide setting `GAMIFICATION_LEVEL` (0–3) in
> [django_project/settings.py](django_project/settings.py) selects the threshold preset:
> app level 0 → Tier 1 (hidden, medium spacing internally), 1 → Tier 2 Low, 2 → Tier 3 Medium,
> 3 → Tier 4 High (plus a ×1.5 XP multiplier). Presets live in `LEVEL_THRESHOLD_PCTS`
> ([soft_skills/models.py](soft_skills/models.py)); restart the server after changing the setting.

Four tiers of gamification, differing in **how easy it is to climb the levels**. A user's level is
the highest band whose threshold their XP ratio (`total_xp / XP_max`) has reached, so a **lower
final threshold makes the top level easier to reach** (= more gamified).

The five level names are the same across all tiers:

| Level | Name |
|---|---|
| 1 | Explorador Interpersonal |
| 2 | Comunicador Asertivo |
| 3 | Colaborador Clave |
| 4 | Líder Empático |
| 5 | Estratega Humano |

Only the **thresholds** (each level's required % of `XP_max`) change per tier:

| Level | Tier 1 — Off | Tier 2 — Low | Tier 3 — Medium | Tier 4 — High |
|---|---|---|---|---|
| 1 | 0% | 0% | 0% | 0% |
| 2 | 15% | 25% | 15% | 10% |
| 3 | 40% | 50% | 40% | 25% |
| 4 | 65% | 75% | 65% | 45% |
| 5 | 85% | 95% | 85% | 65% |

**XP multiplier:** Tiers 1–3 award XP at ×1.0; **Tier 4 applies a ×1.5 multiplier** (`_scaled_xp`
in [soft_skills/services/gamification.py](soft_skills/services/gamification.py)), so XP accumulates
faster *and* the top level needs a lower threshold — making level 5 easier still at Tier 4.

## Tier notes

- **Tier 1 — Off:** no gamification is shown (no XP, levels, or streak UI). XP is still tracked in
  the background, so the thresholds above are used only internally; they mirror the medium spacing.
- **Tier 2 — Low:** widest spacing → **hardest** to reach level 5 (≈ 95% of `XP_max`). Leveling up
  is rare and understated.
- **Tier 3 — Medium:** balanced default.
- **Tier 4 — High:** tightest spacing → **easiest** to reach level 5 (≈ 65% of `XP_max`), plus a
  **×1.5 XP multiplier**. Users level up often, well before completing all content.
