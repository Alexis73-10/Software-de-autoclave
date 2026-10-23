# Informe E1 — Equipo e instalación (tanda 8)

Rama `tanda-8-e1` (worktree `.claude/worktrees/agent-af2e355c6e4aaee60`), sin push, merge ni rebase.
Puntos: D8-3.17, D8-3.19 ★, D8-3.21, D8-3.22, D8-3.20. Fecha: 22/23-oct-2026.
La sesión se cortó una vez por límite de uso; la segunda parte terminó lo que quedó sin commit (revisión final de 3.19 y 3.21), hizo una re-revisión de 3.19 y escribió este informe.

## 1. Qué se hizo, por punto

### D8-3.17 — Canales de E/S derivados del perfil (`d45b6b2`)
- `io_enabled` del YAML de la instancia (`config/instances/ACV-2026-001.yaml`) pasa a ser el **máximo físico** (se agregan `temp_2_camara`, `suministro_electrico`, `descompresion_lenta`, `vapor_caldera`, aire comprimido de chaqueta y de cámara, `agua_chaqueta`, `buzer_alarma`).
- `io_names.filtrar_por_perfil` deja solo lo que declara el perfil de instalación: `temperature_probes`, `supply_inputs`, `door_count`/`door_type` y `vapor_source`. Lo usan `/io/channels` y `/cycle/display-inputs` (Entradas/Salidas y Preciclo).
- Textos nuevos de los canales en `i18n/es.json` y `en.json`.

### D8-3.19 ★ — Aire atmosférico en modo prueba (`bb6b889`, `69a816e`, `24bb200`, `f2cd679`, `a1b4e7d`)
Única excepción a D-ES-15. `PATCH /io/test/output/aire_atmosferico_camara` con `value=true` se rechaza (409, texto del catálogo `io.err_aire_con_presion|sin_presion|sin_referencia`) si:
- `pres_camara` > `presion_atmosferica` + `rango_presion_atm` (CON_PRESION);
- no hay lectura, o es menor que el piso físico de 1 kPa (un lazo 4-20 mA abierto se leía 0,0 kPa = "vacío");
- la cuenta ADC **cruda** del canal no supera su `adc_min` de fábrica durante **5 tramas AI nuevas seguidas** (`Units.TRAMAS_SENAL_PRESION`, igual a la profundidad de la mediana de presión);
- la presión publicada se leyó de Units **antes** de confirmar esa señal (`ControlLoop.estado_leido_mono`);
- la trama AI tiene más de 1,5 s, o el estado publicado por el paso 1 del lazo tiene más de 1,5 s, o los datos (enlace + DI) no están vigentes;
- falta la presión atmosférica de referencia (SIN_REFERENCIA).

En vacío sí se permite (sirve para romper el vacío). Si ya está abierta y la condición deja de cumplirse, el lazo ordena cerrarla en cada tick (sin mirar la trama DO, idempotente) y lo anota una vez en la bitácora (`aire_atmosferico_cortado_prueba`). El texto del diálogo de entrada a modo prueba se actualizó para mencionar este bloqueo.

Revisiones (4 rondas, ver §3). La última parte (`a1b4e7d`):
- `SerialLink` publica `data["ai_seq"]` (+1 por trama AI). Son **las mismas líneas que S1** ya unió a `tanda-8` (`782c0c3` y anteriores), para que esa parte no choque al unir.
- `Units` solo cuenta tramas AI nuevas (misma regla que S1: 0 es el estado inicial; un salto grande hacia atrás es un contador reiniciado). Reinicia los contadores al desconectar (`port_open` False) y al recargar la calibración.
- `ControlLoop` toma como instante de lectura el `now` del inicio del tick, sin otra llamada al reloj. Esto además corrige `test_control_loop_desconexion_ciclo.py::test_reconexion_dentro_de_la_tolerancia_reinicia_el_contador`, que `f2cd679` había roto al agregar una llamada a `time.monotonic()`.

