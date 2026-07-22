# Modo de calibración de sensores desde la interfaz

## Contexto

El equipo permite hoy calibrar sensores de temperatura/presión únicamente
editando a mano `src/autoclave/config/calibration.yaml` (sección
`calibration.user`), sin trazabilidad de quién/cuándo lo cambió, y requiere
reiniciar el backend para que el cambio tome efecto (no hay recarga en
caliente). Este spec agrega un modo de calibración de 2 puntos accesible
desde la interfaz: el técnico entra a la pantalla de sensores de
temperatura o presión, hace clic sobre un sensor, y se abre una página
completa (no un diálogo emergente) donde ingresa los valores mostrados y
reales (equipo patrón) en un punto bajo y uno alto, ve el gain/offset
resultante, y guarda — el cambio se aplica de inmediato sin reiniciar.

Precedente inmediato: en esta misma sesión se recalibraron manualmente
`temp_camara` (reemplazando su ajuste cúbico de 5 puntos por una recta de
2 puntos) y `pres_camara`, editando `calibration.yaml` directamente. Este
spec formaliza ese mismo cálculo (invertir la calibración `user` vigente en
los dos puntos "mostrados" para obtener el valor de fábrica correspondiente,
y ajustar una recta nueva) en una herramienta reutilizable desde la UI para
cualquier sensor.

## Arquitectura

El backend (FastAPI, proceso separado de la interfaz PySide6, comunicados
por HTTP vía `BackendClient`) es quien aplica la calibración a cada lectura
(`hal/measures/converters.py`) a través del objeto `Units` vivo
(`context.units` en `backend/context.py`). Por lo tanto todo el cálculo,
escritura a disco y recarga en caliente debe vivir en el backend — la UI
solo recolecta los 4 valores y llama a un endpoint nuevo.

Flujo: técnico hace clic en una tarjeta de sensor → se abre
`CalibracionSensorView` (página completa) → ingresa 4 valores → la UI llama
`PATCH /calibration/{tipo}/{sensor}` → el backend calcula el nuevo
gain/offset, escribe solo la sección `calibration.user` del sensor afectado
en `calibration.yaml` (preservando comentarios existentes), recarga la
calibración en el `Units` vivo sin reiniciar nada, registra auditoría
(usuario + fecha) en SQLite, y responde con los valores nuevos para que la
UI los muestre de inmediato.

## Restricciones globales

- Solo se modifica la sección `calibration.user` del sensor calibrado —
  `calibration.factory` nunca se toca.
- Calibrar desde esta pantalla **siempre reemplaza** lo que hubiera antes
  (poly o gain/offset) por un gain/offset simple de 2 puntos — no hay
  soporte de más de 2 puntos ni de conservar un polinomio existente.
- Los campos "mostrado" se ingresan siempre a mano — sin autocompletar con
  la lectura en vivo.
- Solo usuarios con rol `admin` o `tecnico` (vía `SessionManager`) pueden
  entrar al modo de calibración.
- El cambio debe aplicarse de inmediato (recarga en caliente), sin reiniciar
  el backend ni la UI.
- Los comentarios existentes en `calibration.yaml` deben preservarse al
  guardar (se usa `ruamel.yaml` en modo round-trip, no `yaml.safe_dump`).
- Sensores calibrables: exactamente los que ya tienen tarjeta visible en
  `io_temp.py`/`io_pres.py`, es decir las claves de
  `EstadoAutoclave.map_temp` (`temp_camara`, `temp_2_camara`, `temp_ref`,
  `temp_chaqueta`, `temp_drenaje_cam`, `temp_drenaje`) y
  `EstadoAutoclave.map_pres` (`pres_camara`, `pres_chaqueta`,
  `pres_empaque_1`, `pres_empaque_2`). Los índices 6-7 (sin nombre asignado)
  no son alcanzables desde esta pantalla.

## Backend — matemática de calibración

Nuevo módulo `src/autoclave/hal/measures/calibration_tools.py`, con
funciones puras (sin I/O) que reutilizan exactamente el mismo orden de
coeficientes/Horner que `_user_calibrate` en `converters.py`, de modo que
la inversión sea consistente con lo que el pipeline en vivo realmente
calcula:

