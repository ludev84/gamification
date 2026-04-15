# Módulo Gamificado para el Desarrollo de Habilidades Blandas

Plataforma Web de Alumnos y Tutores – Instituto Tecnológico de Mérida/TecNM

## 1. Introducción

### 1.1 Propósito del Documento

Este documento describe los requisitos técnicos para una plataforma gamificada de desarrollo de habilidades blandas. La plataforma ofrece módulos con lecciones de preguntas de opción múltiple (MCQs), gestionados por un administrador a través del panel de Django Admin.

### 1.2 Alcance del Proyecto

La plataforma proporcionará:

- Módulos de desarrollo de habilidades blandas, creados y gestionados por el administrador.
- Cada módulo contiene lecciones secuenciales con MCQs.
- Sistema de gamificación (XP, niveles dinámicos, rachas, medallas).
- Asignación de módulos a usuarios por parte del administrador.

## 2. Descripción General

### 2.1 Funcionalidad de la plataforma

- El administrador crea módulos, lecciones y MCQs desde el panel de Django Admin.
- El administrador asigna módulos a usuarios específicos. Solo los módulos asignados aparecen en el dashboard del alumno.
- Cada módulo contiene lecciones secuenciales (estilo Duolingo). Es necesario completar una lección para desbloquear la siguiente.
- Hay una retroalimentación inmediata al contestar cada pregunta, con una explicación específica por cada opción de respuesta.
- El sistema registra respuestas, calcula XP, y actualiza el progreso.

### 2.2 Supuestos y dependencias

- Usar Django.
- Usar SQLite como base de datos.
- El frontend se construye con Django Templates.
- El sistema autenticará usuarios mediante el sistema de auth de Django.
- No se utiliza integración con LLM ni sistema de lógica difusa. Todo el contenido es gestionado manualmente por el administrador.

## 3. Gestión de Contenido (Admin)

### 3.1 Jerarquía de contenido

El contenido se organiza en tres niveles, todos gestionados desde Django Admin:

```
Módulo → Lecciones → Preguntas MCQ
```

### 3.2 Módulos

- El administrador crea módulos con: nombre, slug, descripción, icono, orden y estado de publicación (`is_published`).
- Solo los módulos publicados son visibles para los alumnos.

### 3.3 Lecciones

- Cada lección pertenece a un módulo.
- Las lecciones tienen: título, descripción, orden dentro del módulo y estado de publicación.
- El orden determina la secuencia: el alumno debe completar la lección anterior para desbloquear la siguiente.
- Las lecciones solo otorgan XP una única vez. Si el alumno revisa una lección completada, solo puede ver la retroalimentación sin obtener XP adicional.

### 3.4 Preguntas MCQ

- Cada pregunta pertenece a una lección.
- Estructura de cada MCQ:
    - **Escenario:** texto contextualizado (~80-120 palabras).
    - **Pregunta:** texto corto.
    - **4 opciones (A, B, C, D):** una correcta y tres incorrectas.
    - **Respuesta correcta:** indicada por letra.
    - **4 explicaciones (A, B, C, D):** una explicación individual por cada opción, indicando por qué es correcta o por qué falla.
- Cada pregunta tiene un orden dentro de la lección y un estado de publicación.

### 3.5 Asignación de Módulos a Usuarios

- Los módulos son contenido global, pero solo son visibles para un alumno si el administrador se los ha asignado.
- La asignación se realiza desde Django Admin de dos formas:
    1. **Individual:** Crear un registro de "Progreso de módulo" (UserModuleProgress) seleccionando un usuario y un módulo.
    2. **Masiva:** Desde la lista de módulos, seleccionar los módulos deseados y ejecutar la acción "Asignar módulos seleccionados a todos los usuarios".
- El mismo registro de asignación sirve para rastrear el progreso del alumno (si ha iniciado, completado, su puntaje, XP ganados).

### 3.6 Medallas

- Las medallas también se gestionan desde Django Admin.
- Cada medalla tiene: nombre, slug, descripción, icono, tipo de condición, valor de condición y opcionalmente un módulo asociado.
- Tipos de condición disponibles:
    - `module_complete`: Completar un módulo específico.
    - `module_high_score`: Completar un módulo específico con puntaje mayor o igual al valor de condición.
    - `streak`: Alcanzar una racha de X días consecutivos.
    - `questions_answered`: Contestar X preguntas en total.
    - `questions_correct`: Contestar X preguntas correctamente.
    - `lessons_completed`: Completar X lecciones.
    - `modules_completed`: Completar X módulos.
    - `all_modules`: Completar todos los módulos asignados.
- El sistema evalúa automáticamente las condiciones y otorga medallas cuando se cumplen.

## 4. Requisitos Funcionales (RF)

### 4.1 Responder Preguntas de Opción Múltiple

