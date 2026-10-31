# Informe ESS — Estado seguro silencioso por sensor sin lectura (ESS-01 a ESS-07)

Fecha: 28-oct-2026. Rama `dev`, base 26aa4033 (1.0.0-alpha.9), árbol limpio al empezar. Clase C.
Plan: `docs/mis_plans/planeacion_estado_seguro_silencioso.md`.

**Sin commit**: los cambios quedan sin confirmar para la revisión visual de Cristian.
**No se compiló la entrega.** Comando, desde `dev` limpio y después de confirmar los cambios:
`python tools/entrega/compilar_entrega.py`

---

## 1. ESS-01 · Inventario de sensores (según el código)

### 1.1 Sensores cuya falta de lectura DISPARA el protocolo de estado seguro

| Sensor | Alarma | Dónde | Cómo |
|---|---|---|---|
| Presión de cámara (en ciclo) | SEN-04 | `state_machine/states/ciclo.py:1189-1199` (`CODIGO_EN_CICLO`, `core/runtime/presion_sin_lectura.py:29`) | FALLO, `ejecutar(solo_lenta=True)` |
| Presión de chaqueta (en ciclo, si `io_enabled` la declara) | SEN-05 | mismo bloque, `ciclo.py:1197-1199` | FALLO, `ejecutar(solo_lenta=True)` |
| Principal (en ciclo) | SEN-02 | `ciclo.py:1208-1223` | FALLO, `solo_lenta`; en líquidos modos 4/5 enfriando con contrapresión, sellado (D8-2.10) |
| Empaque de puerta (en ciclo) | SEN-08 | `ciclo.py:524` y `ciclo.py:1167` | FALLO, `ejecutar(solo_lenta=(codigo == SEN_08))` |
| Referencia con carga líquida (en ciclo) | CIC-19 | `ciclo.py:891-892` | FALLO, protocolo normal |
| Presión de cámara o Principal (arranque) | SEN-06 / SEN-03 (fuera de ciclo) | `services/domain/loop/control_loop.py:442-451` | `camara_segura` falsa al arrancar → estado seguro de arranque, `solo_lenta` |
| Principal o presión con el protocolo ya en marcha | — (enclava) | `cycle_phases/protocolo_fallo.py:893-908` (`pasar_a_solo_lenta`) | pasa a solo la lenta |

### 1.2 Sensores cuya falta de lectura DETIENE el protocolo (`bloqueado_motivo`)

`cycle_phases/protocolo_fallo.py:497-531`, por prioridad:
1. Presión de cámara sin lectura (`_presion_perdida`, l. 515; incluye la trama AI vencida, que es comunicación, no sensor).
2. Sellado con líquidos (l. 522) — no es un sensor solo: espera de las sondas con la carga caliente. **Conserva CIC-10.**
3. Principal sin lectura en `solo_lenta` (l. 525).
4. Principal sin lectura enfriando en modos 4/5 (l. 527).
5. Tiempo límite con carga líquida caliente (l. 529) — no es sensor. **Conserva CIC-10.**

### 1.3 Sensores cuya falta de lectura deja `camara_segura` en NO segura

`core/runtime/camara_segura.py:65-102` (`evaluar`): `sin_presion_camara` (l. 92) y `sin_temp_camara` (l. 95, Principal de los programas vía `temp_seguridad`). Lo demás no es sensor: `sin_datos_vigentes` (comunicación, l. 77), `falta_config`, `sobrepresion`, `vacio`, `temp_alta`.
En `services/domain/puertas/ser_puertas.py`: `sensor_temp_indeterminado` (l. 253) es un **error al determinar los programas**, no una lectura; `sin_presion_empaque` (l. 318) solo impide **cerrar** la puerta, no deja la cámara no segura.

### 1.4 Diferencias con la referencia de la spec (se siguió el código)

- **SEN-07 (chaqueta fuera de ciclo) NO entra**: no dispara el protocolo, no lo detiene y no interviene en `camara_segura` (solo bloquea el inicio, `presion_sin_lectura.py:65`). Sin sufijo. DECISIÓN SIN CONFIRMAR.
- **CIC-19 SÍ entra** (Referencia sin lectura con carga líquida dispara el protocolo, `ciclo.py:891`): lleva el sufijo «— No abrir la puerta». No silencia nada (la presión y el Principal leen). DECISIÓN SIN CONFIRMAR.
- **`sensor_temp_indeterminado` NO cuenta como sensor**: es un error de software; falla cerrada (se muestra todo). DECISIÓN SIN CONFIRMAR.
- **`sin_presion_empaque` / SEN-08**: SEN-08 entra por disparar el protocolo (lleva el sufijo), pero el empaque no detiene el protocolo ni interviene en `camara_segura`, así que no participa en el silencio.
- **SEN-05**: entra por disparar el protocolo (sufijo); tampoco participa en el silencio (la chaqueta no está en `camara_segura`).
- La trama AI vencida (presión «perdida» por comunicación) no silencia: `/status` exige `presion_vigente`.