```python
def invert_user_calibration(
    shown_value: float, gain: float = 1.0, offset: float = 0.0,
    poly: list[float] | None = None,
) -> float:
    """Invierte la calibracion 'user' vigente (linear u poly) para obtener
    el valor de fabrica (salida de _factory_calibrate) que produce
    `shown_value` como lectura final. Recibe primitivos (no el objeto
    pydantic SensorCalibration) para poder reutilizarse tal cual tanto en
    el backend (extrayendo los campos del modelo) como en la UI
    (extrayendo los mismos campos del JSON que devuelve GET /calibration)."""
    if poly and len(poly) >= 2:
        return _invert_poly(poly, shown_value)
    if gain == 0:
        raise ValueError("La calibracion actual tiene gain=0; no se puede invertir")
    return (shown_value - offset) / gain


def _poly_eval(coeffs: list[float], x: float) -> float:
    result = 0.0
    for c in coeffs:
        result = result * x + c
    return result


def _poly_derivative_coeffs(poly: list[float]) -> list[float]:
    """poly = [c0..cn] en orden descendente (c0*x^n + ... + cn), igual que
    _user_calibrate. Retorna los coeficientes de la derivada, mismo orden."""
    n = len(poly) - 1
    return [c * (n - i) for i, c in enumerate(poly[:-1])]


def _invert_poly(poly: list[float], target: float, max_iter: int = 100) -> float:
    """Newton-Raphson: encuentra x tal que poly_eval(poly, x) == target.
    x0 = target (el polinomio de calibracion es una correccion pequena
    cerca de la identidad, por lo que target es una semilla razonable)."""
    deriv = _poly_derivative_coeffs(poly)
    x = target
    for _ in range(max_iter):
        fx = _poly_eval(poly, x) - target
        fpx = _poly_eval(deriv, x)
        if fpx == 0:
            raise ValueError("Derivada cero durante la inversion del polinomio")
        x_new = x - fx / fpx
        if abs(x_new - x) < 1e-9:
            return x_new
        x = x_new
    raise ValueError("La inversion del polinomio no convergio")


def fit_two_point(fv_low: float, real_low: float, fv_high: float, real_high: float) -> tuple[float, float]:
    """Ajusta gain/offset tales que gain*fv+offset reproduce real_low en
    fv_low y real_high en fv_high."""
    if fv_high == fv_low:
        raise ValueError("Los dos puntos de fabrica coinciden; no se puede calcular una recta")
    gain = (real_high - real_low) / (fv_high - fv_low)
    offset = real_low - gain * fv_low
    return gain, offset
```

Verificado manualmente en esta sesión con los datos reales de
`temp_camara` (poly) y `pres_camara` (linear) — ambos casos convergen y
reproducen exactamente los puntos de referencia dados.

## Backend — recarga en caliente

Nuevo método en `src/autoclave/hal/measures/units.py`:

```python
def reload_calibration(self, config_path: str | Path) -> None:
    """Recarga factory+user calibration desde disco sin recrear Units ni
    tocar la conexion serial (SerialLink vive fuera de este objeto)."""
    new_config = load_config(config_path)
    with self._lock:
        self._config = new_config
```

`converters.convert_temperatures`/`convert_pressures` ya leen `self._config`
en cada tick (`update_from_serial`), así que reasignar `self._config` (bajo
el mismo `_lock` que ya protege esos accesos) es suficiente para que el
siguiente dato de serial use la calibración nueva — no requiere reiniciar
`SerialLink` ni `ControlLoop`.

## Backend — endpoints nuevos

En `src/autoclave/backend/server.py`, usando `resource_path("autoclave/config/calibration.yaml")`
(mismo helper que usa `factory.py` para resolver la ruta real, incluyendo
el caso empaquetado con `sys._MEIPASS`) como ruta de lectura/escritura:

