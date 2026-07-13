"""OCEAN score ingestion from the psychometric system.

The psychometric backend scores a Big Five questionnaire whose Variables are
named after the five traits (convention). This service maps those free-form
names to UserProfile.ocean_* fields, normalizes to 0-100, and re-runs the
fuzzy recommendation (gamification_level_admin). The user's own level pick
(gamification_level_user) is never touched.
"""

import unicodedata

# Alias (accent-stripped, lowercase) → UserProfile field.
TRAIT_FIELD_BY_ALIAS = {
    'apertura': 'ocean_openness',
    'apertura a la experiencia': 'ocean_openness',
    'openness': 'ocean_openness',
    'o': 'ocean_openness',
    'responsabilidad': 'ocean_conscientiousness',
    'escrupulosidad': 'ocean_conscientiousness',
    'conscientiousness': 'ocean_conscientiousness',
    'c': 'ocean_conscientiousness',
    'extraversion': 'ocean_extraversion',
    'e': 'ocean_extraversion',
    'amabilidad': 'ocean_agreeableness',
    'agreeableness': 'ocean_agreeableness',
    'a': 'ocean_agreeableness',
    'neuroticismo': 'ocean_neuroticism',
    'neuroticism': 'ocean_neuroticism',
    'n': 'ocean_neuroticism',
}


def normalize_trait_name(name):
    """Accent-stripped, lowercased, trimmed key for alias lookup."""
    decomposed = unicodedata.normalize('NFD', str(name))
    stripped = ''.join(ch for ch in decomposed if not unicodedata.combining(ch))
    return stripped.lower().strip()


def normalize_score(value, min_value=None, max_value=None):
    """Scale a raw score to 0-100 given the questionnaire's bounds. Without
    bounds the value is assumed to already be on the 0-100 scale. Returns an
    int clamped to [0, 100], or None if the bounds are unusable."""
    if min_value is None or max_value is None:
        scaled = float(value)
    else:
        span = float(max_value) - float(min_value)
        if span <= 0:
            return None
        scaled = (float(value) - float(min_value)) / span * 100
    return int(max(0, min(100, round(scaled))))


def apply_ocean_scores(profile, scores):
    """Applies a list of {'name', 'value', 'min'?, 'max'?} score entries to the
    profile, recomputes the fuzzy recommendation, and saves.

    Returns {'applied': {field: value}, 'warnings': [...], 'computed_level': int|None}.
    """
    applied = {}
    warnings = []

    for entry in scores:
        name = entry.get('name', '')
        field = TRAIT_FIELD_BY_ALIAS.get(normalize_trait_name(name))
        if field is None:
            warnings.append(f'Rasgo no reconocido: "{name}" — ignorado.')
            continue

        normalized = normalize_score(
            entry.get('value'), entry.get('min'), entry.get('max')
        )
        if normalized is None:
            warnings.append(f'Rasgo "{name}": rango min/max inválido — ignorado.')
            continue

        setattr(profile, field, normalized)
        applied[field] = normalized

    computed_level = profile.apply_fuzzy_gamification_level()
    if applied and computed_level is None:
        ocean_fields = set(TRAIT_FIELD_BY_ALIAS.values())
        if any(getattr(profile, f) is None for f in ocean_fields):
            warnings.append(
                'Puntajes OCEAN incompletos: el nivel de gamificación recomendado no se recalculó.'
            )
        else:
            warnings.append(
                'Ninguna regla difusa se activó con estos puntajes: el nivel recomendado no cambió.'
            )

    profile.save()
    return {
        'applied': applied,
        'warnings': warnings,
        'computed_level': computed_level,
    }
