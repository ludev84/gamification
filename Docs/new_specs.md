# Módulo Gamificado para el Desarrollo de Habilidades Blandas

Plataforma Web de Alumnos y Tutores – Instituto Tecnológico de Mérida/TecNM

## 1. Introducción

### 1.1 Propósito del Documento

Este documento describe los requisitos técnicos para una plataforma gamificada de desarrollo de habilidades blandas. La plataforma ofrece módulos de habilidades blandas con preguntas de opción múltiple (MCQs) generadas por LLM.

### 1.2 Alcance del Proyecto

La plataforma proporcionará:

- Módulos de desarrollo de habilidades blandas por medio de lecciones con MCQs.
- Sistema de gamificación (XP, niveles, rachas, medallas, animaciones y sonidos).

## 2. Descripción General

### 2.1 Funcionalidad de la plataforma

- Módulos de aprendizaje de habilidades blandas.
- Cada módulo contiene MCQs divididas en lecciones. Es necesario completar una lección para iniciar la siguiente.
- Hay una retroalimentación inmediata al contestar cada pregunta, donde se muestra un mensaje diferente para cada opción de respuesta.
- El sistema registra respuestas, calcula XP, y actualiza el progreso.

### 2.2 Supuestos y dependencias

- Usar Django.
- Usar SQLite como base de datos.
- El frontend se construye con Django Templates.
- El sistema autenticará usuarios mediante el sistema de auth de Django.

## 3. Requisitos Funcionales (RF)

### 3.1 Módulos de habilidades blandas

- Un módulo por cada habilidad blanda que tenga MCQs asignados.
- Cada módulo contiene N lecciones con M cantidad de MCQs.

### 3.2 Lecciones

- Las lecciones se organizan en forma de path o árbol de habilidades, similar a la plataforma de Duolingo.
- Completar una lección desbloquea el acceso a la siguiente.
- Al finalizar todas las lecciones, se muestra un trofeo o una insignia de finalización.

### 3.3 Estructura de Preguntas de Opción Múltiple

- Escenario: texto de aprox. 80-120 palabras.
- Pregunta: texto corto.
- 4 opciones (A, B, C, D): Una correcta y tres incorrectas.
- Respuesta correcta: Indicada por letra.
- 4 Explicaciones (A, B, C, D): Por qué la respuesta correcta es la mejor y por qué cada opción incorrecta falla.

### 3.4 Responder Preguntas de Opción Múltiple

- El usuario navega pregunta por pregunta con:
  - Barra de progreso.
  - Selección de respuesta (grid 2x2).
  - Botón "Enviar respuesta".
  - Mostrar mensaje de retroalimentación. Resaltar de manera momentánea los XP obtenidos (efecto aparecer/resaltar en la pantalla). Incluir animación de confeti con efecto de sonido para respuestas correctas, y una sutil para incorrectas.
  - Navegación: "Siguiente pregunta" / "Finalizar" (en la última).

### 3.5 Gamificación

#### 3.5.1 Sistema Dinámico de Niveles

Los niveles se calculan dinámicamente como un porcentaje del XP Máximo Posible (XP_max) en la plataforma. Esto permite que el sistema se adapte automáticamente si se agrega o modifica el contenido de los módulos.

| Nivel | Nombre | Umbral Requerido (% del XP_max) |
| --- | --- | --- |
| 1 | Explorador Interpersonal | 0% |
| 2 | Comunicador Asertivo | 15% |
| 3 | Colaborador Clave | 40% |
| 4 | Líder Empático | 65% |
| 5 | Estratega Humano | 85% |

#### 3.5.2 Puntos de Experiencia (XP) por Acción

Las recompensas otorgadas por las interacciones del estudiante son fijas. El sistema registrará las siguientes acciones:

| Acción | XP |
| --- | --- |
| Respuesta correcta | +10 XP |
| Respuesta incorrecta | +5 XP |
| Módulo iniciado | +30 XP |
| Lección finalizada | +15 XP |
| Módulo finalizado | +50 XP |
| Alto puntaje en módulo (>80%) | +25 XP |

#### 3.5.3 Sistema de Retención (Rachas Diarias)

El tiempo de uso y la constancia se miden mediante un sistema de retención.

- El sistema registrará los inicios de sesión diarios consecutivos.
- La interfaz mostrará un contador visual de "Días en racha" (ej. icono de fuego/llama).
- Se otorgarán medallas o insignias visuales al alcanzar hitos de racha (ej. 7 días, 14 días, 30 días).
- Si el usuario no inicia sesión y completa al menos una acción en un lapso de 24 horas, el contador vuelve a cero.

#### 3.5.4 Cálculo de XP_max (Lógica de Backend)

Para asignar el nivel dinámico correcto a cada estudiante, el sistema calculará en tiempo real el XP_max sumando el valor de todo el contenido de los módulos asignados al usuario.
La fórmula a implementar mediante una propiedad calculada en el modelo de usuario es la siguiente:

XP_max = (M × 80) + (L × 15) + (P × 10)

Donde:

- M: Número total de módulos publicados (Aporta 80 XP base: 30 por iniciar + 50 por finalizar).
- L: Número total de lecciones publicadas.
- P: Número total de preguntas (MCQs) publicadas (asumiendo el escenario de respuestas correctas).

#### 3.5.5 Medallas

Se podrán agregar medallas o recompensas de acuerdo con distintas condiciones, como:

- Completar el módulo correspondiente con más de cierto porcentaje, que puede ser variable.
- Completar X cantidad de lecciones o módulos con 100%.
- Completar X cantidad de módulos.
- Completar todos los módulos.
- Completar cierta cantidad de días de Racha.
- Contestar X cantidad de preguntas.
- Contestar X cantidad de preguntas correctamente.
- etc.

### 3.6 Dashboard del Usuario

Página principal:

- Barra superior de gamificación: racha, nivel/XP, medallas.
- Mensaje de bienvenida personalizado.
- Grid de módulos pendientes (cards con: progreso N/total, nombre del módulo, botón Iniciar/Retroalimentación).
- Sección "Tu progreso": cuestionarios completados y barra de progreso general.

Módulo:

- Listado de lecciones del módulo, que llevarán a contestar los MCQs correspondientes.

### 3.7 Retroalimentación

- Modal después de cada respuesta con: explicación, respuesta ideal, XP ganados.
- Pantalla de resumen al finalizar un módulo con: desglose de XP, felicitación.
- El usuario puede revisar retroalimentación de módulos completados.

## 4. Requisitos No Funcionales (RNF)

### 4.1 Seguridad

- HTTPS en producción.
- Control de acceso: solo usuarios autenticados acceden al módulo.

### 4.2 Usabilidad

- Interfaz responsiva (Django Templates + CSS).
- Navegación simple: Inicio, Dashboard, Cerrar Sesión.

### 4.3 Mantenibilidad

- Arquitectura modular: el módulo de gamificación es una app Django separada.

## 5. Requisitos del Sistema

### 5.1 Stack Tecnológico

- **Backend:** Django 4.x+.
- **Base de Datos:** SQLite.
- **Frontend:** Django Templates + CSS (sin JavaScript frameworks).

### 5.2 Entorno de Desarrollo

- Prototipo local: `python manage.py runserver`
- No se requiere Docker, Nginx, ni Gunicorn para el prototipo.
