# CLAUDE.md

Guía de contexto para trabajar en este repositorio (software de control de autoclave, Especifika S.A.S.).

## Estructura del repositorio (tanda 15, reorganización sin cambio funcional)

- `src/autoclave/auth/`: roles (`roles.py`) y validación de usuario (`validacion_usuario.py`), sin dependencias de interfaz; los usan el backend, el simulador y las UI.
- `src/autoclave/cliente/`: cliente HTTP del backend para las interfaces (`backend_client.py`, `session_manager.py`, `ui_service_backend.py`; antes `ui/service_ui/`).
- `src/autoclave/backend/`: `server.py` (solo `app`, ciclo de vida, compuerta de arranque, manejadores y registro de routers; punto de entrada `autoclave.backend.server:app`), `dependencias.py` (contexto, tokens, auditoría, `requiere_rol`, `guard_estado`) y `rutas/<área>.py`, un `APIRouter` por área, más `rutas/_comun.py` para lo compartido. `rutas/*` nunca importa `server`; `server_reasignacion.py` sigue leyendo sus nombres como `srv.<nombre>`. El estado del modo prueba vive en `rutas/io.py`.
- `packaging/`: los 4 `.spec` de PyInstaller; se compilan desde la raíz: `pyinstaller --noconfirm packaging\Autoclave.spec`.
- `tests/helpers/` (dobles y ayudantes importados por las pruebas; `backend_doble` trae `modulo_backend`/`fijar_en_backend`/`parchear_en_backend` para parchear el backend partido) y `tests/banco/` (bancos y capturas que no son pruebas automáticas). Convención en `tests/README.md`; marcador `req(id)` registrado en `pyproject.toml`.
- `tests/test_arquitectura_capas.py` impide que backend, auth, cliente, simulador, core, services, state_machine, protocols, devices o hal importen la UI; `tests/test_t15_rutas_equivalentes.py` fija rutas y OpenAPI contra `docs/informes/tanda15/base/`.
- `docs/README.md`: qué va en cada carpeta de `docs/` (`arquitectura/`, `referencia/`, `diseno/`, `mis_plans/`, `superpowers/`, `informes/tandaNN/`...).
- Versión (etapa VER, 25-oct): fuente única `src/autoclave/_version.py` (`VERSION_SEMVER` = `1.0.0-alpha.N` de la última entrega, `__version__` en PEP 440, que lee `pyproject.toml`); nadie más escribe la versión ni usa `importlib.metadata` para ella (`tests/test_ver_version.py`). Lo mostrado sale de `version_completa()`. Los 3 `.spec` del autoclave generan `src/autoclave/_build_info.py` (no versionado) con `tools/entrega/info_compilacion.py`. Las entregas se hacen solo con `python tools/entrega/compilar_entrega.py` desde `dev` limpio (N = mayor etiqueta `v1.0.0-alpha.K` + 1; etapa K de las tandas: unir la rama a `dev` y correrlo); historial en `docs/versiones/HISTORIAL_VERSIONES.md`.

## Herramientas

- Trabajos sin supervisión: Cristian los lanza con `powershell -ExecutionPolicy Bypass -File tools\tandas\lanzar_prompt.ps1 -Nombre <nombre>` (prompt en `docs/mis_plans/prompt_claude_code_<nombre>.md`; logs en `docs/informes/<nombre>/lanzador.log` y `sesion_NN_*.log`), que relanza la sesión cuando se restablece el límite de uso. Por eso el trabajo lleva `docs/informes/<nombre>/estado.md` (paso → Hecho/Pendiente, último commit) al día después de cada commit y, al reanudar, sigue desde el primer paso pendiente.
- **Convención `CERRADO.txt`:** el último acto de un trabajo así es escribir `docs/informes/<nombre>/CERRADO.txt` (fecha, commit del merge, resultado de la suite); sin ese archivo el lanzador vuelve a lanzar la sesión. Si el trabajo se detiene por un bloqueo que necesita a Cristian, se escribe igual, con `BLOQUEADO:` y el motivo en la primera línea.