```python
CALIBRATION_PATH = resource_path("autoclave/config/calibration.yaml")

@app.get("/calibration/{tipo}/{sensor}")
def get_calibration(tipo: str, sensor: str):
    index = _resolve_sensor_index(tipo, sensor)   # 404 si tipo/sensor invalido
    config = load_config(CALIBRATION_PATH)
    calib = (config.calibration.user.temperature if tipo == "temperature"
             else config.calibration.user.pressure)[index]
    last = _calibration_audit_db.get_last_change(tipo, sensor)
    return {
        "sensor": sensor,
        "tipo": tipo,
        "is_poly": bool(calib.poly),
        "gain": calib.gain,
        "offset": calib.offset,
        "poly": calib.poly,   # coeficientes crudos si is_poly, si no None —
                               # la UI los necesita para poder invertir
                               # localmente y calcular la vista previa
        "last_change": last,   # {"usuario":..., "timestamp":...} o None
    }


@app.patch("/calibration/{tipo}/{sensor}")
def update_calibration(tipo: str, sensor: str, body: dict = Body(...)):
    index = _resolve_sensor_index(tipo, sensor)

    try:
        shown_low  = float(body["shown_low"]);  real_low  = float(body["real_low"])
        shown_high = float(body["shown_high"]); real_high = float(body["real_high"])
        usuario    = str(body.get("usuario", "Desconocido"))
    except (KeyError, TypeError, ValueError):
        raise HTTPException(422, "shown_low, real_low, shown_high, real_high son obligatorios y numericos")

    config = load_config(CALIBRATION_PATH)
    user_list = (config.calibration.user.temperature if tipo == "temperature"
                 else config.calibration.user.pressure)
    old_calib = user_list[index]
    old_gain, old_offset = getattr(old_calib, "gain", None), getattr(old_calib, "offset", None)

    try:
        old_poly = getattr(old_calib, "poly", None)
        fv_low  = invert_user_calibration(shown_low, old_calib.gain, old_calib.offset, old_poly)
        fv_high = invert_user_calibration(shown_high, old_calib.gain, old_calib.offset, old_poly)
        new_gain, new_offset = fit_two_point(fv_low, real_low, fv_high, real_high)
    except ValueError as e:
        raise HTTPException(422, str(e))

    _write_user_calibration_yaml(CALIBRATION_PATH, tipo, index, new_gain, new_offset,
                                  shown_low, real_low, shown_high, real_high)
    context.units.reload_calibration(CALIBRATION_PATH)
    _calibration_audit_db.log_change(
        tipo, sensor, shown_low, real_low, shown_high, real_high,
        old_gain, old_offset, new_gain, new_offset, usuario,
    )

    return {"ok": True, "gain": new_gain, "offset": new_offset}


def _resolve_sensor_index(tipo: str, sensor: str) -> int:
    name_map = {"temperature": EstadoAutoclave.map_temp, "pressure": EstadoAutoclave.map_pres}.get(tipo)
    if name_map is None:
        raise HTTPException(404, f"Tipo de sensor desconocido: {tipo}")
    if sensor not in name_map:
        raise HTTPException(404, f"Sensor desconocido: {sensor}")
    return name_map[sensor]
```

Nota: `usuario` viaja en el body del PATCH (no como header/token) porque
`SessionManager` es un singleton que vive únicamente en el proceso de la
UI — el backend (proceso FastAPI separado) no tiene acceso a él.

`_write_user_calibration_yaml` usa `ruamel.yaml` (`YAML(typ="rt")`) para
cargar, mutar solo `calibration.user.{temperature|pressure}[index]`
(reemplazando la entrada completa por un mapping `{gain, offset}` — se
descarta cualquier `poly`/`adc_min`/etc. previo en esa entrada) y volcar de
vuelta preservando el resto del árbol y sus comentarios. Se agrega un
comentario de una línea sobre la entrada modificada con fecha y los 4
valores usados, mismo espíritu que los comentarios ya escritos a mano hoy.

Nueva dependencia en `pyproject.toml`: `"ruamel.yaml"`.

## Backend — auditoría

Nuevo `src/autoclave/services/domain/logging/sensor_calibration_audit.py`,
mismo patrón que `cycle_params_audit.py`:

