# Habilidades Blandas — Plataforma Gamificada

Plataforma web Django para desarrollar habilidades blandas mediante lecciones secuenciales (estilo Duolingo) de preguntas de opción múltiple, con XP, niveles dinámicos, rachas y medallas. Desarrollada para el Instituto Tecnológico de Mérida (TecNM).

La interfaz y los datos de contenido están en español. La especificación vigente del proyecto se encuentra en [Docs/new_specs.md](Docs/new_specs.md).

## Stack

- Python 3 + Django 6.0
- SQLite (archivo local `db.sqlite3`)
- Django Templates + CSS + Vanilla JS (sin frameworks de frontend)

## Configuración del entorno de desarrollo

### 1. Clonar e ingresar al directorio

```bash
git clone <url-del-repositorio> gamification
cd gamification
```

### 2. Crear y activar un entorno virtual

```bash
python -m venv .venv
source .venv/bin/activate          # Linux / macOS
# .venv\Scripts\activate           # Windows (PowerShell: .venv\Scripts\Activate.ps1)
```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

> Nota: `scikit-fuzzy`, `scipy`, `numpy` y `networkx` aparecen en `requirements.txt` por motivos históricos (una iteración previa del proyecto). El código actual no los usa, pero se instalan junto con Django.

### 4. Aplicar migraciones

Esto crea el archivo `db.sqlite3` con todas las tablas:

```bash
python manage.py migrate
```

### 5. Crear un superusuario (administrador)

El superusuario es quien gestiona el contenido y asigna módulos a los alumnos desde Django Admin.

```bash
python manage.py createsuperuser
```

Sigue las indicaciones (usuario, correo, contraseña).

### 6. Iniciar el servidor de desarrollo

```bash
python manage.py runserver
```

- App de alumnos: <http://127.0.0.1:8000/>
- Panel de administración: <http://127.0.0.1:8000/admin/>
- Login: <http://127.0.0.1:8000/accounts/login/>

## Cargar contenido inicial (vía Django Admin)

Todo el contenido se administra desde `/admin/`. Inicia sesión ahí con el superusuario.

### Crear un usuario alumno

1. Ve a **Authentication and Authorization → Users → Add user**.
2. Ingresa nombre de usuario y contraseña; guarda.
3. En la pantalla de edición que aparece, deja `is_staff` y `is_superuser` desmarcados (es un alumno regular). Opcionalmente agrega nombre/correo y guarda de nuevo.

> Al crearse el usuario, una señal `post_save` ([soft_skills/signals.py](soft_skills/signals.py)) crea automáticamente su `UserProfile` con XP en cero.

### Crear un módulo

1. **Habilidades Blandas → Módulos → Añadir módulo**.
2. Llena: `name` (ej. "Empatía"), `slug` (se autocompleta), `description`, `icon` (un emoji, ej. 🧠), `order` (0, 1, 2…), y marca `is_published`.
3. Desde la misma pantalla puedes agregar lecciones inline (sección **Lecciones**) — basta con título, ícono, orden y `is_published`.

### Crear lecciones y preguntas

1. **Habilidades Blandas → Lecciones**. Edita la lección que creaste (o crea una nueva apuntando a su módulo).
2. Dentro de la lección, en la sección inline **Preguntas MCQ**, agrega cada pregunta con:
   - `scenario`: situación contextual (~80–120 palabras, segunda persona).
   - `question_text`: la pregunta concreta.
   - `option_a` … `option_d`: las cuatro opciones.
   - `correct_answer`: A, B, C o D.
   - `explanation_a` … `explanation_d`: por qué cada opción es correcta o por qué falla.
   - `order`, `is_published`.
3. Marca `is_published` en módulo, lección y pregunta — el contenido no publicado **no es visible** para los alumnos ni cuenta para el cálculo de XP máximo.

> Hay preguntas de ejemplo (módulo de Empatía, 5 lecciones) en [Docs/mcqs-empathy/](Docs/mcqs-empathy/). Los archivos `MCQs-1.json` … `MCQs-5.json` siguen el formato de [MCQs-format.json](Docs/mcqs-empathy/MCQs-format.json) y pueden usarse como referencia para copiar/pegar campos al admin. (No existe un comando de carga masiva por el momento.)

### Asignar módulos a los alumnos

Un alumno **solo ve los módulos que le han sido asignados**. La asignación se hace desde admin de dos formas:

- **Individual:** **Habilidades Blandas → Progreso de módulos → Añadir** y selecciona usuario + módulo.
- **Masiva:** Ve a la lista de **Módulos**, selecciona uno o más con las casillas, y en el menú de acciones elige **"Asignar módulos seleccionados a todos los usuarios"**.

### (Opcional) Crear medallas

**Habilidades Blandas → Medallas → Añadir medalla**. Cada medalla define:

- `condition_type`: `streak`, `questions_answered`, `questions_correct`, `lessons_completed`, `modules_completed`, `all_modules`, `module_complete`, `module_high_score`.
- `condition_value`: umbral numérico (días de racha, # de respuestas, % mínimo, etc.).
- `condition_module`: solo para `module_complete` / `module_high_score`.

Las medallas se otorgan automáticamente cuando un alumno cumple la condición al responder una pregunta.

## Flujo del alumno

1. Inicia sesión en `/accounts/login/`.
2. El dashboard muestra los módulos asignados, racha, nivel y medallas.
3. Al entrar a un módulo, ve la ruta de lecciones (las posteriores aparecen bloqueadas hasta completar las anteriores).
4. Cada pregunta da retroalimentación inmediata con explicación específica de la opción elegida (y de la correcta si falló) más el XP ganado.
5. Al terminar todas las lecciones de un módulo, se calcula su puntaje y, si es ≥ 80%, recibe un bonus de +25 XP.

## Reiniciar la base de datos

```bash
rm db.sqlite3
python manage.py migrate
python manage.py createsuperuser
```

## Estructura del repositorio

```
gamification/
├── manage.py
├── requirements.txt
├── django_project/        # configuración del proyecto Django (settings, urls, wsgi)
├── soft_skills/           # app principal (modelos, vistas, admin, servicio de gamificación)
│   ├── services/gamification.py   # toda la lógica de XP, niveles, rachas, medallas
│   ├── templates/soft_skills/     # plantillas de la app
│   └── static/soft_skills/css/    # estilos
├── templates/             # plantilla base y login
└── Docs/                  # especificaciones y MCQs de referencia
```

Para detalles arquitectónicos adicionales (patrón AJAX/SPA del flujo de preguntas, niveles dinámicos calculados sobre XP_max, etc.), ver [CLAUDE.md](CLAUDE.md).