## Máquina de estados del ciclo

El ciclo de esterilización se ejecuta como una secuencia de "fases", cada una en su propio módulo bajo `src/autoclave/state_machine/cycle_phases/`. Todas heredan de `BaseFase` (`base_fase.py`) y devuelven un `FaseResult` (`EN_CURSO` / `COMPLETADO` / `FALLO`) desde `update()`, llamado una vez por tick del loop de control.

Convenciones compartidas por las fases:
- Parámetros del ciclo se leen con `self.cycle.get_param(seccion, nombre)`, definidos en los perfiles JSON de `src/autoclave/cycles/{factory,user}/*.json` bajo `parameters.<seccion>`.
- Lecturas de sensores vía `self._temp_camara()` / `self._pres_camara()` (pueden ser `None` — hay que contemplarlo).
- `p_saturacion_kpa(T)` (`autoclave.core.runtime.steam`) da la presión de saturación de vapor para una temperatura en °C; `t_saturacion_c(P)` (tanda 12) es su inversa. Desde la tanda 13 (VAP-01) ambas usan **IAPWS-IF97 región 4** (ecuaciones 30 y 31; antes una ecuación de Antoine que daba ≈2 kPa menos a 134 °C): `Psat(121) = 205.04`, `Psat(134) = 304.20` kPa. Validez 0.01–373.946 °C (≈0.6117–22064 kPa), sin recortar al rango de trabajo; fuera de rango, `P<=0` o entrada no finita → `ValueError`. Presión siempre en kPa absolutos; Psat/Tsat solo con este módulo.
- Temporizador de dos estados (abre `t_on` seg, cierra `t_off` seg, repite; `t_off<=0` → enclavada abierta, `t_on<=0` → enclavada cerrada) es el patrón estándar para escapes (`descompresion_lenta`/`descompresion_rapida`) y para PWM de vapor. Ver `_tick_dos_estados` en `calentamiento.py`/`esterilizacion.py`.
- Condiciones de falla usan debounce antes de disparar `FaseResult.FALLO`. Desde la tanda 12 (C-07.2) ESTERILIZACION usa **debounce por tiempo**: la condición debe sostenerse `_DEBOUNCE_FALLA_S = 5.0` s continuos (monotonic, `_sostenida()`; una lectura dentro de rango reinicia el conteo), y la fase no completa mientras haya una falla en conteo (V12, SAF-01). Las demás fases siguen con 3 lecturas consecutivas (`_DEBOUNCE_LECTURAS`).
- Al entrar en `FALLO`, se apagan todas las salidas de la fase y se registra `self.estado.motivo_fallo`.
- Todo temporizador de proceso (timers de fase, timeouts, debounce, hold) usa `time.monotonic()`, nunca `time.time()` — un salto del reloj de pared (ajuste manual, NTP futuro) no debe alterar la duración medida. `time.time()`/`datetime.now()` quedan reservados para sellos de tiempo de registros/auditoría (ver §11.3 de `docs/mis_plans/planeacion_ui_dual_pantalla.md`). Estos timers son atributos en memoria por instancia de fase, no persisten entre reinicios.

Secuencia actual (PURGA eliminada el 2026-10-01 — todos los perfiles la tenían en `tiempo_purga=0`, nunca corría):

```
PRECALENTAMIENTO → PREVACIO → CALENTAMIENTO → ESTERILIZACION → DESCOMPRESION → SECADO
```

