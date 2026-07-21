# Suavizado adaptativo de sensores analógicos (temperatura / presión)

## Contexto

El equipo reporta variaciones de ±2°C y ±5kPa en los valores de temperatura/presión
ya calibrados y filtrados que se muestran en pantalla, se usan en el control de fases
y se imprimen en el ticket. La causa raíz es ruido de la tarjeta física en la
conversión ADC (fuera de alcance modificar hardware por ahora).

El pipeline actual (`src/autoclave/hal/measures/converters.py`) ya aplica:

```
raw ADC → MedianFilter(size=5) [pre-filtro, rechaza outliers puntuales]
        → calibración de fábrica + usuario
        → EMA de un solo polo (TEMP_ALPHA=0.15, PRES_ALPHA=0.2)
```

El EMA de un solo polo tiene un compromiso rígido entre velocidad de respuesta y
rechazo de ruido: con `alpha=0.15` el tiempo de asentamiento a un cambio real (95%)
es de ~9.2s (18-19 muestras a 500ms), ya por encima del margen de 2-5s deseado para
que el control de fases reaccione a cambios reales de temperatura/presión — y aun así
el ruido residual en régimen estable no baja lo suficiente (de ahí los ±2°C/±5kPa
reportados). Bajar más `alpha` reduciría el ruido pero empeoraría todavía más el
tiempo de respuesta ante cambios reales (arranque de calentamiento, apertura de
purga, etc.), lo cual no es aceptable para la lógica de control de fases.

Se decidió, en sesión de brainstorming con el usuario, reemplazar esa última etapa
por un **filtro adaptativo (One Euro Filter / "1€ Filter", Casiez et al. 2012)**:
suaviza fuerte cuando la señal está estática (ruido de fondo) y responde rápido
cuando detecta un cambio real, resolviendo el compromiso que un EMA de parámetro fijo
no puede resolver. Se descartaron dos alternativas más simples (solo retocar
constantes del EMA/mediana actuales, o reemplazar el EMA por un promedio móvil de
ventana fija) porque comparten la misma limitación estadística de fondo y no
resolverían el problema reportado dentro del margen de latencia aceptado. También se
descartó bifurcar en dos pipelines (uno rápido para control, uno suave para
pantalla/ticket) — el usuario prefirió mantener un único valor filtrado por
simplicidad.

## Alcance

Solo `src/autoclave/hal/measures/converters.py`:

- Se agrega la clase `OneEuroFilter`, junto a `MedianFilter`/`MovingAverage`.
- Se reemplaza el uso de `_ema()` + `_prev_temp_values`/`_prev_pres_values` por
  instancias de `OneEuroFilter` (una por canal, 8 temperatura + 8 presión).
- Se agregan constantes `TEMP_MINCUTOFF`, `TEMP_BETA`, `PRES_MINCUTOFF`,
  `PRES_BETA`, `DCUTOFF` (mismo patrón que las actuales `TEMP_ALPHA`/`PRES_ALPHA`:
  constantes de módulo, sin exponerlas en `calibration.yaml` todavía — YAGNI, se
  puede agregar después si hace falta ajustarlas sin redeploy).

No cambia:

- El pre-filtro de mediana sobre el ADC crudo (`MedianFilter(5)`), se mantiene igual.
- La calibración de fábrica/usuario (`_factory_calibrate`/`_user_calibrate`).
- La firma pública de `convert_temperatures()`/`convert_pressures()` (mismos
  parámetros, mismo tipo de retorno) — ningún consumidor aguas abajo (`units.py`,
  `control_loop.py`, UI, ticket) necesita cambios.
- La detección de sensor desconectado en temperatura (`raw==0` o `raw>=4095`).
- `MovingAverage` (código muerto hoy, se deja como está — no forma parte de este
  cambio).

## Diseño del `OneEuroFilter`

Algoritmo estándar (una instancia por canal, mantiene estado propio):

```python
class OneEuroFilter:
    def __init__(self, mincutoff: float, beta: float, dcutoff: float = 1.0):
        self.mincutoff = mincutoff
        self.beta = beta
        self.dcutoff = dcutoff
        self.x_prev: float | None = None
        self.dx_prev: float = 0.0
        self.t_prev: float | None = None

    def _alpha(self, cutoff: float, dt: float) -> float:
        tau = 1.0 / (2 * math.pi * cutoff)
        return 1.0 / (1.0 + tau / dt)

    def update(self, value: float, timestamp: float) -> float:
        if self.t_prev is None:
            self.x_prev = value
            self.t_prev = timestamp
            return value

        dt = max(timestamp - self.t_prev, 1e-3)
        dt = min(dt, MAX_DT)  # clamp ante gaps largos (freeze/reconexión)

        dx = (value - self.x_prev) / dt
        a_d = self._alpha(self.dcutoff, dt)
        edx = a_d * dx + (1 - a_d) * self.dx_prev

        cutoff = self.mincutoff + self.beta * abs(edx)
        a = self._alpha(cutoff, dt)
        x_hat = a * value + (1 - a) * self.x_prev

        self.x_prev, self.dx_prev, self.t_prev = x_hat, edx, timestamp
        return x_hat

    def reset(self) -> None:
        self.x_prev = None
        self.dx_prev = 0.0
        self.t_prev = None
```

