# Planeación — Comparación del código vs NTC-IEC 62304 y pautas de continuidad

**Software:** Software de Autoclave (Especifika S.A.S.)
**Norma base:** NTC-IEC 62304:2019-12-11 (adopción idéntica, IDT, de IEC 62304:2006; **sin Amendment 1:2015**)
**Clase de seguridad declarada:** C
**Estado del documento:** BORRADOR v0.2 — preguntas de la sección 7 respondidas (ver sección 8); pendiente documentación del SGC
**Regla de este documento:** solo planeación. No modifica código. La ejecución sobre el repositorio la hace Claude Code con instrucciones redactadas en el chat.

---

## 1. Lectura de la norma: lo que condiciona el plan

| # | Hallazgo de lectura | Cláusula NTC | Implicación |
|---|---|---|---|
| N-01 | La NTC es traducción de IEC 62304:2006 **sin AMD1:2015**. AMD1 modificó, entre otros, 4.3 (criterio de reducción de clase), añadió 4.4 (software legado) y ajustó actividades de 5.x/7.x. | Portada (correspondencia) | Hay que decidir qué edición rige la auditoría (pregunta P-01). Verificar contra el texto enmendado antes de afirmar diferencias exactas. |
| N-02 | La norma **no prescribe nombre, formato ni contenido** de la documentación, ni un modelo de ciclo de vida, ni estructura organizacional. | Introducción (p. iii) | Los `.md` de `docs\mis_plans\` son formatos válidos de evidencia si cumplen el contenido exigido por cada tarea. |
| N-03 | Conformidad = implementación **total** de procesos, actividades y tareas según la clase. Se determina por inspección de la documentación (incluido el fichero de gestión de riesgos) y evaluación de procesos. | 1.4 | La auditoría es documental + de procesos; el código es evidencia, no sustituto de documentos. |
| N-04 | Un "según aplique" no cumplido exige **justificación documentada**. | Introducción, 1.4 nota 3 | Toda tarea omitida necesita justificación escrita (registro de exclusiones). |
| N-05 | Mientras no haya clase asignada se aplican requisitos de Clase C. Reducción C→B solo con medida de control **hardware** que reduzca consecuencias o probabilidad de la lesión seria. | 4.3 a), g) | El enclavamiento de puertas es solo por software (sin redundancia mecánica): no hay base para reducir. Clase C se sostiene; debe quedar documentada en el fichero de gestión de riesgos (4.3 c). |
| N-06 | La probabilidad de fallo del software se asume 100 % para clasificar. | 4.3 a) | No se puede justificar una clase menor con "el fallo es improbable". |
| N-07 | La clase se asigna por sistema y por elemento software; los elementos heredan la clase salvo justificación de segregación. | 4.3 d), e), f); 5.3.5 | Hay que decidir y documentar la descomposición (ver 3.2). Si no hay segregación efectiva, todo es C. |
| N-08 | Tabla A.1: para Clase C aplican **todas** las cláusulas, incluidas las exclusivas de C: 5.1.4, 5.3.5, 5.4.2, 5.4.3, 5.4.4, 5.5.4. | Anexo A | Matriz de cumplimiento completa, sin cláusulas "N/A" por clase. |
| N-09 | SOUP: identificación (título, fabricante, designación única) y requisitos funcionales/de ejecución y hardware/software de soporte; evaluar listas de anomalías publicadas; gestión de riesgos de SOUP. | 5.3.3, 5.3.4, 7.1.3, 8.1.2, 5.1.7 | Inventario SOUP con versión exacta (PySide6, FastAPI, uvicorn, pyserial, sounddevice, soundfile, Piper, SO, etc.). |
| N-10 | La norma **no cubre validación** del dispositivo final. | 1.2; Tabla C.3 (14.11) | Validación del autoclave queda fuera de este plan; sí entra verificación (5.2.6, 5.3.6, 5.4.4, 5.5.5, 5.6, 5.7). |
| N-11 | 5.5.4 exige criterios de aceptación adicionales de unidad (Clase C): secuencia de eventos, flujo de datos/control, recursos, manejo de fallos, inicialización de variables, autodiagnóstico, gestión de memoria, condiciones límite. | 5.5.4 a–h | Define el contenido de la auditoría de código (sección 4.3). |
| N-12 | 5.8.7: archivar producto, elementos de configuración y documentación por un periodo ≥ vida útil del dispositivo o lo que exija la regulación. 5.8.8: reproducibilidad de la liberación. | 5.8.7, 5.8.8 | Git en `dev` como respaldo no basta como archivo de liberación; falta definir procedimiento (PRO-07). |
| N-13 | 8.2.4: toda solicitud de cambio, informe de problema y aprobación deben ser trazables. | 8.2.4 | Los hallazgos numerados existentes (C-01, H-03, LIQ-xx, UI-xx, V-xx) son candidatos a informes de problema formales (9.1) si se les añade clasificación. |
| N-14 | El texto NTC tiene errores de traducción/OCR (p. ej. 5.6.6 «ensayo de regresan»; 5.2.6 y otras citas de clase). | Varios | Ante duda, arbitrar con el texto original IEC 62304:2006. |

---

## 2. Principios del plan

1. **Spec-before-code.** Este plan y la matriz se completan antes de proponer cualquier cambio al repositorio.
2. **Auditoría de solo lectura.** Claude Code no modifica archivos durante las fases 2–4.
3. **Toda calificación con evidencia concreta** (archivo, línea, commit, resultado de comando). Sin calificación "a ojo".
4. **Hallazgos numerados con severidad**, prefijo `NRM-xx` (cumplimiento normativo), vinculados a cláusula NTC y, si aplica, a hallazgos previos.
5. **Trazabilidad como hilo conductor** (8.2.4, 5.1.1 c, 7.3.3): requisito de sistema → requisito SW → arquitectura → unidad → prueba → resultado → riesgo/medida de control.
6. **Sin veredictos regulatorios.** El resultado describe brechas técnicas; no certifica conformidad ni aprobación ante INVIMA u otra autoridad.

---

## 3. Fases

### Fase 0 — Alcance y decisiones previas
- Resolver las preguntas de la sección 7.
- Fijar edición normativa, límites del sistema software y estructura de elementos software.
- **Entregable:** sección "Decisiones" de este documento actualizada.

### Fase 1 — Matriz de requisitos de la norma
Construir la matriz clausulada (sección 5 de este documento es el esqueleto) con columnas:
`Cláusula | Requisito (resumen) | Clase | Evidencia esperada | Evidencia encontrada | Tipo (Doc/Código/Ambos) | Estado | Hallazgo`.
Estados permitidos: `Cumple`, `Parcial`, `No cumple`, `No evaluado`, `Excluido (justificado)`.
- **Entregable:** `matriz_cumplimiento_62304` (formato según P-04).

### Fase 2 — Inventario de evidencia documental existente
Mapear cada documento actual a cláusulas. Fuentes a inventariar (rutas por confirmar con Claude Code):
- `docs\mis_plans\*.md` (planeaciones por subsistema).
- Documentación `.docx` técnica y retroactiva.
- Hallazgos numerados y su estado.
- Cualquier archivo de riesgos ISO 14971 (ver P-02).

Asignación preliminar de lo que se espera encontrar:

| Cláusula | Evidencia candidata en el proyecto (por verificar) |
|---|---|
| 5.1 Plan de desarrollo | No hay documento único identificado; las planeaciones por subsistema podrían cubrir parcialmente. |
| 5.2 Requisitos SW | Specs `planeacion_*.md` — verificar IDs únicos, rangos/límites/defaults, alarmas, seguridad (autenticación H-03), interfaces. |
| 5.3 Arquitectura | `planeacion_ui_dual_pantalla.md`, documento de arquitectura/README — verificar interfaces PC↔ESP32, SOUP, segregación. |
| 5.4 Diseño detallado | Docstrings / documentación retroactiva — verificar diseño por unidad e interfaces. |
| 5.5–5.7 Verificación/pruebas | Carpeta de tests, si existe — verificar criterios de aceptación y trazabilidad a requisitos. |
| 5.8 Liberación | Sin evidencia conocida de procedimiento de release. |
| 7 Riesgos | Verificar existencia de fichero de gestión de riesgos ISO 14971. |
| 8 Configuración | Git (`dev`), `requirements.lock.txt` (UTF-16) — verificar identificación de versiones y SOUP. |
| 9 Problemas | Hallazgos numerados — verificar clasificación (tipo, alcance, criticidad), cierre y verificación. |

- **Entregable:** columna "Evidencia encontrada" de la matriz completada a nivel documental.

### Fase 3 — Auditoría de código (Claude Code, solo lectura)
Dividida en paquetes de instrucciones que Cristian le entrega a Claude Code. Cada paquete devuelve informe **en español** con rutas y líneas.

**3.1 Inventario estructural (5.3.1, 5.4.1, 8.1.1)**
- Árbol de módulos/paquetes, tamaño, lenguajes (Python, QML, firmware ESP32).
- Propuesta de descomposición sistema → elementos → unidades (para 4.3 d/e y 5.3.5).
- Estado de git: ramas, tags, commits sin trazabilidad a solicitud de cambio.

**3.2 SOUP (5.3.3, 5.3.4, 7.1.3, 8.1.2)**
- Lista de dependencias con versión exacta (`requirements.lock.txt`, decodificar UTF-16).
- `pip-audit` para anomalías conocidas.
- Dependencias del firmware (Arduino core, librerías).
- SO y runtime (versión de Python, Qt).

**3.3 Criterios de 5.5.4 (a–h), por unidad crítica**
Revisar como mínimo `ControlLoop`, máquina de estados global, fases (calentamiento, esterilización, descompresión, secado), enclavamiento de puertas, HAL/serial, calibración, alarmas.

| 5.5.4 | Qué buscar en el código |
|---|---|
| a) Secuencia de eventos | Orden de pasos de `_tick()`, transiciones de estado legales/ilegales. |
| b) Flujo de datos y control | Quién escribe/lee estado compartido, hilos, colas. |
| c) Recursos | Hilos, puertos serial, archivos abiertos, handles. |
| d) Manejo de fallos | `except` genéricos, errores silenciados, estados por defecto seguro, pérdida de comunicación serial/CRC. |
| e) Inicialización de variables | Estado inicial de salidas y variables de proceso al arrancar; reinicio en frío/caliente. |
| f) Autodiagnóstico | Verificaciones al arranque, diagnóstico I2C, watchdog. |
| g) Memoria | Crecimiento no acotado de buffers/listas/logs. |
| h) Condiciones límite | Validación de rangos de parámetros, valores por defecto, saturaciones. |

**3.4 Calidad de código y estándares (5.1.4, 5.5.3)**
- `radon cc` / `radon mi`, duplicación, linter.
- Existencia de una norma de codificación escrita; adherencia observada.
- Uso de reloj de pared vs `time.monotonic()` en temporización de seguridad (relación con C-01/V-05).

**3.5 Pruebas (5.5.5, 5.6, 5.7)**
- Existencia, ubicación y alcance de pruebas unitarias/integración/sistema.
- Existencia de pruebas de fallo y de límites.
- Vínculo prueba → requisito (ID o nombre).
- Capacidad de repetir pruebas (5.6.7 b).

**3.6 Seguridad de la información (5.2.2 e)**
- Autenticación/autorización/auditoría (H-03 y estado actual).
- Interfaces de red expuestas.

**3.7 Trazabilidad muestral (7.3.3)**
- Elegir 3–5 funciones críticas (p. ej. enclavamiento de puerta bajo presión, sobrepresión/aislamiento, fallo de sensor, pérdida de comunicación con ESP32, alarma de esterilización) y recorrer la cadena completa en ambos sentidos.

- **Entregable:** `informe_codigo_vs_62304.md` por paquete + columna "Evidencia encontrada" de la matriz completada a nivel código.

### Fase 4 — Riesgos (7) y enlace con ISO 14971
- Verificar existencia y vigencia del fichero de gestión de riesgos (4.2, 7.1.4, 7.1.5).
- Para cada medida de control implementada en software: ¿está en los requisitos (7.2.2 a)?, ¿tiene clase asignada (7.2.2 b)?, ¿se desarrolló según 5 (7.2.2 c)?, ¿tiene verificación documentada (7.3.1)?
- Evaluar causas potenciales de 7.1.2 a–e (especificación incorrecta, defectos, SOUP, fallos de hardware, mal uso previsible).
- Revisar si las medidas de control nuevas generan nuevas secuencias peligrosas (7.3.2).
- **Entregable:** tabla de trazabilidad de riesgos de software y hallazgos `NRM-xx` de riesgo.

### Fase 5 — Consolidación de brechas
- Lista de `NRM-xx` con severidad (Crítica / Alta / Media / Baja), cláusula, evidencia, acción propuesta y dependencias con hallazgos previos.
- Priorización: primero lo que afecte seguridad del paciente/operador y trazabilidad de Clase C.
- **Entregable:** `hallazgos_nrm.md` + plan de cierre con orden recomendado.

### Fase 6 — Protocolos de continuidad (sección 6)
Redactar los protocolos de la sección 6 como `.md` independientes en `docs\mis_plans\`, priorizados según las brechas de la Fase 5.

---

## 4. Orden y dependencias

```
Fase 0 ──► Fase 1 ──► Fase 2 ──► Fase 3 ──► Fase 5 ──► Fase 6
                          └──────► Fase 4 ──┘
