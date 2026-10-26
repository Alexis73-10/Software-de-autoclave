# Tanda 16 — Informe R16 (pendientes de la tanda 14 + VCH + PRG-01 + DEU-01)

Fecha: 26-oct-2026. Sesión sin supervisión (prompt `docs/mis_plans/prompt_claude_code_tanda_16.md`). Fuentes: `decisiones_tanda_16.md` (prevalece), `planeacion_control_vapor_chaqueta.md` (VCH), `planeacion_tanda_14_pendientes.md` (P1–P8, P10).

**Resultado:** tanda unida a `dev` (merge `be70836`). **Sin entrega**: `compilar_entrega.py` no se ejecutó porque su condición (suite en verde) no se cumple por una falla **preexistente** de `dev` (§K). Suite final en `dev`: 8251 recolectadas (base 7922 + 329 nuevas); 8234 pasan en paralelo, 3 fallan solo en paralelo y pasan en serie, 1 falla preexistente.

## 1. Tabla de etapas

| Etapa | Estado | Commits / nota |
|---|---|---|
| A0 | Hecha | rama `tanda-16` desde `dev` f403b87; `cbb96ba` documentos; `4c4f4b9` línea base (7922 recolectadas, 1 falla preexistente) |
| V | Hecha | 4 subagentes de solo lectura (V-01+V-02, V-03, V-04, V-05) |
| F1 | Hecha | `f1dc41e` parámetros de equipo VCH, D-CHQ, DEU-01 |
| F2 | Hecha | `3df6b1a` CIC-15..18, motivos de fase, i18n |
| F3 | Hecha | `7a74963` DebounceAcumulado, AislamientoCamara, `profile.modo_vapor` |
| F4 | Hecha | `41ed517`, `687207c` contratos del estado del ciclo |
| F5 | Hecha | `d26d7cf` `testpaths` |
| P | Hecha | s1 `7f364f1`; s2 `4125106`; s3 `00b0bb5`; s4 `d778624`+`e774062`; s5 `d306606`+`53952d9` |
| I | Hecha | merges `00ec5ae`..`d276e1d` (s4, s3, s1, s2, s5; sin conflictos), `7484757` ajustes, `6554f16` integración VCH §8 |
| R | Hecha | 5 revisores; 0 altos; correcciones en `4fda28b` |
| K | Hecha parcial | unión `be70836`; anomalías `e53a63b`; **entrega no ejecutada** (§K) |
| L | Hecha | 13 worktrees quitados, 65 ramas borradas con `-d`, etiquetas `archivo/*`, `/data/` en `.gitignore` (`d5cdbc8`) |
| Z | Hecha | CLAUDE.md, hoja de banco (bloque H), este informe, índice, push de `tanda-16` |

## 2. Respuestas de V

