# Especificación Final — Plataforma Gamificada de Habilidades Blandas

Plataforma Web de Alumnos — Instituto Tecnológico de Mérida / TecNM

> Documento *as-built*: refleja el estado actual del sistema implementado y reemplaza a
> [new_specs.md](new_specs.md). El detalle profundo del sistema de gamificación (XP, niveles,
> rachas, medallas, niveles de gamificación 0–3) vive en [gamification.md](gamification.md) y
> [gamification-tiers.md](gamification-tiers.md); aquí solo se resume.

## 1. Introducción

### 1.1 Propósito

Plataforma gamificada para el desarrollo de habilidades blandas. Ofrece módulos con lecciones
secuenciales de preguntas de opción múltiple (MCQs), gestionados por un administrador desde el
panel de Django Admin. Toda la interfaz y el contenido están en español de México (`es-mx`,
zona horaria `America/Merida`).

### 1.2 Alcance

- Módulos de habilidades blandas creados y gestionados por el administrador.
- Cada módulo contiene lecciones secuenciales con MCQs.
- Sistema de gamificación: XP, niveles dinámicos, dos tipos de racha y medallas.
- Asignación de módulos **y** de medallas a usuarios por parte del administrador.
- Un **nivel de gamificación global (0–3)** que controla cuánta gamificación se muestra.

## 2. Descripción General

### 2.1 Funcionalidad

- El administrador crea módulos, lecciones y MCQs desde Django Admin.
- El administrador **asigna módulos** a usuarios específicos. Solo los módulos asignados aparecen en
  el dashboard del alumno.
- Las lecciones de un módulo son secuenciales (estilo Duolingo): hay que completar una para
  desbloquear la siguiente.
- Al contestar cada pregunta hay retroalimentación inmediata, con una explicación específica por
  cada opción de respuesta. Una respuesta incorrecta puede reintentarse al final de la lección;
  una pregunta ya acertada queda bloqueada.
- El sistema registra respuestas, calcula XP, actualiza rachas y progreso, y otorga medallas.

### 2.2 Supuestos y dependencias

- **Django** (6.x) sobre **SQLite**.
- Frontend con **Django Templates + CSS** y **Vanilla JavaScript** (patrón SPA por AJAX, sin
  frameworks JS).
- Autenticación con el sistema de auth de Django.
- **Sin integración con LLM ni lógica difusa.** Todo el contenido se gestiona manualmente desde
  Django Admin. (En `requirements.txt` permanecen `scikit-fuzzy`, `scipy`, `numpy` y `networkx`
  como dependencias vestigiales de un enfoque abandonado; ningún código de la app las usa.)

## 3. Arquitectura y Modelo de Datos

Un solo proyecto Django (`django_project/`) con una sola app de dominio (`soft_skills/`).

### 3.1 Modelos principales ([soft_skills/models.py](../soft_skills/models.py))

- **Contenido:** `Module` → `Lesson` → `MCQuestion` (cada uno con `order` e `is_published`).
- **Perfil y progreso:** `UserProfile` (XP, nivel, rachas), `UserModuleProgress` (asignación +
  progreso por módulo), `UserLessonProgress` (progreso por lección), `UserResponse` (respuesta por
  pregunta), `DailyActivity` (actividad diaria).
- **Medallas:** `Badge` (definición), `BadgeAssignment` (medalla disponible para un usuario),
  `UserBadge` (medalla ganada).

`UserProfile` se crea automáticamente mediante una señal `post_save` sobre `User`
([soft_skills/signals.py](../soft_skills/signals.py)), por lo que todo usuario autenticado tiene uno.

## 4. Gestión de Contenido (Admin)

### 4.1 Jerarquía de contenido

```
Módulo → Lecciones → Preguntas MCQ
```

### 4.2 Módulos

- Campos: nombre, slug, descripción, icono, orden y `is_published`.
- Solo los módulos publicados son visibles para los alumnos.

### 4.3 Lecciones

- Pertenecen a un módulo; tienen título, descripción, orden y `is_published`.
- El orden define la secuencia: hay que completar la lección anterior para desbloquear la siguiente.
- El XP de lección se otorga **una sola vez**; revisar una lección completada solo muestra la
  retroalimentación, sin XP adicional.

### 4.4 Preguntas MCQ

- Pertenecen a una lección. Estructura:
    - **Escenario:** texto contextualizado (~80–120 palabras).
    - **Pregunta:** texto corto.
    - **4 opciones (A, B, C, D):** una correcta y tres incorrectas.
    - **Respuesta correcta:** indicada por letra.
    - **4 explicaciones (A, B, C, D):** una por opción, indicando por qué acierta o falla.