Fases y su estado de diseño:
- `precalentamiento.py` — sostiene presión de chaqueta.
- `prevacio.py` — pulsos de vacío/vapor (hasta 4 tipos configurables).
- `calentamiento.py` — **rediseñado**: RAMPA (control continuo de `vapor_camara` vía duty cycle — el mínimo entre tres términos: un límite de pendiente `tasa_calentamiento`/`tasa_presion`, una aproximación lineal a `factor_calentamiento` a medida que `temp`/`pres` se acercan a los objetivos fijos, y un corte si la temperatura supera `T_obj - 3 K` (`_MARGEN_CALIDAD_VAPOR_K`, tanda 12 C-09; antes el 97 % del objetivo) sin que la presión llegue a `Psat(T) - 2 kPa` (sin `presion_add`) — más un techo independiente de presión `Psat(T_obj) + presion_add_calentamiento` (tanda 12 C-01; antes 2×`presion_add`) como resguardo — ver `docs/superpowers/specs/2026-08-05-control-continuo-rampa-calentamiento-design.md`) → ESTABLE_PREESTERILIZACION. ESTABLE_PREESTERILIZACION exige una ventana continua de estabilidad (con reinicio ante overshoot) antes de entregar control a ESTERILIZACION — fusiona lo que antes era la fase separada `EstabilizacionFase` (ver `docs/superpowers/specs/2026-08-04-fusion-calentamiento-estabilizacion-design.md`). El término de proximidad tiene un piso `duty_estable` (`1 - factor_calentamiento/100`) que antes se sostenía indefinidamente en cuanto `temp`/`pres` superaban el objetivo, sin importar cuánto — bug real (ciclo 79, 2026-08-06): con `t_obj=134.0` y la cámara ya en 136.7°C, el duty seguía en 0.5 en vez de ir a 0, y el control se veía "sosteniendo" una temperatura muy por encima del setpoint con pulsos de vapor. Corregido escalando ese piso hacia 0 a medida que el sobrepaso crece, llegando a 0 a partir de `rango_calentamiento_temp` °C (temperatura) / `rango_calentamiento_pres` kPa (presión) pasado el objetivo (función `_duty_por_sobrepaso`). Esos dos parámetros (clase "diferencia", defecto 2.0) reemplazan desde la tanda 7 (R1-P3) al antiguo `rango_calentamiento`, que se usaba a la vez como banda de °C y de kPa; un programa viejo se migra al cargarlo (`migrar_parametros` en `cycle_manager.py`, copia el valor a los dos).
  Tanda 12 (24-oct): `presion_add_calentamiento` es **solo techo** (C-01): el objetivo de presión es `p_obj = Psat(T_obj)`; entrada a ESTABLE_PREESTERILIZACION con `T >= T_obj` y `P >= p_obj - 2` (`_TOLERANCIA_PSAT_KPA`); banda de sostenimiento `T_obj <= T <= T_obj + rango_temp_estabilizacion` y `p_obj - 2 <= P <= Psat(T_obj) + presion_add`. Con carga sólida (`globals.tipo_carga != "liquido"`) la banda exige además coherencia T–P `|Tsat(P) - T_principal| <= 1.0 K` (`_COHERENCIA_TP_K`, C-02): fuera de coherencia reinicia la ventana y arma el timeout de recuperación. En la ventana, una Referencia sin lectura (None, no finita o 0) no bloquea (C-13.7b; CicloState marca el ciclo NO CONFORME); las que leen deben estar en consigna.
- `esterilizacion.py` — **rediseñado**, ver detalle abajo.
- `descompresion.py`, `secado.py`, `valvula_reposo.py`, `protocolo_fallo.py` — sin cambios recientes.

---

## F0 (letalidad acumulada) — nueva funcionalidad opcional (2026-08-06)

Ver plan completo en `docs/mis_plans/planeacion_f0.md`. Adición, no reemplazo: activable por ciclo vía `globals.F0` (ya existía como flag sin uso); con `F0=false` el comportamiento de `ESTERILIZACION` es exactamente el de antes.