### D8-3.21 — Windows rechaza el apagado (`d25ba42`, `a7bdea5`)
- Si `shutdown` devuelve un código distinto de 0 o falla al lanzarse, el backend lo marca: `GET /system/shutdown/estado` devuelve `windows_rechazado`.
- El panel Equipo (`PanelEquipo.qml`, puente `comandos_sistema.py`) consulta cada 2 s y muestra "Windows no permitió apagar el equipo: apáguelo manualmente" (catálogo es/en).
- El rechazo queda en `audit_log` (`apagado_windows_rechazado`) con una conexión propia, porque la secuencia de apagado ya cerró la base.
- Revisión final (`a7bdea5`):
  - esa conexión no toma `self._lock`, para no colgarse si el cierre se quedó con el lock (SAF-05);
  - abre con `mode=rw`, así no crea una base vacía (TMG-03);
  - el puente vigila también cuando el POST queda sin respuesta (`APAGADO_INCIERTO`, TMG-02).

### D8-3.22 — Texto final del asistente (`d45b6b2` catálogo, `a0fcfee` prueba)
- "INSTALACIÓN COMPLETADA" / "El equipo ha sido registrado correctamente. Pulse Continuar para empezar a usarlo." con el botón Continuar.
- Al pulsarlo sale con el código 3, que `exe_unico` toma como arranque normal.

### D8-3.20 — Un solo monitor (`16843df`)
Sin detección automática. Se documenta `--una-pantalla` en `docs/instalacion/LEEME_INSTALACION.md`, con un acceso directo de ejemplo.

## 2. Commits (rama `tanda-8-e1`, sobre `23704cb`)

```
7455023 docs(tanda8-e1): hoja de banco (A-07, B-12, B-13, D-38) y registro de riesgos (HAZ-E1-01..03)
a1b4e7d fix(tanda8-e1): D8-3.19 senal de presion confirmada con 5 tramas AI nuevas y estado leido despues
a7bdea5 fix(tanda8-e1): D8-3.21 bitacora del rechazo sin el lock de la base y vigilancia con apagado incierto
16843df docs(tanda8-e1): D8-3.20 LEEME, un solo monitor con --una-pantalla y acceso directo de ejemplo
a0fcfee feat(tanda8-e1): D8-3.22 resultado del asistente "Instalacion completada" con Continuar
d25ba42 feat(tanda8-e1): D8-3.21 aviso y bitacora cuando Windows rechaza el apagado
f2cd679 fix(tanda8-e1): D8-3.19 senal cruda del transductor y estado publicado al dia (tercera revision)
24bb200 fix(tanda8-e1): D8-3.19 exigir trama AI vigente (segunda revision)
69a816e fix(tanda8-e1): D8-3.19 correcciones de la primera revision
d45b6b2 feat(tanda8-e1): D8-3.17 canales de E/S derivados del perfil de instalacion
bb6b889 feat(tanda8-e1): D8-3.19 aire atmosferico en modo prueba solo sin presion en camara
```
(En la lista, los títulos de algunos commits van abreviados; arriba se ve el texto completo.)

## 3. Pruebas y revisores

Pruebas nuevas: `tests/test_t8_e1_aire_atmosferico_prueba.py`, `tests/test_t8_e1_apagado_rechazado.py`, `tests/test_t8_e1_asistente_texto_final.py` y `tests/test_t8_e1_io_enabled_perfil.py`. También se ajustaron `tests/test_io_names.py`, `tests/test_io_test_mode_endpoints.py` y `tests/test_p1_instalacion_manana.py`.

Corrida final, solo con las pruebas relacionadas (por orden de esta sesión **no se corrió la suite completa**). Se usó `PYTHONPATH=<worktree>/src` y `autoclave.__file__` = `C:\Users\tecni\Documents\codigo_autoclave\.claude\worktrees\agent-af2e355c6e4aaee60\src\autoclave\__init__.py`:
- `tests/test_t8_e1_*.py`, `test_p1_instalacion_manana`, `test_b8_salida_forzada_modo_prueba`, `test_control_loop_*` (7 archivos), `test_e1_supply_inputs_loop_status`, `test_e6_control_loop_tarjeta`, `test_io_test_mode_endpoints`, `test_p1_salida_modo_prueba`, `test_serial*` (5 archivos), `test_units_reload_calibration`, `test_converters_realistic`, `test_converters_smoothing`, `test_s4_cic10`, `test_t2_p5_despeje_manual_com`, `test_t7_ui_seguridad`, `test_t7_apagar_equipo` y `test_io_names`: **422 passed**.
- Hubo una corrida anterior con 1 fallo transitorio: `test_control_loop_resilience.py::test_excepcion_en_door_update_no_mata_el_hilo_control_loop`. Depende de hilos y la máquina tenía unos 12 agentes en paralelo. Pasó 3 de 3 veces sola y pasó en la repetición del conjunto.

