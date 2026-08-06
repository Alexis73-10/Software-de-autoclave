# CLAUDE.md

Guía de contexto para trabajar en este repositorio (software de control de autoclave, Especifika S.A.S.).

## Máquina de estados del ciclo

El ciclo de esterilización se ejecuta como una secuencia de "fases", cada una en su propio módulo bajo `src/autoclave/state_machine/cycle_phases/`. Todas heredan de `BaseFase` (`base_fase.py`) y devuelven un `FaseResult` (`EN_CURSO` / `COMPLETADO` / `FALLO`) desde `update()`, llamado una vez por tick del loop de control.

Convenciones compartidas por las fases:
- Parámetros del ciclo se leen con `self.cycle.get_param(seccion, nombre)`, definidos en los perfiles JSON de `src/autoclave/cycles/{factory,user}/*.json` bajo `parameters.<seccion>`.
- Lecturas de sensores vía `self._temp_camara()` / `self._pres_camara()` (pueden ser `None` — hay que contemplarlo).
- `p_saturacion_kpa(T)` (`autoclave.core.runtime.steam`) da la presión de saturación de vapor para una temperatura en °C.
- Temporizador de dos estados (abre `t_on` seg, cierra `t_off` seg, repite; `t_off<=0` → enclavada abierta, `t_on<=0` → enclavada cerrada) es el patrón estándar para escapes (`descompresion_lenta`/`descompresion_rapida`) y para PWM de vapor. Ver `_tick_dos_estados` en `calentamiento.py`/`esterilizacion.py`.
- Condiciones de falla usan debounce de 3 lecturas consecutivas (constante `_DEBOUNCE_LECTURAS`) antes de disparar `FaseResult.FALLO`.
- Al entrar en `FALLO`, se apagan todas las salidas de la fase y se registra `self.estado.motivo_fallo`.

Secuencia actual (sin cambios de orquestación):

```
PRECALENTAMIENTO → PURGA → PREVACIO → CALENTAMIENTO → ESTERILIZACION → (descompresión / secado / fin)
```

Fases y su estado de diseño:
- `precalentamiento.py` — sostiene presión de chaqueta.
- `purga.py` — flujo de vapor para desplazar aire seco.
- `prevacio.py` — pulsos de vacío/vapor (hasta 4 tipos configurables).
- `calentamiento.py` — **rediseñado**: RAMPA (control continuo de `vapor_camara` vía duty cycle — el mínimo entre tres términos: un límite de pendiente `tasa_calentamiento`/`tasa_presion`, una aproximación lineal a `factor_calentamiento` a medida que `temp`/`pres` se acercan a los objetivos fijos, y un corte si la temperatura supera el 97% del objetivo sin que la presión corresponda a vapor saturado — más un techo independiente de presión como resguardo — ver `docs/superpowers/specs/2026-08-05-control-continuo-rampa-calentamiento-design.md`) → ESTABLE_PREESTERILIZACION. ESTABLE_PREESTERILIZACION exige una ventana continua de estabilidad (con reinicio ante overshoot) antes de entregar control a ESTERILIZACION — fusiona lo que antes era la fase separada `EstabilizacionFase` (ver `docs/superpowers/specs/2026-08-04-fusion-calentamiento-estabilizacion-design.md`). El término de proximidad tiene un piso `duty_estable` (`1 - factor_calentamiento/100`) que antes se sostenía indefinidamente en cuanto `temp`/`pres` superaban el objetivo, sin importar cuánto — bug real (ciclo 79, 2026-08-06): con `t_obj=134.0` y la cámara ya en 136.7°C, el duty seguía en 0.5 en vez de ir a 0, y el control se veía "sosteniendo" una temperatura muy por encima del setpoint con pulsos de vapor. Corregido escalando ese piso hacia 0 a medida que el sobrepaso crece, llegando a 0 a partir de `rango_calentamiento` unidades pasado el objetivo (función `_duty_por_sobrepaso`).
- `esterilizacion.py` — **rediseñado**, ver detalle abajo.
- `descompresion.py`, `secado.py`, `valvula_reposo.py`, `protocolo_fallo.py` — sin cambios recientes.

---

## ESTERILIZACION — diseño (rediseño 2026-07-28)

Ver plan completo en `docs/mis_plans/planeacion_fase_esterilizacion.md`. Reemplazo total del `esterilizacion.py` anterior, que fallaba sin tolerancia inferior en temperatura/presión (bug `ESTERILIZACION_PRES_BAJA`: evaluaba la presión contra `P_sat(T_actual)` en vez de `P_sat(temperatura_esterilizacion)` fija).

### Objetivo
Sostener la cámara en vapor saturado a `temperatura_esterilizacion` durante `tiempo_esterilizacion` minutos — la fase que efectivamente esteriliza. No hay tramo de aproximación: viene de CALENTAMIENTO ya en condición de vapor saturado.

### Máquina de estados interna (bidireccional, sin chattering-guard)

```
RECUPERACION            T < temperatura_esterilizacion + brecha_segura_temperatura
                        O P < P_sat(temperatura_esterilizacion) - brecha_segura_presion
  vapor_camara ON continuo (sin techo de control)
       ↕ (evaluado en cada tick, sin guardia anti-chattering — a diferencia de CALENTAMIENTO)
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
- Chequeo de fallas, con debounce de 3 lecturas, **siempre contra `temperatura_esterilizacion` fija** (nunca `T_actual`):
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
| `brecha_segura_temperatura` | °C | 0.3 | Umbral bidireccional RECUPERACION↔PWM_ACTIVO (temperatura) |
| `brecha_segura_presion` | kPa | 1.5 | Umbral bidireccional RECUPERACION↔PWM_ACTIVO (presión) — debe ser MENOR que `brecha_error_presion` (ver texto arriba, al revés que temperatura) |
| `brecha_error_temperatura` | °C | 0.1 | Umbral de falla temp baja |
| `brecha_error_presion` | kPa | 2 | Umbral de falla pres baja |

Eliminados (semántica antigua, sin tolerancia inferior): `temperatura_add_esterilizacion`, `temperatura_error_esterilizacion`, `rango_presion_esterilizacion`, `presion_error_esterilizacion`. El parámetro `Compruebe RTC` del Excel se descarta explícitamente, no forma parte del código.

### UI
La pestaña "Esterilización" de `params_ciclo.py` (PySide6) no filtra claves (`filter_keys=None`) — renderiza automáticamente todo lo que exista en `parameters.esterilizacion` del JSON, así que agregar/quitar parámetros ahí no requiere tocar el código de la UI.

### Riesgo aceptado (decisión explícita)
No hay timeout de fase. Si un sensor de temperatura o presión queda en `None`, la fase devuelve `EN_CURSO` indefinidamente — no avanza ni falla, incluso si el timer de finalización ya venció. Mitigación (si se requiere) quedaría a nivel de `CicloState` o watchdog de sensor, fuera del alcance de esta fase.

### Pendiente compartido con CALENTAMIENTO
Sensor de líquido secundario (`temp_camara_2`/`has_liquid_sensor`) para configuraciones de dos puertas — aplazado en ambas fases hasta un levantamiento aparte.
