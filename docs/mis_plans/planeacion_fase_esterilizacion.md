# Planeación de la fase ESTERILIZACION

**Proyecto:** Software-de-autoclave (Especifika S.A.S.)
**Alcance:** Rediseño completo de la fase ESTERILIZACION del ciclo de esterilización — reemplazo total de `esterilizacion.py`.

---

## 1. Objetivo y alcance de la fase

### Objetivo

Sostener la cámara en condición de vapor saturado a `temperatura_esterilizacion` durante `tiempo_esterilizacion` minutos, garantizando que la temperatura y presión no caigan por debajo del punto de esterilización (reserva térmica) ni excedan los umbrales de falla, mientras se ejecutan en paralelo los ciclos de escape lento y rápido. Es la fase que efectivamente esteriliza; el conteo de tiempo es la variable crítica de proceso.

### Reemplazo, no modificación

Elimina completamente `esterilizacion.py` actual (falla inmediata sin tolerancia inferior en temperatura/presión, ver bug documentado `ESTERILIZACION_PRES_BAJA` en logs — presión evaluada contra `P_sat(T_actual)` en vez de `P_sat(temperatura_esterilizacion)` fija). Sin compatibilidad hacia atrás con `temperatura_add_esterilizacion`, `temperatura_error_esterilizacion`, `rango_presion_esterilizacion`, `presion_error_esterilizacion` (nombres/semántica antigua) — quedan obsoletos.

Se **elimina también** el parámetro `Compruebe RTC` del Excel (fila 15) — la comprobación de integridad de reloj queda fuera de esta fase por decisión explícita.

### Posición en el pipeline

Sin cambios en la orquestación de `CicloState`:

```
... → CALENTAMIENTO → ESTABILIZACION → ESTERILIZACION → (fin de ciclo)
```

### Entradas

- Estado de cámara al salir de ESTABILIZACION (ya validada en condición de vapor saturado, pero esta fase no asume que se mantenga — contempla tramo de recuperación desde el primer tick).
- Lecturas continuas de `temp_camara` y `pres_camara`.
- Parámetros de la sección `esterilizacion` del perfil (14, ver tabla).

### Salidas (I/O física)

- `vapor_camara` (ON continuo / PWM, según tramo).
- `descompresion_lenta`.
- `descompresion_rapida`.

Sin I/O nuevo.

### Fuera de alcance de esta fase

- Comprobación de integridad de reloj (RTC) — eliminada del alcance.
- Sensor de líquido secundario (`temp_camara_2`) — se mantiene con un solo sensor; queda como pendiente compartido con CALENTAMIENTO (sección 9).
- Timeout de fase — no existe; el conteo de `tiempo_esterilizacion` inicia inmediatamente al entrar a la fase y corre sin pausa ni reinicio, independiente del tramo de control activo (RECUPERACION o PWM_ACTIVO).

---

## 2. Tabla de parámetros normalizados

