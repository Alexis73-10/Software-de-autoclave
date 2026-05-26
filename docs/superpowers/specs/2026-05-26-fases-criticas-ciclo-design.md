# Diseño: Fases Críticas del Ciclo — Calentamiento, Estabilización, Esterilización

**Fecha:** 2026-05-26
**Estado:** Pendiente de aprobación

---

## Contexto

Las fases calentamiento, estabilización y esterilización son las fases críticas del ciclo de autoclave porque en ellas la relación presión-temperatura del vapor saturado es condición de calidad del proceso. Las tres fases comparten una estructura común:

- `descompresion_lenta` siempre activa durante toda la fase
- Al finalizar (COMPLETADO o FALLO): todas las salidas de la fase se apagan explícitamente
- Verificación continua de condiciones de seguridad (paro de emergencia, puertas, sensores ausentes)

---

## Módulo de vapor saturado — `src/autoclave/core/steam.py`

Módulo nuevo con una sola función pública que implementa la ecuación de Antoine para agua líquida en el rango 99–145 °C.

**Ecuación:**

```
log₁₀(P_kPa) = A - B / (C + T_celsius)
```

**Constantes** (NIST WebBook, agua 99–145 °C):

| Constante | Valor |
|-----------|-------|
| A | 7.26509 |
| B | 1810.94 |
| C | 244.485 |

**Precisión verificada:**

| T (°C) | P_Antoine (kPa abs) | P_IAPWS (kPa abs) | Error |
|--------|--------------------|--------------------|-------|
| 100    | 101.9              | 101.3              | 0.6 kPa |
| 121    | 204.3              | 205.0              | 0.7 kPa |
| 134    | 302.2              | 302.9              | 0.7 kPa |

El error máximo (~0.7 kPa) es insignificante frente a la precisión de los sensores industriales y las tolerancias de alarma configuradas en JSON.

**API pública:**

```python
def p_saturacion_kpa(t_celsius: float) -> float:
    """Presión de saturación del vapor de agua (kPa absolutos). Rango válido: 99–145 °C."""
```

**Helper en BaseFase** — agregado a `base_fase.py`:

```python
def _verificar_vapor_saturado(self, t_celsius: float, p_real_kpa: float, tolerancia_kpa: float) -> bool:
    """True si |P_real - P_sat(T)| <= tolerancia."""
```

---

## Fase 4 — CALENTAMIENTO

### Propósito

Elevar la temperatura de la cámara desde la temperatura inicial hasta `temperatura_calentamiento` introduciendo vapor saturado, controlando la tasa de subida y verificando la calidad del vapor en dos puntos intermedios.

### Parámetros JSON (sección `"calentamiento"`)

| Parámetro | Tipo | Unidad | Descripción |
|-----------|------|--------|-------------|
| `temperatura_calentamiento` | float | °C | Temperatura objetivo final |
| `tasa_calentamiento` | float | °C/min | Tasa máxima de calentamiento |
| `timeout_calentamiento` | float | min | Timeout global; si expira → FALLO |
| `presion_add_calentamiento` | float | kPa | Tolerancia ± para verificación de vapor saturado en checkpoints |

### Salidas activas

| Salida | Comportamiento |
|--------|---------------|
| `descompresion_lenta` | ON durante toda la fase |
| `vapor_camara` | Bang-bang siguiendo rampa de temperatura |

### Flujo de control

```
Inicializar:
    T_inicio = temp_camara actual
    timer_timeout = now + timeout_seg
    checkpoints = [0.50 × temperatura_calentamiento,
                   0.90 × temperatura_calentamiento]
    descompresion_lenta_on()

Cada ciclo:

    1. Timeout global
           now > timer_timeout → apagar salidas → FALLO

    2. Sensores
           temp o pres = None → EN_CURSO (esperar)

    3. Emergencia / puertas / sensores
           condición activa → apagar salidas → FALLO

    4. Control de rampa
           T_permitida = T_inicio + tasa × elapsed
           if T_real >= T_permitida: vapor_camara_off()
           else:                     vapor_camara_on()

    5. Checkpoint (si queda alguno y T_real >= checkpoint[0])
           Entrar en bucle de verificación:
               if P_real > P_sat(T_real) + tolerancia: vapor_camara_off(), esperar
               if P_real < P_sat(T_real) - tolerancia: vapor_camara_on() (pulso corto)
               if |P_real - P_sat(T_real)| <= tolerancia: pop checkpoint[0], salir bucle
           → EN_CURSO mientras el checkpoint no se libere

    6. Condición de finalización
           T_real >= temperatura_calentamiento → apagar salidas → COMPLETADO
```