`ControlLoop._acumular_f0()` (nuevo paso en `_tick()`, no depende del orden respecto a `state_machine.update()` porque solo lee `estado.fase_ciclo` ya publicado) acumula en `estado.f0_acumulado` mientras `estado.get_machine_state() == CICLO`, `estado.fase_ciclo` esté en `{"CALENTAMIENTO", "ESTABILIZACION", "ESTERILIZACION"}` y `globals.F0` sea `true`. `ESTABILIZACION` nunca hace match hoy (fusionada dentro de `CalentamientoFase`, que conserva `name = "CALENTAMIENTO"` durante todo su tramo interno, incluida la ventana de estabilidad) — se deja en el conjunto por si una futura reversión de esa fusión la reintroduce. `T_ref` es `temp_camara`, o `min(temp_camara, temp_2_camara)` si `cap.has_liquid_sensor` y hay lectura del segundo sensor (degrada a solo `temp_camara` si no la hay). `dt_min` es el tiempo real transcurrido desde el tick anterior (no el `interval` nominal), vía `ControlLoop._f0_ultimo_tick`. Ese timestamp se resetea a `None` cada vez que alguna condición no se cumple — como PRE_VACIO nunca acumula y siempre corre antes de CALENTAMIENTO, esto ya cubre el reset entre ciclos sin que `CicloState` necesite conocer a `ControlLoop`; `CicloState.reset()` solo pone `estado.f0_acumulado = 0.0`. La fórmula pura vive en `core/runtime/letalidad.py` (`calcular_incremento_f0`, z=10 y 121.1°C fijos en código).

En `EsterilizacionFase`, con `F0=true` la finalización exitosa exige tiempo Y F0 (`estado.f0_acumulado >= globals.F0_objetivo`); el criterio de solo-tiempo original se mantiene intacto si `F0=false`. Timeout de seguridad nuevo, armado solo si `F0=true`: `2 × tiempo_esterilizacion`, FALLO `ESTERILIZACION_TIMEOUT_F0` (mensaje de texto plano vía `self._fallo(...)`, que en este código nunca toma `alarm_id` — no una alarma separada). `globals.F0_objetivo` (min, defecto 12, rango 0-60) se agregó a los 5 perfiles JSON existentes. El footer del ticket (`format_footer`) agrega `F0 total: {valor:.1f} min` solo si el ciclo tenía F0 activo.

---

## PREPARADO / PREPARACION — separación válvula / alarma / gate (2026-08-06)

El control de presión de chaqueta (`presion_chaqueta`/`rango_presion_chaqueta`) y temperatura de drenaje (`temp_segura_drenaje`/`rango_temp_drenaje`, nuevo) en `preparado.py` y `preparacion.py` usaba un único umbral (borde de la banda `objetivo±rango`, o techo único en drenaje) tanto para accionar la válvula como para disparar la alarma bloqueante y decidir si el equipo está "listo". Esto hacía que la alarma bloqueante (`CHAQUETA_FRIA`, `TEMP_DRENAJE_ALTA`) disparara casi en cada arranque en frío, porque la válvula no reaccionaba hasta que ya se había cruzado el borde tolerado.

Separado en `control_banda.py` (`evaluar_banda()`): la válvula reacciona al **objetivo** exacto, sin tolerancia (chaqueta: ON si `presión < objetivo`; drenaje: ON si `temp > objetivo`, sin cambios respecto al drenaje anterior). La alarma bloqueante y el gate de listo/inicio de ciclo siguen usando la **banda** `objetivo±rango`, sin cambiar esos umbrales — solo se separan de la válvula. Drenaje es un caso especial: `temp_segura_drenaje` es un techo de seguridad de un solo lado (no un objetivo — no existe calefactor de drenaje, un drenaje frío siempre es seguro), así que a diferencia de chaqueta, tanto la alarma bloqueante como el gate de listo/inicio para drenaje solo miran el lado alto de la banda (`fuera_por_encima`) — el lado bajo no participa de ninguno de los dos, para no bloquear el arranque en frío.

`control_banda.py` también expone `ConfirmadorApagado`: exige 3 ticks consecutivos de "debe estar apagado" antes de cortar `vapor_chaqueta`, `agua_intercambiador` o `aire_admosferico_camara` — el encendido sigue siendo inmediato. Necesario porque, al mover el umbral de encendido al objetivo exacto (sin histéresis), es más fácil que la válvula oscile justo en ese punto.