- `timestamp` se pasa explícitamente (no `time.monotonic()` interno a la clase) para
  que los tests puedan controlar el tiempo sin mockear el reloj del sistema.
- `MAX_DT` (constante, propuesta 2.0s): si el hilo se congela o hay una reconexión
  serial larga, evita que un `dt` gigante genere una `dx` artificialmente enorme al
  volver, lo que dispararía el `cutoff` (y por ende el suavizado se apagaría de golpe
  en el peor momento).
- Primera lectura real: arranca directo en el valor, sin rampa inicial (igual que el
  comportamiento actual del EMA).

## Integración en `convert_temperatures`/`convert_pressures`

- `_oe_temp: List[OneEuroFilter]` y `_oe_pres: List[OneEuroFilter]` (8 instancias
  cada uno) reemplazan a `_prev_temp_values`/`_prev_pres_values`.
- `timestamp = time.monotonic()` se captura una vez al entrar a cada función y se
  pasa a `update()` de cada canal (todos los canales de una misma lectura comparten
  el mismo timestamp).
- Temperatura: al detectar sensor desconectado (`raw==0` o `raw>=4095`), además de
  limpiar el buffer de mediana (como hoy), se llama `_oe_temp[i].reset()` — mismo
  propósito que hoy tiene poner `_prev_temp_values[i] = None`, pero también limpia
  `dx_prev`/`t_prev` para que la reconexión no herede una derivada o un `dt` viejo.
- Presión: no tiene hoy detección de desconexión (fuera de alcance agregarla en este
  cambio); simplemente se reemplaza el EMA por `_oe_pres[i].update(...)`.

## Valores iniciales de `mincutoff`/`beta`

Puntos de partida razonables, **no calibrados con datos reales** (no hay telemetría
del ruido real de este equipo disponible en esta sesión):

| Constante | Valor inicial | Razonamiento |
|---|---|---|
| `TEMP_MINCUTOFF` | 0.05 Hz | Suavizado fuerte en reposo (temperatura cambia lento) |
| `TEMP_BETA` | 0.02 | Respuesta más rápida solo ante rampas reales de calentamiento |
| `PRES_MINCUTOFF` | 0.1 Hz | Algo menos agresivo que temperatura — presión cambia más rápido |
| `PRES_BETA` | 0.05 | Mayor sensibilidad a cambios reales (purga, vacío) |
| `DCUTOFF` | 1.0 Hz | Valor estándar del algoritmo original, rara vez necesita ajuste |
| `MAX_DT` | 2.0 s | Tope de gap de tiempo entre lecturas consecutivas |

**Estos valores requieren una pasada de calibración empírica después de implementar**:
loguear valor crudo + filtrado durante (a) el equipo en reposo/estable y (b) una
rampa de calentamiento real, y ajustar `mincutoff`/`beta` según el ruido y la
velocidad de cambio real observados. Se deja como tarea de seguimiento, no bloquea
la implementación inicial.

## Fuera de alcance

- Exponer `mincutoff`/`beta`/`MAX_DT` en `calibration.yaml` (se mantienen como
  constantes de módulo por ahora, YAGNI).
- Agregar detección de sensor desconectado a presión (inconsistencia preexistente,
  no relacionada a este cambio).
- Aumentar el promedio de muestras en firmware (`ADC_SAMPLES` en el `.ino`) — fuera
  de alcance por decisión explícita del usuario (no hay acceso a modificar hardware
  ahora).
- Bifurcar el pipeline en un valor "rápido" (control) y uno "suave" (display/ticket)
  — descartado en brainstorming, se mantiene un único valor filtrado.
- El parámetro fantasma `sampling_interval_ms` en `calibration.yaml`/`schema.py`
  (definido pero nunca consumido) — no relacionado a este cambio, no se toca.

## Testing

`tests/test_converters_realistic.py` (o un archivo nuevo `tests/test_one_euro_filter.py`
para los unitarios aislados):

1. **`OneEuroFilter` aislado, señal plana + ruido**: alimentar una secuencia con
   pequeñas variaciones aleatorias alrededor de un valor constante → confirmar que la
   salida varía sensiblemente menos que la entrada (suavizado fuerte en reposo).
2. **`OneEuroFilter` aislado, escalón**: alimentar un cambio real tipo escalón →
   confirmar que la salida llega al nuevo valor notablemente más rápido que el EMA
   actual (`alpha=0.15`) para una señal equivalente.
3. **`reset()`**: confirmar que tras `reset()`, la siguiente lectura arranca directo
   en el valor nuevo (sin rampa), y que el estado interno (`x_prev`, `dx_prev`,
   `t_prev`) vuelve a `None`/`0.0`.
4. **`dt` clamp**: simular un gap de tiempo mayor a `MAX_DT` entre dos `update()` →
   confirmar que no se dispara un `cutoff` desproporcionado (comparar contra el caso
   sin clamp).
5. **Integración `convert_temperatures`**: reemplazo del EMA verificado end-to-end;
   desconexión (`raw=0`)/reconexión de un canal → confirmar que `reset()` se invoca y
   no hay salto artificial al reconectar.
6. **Integración `convert_pressures`**: mismo reemplazo, sin lógica de desconexión
   (no aplica).
7. Suite completa (`pytest tests/`) debe seguir pasando.