- **V-01** (función de chaqueta del perfil): no existía. `entrada_requerida` (`installation/profile.py:41`) solo cubre DI de suministro; `salidas_vapor_permitidas` (`:160`) solo generador/caldera; `EquipmentCapabilities.has_full_jacket` (`installation/equipment.py:16`) no lo usaba el ciclo; `io_enabled` del YAML de la instancia lista todo para todos los equipos. Las fases reciben `cap` pero no el perfil (`base_fase.py:28`); el perfil solo lo tiene `CicloState` (`states/ciclo.py:138`). **Creada** `installation/profile.py::modo_vapor(profile, io_enabled=None)`: chaqueta solo con `InstallationProfile` real, `has_full_jacket is True` y `vapor_chaqueta`/`pres_chaqueta` en io_enabled filtrado; si no, cámara.
- **V-02** (cierre de válvulas en FALLO, cancelación y paro): las tres rutas pasan por `ProtocoloFallo.ejecutar()` → `reset_all_outputs()` (ALL_OFF, `protocolo_fallo.py:544`, `set_io.py:296`). Paro: además ALL_OFF en el flanco (`control_loop.py:1159-1179`). Huecos: (a) tolerancia de DI vencida solo apagaba cámara y chaqueta (`ciclo.py:934`) → **corregido** (también generador y caldera); (b) el protocolo no reafirmaba el vapor OFF tras el ACK → **corregido** (`ProtocoloFallo.update()`); (c) sin enlace antes de COM-02 no sale orden de apagado (`control_loop.py:974-986`), (d) `all_off()` sin handshake no envía (`serial_link.py:1059`), (e) la cancelación depende del siguiente tick — **no corregidos** (fuera del alcance de archivos; quedan para una tanda de comunicación).
- **V-03**: programa en `cycles/{factory,user}/*.json` + `catalogo_parametros.py` (`_poner`, `CATALOGO`, `errores_coherencia`, `errores_programa`) + `cycle_manager.migrar_parametros` (C-04.4 con auditoría, SIS-06, `.bak` vía `backend/context.py`); UI genérica `OpcionesParametrosCiclo.qml`. Equipo en `config/global_params.json` + `ConfigManager` (`_validar`, `_incoherencia`, `fijar`) + `PATCH /global_params/{clave}` (técnico/ingeniero, fuera de CICLO, auditoría `param_sistema_cambio`) + UI genérica `OpcionesParametrosEquipo.qml` por `grupo`.
- **V-04**: los dobles usan `estado`/`cap` `MagicMock` y `profile=None` (los simuladores de planta usan `PISO_LAB` real): el modo se decide por `estado.modo_vapor == "chaqueta"` estricto, así ninguna prueba anterior entra a modo chaqueta (D13 sin tocar pruebas). P1 afecta a los programas de usuario del repo (121/9, 134/9, 134,5/9) y a todas las pruebas que los cargan; P6 a `test_t12_c07`/`c03`; P3/P5/P7 sin efecto en aserciones existentes.
- **V-05**: las constantes de presión solo las usaba `catalogo_parametros._evaluar_limites` (400 escrito a mano en `hal/measures/converters.py:299,379`, no tocado); lecturas vivas publicadas en un único punto, `EstadoAutoclave.update` (`core/runtime/status.py:147`); roles en `backend/rutas/programas.py:413` (`PUT /cycle/sensor-roles`, auditoría `ROLES_SENSOR`) y `core/runtime/sensores_ciclo.py` (`verificar_inicio`, llamada por `POST /cycle/start`); NO CONFORME solo en `avisos_ciclo`/ticket (`ciclo.py:680-724`, `ticket_formatter.py`).

## 3. Tabla de propiedad de archivos (etapa P)

Ver `docs/informes/tanda16/estado.md` (sección «Tabla de propiedad»). Un dueño por archivo; la sesión principal se reservó i18n, catálogo de alarmas, motivos, `global_params.json`, `config_manager.py`, `limites_equipo.py`, los módulos F3, `profile.py` y las pruebas de integración.

## 4. Qué se implementó

- **VCH completo:** modo chaqueta/cámara; en modo chaqueta CALENTAMIENTO y ESTERILIZACION actúan sobre `vapor_chaqueta` y `vapor_camara` queda abierta del primer tick de CALENTAMIENTO al fin de ESTERILIZACION; aislamiento VCH-AIS (CIC-15 sostenido, CIC-16 recurrente); `_mantener_chaqueta` no actúa con `controla_vapor_chaqueta`; corte único D-CHQ (375 kPa abs) con CIC-18; F0 y exposición siguen durante el aislamiento.
- **Tanda 14:** P1 (regla de coherencia y programas de 134 °C con 15), P2 (migración con extensión), P3, P4 (NO CONFORME visible con reconocimiento auditado), P5 (`max_reinicios_exposicion`, CIC-17), P6 (`DebounceAcumulado` 5 s / 10 s), P7 (plausibilidad 0–200 °C, −10–450 kPa), P8 (SAF-05, SAF-09 = corte único, excursión con pérdida de lectura). P10 en L.
- **DEU-01:** 4 límites en Parámetros del equipo (submenú Chaqueta), coherencia en `ConfigManager`, `catalogo_parametros` lee los límites vigentes, revalidación de programas al vincular la base y al cambiar un límite.
- **PRG-01:** rechazo al asignar un rol a una sonda no activa (`ROL_SONDA_NO_ACTIVA`) y bloqueo del inicio (`SENSOR_NO_DISPONIBLE` con motivo propio).