```

Fases 3 y 4 son paralelizables una vez cerrada la Fase 2.

---

## 5. Esqueleto de la matriz de cumplimiento (Clase C: todas aplican)

| Cláusula | Requisito resumido | Tipo |
|---|---|---|
| 4.1 | Demostrar capacidad de proveer software que cumpla requisitos del cliente y reglamentarios (SGC) | Doc |
| 4.2 | Proceso de gestión de riesgos conforme a ISO 14971 | Doc |
| 4.3 a–g | Clasificación de seguridad documentada en fichero de riesgos; herencia y segregación | Doc |
| 5.1.1 | Plan de desarrollo (procesos, entregables, trazabilidad, configuración/SOUP, resolución de problemas) | Doc |
| 5.1.2 | Mantener actualizado el plan | Doc |
| 5.1.3 | Referencia a requisitos del sistema; coordinación y validación del diseño | Doc |
| 5.1.4 | Normas, métodos y herramientas (Clase C) | Doc |
| 5.1.5 | Plan de integración y ensayos de integración (incluye SOUP) | Doc |
| 5.1.6 | Plan de verificación (entregables, tareas, hitos, criterios) | Doc |
| 5.1.7 | Plan de gestión de riesgos del software (incluye SOUP) | Doc |
| 5.1.8 | Planificación de documentación | Doc |
| 5.1.9 | Planificación de gestión de configuración | Doc |
| 5.1.10 | Elementos de soporte controlados (herramientas, ajustes) | Doc/Código |
| 5.1.11 | Control de configuración antes de verificar | Doc/Código |
| 5.2.1 | Requisitos SW derivados de requisitos del sistema | Doc |
| 5.2.2 a–l | Contenido: funcionales, E/S, interfaces, alarmas, seguridad (security), usabilidad, datos/BD, instalación, operación, documentación de usuario, mantenimiento, reglamentarios | Doc |
| 5.2.3 | Medidas de control de riesgo en los requisitos | Doc |
| 5.2.4 / 5.2.5 | Reevaluar análisis de riesgos; actualizar requisitos del sistema | Doc |
| 5.2.6 | Verificar requisitos (no contradictorios, sin ambigüedad, comprobables, identificables, trazables) | Doc |
| 5.3.1 / 5.3.2 | Arquitectura documentada e interfaces entre elementos y con externos | Doc/Código |
| 5.3.3 / 5.3.4 | Requisitos funcionales/de ejecución y de soporte del SOUP | Doc |
| 5.3.5 | Segregación necesaria para control de riesgo (Clase C) | Doc/Código |
| 5.3.6 | Verificación de arquitectura | Doc |
| 5.4.1 | Refinar arquitectura hasta unidades | Doc/Código |
| 5.4.2 / 5.4.3 | Diseño detallado por unidad e interfaces (Clase C) | Doc/Código |
| 5.4.4 | Verificación del diseño detallado (Clase C) | Doc |
| 5.5.1 | Implementar cada unidad | Código |
| 5.5.2 / 5.5.3 | Proceso de verificación de unidad; criterios de aceptación | Doc/Código |
| 5.5.4 a–h | Criterios de aceptación adicionales (Clase C) | Código |
| 5.5.5 | Verificar unidades y documentar resultados | Doc/Código |
| 5.6.1–5.6.8 | Integración, ensayos de integración, regresión, registros, resolución de problemas | Doc/Código |
| 5.7.1–5.7.5 | Ensayos de sistema: cobertura de todos los requisitos, reensayo tras cambios, verificación y registros | Doc/Código |
| 5.8.1–5.8.8 | Liberación: verificación completa, anomalías residuales, versión, cómo se creó, archivo, reproducibilidad | Doc |
| 6.1 | Plan de mantenimiento | Doc |
| 6.2.1–6.2.5 | Retroalimentación, informes de problemas, solicitudes de cambio, comunicación a usuarios/reguladores | Doc |
| 6.3.1 / 6.3.2 | Implementación de modificaciones y redifusión | Doc |
| 7.1.1–7.1.5 | Elementos y causas que contribuyen a situaciones peligrosas, SOUP, secuencias de eventos | Doc |
| 7.2.1 / 7.2.2 | Medidas de control de riesgo y su implementación en software | Doc/Código |
| 7.3.1–7.3.3 | Verificación de medidas, nuevas secuencias, trazabilidad | Doc |
| 7.4.1–7.4.3 | Gestión de riesgos de cambios | Doc |
| 8.1.1–8.1.3 | Identificación de configuración, SOUP, documentación de configuración | Doc/Código |
| 8.2.1–8.2.4 | Aprobación e implementación de cambios, verificación, trazabilidad | Doc/Código |
| 8.3 | Registros recuperables de historia de configuración | Código (git) |
| 9.1–9.8 | Informes de problemas, estudio, aviso, control de cambios, registros, tendencias, verificación, contenido de documentación de ensayo | Doc |

---

## 6. Protocolos de continuidad (a redactar en Fase 6)

Pautas mínimas para que el desarrollo siguiente nazca conforme. Cada una será un `.md` propio.

| ID | Protocolo | Cláusulas | Contenido mínimo |
|---|---|---|---|
| PRO-01 | Plan de desarrollo de software | 5.1 | Ciclo de vida elegido, entregables por actividad, herramientas, responsables. |
| PRO-02 | Identificación y trazabilidad | 5.2, 7.3.3, 8.1 | Esquema de IDs únicos (propuesta: `REQ-SW-xxx`, `RSK-xxx`, `TC-xxx`, `CR-xxx`, `PR-xxx`), matriz de trazabilidad viva. |
| PRO-03 | Solicitud de cambio | 8.2, 6.2.3–6.2.4, 7.4 | Registro de cambio, análisis de impacto en riesgo (7.4.1–7.4.2), aprobación antes de implementar, verificación y reensayo (5.7.3). |
| PRO-04 | Informe y resolución de problemas | 9, 6.2.1 | Plantilla con tipo, alcance y criticidad; relevancia de seguridad; cierre verificado. Adopta el esquema de hallazgos numerados actual. |
| PRO-05 | SOUP | 5.3.3–5.3.4, 7.1.3, 8.1.2 | Ficha por componente, evaluación de anomalías publicadas, política de actualización, `pip-audit` periódico. |
| PRO-06 | Verificación de unidad y pruebas | 5.5, 5.6, 5.7 | Criterios de aceptación 5.5.3/5.5.4, plantilla de caso de prueba, registros repetibles, regresión. |
| PRO-07 | Liberación y archivo | 5.8 | Lista de verificación de release, anomalías residuales evaluadas, versión identificada, entorno de build, archivo de largo plazo, reproducibilidad. |
| PRO-08 | Mantenimiento | 6 | Recepción y evaluación de retroalimentación de campo, criterios de problema, obsolescencia de SOUP. |
| PRO-09 | Gestión de riesgos del software | 7 | Cómo se actualiza el fichero de riesgos ante cambios de requisitos/arquitectura; clase por elemento. |
| PRO-10 | Estándar de codificación | 5.1.4, 5.5.3 | Reglas de estilo, complejidad máxima, manejo de errores, reloj monotónico, inicialización segura. |

**Definición de "terminado" propuesta para todo cambio futuro** (sujeta a confirmación):
1. Existe solicitud de cambio aprobada (8.2.1).
2. Análisis de impacto en riesgo registrado (7.4).
3. Requisitos/arquitectura/diseño afectados actualizados.
4. Unidad verificada contra criterios (5.5.5); pruebas de integración y regresión ejecutadas y registradas (5.6.6, 5.7.3).
5. Trazabilidad actualizada.
6. Cambio visualmente confirmado por Cristian antes del commit (flujo actual).

---

## 7. Preguntas bloqueantes

**P-01 — Edición normativa.** La NTC-IEC 62304:2019 equivale a IEC 62304:2006 sin AMD1:2015. ¿La auditoría se basa solo en la NTC, o también debe contrastarse con AMD1 (relevante si el mercado objetivo o un cliente exige la edición enmendada)? Propuesta por defecto: NTC como base normativa y AMD1 como referencia complementaria, marcando diferencias relevantes.

**P-02 — Gestión de riesgos.** ¿Existe un fichero de gestión de riesgos ISO 14971 (peligros, causas, medidas de control) y una clasificación de seguridad documentada y aprobada? Si existe, ¿dónde está y quién la aprobó? Si no, Fase 4 pasa a ser construcción desde cero y se redefine su alcance.

**P-03 — Alcance de elementos software.** Propuesta por defecto: dentro del alcance backend Python, HAL/serial, firmware ESP32, UI QML y launcher. SOUP: Python, PySide6/Qt, FastAPI, uvicorn, pyserial, sounddevice, soundfile, Piper (build-time) y librerías del firmware. ¿Confirmas o excluyes algo?

**P-04 — Formato de la matriz.** Por defecto el flujo usa `.md`. Una matriz de ~90 filas con estados filtrables es más manejable en `.xlsx`. ¿`.md`, `.xlsx` o ambos?

**P-05 — Sistema de gestión de calidad.** ¿Especifika S.A.S. tiene un SGC (ISO 13485 u otro) con procedimientos documentados para diseño y desarrollo, control de documentos y registros? Define si 4.1 se evalúa contra procedimientos existentes o se registra como brecha (ver hoja D.5 de la norma).

**P-06 — Ejecución sobre el repositorio.** Confirma que la Fase 3 la ejecuta Claude Code en modo solo lectura sobre la rama `dev`, con informe en español, y que yo redacto los paquetes de instrucciones 3.1–3.7.

---

## 8. Decisiones registradas

Respuestas de Cristian, 2026-10-07:

| ID | Decisión | Efecto |
|---|---|---|
| P-01 | «Sí» — interpretado como aceptar el valor por defecto: NTC como base y AMD1:2015 como referencia complementaria. **Corregir si la intención era otra.** | Se marcan diferencias NTC vs AMD1 en hallazgos relevantes. |
| P-02 | **No existe fichero de gestión de riesgos ISO 14971.** | Fase 4 = construcción desde cero. Clase C declarada sin fichero: hallazgos críticos en 4.2, 4.3 c, 7.1.4, 7.1.5, 7.2.1, 7.3.3 (precargados en la matriz como «No cumple», severidad propuesta Crítica, a validar). |
| P-03 | Alcance confirmado: backend Python, HAL/serial, firmware ESP32, UI QML, launcher; SOUP según lista propuesta. | Alcance fijo. |
| P-04 | Matriz en `.xlsx`. | `matriz_cumplimiento_62304.xlsx` (Fase 1 iniciada). |
| P-05 | Existe SGC, pero su manual solo remite a documentos anexos que no se han entregado; fueron solicitados y prometidos para 2026-10-08. | 4.1 y procedimientos asociados quedan «No evaluado» hasta recibirlos. La Fase 2 documental del SGC se retoma al recibirlos. |
| P-06 | Fase 3 la ejecuta Claude Code, solo lectura, rama `dev`, informe en español. | Paquetes redactados en `paquetes_claude_code_62304.md`. |

---

## 9. Limitaciones conocidas

- En este chat no hay acceso al código; el código no ha sido inspeccionado. Toda afirmación sobre el estado del repositorio en este documento es **hipótesis por verificar**.
- Las diferencias entre IEC 62304:2006 y AMD1:2015 citadas provienen de conocimiento general y deben verificarse contra el texto enmendado.
- Este documento no constituye certificación ni dictamen regulatorio.