```python
_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS sensor_calibration_audit (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo        TEXT NOT NULL,
    sensor      TEXT NOT NULL,
    shown_low   REAL NOT NULL,
    real_low    REAL NOT NULL,
    shown_high  REAL NOT NULL,
    real_high   REAL NOT NULL,
    gain_anterior   REAL,
    offset_anterior REAL,
    gain_nuevo      REAL NOT NULL,
    offset_nuevo    REAL NOT NULL,
    usuario     TEXT NOT NULL,
    timestamp   TEXT NOT NULL
);
"""

class SensorCalibrationAuditDB:
    def __init__(self, db_path: Path = _DB_DEFAULT): ...
    def log_change(self, tipo, sensor, shown_low, real_low, shown_high, real_high,
                    gain_anterior, offset_anterior, gain_nuevo, offset_nuevo, usuario) -> None: ...
    def get_last_change(self, tipo: str, sensor: str) -> dict | None:
        """Retorna {'usuario':..., 'timestamp':...} del ultimo cambio, o None."""
```

`db_path` por defecto: `data/autoclave.db` (mismo archivo SQLite que ya usa
`cycle_params_audit.py`, tabla nueva y separada).

## UI — cliente HTTP

En `src/autoclave/ui/service_ui/backend_client.py`, dos métodos nuevos
siguiendo el estilo ya existente (`get_config`/`get_cycle`):

```python
def get_calibration(self, tipo: str, sensor: str) -> dict:
    return self.get(f"/calibration/{tipo}/{sensor}")

def save_calibration(self, tipo: str, sensor: str, body: dict) -> dict:
    return self.patch(f"/calibration/{tipo}/{sensor}", body)
```

## UI — navegación con payload

`MainWindowFluent.navigate_to` (`ui_pyside/main_window.py:176`) solo acepta
un `view_name: str`. Se extiende a:

```python
def navigate_to(self, view_name: str, payload: dict | None = None) -> None:
    views = { ... }  # sin cambios
    target = views.get(view_name)
    if target:
        if payload and hasattr(target, "set_context"):
            target.set_context(**payload)
        self._stack.setCurrentWidget(target)
```

Compatible con todas las llamadas existentes (`payload` por defecto
`None`). Se registra la nueva vista `self._calibracion_sensor` igual que
las demás (constructor con `nav_callback=self.navigate_to`, agregada al
`_stack`, entrada en el diccionario `views` con clave `"calibracion_sensor"`).

## UI — tarjetas de sensor clicables

En `io_temp.py`/`io_pres.py`, `_TempCard`/`_PresCard` ganan el mismo patrón
de `_ParamCard` (`params_ciclo.py:73-149`): `setCursor(PointingHandCursor)`,
`enterEvent`/`leaveEvent` para hover, y `mousePressEvent` que llama:

```python
self._nav("calibracion_sensor", {"tipo": "temperature", "sensor": name})
```

donde `name` es la clave completa ya usada internamente
(`"temp_camara"`, etc. — la misma que indexa `self._cards` en
`TemperaturasView`/`PresionesView`, sin necesidad de traducir a los alias
cortos que usa `/status`).

Nota menor de limpieza detectada durante la exploración: `io_pres.py:33`
tiene un `3333` huérfano entre clases — se elimina de paso al tocar ese
archivo (no es parte del alcance funcional, es basura evidente).

## UI — pantalla de calibración

Nueva vista `CalibracionSensorView` en
`src/autoclave/ui_pyside/views/entrdas_salidas/calibracion_sensor.py`,
página completa (no diálogo), con el mismo header patrón "← + título" que
`_MonitorBase`, pero back-target dinámico (vuelve a `io_temp` o `io_pres`
según de dónde vino, guardado en `set_context`):

- **Control de acceso**: en `set_context`/`showEvent`, si
  `not SessionManager.is_authenticated()` o
  `SessionManager.current_role() not in ("admin", "tecnico")`, se muestra
  un mensaje de acceso denegado (label centrado) en vez del formulario, y
  el formulario/botón guardar quedan ocultos.
- **Encabezado de info**: nombre del sensor, gain/offset actuales (o
  "polinomio (5 puntos)" si `is_poly`), y "Última modificación: {usuario} ·
  {timestamp}" o "Sin modificaciones previas" (via `GET /calibration/...`
  en `showEvent`/`set_context`).