Ver spec: `docs/superpowers/specs/2026-08-06-control-banda-objetivo-alarma-gate-design.md`.

---

## CHAQUETA EN CICLO — consigna acoplada al programa (tanda 12, 24-oct)

`CicloState._mantener_chaqueta` (C-05) ya no usa `globals.presion_chaqueta`/`rango_presion_chaqueta` durante el CICLO (esos dos siguen rigiendo PREPARACION/PREPARADO vía `control_banda.py`, sin cambios). Consigna = `max(Psat(T_est + delta_temp_chaqueta), Psat(T_est) + presion_add_esterilizacion + margen_flujo_chaqueta)` (`catalogo_parametros.consigna_chaqueta`; `globals.delta_temp_chaqueta` 1.5 K, 0–5; `globals.margen_flujo_chaqueta` 15 kPa, 0–40). Banda fija ±10 kPa (`_BANDA_CHAQUETA_KPA`): ON si `P < consigna - 10`, OFF si `P > consigna + 10`, sin cambio dentro. Ejemplo: 134 °C/9 → ≈328.2 kPa (tanda 13, IF97; con la fórmula anterior 326.3). Se conserva: secado excluido, enfriamiento modos 4/5 → OFF, sin dato → OFF, SUM-06. La consigna y las advertencias del programa se registran en el log al iniciar el ciclo.

Límites físicos (constantes en `catalogo_parametros.py`, una sola fuente; deuda DEU-01: deberían venir del perfil o de Parámetros del equipo): fondo de escala 400, suministro 350 (40 psig + 74.6 kPa de atmósfera en Bogotá), alivio de cámara y de chaqueta 385 kPa abs. Al guardar y al cargar (`errores_coherencia`/`errores_programa`): se **rechaza** `Psat(T)+presion_add >= 385` (calentamiento y esterilización), `consigna + 10 >= 385` y `presion_chaqueta + rango_presion_chaqueta >= 385`; por encima de 350 solo **advertencia** no bloqueante (la válvula quedará abierta en ese tramo). `presion_add_*` máximo 30 kPa. Migración correctiva (C-04.4): un programa instalado con `presion_add_* > 30` baja a 9 al cargar, con fila de auditoría `param_ciclo_cambio` (origen "migración tanda 12"), aviso no bloqueante SIS-06 (bandeja de Preciclo y campana) y el JSON de usuario reescrito con `.bak`.

---

## APERTURA AUTOMÁTICA DE PUERTA AL FINALIZAR EL CICLO (2026-08-06)

La sección `finalizacion` de cada perfil JSON de ciclo trae 4 parámetros (`tiempo_espera_apertura`, `temp_max_apertura`, `timeout_temperatura`, `apertura_automatica`) implementados en `CicloState._mantener_apertura_automatica()`. Cuando el ciclo termina en `COMPLETADO` y `apertura_automatica=true`, el equipo abre solo la puerta de descarga (`"Puerta 2"` si existe, si no `"Puerta 1"`) y confirma el ciclo (`CICLO_CONFIRMADO`) sin esperar al operador, en vez del flujo manual normal (botón CONFIRMAR + apertura manual). No aplica a `FALLO`/`CANCELADO`/emergencia.

Secuencia: espera fija `tiempo_espera_apertura` segundos → espera a que `temp_camara` Y `pres_camara` estén en condición segura (mismo criterio fail-closed que el botón CONFIRMAR manual — sensor ausente nunca habilita nada; `temp_max_apertura` del ciclo se recorta al tope global si este es menor, para que una mala configuración por sitio no reproduzca el problema de abajo en silencio) → confirma solo cuando el **estado observado** de la puerta (`ServicioPuertas.get_status`) muestra `ABRIENDO`/`ABIERTO` — no basta con que `request_open()` devuelva éxito, porque eso solo significa que el comando se despachó (una puerta `SimpleDoor` no tiene actuador, y `AdvancedDoor.cmd_abrir()` se autocancela en silencio si el bloqueo mecánico está activo). Mientras la puerta no se mueva, reintenta cada 5 segundos y avisa una sola vez por alarma no bloqueante (`APERTURA_AUTOMATICA_DENEGADA`) si la denegación supera 60 segundos — sigue esperando indefinidamente, igual que el aviso de timeout de temperatura (`TIMEOUT_APERTURA_AUTOMATICA`).