Inventario resultante: **silencio** solo por `sin_presion_camara` y `sin_temp_camara`; **sufijo** en SEN-02, SEN-03, SEN-04, SEN-05, SEN-06, SEN-08 y CIC-19; **CIC-10** suprimido para los motivos 1, 3 y 4 de §1.2.

---

## 2. Cambios (sin commit)

| Archivo | Cambio |
|---|---|
| `src/autoclave/state_machine/cycle_phases/protocolo_fallo.py` | `bloqueado_motivo(incluir_sensor=False)` y propiedad `bloqueado_motivo_no_sensor` (solo consulta; el protocolo no cambia). |
| `src/autoclave/state_machine/estado_seguro.py` | ESS-03: CIC-10 con `bloqueado_motivo_no_sensor` (sellado y tiempo límite con carga caliente se conservan); log de desarrollo una vez por episodio del Principal (ESS-06; el de presión ya existía). Propiedades `bloqueado_motivo_sin_presion` y `bloqueo_no_sensor` (falla cerrada: sin la consulta, True). |
| `src/autoclave/core/runtime/camara_segura.py` | `motivos()` (todos los motivos, mismo orden que `evaluar`), `CODIGOS_SENSOR`, `solo_por_sensor()`. Solo presentación; `evaluar` intacto. |
| `src/autoclave/backend/rutas/sistema.py` | `/status`: `camara_segura_motivo_es_sensor` y `estado_seguro.silencioso_por_sensor`; `estado_seguro.bloqueado_motivo` = `bloqueado_motivo_sin_presion`. |
| `src/autoclave/ui_qml/bridge/ui_bridge.py` | `noAbrirPorSensor`, `estadoSeguroSilencioso` (solo `is True`). |
| `src/autoclave/ui_qml/qml/Componentes/SeccionEstadoSeguro.qml` | Oculta las 5 filas del estado 3 en silencio y `filaNoAbrir` con motivo de sensor; no cuentan en la campana. |
| `src/autoclave/ui_qml/qml/Componentes/VentanaDetalleAlarma.qml`, `PanelNotificaciones.qml`, `Pantallas/PantallaPreciclo.qml` | Botón «Asignar sonda Principal» en el detalle de SEN-02/SEN-03 cuando el estado seguro está detenido por la sonda. |
| `src/autoclave/state_machine/alarms/catalogo.py`, `src/autoclave/i18n/es.json`, `en.json` | Sufijo «— No abrir la puerta» / «— Do not open the door» (ESS-05). |
| `src/autoclave/backend/server_reasignacion.py` | 409 de ESS-07 (§4.3: `_motivo_estado_seguro`, `_motivo_sensor_seguridad`); comentario de cabecera sin «PENDIENTE»; mensaje 409 `estado` y docstring (SAF-10). |
| `src/autoclave/ui_qml/controllers/reasignacion_controller.py` | Motivos `estado_seguro_confirmar`, `estado_seguro_liquido` y error `sensor_camara_no_segura`; textos `reasignacion.*` es/en (también `motivo_estado` corregido). |
| `tests/test_r8_reasignacion_api.py` | Fixture con lecturas reales y sin paro; sección ESS-07 (H1, SAF-01, SAF-03 y los huecos de la revisión de los 409). |
| `docs/riesgos/registro_riesgos.md` | HAZ-ESS-01, HAZ-IO-05 (con la mitigación del 29-oct) y HAZ-IO-01 actualizado. |
| `tests/test_ess_estado_seguro_silencioso.py` (nuevo) | 36 casos: §5 completo, falla cerrada, textos, QML (campana en 1) y SAF-04 a SAF-08. |
| `tests/test_ess07_reasignacion_reinicio.py` (nuevo) | Reinicio con protocolo activo (con y sin presión, líquidos), puertas en la ventana, SEN-09; 4 `xfail(strict)` que documentan H1. |
| `tests/test_t17_s3_esg.py`, `tests/test_s9_estado_seguro_arranque.py`, `tests/test_t5_estado_seguro.py` | Actualizadas a ESS-03 (el Principal sin lectura ya no da CIC-10). |

