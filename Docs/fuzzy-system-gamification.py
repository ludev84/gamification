import numpy as np
import matplotlib.pyplot as plt
import skfuzzy as fuzz
from skfuzzy import control as ctrl

# New Antecedent/Consequent objects hold universe variables and membership
# functions

openness = ctrl.Antecedent(np.arange(0,101,1), 'openness')
conscientiousness = ctrl.Antecedent(np.arange(0,101,1), 'conscientiousness')
extraversion = ctrl.Antecedent(np.arange(0,101,1), 'extraversion')
agreeableness = ctrl.Antecedent(np.arange(0,101,1), 'agreeableness')
neuroticism = ctrl.Antecedent(np.arange(0,101,1), 'neuroticism')

gamification = ctrl.Consequent(np.arange(0, 4, 0.01), 'gamification')

# Membership functions
for trait in [openness, conscientiousness, extraversion, agreeableness, neuroticism]:
    # Low: 1.0 from 0 to 20, falls to 0 at 40
    trait['low'] = fuzz.trapmf(trait.universe, [0, 0, 20, 40])
    
    # Medium: rises 20-40, plateaus 40-60, falls 60-80
    trait['medium'] = fuzz.trapmf(trait.universe, [20, 40, 60, 80])
    
    # High: rises 60-80, plateaus at 1.0 from 80 to 100
    trait['high'] = fuzz.trapmf(trait.universe, [60, 80, 100, 100])

# Singletons: triángulos degenerados con los 3 puntos en la misma coordenada.
gamification['none'] = fuzz.trimf(gamification.universe, [0, 0, 0])    # Snaps to 0
gamification['low'] = fuzz.trimf(gamification.universe, [1, 1, 1])     # Snaps to 1
gamification['medium'] = fuzz.trimf(gamification.universe, [2, 2, 2])  # Snaps to 2
gamification['high'] = fuzz.trimf(gamification.universe, [3, 3, 3])    # Snaps to 3

gamification.defuzzify_method = 'som'

# Rules
#
# Reglas difusas proporcionadas por dos psicólogos (rules.csv).
#
# Psicólogo 1 (2026/05/20):
# 1. SI Apertura es alto Y Responsabilidad es cualquiera Y Extraversión es medio Y Amabilidad es cualquiera Y Neuroticismo es medio, ENTONCES el nivel de gamificación apropiado es alto.
# 2. SI Apertura es bajo Y Responsabilidad es cualquiera Y Extraversión es alto Y Amabilidad es bajo Y Neuroticismo es alto, ENTONCES el nivel de gamificación apropiado es bajo.
# 3. SI Apertura es medio Y Responsabilidad es medio Y Extraversión es cualquiera Y Amabilidad es medio Y Neuroticismo es medio, ENTONCES el nivel de gamificación apropiado es medio.
# 4. SI Apertura es bajo Y Responsabilidad es cualquiera Y Extraversión es alto Y Amabilidad es cualquiera Y Neuroticismo es alto, ENTONCES el nivel de gamificación apropiado es nulo.
# 5. SI Apertura es cualquiera Y Responsabilidad es alto Y Extraversión es medio Y Amabilidad es cualquiera Y Neuroticismo es bajo, ENTONCES el nivel de gamificación apropiado es medio.
#
# Psicólogo 2 (2026/05/22):
# 6. SI Apertura es alto Y Responsabilidad es medio Y Extraversión es alto Y Amabilidad es cualquiera Y Neuroticismo es bajo, ENTONCES el nivel de gamificación apropiado es alto.
# 7. SI Apertura es cualquiera Y Responsabilidad es alto Y Extraversión es cualquiera Y Amabilidad es cualquiera Y Neuroticismo es bajo, ENTONCES el nivel de gamificación apropiado es medio.
# 8. SI Apertura es cualquiera Y Responsabilidad es cualquiera Y Extraversión es bajo Y Amabilidad es cualquiera Y Neuroticismo es alto, ENTONCES el nivel de gamificación apropiado es bajo.
# 9. SI Apertura es bajo Y Responsabilidad es alto Y Extraversión es bajo Y Amabilidad es cualquiera Y Neuroticismo es alto, ENTONCES el nivel de gamificación apropiado es nulo.
# 10. SI Apertura es medio Y Responsabilidad es medio Y Extraversión es medio Y Amabilidad es alto Y Neuroticismo es medio, ENTONCES el nivel de gamificación apropiado es medio.

# Antecedentes marcados como "cualquiera" se omiten de la regla (no restringen).

# Psicólogo 1
psic1_rule1 = ctrl.Rule(
    openness['high'] & extraversion['medium'] & neuroticism['medium'],
    gamification['high'])
psic1_rule2 = ctrl.Rule(
    openness['low'] & extraversion['high'] & agreeableness['low'] & neuroticism['high'],
    gamification['low'])
psic1_rule3 = ctrl.Rule(
    openness['medium'] & conscientiousness['medium'] & agreeableness['medium'] & neuroticism['medium'],
    gamification['medium'])
psic1_rule4 = ctrl.Rule(
    openness['low'] & extraversion['high'] & neuroticism['high'],
    gamification['none'])
psic1_rule5 = ctrl.Rule(
    conscientiousness['high'] & extraversion['medium'] & neuroticism['low'],
    gamification['medium'])

# Psicólogo 2
psic2_rule1 = ctrl.Rule(
    openness['high'] & conscientiousness['medium'] & extraversion['high'] & neuroticism['low'],
    gamification['high'])
psic2_rule2 = ctrl.Rule(
    conscientiousness['high'] & neuroticism['low'],
    gamification['medium'])
psic2_rule3 = ctrl.Rule(
    extraversion['low'] & neuroticism['high'],
    gamification['low'])
psic2_rule4 = ctrl.Rule(
    openness['low'] & conscientiousness['high'] & extraversion['low'] & neuroticism['high'],
    gamification['none'])
psic2_rule5 = ctrl.Rule(
    openness['medium'] & conscientiousness['medium'] & extraversion['medium'] & agreeableness['high'] & neuroticism['medium'],
    gamification['medium'])

rules = [
    psic1_rule1, psic1_rule2, psic1_rule3, psic1_rule4, psic1_rule5,
    psic2_rule1, psic2_rule2, psic2_rule3, psic2_rule4, psic2_rule5,
]

# Control system
gamification_ctrl = ctrl.ControlSystem(rules)
gamification_sim = ctrl.ControlSystemSimulation(gamification_ctrl)


def compute_gamification_level(openness_score, conscientiousness_score,
                               extraversion_score, agreeableness_score,
                               neuroticism_score):
    """Computa el nivel de gamificación (0=nulo, 1=bajo, 2=medio, 3=alto)
    a partir de los cinco rasgos de personalidad (escala 0-100)."""
    gamification_sim.input['openness'] = openness_score
    gamification_sim.input['conscientiousness'] = conscientiousness_score
    gamification_sim.input['extraversion'] = extraversion_score
    gamification_sim.input['agreeableness'] = agreeableness_score
    gamification_sim.input['neuroticism'] = neuroticism_score
    gamification_sim.compute()
    return gamification_sim.output['gamification']


if __name__ == '__main__':
    # Ejemplo de uso
    level = compute_gamification_level(
        openness_score=80,
        conscientiousness_score=50,
        extraversion_score=60,
        agreeableness_score=50,
        neuroticism_score=50,
    )
    print(f"Nivel de gamificación: {level}")
