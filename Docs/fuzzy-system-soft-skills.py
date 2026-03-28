import numpy as np
import skfuzzy as fuzz
from skfuzzy import control as ctrl

class SoftSkillsFuzzyAllocator:
    def __init__(self):
        # Define antecedent (input) - Skill Level (0-100)
        self.skill_level = ctrl.Antecedent(np.arange(0, 101, 1), 'skill_level')

        # Define consequent (output) - Training Priority Weight (0-10)
        self.priority_weight = ctrl.Consequent(np.arange(0, 11, 0.1), 'priority_weight')

        # Setup membership functions
        self._setup_membership_functions()

        # Setup fuzzy rules
        self._setup_rules()

        # Create control system
        self.control_system = ctrl.ControlSystem(self.rules)
        self.simulation = ctrl.ControlSystemSimulation(self.control_system)

    def _setup_membership_functions(self):
        # Skill Level membership functions
        self.skill_level['Very_Poor'] = fuzz.trapmf(self.skill_level.universe, [0, 0, 25, 40])
        self.skill_level['Poor'] = fuzz.trimf(self.skill_level.universe, [25, 40, 60])
        self.skill_level['Adequate'] = fuzz.trimf(self.skill_level.universe, [45, 60, 80])
        self.skill_level['Good'] = fuzz.trapmf(self.skill_level.universe, [65, 80, 100, 100])

        # Priority Weight membership functions
        self.priority_weight['Very_Low'] = fuzz.trapmf(self.priority_weight.universe, [0, 0, 2, 4])
        self.priority_weight['Low'] = fuzz.trimf(self.priority_weight.universe, [2, 4, 6])
        self.priority_weight['Medium'] = fuzz.trimf(self.priority_weight.universe, [4, 6, 8])
        self.priority_weight['High'] = fuzz.trimf(self.priority_weight.universe, [6, 8, 10])
        self.priority_weight['Very_High'] = fuzz.trapmf(self.priority_weight.universe, [8, 9, 10, 10])

    def _setup_rules(self):
        # Define fuzzy rules
        self.rules = [
            ctrl.Rule(self.skill_level['Very_Poor'], self.priority_weight['Very_High']),
            ctrl.Rule(self.skill_level['Poor'], self.priority_weight['High']),
            ctrl.Rule(self.skill_level['Adequate'], self.priority_weight['Medium']),
            ctrl.Rule(self.skill_level['Good'], self.priority_weight['Low'])
        ]

    def calculate_priority_weights(self, skill_scores):
        """Calculate raw priority weights for each skill"""
        priority_weights = {}

        for skill, score in skill_scores.items():
            self.simulation.input['skill_level'] = score
            self.simulation.compute()
            priority_weights[skill] = self.simulation.output['priority_weight']

        return priority_weights

    def allocate_mcqs(self, skill_scores, total_mcqs=100):
        """
        Allocate MCQs to skills based on their scores
        Returns exactly total_mcqs distributed across all skills
        """
        # Step 1: Calculate raw priority weights
        priority_weights = self.calculate_priority_weights(skill_scores)

        # Step 2: Calculate total weight for normalization
        total_weight = sum(priority_weights.values())

        if total_weight == 0:
            # If all weights are zero, distribute equally
            equal_share = total_mcqs // len(skill_scores)
            return {skill: equal_share for skill in skill_scores.keys()}

        # Step 3: Calculate percentage share and initial MCQ allocation
        mcq_allocation = {}
        remaining_mcqs = total_mcqs

        # First pass: calculate shares and assign integer parts
        decimal_shares = {}
        for skill, weight in priority_weights.items():
            share = (weight / total_weight) * total_mcqs
            integer_part = int(share)
            decimal_part = share - integer_part

            mcq_allocation[skill] = integer_part
            decimal_shares[skill] = decimal_part
            remaining_mcqs -= integer_part

        # Step 4: Distribute remaining MCQs based on highest decimal parts
        if remaining_mcqs > 0:
            # Sort skills by decimal part in descending order
            sorted_skills = sorted(decimal_shares.items(), key=lambda x: x[1], reverse=True)

            # Distribute remaining MCQs to skills with highest decimal parts
            for i in range(remaining_mcqs):
                skill = sorted_skills[i][0]
                mcq_allocation[skill] += 1

        return mcq_allocation

    def get_detailed_allocation(self, skill_scores, total_mcqs=100):
        """Get detailed breakdown of the allocation process"""
        priority_weights = self.calculate_priority_weights(skill_scores)
        mcq_allocation = self.allocate_mcqs(skill_scores, total_mcqs)
        total_weight = sum(priority_weights.values())

        detailed_info = {
            'skill_scores': skill_scores,
            'priority_weights': priority_weights,
            'mcq_allocation': mcq_allocation,
            'total_weight': total_weight,
            'percentage_breakdown': {}
        }

        # Calculate percentage breakdown
        for skill in skill_scores.keys():
            percentage = (priority_weights[skill] / total_weight * 100) if total_weight > 0 else 0
            detailed_info['percentage_breakdown'][skill] = percentage

        return detailed_info

    def plot_membership_functions(self):
        """Visualize the membership functions"""
        import matplotlib.pyplot as plt

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))

        self.skill_level.view(ax=ax1)
        ax1.set_title('Skill Level Membership Functions')
        ax1.set_ylabel('Membership')

        self.priority_weight.view(ax=ax2)
        ax2.set_title('Training Priority Weight Membership Functions')
        ax2.set_ylabel('Membership')

        plt.tight_layout()
        plt.show()