- El usuario navega pregunta por pregunta dentro de una lección con:
    - Barra de progreso.
    - Selección de respuesta (grid 2x2).
    - Botón "Enviar respuesta".
    - Mostrar mensaje de retroalimentación con la explicación específica de la opción seleccionada y, si es incorrecta, la explicación de la respuesta correcta. Resaltar los XP obtenidos.
    - Navegación: "Siguiente pregunta" / "Volver al módulo" (en la última).

### 4.2 Navegación del Módulo (Estilo Duolingo)

- Al entrar a un módulo, se muestra la lista de lecciones en formato de ruta secuencial.
- Las lecciones completadas muestran un check. Las desbloqueadas muestran su número. Las bloqueadas muestran un candado.
- Solo se puede iniciar una lección si todas las anteriores están completadas.

### 4.3 Gamificación

#### 4.3.1 Sistema Dinámico de Niveles

Los niveles se calculan dinámicamente como un porcentaje del XP Máximo Posible (XP_max) de los módulos asignados al usuario. Esto permite que el sistema se adapte automáticamente si se agrega o modifica el contenido.

| Nivel | Nombre | Umbral Requerido (% del XP_max) |
| --- | --- | --- |
| 1 | Explorador Interpersonal | 0% |
| 2 | Comunicador Asertivo | 15% |
| 3 | Colaborador Clave | 40% |
| 4 | Líder Empático | 65% |
| 5 | Estratega Humano | 85% |

#### 4.3.2 Puntos de Experiencia (XP) por Acción

| Acción | XP |
| --- | --- |
| Respuesta correcta | +10 XP |
| Respuesta incorrecta | +5 XP |
| Módulo iniciado | +30 XP |
| Lección finalizada | +15 XP |
| Módulo finalizado | +50 XP |
| Alto puntaje en módulo (≥80% de respuestas correctas) | +25 XP |

#### 4.3.3 Cálculo de XP_max (Lógica de Backend)

El XP_max se calcula a partir de los módulos asignados al usuario, considerando solo el contenido publicado:

$XP\_max = (M \times 80) + (L \times 15) + (P \times 10)$

Donde:

- M: Número de módulos asignados y publicados (aporta 80 XP base: 30 por iniciar + 50 por finalizar).
- L: Número de lecciones publicadas dentro de esos módulos.
- P: Número de preguntas MCQ publicadas (asumiendo el escenario de respuestas correctas).

*Nota:* Los puntos por alto puntaje (+25 XP) se consideran excedente, permitiendo que alumnos con buen desempeño superen el 100% del XP_max.

#### 4.3.4 Sistema de Retención (Rachas Diarias)

- El sistema registra la completación de lecciones como actividad diaria.
- La interfaz muestra un contador visual de "Días en racha".
- Se otorgan +5 XP por día de racha, y +15 XP cada 7 días consecutivos.
- Si el usuario no completa al menos una lección en un lapso de 24 horas, la racha vuelve a cero.
- Se otorgan medallas al alcanzar hitos de racha (configurables por el administrador).

### 4.4 Dashboard del Usuario

Página principal:

- Barra superior de gamificación: racha, nivel/XP, medallas.
- Mensaje de bienvenida personalizado.
- Grid de módulos asignados (cards con: icono, nombre del módulo, estado, botón Iniciar/Continuar/Retroalimentación).
- Sección "Tu progreso": módulos y lecciones completadas, barra de progreso general.

Módulo:

- Listado de lecciones en formato de ruta secuencial con indicadores de bloqueo/desbloqueo/completado.

### 4.5 Retroalimentación

- Después de cada respuesta: explicación de la opción seleccionada, respuesta correcta si aplica, XP ganados.
- Pantalla de resumen al finalizar un módulo con: desglose de XP (respuestas correctas/incorrectas, lecciones completadas, módulo iniciado/finalizado, bonus).
- El usuario puede revisar retroalimentación de módulos completados, agrupada por lección.

## 5. Requisitos No Funcionales (RNF)

### 5.1 Seguridad

- HTTPS en producción.
- Control de acceso: solo usuarios autenticados acceden a la plataforma.
- Los alumnos solo pueden ver y acceder a módulos que les han sido asignados.

### 5.2 Usabilidad

- Interfaz responsiva (Django Templates + CSS).
- Navegación simple: Inicio, Dashboard, Cerrar Sesión.
- Tipografía: Open Sans.

### 5.3 Mantenibilidad

- Arquitectura modular: el módulo de gamificación es una app Django separada (`soft_skills`).
- Todo el contenido y configuración de medallas se gestiona desde Django Admin sin necesidad de modificar código.

## 6. Requisitos del Sistema

### 6.1 Stack Tecnológico

- **Backend:** Django 4.x+
- **Base de Datos:** SQLite
- **Frontend:** Django Templates + CSS. Se permite el uso de Vanilla JavaScript para interacciones (sin frameworks de JS como React o Vue).

### 6.2 Entorno de Desarrollo

- Prototipo local: `python manage.py runserver`
- No se requiere Docker, Nginx, ni Gunicorn para el prototipo.