- **Formulario** (`QFormLayout`, 4 `QDoubleSpinBox`): "Mostrado bajo",
  "Real bajo (patrón)", "Mostrado alto", "Real alto (patrón)" — todos
  vacíos al entrar (sin autocompletar).
- **Vista previa en vivo**: al cambiar cualquier campo, si los 4 tienen
  valor y `shown_low != shown_high`, se muestra el gain/offset resultante.
  Como la UI y el backend son el mismo paquete Python instalado (solo
  corren como procesos separados), la vista previa se calcula localmente
  en el proceso de la UI importando directamente
  `autoclave.hal.measures.calibration_tools` (`invert_user_calibration` +
  `fit_two_point`) con el `gain`/`offset`/`poly` ya obtenidos del
  `GET /calibration/...` inicial — sin round-trip de red por cada tecla,
  y sin mezclar lectura/escritura en el endpoint `PATCH`. Si los campos son
  inválidos (incompletos, `shown_low == shown_high`, o la inversión lanza
  `ValueError`), se oculta la vista previa y se deshabilita "Guardar".
- **Botón "Guardar"**: llama `save_calibration(tipo, sensor, {..., "usuario": ...})`
  con `usuario` resuelto igual que en `params_ciclo.py:318-323`
  (`SessionManager.current_user().get("nombre", "Desconocido")` si
  autenticado, si no `"Desconocido"` — aunque el control de acceso ya
  exige `admin`/`tecnico` autenticado antes de llegar aquí). Muestra el
  resultado (gain/offset nuevos) y refresca el encabezado de info
  (última modificación ahora es este cambio).

## Fuera de alcance

- No se agrega recarga en caliente de otros parámetros de configuración
  fuera de `calibration.yaml` (p. ej. `global_params.json` sigue con su
  mecanismo actual).
- No se agrega un histórico visual de calibraciones anteriores en la UI
  más allá de "última modificación" (la tabla SQLite sí guarda todas,
  pero no se expone un listado completo en esta iteración).
- No se soporta calibración de más de 2 puntos ni conservar polinomios
  desde esta pantalla.
- No se agrega control de acceso basado en roles a ninguna otra pantalla
  existente — solo a esta nueva.
- Los índices 6-7 de `calibration.yaml` (sin nombre asignado en
  `map_temp`/`map_pres`) no son alcanzables ni editables desde esta
  pantalla.

## Pruebas

- `tests/test_calibration_tools.py`: `invert_user_calibration` caso lineal
  y caso poly (usando el poly real de `temp_camara` antes de esta sesión
  como fixture), `fit_two_point` caso normal y caso `fv_high == fv_low`
  (`ValueError`), y un test de extremo a extremo reproduciendo los cálculos
  ya verificados manualmente para `temp_camara`/`pres_camara` (los mismos
  4 valores de esta conversación, verificando que se reproducen exactamente
  los gain/offset ya escritos en `calibration.yaml`).
- `tests/test_units_reload_calibration.py`: `Units.reload_calibration`
  cambia `self._config` y una llamada posterior a
  `update_from_serial`/`get_all` refleja la calibración nueva.
- `tests/test_sensor_calibration_audit.py`: mismo patrón que
  `test_cycle_params_audit.py` (log/retrieve, "sin historial" retorna
  `None`, "retorna el más reciente").
- `tests/test_backend_calibration_endpoints.py`: `GET`/`PATCH
  /calibration/{tipo}/{sensor}` vía `TestClient` de FastAPI — 404 con
  tipo/sensor inválido, 422 con campos faltantes o `shown_low==shown_high`,
  200 con payload válido y verificación de que el yaml en disco (tmp_path)
  cambió y que `context.units.reload_calibration` fue invocado.
- Tests de UI (PySide6, siguiendo el estilo de `tests/test_io_views.py`):
  tarjeta clicable navega con el payload correcto; `CalibracionSensorView`
  bloquea el formulario sin rol admin/tecnico; vista previa se calcula y
  se deshabilita "Guardar" con campos inválidos.
