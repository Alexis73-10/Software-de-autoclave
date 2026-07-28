# Planeación de la fase CALENTAMIENTO

**Proyecto:** Software-de-autoclave (Especifika S.A.S.)
**Alcance:** Rediseño completo de la fase CALENTAMIENTO del ciclo de esterilización — reemplazo total de `calentamiento.py`.

---

## 1. Objetivo y alcance de la fase

### Objetivo

Elevar la cámara desde la condición de salida de PRE_VACIO hasta el punto de vapor saturado correspondiente al setpoint de esterilización (`temperatura_calentamiento` + `presion_add_calentamiento`), y sostener esa condición (presión y temperatura) durante `tiempo_estable_preesterilizacion` segundos antes de entregar el control a ESTABILIZACION. Es la fase que prepara las condiciones de entrada para el ciclo de esterilización propiamente dicho; no realiza ninguna función de esterilización por sí misma.

### Reemplazo, no modificación

Esta especificación **elimina completamente** la implementación actual de `calentamiento.py` (rampa por pendiente + checkpoints al 80%/97% con verificación de vapor saturado, ver `tests/test_calentamiento_fase.py`). No hay compatibilidad hacia atrás con esos parámetros (`margen_techo_calentamiento`, `tiempo_apertura_vapor_checkpoint`, `tiempo_cierre_vapor_checkpoint`, semántica antigua de `rango_presion_calentamiento`) — quedan obsoletos y deben removerse del perfil/config junto con el código viejo.

### Posición en el pipeline

Sin cambios en la orquestación de `CicloState`:

```
PRECALENTAMIENTO → PURGA → PRE_VACIO → CALENTAMIENTO → ESTABILIZACION → ESTERILIZACION
```

`CALENTAMIENTO` sigue devolviendo `FaseResult.EN_CURSO / COMPLETADO / FALLO` al orquestador — el rediseño es interno a la fase, no toca `ciclo.py`.

### Entradas

- Estado de cámara al salir de PRE_VACIO (temperatura y presión iniciales, no controladas por esta fase).
- Lecturas continuas de `temp_camara` y `pres_camara`.
- Parámetros de la sección `calentamiento` del perfil (los 13 del Excel).
- Estado de puertas/sensores vía `alarm_manager` (fuera del alcance de esta fase — corre en paralelo durante todo el ciclo, no se re-implementa aquí).

### Salidas (I/O física)

- `vapor_camara` (control ON/PWM).
- `descompresion_lenta` ("escape lento" del Excel).
- `descompresion_rapida` ("escape rápido" del Excel).

Sin I/O nuevo — las tres salidas ya existen en el HAL.

### Dependencias con otras secciones de parámetros

`temperatura_calentamiento` es un parámetro **independiente** dentro de la sección `calentamiento` (no se lee de `esterilizacion.temperatura_esterilizacion`). Esto implica que el perfil JSON puede tener valores distintos configurados para la temperatura de calentamiento vs. la de esterilización — es responsabilidad del operador/comisionamiento mantenerlos coherentes; esta fase no valida esa coherencia.

### Fuera de alcance de esta fase

- La verificación de vapor saturado como criterio de *entrada* a un control activo intermedio distinto al descrito (no hay checkpoints intermedios en este diseño).
- Manejo de sensor de líquido secundario (`temp_camara_2` / `has_liquid_sensor`) — el Excel no lo menciona; si el hardware de dos puertas lo requiere, es una decisión pendiente que hay que levantar aparte.
- Actualización del `ConfigManager`/JSON de perfil y de la UI de configuración de ciclos — se referencia como entregable derivado, no como parte de esta fase de planeación.

---

## 2. Tabla de parámetros normalizados