### Reglas del silencio (`sistema._silencioso_por_sensor` / `_motivo_es_sensor`)
`silencioso_por_sensor` = estado seguro activo **y** sin confirmación pendiente **y** sin `PARO_EMERGENCIA` **y** `bloqueo_no_sensor` False **y** `camara_segura_motivo_es_sensor`.
`camara_segura_motivo_es_sensor` = presión vigente **y** todos los motivos de `camara_segura.motivos()` son de sensor **y** ninguna sonda de cámara con lectura supera `temp_max_apertura` **y** (si falta la presión) la última presión vigente estaba en atm ± rango **y** cada motivo tiene su alarma ACTIVA (presión: SEN-04 o SEN-06; Principal: SEN-03 con su nombre o SEN-02 que lo nombre). Cualquier excepción → False. `bloqueo_no_sensor` es además True enfriando en modos 4/5 y con el protocolo inactivo. Además la sección QML nunca silencia con sin conexión, tarjeta desconectada o sin datos.

---

## 3. ESS-07 · Cambios rápidos sin prueba ni revisión desde 3531c194

| Commit / sitio | Contenido | Pruebas | Riesgo | Revisión | Estado |
|---|---|---|---|---|---|
| acb33873 | Reasignación de E/S en FALLA y con el estado seguro actuando (`server_reasignacion.py`), «urgente, sin pruebas» | 3be8252d + `tests/test_ess07_reasignacion_reinicio.py` (nuevas) | HAZ-IO-05 (nuevo) | Esta sesión (§4) | H1 y SAF-01 (ALTOS) y SAF-03 mitigados con 409 por decisión de Cristian (29-oct, §4.3); quedan residuales en §4.3 |
| 3be8252d | Ajuste de `test_r8_reasignacion_api.py` | sí | — | Esta sesión | Cerrado |
| 26aa4033 | Versión 1.0.0-alpha.9 (compilada con los dos anteriores) | — | — | — | La alpha.9 lleva H1 y SAF-01 sin mitigar |
| e8d57124, ecb0a198, f3ae8c5f | Versión alpha.8 y documentos de la tanda 21 | — | — | — | Sin cambios de código |
| `src/` «PENDIENTE: análisis de riesgo / pruebas» | Solo la cabecera de `server_reasignacion.py` | — | — | — | Comentario actualizado |

---

## 4. Revisión de seguridad

Dos pasadas: el análisis de §6.2 de acb33873 (subagente, con pruebas en `tests/test_ess07_reasignacion_reinicio.py`) y **un solo revisor de seguridad Clase C** al final, sobre el diff de ESS y sobre acb33873 + 3be8252d (solo lectura, sin ejecutar pruebas). H1 lo verifiqué además en el código (`control_loop.py:448-449` llama a `ejecutar(abrir_valvulas=False, solo_lenta=True)` sin `en_enfriamiento_contrapresion`).

### 4.1 acb33873 / 3be8252d (alcance B) — hallazgos (mitigados el 29-oct, ver §4.3)