### Salidas al terminar

| Resultado | `vapor_camara` | `descompresion_lenta` |
|-----------|---------------|----------------------|
| COMPLETADO | OFF | OFF |
| FALLO | OFF | OFF |

---

## Fase 5 — ESTABILIZACIÓN

### Propósito

Verificar que la cámara mantiene las condiciones de temperatura y presión de esterilización durante un tiempo configurable antes de iniciar la cuenta oficial. Si `tiempo_estable_preesterilizacion = 0`, la fase se salta.

### Parámetros JSON (sección `"calentamiento"`)

| Parámetro | Tipo | Unidad | Descripción |
|-----------|------|--------|-------------|
| `tiempo_estable_preesterilizacion` | float | min | Duración; `0` = saltar fase |
| `temperatura_calentamiento` | float | °C | Temperatura objetivo a mantener |
| `rango_temp_estabilizacion` | float | °C | Tolerancia ± de temperatura durante sostenimiento |
| `presion_add_calentamiento` | float | kPa | Tolerancia ± de presión durante sostenimiento |
| `timeout_recuperacion_estabilizacion` | float | min | Tiempo máximo para recuperar condiciones antes de FALLO |

### Salidas activas

| Salida | Comportamiento |
|--------|---------------|
| `descompresion_lenta` | ON durante toda la fase |
| `vapor_camara` | Bang-bang para mantener temperatura y presión |

### Flujo de control

```
Si tiempo == 0 → COMPLETADO (skip)

Inicializar:
    timer_principal_fin = now + tiempo_seg
    timer_recuperacion = None
    descompresion_lenta_on()

Cada ciclo:

    1. Sensores ausentes → apagar salidas → FALLO

    2. Emergencia / puertas → apagar salidas → FALLO

    3. Leer T y P

    4. Verificar condiciones:
           dentro_rango = (|T - T_obj| <= rango_temp_estabilizacion) AND (|P - P_sat(T)| <= presion_add_calentamiento)

    5. Recuperación:
           if not dentro_rango:
               if timer_recuperacion is None: timer_recuperacion = now + timeout_recuperacion_seg
               if now > timer_recuperacion: apagar salidas → FALLO
           else:
               timer_recuperacion = None

    6. Control bang-bang:
           T < T_obj: vapor_camara_on()
           T >= T_obj: vapor_camara_off()

    7. Condición de finalización:
           now >= timer_principal_fin → apagar salidas → COMPLETADO
```

### Salidas al terminar

| Resultado | `vapor_camara` | `descompresion_lenta` |
|-----------|---------------|----------------------|
| COMPLETADO | OFF | OFF |
| FALLO | OFF | OFF |

---

## Fase 6 — ESTERILIZACIÓN

### Propósito

Mantener las condiciones de vapor saturado durante el tiempo de esterilización. Es la fase más crítica — cualquier desviación fuera de los rangos definidos termina el ciclo en FALLO.

### Zonas de control

#### Temperatura

```
FALLO baja              NORMAL                  AVISO         FALLO alta
    │←─ sin tolerancia ─→│←─ temperatura_add ─→│←─ error ─→│
T_est                T_est              T_est+add        T_est+add+error
```

- `T < T_esterilizacion` → **FALLO: temp baja** (inmediato, sin tolerancia)
- `T_esterilizacion ≤ T ≤ T_est + temperatura_add_esterilizacion` → zona normal
- `T > T_est + temperatura_add + temperatura_error_esterilizacion` → **FALLO: temp alta**

#### Presión (referencia = `P_sat(T_actual)`)

```
FALLO baja              NORMAL                  FALLO alta
    │←─ sin tolerancia ─→│←── rango ──→│←─ error ─→│
P_sat(T)           P_sat(T)       P_sat(T)+rango   P_sat(T)+rango+error
```