def print_allocation_summary(detailed_info):
    """Print a formatted summary of the allocation"""
    print("=" * 70)
    print("SOFT SKILLS MCQ ALLOCATION SYSTEM")
    print("=" * 70)

    print(f"\n{'SKILL':<25} {'SCORE':<8} {'WEIGHT':<8} {'SHARE %':<10} {'MCQs':<6}")
    print("-" * 70)

    total_mcqs = 0
    for skill in detailed_info['skill_scores']:
        score = detailed_info['skill_scores'][skill]
        weight = detailed_info['priority_weights'][skill]
        percentage = detailed_info['percentage_breakdown'][skill]
        mcqs = detailed_info['mcq_allocation'][skill]
        total_mcqs += mcqs

        print(f"{skill:<25} {score:<8} {weight:<8.2f} {percentage:<10.2f} {mcqs:<6}")

    print("-" * 70)
    print(f"{'TOTAL':<25} {'':<8} {detailed_info['total_weight']:<8.2f} {'100.00':<10} {total_mcqs:<6}")

    # Show priority skills (top 3 by MCQ allocation)
    sorted_skills = sorted(detailed_info['mcq_allocation'].items(),
                          key=lambda x: x[1], reverse=True)[:3]

    print(f"\nTOP PRIORITY SKILLS:")
    for i, (skill, mcqs) in enumerate(sorted_skills, 1):
        print(f"  {i}. {skill} ({mcqs} MCQs)")

# Example usage and testing
def main():
    # Create the fuzzy allocator
    allocator = SoftSkillsFuzzyAllocator()

    # Test case 1: Mixed skill levels
    print("TEST CASE 1: Mixed Skill Levels")
    skill_scores_1 = {
        'communication': 25,
        'teamwork': 75,
        'leadership': 35,
        'problem_solving': 60,
        'time_management': 85,
        'adaptability': 45,
        'creativity': 55,
        'emotional_intelligence': 70,
        'conflict_resolution': 20,
        'critical_thinking': 65
    }

    detailed_info_1 = allocator.get_detailed_allocation(skill_scores_1)
    print_allocation_summary(detailed_info_1)

    # Test case 2: All high scores
    print("\n\n" + "="*70)
    print("TEST CASE 2: All High Scores")
    skill_scores_2 = {
        'communication': 85,
        'teamwork': 90,
        'leadership': 80,
        'problem_solving': 75,
        'time_management': 88,
        'adaptability': 82,
        'creativity': 78,
        'emotional_intelligence': 85,
        'conflict_resolution': 79,
        'critical_thinking': 83,
    }

    detailed_info_2 = allocator.get_detailed_allocation(skill_scores_2)
    print_allocation_summary(detailed_info_2)

    # Test case 3: All low scores
    print("\n\n" + "="*70)
    print("TEST CASE 3: All Low Scores")
    skill_scores_3 = {
        'communication': 25,
        'teamwork': 30,
        'leadership': 20,
        'problem_solving': 35,
        'time_management': 28,
        'adaptability': 32,
        'creativity': 26,
        'emotional_intelligence': 29,
        'conflict_resolution': 18,
        'critical_thinking': 31
    }

    detailed_info_3 = allocator.get_detailed_allocation(skill_scores_3)
    print_allocation_summary(detailed_info_3)

    # Optional: Plot membership functions
    # allocator.plot_membership_functions()

if __name__ == "__main__":
    main()