| ID | Sev. | Hallazgo | Opción más segura y reversible |
|---|---|---|---|
| **H1 / SAF-02** | **ALTO** | El reinicio que sigue a la reasignación pierde el sellado de líquidos (D8-2.10) y la contrapresión de modos 4/5: el estado seguro de arranque corre en `solo_lenta` sin sellar y ventea por la lenta con la carga caliente (`control_loop.py:448-449`, `protocolo_fallo.py:221-222` y `:599-607`). Documentado con 4 `xfail(strict)`. | **DECISIÓN PARA CRISTIAN.** Una línea en `_motivo_bloqueo`: 409 con el estado seguro activo y (`sellado`, o carga líquida con la cámara sobre atm + brecha o sobre `temp_max_apertura`). Conserva el caso urgente (sólido o cámara fría con el sensor dañado). |
| **SAF-01** | **ALTO** | Tras reasignar `pres_camara` o el Principal, la lectura del puerto nuevo **sin verificar** (SEN-09) decide `camara_segura`, el fin del estado seguro, `no_abrir` y el interlock de puertas. Un puerto mal cableado que lea ~atm con la cámara presurizada termina el protocolo y habilita la puerta (`camara_segura.py:90`, `context.py:370-389`). SEN-09 solo bloquea el inicio y las salidas de energía. Antes la reasignación exigía la cámara segura. | **DECISIÓN PARA CRISTIAN.** 409 al reasignar `pres_camara` o el Principal con la cámara no segura (lo más reversible), o que `camara_segura` y el interlock fallen cerrados mientras esas AI estén sin verificar. |
| SAF-03 | MEDIO | No se rechaza la reasignación con la confirmación pendiente tras un paro real: el proceso nuevo arranca el estado seguro sin confirmación (D9-1.2 eludido) (`server_reasignacion.py:194-207`, `control_loop.py:451`). | 409 con `estado_seguro.requiere_confirmacion` o `PARO_EMERGENCIA`. |
| H2 | MEDIO | Con la presión sin lectura, la lenta que venteaba se cierra en el reinicio y el arranque sin presión no la reabre (HAZ-S9-02). | Cubierto por la regla del 409 de SAF-01. |
| Obs. | MEDIO | El reinicio saca al equipo de FALLA sin reconocimiento (arranca en PREPARACION). SEN-09 sí sobrevive. | Por confirmar. |
| (c) | BAJO | Se pierde el aviso CIC-10 de «tiempo límite con carga caliente»; la rápida sigue sin abrirse en ningún modo. | — |
| Ventana | — | Sin vigilancia estimada en 4–10 s (hasta ~45 s si el módulo reescribe su configuración de seguridad), **no medida**; todas las salidas apagadas; ninguna puerta abre por API (proceso viejo: estado seguro activo; nuevo: 503 y `camara_segura` sin datos vigentes). ALL_OFF deja `bloqueo/desbloqueo_puerta_N` en reposo (empaque conservado) pero apaga `cerrar_on`: confirmar en banco. | Medir en banco. |
| SEN-09 | — | Sigue exigida antes de iniciar un ciclo (`context.py:316-345`). | — |

Riesgo: **HAZ-IO-05** en `registro_riesgos.md` (H1, SAF-01, SAF-03, H2). HAZ-IO-01 sigue diciendo «solo en PREPARACION/PREPARADO»: actualizar cuando Cristian decida.
Textos obsoletos corregidos (SAF-10, solo texto): mensaje 409 `estado` y docstring de `server_reasignacion.py`; `reasignacion.motivo_estado` es/en ya no dice «resuelva primero la falla».

### 4.2 Diff de ESS (alcance A) — corregidos en esta sesión

| ID | Sev. | Hallazgo | Corrección |
|---|---|---|---|
| SAF-04 | MEDIO | Silencio con una sonda caliente conocida: sin el Principal, `temp_seguridad` da None aunque otra sonda lea 120 °C. | No hay silencio si alguna sonda de cámara con lectura (no el drenaje) supera `temp_max_apertura` (`sistema._alguna_sonda_caliente`). |
| SAF-05 | MEDIO | Silencio con la cámara presurizada un instante antes de perder la presión, o con contrapresión de aire. | Se guarda la última presión vigente vista por `/status`; fuera de atm ± rango no hay silencio. `bloqueo_no_sensor` es True enfriando en modos 4/5. Con la última presión desconocida (arranque con el sensor ya dañado) rige el residual de HAZ-ESS-01. |
| SAF-06 | BAJO | Bastaba cualquier SEN-02/SEN-03 activa. | SEN-03 con el nombre del Principal como origen, o SEN-02 que lo nombre. |
| SAF-07 | BAJO | Sin SEN-02/SEN-03 activa (p. ej. tras P-2) se quitaba CIC-10 y no quedaba ningún aviso. | CIC-10 se conserva si no hay SEN-02/SEN-03 ACTIVA **del Principal** (SEN-03 con su nombre como origen o SEN-02 que lo nombre; misma regla que `/status`). Ajustado tras la suite completa: antes valía la de cualquier sonda (lo detectó `test_saf06_alarma_de_otra_sonda_no_silencia`). |
| SAF-08 | BAJO | `bloqueo_no_sensor` daba False con el protocolo terminado entre lecturas. | True si no está activo (falla cerrada). |
| SAF-09 | BAJO | `bloqueado_motivo` sin el texto de presión también cuando no hay silencio. | **No aplicado**: la spec (ESS-02) pide quitarlo siempre. Queda para Cristian. |
| FC-10 | — | Los títulos más largos envuelven (WordWrap, sin recorte) en la bandeja, la campana y el detalle; no bajan la letra porque envuelven. Ticket, PDF e historial no revisados con los títulos nuevos. | Revisar en la verificación visual. |