- Cada pregunta tiene orden dentro de la lección y `is_published`.

### 4.5 Asignación de Módulos a Usuarios

- Los módulos son contenido global, pero solo son visibles si el administrador los asigna.
- La asignación se hace desde Django Admin de dos formas:
    1. **Individual:** crear un registro `UserModuleProgress` (usuario + módulo).
    2. **Masiva:** acción "Asignar módulos seleccionados a todos los usuarios" desde la lista de
       módulos.
- El mismo registro de asignación rastrea el progreso (iniciado, completado, puntaje, XP).

### 4.6 Medallas

- Se gestionan desde Django Admin. Cada medalla tiene: nombre, slug, descripción, icono, tipo de
  condición, valor de condición y, opcionalmente, un módulo asociado.
- **Asignación por usuario (cambio respecto a la versión anterior):** una medalla solo puede verse
  y ganarse si el administrador la ha **asignado** al usuario (`BadgeAssignment`), mediante el
  inline en la página del usuario o el admin de `BadgeAssignment`. Asignar una medalla cuya
  condición ya se cumple la otorga de inmediato; quitar la asignación retira la medalla ganada.
- El sistema evalúa automáticamente las condiciones de las medallas **asignadas** y las otorga al
  cumplirse. Las medallas se desactivan por completo cuando el nivel de gamificación es menor a 2.
- Tipos de condición disponibles: `module_complete`, `module_high_score`, `streak`,
  `questions_answered`, `questions_correct`, `lessons_completed`, `modules_completed`,
  `all_modules`.

> Detalle completo del esquema y la evaluación de medallas: [gamification.md §5](gamification.md).

## 5. Requisitos Funcionales (RF)

### 5.1 Responder Preguntas de Opción Múltiple

- El usuario navega pregunta por pregunta dentro de una lección con barra de progreso, selección de
  respuesta (grid 2×2) y botón "Enviar respuesta".
- La retroalimentación se muestra en un modal con la explicación de la opción seleccionada y, si la
  respuesta es correcta, la de la respuesta correcta; resalta los XP obtenidos.
- **Flujo tipo SPA:** los envíos y la navegación se interceptan por JavaScript y se reemplaza el
  contenido vía AJAX (parcial `_question_content.html`), con respaldo clásico no-AJAX por sesión.
- **Reintentos / dominio:** una respuesta incorrecta puede reintentarse al final de la lección; una
  pregunta ya acertada queda bloqueada. El primer intento fija `is_correct` y el XP de la respuesta.

### 5.2 Navegación del Módulo (Estilo Duolingo)

- Al entrar a un módulo se muestra la lista de lecciones como ruta secuencial.
- Lecciones completadas con check, desbloqueadas con su número, bloqueadas con candado.
- Solo se inicia una lección si todas las anteriores están completas.

### 5.3 Gamificación (resumen)

> Referencia completa (multiplicadores, niveles de gamificación 0–3, rachas, medallas):
> [gamification.md](gamification.md) y [gamification-tiers.md](gamification-tiers.md).

#### 5.3.1 Niveles dinámicos

Los niveles se calculan como porcentaje del XP máximo posible (`XP_max`) de los módulos asignados,
de modo que se adaptan al contenido publicado/asignado. Umbrales (preset medio, nivel de
gamificación 2):

| Nivel | Nombre | Umbral (% de XP_max) |
| --- | --- | --- |
| 1 | Explorador Interpersonal | 0% |
| 2 | Comunicador Asertivo | 15% |
| 3 | Colaborador Clave | 40% |
| 4 | Líder Empático | 65% |
| 5 | Estratega Humano | 85% |

Los umbrales dependen del **nivel de gamificación global (0–3)** definido en
`GAMIFICATION_LEVEL` ([settings.py](../django_project/settings.py)); ver
[gamification-tiers.md](gamification-tiers.md).

#### 5.3.2 XP por acción (valores base)

| Acción | XP base |
| --- | --- |
| Respuesta correcta (primer intento) | +10 |
| Respuesta incorrecta (primer intento) | +5 |
| Módulo iniciado (al primer responder) | +30 |
| Lección finalizada | +15 |
| Módulo finalizado | +50 |
| Alto puntaje en módulo (≥80%) | +25 |

> El XP de "módulo iniciado" se otorga al **enviar la primera respuesta** del módulo, no al abrir
> la página del módulo. En el nivel de gamificación 3 todo el XP se multiplica por **×1.5**.