Los perfiles `factory/*.json` traen `apertura_automatica=false` por defecto; los `user/*.json` también, hasta validar la función en campo por sitio.

Ver spec: `docs/superpowers/specs/2026-08-06-apertura-automatica-puerta-design.md` (incluye el addendum del 2026-08-06 con el detalle de estas 3 correcciones de seguridad).

---

## ESTERILIZACION — diseño (rediseño 2026-07-28)

Ver plan completo en `docs/mis_plans/planeacion_fase_esterilizacion.md`. Reemplazo total del `esterilizacion.py` anterior, que fallaba sin tolerancia inferior en temperatura/presión (bug `ESTERILIZACION_PRES_BAJA`: evaluaba la presión contra `P_sat(T_actual)` en vez de `P_sat(temperatura_esterilizacion)` fija).

### Objetivo
Sostener la cámara en vapor saturado a `temperatura_esterilizacion` durante `tiempo_esterilizacion` minutos — la fase que efectivamente esteriliza. No hay tramo de aproximación: viene de CALENTAMIENTO ya en condición de vapor saturado.

### Máquina de estados interna (bidireccional; desde la tanda 12 con histéresis de salida, ver "Cambios de la tanda 12")

```
RECUPERACION            T < temperatura_esterilizacion + brecha_segura_temperatura
                        O P < P_sat(temperatura_esterilizacion) - brecha_segura_presion
  vapor_camara ON continuo (sin techo de control)
       ↕ (evaluado en cada tick, entrada inmediata; salida con histéresis desde la tanda 12 (C-08))
PWM_ACTIVO               T >= temperatura_esterilizacion + brecha_segura_temperatura
                        Y P >= P_sat(temperatura_esterilizacion) - brecha_segura_presion
  vapor_camara en PWM dentro de banda fija [P_sat(T_actual)-2, P_sat(T_actual)+1] kPa:
    P < banda baja  → ON forzado
    P > banda alta  → OFF forzado
    dentro de banda → duty cycle (factor_esterilizacion % OFF de intervalo_segmentos_ester)
  Techo independiente: P >= P_control_max = P_sat(temperatura_esterilizacion) + presion_add_esterilizacion
    → OFF forzado sin importar la banda local (evita que la banda, que sigue a T_actual, arrastre
      la presión hasta el umbral real de falla rango_presion_ester)
```

El disparador por presión (`brecha_segura_presion`, agregado 2026-08-04) cubre un caso visto en producción: la temperatura se mantiene igual o por encima del setpoint mientras la presión sola cae de forma sostenida (fuga continua de `descompresion_lenta`, que corre enclavada abierta durante toda la fase, más rápido de lo que el duty cycle de PWM_ACTIVO alcanza a compensar). Antes de este cambio, RECUPERACION solo miraba temperatura y nunca se activaba en ese escenario — la presión seguía cayendo bajo el techo de PWM_ACTIVO hasta disparar `FALLO_PRES_BAJA` sin que el control pasara nunca a modo agresivo (sin techo).

Debe cumplirse `brecha_segura_presion < brecha_error_presion` (no `>`, a diferencia de temperatura) para que RECUPERACION dispare antes que el FALLO. A diferencia de temperatura — donde el umbral de RECUPERACION suma (`temp < t_est + brecha_seg`, queda por *encima* del setpoint, del lado opuesto al umbral de falla que resta) — en presión ambos umbrales restan del mismo punto de referencia (`P_sat(t_est) - brecha_segura_presion` y `P_sat(t_est) - brecha_error_presion`), así que la relación queda invertida: el valor de `brecha_segura_presion` debe ser *menor* para que su umbral quede más cerca del setpoint que el de falla. Bug real encontrado el 2026-08-06 con el valor por defecto original (6.0 > 2.0): una presión sostenida dentro del hueco entre ambos umbrales (ej. 3 kPa por debajo del setpoint) nunca activaba RECUPERACION y terminaba en `FALLO_PRES_BAJA` por el debounce sin que el control pasara nunca a modo agresivo — visible en campo como pulsos de PWM que se alargaban y se acercaban demasiado a la presión de falla antes de recuperar. Corregido bajando `brecha_segura_presion` a 1.5 kPa en los 4 perfiles.