| # | Nombre (Excel) | Nombre en código | Unidad | Defecto | Mín | Máx | Rol |
|---|---|---|---|---|---|---|---|
| 1 | Temperatura de esterilizacion | `temperatura_calentamiento` | °C | 134 | 100 | 140 | Setpoint de control — objetivo de temperatura de la fase |
| 2 | Presion de calentamiento añadida | `presion_add_calentamiento` | kPa | 11 | 0 | 100 | Setpoint de control — se suma a `P_sat(temperatura_calentamiento)` para definir `P_obj` |
| 3 | Error de tiempo de calentamiento | `timeout_calentamiento` | min | 60 | 1 | 999 | Umbral de falla — timeout global de la fase |
| 4 | Factor de calentamiento | `factor_calentamiento` | % | 50 | 0 | 100 | Setpoint de control — % de `intervalo_segmentos_calor` que `vapor_camara` permanece OFF durante PWM |
| 5 | Rango de calentamiento | `rango_calentamiento` | kPa | 2 | 0 | 30 | Setpoint de control — banda alrededor de `P_sat(temp_actual)` que determina entrada a PWM |
| 6 | Tasa de calentamiento | `tasa_calentamiento` | °C/min | 50 | 0 | 100 | Umbral de falla — pendiente máxima de temperatura (debounce 3 lecturas) |
| 7 | Tasa de presion | `tasa_presion` | kPa/min | 100 | 0 | 300 | Umbral de falla — pendiente máxima de presión (debounce 3 lecturas) |
| 8 | Tiempo estable pre esterilizacion | `tiempo_estable_preesterilizacion` | seg | 3 | 0 | 180 | Setpoint de control — duración de sostenimiento antes de `COMPLETADO`; si=0, finaliza al cumplirse la condición instantánea |
| 9 | Intervalo segmentos de calor | `intervalo_segmentos_calor` | seg | 2 | 0 | 30 | Setpoint de control — periodo del ciclo PWM de `vapor_camara` |
| 10 | Escape lento encendido | `escape_lento_on` | seg | 1 | 0 | 1000 | Setpoint de control — tiempo abierto de `descompresion_lenta` |
| 11 | Escape lento apagado | `escape_lento_off` | seg | 0 | 0 | 1000 | Setpoint de control — tiempo cerrado de `descompresion_lenta`; 0 = enclavada abierta |
| 12 | Escape rapido encendido | `escape_rapido_on` | seg | 0 | 0 | 1000 | Setpoint de control — tiempo abierto de `descompresion_rapida`; 0 = enclavada cerrada |
| 13 | Escape rapido apagado | `escape_rapido_off` | seg | 10 | 0 | 1000 | Setpoint de control — tiempo cerrado de `descompresion_rapida` |

### Notas de consistencia

- **Fila 6**: el nombre en el Excel dice "esterilizacion" pero la descripción y el contexto (sheet `Calentando`) confirman que es el setpoint de esta fase, no una referencia cruzada — se mantiene `temperatura_calentamiento` para evitar el mismo tipo de ambigüedad que generó el hallazgo H-01 en la auditoría (nombres que no coinciden con su función real).
- **Filas 10–13**: dos pares independientes (`on`, `off`) por válvula. El caso borde `off=0` (fila 11) y `on=0` (fila 12) se documenta explícitamente porque son los valores por defecto — en configuración de fábrica **escape lento arranca prácticamente siempre abierto** y **escape rápido prácticamente siempre cerrado**, consistente con la función de mantener flujo de vapor constante y evitar condensación.
- **Fila 5 vs. fila 2**: `rango_calentamiento` es la banda de entrada a PWM alrededor de `P_sat(temp_actual)` — es una banda dinámica que sigue la temperatura instantánea, **no** una banda fija alrededor de `P_obj`. Esto es distinto del criterio de fin de fase (sección 5), que sí usa `P_obj = P_sat(temperatura_calentamiento) + presion_add_calentamiento` como referencia fija.
- Todos los parámetros están en la sección `calentamiento` del perfil/config; ninguno se comparte por referencia con otra sección.

---

## 3. Máquina de estados interna de la fase

Tres tramos secuenciales, sin retroceso entre ellos (excepto por FALLO, que corta cualquier tramo):

```
[Entrada desde PRE_VACIO]
        │
        ▼
┌──────────────────────┐   |P_camara - P_sat(T_camara)| <= rango_calentamiento
│    APROXIMACION       │ ─────────────────────────────────────►┐
│  vapor_camara = ON    │                                        │
│  continuo             │                                        ▼
└──────────────────────┘                          ┌──────────────────────────┐
        │ timeout_calentamiento                    │       PWM_ACTIVO          │
        │ excedido                                 │  vapor_camara en PWM      │
        ▼                                          │  (factor_calentamiento /  │
     FALLO                                         │   intervalo_segmentos)    │
                                                     └──────────────────────────┘
                                                              │ T >= temperatura_calentamiento
                                                              │ Y P >= P_obj
                                                              ▼
                                               ┌────────────────────────────────┐
                                               │  ESTABLE_PREESTERILIZACION      │
                                               │  fase_en_sostenimiento = True   │
                                               │  vapor_camara sigue en PWM      │
                                               └────────────────────────────────┘
                                                              │ transcurrido >= tiempo_estable_preesterilizacion
                                                              │ (o inmediato si == 0)
                                                              ▼
                                                         COMPLETADO
```

Los lazos de `descompresion_lenta` y `descompresion_rapida` corren **en paralelo a los tres tramos**, desde el inicio de la fase hasta `COMPLETADO`/`FALLO` — no están sincronizados con las transiciones de estado anteriores.

El chequeo de `tasa_calentamiento` / `tasa_presion` (con debounce de 3 lecturas) corre también en paralelo, activo durante toda la fase, y puede producir `FALLO` desde cualquier tramo.

---

## 4. Lógica de control