#### 5.3.3 Cálculo de XP_max

$XP\_max = (M \times 80) + (L \times 15) + (P \times 10)$ — con M módulos, L lecciones y P preguntas
**publicadas y asignadas** al usuario. El bonus de +25 por alto puntaje no se incluye, por lo que un
alumno con buen desempeño puede superar el 100% del `XP_max`.

#### 5.3.4 Rachas

- **Racha diaria:** días consecutivos en que se completa al menos una lección. Se reinicia si pasan
  más de 24 h sin completar una lección.
- **Racha de respuestas:** respuestas correctas consecutivas a primer intento, mostrada en la barra
  de navegación.
- **Las rachas ya no otorgan XP** (a diferencia de la versión anterior); solo se registran y se usan
  para medallas de tipo `streak` y para la UI.

### 5.4 Dashboard del Usuario

- **Barra de gamificación** (racha, nivel/XP, medallas): visible según el nivel de gamificación
  (oculta por completo en el nivel 0).
- Mensaje de bienvenida personalizado.
- **Grid de módulos asignados:** cards con icono, nombre, estado (Nuevo/En progreso/Completado),
  **barra de progreso de lecciones completadas** (visible en todos los niveles de gamificación) y
  botón Iniciar/Continuar/Ver lecciones/Resumen.
- Sección "Tu progreso": módulos y lecciones completadas, barra de progreso general.

### 5.5 Retroalimentación

- Tras cada respuesta: modal con explicación de la opción seleccionada, respuesta correcta si
  aplica, y XP ganados.
- **Resumen de módulo** (`/modulo/<id>/resumen/`) con desglose de XP (los montos por unidad reflejan
  el multiplicador del nivel de gamificación).
- **Revisión de retroalimentación** de lecciones (`/leccion/<id>/retroalimentacion/`) y de módulos
  completados agrupada por lección (`/modulo/<id>/retroalimentacion/`).

## 6. Requisitos No Funcionales (RNF)

### 6.1 Seguridad

- HTTPS en producción.
- Solo usuarios autenticados acceden a la plataforma.
- Cada vista de acceso valida la asignación con
  `get_object_or_404(UserModuleProgress, user=request.user, module=…)`; los alumnos solo ven y
  acceden a módulos asignados.

### 6.2 Usabilidad

- Interfaz responsiva (Django Templates + CSS).
- Navegación simple: Dashboard, Cerrar Sesión.
- Tipografía: **DM Sans** (con Fraunces disponible para títulos).

### 6.3 Mantenibilidad

- Arquitectura modular: una sola app Django (`soft_skills`); la lógica de gamificación se centraliza
  en `GamificationService` ([soft_skills/services/gamification.py](../soft_skills/services/gamification.py)).
- Contenido, asignaciones y medallas se gestionan desde Django Admin sin tocar código.
- El nivel de gamificación se ajusta con una sola variable (`GAMIFICATION_LEVEL`); se lee al
  importar, por lo que requiere reiniciar el servidor.

## 7. Requisitos del Sistema

### 7.1 Stack tecnológico

- **Backend:** Django 6.x
- **Base de datos:** SQLite (`db.sqlite3`, fuera de control de versiones)
- **Frontend:** Django Templates + CSS + Vanilla JavaScript (sin React/Vue)

### 7.2 Entorno de desarrollo

- Prototipo local: `python manage.py runserver`
- No se requiere Docker, Nginx ni Gunicorn para el prototipo.
- No hay suite de pruebas ni CI configurados.

## 8. Rutas (URL)

Todas con segmentos en español ([soft_skills/urls.py](../soft_skills/urls.py)):

| Ruta | Vista | Propósito |
| --- | --- | --- |
| `/` | `dashboard` | Panel del alumno |
| `/modulo/<id>/` | `module_view` | Ruta de lecciones del módulo |
| `/leccion/<id>/` | `lesson_view` | Entrada a la lección (redirige a la primera pregunta pendiente) |
| `/leccion/<id>/pregunta/<n>/` | `question_view` | Pregunta n (página completa o parcial AJAX) |
| `/leccion/<id>/responder/` | `submit_answer` | Procesa la respuesta |
| `/leccion/<id>/retroalimentacion/` | `lesson_review` | Revisión de la lección |
| `/modulo/<id>/resumen/` | `module_summary` | Resumen de XP del módulo |
| `/modulo/<id>/retroalimentacion/` | `module_review` | Revisión del módulo por lección |