En paralelo, desde el primer tick e independientes entre sí:
- `descompresion_lenta` / `descompresion_rapida` — temporizador de dos estados estándar (`escape_lento_on_ester`/`off_ester`, `escape_rapido_on_ester`/`off_ester`).
- Timer de finalización: fijado en inicialización (`t_inicio + tiempo_esterilizacion*60`), corre sin pausa ni reinicio, **única** condición de éxito (no depende de temperatura/presión ni del tramo activo).
- Chequeo de fallas, con debounce de 5 s continuos (tanda 12, C-07.2; antes 3 lecturas), **siempre contra `temperatura_esterilizacion` fija** (nunca `T_actual`):
  - Temp alta: `T > t_est + rango_temperatura_ester`
  - Temp baja: `T < t_est - brecha_error_temperatura`
  - Pres alta: `P > P_sat(t_est) + rango_presion_ester`
  - Pres baja: `P < P_sat(t_est) - brecha_error_presion`

### Parámetros (sección `esterilizacion` de los perfiles JSON)

| Nombre en código | Unidad | Defecto | Rol |
|---|---|---|---|
| `escape_lento_on_ester` / `escape_lento_off_ester` | seg | 1 / 0 | Escape lento (0 en off = enclavada abierta) |
| `escape_rapido_on_ester` / `escape_rapido_off_ester` | seg | 0 / 400 | Escape rápido (0 en on = enclavada cerrada) |
| `temperatura_esterilizacion` | °C | 134 | Referencia fija de todo el control y las fallas |
| `tiempo_esterilizacion` | min | 3.5 | Duración fija del conteo, única condición de éxito |
| `factor_esterilizacion` | % | 70 | % OFF del PWM dentro de banda |
| `presion_add_esterilizacion` | kPa | 11 | Define `P_control_max` (techo de control, no falla) |
| `intervalo_segmentos_ester` | seg | 3 | Periodo del ciclo PWM |
| `rango_temperatura_ester` | °C | 3 | Umbral de falla temp alta |
| `rango_presion_ester` | kPa | 30 | Umbral de falla pres alta |
| `brecha_segura_temperatura` | °C | 1.0 (tanda 12, C-07.1; antes 0.3) | Umbral de entrada a RECUPERACION (temperatura); la salida suma `_HIST_RECUP_TEMP_K` = 0.3 |
| `brecha_segura_presion` | kPa | 1.5 | Umbral bidireccional RECUPERACION↔PWM_ACTIVO (presión) — debe ser MENOR que `brecha_error_presion` (ver texto arriba, al revés que temperatura) |
| `brecha_error_temperatura` | °C | 0.1 | Umbral de falla temp baja |
| `brecha_error_presion` | kPa | 2 | Umbral de falla pres baja |
| `timeout_excursion_referencia` | min | 5 (int, 1–30) | Tanda 12 (C-13.4): tiempo máximo de una excursión de Referencia sin volver a la banda → FALLO CIC-14 |

Eliminados (semántica antigua, sin tolerancia inferior): `temperatura_add_esterilizacion`, `temperatura_error_esterilizacion`, `rango_presion_esterilizacion`, `presion_error_esterilizacion`. El parámetro `Compruebe RTC` del Excel se descarta explícitamente, no forma parte del código.

