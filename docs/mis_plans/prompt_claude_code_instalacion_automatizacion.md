# Prompt: instalación por «automatización» en el autoclave

**Prerrequisito:** la sesión del generador debe haber entregado la variante `INSA`/`REIA` del formato 2.1.0 con su informe (vectores finales y función de normalización exacta). No empieces el paso 2 sin esos vectores; si no están, termina el paso 1 y repórtalo.

Trabajo de seguridad (IEC 62304 Clase C): rama propia desde `dev` limpio, pruebas primero donde aplique, y al cerrar actualiza `CLAUDE.md`, `docs/riesgos/registro_riesgos.md` y la trazabilidad. Sin push.

## Contexto y decisiones (cerradas por Cristian)

Hay dos modalidades: **fabricación** (equipo de Especifika, como hoy) y **automatización** (equipo de otro fabricante al que se le instala nuestro software y hardware, conservando su serie y modelo originales).

- La identidad del equipo es el serial interno `SNAANNNN` (el de la licencia, `K_e` y `machine_id = ACV-<año>-<SNAANNNN>`). Es lo que el técnico teclea en el campo de serie del asistente, en ambas modalidades.
- Serie y modelo originales son datos adicionales, firmados en el código a través de `h_orig`. En automatización el técnico los teclea (ASCII imprimible sin `|`; serie 1–40, modelo 1–80) y deben coincidir con lo emitido tras la normalización del generador (copiar su función exacta; no reinventarla).
- **`model_id` NO cambia de significado:** sigue siendo el nombre calculado por `calcular_modelo` y `validate_profile_data` sigue exigiendo que coincida (`installation/profile.py:254-269`). Las capacidades, `desglosar_modelo` y la lógica de clase no se tocan. Se agregan campos nuevos al perfil; el modelo original **no** pasa por `calcular_modelo`.
- **Presentación:** donde hoy se muestra el modelo y la serie, en automatización se muestra el modelo original como principal y la serie original, más el «Serial Especifika» (`SNAANNNN`). En fabricación todo se ve igual que hoy.
- El código de activación v1 de 12 caracteres (`validate_installation_code`, `activation.py:100-114`) no sabe de automatización. El v2 de 48 caracteres (Parte A) aún no existe en el autoclave: se implementa aquí el verificador v2 completo, con `INS/REI/INSA/REIA` (y lo que ya cubra Parte A para FIN/EMG/EXT solo si es necesario para no dejar el verificador incompleto; si Parte A es mucho más grande, limita este trabajo a INS/REI/INSA/REIA y repórtalo). Antes de tocarlo, busca en el repo (`docs/`, `docs/mis_plans/`) la especificación de la Parte A y del formato v2 y úsala como fuente; el autoclave debe llevar `K_t` según su §3.1. **Decisión de Cristian: v1 y v2 conviven.** Reglas:
  - El verificador acepta ambos formatos y los distingue por su forma (longitud/alfabeto; define la detección sin ambigüedad y pruébala con casos límite). Un código que no encaja en ninguno se rechaza como inválido.
  - **Fabricación:** vale un código v1 o v2. El comportamiento con v1 queda exactamente como hoy (regresión con los vectores y pruebas existentes de `validate_installation_code`).
  - **Automatización:** solo vale `INSA`/`REIA` en v2. Un código v1 jamás activa una instalación por automatización (v1 no firma serie ni modelo originales); rechazarlo con un mensaje claro. Un código v2 de fabricación (`INS`) tampoco vale en modo automatización, y al revés.
  - La reinstalación sigue la modalidad del perfil: un equipo de fabricación instalado con v1 se reinstala con v1 o v2; uno de automatización, con `REIA`.
  - No se elimina el v1 en este trabajo. Deja anotado en el informe qué haría falta para retirarlo después (no hacerlo).
  - Añade a las pruebas la matriz completa: {v1, v2} × {fabricación, automatización} × {INS, INSA, REI, REIA}.

