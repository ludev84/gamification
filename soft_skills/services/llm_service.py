import json
import logging

from django.conf import settings

logger = logging.getLogger(__name__)

MCQ_EXAMPLE = """
{
  "scenario": "Tu compañero de cuarto, Liam, acaba de terminar una videollamada con su familia. Usualmente es alegre, pero ahora está callado y mirando fijamente la pantalla de su computadora. Cuando le preguntas si está bien, se encoge de hombros y dice: 'Estoy bien, solo cansado'. Sin embargo, se pasa la mano por el cabello repetidamente, un hábito que has notado que tiene cuando está estresado.",
  "question_text": "Dadas sus señales verbales y no verbales, ¿cuál es la respuesta más empática?",
  "option_a": "Se nota que la llamada te dejó muy estresado. Sentir toda esa presión por las calificaciones y la pasantía debe ser bastante agobiante.",
  "option_b": "Bueno, todavía tienes tiempo para encontrar una pasantía. Podemos buscar algunas ofertas en línea esta noche si quieres. Hagamos un plan.",
  "option_c": "No deberías dejar que te afecten tanto. Es algo común en los padres y las madres; se preocupan. Solo necesitas enfocarte en lo que puedes controlar.",
  "option_d": "Tuve una llamada así con mi familia el mes pasado. Me estuvieron molestando sobre mi carrera durante casi una hora. Es súper molesto.",
  "correct_answer": "A",
  "explanation": "Esta respuesta reconoce la diferencia entre lo que Liam dice y lo que hace. Identifica sus sentimientos probables (estrés, agobio) y los conecta con lo que los causó (la presión familiar).\\n- B es incorrecta porque ofrece una solución inmediata sin primero reconocer o validar los sentimientos.\\n- C es incorrecta porque es evaluativa y desdeñosa, diciéndole cómo debería sentirse.\\n- D es incorrecta porque cambia el enfoque a tu propia experiencia."
}
"""

SYSTEM_PROMPT = """Eres un experto en habilidades blandas y desarrollo personal para estudiantes universitarios.
Tu tarea es generar preguntas de opción múltiple (MCQ) sobre habilidades blandas.

Cada MCQ debe seguir este formato exacto en JSON:
- "scenario": Situación contextualizada y detallada en segunda persona, con personajes y contexto emocional.
- "question_text": Pregunta directa sobre la acción más apropiada.
- "option_a", "option_b", "option_c", "option_d": Cuatro opciones donde una es correcta y tres son incorrectas, cada una representando un patrón de respuesta distinto.
- "correct_answer": Letra de la respuesta correcta (A, B, C o D).
- "explanation": Por qué la respuesta correcta es la mejor, seguido de por qué cada opción incorrecta falla.

IMPORTANTE:
- Los escenarios deben ser variados, realistas y relevantes para estudiantes universitarios en México.
- Cada opción incorrecta debe representar un error distinto (ej: consejo no solicitado, minimización, cambio de enfoque, evaluación crítica).
- La explicación debe ser educativa y constructiva.
- Todo el contenido debe estar en español.
- Responde ÚNICAMENTE con un array JSON válido de objetos MCQ."""


class LLMService:
    def __init__(self):
        self.provider = settings.LLM_PROVIDER
        self.api_key = settings.LLM_API_KEY
        self.model = settings.LLM_MODEL

    def generate_mcqs(self, skill_name, count):
        if not self.api_key:
            logger.warning('No LLM API key configured. Returning empty list.')
            return []

        prompt = self._build_prompt(skill_name, count)

        try:
            if self.provider == 'openai':
                raw = self._call_openai(prompt)
            elif self.provider == 'anthropic':
                raw = self._call_anthropic(prompt)
            else:
                logger.error(f'Unknown LLM provider: {self.provider}')
                return []

            return self._parse_response(raw)
        except Exception as e:
            logger.error(f'Error generating MCQs for {skill_name}: {e}')
            return []

    def _build_prompt(self, skill_name, count):
        return (
            f"Genera exactamente {count} preguntas MCQ sobre la habilidad blanda: '{skill_name}'.\n\n"
            f"Ejemplo de formato esperado:\n{MCQ_EXAMPLE}\n\n"
            f"Genera {count} MCQs variadas siguiendo exactamente ese formato JSON. "
            f"Responde con un array JSON de {count} objetos."
        )

    def _parse_response(self, raw_text):
        text = raw_text.strip()
        # Try to extract JSON array from the response
        start = text.find('[')
        end = text.rfind(']')
        if start != -1 and end != -1:
            text = text[start:end + 1]

        try:
            mcqs = json.loads(text)
            if isinstance(mcqs, list):
                valid = []
                required_keys = {'scenario', 'question_text', 'option_a', 'option_b',
                                 'option_c', 'option_d', 'correct_answer', 'explanation'}
                for mcq in mcqs:
                    if isinstance(mcq, dict) and required_keys.issubset(mcq.keys()):
                        if mcq['correct_answer'].upper() in ('A', 'B', 'C', 'D'):
                            mcq['correct_answer'] = mcq['correct_answer'].upper()
                            valid.append(mcq)
                return valid
        except json.JSONDecodeError as e:
            logger.error(f'Failed to parse LLM response as JSON: {e}')

        return []

    def _call_openai(self, prompt):
        from openai import OpenAI
        client = OpenAI(api_key=self.api_key)
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {'role': 'system', 'content': SYSTEM_PROMPT},
                {'role': 'user', 'content': prompt},
            ],
            temperature=0.8,
            response_format={'type': 'json_object'},
        )
        return response.choices[0].message.content

    def _call_anthropic(self, prompt):
        import anthropic
        client = anthropic.Anthropic(api_key=self.api_key)
        response = client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{'role': 'user', 'content': prompt}],
        )
        return response.content[0].text
