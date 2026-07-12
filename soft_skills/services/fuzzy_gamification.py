"""Sistema difuso que recomienda el nivel de gamificación (0-3) a partir de
los cinco rasgos OCEAN (escala 0-100).

Port de Docs/fuzzy-system-gamification.py para uso dentro de la app (sin
matplotlib). Las reglas provienen de dos psicólogos (ver comentarios en el
script original). El sistema de control se construye una sola vez de forma
perezosa; cada cómputo usa su propia simulación para no compartir estado.
"""

import numpy as np
import skfuzzy as fuzz
from skfuzzy import control as ctrl
from skfuzzy.control.controlsystem import CrispValueCalculator

_control_system = None
_consequent = None


def _build_control_system():
    openness = ctrl.Antecedent(np.arange(0, 101, 1), 'openness')
    conscientiousness = ctrl.Antecedent(np.arange(0, 101, 1), 'conscientiousness')
    extraversion = ctrl.Antecedent(np.arange(0, 101, 1), 'extraversion')
    agreeableness = ctrl.Antecedent(np.arange(0, 101, 1), 'agreeableness')
    neuroticism = ctrl.Antecedent(np.arange(0, 101, 1), 'neuroticism')

    gamification = ctrl.Consequent(np.arange(0, 4, 0.01), 'gamification')

    for trait in [openness, conscientiousness, extraversion, agreeableness, neuroticism]:
        trait['low'] = fuzz.trapmf(trait.universe, [0, 0, 20, 40])
        trait['medium'] = fuzz.trapmf(trait.universe, [20, 40, 60, 80])
        trait['high'] = fuzz.trapmf(trait.universe, [60, 80, 100, 100])

    # Singletons: triángulos degenerados con los 3 puntos en la misma coordenada.
    gamification['none'] = fuzz.trimf(gamification.universe, [0, 0, 0])
    gamification['low'] = fuzz.trimf(gamification.universe, [1, 1, 1])
    gamification['medium'] = fuzz.trimf(gamification.universe, [2, 2, 2])
    gamification['high'] = fuzz.trimf(gamification.universe, [3, 3, 3])

    gamification.defuzzify_method = 'som'

    # Antecedentes marcados como "cualquiera" se omiten de la regla (no restringen).
    rules = [
        # Psicólogo 1 (2026/05/20)
        ctrl.Rule(openness['high'] & extraversion['medium'] & neuroticism['medium'],
                  gamification['high']),
        ctrl.Rule(openness['low'] & extraversion['high'] & agreeableness['low'] & neuroticism['high'],
                  gamification['low']),
        ctrl.Rule(openness['medium'] & conscientiousness['medium'] & agreeableness['medium'] & neuroticism['medium'],
                  gamification['medium']),
        ctrl.Rule(openness['low'] & extraversion['high'] & neuroticism['high'],
                  gamification['none']),
        ctrl.Rule(conscientiousness['high'] & extraversion['medium'] & neuroticism['low'],
                  gamification['medium']),
        # Psicólogo 2 (2026/05/22)
        ctrl.Rule(openness['high'] & conscientiousness['medium'] & extraversion['high'] & neuroticism['low'],
                  gamification['high']),
        ctrl.Rule(conscientiousness['high'] & neuroticism['low'],
                  gamification['medium']),
        ctrl.Rule(extraversion['low'] & neuroticism['high'],
                  gamification['low']),
        ctrl.Rule(openness['low'] & conscientiousness['high'] & extraversion['low'] & neuroticism['high'],
                  gamification['none']),
        ctrl.Rule(openness['medium'] & conscientiousness['medium'] & extraversion['medium'] & agreeableness['high'] & neuroticism['medium'],
                  gamification['medium']),
    ]

    return ctrl.ControlSystem(rules), gamification


def compute_gamification_level(openness_score, conscientiousness_score,
                               extraversion_score, agreeableness_score,
                               neuroticism_score):
    """Computa el nivel de gamificación (0=nulo, 1=bajo, 2=medio, 3=alto)
    a partir de los cinco rasgos de personalidad (escala 0-100).

    Devuelve un entero 0-3, o None si ninguna regla se activa con los
    puntajes dados (skfuzzy no puede defuzzificar en ese caso).
    """
    global _control_system, _consequent
    if _control_system is None:
        _control_system, _consequent = _build_control_system()

    sim = ctrl.ControlSystemSimulation(_control_system)
    sim.input['openness'] = openness_score
    sim.input['conscientiousness'] = conscientiousness_score
    sim.input['extraversion'] = extraversion_score
    sim.input['agreeableness'] = agreeableness_score
    sim.input['neuroticism'] = neuroticism_score
    try:
        sim.compute()
        crisp = sim.output['gamification']
    except (ValueError, KeyError):
        # Ninguna regla se activó — no hay recomendación.
        return None

    # Con defuzzificación 'som' una salida agregada totalmente en cero no lanza
    # error: devuelve 0.0, indistinguible de una recomendación real de nivel 0.
    # Detectarlo revisando la membresía agregada del consecuente.
    _, output_mf, _ = CrispValueCalculator(_consequent, sim).find_memberships()
    if not np.any(output_mf):
        return None

    return max(0, min(3, round(crisp)))
