# Especificaciones del Módulo Gamificado para el Desarrollo de Habilidades Blandas

Plataforma Web de Alumnos y Tutores – Instituto Tecnológico de Mérida/TecNM

## 1. Introducción

### 1.1 Propósito del Documento

Este documento describe los requisitos técnicos para un módulo gamificado de desarrollo de habilidades blandas, integrado a la plataforma web de tutorías del TecNM. El módulo ofrece preguntas de opción múltiple (MCQ) generadas por LLM, con distribución personalizada mediante un sistema de lógica difusa.

### 1.2 Alcance del Proyecto

El módulo es un prototipo funcional integrado a la plataforma Django existente. Proporcionará:

- Evaluación inicial de 10 habilidades blandas (scores 0-100).
- Distribución personalizada de MCQs por habilidad usando el sistema de lógica difusa.
- Preguntas MCQ generadas por LLM, organizadas en módulos por habilidad.
- Sistema de gamificación (XP, niveles, rachas, medallas).
- Panel de progreso del usuario.

## 2. Descripción General

### 2.1 Funcionalidad del Módulo

- Evaluación inicial: el usuario proporciona (o se le asignan) scores para 10 habilidades blandas.
- El sistema de lógica difusa calcula la distribución de MCQs entre las habilidades (total configurable, por defecto 100 MCQs).
- Se generan MCQs por LLM para cada habilidad según la cantidad asignada.
- El usuario completa los MCQs organizados en módulos (uno por habilidad), con retroalimentación inmediata.
- El sistema registra respuestas, calcula XP, y actualiza progreso.

### 2.2 Supuestos y Dependencias

- La plataforma web existente está construida en Django.
- Se usa SQLite como base de datos.
- El frontend se construye con Django Templates (sin React ni API REST separada).
- El sistema tendrá acceso a una API de LLM (ej. OpenAI, Anthropic).
- El sistema autenticará usuarios mediante el sistema de auth de Django.

## 3. Sistema de Personalización (Lógica Difusa)

### 3.1 Descripción

La personalización se limita a la distribución de MCQs entre habilidades. Se usa el sistema de lógica difusa (`scikit-fuzzy`) descrito en `fuzzy-system-soft-skills.py`.

### 3.2 Entradas

10 scores de habilidades blandas (0-100):

1. Comunicación
2. Trabajo en equipo
3. Liderazgo
4. Resolución de problemas
5. Gestión del tiempo
6. Adaptabilidad
7. Creatividad
8. Inteligencia emocional
9. Resolución de conflictos
10. Pensamiento crítico

### 3.3 Proceso

- **Antecedente:** Nivel de habilidad (0-100) con funciones de membresía: Very_Poor, Poor, Adequate, Good.
- **Consecuente:** Peso de prioridad (0-10) con funciones de membresía: Very_Low, Low, Medium, High, Very_High.
- **Reglas:** A menor nivel de habilidad, mayor prioridad de entrenamiento.
- **Salida:** Distribución de MCQs proporcional a los pesos de prioridad (las habilidades más débiles reciben más preguntas).

### 3.4 Salida

Un diccionario `{habilidad: número_de_MCQs}` que suma exactamente el total configurado. El sistema usa el método de mayor residuo para asegurar que la suma sea exacta.

## 4. Requisitos Funcionales (RF)

### 4.1 Gestión de Usuarios

- Autenticación mediante `django.contrib.auth`.
- Perfil extendido que almacena: scores de habilidades blandas y datos de gamificación.

### 4.2 Ingesta de Scores (JSON)

- No se implementa evaluación inicial en este prototipo.
- Los scores de habilidades blandas se cargan desde un archivo JSON por usuario.
- Formato del JSON:

    ```json
    {
        "user_id": "alumno01",
        "scores": {
            "comunicacion": 45,
            "trabajo_en_equipo": 70,
            "liderazgo": 30,
            "resolucion_de_problemas": 60,
            "gestion_del_tiempo": 25,
            "adaptabilidad": 80,
            "creatividad": 55,
            "inteligencia_emocional": 40,
            "resolucion_de_conflictos": 65,
            "pensamiento_critico": 50
        }
    }
    ```

- Al cargar el JSON, el sistema de lógica difusa calcula la distribución de MCQs.

### 4.3 Generación de Preguntas (LLM)

- El sistema se comunica con una API de LLM para generar MCQs basadas en la habilidad blanda objetivo.
- Se usan prompts genéricos que solicitan el formato estándar del proyecto (ver `Docs/MCQs-empatia.md` como referencia).
- Cada MCQ generada debe incluir:
    - **Escenario:** Situación contextualizada y detallada en segunda persona, con personajes y contexto emocional.
    - **Pregunta:** Pregunta directa sobre la acción más empática/apropiada.
    - **4 opciones (A, B, C, D):** Una correcta y tres incorrectas, cada una representando un patrón de respuesta distinto (ej. consejo no solicitado, minimización, cambio de enfoque a uno mismo, evaluación crítica).
    - **Respuesta correcta:** Indicada por letra.
    - **Explicación:** Por qué la respuesta correcta es la mejor, seguida de por qué cada opción incorrecta falla (con viñetas por cada opción incorrecta).