## 5. Códigos asignados

| Código | Nivel | Uso |
|---|---|---|
| CIC-15 | ALARMA, bloquea, despeje manual | Aislamiento de cámara sostenido (VCH §4.5) |
| CIC-16 | ALARMA, bloquea, despeje manual | Aislamiento de cámara recurrente (VCH §4.5) |
| CIC-17 | ALARMA, bloquea, despeje manual | Excursión después del tope de reinicios (P5) |
| CIC-18 | AVISO, no bloquea, despeje automático | Chaqueta en el corte de control, modo chaqueta (VCH-CHQ) |
| Motivos | — | `ais_sostenida`, `ais_recurrente`, `est_tope_reinicios` |
| Rechazos API | — | `COHERENCIA_RECUPERACION` (P1), `ROL_SONDA_NO_ACTIVA` (PRG-01), `no_conforme_sin_reconocer` (P4, 409) |
| Bitácora | — | `ciclo_no_conforme_reconocido` |
| Ruta nueva | — | `POST /cycle/acknowledge-no-conforme` |

## 6. Pruebas

- Nuevas (con `req`): `test_t16_f1_parametros_equipo.py`, `test_t16_f3_modulos.py`, `test_t16_f4_contratos.py`, `test_t16_s1_esterilizacion.py`, `test_t16_s2_calentamiento_chaqueta.py`, `test_t16_s2_plausibilidad.py`, `test_t16_s3_ciclo_chaqueta.py`, `test_t16_s3_protocolo_vapor.py`, `test_t16_s4_programas.py`, `test_t16_s5_no_conforme_{backend,salidas,qml}.py`, `test_t16_integracion.py` (VCH §8 puntos 1–9 de punta a punta con fases reales), `test_t16_r_correcciones.py`.
- **Existentes tocadas:**

| Prueba | Cambio | Motivo |
|---|---|---|
| `tests/test_alarmas_catalogo.py` | Ejemplos y nivel de CIC-15..18 agregados a sus tablas (sin cambiar los anteriores) | Extensión obligatoria para registrar códigos nuevos |
| `tests/test_t12_c07_debounce_tiempo_esterilizacion.py:64` | Aserción: ahora FALLO al volver a salir | P6 / D-14.6 (comentario en la prueba) |
| `tests/test_t12_c03_saturacion_esterilizacion.py:62` | Aserción: FALLO a los 5,5 s acumulados | P6 / D-14.6 |
| `tests/test_t12_c04_presion_add.py:46` y `_cycle_alto` (140 °C/0 → 139,5 °C/17) | Aserción y datos | P1 / D-14.1 |
| `tests/test_t12_c05_chaqueta.py` (2 pruebas) | Consigna con 15; 138 °C con 16 | P1 / D-14.1 |
| `tests/test_t12_c10_sin_medicion.py` (2 pruebas) | +60 → +60,5 s; +30 → +31 s | **SAF-05 / P8 (D-14.8)**. DECISIÓN SIN CONFIRMAR: P8 no está en la lista de excepciones de la regla 3, pero SAF-05 cambia ese resultado por definición (el tramo empieza en la última lectura válida) |
| `docs/informes/tanda15/base/{rutas,openapi}.json` (datos de `test_t15_rutas_equivalentes.py`) | Solo se agrega `POST /cycle/acknowledge-no-conforme` | P4 crea la ruta; DECISIÓN SIN CONFIRMAR: se actualiza la foto de la API, no la prueba |

- Ninguna prueba se borró, saltó ni relajó.

## 7. Hallazgos de R y su resolución