Sin hallazgo: las funciones nuevas no las usa ningún interlock, válvula, bloqueo de inicio ni `no_abrir`; sin datos vigentes, trama AI vencida, paro, confirmación pendiente, sin conexión o tarjeta sin datos no hay silencio; CIC-10 se conserva para el sellado y el tiempo límite también con la presión o el Principal perdidos.

### 4.3 Decisión de Cristian (29-oct): 409 acotados — IMPLEMENTADOS

Cristian confirmó los 409 para H1 y SAF-01 (y SAF-03, incluido en la propuesta). En `server_reasignacion._motivo_bloqueo(diferencias)`:

| Regla | Código (`motivo`) | Dónde |
|---|---|---|
| Paro activo o «Confirmar y llevar a estado seguro» pendiente (SAF-03) | `estado_seguro_confirmar` | `_motivo_estado_seguro` (también en GET: pantalla no editable con el texto propio) |
| Estado seguro activo con carga líquida o sellada; tipo de carga ilegible = líquida (H1) | `estado_seguro_liquido` | `_motivo_estado_seguro` |
| Mover `pres_camara` o un Principal con la cámara no segura (SAF-01) | error `sensor_camara_no_segura` | `_motivo_sensor_seguridad`, bajo `_sm_lock` justo antes de detener el lazo |

Excepción del caso urgente de acb33873 (DECISIÓN SIN CONFIRMAR, refinamiento mío para no volver a dejar el equipo sin salida con el sensor dañado): se permite mover **solo** la presión si el único motivo es `sin_presion_camara`, o **solo** el Principal si el único motivo es `sin_temp_camara`, y además ninguna sonda de cámara lee por encima de `temp_max_apertura` y, al mover el Principal, otra sonda de cámara que no se mueve lee fría (el drenaje no cuenta). Todo error → 409.

Revisión de seguridad de este diff (un revisor Clase C adicional, incluido en la opción elegida):

| ID | Sev. | Hallazgo | Estado |
|---|---|---|---|
| R-SAF-01 | ALTO | `temp_ref` (estado) vs `temp_referencia` (asignación): una Referencia usada como Principal se movía sin comprobar. | **Corregido**: comparación canónica (`aio.canonico`). Prueba `test_saf01_referencia_como_principal_*`. |
| R-SAF-02 | MEDIO | Sin programas, no se consideraba `temp_camara` (el fixture devolvía `[None]`). | **Corregido** (`lista or [None]`; el fixture devuelve `[]`). |
| R-SAF-03 | MEDIO | Las diferencias se calculaban contra lo guardado, no contra lo que usa el proceso (respaldo restaurado sin aplicar, archivo dañado). | **Corregido**: se suman las diferencias con `aio.en_memoria()`. Pruebas `test_saf01_asignacion_guardada_*` y `test_saf01_restaurar_fabrica_*`. **Fuera de alcance, abierto:** «Reiniciar software» (`rutas/apagado.py:229-239`) aplica una asignación pendiente sin esta comprobación. |
| R-SAF-04 | MEDIO | La excepción del caso urgente suponía que la presión atmosférica prueba la carga fría, y viceversa. | **Endurecido**: hace falta otra sonda fría al mover el Principal y ninguna sonda caliente. **Residual (pregunta para Cristian):** una cámara fría presurizada con aire (contrapresión fuera del estado seguro, prueba de aire) con el sensor de presión dañado permite mover la presión. |
| R-SAF-05 | BAJO | Tras un 409 `estado_no_permitido`, la pantalla muestra el texto genérico (`err_estado`); el motivo concreto solo se ve en el aviso de no editable al recargar. | No aplicado. |

Preguntas del revisor: (1) con `_recuperacion_pendiente` líquida aún no entregada (sin la primera AI) el estado seguro no está activo y la reasignación pasa; el proceso nuevo repite la misma recuperación (no parece empeorar). (2) Mover las DI de puerta cerrada o de paro con la cámara no segura no está cubierto por ESS-07.

Los `xfail(strict)` de `tests/test_ess07_reasignacion_reinicio.py` siguen: documentan el comportamiento del protocolo de arranque (que no cambió); por una reasignación ya no se alcanza.

---

## 5. Decisiones sin confirmar

