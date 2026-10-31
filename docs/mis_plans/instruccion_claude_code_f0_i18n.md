# Instrucción para Claude Code — F0: Inventario de cadenas (i18n)

Pega el bloque siguiente en Claude Code, en `C:\Users\tecni\Documents\codigo_autoclave\`, rama `dev`.

---

```
Tarea: F0 del plan de idiomas (español/inglés). Es una tarea de SOLO LECTURA.

Reglas
- No modifiques ningún archivo de código, de configuración ni de datos existente.
- No hagas commit.
- Lee docs\mis_plans\planeacion_i18n.md (v2) antes de empezar.
- No asumas: si algo no se puede determinar leyendo el código, anótalo como pregunta abierta, no lo adivines.
- Responde y redacta todo en español.

Entregables (crear solo estos dos archivos nuevos)
1. docs\mis_plans\inventario_cadenas_i18n.md  (resumen y hallazgos)
2. docs\mis_plans\inventario_cadenas_i18n.csv (una fila por cadena)

Columnas del CSV: superficie, archivo, línea, cadena literal, tipo (fija / con variables), variables, criticidad (alarma-seguridad / informativa), dominio sugerido, observación.

Qué inventariar

A. UI QML: toda cadena visible al usuario en archivos .qml y en textos que Python entrega a QML. Cuenta por archivo.
B. Alarmas, fallas y eventos: lista completa de códigos. Para cada uno indica dónde se define su texto, si el texto viaja o se guarda como texto libre o como código, y en qué tablas/columnas/archivos queda guardado. Esto responde el hallazgo I18N-01.
C. Persistencia: columnas de SQLite, archivos JSON y YAML que contengan texto visible al usuario (nombres de ciclos, fases, parámetros, sensores, roles, etc.). Distingue ciclos de fábrica (cycles/factory) de los creados por usuario.
D. Reportes PDF, ticket de arranque y plantillas de correo: módulo que los genera y todas sus cadenas.
E. Logs técnicos: configuración de logging, formato y los mensajes emitidos.
F. Voz: estado real de implementación del subsistema de anuncios de voz (si existe código o solo el plan); los 33 anuncios y su texto; modelo Piper usado y su versión; carpeta y nombres de los WAV; cómo se reproduce y cómo se prioriza la cola.
G. Fechas y números: dónde se formatean (strftime, QLocale, f-strings con decimales, etc.) y con qué formato.
H. Mecanismos de traducción existentes: gettext, QTranslator, qsTr, tr() u otro. Indica si ya hay alguno y dónde.
I. Vistas PySide de configuración y service_ui: solo cuenta de cadenas por archivo (están fuera de alcance, D-02).

Cierre del informe (inventario_cadenas_i18n.md)
- Totales por superficie.
- Respuesta explícita a I18N-01, con evidencia (archivo y línea).
- Lista de preguntas abiertas que no pudiste resolver leyendo el código.
- Cualquier hallazgo de seguridad o inconsistencia que encuentres, con código de severidad (I18N-xx) siguiendo el formato de planeacion_i18n.md.
- No propongas cambios de código en este informe.
```
