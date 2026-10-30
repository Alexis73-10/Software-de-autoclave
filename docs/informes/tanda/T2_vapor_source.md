# T2 — E1b: fuente de vapor (`vapor_source`)

Instrucción: tanda 2026-10-14 §2 T2 y §1.3 (D-23 de `planeacion_fin_de_ciclo_y_puertas.md`).

## 1. Qué se hizo

- `installation/profile.py`: `VAPOR_SOURCES = ("generator", "boiler", "mixed")`, campo `InstallationProfile.vapor_source` (opcional), validación en `validate_profile_data` y `salidas_vapor_permitidas(profile)`.
- `installation/storage.py`: lee y guarda el campo (solo si está definido).
- `devices/io/set_io.py`: `SetOutput.set_output` fuerza OFF todo encendido de DO1 (`vapor_generador`) o DO2 (`vapor_caldera`) cuando la fuente no está instalada; `salida_bloqueada(canal)`.
- `backend/server.py`: `PATCH /io/test/output/{name}` responde 409 `fuente_vapor_no_instalada` si se intenta encender la salida de una fuente ausente (antes respondía ok aunque la salida no se encendía).
- Asistente QML de instalación: los valores que envía pasan de `interno | externo | mixto` a `generator | boiler | mixed`; las claves `instalacion.vapor_*` de `es.json`/`en.json` se renombraron igual (sin cambiar los textos).
- Adenda en `planeacion_menu_instalacion_ui.md`.

| `vapor_source` | Salidas permitidas |
|---|---|
| `generator` | `vapor_generador` |
| `boiler` | `vapor_caldera` |
| `mixed` | ambas |
| ausente (perfil anterior a E1b) | ambas (comportamiento previo) |
| valor desconocido | ninguna (falla cerrada) |

## 2. Pruebas

`tests/test_t2_vapor_source.py` (24 pruebas): validación, salidas por fuente, bloqueo en `set_output` (también por la ruta genérica), apagado siempre permitido, falla cerrada con valor desconocido, persistencia. Se vieron fallar antes de implementar (ImportError). Suite completa: ver `estado.md`.

## 3. Revisor de seguridad

T2 no está en la lista obligatoria, pero toca actuadores y se revisó. Sin Crítico ni Alto. Corregidos: SAF-01 (Medio; valor desconocido habilitaba las dos fuentes, ahora ninguna) y SAF-03 (Bajo; respuesta de `/io/test/output`). Pendiente SAF-02 (Bajo): el bloqueo se calcula al construir `SetOutput`; un cambio de `vapor_source` exige reiniciar el backend (hoy el perfil no se puede cambiar en caliente: está bloqueado).

## 4. PENDIENTE (decisión de seguridad)

Ningún código del control enciende hoy DO1 ni DO2: solo el modo prueba. T2 garantiza que la salida de la fuente ausente nunca se encienda, pero **cuándo se enciende la del generador o la caldera** (en PREPARACION, durante el ciclo, al paro) no está definido en ningún documento y no se implementó. Si el generador del equipo de pruebas depende de DO1 para producir vapor, hay que decidirlo antes del 19-oct.

Riesgo anotado por el revisor: si no hay interlock de hardware que impida energizar la válvula de una fuente no instalada, el bloqueo por software es la única barrera.

## 5. DECISIONES SIN CONFIRMAR

- D-T2-1: perfil sin `vapor_source` = ambas salidas (compatibilidad). Alternativa: falla cerrada (ninguna) con aviso al arrancar.
- D-T2-2: los YAML `config/instances/*.yaml` y `config/models/*.yaml` listan salidas de vapor, pero ningún código los lee (OPC-31); no se tocaron.

## 6. Comprobaciones manuales de Cristian

- En la instalación del 19-oct elegir "Generador interno": `installation_profile.json` debe quedar con `"vapor_source": "generator"`.
- En modo prueba, encender `vapor_caldera`: debe rechazarse con "La fuente de vapor de esta salida no está instalada".
- Confirmar cómo se habilita el generador del equipo (DO1 o control propio) — ver §4.