### 4.1 Control de `vapor_camara`

- Tramo `APROXIMACION`: `vapor_camara` en `ON` continuo (sin PWM, sin límite de rampa activo — `tasa_calentamiento` solo vigila, no limita).
- Entrada a `PWM_ACTIVO`: cuando `abs(pres_camara - p_saturacion_kpa(temp_camara)) <= rango_calentamiento`.
- Dentro de `PWM_ACTIVO` y `ESTABLE_PREESTERILIZACION`: ciclo PWM de periodo `intervalo_segmentos_calor` segundos, con `vapor_camara` en `OFF` durante `factor_calentamiento` % del periodo y en `ON` el resto. Ejemplo con defectos (factor=50%, intervalo=2s): 1s ON / 1s OFF.
- No hay retorno de `PWM_ACTIVO` a `APROXIMACION`: una vez dentro de la banda, el control permanece en PWM aunque la lectura salga momentáneamente de la banda (evita chattering entre modos de control ante ruido de sensor).

### 4.2 Control de `descompresion_lenta` (escape lento)

Temporizador de dos estados, independiente de temperatura/presión:
- Abierta `escape_lento_on` segundos → cerrada `escape_lento_off` segundos → repite.
- Caso borde `escape_lento_off = 0` (defecto): permanece abierta de forma continua (el ciclo nunca entra a la fase "cerrada").

### 4.3 Control de `descompresion_rapida` (escape rápido)

Mismo patrón, temporizador independiente:
- Abierta `escape_rapido_on` segundos → cerrada `escape_rapido_off` segundos → repite.
- Caso borde `escape_rapido_on = 0` (defecto): permanece cerrada de forma continua.

### 4.4 Independencia de los tres lazos

`vapor_camara`, `descompresion_lenta` y `descompresion_rapida` se evalúan y actualizan de forma independiente en cada tick de control — ninguno bloquea o condiciona a otro. Esto es intencional: mantiene flujo de vapor constante para evitar condensación y lecturas erróneas de temperatura, independientemente del estado del PWM de calor.

---

## 5. Condición de finalización

```
P_obj = p_saturacion_kpa(temperatura_calentamiento) + presion_add_calentamiento

condición_instantánea =
    temp_camara >= temperatura_calentamiento
    Y
    pres_camara >= P_obj
```

- Si `tiempo_estable_preesterilizacion == 0`: `FaseResult.COMPLETADO` en el mismo tick en que `condición_instantánea` se cumple por primera vez.
- Si `tiempo_estable_preesterilizacion > 0`: al cumplirse `condición_instantánea` por primera vez, arranca un timer simple (`_timer_estable_inicio = time.time()`), se activa `fase_en_sostenimiento = True`. El timer **no se reinicia** si la condición sale momentáneamente de rango (a diferencia de `EstabilizacionFase`, que sí usa un timer de recuperación separado — decisión de diseño explícita para esta fase). `COMPLETADO` cuando `time.time() - _timer_estable_inicio >= tiempo_estable_preesterilizacion`.
- No hay tolerancia de banda adicional para "estable" — se reutiliza la misma condición `>=` de arriba, evaluada en cada tick durante el sostenimiento.

---

## 6. Condiciones de FALLO

| Condición | Umbral | Debounce | Acción |
|---|---|---|---|
| Timeout global | `time.time() > t_inicio_fase + timeout_calentamiento*60` | Ninguno (instantáneo) | `FALLO`, apagar `vapor_camara` |
| Exceso pendiente temperatura | `ΔT/Δtick > tasa_calentamiento` (por minuto) | 3 lecturas consecutivas | `FALLO`, apagar `vapor_camara` |
| Exceso pendiente presión | `ΔP/Δtick > tasa_presion` (por minuto) | 3 lecturas consecutivas | `FALLO`, apagar `vapor_camara` |
| Sensores/puertas | Delegado a `alarm_manager` | — | Fuera del alcance de esta fase (corre en paralelo durante todo el ciclo) |

**Justificación del debounce de 3 lecturas:** un umbral de 1 sola lectura fuera de rango es demasiado sensible al ruido típico de sensores de presión/temperatura industrial y generaría falsos positivos en una fase agresiva (hasta 50 °C/min de tasa configurada). Con tick de control ~1s, 3 lecturas equivalen a ~3s de persistencia — da margen sin comprometer el tiempo de reacción ante un evento real de fuga o descontrol.

Al entrar en `FALLO`, se apagan las tres salidas (`vapor_camara`, `descompresion_lenta`, `descompresion_rapida`) — mismas salidas usadas en operación normal, sin I/O adicional que forzar.

---

## 7. Mapeo a I/O existente