| Hallazgo | Sev. | Resolución |
|---|---|---|
| V16-s1-02 / s2-01 / s3-02 — sin suministro (SUM-06) la fase reabría la chaqueta en el mismo tick | Media | Corregido: SUM-06 entra en `inhibir_vapor_chaqueta` en modo chaqueta (`4fda28b`) |
| V16-s3-01 — PRECALENTAMIENTO/SECADO encendían con el corte (pulso por tick) | Media | Corregido: `BaseFase._chaqueta_on` |
| V16-s1-01 — Referencia en el borde llegaba a CIC-17 en segundos | Media | Corregido: el debounce de la Referencia se reinicia al cerrar su excursión |
| V16-s3-03 / s4-01 — bajar un alivio no revalidaba en caliente | Media | Corregido: `PATCH`/reset de un límite llama `revalidar_programas()` |
| V16-s3-04 / s2-03 / s1-04 — pruebas de integración que no probaban lo que decían | Media/baja | Corregido: 6b/6c, F0 con `ControlLoop._acumular_f0`, órdenes en la transición |
| V16-s4-02 — P2 se evalúa con los límites de fábrica antes de leer los del sitio | Media | **Abierto** → anomalía AN-15 (solo afecta sitios con límites distintos; el equipo de pruebas usa los de fábrica) |
| V16-s4-03 / s2-02 — fondo de escala configurable sin atar al transductor (0–400) ni a P7 (450) | Media/baja | **Abierto** → AN-16; decisión de Cristian (D-DEU-1 fijó 100–1000) |
| V16-s1-03 — sin Principal con presión alta no aislaba | Baja | Corregido (ESTERILIZACION y CALENTAMIENTO) |
| V16-s1-05, s4-06 — pruebas permisivas | Baja | Corregido |
| V16-s1-06 — nombres de pruebas viejas («reinicia») | Baja | No se renombran (regla 3); anotado |
| V16-s3-05 — corte y CIC-18 sin histéresis | Baja | Abierto → AN-19 |
| V16-s3-06 — log por tick con límites incoherentes; respaldo con límites a medias; consigna entre corte y alivio | Baja | Log corregido; lo demás abierto (anotado) |
| V16-s3-07 — CICLO aceptaba CICLO_CONFIRMADO sin reconocimiento | Baja | Corregido (defensa en profundidad) |
| V16-s4-04 — consigna + 10 entre el corte y el alivio sin advertencia | Baja | Abierto (decisión de Cristian) |
| V16-s4-05 — límites inválidos vuelven a los de fábrica | Baja | Abierto (no alcanzable por la API) |
| V16-s5-01 — reconocimiento sin sesión | Baja | Abierto → AN-18 (DECISIÓN SIN CONFIRMAR de s5) |
| V16-s5-02 — reimpresión de la app de ajustes sin NO CONFORME | Baja | Corregido |

No hubo hallazgos altos. Suite tras R: 8251 recolectadas, 8235 pasan; 1 falla preexistente; 2 solo en paralelo (pasan en serie).

## 8. K — unión y entrega

1. `git merge --no-ff tanda-16` en `dev` → `be70836`. Suite en `dev`: 8234 pasan, 4 fallan en paralelo; en serie solo queda `tests/test_ver_entrega.py::test_historial_entrada_debajo_de_la_marca`.
2. Esa prueba es **preexistente en `dev`** (falla desde la entrega `1.0.0-alpha.1`, f403b87: exige que `HISTORIAL_VERSIONES.md` no tenga entradas bajo la marca, y la entrega agregó la primera). DECISIÓN SIN CONFIRMAR: la unión se mantiene (no introduce fallas nuevas: `dev` ya fallaba igual). La prueba no se tocó (regla 3).
3. `docs/versiones/anomalias_conocidas_1.0.0-alpha.2.md` en `dev` (`e53a63b`): AN-01..08, AN-10, AN-11 corregidas; VCH-01 (ALTA), VCH-02, AN-14 (DECISIONES SIN CONFIRMAR de P1, P3, P6) y AN-15..19 de la revisión; uso previsto igual que la alpha.1; prueba de humo.
4. **`compilar_entrega.py --con-generador` no se ejecutó**: su verificación previa exige la suite en verde (`verificaciones_previas` → `correr_suite_real`), y la falla preexistente la bloquea. No hay versión, SHA-256 ni comando de push de etiqueta. **Para Cristian:** corregir `test_historial_entrada_debajo_de_la_marca` (que compruebe la inserción bajo la marca sobre un texto sin entradas, no el archivo real) y volver a correr `python tools/entrega/compilar_entrega.py --con-generador` desde `dev` limpio; saldrá la `1.0.0-alpha.2`.