Revisores sobre 3.19 (★): `safety-reviewer`, `timing-auditor` y `sensor-role-auditor`, en paralelo, en cada ronda:

| Ronda | Hallazgos Alto/Crítico | Corregido en |
|---|---|---|
| 1 | SAF-01/02/04, TMG-01/02/06, SEN-01 | `69a816e` |
| 2 | SAF-01/TMG-01/SEN-01: trama AI congelada | `24bb200` |
| 3 | SEN-01: lazo abierto leído ~1,5 kPa con calibración de fábrica; SAF-01/TMG-01: estado publicado viejo | `f2cd679` |
| Final (sesión 1) | Media: SEN-01, ventana de la mediana. 3.21: SAF-05, TMG-02, TMG-03 | sin commit al cortarse; commiteado en `a1b4e7d` / `a7bdea5` |
| Re-revisión (sesión 2) | **SEN-01 Alto**: el contador de 5 sumaba líneas DI/DO/ST, no tramas AI. SAF-01/TMG-02 Medio: presión publicada leída antes de la confirmación. SEN-02/SAF-03 Bajo: `reload_calibration` | `a1b4e7d` |

Re-verificación de `sensor-role-auditor` sobre `a1b4e7d`: **SEN-01, SAF-01/TMG-02 y SEN-02 cerrados, sin Altos ni Críticos nuevos.** Dejó 2 hallazgos Bajos (ver §7).

Planta simulada en los 4 programas de fábrica: **no aplica**. D8-3.19 solo actúa en modo prueba (fuera de ciclo) y no toca ninguna celda de transición de ciclo ni de puertas.

Hoja de banco (`docs/mis_plans/hoja_pruebas_banco_equipo_pruebas.md`):
- A-07 (3.22);
- B-12 (3.19, con el paso 6 nuevo: reconectar el transductor con la cámara presurizada);
- B-13 (3.21);
- D-38 (3.17).

Registro de riesgos (`docs/riesgos/registro_riesgos.md`): HAZ-E1-01 (3.19), HAZ-E1-02 (3.21) y HAZ-E1-03 (3.17).

## 4. Puntos de choque al unir

- **`src/autoclave/hal/measures/units.py`**: choca con S1, que ya está en `tanda-8`. S1 cambió `update_from_serial` (`_pressure` empieza en None, `_ultimo_ai_seq`, `convert_pressures(..., nueva_muestra=nueva)`). Cómo resolver:
  - conservar el código de S1;
  - mantener la llamada `self._contar_senal_presion(data)` después de la conversión.
  - E1 usa su propio atributo `_ultimo_ai_seq_senal` con la misma regla, así que los dos conviven. Más adelante se puede unificar usando la `nueva` de S1.
- **`src/autoclave/protocols/serial_link.py`**: las líneas de `ai_seq` son idénticas a las de S1 y deberían unirse limpias. Si git marca conflicto, quedarse con una sola copia.
- **`src/autoclave/services/domain/loop/control_loop.py`**: E1 cambió el paso 1 (`estado_leido_mono`/`_estado_publicado_mono = now`), `presion_vigente`, `_ai_vigente` y `_vigilar_aire_atmosferico_prueba`. Puede chocar con S1/R8 en el paso 1.
- **`src/autoclave/backend/server.py`**: `/io/test/output`, `/io/channels`, `/cycle/display-inputs` y `/system/shutdown/estado`.
- **i18n** (`es.json`/`en.json`): `instalacion.listo_texto`, `equipo.apagado_windows_rechazado`, `io.err_aire_*`, nombres de canales nuevos, `io.ui.dialogo_texto` y textos de bitácora (`aire_atmosferico_cortado_prueba`, `apagado_windows_rechazado`).
- **`db_manager.py`**: solo se agrega el método `registrar_auditoria_tras_cierre`. **Sin migración** (no cambia el esquema; usa la tabla `audit_log` existente).
- **QML compartidos**: `Componentes/PanelEquipo.qml`, `InstalacionVentana.qml`, `Pantallas/Instalacion.qml` (un `objectName`). También el puente `comandos_sistema.py`, que S1/V8a también tocaron en `tanda-8`, así que habrá conflicto.
- `config/instances/ACV-2026-001.yaml` (`io_enabled`).