| # | Nombre (Excel) | Nombre en código | Unidad | Defecto | Mín | Máx | Rol |
|---|---|---|---|---|---|---|---|
| 1 | Escape lento Ester on | `escape_lento_on_ester` | seg | 1 | 0 | 1000 | Setpoint de control — tiempo abierto de `descompresion_lenta` |
| 2 | Escape lento Ester off | `escape_lento_off_ester` | seg | 0 | 0 | 1000 | Setpoint de control — tiempo cerrado; 0 = enclavada abierta |
| 3 | Escape rapido ester on | `escape_rapido_on_ester` | seg | 0 | 0 | 1000 | Setpoint de control — tiempo abierto; 0 = enclavada cerrada |
| 4 | Escape rapido Ester off | `escape_rapido_off_ester` | seg | 400 | 0 | 1000 | Setpoint de control — tiempo cerrado de `descompresion_rapida` |
| 5 | Temperatura de esterilizacion | `temperatura_esterilizacion` | °C | 134 | 100 | 140 | Setpoint de control — referencia fija para todas las fórmulas de control y falla |
| 6 | Tiempo de esterilizacion | `tiempo_esterilizacion` | min | 3.5 | 0 | 9999 | Setpoint de control — duración fija del conteo, inicia al entrar a la fase, sin timeout ni pausa |
| 7 | Factor de esterilizacion | `factor_esterilizacion` | % | 70 | 0 | 100 | Setpoint de control — % OFF del ciclo PWM dentro de banda fija [-2,+1] kPa sobre `P_sat(T_actual)` |
| 8 | Presion de esterilizacion adicional | `presion_add_esterilizacion` | kPa | 11 | 0 | 100 | Setpoint de control — define `P_control_max = P_sat(temperatura_esterilizacion) + presion_add`; techo de control (fuerza OFF, no es falla) |
| 9 | Intervalos segmentos ester | `intervalo_segmentos_ester` | seg | 3 | 0 | 30 | Setpoint de control — periodo del ciclo PWM |
| 10 | Rango de temperatura Ester | `rango_temperatura_ester` | °C | 3 | 0 | 50 | Umbral de falla — temp alta: `T > temperatura_esterilizacion + rango_temperatura_ester` |
| 11 | Rango de presion en ester | `rango_presion_ester` | kPa | 30 | 0 | 100 | Umbral de falla — presión alta: `P > P_sat(temperatura_esterilizacion) + rango_presion_ester` |
| 12 | Brecha segura temperatura | `brecha_segura_temperatura` | °C | 0.3 | 0 | 2 | Setpoint de control — umbral bidireccional RECUPERACION↔PWM_ACTIVO: `T < temperatura_esterilizacion + brecha_segura_temperatura` |
| 13 | Brecha error de temperatura | `brecha_error_temperatura` | °C | 0.1 | 0 | 2 | Umbral de falla — temp baja: `T < temperatura_esterilizacion - brecha_error_temperatura` |
| 14 | Brecha error presion | `brecha_error_presion` | kPa | 2 | 0 | 10 | Umbral de falla — presión baja: `P < P_sat(temperatura_esterilizacion) - brecha_error_presion` |

Todos con debounce de 3 lecturas consecutivas para las 4 condiciones de falla (10, 11, 13, 14) — mismo criterio que CALENTAMIENTO.

### Notas de consistencia

- **`presion_add_esterilizacion`** no es referencia de falla (a diferencia de CALENTAMIENTO, donde define `P_obj` de finalización). Aquí es un techo de control: evita que la banda local de PWM (que sigue a `T_actual`, no a la temperatura fija) arrastre la presión hasta el umbral real de falla.
- Todas las condiciones de falla usan `temperatura_esterilizacion` fija como referencia (nunca `T_actual`) — corrige el bug de `ESTERILIZACION_PRES_BAJA` documentado en logs.
- Transición RECUPERACION↔PWM_ACTIVO es **bidireccional** (a diferencia del diseño unidireccional de CALENTAMIENTO) — decisión explícita para reaccionar ante cualquier pérdida de reserva térmica durante el sostenimiento.

---

## 3. Máquina de estados interna de la fase

```
[Entrada desde ESTABILIZACION]
        │
        ▼
   ¿T < temperatura_esterilizacion + brecha_segura_temperatura?
        │                                   │
       Sí                                  No
        │                                   │
        ▼                                   ▼
┌──────────────────────┐          ┌──────────────────────────┐
│     RECUPERACION       │◄────────►│       PWM_ACTIVO           │
│  vapor_camara = ON     │  bidir.  │  vapor_camara en PWM      │
│  continuo               │          │  (factor_esterilizacion / │
└──────────────────────┘          │   intervalo_segmentos_ester)│
                                     │  banda fija [-2,+1] kPa    │
                                     │  sobre P_sat(T_actual)     │
                                     │  techo: P_control_max      │
                                     └──────────────────────────┘
        │                                   │
        └───────────────┬───────────────────┘
                         ▼
        (en paralelo, desde el inicio, sin depender del tramo)
        timer tiempo_esterilizacion → COMPLETADO al expirar
        escape_lento / escape_rapido → ciclos independientes
        chequeo de fallas (temp/pres alta/baja, debounce 3) → FALLO
```

No hay tramo de aproximación tipo CALENTAMIENTO: la fase asume condición inicial cercana al setpoint (viene de ESTABILIZACION), y cualquier desviación se resuelve con la transición RECUPERACION↔PWM_ACTIVO.

---

## 4. Lógica de control

### 4.1 Control de `vapor_camara`

