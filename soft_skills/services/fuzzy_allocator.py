import numpy as np
import skfuzzy as fuzz
from django.conf import settings
from skfuzzy import control as ctrl

SKILL_SLUG_TO_ENGLISH = {
    'comunicacion': 'communication',
    'trabajo_en_equipo': 'teamwork',
    'liderazgo': 'leadership',
    'resolucion_de_problemas': 'problem_solving',
    'gestion_del_tiempo': 'time_management',
    'adaptabilidad': 'adaptability',
    'creatividad': 'creativity',
    'inteligencia_emocional': 'emotional_intelligence',
    'resolucion_de_conflictos': 'conflict_resolution',
    'pensamiento_critico': 'critical_thinking',
}

ENGLISH_TO_SKILL_SLUG = {v: k for k, v in SKILL_SLUG_TO_ENGLISH.items()}


class SoftSkillsFuzzyAllocator:
    def __init__(self):
        self.skill_level = ctrl.Antecedent(np.arange(0, 101, 1), 'skill_level')
        self.priority_weight = ctrl.Consequent(np.arange(0, 11, 0.1), 'priority_weight')
        self._setup_membership_functions()
        self._setup_rules()
        self.control_system = ctrl.ControlSystem(self.rules)
        self.simulation = ctrl.ControlSystemSimulation(self.control_system)

    def _setup_membership_functions(self):
        self.skill_level['Very_Poor'] = fuzz.trapmf(self.skill_level.universe, [0, 0, 25, 40])
        self.skill_level['Poor'] = fuzz.trimf(self.skill_level.universe, [25, 40, 60])
        self.skill_level['Adequate'] = fuzz.trimf(self.skill_level.universe, [45, 60, 80])
        self.skill_level['Good'] = fuzz.trapmf(self.skill_level.universe, [65, 80, 100, 100])

        self.priority_weight['Very_Low'] = fuzz.trapmf(self.priority_weight.universe, [0, 0, 2, 4])
        self.priority_weight['Low'] = fuzz.trimf(self.priority_weight.universe, [2, 4, 6])
        self.priority_weight['Medium'] = fuzz.trimf(self.priority_weight.universe, [4, 6, 8])
        self.priority_weight['High'] = fuzz.trimf(self.priority_weight.universe, [6, 8, 10])
        self.priority_weight['Very_High'] = fuzz.trapmf(self.priority_weight.universe, [8, 9, 10, 10])

    def _setup_rules(self):
        self.rules = [
            ctrl.Rule(self.skill_level['Very_Poor'], self.priority_weight['Very_High']),
            ctrl.Rule(self.skill_level['Poor'], self.priority_weight['High']),
            ctrl.Rule(self.skill_level['Adequate'], self.priority_weight['Medium']),
            ctrl.Rule(self.skill_level['Good'], self.priority_weight['Low']),
        ]

    def calculate_priority_weights(self, skill_scores):
        priority_weights = {}
        for skill, score in skill_scores.items():
            self.simulation.input['skill_level'] = score
            self.simulation.compute()
            priority_weights[skill] = self.simulation.output['priority_weight']
        return priority_weights

    def allocate_mcqs(self, skill_scores, total_mcqs=100):
        priority_weights = self.calculate_priority_weights(skill_scores)
        total_weight = sum(priority_weights.values())

        if total_weight == 0:
            equal_share = total_mcqs // len(skill_scores)
            return {skill: equal_share for skill in skill_scores.keys()}

        mcq_allocation = {}
        remaining_mcqs = total_mcqs

        decimal_shares = {}
        for skill, weight in priority_weights.items():
            share = (weight / total_weight) * total_mcqs
            integer_part = int(share)
            decimal_part = share - integer_part
            mcq_allocation[skill] = integer_part
            decimal_shares[skill] = decimal_part
            remaining_mcqs -= integer_part

        if remaining_mcqs > 0:
            sorted_skills = sorted(decimal_shares.items(), key=lambda x: x[1], reverse=True)
            for i in range(remaining_mcqs):
                skill = sorted_skills[i][0]
                mcq_allocation[skill] += 1

        return mcq_allocation


def allocate_mcqs_for_user(user_profile, total_mcqs=None):
    if total_mcqs is None:
        total_mcqs = settings.TOTAL_MCQS_PER_USER

    scores_dict = user_profile.get_skill_scores_dict()

    # Map Spanish slugs to English keys for the fuzzy system
    english_scores = {
        SKILL_SLUG_TO_ENGLISH[slug]: score
        for slug, score in scores_dict.items()
        if slug in SKILL_SLUG_TO_ENGLISH
    }

    allocator = SoftSkillsFuzzyAllocator()
    english_allocation = allocator.allocate_mcqs(english_scores, total_mcqs)

    # Map back to Spanish slugs
    return {
        ENGLISH_TO_SKILL_SLUG[eng_key]: count
        for eng_key, count in english_allocation.items()
    }
