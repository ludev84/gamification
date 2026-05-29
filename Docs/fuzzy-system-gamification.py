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
gamification = ctrl.Consequent(np.array([0, 1, 2, 3]), 'gamimfication')

# Membership functions
openness['low'] = fuzz.trapmf(openness.universe, [0, 0, 25, 50])
openness['medium'] = fuzz.trimf(openness.universe, [25, 50, 75])
openness['high'] = fuzz.trapmf(openness.universe, [50, 75, 100, 100])

conscientiousness['low'] = fuzz.trapmf(conscientiousness.universe, [0, 0, 25, 50])
conscientiousness['medium'] = fuzz.trimf(conscientiousness.universe, [25, 50, 75])
conscientiousness['high'] = fuzz.trapmf(conscientiousness.universe, [50, 75, 100, 100])

extraversion['low'] = fuzz.trapmf(extraversion.universe, [0, 0, 25, 50])
extraversion['medium'] = fuzz.trimf(extraversion.universe, [25, 50, 75])
extraversion['high'] = fuzz.trapmf(extraversion.universe, [50, 75, 100, 100])

agreeableness['low'] = fuzz.trapmf(agreeableness.universe, [0, 0, 25, 50])
agreeableness['medium'] = fuzz.trimf(agreeableness.universe, [25, 50, 75])
agreeableness['high'] = fuzz.trapmf(agreeableness.universe, [50, 75, 100, 100])

neuroticism['low'] = fuzz.trapmf(neuroticism.universe, [0, 0, 25, 50])
neuroticism['medium'] = fuzz.trimf(neuroticism.universe, [25, 50, 75])
neuroticism['high'] = fuzz.trapmf(neuroticism.universe, [50, 75, 100, 100])

# 2. Define singletons by providing the exact same coordinate for all 3 points
gamification['none'] = [1.0, 0.0, 0.0, 0.0]  # Snaps to 0
gamification['low'] = [0.0, 1.0, 0.0, 0.0]  # Snaps to 1
gamification['medium'] = [0.0, 0.0, 1.0, 0.0]  # Snaps to 2
gamification['high'] = [0.0, 0.0, 0.0, 1.0]  # Snaps to 3

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

psic1_rule1 = ctrl.Rule(openness[''])