## Pasos

1. **Exploración y plan breve.** Lee `installation/profile.py`, `storage.py`, `cambio_perfil.py`, `modelo.py`, `activation.py`, `ui_qml/bridge/puente_instalacion.py`, `ui_qml/qml/Pantallas/Instalacion.qml`, y todos los consumidores de `serial_number`/`model_id` (ticket `startup_ticket.py`, PDF `backend/rutas/reportes.py`, `cycle_logger.py`, `info_equipo.py`, `backend/rutas/sistema.py`, `_comun.py`, `parametros_equipo_controller.py`). Lista qué se toca. Escribe `docs/informes/automatizacion/plan.md` (corto) y sigue.
2. **Verificador v2 con INSA/REIA** en `installation/activation.py` (o módulo vecino), alineado a los vectores del generador. Pruebas con TODOS los vectores (fabricación idénticos a los actuales; INSA/REIA nuevos; INS no valida como INSA y al revés; normalización; rechazos). Sin dependencias de UI (`tests/test_arquitectura_capas.py`).
3. **Perfil:** campos `tipo_instalacion` (`"fabricacion"` | `"automatizacion"`; por defecto `"fabricacion"` al leer perfiles existentes, sin migración destructiva), `serial_original` y `modelo_original` (obligatorios si y solo si automatización; `None`/ausentes en fabricación). `validate_profile_data` valida esa coherencia sin relajar la regla de `model_id`. `storage.py` y `cambio_perfil.py` los serializan, los protegen (un perfil bloqueado no cambia de modalidad ni de originales salvo reinstalando) y los incluyen en cualquier firma/hash del perfil. Un perfil existente sin los campos debe seguir cargando válido.
4. **Asistente (`puente_instalacion.construir_perfil` + `Instalacion.qml`):** casilla «Equipo automatizado (de terceros)» que muestra los campos de serie y modelo originales (validación de charset y largo en el momento, con teclado en pantalla según la regla de `abrirAlfanumericoAccion` del CLAUDE.md si aplica). El modo elige el tipo de código a validar (INS o INSA); no se prueban las dos variantes. Mensaje de error propio en automatización: «Código inválido: revise el serial Especifika y la serie y el modelo originales» (i18n es/en). Reinstalación: `REI`/`REIA` según la modalidad del perfil.
5. **Salidas:** ticket de arranque, PDF/reportes, ticket de ciclo y `cycle_logger` (el modelo/serie que se guarda con cada ciclo es el original en automatización, más el serial Especifika), Información del equipo, `/status.equipo`, bitácora `equipo_instalado` (agrega tipo, serie y modelo originales). Ciclos históricos no cambian. Etiquetas i18n es/en.
6. **Pruebas:** perfil de fabricación idéntico a hoy (regresión), perfil de automatización completo de punta a punta (asistente → perfil → salidas), perfil inválido (originales ausentes o presentes en la modalidad equivocada, `model_id` ajeno rechazado como hoy), carga de perfil antiguo, código cruzado rechazado. Suite completa en verde (`pytest tests`).
7. **Documentación y riesgos:** sección corta en `CLAUDE.md`; entrada en `docs/riesgos/registro_riesgos.md` (riesgo de datos de identidad mal tecleados → código rechazado y reemisión; trazabilidad de dos identidades; custodia de `K_t` en el autoclave); trazabilidad de requisitos. Informe en `docs/informes/automatizacion/R_informe.md` con preguntas abiertas. `estado.md` al día tras cada commit.

## Restricciones

- No cambiar la lógica de control, actuadores, fallas ni puertas.
- No relajar `validate_profile_data` para `model_id`.
- Nada de datos reales de fabricantes en pruebas: usa series y modelos ficticios.
- Si el generador y este prompt discrepan en algo (normalización, charset, mensaje), manda el generador: repórtalo y alinea.
- Sin push; la entrega la hace Cristian con `tools/entrega/compilar_entrega.py`.
