# Habilidades Blandas — Plataforma Gamificada

Plataforma web Django para desarrollar habilidades blandas mediante lecciones secuenciales (estilo Duolingo) de preguntas de opción múltiple, con XP, niveles dinámicos, rachas y medallas. Desarrollada para el Instituto Tecnológico de Mérida (TecNM).

Toda la interfaz y el contenido están en español de México. La especificación del proyecto está en [Docs/final_specs.md](Docs/final_specs.md).

**Cómo funciona en resumen:** no hay registro público ni gestión de contenido para los alumnos. Un **administrador** crea los módulos, lecciones y preguntas desde el panel de Django Admin (o los importa desde archivos JSON), crea las cuentas de los alumnos y les **asigna** los módulos. El alumno inicia sesión y solo ve lo que se le asignó.

---

## Índice

1. [Requisitos previos](#1-requisitos-previos)
2. [Instalación](#2-instalación)
3. [Crear el usuario administrador y entrar al panel](#3-crear-el-usuario-administrador-y-entrar-al-panel)
4. [Crear usuarios (alumnos)](#4-crear-usuarios-alumnos)
5. [Cargar contenido: módulos, lecciones y preguntas](#5-cargar-contenido-módulos-lecciones-y-preguntas)
6. [Asignar módulos a los alumnos (obligatorio)](#6-asignar-módulos-a-los-alumnos-obligatorio)
7. [Niveles de gamificación](#7-niveles-de-gamificación)
8. [Medallas](#8-medallas)
9. [Cómo se calculan el XP y los niveles](#9-cómo-se-calculan-el-xp-y-los-niveles)
10. [Flujo del alumno](#10-flujo-del-alumno)
11. [Solución de problemas](#11-solución-de-problemas)
12. [Mantenimiento y referencia](#12-mantenimiento-y-referencia)

---

## 1. Requisitos previos

| Requisito | Versión | Notas |
| --- | --- | --- |
| Python | **3.12 o superior** | Django 6.0 no funciona con versiones anteriores. Verifica con `python --version`. |
| pip + venv | incluidos con Python | En Debian/Ubuntu puede hacer falta `sudo apt install python3-venv python3-pip`. |
| Git | cualquiera | Solo para clonar el repositorio. |

No se necesita Docker, PostgreSQL, Node.js ni servidor web: la base de datos es SQLite (un archivo local) y el frontend son plantillas de Django.

**Stack:** Python 3 + Django 6.0 · SQLite · Django Templates + CSS + JavaScript vanilla (más `canvas-confetti` por CDN) · `scikit-fuzzy` para la recomendación de nivel de gamificación.

---

## 2. Instalación

### 2.1 Clonar el repositorio

```bash
git clone <url-del-repositorio> gamification
cd gamification
```

### 2.2 Crear y activar el entorno virtual

```bash
python -m venv .venv
```

```bash
source .venv/bin/activate          # Linux / macOS
.venv\Scripts\activate             # Windows (CMD)
.venv\Scripts\Activate.ps1         # Windows (PowerShell)
```

> Sabrás que está activo porque el prompt de la terminal empieza con `(.venv)`. **Hay que activarlo cada vez que abras una terminal nueva** para trabajar en el proyecto.

### 2.3 Instalar dependencias

```bash
pip install -r requirements.txt
```

Esto instala Django, Django REST Framework y `scikit-fuzzy` / `numpy` / `scipy` (usados por el sistema difuso que recomienda el nivel de gamificación a partir de los rasgos de personalidad).

### 2.4 Crear la base de datos

```bash
python manage.py migrate
```

Crea el archivo `db.sqlite3` con todas las tablas. No está en control de versiones, así que cada instalación arranca con una base vacía.

### 2.5 Arrancar el servidor

```bash
python manage.py runserver
```

Deja esa terminal abierta mientras uses la plataforma. Direcciones:

| Para | URL |
| --- | --- |
| App del alumno | <http://127.0.0.1:8000/> |
| Panel de administración | <http://127.0.0.1:8000/admin/> |
| Inicio de sesión | <http://127.0.0.1:8000/accounts/login/> |

Para detenerlo: `Ctrl + C`.

---

## 3. Crear el usuario administrador y entrar al panel

El administrador (superusuario) es quien gestiona todo el contenido. Con el servidor detenido o en otra terminal (con el entorno virtual activado):

```bash
python manage.py createsuperuser
```

Pide usuario, correo (opcional, puede dejarse vacío) y contraseña dos veces. La contraseña no se muestra al escribirla, eso es normal.

Luego entra a <http://127.0.0.1:8000/admin/> con esas credenciales. Verás dos secciones:

- **Authentication and Authorization** → `Users` (cuentas de acceso).
- **Habilidades Blandas** → todo lo demás: Módulos, Lecciones, Preguntas MCQ, Perfiles, Progreso, Medallas.

---

## 4. Crear usuarios (alumnos)

> Los alumnos **no se pueden registrar solos**: todas las cuentas las crea el administrador.

1. **Authentication and Authorization → Users → Add user** (botón "Añadir" / "Add").
2. Escribe **nombre de usuario** y **contraseña** (dos veces). Guarda.
3. Django abre la pantalla de edición del usuario. Ahí puedes agregar nombre, apellido y correo.
4. **Importante:** deja `is_staff` y `is_superuser` **desmarcados** para un alumno normal. Marcar `is_staff` le daría acceso al panel de administración.
5. Guarda de nuevo.

Al guardar el usuario se le crea automáticamente su **perfil** (`UserProfile`) con 0 XP, racha en cero y el nivel de gamificación por defecto. No hay que crearlo a mano.

**Para que el alumno vea contenido faltan dos cosas:** que exista contenido publicado (paso 5) y que se le **asigne** al menos un módulo (paso 6).

---

## 5. Cargar contenido: módulos, lecciones y preguntas

La jerarquía es siempre **Módulo → Lecciones → Preguntas MCQ**:

- Un **módulo** es una habilidad blanda (ej. "Empatía").
- Cada módulo tiene **lecciones** secuenciales: hay que completar una para desbloquear la siguiente.
- Cada lección tiene **preguntas** de opción múltiple con 4 opciones y una explicación por opción.

Hay dos formas de cargarlo. **La opción A es mucho más rápida** si ya tienes las preguntas en archivos JSON.

> ⚠️ **Regla que aplica a todo:** el contenido solo es visible para los alumnos si `is_published` está marcado en **los tres niveles** (módulo, lección y pregunta). El contenido sin publicar tampoco cuenta para el cálculo de XP máximo.

### Opción A — Importar desde archivos JSON (recomendado)

El comando `import_mcq_module` crea un módulo completo a partir de un directorio de archivos JSON: **un archivo = una lección**, y las preguntas dentro del archivo se crean en el orden del arreglo.

El repositorio incluye un módulo de ejemplo listo para importar (Empatía, 5 lecciones de 10 preguntas):

```bash
python manage.py import_mcq_module --name "Empatía" --dir Docs/mcqs-empathy --publish
```

Salida esperada:

```
Created module "Empatía" (slug=empatia, order=0).
  · Lesson 1 "Lección 1" — 10 question(s) [MCQs-1.json]
  · Lesson 2 "Lección 2" — 10 question(s) [MCQs-2.json]
  ...
Imported 5 lesson(s) and 50 question(s) into module "Empatía" (slug=empatia).
```

**Antes de importar en serio**, puedes validar todo sin escribir nada en la base con `--dry-run`:

```bash
python manage.py import_mcq_module --name "Empatía" --dir Docs/mcqs-empathy --publish --dry-run
```

Opciones del comando:

| Flag | Para qué sirve |
| --- | --- |
| `--name` *(obligatorio)* | Nombre visible del módulo, ej. `"Trabajo en equipo"`. |
| `--dir` *(obligatorio)* | Directorio con los archivos JSON (uno por lección). |
| `--publish` | Marca módulo, lecciones y preguntas como publicadas. **Sin este flag nada queda visible** para los alumnos. |
| `--dry-run` | Valida y reporta todo, pero revierte los cambios. |
| `--slug` | Identificador en la URL; si se omite se deriva del nombre (`"Empatía"` → `empatia`). |
| `--description` | Descripción del módulo. |
| `--icon` | Emoji del módulo (por defecto `📘`). |
| `--module-order` | Posición del módulo en el dashboard. Por defecto se agrega al final. |
| `--lesson-prefix` | Prefijo de los títulos de lección cuando el JSON no trae `title` (por defecto `"Lección"` → "Lección 1", "Lección 2"…). |
| `--lesson-icon` | Emoji por defecto de las lecciones (`📖`). |
| `--pattern` | Patrón de archivos a leer dentro de `--dir` (por defecto `*.json`). |

Detalles útiles:

- **Es idempotente:** volver a correrlo con el mismo `--name`/`--slug` **actualiza** el módulo, las lecciones y las preguntas existentes en lugar de duplicarlos. Sirve para corregir un lote de preguntas y recargarlo.
- El orden de las lecciones lo da el **orden alfabético de los nombres de archivo**. Nombra los archivos para que ordenen bien (`MCQs-01.json`, `MCQs-02.json`… si vas a pasar de 9).
- El archivo `MCQs-format.json` se ignora siempre (es solo la muestra del formato).
- Al reimportar **no** se pisa el orden del módulo si lo cambiaste a mano en el admin (salvo que pases `--module-order`).
- Después de importar puedes ajustar en el admin lo que el comando no define: íconos y descripciones de cada lección, orden, etc.

#### Formato de los archivos JSON

Cada archivo es un **arreglo** de preguntas:

```json
[
  {
    "type": "multiple_choice",
    "scenario": "Situación contextual de ~80–120 palabras, escrita en segunda persona.",
    "question": "¿Cuál es la respuesta más empática?",
    "options": [
      { "id": "A", "text": "Primera opción.",  "isCorrect": true,  "feedback": "Por qué esta es la correcta." },
      { "id": "B", "text": "Segunda opción.",  "isCorrect": false, "feedback": "Por qué esta falla." },
      { "id": "C", "text": "Tercera opción.",  "isCorrect": false, "feedback": "Por qué esta falla." },
      { "id": "D", "text": "Cuarta opción.",   "isCorrect": false, "feedback": "Por qué esta falla." }
    ]
  }
]
```

Reglas del formato:

- Exactamente **4 opciones**, con `id` `A`, `B`, `C` y `D`.
- Exactamente **una** con `"isCorrect": true`.
- `feedback` es la explicación que ve el alumno para la opción que eligió — conviene llenar las cuatro.
- Opcionalmente, en lugar de un arreglo simple de preguntas, el archivo puede ser un objeto que incluya metadatos de la lección:

```json
{
  "title": "Lección 3 — Escucha activa",
  "description": "Reconocer señales no verbales.",
  "icon": "💬",
  "questions": [ { "...": "..." } ]
}
```

Referencia completa: [Docs/mcqs-empathy/MCQs-format.json](Docs/mcqs-empathy/MCQs-format.json) (una pregunta de ejemplo) y [Docs/mcqs-empathy/](Docs/mcqs-empathy/) (5 lecciones reales). El código del importador es [import_mcq_module.py](soft_skills/management/commands/import_mcq_module.py).

### Opción B — Crear el contenido a mano en el admin

**Crear el módulo:**

1. **Habilidades Blandas → Módulos → Añadir módulo**.
2. Llena `name` (ej. "Empatía"), `slug` (se autocompleta), `description`, `icon` (un emoji) y `order` (0, 1, 2… define la posición en el dashboard).
3. Marca `is_published`.
4. En la misma pantalla, en la sección inline **Lecciones**, puedes ir agregando las lecciones: orden, ícono, título e `is_published`. Guarda.

**Crear las preguntas:**

1. **Habilidades Blandas → Lecciones** y entra a la lección.
2. En la sección inline **Preguntas MCQ**, agrega cada pregunta:

| Campo | Contenido |
| --- | --- |
| `scenario` | Situación contextual (~80–120 palabras, en segunda persona). |
| `question_text` | La pregunta concreta. |
| `option_a` … `option_d` | Las cuatro opciones. |
| `correct_answer` | `A`, `B`, `C` o `D`. |
| `explanation_a` … `explanation_d` | Por qué cada opción es correcta o por qué falla. |
| `order` | Posición de la pregunta dentro de la lección. |
| `is_published` | Debe estar marcado para que sea visible. |

Guarda al terminar cada pregunta.

> Atajo: en las listas de **Módulos**, **Lecciones** y **Preguntas MCQ** las columnas `order` e `is_published` son editables directamente desde la lista, sin entrar a cada registro.

---

## 6. Asignar módulos a los alumnos (obligatorio)

Un alumno **solo ve los módulos que le fueron asignados**. Crear y publicar un módulo no lo hace visible para nadie: la asignación es el paso que da acceso *y* el que registra el progreso.

Dos formas:

- **Individual:** **Habilidades Blandas → Progreso de módulos → Añadir**. Selecciona el usuario y el módulo, y guarda (deja los campos de progreso en sus valores por defecto).
- **Masiva (a todos los usuarios):** ve a la lista de **Módulos**, marca las casillas de los módulos deseados y en el menú de acciones elige **"Asignar módulos seleccionados a todos los usuarios"** → *Ir*. Te confirmará cuántas asignaciones creó (no duplica las existentes).

En esa misma pantalla de **Progreso de módulos** puedes consultar después si el alumno inició el módulo (`is_started`), si lo completó (`is_completed`), su puntaje (`score_percent`) y el XP que ganó.

---

## 7. Niveles de gamificación

Además del nivel que el alumno *sube* con XP, existe un **nivel de gamificación de 0 a 3** que controla **cuánta gamificación se muestra**. Es por usuario.

| Nivel | Nombre | Qué se muestra / cambia |
| --- | --- | --- |
| **0** | Nulo | Sin UI de gamificación: ni XP, ni nivel, ni rachas, ni medallas, ni confeti ni sonidos. El XP y las rachas **se siguen registrando** en la base de datos. |
| **1** | Bajo | Se muestran nivel y XP. Sin rachas ni medallas. Confeti y animaciones discretos. Umbrales de nivel más exigentes. |
| **2** | Medio | Todo lo anterior + racha de días, racha de respuestas y medallas. Es el valor por defecto. |
| **3** | Alto | Todo visible, confeti/sonido/animaciones al máximo, umbrales de nivel más fáciles y **multiplicador ×1.5 en todo el XP** que se otorga. |

> ⚠️ **Las medallas solo existen a partir del nivel 2.** Por debajo de eso no se muestran ni se otorgan, aunque estén asignadas.

### De dónde sale el nivel de cada usuario

Hay dos campos en el perfil y el **nivel efectivo** es:

> **el nivel que el alumno eligió** (si eligió alguno) **, si no, el nivel definido por el administrador.**

- **Nivel del administrador / recomendado** (`gamification_level_admin`): lo define el admin, y es el que se usa mientras el alumno no elija otro.
- **Nivel del usuario** (`gamification_level_user`): la elección del propio alumno desde el selector **"Nivel de gamificación"** que aparece en el encabezado de su dashboard. El nivel recomendado por el admin aparece ahí marcado como "· recomendado". Si está vacío (`None`), el nivel seleccionado es el del admin.

### Cambiar el nivel de un usuario (admin)

1. **Habilidades Blandas → Perfiles de usuario** (`UserProfile`) y entra al perfil del alumno.
2. En la sección **Gamificación** ajusta:
   - **Nivel de gamificación (admin/recomendado)** → el que tú defines.
   - **Nivel de gamificación (usuario)** → lo que el alumno eligió; **déjalo vacío** para que el alumno siga tu nivel recomendado (vaciarlo también sirve para "resetear" su elección).
3. Guarda. La columna **Nivel efectivo** en la lista de perfiles te muestra cuál está aplicando.

### Recomendación automática por personalidad (OCEAN)

El nivel recomendado se puede calcular automáticamente a partir de los cinco rasgos de personalidad Big Five / OCEAN mediante un sistema de lógica difusa:

1. En el perfil del alumno, llena la sección **Personalidad OCEAN (0-100)** con los cinco puntajes: apertura, responsabilidad, extraversión, amabilidad y neuroticismo.
2. Guarda. Al detectar puntajes OCEAN nuevos, el sistema difuso calcula el nivel recomendado, lo escribe en **Nivel de gamificación (admin/recomendado)** y te muestra un mensaje con el resultado.
3. Si en **ese mismo guardado** editas a mano el campo del nivel, **tu valor gana** y no se recalcula.

Si ninguna regla difusa se activa con esos puntajes, el admin te avisa con una advertencia y el nivel no se modifica. El sistema está en [soft_skills/services/fuzzy_gamification.py](soft_skills/services/fuzzy_gamification.py).

> El valor `GAMIFICATION_LEVEL = 2` en [django_project/settings.py](django_project/settings.py) solo es el nivel por defecto de los perfiles nuevos, no un ajuste global.

---

## 8. Medallas

Las medallas son logros que se otorgan **automáticamente** cuando el alumno cumple una condición (se revisa cada vez que responde una pregunta).

> ⚠️ **Dos condiciones indispensables para que una medalla se otorgue:**
>
> 1. La medalla debe estar **asignada** a ese usuario (paso 8.2). Crear la medalla no basta: si no está asignada, el alumno no la ve ni la puede ganar.
> 2. El **nivel de gamificación efectivo** del usuario debe ser **2 o 3**. Por debajo de eso las medallas están desactivadas por completo.

### 8.1 Crear una medalla

**Habilidades Blandas → Medallas → Añadir medalla**. Campos:

| Campo | Contenido |
| --- | --- |
| `name` | Nombre visible, ej. "Constancia de bronce". |
| `slug` | Identificador único (se autocompleta desde el nombre). |
| `description` | Texto que explica cómo se gana. |
| `icon` | Emoji, ej. 🔥 (por defecto 🏅). |
| `condition_type` | El tipo de logro (tabla de abajo). |
| `condition_value` | El umbral numérico que corresponde a ese tipo. |
| `condition_module` | **Solo** para los dos tipos de módulo específico; en los demás déjalo vacío. |

**Tipos de condición disponibles:**

| `condition_type` | Se gana cuando… | `condition_value` | `condition_module` |
| --- | --- | --- | --- |
| `streak` — Racha de días | La racha diaria actual alcanza el valor | nº de días (ej. `7`) | — |
| `questions_answered` — Preguntas contestadas | El total de respuestas (correctas o no) alcanza el valor | nº de preguntas (ej. `50`) | — |
| `questions_correct` — Preguntas correctas | El total de respuestas correctas alcanza el valor | nº de preguntas (ej. `25`) | — |
| `lessons_completed` — Lecciones completadas | Completa esa cantidad de lecciones, de cualquier módulo | nº de lecciones (ej. `10`) | — |
| `modules_completed` — Múltiples módulos completados | Completa esa cantidad de módulos | nº de módulos (ej. `3`) | — |
| `all_modules` — Todos los módulos completados | Completa **todos** los módulos que tiene asignados | se ignora | — |
| `module_complete` — Módulo completado | Completa **un módulo específico** | se ignora | **obligatorio** |
| `module_high_score` — Módulo con alto puntaje | Completa un módulo específico con un puntaje ≥ al valor | porcentaje (ej. `80`) | **obligatorio** |

**Ejemplos:**

- *"Racha de 7 días"* → `condition_type: streak`, `condition_value: 7`.
- *"Maestro de la Empatía"* → `condition_type: module_high_score`, `condition_value: 90`, `condition_module: Empatía`.
- *"Todo completado"* → `condition_type: all_modules` (el valor no importa).

### 8.2 Asignar medallas a los alumnos

La forma más cómoda es desde la ficha del usuario:

1. **Authentication and Authorization → Users** y entra al alumno.
2. Hasta abajo, en la sección inline **Medallas asignadas**, elige una o varias medallas y guarda.

También existe **Habilidades Blandas → Medallas asignadas → Añadir** para hacerlo de una en una (usuario + medalla).

Comportamiento al asignar y desasignar:

- Si al asignarla el alumno **ya cumplía** la condición, la gana de inmediato (no tiene que volver a responder nada).
- Si **quitas** la asignación, también se borra la medalla ganada.
- Las medallas **no otorgan XP**; son solo reconocimiento.

### 8.3 Ver las medallas ganadas

**Habilidades Blandas → User badges** lista qué medallas ha ganado cada alumno y cuándo. El contador de medallas del dashboard del alumno se basa en esa tabla.

---

## 9. Cómo se calculan el XP y los niveles

### XP que se otorga

| Acción | XP base |
| --- | --- |
| Responder correctamente (primer intento) | **+10** |
| Responder incorrectamente (primer intento) | **+5** |
| Iniciar un módulo (al responder su primera pregunta) | **+30** |
| Completar una lección | **+15** (una sola vez por lección) |
| Completar un módulo | **+50** |
| Bonus por completar un módulo con puntaje ≥ 80% | **+25** |

Los reintentos de una pregunta ya contestada **no** dan XP. En el nivel de gamificación 3 todas estas cantidades se multiplican por **1.5**. Las rachas no otorgan XP.

### Niveles del alumno

Los niveles **no son fijos: se calculan**. Cada alumno tiene un máximo personalizado:

```
XP_max = (nº de módulos × 80) + (nº de lecciones × 15) + (nº de preguntas × 10)
```

contando solo el contenido **publicado** de los módulos **asignados a ese alumno**. Su nivel es la banda más alta que alcanza con `XP actual / XP_max`:

| Nivel | Nombre | Umbral (nivel gam. 1 / 2 / 3) |
| --- | --- | --- |
| 1 | Explorador Interpersonal | 0% / 0% / 0% |
| 2 | Comunicador Asertivo | 25% / 15% / 10% |
| 3 | Colaborador Clave | 50% / 40% / 25% |
| 4 | Líder Empático | 75% / 65% / 45% |
| 5 | Estratega Humano | 95% / 85% / 65% |

> Consecuencia a tener en cuenta: **publicar contenido nuevo o asignar módulos cambia el `XP_max`** y por lo tanto puede mover el nivel de un alumno hacia abajo, porque ahora hay más por recorrer.

Detalle completo del sistema en [Docs/gamification.md](Docs/gamification.md) y [Docs/gamification-tiers.md](Docs/gamification-tiers.md).

---

## 10. Flujo del alumno

1. Inicia sesión en <http://127.0.0.1:8000/accounts/login/> con el usuario y contraseña que le dio el admin.
2. En el **dashboard** ve sus módulos asignados, su nivel y XP, sus rachas, sus medallas y el selector de nivel de gamificación (según su nivel de gamificación se muestra más o menos de esto).
3. Al entrar a un módulo ve la **ruta de lecciones**; las lecciones posteriores están bloqueadas hasta completar las anteriores.
4. Responde una pregunta a la vez y recibe **retroalimentación inmediata**: la explicación de la opción que eligió, el XP ganado y, si acertó, la confirmación (con confeti según su nivel). La respuesta correcta **no se revela** hasta que la acierta.
5. Una pregunta fallada se puede reintentar al final de la lección; una ya acertada queda bloqueada.
6. Al completar todas las lecciones de un módulo ve el **resumen** con su puntaje; si es ≥ 80% recibe el bonus de +25 XP.

---

## 11. Solución de problemas

| Síntoma | Causa y solución |
| --- | --- |
| `command not found: python` | En Ubuntu/Debian instala `sudo apt install python-is-python3` (o usa `python3` solo para crear el entorno virtual); en macOS usa `python3`; en Windows reinstala Python marcando "Add to PATH". Con el entorno virtual activado, `python` funciona en todos los sistemas. |
| `ModuleNotFoundError: No module named 'django'` | El entorno virtual no está activado (falta el `(.venv)` en el prompt) o no corriste `pip install -r requirements.txt`. |
| El alumno inicia sesión pero **no ve ningún módulo** | Falta asignarle el módulo (paso 6), o el módulo/lecciones/preguntas no tienen `is_published` marcado. |
| El alumno no ve XP, rachas ni medallas | Su nivel de gamificación efectivo es 0 (o 1 para rachas y medallas). Revisa el paso 7. |
| Una medalla no se otorga aunque se cumpla la condición | No está **asignada** a ese usuario, o su nivel de gamificación es menor a 2. Ver paso 8. |
| `WARNINGS: ?: (staticfiles.W004) The directory '…/static' … does not exist` | Advertencia inofensiva: el proyecto no usa un directorio `static/` en la raíz. Puedes ignorarla o crearlo vacío con `mkdir static`. |
| `That port is already in use` | Ya hay un servidor corriendo. Ciérralo con `Ctrl + C` o usa otro puerto: `python manage.py runserver 8001`. |
| Olvidaste la contraseña del admin | `python manage.py changepassword <usuario>`. |
| `no such table: …` | Falta correr `python manage.py migrate`. |

---

## 12. Mantenimiento y referencia

### Comandos útiles

```bash
python manage.py runserver              # iniciar el servidor de desarrollo
python manage.py createsuperuser        # crear un administrador
python manage.py changepassword <user>  # cambiar una contraseña
python manage.py migrate                # aplicar migraciones (crear/actualizar tablas)
python manage.py makemigrations         # generar migraciones tras cambiar los modelos
python manage.py test soft_skills       # correr la suite de pruebas (35 pruebas)
python manage.py backfill_profiles      # crear el perfil de usuarios que no lo tengan
python manage.py import_mcq_module --name "<módulo>" --dir <directorio> --publish
```

### Reiniciar la base de datos desde cero

Borra **todo** (usuarios, contenido y progreso):

```bash
rm db.sqlite3                      # Windows: del db.sqlite3
python manage.py migrate
python manage.py createsuperuser
```

### Estructura del repositorio

```
gamification/
├── manage.py
├── requirements.txt
├── db.sqlite3                     # base de datos local (no versionada)
├── django_project/                # configuración del proyecto (settings, urls)
├── soft_skills/                   # app principal
│   ├── models.py                  # módulos, lecciones, preguntas, perfiles, medallas
│   ├── admin.py                   # panel de administración
│   ├── views.py                   # vistas del alumno
│   ├── services/                  # lógica de XP, niveles, rachas, medallas y sistema difuso
│   ├── management/commands/       # import_mcq_module, backfill_profiles
│   ├── templates/soft_skills/     # plantillas de la app
│   └── static/soft_skills/css/    # estilos
├── templates/                     # plantilla base y página de login
└── Docs/                          # especificaciones y MCQs de referencia
```

### Documentación adicional

- [Docs/final_specs.md](Docs/final_specs.md) — especificación del sistema tal como está construido.
- [Docs/gamification.md](Docs/gamification.md) — detalle de XP, niveles, rachas y medallas.
- [Docs/gamification-tiers.md](Docs/gamification-tiers.md) — los cuatro presets de umbrales de nivel.
- [CLAUDE.md](CLAUDE.md) — notas de arquitectura para quien vaya a modificar el código.

> Este proyecto también expone una API REST para consumirse desde un frontend externo; no hace falta para correrlo en local como se describe aquí. Si la necesitas, está documentada en [Docs/api-integration-guide.md](Docs/api-integration-guide.md).