1. Inventario (§1.4): SEN-07 fuera, CIC-19 dentro, `sensor_temp_indeterminado` no es sensor.
2. El silencio exige la alarma del sensor ACTIVA, ninguna otra sonda caliente y la última presión conocida en banda (protecciones añadidas tras la revisión, no pedidas en la spec): si no, se muestra todo. CIC-10 por el Principal se conserva si no hay SEN-02/SEN-03 activa.
3. `botonAsignarSonda` (S4): se conserva en la sección mientras se vea el estado seguro y se agrega al detalle de SEN-02/SEN-03 (en silencio la sección lo oculta). Así no se pierde la vía de recuperación.
4. `estado_seguro.bloqueado_motivo` en `/status` sigue llevando el texto del Principal (la spec pide solo quitar el de presión); `estadoSeguroBloqueoPorSonda` depende de él.
5. Con motivo mixto (Principal perdido y cámara presurizada) la UI muestra el estado seguro y la nota «detenido» pero **no hay CIC-10** (ESS-03 literal: el único motivo de *bloqueo* es un sensor).
6. Trama AI vencida: sigue sin CIC-10 (ESG-01) y ahora tampoco silencia (sin `presion_vigente` se muestra todo).
7. SAF-09 no aplicado (la spec manda quitar siempre el texto de presión de `bloqueado_motivo`).
8. La última presión vigente se guarda en memoria del backend: tras un reinicio es desconocida y se permite el silencio (caso de la foto, residual de HAZ-ESS-01).

---

## 6. Suite

Suite completa, una vez, al final (`python -m pytest tests -q -p no:cacheprovider`, 29-oct, 1 h 01 min):

**3 failed, 9100 passed, 11 skipped, 7 xfailed** (los 7 xfail incluyen los 4 `xfail(strict)` de `test_ess07_reasignacion_reinicio.py`).

| Prueba que falló | Causa | Arreglo |
|---|---|---|
| `test_ess_estado_seguro_silencioso.py::test_saf06_alarma_de_otra_sonda_no_silencia` | Defecto real de SAF-07: una SEN-03 de una Referencia quitaba CIC-10 con el Principal sin lectura. | `ProtocoloEstadoSeguro._alarma_principal_activa` exige la alarma del Principal (falla cerrada: ante la duda, CIC-10 se conserva). Las pruebas antiguas que activaban SEN-03 con `origen="Principal"` (`test_t5`, `test_s9`, `test_t17_s3_esg`) pasan al origen real (`nombre_legible`, como `sensores_ciclo.py:276`). |
| `test_t21_fin_de_ciclo_backend.py::test_cic19_en_el_catalogo_es_bloqueante_como_cic12` | Título de CIC-19 con el sufijo de ESS-05 (es y en). | Prueba actualizada al texto nuevo. |
| `test_v8b_textos.py::test_descripciones_citan_nombres_visibles_de_parametros` | El texto nuevo `reasignacion.motivo_estado_seguro_confirmar` citaba un botón entre «» (la regla reserva «» para nombres de parámetros). | Texto sin comillas angulares (es y en). |

Después del arreglo se repitieron solo los archivos afectados: `test_ess_estado_seguro_silencioso`, `test_t21_fin_de_ciclo_backend`, `test_v8b_textos`, `test_t17_s3_esg`, `test_s9_estado_seguro_arranque`, `test_t5_estado_seguro`, `test_r8_reasignacion_api`, `test_ess07_reasignacion_reinicio`: **296 passed, 4 xfailed**. La suite completa **no** se volvió a correr (regla: una sola vez al final); conviene repetirla antes del commit.

---

## 7. Prueba de banco a repetir

Transductor de presión de cámara desconectado, arrancar el equipo (foto del 28-oct, Preciclo):
- Solo la fila **SEN-06 «Sensor de presión de cámara sin lectura — No abrir la puerta»**; la campana marca **1**.
- No aparecen «Llevando la cámara a estado seguro», «Arranque con la cámara no segura…», el botón «En curso…», «NO ABRIR hasta que la cámara esté segura», la nota naranja ni la fila NO ABRIR.
- Comprobar que la puerta sigue sin abrir (bloqueo del backend) y que el inicio de ciclo sigue bloqueado.
- Reconectar el transductor: el estado seguro termina solo con la cámara segura (3 lecturas) o, si sigue no segura por otra causa, vuelven a verse sus filas.
- En inglés: «Chamber pressure sensor without reading — Do not open the door» completo, sin recorte.