- `P < P_sat(T_actual)` → **FALLO: presión baja** (inmediato, sin tolerancia)
- `P_sat(T) ≤ P ≤ P_sat(T) + rango_presion_esterilizacion` → zona normal
- `P > P_sat(T) + rango + presion_error_esterilizacion` → **FALLO: presión alta**

### Parámetros JSON (sección `"esterilizacion"`)

| Parámetro | Tipo | Unidad | Descripción |
|-----------|------|--------|-------------|
| `temperatura_esterilizacion` | float | °C | Temperatura objetivo |
| `tiempo_esterilizacion` | float | min | Duración del ciclo |
| `temperatura_add_esterilizacion` | float | °C | Banda superior permitida sobre T_est |
| `temperatura_error_esterilizacion` | float | °C | Margen adicional antes de FALLO temp alta |
| `rango_presion_esterilizacion` | float | kPa | Banda superior permitida sobre P_sat(T) |
| `presion_error_esterilizacion` | float | kPa | Margen adicional antes de FALLO presión alta |

### Salidas activas

| Salida | Comportamiento |
|--------|---------------|
| `descompresion_lenta` | ON durante toda la fase |
| `vapor_camara` | Pulsos cortos para mantener temperatura |

### Flujo de control

```
Inicializar:
    timer_esterilizacion_fin = now + tiempo_seg
    descompresion_lenta_on()

Cada ciclo:

    1. Sensores ausentes → apagar salidas → FALLO (sensor ausente)

    2. Emergencia → apagar salidas → FALLO (paro de emergencia)

    3. Puertas abiertas o en error → apagar salidas → FALLO (puerta)

    4. Leer T y P

    5. Verificar temperatura:
           T < T_est                             → FALLO: temp baja
           T > T_est + add + error_temp          → FALLO: temp alta

    6. Verificar presión:
           P < P_sat(T_actual)                   → FALLO: presión baja
           P > P_sat(T_actual) + rango + error_P → FALLO: presión alta

    7. Control (zona normal):
           T < T_esterilizacion: vapor_camara_on() (pulso corto)
           T >= T_esterilizacion: vapor_camara_off()

    8. Condición de finalización:
           now >= timer_esterilizacion_fin → apagar salidas → COMPLETADO
```

### FALLOs posibles

| Código | Condición |
|--------|-----------|
| `TEMP_ALTA` | T > T_est + add + error_temp |
| `TEMP_BAJA` | T < T_esterilizacion |
| `PRES_ALTA` | P > P_sat(T) + rango + error_P |
| `PRES_BAJA` | P < P_sat(T_actual) |
| `PARO_EMERGENCIA` | Entrada de emergencia activa |
| `PUERTA` | Puerta abierta o en estado de error |
| `SENSOR_AUSENTE` | temp_camara o pres_camara = None |

### Salidas al terminar

| Resultado | `vapor_camara` | `descompresion_lenta` |
|-----------|---------------|----------------------|
| COMPLETADO | OFF | OFF |
| FALLO (cualquiera) | OFF | OFF |

---

## Archivos afectados

| Archivo | Cambio |
|---------|--------|
| `src/autoclave/core/steam.py` | Nuevo — función `p_saturacion_kpa()` |
| `src/autoclave/state_machine/cycle_phases/base_fase.py` | Agregar helper `_verificar_vapor_saturado()` |
| `src/autoclave/state_machine/cycle_phases/calentamiento.py` | Implementar lógica completa |
| `src/autoclave/state_machine/cycle_phases/estabilizacion.py` | Implementar lógica completa |
| `src/autoclave/state_machine/cycle_phases/esterilizacion.py` | Implementar lógica completa |
| `src/autoclave/cycles/factory/instrumental_134.json` | Agregar parámetros nuevos de esterilización |
| `src/autoclave/cycles/factory/bowe_dick.json` | Agregar parámetros nuevos de esterilización |

## Lo que NO cambia

- Interfaz `BaseFase` (`update()` / `reset()`)
- Orquestación en `CicloState`
- Estructura de alarmas existente