## 5. DECISIONES SIN CONFIRMAR

1. **Cierre automático (3.19)**: si el aire atmosférico ya está abierto en modo prueba y la condición deja de cumplirse, el lazo lo cierra y lo anota en la bitácora. D8-3.19 solo habla de rechazar la orden; se eligió lo más seguro.
2. **En vacío se permite abrir (3.19)**: el único límite es por arriba (atm + brecha). Romper el vacío es el uso normal de la salida.
3. **Piso de 1 kPa, señal cruda sobre `adc_min` y 5 tramas AI (3.19)**: con esto un lazo 4-20 mA abierto cuenta como "sin lectura". Consecuencias:
   - la salida queda bloqueada unos 2,5 s después de reconectar el transductor;
   - si el equipo no tiene calibración de fábrica, el criterio es "ADC > 0".
4. **Instante de lectura = inicio del tick (3.19)**: `_estado_publicado_mono` también pasa a ser el inicio del tick, así la vigencia de 1,5 s queda unos milisegundos más estricta.
5. **`io_enabled` como máximo físico (3.17)**: un equipo **actualizado** (no reinstalado) conserva su YAML viejo (LEEME 1.4) y no ve los canales nuevos hasta que se copie el YAML.
6. **Apagado incierto (3.21)**: si el POST queda sin respuesta, se muestra ese mensaje, el botón se vuelve a habilitar y la vigilancia del estado sigue cada 2 s, sin límite de tiempo.

## 6. PREGUNTAS PARA CRISTIAN

1. ¿Qué cuenta ADC entrega en campo el transductor de presión de cámara con el lazo abierto: 0 estable o ruido de varias cuentas? Con `adc_min` = 5 el margen es pequeño (SEN-03).
2. ¿`adc_min` de fábrica corresponde a 4 mA del transmisor?
3. ¿La entrada de aire atmosférico tiene antirretorno o filtro que limite la salida de vapor? Eso fija la severidad residual de HAZ-E1-01.
4. ¿El firmware de campo mantiene AI cada 500 ms? La espera de 5 tramas depende de esa cadencia.
5. ¿Se acepta cerrar solo el aire atmosférico abierto en modo prueba (decisión 1)?
6. Para equipos actualizados (decisión 5): ¿el instalador debe reemplazar el YAML de la instancia?

## 7. Pendientes y hallazgos abiertos (no Altos/Críticos)

- SEN-03 (Bajo): el piso usa `adc_min` aunque la calibración de fábrica esté incompleta, y sin calibración el criterio es "ADC > 0".
- TMG-03 (Bajo, 3.21): si `close()` quedó con una transacción abierta, la fila de auditoría se pierde tras 10 s y solo queda en el log.
- TMG-04 (Bajo, 3.21): faltan `@Slot` en `_al_terminar`/`_al_leer_estado_apagado`, y la vigilancia con apagado incierto no tiene límite de tiempo.
- No se corrió la suite completa en esta sesión (orden explícita). La sesión principal debe correrla después de unir con `tanda-8`.
- Bajo (re-verificación): `_reiniciar_senal_presion()` no pone en blanco `_ultimo_ai_seq_senal`.
  - Se deja así a propósito: si se borrara, la notificación de `_connect`, que trae la AI vieja, contaría como trama nueva.
  - Hoy `ai_seq` nunca baja en la vida del proceso. Si un día se reiniciara, el efecto sería una espera más larga, que es el lado seguro.
- Bajo (re-verificación): en `/io/test/output`, la señal se lee antes que `estado.sensores_pres`. La ventana entre las dos lecturas es de microsegundos y el lazo vuelve a cerrar en el tick siguiente.
- Nota: en esta rama la mediana de presión todavía se alimenta con cada notificación. En `tanda-8`, S1 ya la limitó a tramas AI nuevas (`nueva_muestra`). Al unir, la afirmación "5 tramas AI llenan la mediana" queda exacta. La compuerta de E1 no depende de eso.

**Altos/Críticos abiertos: ninguno.**