## 9. L — limpieza de git (P10, D-14.10)

- Worktrees de `.claude/worktrees/`: **13 quitados** (sin cambios). **31 se dejaron** (listados): 28 solo tienen `data/mantenimiento_base.json` sin seguimiento (borrar archivos sin seguimiento está prohibido); `agent-a26b3309f9ff1210b` (171 entradas) y `anuncios-voz` (93) con cambios; `agent-a229dc3ec41f75b3f` es una carpeta que ya no es un worktree registrado. `git worktree prune` hecho.
- Ramas: **65 borradas con `-d`** (todas unidas a `dev`). No borradas (unidas, pero en uso por un worktree que se conserva): tanda-10-t10, tanda-10-u10b, tanda-11-e11, tanda-11-r11, tanda-11-s11, tanda-11-u11, tanda-12-e12, tanda-12-j12, tanda-16-s2..s5, tanda-8-d8, -e1, -e2, -l8, -m8, -n8, -r8, -s1, -s2a, -s2b, -u8, -v8b, tanda-9-a9, -b9, -p9, -s9, -x9. Todas con 0 commits sin unir. `tanda-16` se borró con `-d` y se recreó en `71cf5c5` para el push de Z.
- Etiquetas: `archivo/feature/roles-sensor-temperatura` (87fca2f, 16 commits sin unir, 726 detrás de `dev`), `archivo/instalador-setup` (2609644, 1 sin unir, 444 detrás); `archivo/worktree-anuncios-voz` ya existía (786c735). Ninguna de las tres ramas se pudo borrar: están en uso por worktrees (`.worktrees/roles-sensor-temperatura`, `.claude/worktrees/anuncios-voz`, `../_instalador`).
- `main` (commits que no están en `dev`, sin integrar): `3d55cc1` AdvancedDoor (16-may; `advanced_door.py` de `dev` evolucionó mucho después, la última modificación es d41822f de la tanda 8: contenido superado), `d5e602f` audios mp3 de la puerta (**no están en `dev`**: no hay `src/autoclave/audio/`), `0f79cb0` iconos SVG (en `dev`), `5fe9e1c` diseño UI v2 (170 de 171 archivos en `dev`; falta `src/autoclave/ui_qml/assets/textos/es.json`). Los demás son merges de PR.
- Remotas `origin/tanda-*` (las borra Cristian): tanda-2, -3, -4, -5, -6, -7, -8, -9, -10, -11, -12, -13, -15.
- `/data/` completo en `.gitignore` (`d5cdbc8`, prefijo `chore(t16)`: debió ser `fix(t16)`; no se reescribe el historial).

## 10. Evaluación IEC 62304

- **Solicitud de cambio:** tanda 16 = SC de control de vapor por chaqueta (VCH, decisiones D1–D7 de Cristian del 25-oct) + pendientes de la tanda 14 (D-14.1..D-14.10) + PRG-01 + DEU-01 (26-oct). Clasificación Clase C (control de presión/temperatura, fallas, NO CONFORME).
- **Peligros nuevos o actualizados (fichero de gestión de riesgos):**
  - Sobrepresión de cámara en modo chaqueta (mitigación: VCH-AIS, CIC-15/16, fallas de la fase, alivio mecánico).
  - Sobrepresión de chaqueta (corte único D-CHQ 375 kPa, CIC-18, alivio mecánico; AN-19 sin histéresis).
  - `vapor_camara` pegada abierta (aislamiento no actúa: fallas de presión alta, CIC-15, alivio) o cerrada (timeout de calentamiento) — VCH-03.
  - Pérdida del sensor de chaqueta (corte en modo chaqueta; SEN-05 si está vigilado).
  - Sobrepaso por el retardo de la chaqueta (VCH-01, ALTA: reajuste en banco antes de liberar).
  - SAF: falla no confirmada por ruido (P6), Referencia fría falla de más (P3), lectura fuera de rango (P7), exposición sin tope (P5).
  - NO CONFORME: liberación de una carga no verificada (P4: franja, reconocimiento auditado, marcas; AN-18 sin sesión).
  - DEU-01: límites del sitio mal configurados (coherencia en ConfigManager; AN-15, AN-16 abiertos).
  - PRG-01: rol de sensor sobre una sonda inexistente.