- Se almacena en la base de datos: texto del escenario, pregunta, opciones, respuesta correcta, explicación completa, metadatos (habilidad, fecha de generación).
- Las preguntas se generan por lotes al crear los módulos del usuario.

### 4.4 Módulos de MCQ

- Un módulo por cada habilidad blanda que tenga MCQs asignados.
- Cada módulo contiene N preguntas (según la distribución de la lógica difusa).
- El usuario navega pregunta por pregunta con:
    - Barra de progreso.
    - Selección de respuesta (grid 2x2).
    - Botón "Enviar respuesta".
    - Modal de retroalimentación con respuesta ideal y XP ganados.
    - Navegación: "Siguiente pregunta" / "Finalizar" (en la última).

### 4.5 Gamificación

#### 4.5.1 Puntos de Experiencia (XP)

| Acción | XP |
|---|---|
| Respuesta correcta | +15 XP |
| Respuesta incorrecta (participación) | +10 XP |
| Módulo iniciado | +15 XP |
| Módulo finalizado | +50 XP |
| Alto puntaje en módulo (>80%) | +25 XP |
| Racha diaria (días 1-6) | +5 XP/día |
| Racha diaria (día 7) | +15 XP |

#### 4.5.2 Niveles

| Nivel | Nombre | XP requerido |
|---|---|---|
| 1 | Principiante en Habilidades Blandas | 200 XP |
| 2 | Escuchante Activo | 400 XP |
| 3 | Mentor Acompañante | 700 XP |
| 4 | Líder Empático | 1000 XP |
| 5 | Maestro en Habilidades Blandas | 1600 XP |

#### 4.5.3 Rachas

- Se registra actividad diaria (contestar al menos 1 MCQ).
- Ciclo semanal de 7 días con XP acumulativo.
- Al completar 7 días consecutivos se otorga una medalla y se reinicia el ciclo.

#### 4.5.4 Medallas

Medallas predefinidas por logros:

- **Primeros pasos:** Completar la evaluación inicial.
- **Maestro de Empatía / Responsabilidad / etc.:** Completar el módulo correspondiente con >80%.
- **Primera llama:** Racha de 3 días.
- **Fuego constante:** Racha de 7 días.
- **Fuego intenso:** Racha de 14 días.
- **Mes en llamas:** Racha de 30 días.
- **Coleccionista de habilidades:** Completar 5 módulos.
- **Campeón en habilidades blandas:** Completar todos los módulos.
- **Aprendiz constante:** Contestar 50 preguntas.

### 4.6 Dashboard del Usuario

Según el mockup, el dashboard muestra:

- Barra superior de gamificación: racha, nivel/XP, medallas.
- Mensaje de bienvenida personalizado.
- Grid de módulos pendientes (cards con: progreso N/total, nombre del módulo, botón Iniciar/Retroalimentación).
- Sección "Tu progreso": cuestionarios completados y barra de progreso general.

### 4.7 Retroalimentación

- Modal después de cada respuesta con: explicación, respuesta ideal, XP ganados.
- Pantalla de resumen al finalizar un módulo con: desglose de XP, felicitación.
- El usuario puede revisar retroalimentación de módulos completados.

## 5. Requisitos No Funcionales (RNF)

### 5.1 Seguridad

- HTTPS en producción.
- Credenciales de API de LLM almacenadas en variables de entorno.
- Control de acceso: solo usuarios autenticados acceden al módulo.

### 5.2 Usabilidad

- Interfaz responsiva (Django Templates + CSS).
- Navegación simple: Inicio, Dashboard, Cerrar Sesión.

### 5.3 Mantenibilidad

- Arquitectura modular: el módulo de gamificación es una app Django separada.
- Código del sistema de lógica difusa encapsulado en un servicio reutilizable.

## 6. Requisitos del Sistema

### 6.1 Stack Tecnológico

- **Backend:** Django 4.x+
- **Base de Datos:** SQLite
- **Frontend:** Django Templates + CSS (sin JavaScript frameworks)
- **LLM:** API externa (OpenAI, Anthropic, etc.)
- **Lógica difusa:** scikit-fuzzy (numpy, scikit-fuzzy)

### 6.2 Dependencias Python

- Django
- scikit-fuzzy
- numpy
- openai / anthropic (cliente de LLM)

### 6.3 Entorno de Desarrollo

- Prototipo local: `python manage.py runserver`
- No se requiere Docker, Nginx, ni Gunicorn para el prototipo.