- **RECUPERACION**: ON continuo, sin PWM.
- **PWM_ACTIVO**: banda fija de referencia `[P_sat(T_actual) - 2, P_sat(T_actual) + 1]` kPa (hardcodeada, no configurable):
  - `P < P_sat(T_actual) - 2` → `vapor_camara` ON forzado (fuera de banda, por abajo).
  - `P > P_sat(T_actual) + 1` → `vapor_camara` OFF forzado (fuera de banda, por arriba).
  - Dentro de banda → ciclo PWM de periodo `intervalo_segmentos_ester`, OFF durante `factor_esterilizacion` % del periodo, ON el resto.
  - **Techo de control independiente**: si `P >= P_control_max = P_sat(temperatura_esterilizacion) + presion_add_esterilizacion` → `vapor_camara` OFF forzado, sin importar el estado de la banda local. Esto evita que la banda local (que sigue a `T_actual`, no a `temperatura_esterilizacion` fija) arrastre la presión hasta el umbral real de falla (`rango_presion_ester`).
- Transición **bidireccional** RECUPERACION↔PWM_ACTIVO: se evalúa en cada tick, sin importar el tramo previo (no hay chattering-guard como en CALENTAMIENTO, porque aquí la reacción rápida ante pérdida de reserva térmica es el objetivo de diseño).

### 4.2 Control de `descompresion_lenta` (escape lento)

Mismo patrón que CALENTAMIENTO: temporizador de dos estados, independiente de T/P — abierta `escape_lento_on_ester` seg → cerrada `escape_lento_off_ester` seg → repite. `off=0` → enclavada abierta.

### 4.3 Control de `descompresion_rapida` (escape rápido)

Mismo patrón — abierta `escape_rapido_on_ester` seg → cerrada `escape_rapido_off_ester` seg → repite. `on=0` (caso por defecto aquí) → enclavada cerrada.

### 4.4 Independencia de los lazos

`vapor_camara`, `descompresion_lenta` y `descompresion_rapida` se evalúan de forma independiente en cada tick — ninguno bloquea a otro.

---

## 5. Condición de finalización

```
_timer_fin = t_inicio_fase + tiempo_esterilizacion * 60   # fijado en inicialización
```

`FaseResult.COMPLETADO` cuando `time.time() >= _timer_fin`, sin importar el tramo de control activo en ese instante (RECUPERACION o PWM_ACTIVO) — el timer no se pausa ni se reinicia por transiciones de tramo. No hay condición de presión/temperatura para completar: el conteo de tiempo es la única variable de finalización exitosa.

---

## 6. Condiciones de FALLO

| Condición | Umbral | Debounce | Acción |
|---|---|---|---|
| Temp alta | `T > temperatura_esterilizacion + rango_temperatura_ester` | 3 lecturas | `FALLO`, apagar salidas |
| Temp baja | `T < temperatura_esterilizacion - brecha_error_temperatura` | 3 lecturas | `FALLO`, apagar salidas |
| Presión alta | `P > P_sat(temperatura_esterilizacion) + rango_presion_ester` | 3 lecturas | `FALLO`, apagar salidas |
| Presión baja | `P < P_sat(temperatura_esterilizacion) - brecha_error_presion` | 3 lecturas | `FALLO`, apagar salidas |
| Sensores no disponibles (`None`) | — | — | `return FaseResult.EN_CURSO` (no avanza, no falla; sin timeout que lo capture — riesgo aceptado, ver sección 8) |

Las cuatro condiciones de falla usan `temperatura_esterilizacion` fija como referencia (nunca `T_actual`) — corrige directamente el bug de `ESTERILIZACION_PRES_BAJA` documentado en logs, donde la referencia móvil generaba falsos positivos.

Al entrar en `FALLO`: apagar `vapor_camara`, `descompresion_lenta`, `descompresion_rapida` — mismo patrón que CALENTAMIENTO.

---

## 7. Mapeo a I/O existente

| Nombre lógico (Excel) | Método HAL/`set_do` |
|---|---|
| Fuente de energía (vapor) | `set_do.vapor_camara_on()` / `set_do.vapor_camara_off()` |
| Escape lento | `set_do.descompresion_lenta_on()` / `set_do.descompresion_lenta_off()` |
| Escape rápido | `set_do.descompresion_rapida_on()` / `set_do.descompresion_rapida_off()` |

Sin adiciones al HAL.

---

## 8. Matriz de modos de falla (FMEA simplificado)