| Nombre lógico (Excel) | Método HAL/`set_do` |
|---|---|
| Fuente de energía (vapor) | `set_do.vapor_camara_on()` / `set_do.vapor_camara_off()` |
| Escape lento | `set_do.descompresion_lenta_on()` / `set_do.descompresion_lenta_off()` |
| Escape rápido | `set_do.descompresion_rapida_on()` / `set_do.descompresion_rapida_off()` |

Sin adiciones al HAL — las tres salidas ya existen.

---

## 8. Matriz de modos de falla (FMEA simplificado)

| Tramo | Modo de falla | Efecto | Causa probable | Detección | Prevención/control |
|---|---|---|---|---|---|
| APROXIMACION | Calentamiento no alcanza banda de PWM en tiempo razonable | Timeout de fase, ciclo abortado | Fuga de vapor, válvula `vapor_camara` no abre, sensor de presión con offset de calibración | `timeout_calentamiento` | Timer global de fase |
| APROXIMACION → PWM_ACTIVO | Oscilación entre tramos por ruido de sensor | Chattering de válvula, desgaste prematuro | Ruido de lectura cerca del límite de `rango_calentamiento` | N/A (por diseño no hay retorno) | Transición unidireccional (sección 4.1) |
| PWM_ACTIVO | Sobrepresión por PWM mal calibrado (`factor_calentamiento` muy bajo) | Presión sube más rápido de lo esperado | `intervalo_segmentos_calor`/`factor_calentamiento` mal configurados para el volumen de cámara | `tasa_presion` con debounce de 3 lecturas | `FALLO` + apagado de salidas |
| PWM_ACTIVO / ESTABLE | Rampa de temperatura anómala (subida o caída abrupta) | Riesgo de choque térmico, indicativo de fuga o sensor dañado | Sensor de temperatura defectuoso, fuga de vapor directa a cámara | `tasa_calentamiento` con debounce de 3 lecturas | `FALLO` + apagado de salidas |
| ESTABLE_PREESTERILIZACION | Condición sale de rango pero timer no se reinicia (por diseño) | Fase completa con estabilidad marginal, no con estabilidad real sostenida | Ruido de sensor puntual durante el conteo | Ninguna a nivel de esta fase (riesgo aceptado por decisión de diseño) | Ver nota de riesgo abajo |
| Todo el ciclo de la fase | `descompresion_lenta`/`descompresion_rapida` con parámetros mal configurados (p. ej. ambas abiertas simultáneamente en exceso) | Pérdida de vapor, calentamiento más lento de lo esperado, no crítico para seguridad | Error de comisionamiento/configuración | Ninguna automática — es configuración, no falla de sensor | Validación de rangos en `ConfigManager` al cargar perfil (fuera de esta fase) |
| Todo el ciclo de la fase | Sensor de presión o temperatura no disponible (`None`) | Fase bloqueada indefinidamente si no se maneja | Desconexión de sensor, fallo de comunicación ESP32 | Chequeo `if temp is None / pres is None: return EN_CURSO` (no avanza, pero tampoco falla) — el timeout global eventualmente lo captura | Igual que fases existentes (`precalentamiento.py`, `esterilizacion.py`) |

**Nota de riesgo (fila 5 de la matriz):** el timer de `tiempo_estable_preesterilizacion` sin reinicio ante salida de rango es una decisión de diseño explícita. Queda documentada aquí como riesgo aceptado, no como omisión — si en pruebas de comisionamiento se observa que la fase completa con lecturas inestables cerca del límite del conteo, la mitigación sería introducir un timer de recuperación (patrón ya usado en `EstabilizacionFase`), pero eso quedaría fuera del alcance actual salvo que se solicite explícitamente.

---

## 9. Próximos pasos fuera de este documento

- Implementación de `calentamiento.py` (reemplazo completo del archivo actual) siguiendo la máquina de estados de la sección 3.
- Tests unitarios nuevos (reemplazan `tests/test_calentamiento_fase.py` actual, que valida la lógica de checkpoints obsoleta).
- Actualización de `ConfigManager`/JSON de perfil: eliminar parámetros obsoletos (`margen_techo_calentamiento`, `tiempo_apertura_vapor_checkpoint`, `tiempo_cierre_vapor_checkpoint`, semántica antigua de `rango_presion_calentamiento`), agregar los 13 nuevos con los rangos de la sección 2.
- Actualización de la UI de configuración de ciclos (Tkinter actual o PySide6, según en qué punto esté la migración cuando se implemente) para exponer los 13 parámetros nuevos.
- Decisión pendiente (marcada en sección 1): manejo de sensor de líquido secundario (`temp_camara_2`) en configuraciones de dos puertas — el Excel no lo contempla; requiere levantamiento aparte antes de codificar si aplica a esta fase.
- Programación de PLC/direccionamiento de I/O detallado: no aplica aquí — las salidas ya existen en el HAL; esto es responsabilidad de la capa de implementación, no de este documento de planeación.
