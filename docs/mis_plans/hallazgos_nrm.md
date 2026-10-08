# Hallazgos NRM — NTC-IEC 62304:2019 (IEC 62304:2006) — Software de Autoclave

Estado: v0.1 — 2026-10-07. Fuentes: declaración de Cristian (P-02) y paquete 3.1 (rama `dev`, commit `e7bccf2`).
Severidad = propuesta; la valida el responsable técnico. Solo planeación: ninguna acción se implementa durante la auditoría.

---

## NRM-01 — Clase C declarada sin fichero de gestión de riesgos
- **Severidad:** Crítica
- **Cláusulas:** 4.2, 4.3 c, 7.1.4, 7.1.5, 7.2.1, 7.3.3 (y, por dependencia, 7.1.1–7.1.3, 7.2.2, 7.3.1–7.3.2, 7.4)
- **Evidencia:** declaración de Cristian, 2026-10-07: no existe fichero ISO 14971.
- **Descripción:** no hay peligros, causas, secuencias de eventos ni medidas de control documentados. Sin ellos no es posible demostrar la clasificación ni trazar medidas de control a sus verificaciones.
- **Relacionados:** C-01, H-03, LIQ-01 y demás hallazgos previos son candidatos a entradas del fichero (causas potenciales).
- **Acción propuesta:** construir el fichero desde cero (Fase 4), empezando por las funciones de seguridad ya identificadas en el código (ver sección "Insumos" más abajo).
- **Estado:** Abierto

## NRM-02 — Cambios sin trazabilidad a solicitud de cambio
- **Severidad:** Alta
- **Cláusulas:** 8.2.4 (también 8.2.1, 6.2.4)
- **Evidencia:** paquete 3.1-D: 1 de 519 commits en `dev` cita un identificador de cambio o hallazgo (`aa900f1`, 2026-09-29); búsqueda ampliada a NRM-, NU-, G- sin resultados adicionales. Varios commits citan planes por nombre (p. ej. `a01dfc5` → `planeacion_teclados_qml`).
- **Descripción:** existen planes y specs por subsistema, pero no hay enlace verificable commit ↔ solicitud de cambio ↔ aprobación. Calificado a nivel de commits; falta revisar si hay registros de aprobación en otro lugar.
- **Relacionados:** NRM-03.
- **Acción propuesta:** definir PRO-03 (solicitud de cambio) y convención de ID en el mensaje de commit.
- **Estado:** Abierto

## NRM-03 — Identificación de versión y liberación no formalizada
- **Severidad:** Media
- **Cláusulas:** 8.1.1, 8.3, 5.8.4 (relacionadas: 5.8.5, 5.8.7, 5.8.8)
- **Evidencia:** paquete 3.1-D/E: sin tags (`git tag -l` vacío); versión `0.5.0` única en `pyproject.toml:7`; sin `__version__` ni `VERSION`; 7 ramas locales y 3 worktrees paralelos; correspondencia entre `0.5.0` y lo compilado en `dist/` NO VERIFICADO.
- **Descripción:** hay versión declarada y registrada en el ciclo (`cycle_logger.py:37-44`), pero no esquema documentado de identificación de elementos de configuración (incluidos SOUP y documentos) ni registro de liberación.
- **Acción propuesta:** PRO-07 (liberación y archivo) y esquema de identificación (PRO-02).
- **Estado:** Abierto

## NRM-04 — Sin política de control documental
- **Severidad:** Media
- **Cláusulas:** 8.1.3, 8.3, 5.1.8 d), 5.1.9, 5.1.11
- **Evidencia:** paquete 3.1-F: varios planes de `docs\mis_plans\` (autenticación, protocolo serial ESP32, opciones, migración QML, sensores, etc.) y 7 informes de `docs\informes\` figuran sin versionar `(u)`. Confirmación de Cristian (2026-10-07): **no existe política** sobre qué documentos se versionan ni cómo se aprueban.
- **Descripción:** documentos que especifican comportamiento de seguridad (autenticación, protocolo serial) están fuera de control de configuración. 5.1.8 d) exige procedimientos y responsabilidades de desarrollo, revisión, aprobación y modificación de documentos.
- **Acción propuesta:** definir en PRO-01/PRO-02 qué documentos son elementos de configuración, dónde viven, cómo se aprueban y cómo se versionan.
- **Estado:** Abierto

---

## Observaciones del paquete 3.1 aún sin clasificar
Se anotan como candidatas; no son hallazgos hasta recolectar más evidencia.

| # | Observación | Evidencia | Cláusula posible |
|---|---|---|---|
| O-01 | `pyproject.toml:32` declara el punto de entrada `autoclave.app:main`, pero `src/autoclave/app.py` no existe | `ls`: «No such file or directory» | 8.1 / 5.8.5 |
| O-02 | `README.md` referenciado en `pyproject.toml:9` no existe | paquete 3.1-F | 5.1.8 / 5.8.5 |
| O-03 | Solo 4 módulos Python con docstring de módulo (de 196 archivos) | paquete 3.1-B | 5.4.2 (diseño detallado por unidad); revisar si los `.docx` de `Documentacion\` lo cubren |
| O-04 | UI tkinter heredada sigue en el árbol (`ui/`, `main_window.py` 1052 líneas con términos de seguridad) junto a QML y PySide6 | paquete 3.1-B/C | 5.3.1 (arquitectura), 5.1.10 |
| O-05 | Tres ramas viven en worktrees paralelos (`alarmas-parte-a`, `roles-sensor-temperatura`, `anuncios-voz`) | `git worktree list` | 8.2, 5.1.11 |
| O-06 | Firmware ESP32 en un solo archivo `.ino` de 229 líneas | paquete 3.1-C | 5.4.x, 5.5.x |

## Insumos para los siguientes paquetes (nombres reales confirmados)
Unidades con lógica de seguridad según 3.1 (clasificación heurística, no análisis de riesgo):
- `services/domain/loop/control_loop.py` (383 l.) · `core/runtime/status.py` · `core/runtime/letalidad.py` · `core/runtime/steam.py`
- `state_machine/state_machine.py` · `states/{ciclo,preparacion,preparado,emergencia,falla,hibernacion,control_banda}.py` · `cycle_phases/{precalentamiento,prevacio,calentamiento,esterilizacion,descompresion,secado,protocolo_fallo,valvula_reposo}.py` · `alarms/{alarm,alarm_manager}.py`
- Puertas: `devices/puertas/{advanced_door,simple_door,base_puertas,door_factory}.py` · `services/domain/puertas/{ser_puertas,door_command_service,permissions}.py`
- Salidas/seguridad física: `devices/io/set_io.py` · `devices/paro_emergencia/paro_emergencia.py` · `devices/suministro_electrico/suministro_electrico.py` · `devices/pump/pump.py`
- Comunicación: `protocols/{crc16,serial_link,serial_link_config,device_reset}.py` · firmware `.ino`
- Conversión/calibración: `hal/measures/{converters,units,calibration_tools}.py` · `config/{calibration_writer,schema}.py`
- API y autenticación: `backend/server.py` (1275 l.) · `backend/{autenticacion,contrasenas,context}.py`

Pruebas: 168 archivos `.py` en `tests/` (a evaluar en el paquete 3.5).
