# Guía de integración: API de aprendizaje + psicometric-FRONT

Este documento describe (1) cómo corre la integración **hoy** con dos backends
separados, y (2) cómo montar `soft_skills` dentro del backend psicométrico
**mañana** sin que el frontend cambie.

## Arquitectura actual (backends separados)

```
psicometric-FRONT (Vite :5173)
 ├── /api          → backend psicométrico (Django :8000)  — cuestionarios
 └── /platform-api → esta plataforma      (Django :8001)  — /users/* + /learning/*
```

- La API vive en [soft_skills/api/](../soft_skills/api/) y replica las
  convenciones del backend psicométrico: envelope
  `{status, statusCode, message, data}`, cookie httpOnly `auth_token`
  (DRF Token dentro de la cookie — `CookieTokenAuthentication`).
- `/users/login|logout|profile/` es un **shim provisional**
  ([soft_skills/api/auth_urls.py](../soft_skills/api/auth_urls.py)) con el
  mismo contrato que el backend psicométrico. `/learning/...` es la API
  portable ([soft_skills/api/urls.py](../soft_skills/api/urls.py)).
- En el proxy de Vite, `cookiePathRewrite: "/platform-api"` aísla la cookie de
  esta plataforma para que no colisione con la del backend psicométrico en el
  mismo origen.

### Correr en local

```bash
# Plataforma (este repo)
source .venv/bin/activate
python manage.py runserver 8001

# Frontend
cd psicometric-FRONT && npm run dev   # http://localhost:5173/#/learning
```

**Restricción provisional:** el alumno debe existir en AMBAS bases con el
mismo correo (el gate de /learning pide login con las credenciales de esta
plataforma la primera vez).

### Endpoints de /learning

| Endpoint | Método | Descripción |
|---|---|---|
| `/learning/dashboard/` | GET | perfil, nivel/XP, flags de UI, selector de nivel, racha semanal, medallas, módulos, totales |
| `/learning/modules/<id>/` | GET | camino de lecciones con bloqueo secuencial y progreso |
| `/learning/lessons/<id>/` | GET | preguntas (sin respuestas correctas), progreso, siguiente pregunta |
| `/learning/lessons/<id>/answers/` | POST | `{question_id, selected_answer}` → feedback (solo revela la correcta si acertó), XP, rachas; 409 si ya estaba dominada |
| `/learning/gamification-level/` | POST | `{level: 0..3}` → guarda la elección del usuario |
| `/learning/modules/<id>/summary/` | GET | resumen de XP del módulo (requiere módulo completado) |
| `/learning/modules/<id>/review/`, `/learning/lessons/<id>/review/` | GET | retroalimentación completa (requiere completado) |
| `/learning/ocean-scores/` | POST | ingesta de puntajes OCEAN (ver abajo) |

## Ingesta de puntajes OCEAN (Big Five por convención)

El backend psicométrico (u otro caller servidor-a-servidor) envía los puntajes
del cuestionario Big Five cuyas Variables se llaman como los 5 rasgos:

```bash
curl -X POST http://localhost:8001/learning/ocean-scores/ \
  -H "Content-Type: application/json" \
  -H "X-Internal-Api-Key: $PLATFORM_INTERNAL_API_KEY" \
  -d '{
    "user": {"email": "alumno@tecnm.mx"},
    "scores": [
      {"name": "Apertura",       "value": 42, "min": 12, "max": 60},
      {"name": "Responsabilidad", "value": 30, "min": 12, "max": 60},
      {"name": "Extraversión",    "value": 48, "min": 12, "max": 60},
      {"name": "Amabilidad",      "value": 36, "min": 12, "max": 60},
      {"name": "Neuroticismo",    "value": 24, "min": 12, "max": 60}
    ]
  }'
```

- **Autenticación**: header `X-Internal-Api-Key` (setting
  `PLATFORM_INTERNAL_API_KEY`) o token de un usuario staff.
- **Usuario destino**: por `email` (case-insensitive). Sin coincidencia → 404;
  correo ambiguo → 409.
- **Mapeo de nombres** (sin acentos, case-insensitive, en
  [soft_skills/services/ocean.py](../soft_skills/services/ocean.py)):
  Apertura/Openness, Responsabilidad/Escrupulosidad/Conscientiousness,
  Extraversión, Amabilidad/Agreeableness, Neuroticismo/Neuroticism. Nombres
  desconocidos van a `warnings` sin fallar.
- **Normalización**: `(value - min) / (max - min) * 100` (0-100). Si se omiten
  `min`/`max`, el valor se asume ya en escala 0-100. Para Likert:
  `min = preguntas × puntaje_mínimo`, `max = preguntas × puntaje_máximo`.
- **Efecto**: escribe `UserProfile.ocean_*`, corre el sistema difuso
  (`apply_fuzzy_gamification_level`) y actualiza el nivel **recomendado**
  (`gamification_level_admin`). Nunca toca la elección del usuario
  (`gamification_level_user`).

## Fusión futura: montar soft_skills en el backend psicométrico

1. Dependencias: `pip install djangorestframework scikit-fuzzy scipy numpy networkx`
   (DRF probablemente ya está).
2. Copia/instala la app `soft_skills` y agrega `'soft_skills'` a
   `INSTALLED_APPS`; corre `python manage.py migrate`.
3. Monta **solo** la API portable — NO el shim de auth (los `/users/*` del
   host ganan):
   ```python
   path('learning/', include('soft_skills.api.urls')),
   ```
   Las vistas solo dependen de `request.user`, así que funcionan con la clase
   de autenticación que el host ya use.
4. Respalda perfiles para los usuarios preexistentes (la señal solo cubre
   usuarios nuevos):
   ```bash
   python manage.py backfill_profiles
   ```
5. Sustituye el hop HTTP de OCEAN por una llamada directa a
   `soft_skills.services.ocean.apply_ocean_scores(profile, scores)` en el
   hook de submit del cuestionario Big Five (o conserva el endpoint).
6. Frontend: define `VITE_PLATFORM_API_URL` con la misma base que
   `VITE_API_URL` (o elimina el proxy `/platform-api`). Nada más cambia.
7. Los templates Django de este repo son opcionales; si no se llevan, no
   registres `soft_skills.context_processors.gamification_context`.