| Tramo | Modo de falla | Efecto | Causa probable | Detección | Prevención/control |
|---|---|---|---|---|---|
| RECUPERACION | Vapor ON continuo prolongado sin recuperar T | Sobrecalentamiento, riesgo de `falla_temp_alta` en cascada | Fuga de vapor insuficiente para recuperar, válvula parcialmente obstruida, sensor con offset | `falla_temp_alta` (debounce 3) | `FALLO` + apagado de salidas |
| RECUPERACION↔PWM_ACTIVO | Oscilación frecuente entre tramos (chattering térmico) | Ciclado excesivo de válvula, desgaste prematuro | `brecha_segura_temperatura` muy ajustada frente a ruido del sensor | Ninguna a nivel de esta fase — riesgo aceptado por decisión de diseño (transición bidireccional intencional) | Ajuste de `brecha_segura_temperatura` en comisionamiento si se observa chattering excesivo |
| PWM_ACTIVO | Presión sube hasta `P_control_max` de forma sostenida | Válvula OFF forzada de forma prolongada, posible enfriamiento no deseado | `factor_esterilizacion`/`intervalo_segmentos_ester` mal calibrados para el volumen de cámara | Techo `P_control_max` (control, no falla) + `falla_pres_alta` si `P_control_max` no contiene la subida | `FALLO` + apagado de salidas si escala a `rango_presion_ester` |
| PWM_ACTIVO | Banda local `[-2,+1]` kPa nunca se estabiliza (oscilación de válvula) | Ciclado excesivo, posible impacto en repetibilidad del proceso | Volumen de cámara/dinámica de vapor no coincide con `intervalo_segmentos_ester` configurado | Ninguna automática — es ajuste de comisionamiento | Validación de parámetros en pruebas de fábrica (fuera de esta fase) |
| Todo el ciclo de la fase | `descompresion_lenta`/`descompresion_rapida` mal configuradas (ambas con poca apertura) | Pérdida de vapor insuficiente para renovación, no crítico para seguridad | Error de comisionamiento | Ninguna automática | Validación de rangos en `ConfigManager` (fuera de esta fase) |
| Todo el ciclo de la fase | Sensor de presión o temperatura no disponible (`None`) | Fase bloqueada indefinidamente — **sin timeout que lo capture** (decisión explícita, sección 1) | Desconexión de sensor, fallo de comunicación ESP32 | Ninguna a nivel de fase | Depende de `alarm_manager`/supervisión externa (fuera de esta fase); riesgo aceptado por ausencia de timeout |
| Todo el ciclo de la fase | `P_control_max` calculado sobre `presion_add_esterilizacion` mal configurado (muy bajo) | Corta el vapor prematuramente, riesgo de no sostener saturación | Error de comisionamiento | Ninguna automática | Validación de rangos en comisionamiento |

**Nota de riesgo (ausencia de timeout):** al no existir protección por tiempo máximo si los sensores quedan en `None`, la fase puede quedar indefinidamente en `EN_CURSO`. Queda documentado como riesgo aceptado por decisión explícita del usuario (sección 1); si en comisionamiento se observa este escenario, la mitigación sería un timeout de nivel superior en `CicloState` o un watchdog de sensor — fuera del alcance actual salvo que se solicite.

---

## 9. Próximos pasos fuera de este documento

- Implementación de `esterilizacion.py` (reemplazo completo) siguiendo la máquina de estados de la sección 3.
- Tests unitarios nuevos (reemplazan los actuales que validan la lógica sin tolerancia inferior — el bug de origen).
- Actualización de `ConfigManager`/JSON de perfil: eliminar parámetros obsoletos (`temperatura_add_esterilizacion`, `temperatura_error_esterilizacion`, `rango_presion_esterilizacion`, `presion_error_esterilizacion`, `compruebe_rtc`), agregar los 14 nuevos con los rangos de la sección 2.
- Actualización de la UI de configuración de ciclos (Tkinter actual o PySide6, según estado de la migración) para exponer los 14 parámetros nuevos.
- **Pendiente compartido con CALENTAMIENTO**: manejo de sensor de líquido secundario (`temp_camara_2`/`has_liquid_sensor`) para configuraciones de dos puertas — aplazado en ambas fases, requiere levantamiento aparte antes de codificar cualquiera de las dos.
- Riesgo aceptado documentado en sección 8 (ausencia de timeout ante sensores `None`) — evaluar en comisionamiento si requiere mitigación posterior.
- Programación/direccionamiento de I/O detallado: no aplica — salidas ya existentes en el HAL.
