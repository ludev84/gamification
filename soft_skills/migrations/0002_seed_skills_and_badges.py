from django.db import migrations


SKILLS = [
    ('comunicacion', 'Comunicación', '💬', 1),
    ('trabajo_en_equipo', 'Trabajo en equipo', '🤝', 2),
    ('liderazgo', 'Liderazgo', '👑', 3),
    ('resolucion_de_problemas', 'Resolución de problemas', '🧩', 4),
    ('gestion_del_tiempo', 'Gestión del tiempo', '⏰', 5),
    ('adaptabilidad', 'Adaptabilidad', '🔄', 6),
    ('creatividad', 'Creatividad', '💡', 7),
    ('inteligencia_emocional', 'Inteligencia emocional', '❤️', 8),
    ('resolucion_de_conflictos', 'Resolución de conflictos', '🕊️', 9),
    ('pensamiento_critico', 'Pensamiento crítico', '🧠', 10),
]

BADGES = [
    ('primeros_pasos', 'Primeros pasos', 'Completar la evaluación inicial.', '🎯', 'scores_loaded', 0, None),
    ('primera_llama', 'Primera llama', 'Racha de 3 días.', '🔥', 'streak', 3, None),
    ('fuego_constante', 'Fuego constante', 'Racha de 7 días.', '🔥', 'streak', 7, None),
    ('fuego_intenso', 'Fuego intenso', 'Racha de 14 días.', '🔥', 'streak', 14, None),
    ('mes_en_llamas', 'Mes en llamas', 'Racha de 30 días.', '🔥', 'streak', 30, None),
    ('coleccionista', 'Coleccionista de habilidades', 'Completar 5 módulos.', '🎖️', 'modules_completed', 5, None),
    ('campeon', 'Campeón en habilidades blandas', 'Completar todos los módulos.', '🏆', 'all_modules', 0, None),
    ('aprendiz_constante', 'Aprendiz constante', 'Contestar 50 preguntas.', '📚', 'questions_answered', 50, None),
]

# Skill-specific badges: "Maestro de X" for each skill with >80%
SKILL_BADGES = [
    ('maestro_comunicacion', 'Maestro de Comunicación', 'Completar el módulo de Comunicación con >80%.', '🥇', 'module_high_score', 80, 'comunicacion'),
    ('maestro_trabajo_en_equipo', 'Maestro de Trabajo en equipo', 'Completar el módulo de Trabajo en equipo con >80%.', '🥇', 'module_high_score', 80, 'trabajo_en_equipo'),
    ('maestro_liderazgo', 'Maestro de Liderazgo', 'Completar el módulo de Liderazgo con >80%.', '🥇', 'module_high_score', 80, 'liderazgo'),
    ('maestro_resolucion_de_problemas', 'Maestro de Resolución de problemas', 'Completar el módulo de Resolución de problemas con >80%.', '🥇', 'module_high_score', 80, 'resolucion_de_problemas'),
    ('maestro_gestion_del_tiempo', 'Maestro de Gestión del tiempo', 'Completar el módulo de Gestión del tiempo con >80%.', '🥇', 'module_high_score', 80, 'gestion_del_tiempo'),
    ('maestro_adaptabilidad', 'Maestro de Adaptabilidad', 'Completar el módulo de Adaptabilidad con >80%.', '🥇', 'module_high_score', 80, 'adaptabilidad'),
    ('maestro_creatividad', 'Maestro de Creatividad', 'Completar el módulo de Creatividad con >80%.', '🥇', 'module_high_score', 80, 'creatividad'),
    ('maestro_inteligencia_emocional', 'Maestro de Inteligencia emocional', 'Completar el módulo de Inteligencia emocional con >80%.', '🥇', 'module_high_score', 80, 'inteligencia_emocional'),
    ('maestro_resolucion_de_conflictos', 'Maestro de Resolución de conflictos', 'Completar el módulo de Resolución de conflictos con >80%.', '🥇', 'module_high_score', 80, 'resolucion_de_conflictos'),
    ('maestro_pensamiento_critico', 'Maestro de Pensamiento crítico', 'Completar el módulo de Pensamiento crítico con >80%.', '🥇', 'module_high_score', 80, 'pensamiento_critico'),
]


def seed_data(apps, schema_editor):
    SoftSkill = apps.get_model('soft_skills', 'SoftSkill')
    Badge = apps.get_model('soft_skills', 'Badge')

    skill_map = {}
    for slug, name, icon, order in SKILLS:
        skill, _ = SoftSkill.objects.get_or_create(
            slug=slug, defaults={'name': name, 'icon': icon, 'order': order}
        )
        skill_map[slug] = skill

    for slug, name, desc, icon, cond_type, cond_val, skill_slug in BADGES:
        Badge.objects.get_or_create(
            slug=slug,
            defaults={
                'name': name, 'description': desc, 'icon': icon,
                'condition_type': cond_type, 'condition_value': cond_val,
                'condition_skill': None,
            }
        )

    for slug, name, desc, icon, cond_type, cond_val, skill_slug in SKILL_BADGES:
        Badge.objects.get_or_create(
            slug=slug,
            defaults={
                'name': name, 'description': desc, 'icon': icon,
                'condition_type': cond_type, 'condition_value': cond_val,
                'condition_skill': skill_map.get(skill_slug),
            }
        )


def reverse_seed(apps, schema_editor):
    SoftSkill = apps.get_model('soft_skills', 'SoftSkill')
    Badge = apps.get_model('soft_skills', 'Badge')
    SoftSkill.objects.all().delete()
    Badge.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('soft_skills', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_data, reverse_seed),
    ]