### UI
La pestaña "Esterilización" de `params_ciclo.py` (PySide6) no filtra claves (`filter_keys=None`) — renderiza automáticamente todo lo que exista en `parameters.esterilizacion` del JSON, así que agregar/quitar parámetros ahí no requiere tocar el código de la UI.

### Sin medición válida (tanda 12, C-10 — reemplaza el antiguo "riesgo aceptado")
CicloState §4 (vigilancia SENSOR_AUSENTE) corre antes de `fase.update()` en el mismo tick: Principal sin lectura → FALLO SEN-02; presión sin lectura → su código propio (SEN-04), sin que ESTERILIZACION cuente ese tick. Defensa propia de la fase: con `temp` o `pres` en `None`, `vapor_camara` OFF (V12, SAF-03) y, al volver la lectura, el fin de exposición se corre el tramo sin datos (sin sumar a `pausa_total_s` de CIC-11).

### Cambios de la tanda 12 (24-oct) en ESTERILIZACION
Ver `docs/mis_plans/decisiones_tanda_12.md` e informes `docs/informes/tanda12/E12_esterilizacion.md` y `V12_revision_seguridad.md`.
- **C-08 histéresis**: entrada a RECUPERACION igual que antes (inmediata); salida a PWM_ACTIVO solo con `T >= t_est + brecha_segura_temperatura + 0.3` (`_HIST_RECUP_TEMP_K`) **y** `P >= P_sat(t_est) - brecha_segura_presion + 1.0` (`_HIST_RECUP_PRES_KPA`). En RECUPERACION también rige el techo `P_control_max` (C-08.3), con histéresis de 2 kPa (`_HIST_TECHO_KPA`, DECISIÓN SIN CONFIRMAR): OFF al llegar al techo y OFF hasta `P < P_control_max - 2`. Ojo: a 134 °C con `presion_add_esterilizacion` 9–11, `Tsat(P_control_max)` ≈ 135.0–135.2 °C < 135.3 °C (sigue igual con IF97, tanda 13: techo 313.2 kPa a 134 °C/9), así que en vapor saturado la fase queda en RECUPERACION pegada al techo y nunca pasa a PWM (pregunta abierta para Cristian).
- **C-03 saturación (solo sólidos)**: `dT = Tsat(P) - T_principal`; `dT > +2 K` 5 s → FALLO CIC-12 (aire / no condensables); `dT < -2 K` 5 s → FALLO CIC-13 (vapor sobrecalentado o falla de la sonda). `_UMBRAL_SATURACION_K = 2.0`.
- **C-13 Referencias**: banda `[t_est - brecha_error_temperatura, t_est + rango_temperatura_ester]` por Referencia con lectura; excursión confirmada a los 5 s → exposición detenida; al volver, el conteo se reinicia desde cero (`_timer_fin = now + tiempo`); F0 no se reinicia ni cambia su timeout 2×tiempo. Sin retorno en `timeout_excursion_referencia` → FALLO CIC-14. No se completa con una Referencia fuera de banda aunque la excursión no esté confirmada. Cada excursión va al ticket (`ticket_ciclo.aviso_excursion[_alta]`: sensor, duración, mínima/máxima). CIC-09 sigue una vez por sensor. La fase publica `estado.exposicion_restante_s`, que usa `GET /cycle/current/progress`.
- **C-13.7b Referencia sin lectura**: el ciclo continúa; CicloState activa SEN-11 (aviso no bloqueante, despeje manual) y marca el ciclo **NO CONFORME** (bandera `_no_conforme` + línea `ticket_ciclo.no_conforme_referencia` en `estado.avisos_ciclo`, que llega al ticket y al registro aunque la Referencia vuelva a leer). Un ciclo NO CONFORME no usa apertura automática. La marca hoy no se ve en la pantalla final (V12 SAF-02, pregunta abierta). Principal o presión sin lectura → FALLO como antes.

### Pendiente compartido con CALENTAMIENTO
Sensor de líquido secundario (`temp_camara_2`/`has_liquid_sensor`) para configuraciones de dos puertas — aplazado en ambas fases hasta un levantamiento aparte.