- **Regresión:** suite completa (8251) con la base intacta salvo las pruebas listadas en §6; modo cámara idéntico por diseño (D11/D13) y cubierto por las pruebas anteriores sin cambios; pruebas de integración de punta a punta de VCH §8; verificación en banco pendiente (hoja de banco, bloque H).

## 11. DECISIONES SIN CONFIRMAR

1. Límites DEU-01 y parámetros VCH en el submenú «Chaqueta» (un submenú nuevo rompía pruebas que fijan la pantalla).
2. `modo_vapor`: cámara ante cualquier duda (sin perfil, clase sin chaqueta, io_enabled ilegible).
3. Límites de presión incoherentes al leer → rigen los de fábrica.
4. P1: margen 0,3 K e histéresis 0,3 K; mínimo redondeado hacia arriba a 0,1 kPa en el mensaje y a 0,5 kPa en la migración.
5. P2 extendida a todo programa que incumpla P1 (no solo brecha 0,3), con la misma salvaguarda; también mira el techo de cámara y el máximo de 30 kPa; solo al cargar desde archivo; los JSON de usuario del repo se actualizaron (121 → 11 kPa; 134 y 134,5 → 15 kPa).
6. P3: `brecha_error_temperatura` inválida → 0 (criterio anterior).
7. P6: `en_conteo` = condición activa en el último tick (un tiempo acumulado sin condición activa no bloquea completar); 50 % del tiempo fuera en 10 s ya confirma.
8. P5: `max_reinicios_exposicion` con decimales se trunca.
9. Sin lectura en modo chaqueta con aislamiento en curso: la cámara no se reabre.
10. Corte de chaqueta: error al evaluarlo → corte activo en los dos modos; en modo cámara la falta de lectura no es corte (ya apaga A-5).
11. V-02: reafirmación de vapor OFF en cada `ProtocoloFallo.update()`; DI vencida apaga también generador y caldera.
12. P7: rangos como constantes en `status.py` (prueba de coincidencia con `CALIBRACION_PLAUSIBLE`); `temp_drenaje` también 0–200.
13. P4: reconocimiento sin sesión (auditado sin usuario); exigido también si el ciclo NO CONFORME terminó en fallo o cancelado; «NO CONFORME» en rojo en la lista del historial.
14. PRG-01 (b) reutiliza `SENSOR_NO_DISPONIBLE` con motivo propio.
15. Revalidación de programas al vincular la base sin intentar el `.bak`.
16. SIS-06 conserva su texto («kPa», «sobre el máximo»): la prueba existente lo fija (AN-17).
17. Foto de la API de la tanda 15 actualizada con la ruta nueva; `test_t12_c10` actualizado por SAF-05.
18. K: unión a `dev` mantenida con la falla preexistente; entrega no ejecutada.

## 12. Notas de proceso

- Los subagentes en worktree debieron correr las pruebas con `PYTHONPATH=<worktree>\src`: el paquete instalado apunta al checkout principal. Se les avisó a mitad de la etapa P y repitieron sus corridas.
- La hoja de banco: el bloque H se agregó a `hoja_pruebas_banco/pruebas.py` y a mano al `.md`; el `.md` tiene bloques (E9, N11, T12 y filas extra) que no están en `pruebas.py`, por eso no se regeneró (tampoco el `.html`). Reconciliar antes de regenerar.
