# Modo de calibración de sensores desde la interfaz — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Agregar un modo de calibración de 2 puntos accesible desde la interfaz — clic en una tarjeta de sensor (temperatura/presión) abre una página completa donde el técnico ingresa valor mostrado/real en un punto bajo y uno alto, ve el gain/offset resultante, y guarda; el cambio se aplica de inmediato (recarga en caliente del backend) con auditoría de usuario/fecha.

**Architecture:** Backend (FastAPI) nuevo: módulo puro de matemática de calibración (invierte la calibración `user` vigente — lineal o polinomio — en los dos puntos dados y ajusta una recta nueva), método de recarga en caliente en `Units`, escritura a `calibration.yaml` con `ruamel.yaml` (preserva comentarios), auditoría SQLite, y dos endpoints HTTP. UI (PySide6) nueva: tarjetas de sensor clicables, navegación con payload, página completa `CalibracionSensorView` con control de acceso por rol.

**Tech Stack:** Python 3.14, FastAPI, pydantic, PySide6, pytest, ruamel.yaml (nueva dependencia), SQLite.

## Global Constraints

- Solo se modifica `calibration.user` del sensor calibrado — `calibration.factory` nunca se toca.
- Calibrar desde esta pantalla siempre reemplaza lo que hubiera (poly o gain/offset) por un gain/offset simple de 2 puntos.
- Los campos "mostrado" se ingresan siempre a mano — sin autocompletar con la lectura en vivo.
- Solo usuarios con rol `admin` o `tecnico` (vía `SessionManager`) pueden entrar al modo de calibración.
- El cambio se aplica de inmediato (recarga en caliente vía `Units.reload_calibration`), sin reiniciar backend ni UI.
- Los comentarios existentes en `calibration.yaml` deben preservarse al guardar (usar `ruamel.yaml` round-trip, nunca `yaml.safe_dump`).
- Sensores calibrables: exactamente las claves de `EstadoAutoclave.map_temp` (`temp_camara`, `temp_2_camara`, `temp_ref`, `temp_chaqueta`, `temp_drenaje_cam`, `temp_drenaje`) y `EstadoAutoclave.map_pres` (`pres_camara`, `pres_chaqueta`, `pres_empaque_1`, `pres_empaque_2`).
- Spec completo: `docs/superpowers/specs/2026-07-22-calibracion-sensores-ui-design.md`.
- El entorno de desarrollo estaba roto (editable install de `autoclave` apuntando a un worktree borrado) y ya fue reparado (`pip install -e .` desde la raíz del repo). Baseline real de la suite: 411 passed, 19 failed en `tests/test_io_views.py` (archivo obsoleto, rutas de import de antes de una reestructuración de módulos — preexistente, no relacionado con este plan, no intentar arreglarlo).

---

### Task 1: `calibration_tools.py` — matemática pura de calibración

**Files:**
- Create: `src/autoclave/hal/measures/calibration_tools.py`
- Test: `tests/test_calibration_tools.py`

**Interfaces:**
- Produces: `invert_user_calibration(shown_value: float, gain: float = 1.0, offset: float = 0.0, poly: list[float] | None = None) -> float`, `fit_two_point(fv_low: float, real_low: float, fv_high: float, real_high: float) -> tuple[float, float]`. Ambas lanzan `ValueError` en casos inválidos (gain=0, fv_high==fv_low, derivada cero, no convergencia).

- [ ] **Step 1: Escribir los tests que fallan**

Crear `tests/test_calibration_tools.py`:

```python
import pytest
from autoclave.hal.measures.calibration_tools import invert_user_calibration, fit_two_point


def test_invert_lineal():
    # pres_camara antes de esta sesion: gain=1.3466, offset=-67.11
    fv = invert_user_calibration(12.0, gain=1.3466, offset=-67.11)
    assert fv == pytest.approx(58.747958, abs=1e-5)


def test_invert_lineal_gain_cero_lanza_valueerror():
    with pytest.raises(ValueError):
        invert_user_calibration(20.0, gain=0.0, offset=0.0)


def test_invert_poly_temp_camara():
    # poly real de temp_camara antes de esta sesion (5 puntos: 2,70,100,120,135 C)
    poly = [2.046e-05, -0.00511265, 1.35714148, -3.74342417]
    fv_low = invert_user_calibration(20.0, poly=poly)
    fv_high = invert_user_calibration(131.3, poly=poly)
    assert fv_low == pytest.approx(18.715942, abs=1e-5)
    assert fv_high == pytest.approx(130.064013, abs=1e-5)


def test_fit_two_point_normal():
    gain, offset = fit_two_point(58.747958, 9.54, 288.957374, 300.0)
    assert gain == pytest.approx(1.261721, abs=1e-5)
    assert offset == pytest.approx(-64.583518, abs=1e-4)


def test_fit_two_point_puntos_iguales_lanza_valueerror():
    with pytest.raises(ValueError):
        fit_two_point(50.0, 10.0, 50.0, 20.0)


def test_extremo_a_extremo_temp_camara_reproduce_calibration_yaml():
    """Reproduce el calculo verificado manualmente en esta sesion para
    temp_camara: bajo 20.0->20.0, alto 131.3->132.5, reemplazando el poly
    de 5 puntos. Debe dar el gain/offset ya escrito en calibration.yaml."""
    poly = [2.046e-05, -0.00511265, 1.35714148, -3.74342417]
    fv_low = invert_user_calibration(20.0, poly=poly)
    fv_high = invert_user_calibration(131.3, poly=poly)
    gain, offset = fit_two_point(fv_low, 20.0, fv_high, 132.5)
    assert round(gain, 6) == pytest.approx(1.010345, abs=1e-6)
    assert round(offset, 6) == pytest.approx(1.090435, abs=1e-6)


def test_extremo_a_extremo_pres_camara_reproduce_calibration_yaml():
    """Idem para pres_camara: bajo 12->9.54, alto 322->300, con la
    calibracion previa gain=1.3466/offset=-67.11."""
    fv_low = invert_user_calibration(12.0, gain=1.3466, offset=-67.11)
    fv_high = invert_user_calibration(322.0, gain=1.3466, offset=-67.11)
    gain, offset = fit_two_point(fv_low, 9.54, fv_high, 300.0)
    assert round(gain, 6) == pytest.approx(1.261721, abs=1e-6)
    assert round(offset, 6) == pytest.approx(-64.583518, abs=1e-5)
```

- [ ] **Step 2: Ejecutar y verificar que fallan**

Run: `python -m pytest tests/test_calibration_tools.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'autoclave.hal.measures.calibration_tools'`

- [ ] **Step 3: Implementar**

Crear `src/autoclave/hal/measures/calibration_tools.py`:

```python
"""
autoclave.hal.measures.calibration_tools
-----------------------------------------
Funciones puras (sin I/O) para el modo de calibracion de 2 puntos: invierte
la calibracion 'user' vigente de un sensor (lineal o polinomio) en los
valores "mostrados" dados por el tecnico, y ajusta una recta nueva contra
los valores "reales" (equipo patron). Usa el mismo orden de coeficientes
que _user_calibrate en converters.py (Horner, orden descendente).
"""


def invert_user_calibration(
    shown_value: float,
    gain: float = 1.0,
    offset: float = 0.0,
    poly: list[float] | None = None,
) -> float:
    """Invierte la calibracion 'user' vigente (lineal u poly) para obtener
    el valor de fabrica (salida de _factory_calibrate) que produce
    `shown_value` como lectura final."""
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
    """Newton-Raphson: encuentra x tal que _poly_eval(poly, x) == target.
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

- [ ] **Step 4: Ejecutar y verificar que pasan**

Run: `python -m pytest tests/test_calibration_tools.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add src/autoclave/hal/measures/calibration_tools.py tests/test_calibration_tools.py
git commit -m "feat: agregar matematica pura de calibracion de 2 puntos"
```

---

### Task 2: `Units.reload_calibration()` — recarga en caliente

**Files:**
- Modify: `src/autoclave/hal/measures/units.py`
- Test: `tests/test_units_reload_calibration.py`

**Interfaces:**
- Consumes: `load_config` de `autoclave.config` (ya existente, sin cambios de firma).
- Produces: `Units.reload_calibration(self, config_path: str | Path) -> None`.

- [ ] **Step 1: Escribir el test que falla**

Crear `tests/test_units_reload_calibration.py`:

```python
import textwrap
from autoclave.hal.measures.units import Units


def test_reload_calibration_actualiza_config(tmp_path):
    yaml_a = tmp_path / "a.yaml"
    yaml_a.write_text(textwrap.dedent("""
        calibration:
          user:
            pressure:
              - gain: 1.0
                offset: 0.0
    """), encoding="utf-8")

    yaml_b = tmp_path / "b.yaml"
    yaml_b.write_text(textwrap.dedent("""
        calibration:
          user:
            pressure:
              - gain: 2.5
                offset: -10.0
    """), encoding="utf-8")

    units = Units(str(yaml_a))
    assert units._config.calibration.user.pressure[0].gain == 1.0
    assert units._config.calibration.user.pressure[0].offset == 0.0

    units.reload_calibration(str(yaml_b))
    assert units._config.calibration.user.pressure[0].gain == 2.5
    assert units._config.calibration.user.pressure[0].offset == -10.0
```

- [ ] **Step 2: Ejecutar y verificar que falla**

Run: `python -m pytest tests/test_units_reload_calibration.py -v`
Expected: FAIL — `AttributeError: 'Units' object has no attribute 'reload_calibration'`

- [ ] **Step 3: Implementar**

En `src/autoclave/hal/measures/units.py`, agregar este método dentro de la clase `Units` (después de `__init__`, junto a `update_from_serial`):

```python
    def reload_calibration(self, config_path: str | Path) -> None:
        """Recarga factory+user calibration desde disco sin recrear Units
        ni tocar la conexion serial (SerialLink vive fuera de este objeto).
        Seguro de llamar mientras update_from_serial corre en otro hilo."""
        new_config = load_config(config_path)
        with self._lock:
            self._config = new_config
```

- [ ] **Step 4: Ejecutar y verificar que pasa**

Run: `python -m pytest tests/test_units_reload_calibration.py -v`
Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
git add src/autoclave/hal/measures/units.py tests/test_units_reload_calibration.py
git commit -m "feat: agregar recarga en caliente de calibracion en Units"
```

---

### Task 3: `SensorCalibrationAuditDB` — auditoría SQLite

**Files:**
- Create: `src/autoclave/services/domain/logging/sensor_calibration_audit.py`
- Test: `tests/test_sensor_calibration_audit.py`

**Interfaces:**
- Produces: `SensorCalibrationAuditDB(db_path=_DB_DEFAULT)`, `.log_change(tipo, sensor, shown_low, real_low, shown_high, real_high, gain_anterior, offset_anterior, gain_nuevo, offset_nuevo, usuario) -> None`, `.get_last_change(tipo, sensor) -> dict | None` (retorna `{"usuario":..., "timestamp":...}`).

- [ ] **Step 1: Escribir los tests que fallan**

Crear `tests/test_sensor_calibration_audit.py` (mismo patrón que `tests/test_cycle_params_audit.py`):

```python
import pytest
from autoclave.services.domain.logging.sensor_calibration_audit import SensorCalibrationAuditDB


@pytest.fixture
def db(tmp_path):
    return SensorCalibrationAuditDB(db_path=tmp_path / "test.db")


def test_get_last_change_returns_none_when_no_history(db):
    assert db.get_last_change("temperature", "temp_camara") is None


def test_log_and_retrieve_last_change(db):
    db.log_change(
        "temperature", "temp_camara", 20.0, 20.0, 131.3, 132.5,
        None, None, 1.010345, 1.090435, "admin",
    )
    result = db.get_last_change("temperature", "temp_camara")
    assert result is not None
    assert result["usuario"] == "admin"
    assert len(result["timestamp"]) == 16   # "YYYY-MM-DD HH:MM"


def test_get_last_change_returns_most_recent(db):
    db.log_change("pressure", "pres_camara", 12.0, 9.0, 322.0, 299.0,
                   1.3466, -67.11, 1.26, -64.5, "user1")
    db.log_change("pressure", "pres_camara", 12.0, 9.54, 322.0, 300.0,
                   1.26, -64.5, 1.261721, -64.583518, "user2")
    assert db.get_last_change("pressure", "pres_camara")["usuario"] == "user2"


def test_get_last_change_distingue_por_sensor(db):
    db.log_change("temperature", "temp_camara", 20.0, 20.0, 131.3, 132.5,
                   None, None, 1.010345, 1.090435, "admin")
    assert db.get_last_change("temperature", "temp_chaqueta") is None
```

- [ ] **Step 2: Ejecutar y verificar que fallan**

Run: `python -m pytest tests/test_sensor_calibration_audit.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implementar**

Crear `src/autoclave/services/domain/logging/sensor_calibration_audit.py`:

```python
import sqlite3
from datetime import datetime
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[5]
_DB_DEFAULT   = _PROJECT_ROOT / "data" / "autoclave.db"

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS sensor_calibration_audit (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo            TEXT NOT NULL,
    sensor          TEXT NOT NULL,
    shown_low       REAL NOT NULL,
    real_low        REAL NOT NULL,
    shown_high      REAL NOT NULL,
    real_high       REAL NOT NULL,
    gain_anterior   REAL,
    offset_anterior REAL,
    gain_nuevo      REAL NOT NULL,
    offset_nuevo    REAL NOT NULL,
    usuario         TEXT NOT NULL,
    timestamp       TEXT NOT NULL
);
"""


class SensorCalibrationAuditDB:
    def __init__(self, db_path: Path = _DB_DEFAULT):
        self._db_path = db_path
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(_CREATE_TABLE)

    def log_change(
        self,
        tipo: str,
        sensor: str,
        shown_low: float,
        real_low: float,
        shown_high: float,
        real_high: float,
        gain_anterior,
        offset_anterior,
        gain_nuevo: float,
        offset_nuevo: float,
        usuario: str,
    ) -> None:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "INSERT INTO sensor_calibration_audit "
                "(tipo, sensor, shown_low, real_low, shown_high, real_high, "
                " gain_anterior, offset_anterior, gain_nuevo, offset_nuevo, usuario, timestamp) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (tipo, sensor, shown_low, real_low, shown_high, real_high,
                 gain_anterior, offset_anterior, gain_nuevo, offset_nuevo, usuario, ts),
            )

    def get_last_change(self, tipo: str, sensor: str) -> dict | None:
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT usuario, timestamp FROM sensor_calibration_audit "
                "WHERE tipo=? AND sensor=? "
                "ORDER BY timestamp DESC, id DESC LIMIT 1",
                (tipo, sensor),
            ).fetchone()
        return {"usuario": row[0], "timestamp": row[1]} if row else None
```

- [ ] **Step 4: Ejecutar y verificar que pasan**

Run: `python -m pytest tests/test_sensor_calibration_audit.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/autoclave/services/domain/logging/sensor_calibration_audit.py tests/test_sensor_calibration_audit.py
git commit -m "feat: agregar auditoria SQLite para calibracion de sensores"
```

---

### Task 4: Escritura de `calibration.yaml` preservando comentarios (ruamel.yaml)

**Files:**
- Modify: `pyproject.toml` (agregar dependencia `ruamel.yaml`)
- Create: `src/autoclave/config/calibration_writer.py`
- Test: `tests/test_calibration_writer.py`

**Interfaces:**
- Produces: `write_user_calibration(yaml_path, tipo: str, index: int, gain: float, offset: float, shown_low: float, real_low: float, shown_high: float, real_high: float) -> None`. `tipo` es `"temperature"` o `"pressure"`.

- [ ] **Step 1: Agregar la dependencia**

En `pyproject.toml`, en la lista `dependencies` (línea 16-28), agregar `"ruamel.yaml"` después de `"PyYAML"`:

```toml
dependencies = [ #Lista de dependencias del paquete
  "pyserial",
  "tk",
  "pillow",
  "PyYAML",
  "ruamel.yaml",
  "SQLAlchemy",
  "pydantic",
  "PySide6",
  "PySide6-Fluent-Widgets[full]",
  "pyqtgraph",
  "keyring",
  "pywin32"
]
```

Run: `pip install ruamel.yaml` (ya verificado instalable en este entorno — versión 0.19.1).

- [ ] **Step 2: Escribir los tests que fallan**

Crear `tests/test_calibration_writer.py`:

```python
import textwrap
from autoclave.config.calibration_writer import write_user_calibration


def _make_yaml(tmp_path):
    path = tmp_path / "calibration.yaml"
    path.write_text(textwrap.dedent("""
        calibration:
          user:
            temperature:
              # Sensor 0 -- calibrado con 5 puntos, no tocar sin patron
              - poly: [2.046e-05, -0.00511265, 1.35714148, -3.74342417]
              - gain: 1.0
                offset: 0.0
            pressure:
              - gain: 1.3466
                offset: -67.11
              - gain: 1.3466
                offset: -67.11
    """), encoding="utf-8")
    return path


def test_reemplaza_poly_por_gain_offset(tmp_path):
    path = _make_yaml(tmp_path)
    write_user_calibration(path, "temperature", 0, 1.010345, 1.090435,
                            20.0, 20.0, 131.3, 132.5)

    from ruamel.yaml import YAML
    yaml = YAML(typ="safe")
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.load(f)

    entry = data["calibration"]["user"]["temperature"][0]
    assert entry["gain"] == 1.010345
    assert entry["offset"] == 1.090435
    assert "poly" not in entry


def test_no_toca_otros_sensores(tmp_path):
    path = _make_yaml(tmp_path)
    write_user_calibration(path, "pressure", 0, 1.261721, -64.583518,
                            12.0, 9.54, 322.0, 300.0)

    from ruamel.yaml import YAML
    yaml = YAML(typ="safe")
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.load(f)

    # sensor 1 de pressure no cambio
    assert data["calibration"]["user"]["pressure"][1]["gain"] == 1.3466
    # sensor 1 de temperature (gain/offset simple) no cambio
    assert data["calibration"]["user"]["temperature"][1]["gain"] == 1.0


def test_preserva_comentarios_existentes(tmp_path):
    path = _make_yaml(tmp_path)
    write_user_calibration(path, "pressure", 0, 1.261721, -64.583518,
                            12.0, 9.54, 322.0, 300.0)

    texto = path.read_text(encoding="utf-8")
    assert "calibrado con 5 puntos" in texto


def test_agrega_comentario_de_trazabilidad(tmp_path):
    path = _make_yaml(tmp_path)
    write_user_calibration(path, "pressure", 0, 1.261721, -64.583518,
                            12.0, 9.54, 322.0, 300.0)

    texto = path.read_text(encoding="utf-8")
    assert "12.0" in texto and "300.0" in texto
```

- [ ] **Step 3: Ejecutar y verificar que fallan**

Run: `python -m pytest tests/test_calibration_writer.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'autoclave.config.calibration_writer'`

- [ ] **Step 4: Implementar**

Crear `src/autoclave/config/calibration_writer.py`:

```python
"""
autoclave.config.calibration_writer
------------------------------------
Escribe de vuelta a calibration.yaml usando ruamel.yaml en modo round-trip,
preservando comentarios y formato existentes. Reemplaza por completo la
entrada del sensor calibrado (descarta poly/adc_min/etc previos) por un
mapping simple {gain, offset}.
"""

from datetime import date
from pathlib import Path

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap

_SECCION_POR_TIPO = {"temperature": "temperature", "pressure": "pressure"}


def write_user_calibration(
    yaml_path: str | Path,
    tipo: str,
    index: int,
    gain: float,
    offset: float,
    shown_low: float,
    real_low: float,
    shown_high: float,
    real_high: float,
) -> None:
    seccion = _SECCION_POR_TIPO[tipo]

    yaml = YAML(typ="rt")
    yaml.preserve_quotes = True

    yaml_path = Path(yaml_path)
    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.load(f)

    seq = data["calibration"]["user"][seccion]

    nuevo = CommentedMap()
    nuevo["gain"] = round(gain, 6)
    nuevo["offset"] = round(offset, 6)
    seq[index] = nuevo

    comentario = (
        f"Sensor {index} -- recalibrado {date.today().isoformat()} con 2 puntos "
        f"contra equipo patron: bajo {shown_low}->{real_low}, "
        f"alto {shown_high}->{real_high}."
    )
    seq.yaml_set_comment_before_after_key(index, before=comentario)

    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f)
```

- [ ] **Step 5: Ejecutar y verificar que pasan**

Run: `python -m pytest tests/test_calibration_writer.py -v`
Expected: 4 passed

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml src/autoclave/config/calibration_writer.py tests/test_calibration_writer.py
git commit -m "feat: escribir calibration.yaml preservando comentarios con ruamel.yaml"
```

---

### Task 5: Endpoints backend `GET`/`PATCH /calibration/{tipo}/{sensor}`

**Files:**
- Modify: `src/autoclave/backend/context.py` (agregar `self.calibration_audit`)
- Modify: `src/autoclave/backend/server.py` (agregar 2 endpoints)
- Test: `tests/test_backend_calibration_endpoints.py`

**Interfaces:**
- Consumes: `invert_user_calibration`/`fit_two_point` (Task 1), `Units.reload_calibration` (Task 2), `SensorCalibrationAuditDB` (Task 3), `write_user_calibration` (Task 4).
- Produces: `GET /calibration/{tipo}/{sensor}` → `{"sensor","tipo","is_poly","gain","offset","poly","last_change"}`. `PATCH /calibration/{tipo}/{sensor}` con body `{"shown_low","real_low","shown_high","real_high","usuario"}` → `{"ok": true, "gain", "offset"}`; 404 si tipo/sensor desconocido, 422 si faltan campos o `shown_low == shown_high` o falla la inversión.

- [ ] **Step 1: Escribir los tests que fallan**

Crear `tests/test_backend_calibration_endpoints.py` (mismo patrón que `tests/test_io_endpoints.py`):

```python
import sys
import importlib
import textwrap
import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def calib_client(tmp_path):
    yaml_path = tmp_path / "calibration.yaml"
    yaml_path.write_text(textwrap.dedent("""
        calibration:
          user:
            temperature:
              - gain: 1.0
                offset: 0.0
            pressure:
              - gain: 1.3466
                offset: -67.11
    """), encoding="utf-8")

    mock_ctx = MagicMock()

    for key in list(sys.modules):
        if "autoclave.backend.server" in key:
            del sys.modules[key]

    with patch("autoclave.backend.context.BackendContext", return_value=mock_ctx):
        srv = importlib.import_module("autoclave.backend.server")

    srv.CALIBRATION_PATH = yaml_path

    from fastapi.testclient import TestClient
    return TestClient(srv.app), mock_ctx, yaml_path


def test_get_calibration_404_tipo_invalido(calib_client):
    client, _, _ = calib_client
    resp = client.get("/calibration/no_existe/temp_camara")
    assert resp.status_code == 404


def test_get_calibration_404_sensor_invalido(calib_client):
    client, _, _ = calib_client
    resp = client.get("/calibration/temperature/no_existe")
    assert resp.status_code == 404


def test_get_calibration_devuelve_valores_actuales(calib_client):
    client, mock_ctx, _ = calib_client
    mock_ctx.calibration_audit.get_last_change.return_value = None
    resp = client.get("/calibration/pressure/pres_camara")
    assert resp.status_code == 200
    data = resp.json()
    assert data["gain"] == 1.3466
    assert data["offset"] == -67.11
    assert data["is_poly"] is False
    assert data["poly"] is None
    assert data["last_change"] is None


def test_patch_calibration_422_valores_faltantes(calib_client):
    client, _, _ = calib_client
    resp = client.patch("/calibration/pressure/pres_camara", json={"shown_low": 12.0})
    assert resp.status_code == 422


def test_patch_calibration_422_puntos_iguales(calib_client):
    client, _, _ = calib_client
    resp = client.patch("/calibration/pressure/pres_camara", json={
        "shown_low": 12.0, "real_low": 9.54, "shown_high": 12.0, "real_high": 300.0,
    })
    assert resp.status_code == 422


def test_patch_calibration_actualiza_yaml_recarga_y_audita(calib_client):
    client, mock_ctx, yaml_path = calib_client
    resp = client.patch("/calibration/pressure/pres_camara", json={
        "shown_low": 12.0, "real_low": 9.54, "shown_high": 322.0, "real_high": 300.0,
        "usuario": "tecnico1",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert round(data["gain"], 6) == pytest.approx(1.261721, abs=1e-6)
    assert round(data["offset"], 6) == pytest.approx(-64.583518, abs=1e-5)

    on_disk = yaml_path.read_text(encoding="utf-8")
    assert "1.261721" in on_disk

    mock_ctx.units.reload_calibration.assert_called_once_with(yaml_path)

    mock_ctx.calibration_audit.log_change.assert_called_once()
    args = mock_ctx.calibration_audit.log_change.call_args.args
    assert args[0] == "pressure"
    assert args[1] == "pres_camara"
    assert args[-1] == "tecnico1"
```

- [ ] **Step 2: Ejecutar y verificar que fallan**

Run: `python -m pytest tests/test_backend_calibration_endpoints.py -v`
Expected: FAIL — 404s en vez de 200 (los endpoints no existen aún)

- [ ] **Step 3: Implementar**

En `src/autoclave/backend/context.py`, agregar el import y una línea en `__init__` (junto a `self.db = DbManager()`, línea 72):

```python
from autoclave.services.domain.logging.sensor_calibration_audit import SensorCalibrationAuditDB
```

```python
        self.db               = DbManager()
        self.calibration_audit = SensorCalibrationAuditDB()
        self.realtime_printer = RealtimePrinter()
```

En `src/autoclave/backend/server.py`, agregar imports (junto a los existentes, línea 10-12):

```python
from autoclave.hal.measures.calibration_tools import invert_user_calibration, fit_two_point
from autoclave.config.calibration_writer import write_user_calibration
from autoclave.config import load_config
from autoclave.utils.resources import resource_path
```

Agregar después de `context = BackendContext()` (línea 20):

```python
CALIBRATION_PATH = resource_path("autoclave/config/calibration.yaml")


def _resolve_sensor_index(tipo: str, sensor: str) -> int:
    name_map = {"temperature": EstadoAutoclave.map_temp, "pressure": EstadoAutoclave.map_pres}.get(tipo)
    if name_map is None:
        raise HTTPException(status_code=404, detail=f"Tipo de sensor desconocido: {tipo}")
    if sensor not in name_map:
        raise HTTPException(status_code=404, detail=f"Sensor desconocido: {sensor}")
    return name_map[sensor]


@app.get("/calibration/{tipo}/{sensor}")
def get_calibration(tipo: str, sensor: str):
    index = _resolve_sensor_index(tipo, sensor)
    config = load_config(CALIBRATION_PATH)
    calib = (config.calibration.user.temperature if tipo == "temperature"
             else config.calibration.user.pressure)[index]
    last = context.calibration_audit.get_last_change(tipo, sensor)
    return {
        "sensor": sensor,
        "tipo": tipo,
        "is_poly": bool(calib.poly),
        "gain": calib.gain,
        "offset": calib.offset,
        "poly": calib.poly,
        "last_change": last,
    }


@app.patch("/calibration/{tipo}/{sensor}")
def update_calibration(tipo: str, sensor: str, body: dict = Body(...)):
    index = _resolve_sensor_index(tipo, sensor)

    try:
        shown_low  = float(body["shown_low"]);  real_low  = float(body["real_low"])
        shown_high = float(body["shown_high"]); real_high = float(body["real_high"])
    except (KeyError, TypeError, ValueError):
        raise HTTPException(
            status_code=422,
            detail="shown_low, real_low, shown_high, real_high son obligatorios y numericos",
        )
    usuario = str(body.get("usuario", "Desconocido"))

    config = load_config(CALIBRATION_PATH)
    user_list = (config.calibration.user.temperature if tipo == "temperature"
                 else config.calibration.user.pressure)
    old_calib = user_list[index]
    old_gain, old_offset = old_calib.gain, old_calib.offset

    try:
        fv_low  = invert_user_calibration(shown_low, old_calib.gain, old_calib.offset, old_calib.poly)
        fv_high = invert_user_calibration(shown_high, old_calib.gain, old_calib.offset, old_calib.poly)
        new_gain, new_offset = fit_two_point(fv_low, real_low, fv_high, real_high)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    write_user_calibration(
        CALIBRATION_PATH, tipo, index, new_gain, new_offset,
        shown_low, real_low, shown_high, real_high,
    )
    context.units.reload_calibration(CALIBRATION_PATH)
    context.calibration_audit.log_change(
        tipo, sensor, shown_low, real_low, shown_high, real_high,
        old_gain, old_offset, new_gain, new_offset, usuario,
    )

    return {"ok": True, "gain": new_gain, "offset": new_offset}
```

- [ ] **Step 4: Ejecutar y verificar que pasan**

Run: `python -m pytest tests/test_backend_calibration_endpoints.py -v`
Expected: 6 passed

- [ ] **Step 5: Ejecutar el resto de tests de backend para confirmar que no se rompió nada**

Run: `python -m pytest tests/test_io_endpoints.py tests/test_io_test_mode_endpoints.py tests/test_status_endpoint_alarms.py -v`
Expected: todos passed (mismo patrón de mock de `BackendContext`, no debería verse afectado)

- [ ] **Step 6: Commit**

```bash
git add src/autoclave/backend/context.py src/autoclave/backend/server.py tests/test_backend_calibration_endpoints.py
git commit -m "feat: agregar endpoints GET/PATCH /calibration/{tipo}/{sensor}"
```

---

### Task 6: Métodos nuevos en `BackendClient`

**Files:**
- Modify: `src/autoclave/ui/service_ui/backend_client.py`
- Test: `tests/test_backend_client_calibration.py`

**Interfaces:**
- Produces: `BackendClient.get_calibration(tipo: str, sensor: str) -> dict`, `BackendClient.save_calibration(tipo: str, sensor: str, body: dict) -> dict`.

- [ ] **Step 1: Escribir los tests que fallan**

Crear `tests/test_backend_client_calibration.py`:

```python
from unittest.mock import patch, MagicMock
from autoclave.ui.service_ui.backend_client import BackendClient


def test_get_calibration_llama_get_con_ruta_correcta():
    client = BackendClient("http://localhost:8000")
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"gain": 1.0, "offset": 0.0}
    mock_resp.raise_for_status.return_value = None
    with patch("requests.get", return_value=mock_resp) as mock_get:
        result = client.get_calibration("temperature", "temp_camara")
    mock_get.assert_called_once_with(
        "http://localhost:8000/calibration/temperature/temp_camara", timeout=0.8
    )
    assert result == {"gain": 1.0, "offset": 0.0}


def test_save_calibration_llama_patch_con_body():
    client = BackendClient("http://localhost:8000")
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"ok": True, "gain": 1.26, "offset": -64.5}
    mock_resp.raise_for_status.return_value = None
    body = {"shown_low": 12.0, "real_low": 9.54, "shown_high": 322.0, "real_high": 300.0}
    with patch("requests.patch", return_value=mock_resp) as mock_patch:
        result = client.save_calibration("pressure", "pres_camara", body)
    mock_patch.assert_called_once_with(
        "http://localhost:8000/calibration/pressure/pres_camara",
        json=body, timeout=0.8,
    )
    assert result == {"ok": True, "gain": 1.26, "offset": -64.5}
```

- [ ] **Step 2: Ejecutar y verificar que fallan**

Run: `python -m pytest tests/test_backend_client_calibration.py -v`
Expected: FAIL — `AttributeError: 'BackendClient' object has no attribute 'get_calibration'`

- [ ] **Step 3: Implementar**

En `src/autoclave/ui/service_ui/backend_client.py`, agregar junto a `get_cycle` (después de la línea 21):

```python
    def get_calibration(self, tipo: str, sensor: str) -> dict:
        return self.get(f"/calibration/{tipo}/{sensor}")

    def save_calibration(self, tipo: str, sensor: str, body: dict) -> dict:
        return self.patch(f"/calibration/{tipo}/{sensor}", body)
```

- [ ] **Step 4: Ejecutar y verificar que pasan**

Run: `python -m pytest tests/test_backend_client_calibration.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add src/autoclave/ui/service_ui/backend_client.py tests/test_backend_client_calibration.py
git commit -m "feat: agregar metodos de calibracion a BackendClient"
```

---

### Task 7: `navigate_to` con payload + registro de la vista

**Files:**
- Modify: `src/autoclave/ui_pyside/main_window.py`
- Create (stub mínimo, se completa en Task 9): `src/autoclave/ui_pyside/views/entrdas_salidas/calibracion_sensor.py`
- Test: `tests/test_main_window_navigate_payload.py`

**Interfaces:**
- Produces: `MainWindowFluent.navigate_to(view_name: str, payload: dict | None = None) -> None`. La vista destino, si define `set_context(**payload)`, la recibe antes de mostrarse.
- Consumes (stub): `CalibracionSensorView(nav_callback)` — constructor mínimo que no falla; el resto de su comportamiento se completa en la Tarea 9.

- [ ] **Step 1: Escribir los tests que fallan**

Crear `tests/test_main_window_navigate_payload.py`:

```python
import sys
import pytest


@pytest.fixture(scope="session", autouse=True)
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


def test_navigate_to_sin_payload_no_falla():
    from autoclave.ui_pyside.main_window import MainWindowFluent
    win = MainWindowFluent()
    win.navigate_to("home")
    assert win._stack.currentWidget() is win._home


def test_navigate_to_con_payload_llama_set_context():
    from autoclave.ui_pyside.main_window import MainWindowFluent
    win = MainWindowFluent()
    calls = []
    win._calibracion_sensor.set_context = lambda **kw: calls.append(kw)
    win.navigate_to("calibracion_sensor", {"tipo": "temperature", "sensor": "temp_camara"})
    assert calls == [{"tipo": "temperature", "sensor": "temp_camara"}]
    assert win._stack.currentWidget() is win._calibracion_sensor


def test_navigate_to_payload_none_no_llama_set_context():
    from autoclave.ui_pyside.main_window import MainWindowFluent
    win = MainWindowFluent()
    calls = []
    win._calibracion_sensor.set_context = lambda **kw: calls.append(kw)
    win.navigate_to("calibracion_sensor")
    assert calls == []
```

- [ ] **Step 2: Ejecutar y verificar que fallan**

Run: `python -m pytest tests/test_main_window_navigate_payload.py -v`
Expected: FAIL — `AttributeError: 'MainWindowFluent' object has no attribute '_calibracion_sensor'`

- [ ] **Step 3: Implementar**

Crear el stub `src/autoclave/ui_pyside/views/entrdas_salidas/calibracion_sensor.py` (se completa en Task 9):

```python
from collections.abc import Callable
from PySide6.QtWidgets import QWidget


class CalibracionSensorView(QWidget):
    def __init__(self, nav_callback: Callable[[str], None]) -> None:
        super().__init__()
        self._nav = nav_callback
```

En `src/autoclave/ui_pyside/main_window.py`, agregar el import (junto a los demás, línea 51):

```python
from autoclave.ui_pyside.views.entrdas_salidas.calibracion_sensor import CalibracionSensorView
```

Instanciar (junto a `self._params_ciclo`, línea 64):

```python
        self._calibracion_sensor = CalibracionSensorView(nav_callback=self.navigate_to)
```

Agregar a la tupla de `_stack.addWidget` (líneas 66-69):

```python
        for view in (self._home, self._secado, self._login,
                     self._ciclos, self._impresion_menu, self._admin_menu, self._io_menu,
                     self._io_di, self._io_temp, self._io_pres, self._io_do,
                     self._params_ciclo, self._calibracion_sensor):
            self._stack.addWidget(view)
```

Cambiar `navigate_to` (líneas 176-193):

```python
    def navigate_to(self, view_name: str, payload: dict | None = None) -> None:
        views = {
            "home":         self._home,
            "secado":       self._secado,
            "login":        self._login,
            "ciclos":       self._ciclos,
            "impresion_menu": self._impresion_menu,
            "admin_menu":   self._admin_menu,
            "io_menu":      self._io_menu,
            "io_di":        self._io_di,
            "io_temp":      self._io_temp,
            "io_pres":      self._io_pres,
            "io_do":        self._io_do,
            "params_ciclo": self._params_ciclo,
            "calibracion_sensor": self._calibracion_sensor,
        }
        target = views.get(view_name)
        if target:
            if payload and hasattr(target, "set_context"):
                target.set_context(**payload)
            self._stack.setCurrentWidget(target)
```

- [ ] **Step 4: Ejecutar y verificar que pasan**

Run: `python -m pytest tests/test_main_window_navigate_payload.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/autoclave/ui_pyside/main_window.py src/autoclave/ui_pyside/views/entrdas_salidas/calibracion_sensor.py tests/test_main_window_navigate_payload.py
git commit -m "feat: soportar payload en navigate_to y registrar CalibracionSensorView"
```

---

### Task 8: Tarjetas de sensor clicables

**Files:**
- Modify: `src/autoclave/ui_pyside/views/entrdas_salidas/io_temp.py`
- Modify: `src/autoclave/ui_pyside/views/entrdas_salidas/io_pres.py`
- Test: `tests/test_io_temp_pres_clickable.py`

**Interfaces:**
- Produces: `_TempCard`/`_PresCard` con `setCursor(PointingHandCursor)`, hover, y `mousePressEvent` que llama `self._nav("calibracion_sensor", {"tipo": "temperature"|"pressure", "sensor": name})`. Requiere que `TemperaturasView`/`PresionesView` pasen su `nav_callback` a cada card.

- [ ] **Step 1: Escribir los tests que fallan**

Crear `tests/test_io_temp_pres_clickable.py`:

```python
import sys
import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtCore import QPointF


@pytest.fixture(scope="session", autouse=True)
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


def _click(widget):
    event = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress, QPointF(5, 5), Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
    )
    widget.mousePressEvent(event)


def test_temp_card_click_navega_con_payload_correcto():
    from autoclave.ui_pyside.views.entrdas_salidas.io_temp import TemperaturasView
    calls = []
    view = TemperaturasView(nav_callback=lambda name, payload=None: calls.append((name, payload)))
    _click(view._cards["temp_camara"])
    assert calls == [("calibracion_sensor", {"tipo": "temperature", "sensor": "temp_camara"})]


def test_pres_card_click_navega_con_payload_correcto():
    from autoclave.ui_pyside.views.entrdas_salidas.io_pres import PresionesView
    calls = []
    view = PresionesView(nav_callback=lambda name, payload=None: calls.append((name, payload)))
    _click(view._cards["pres_chaqueta"])
    assert calls == [("calibracion_sensor", {"tipo": "pressure", "sensor": "pres_chaqueta"})]
```

- [ ] **Step 2: Ejecutar y verificar que fallan**

Run: `python -m pytest tests/test_io_temp_pres_clickable.py -v`
Expected: FAIL — las tarjetas no navegan (sin `mousePressEvent` propio, o `calls` queda vacío)

- [ ] **Step 3: Implementar**

En `src/autoclave/ui_pyside/views/entrdas_salidas/io_temp.py`, reemplazar la clase `_TempCard` completa y el bucle de construcción en `TemperaturasView.__init__`:

```python
from collections.abc import Callable
from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout
from autoclave.core.runtime.status import EstadoAutoclave
from autoclave.ui_pyside.views.entrdas_salidas._io_base import _MonitorBase, _format_name

_CARD_NORMAL = "QFrame { background: white; border-radius: 10px; border: 1.5px solid #e8eaed; }"
_CARD_HOVER = "QFrame { background: #eff6ff; border-radius: 10px; border: 1.5px solid #2563eb; }"


class _TempCard(QFrame):
    def __init__(self, name: str, nav_callback: Optional[Callable] = None):
        super().__init__()
        self._name = name
        self._nav = nav_callback
        self.setStyleSheet(_CARD_NORMAL)
        self.setMinimumSize(180, 90)
        if nav_callback is not None:
            self.setCursor(Qt.CursorShape.PointingHandCursor)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(6)

        lbl_name = QLabel(_format_name(name))
        lbl_name.setFont(QFont("Segoe UI", 11))
        lbl_name.setStyleSheet("color: #555; border: none;")
        lay.addWidget(lbl_name)

        self._lbl_value = QLabel("---")
        self._lbl_value.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        self._lbl_value.setStyleSheet("color: #f97316; border: none;")
        lay.addWidget(self._lbl_value)

    def set_value(self, value: Optional[float]) -> None:
        if value is None:
            self._lbl_value.setText("---")
            self._lbl_value.setStyleSheet("color: #f97316; font-weight: bold; border: none;")
        else:
            self._lbl_value.setText(f"{value:.1f} °C")
            self._lbl_value.setStyleSheet("color: #1a2a3a; font-weight: bold; border: none;")

    def enterEvent(self, event) -> None:
        if self._nav is not None:
            self.setStyleSheet(_CARD_HOVER)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self.setStyleSheet(_CARD_NORMAL)
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        if self._nav is not None and event.button() == Qt.MouseButton.LeftButton:
            self._nav("calibracion_sensor", {"tipo": "temperature", "sensor": self._name})
        super().mousePressEvent(event)


class TemperaturasView(_MonitorBase):
    _TEMP_NAMES = list(EstadoAutoclave.map_temp.keys())

    _NAME_MAP = {
        "temp_camara":      "camara",
        "temp_2_camara":    "camara_2",
        "temp_ref":         "ref",
        "temp_chaqueta":    "chaqueta",
        "temp_drenaje_cam": "drenaje_camara",
        "temp_drenaje":     "drenaje",
    }

    def __init__(self, nav_callback: Callable[[str], None]) -> None:
        super().__init__("SENSORES DE TEMPERATURA", "io_menu", nav_callback)
        self._cards: dict[str, _TempCard] = {}
        for idx, name in enumerate(self._TEMP_NAMES):
            card = _TempCard(name, nav_callback=nav_callback)
            self._cards[name] = card
            row, col = divmod(idx, 2)
            self._grid.addWidget(card, row, col)

    def _update_cards(self, status: dict) -> None:
        temp = status.get("sensors", {}).get("temperature", {})
        for name, card in self._cards.items():
            key = self._NAME_MAP.get(name, name)
            card.set_value(temp.get(key))
```

Nota: `_MonitorBase.__init__` llama a `self._nav(back_target)` con un solo argumento (sin payload) — como `navigate_to` ahora acepta `payload: dict | None = None` con default, esa llamada sigue funcionando sin cambios.

El archivo real actual `src/autoclave/ui_pyside/views/entrdas_salidas/io_pres.py` (verificado leyéndolo completo) es:

```python
from collections.abc import Callable
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout
from autoclave.core.runtime.status import EstadoAutoclave
from autoclave.ui_pyside.views.entrdas_salidas._io_base import _MonitorBase, _format_name


class _PresCard(QFrame):
    def __init__(self, name: str):
        super().__init__()
        self.setStyleSheet(
            "QFrame { background: white; border-radius: 10px; border: 1.5px solid #e8eaed; }"
        )
        self.setMinimumSize(180, 90)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(6)

        lbl_name = QLabel(_format_name(name))
        lbl_name.setFont(QFont("Segoe UI", 11))
        lbl_name.setStyleSheet("color: #555; border: none;")
        lay.addWidget(lbl_name)

        self._lbl_value = QLabel("0.00 kPa")
        self._lbl_value.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        self._lbl_value.setStyleSheet("color: #1a2a3a; border: none;")
        lay.addWidget(self._lbl_value)

    def set_value(self, value: float) -> None:
        self._lbl_value.setText(f"{value:.2f} kPa")

3333
class PresionesView(_MonitorBase):
    _PRES_NAMES = list(EstadoAutoclave.map_pres.keys())

    _NAME_MAP = {
        "pres_camara":    "camara",
        "pres_chaqueta":  "chaqueta",
        "pres_empaque_1": "empaque_1",
        "pres_empaque_2": "empaque_2",
    }

    def __init__(self, nav_callback: Callable[[str], None]) -> None:
        super().__init__("SENSORES DE PRESIÓN", "io_menu", nav_callback)
        self._cards: dict[str, _PresCard] = {}
        for idx, name in enumerate(self._PRES_NAMES):
            card = _PresCard(name)
            self._cards[name] = card
            row, col = divmod(idx, 2)
            self._grid.addWidget(card, row, col)

    def _update_cards(self, status: dict) -> None:
        pres = status.get("sensors", {}).get("pressure", {})
        for name, card in self._cards.items():
            key = self._NAME_MAP.get(name, name)
            card.set_value(pres.get(key, 0.0) or 0.0)
```

Nota: el `3333` en la línea 33 es una línea huérfana sin efecto (un statement suelto que Python evalúa y descarta) — se elimina de paso. La unidad real es `kPa` (no `bar`) y `set_value` recibe siempre un `float` no-opcional (el llamador ya cubre `None` con `pres.get(key, 0.0) or 0.0`) — el reemplazo de abajo preserva ambos detalles exactamente, solo agregando cursor/hover/clic:

```python
from collections.abc import Callable
from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout
from autoclave.core.runtime.status import EstadoAutoclave
from autoclave.ui_pyside.views.entrdas_salidas._io_base import _MonitorBase, _format_name

_CARD_NORMAL = "QFrame { background: white; border-radius: 10px; border: 1.5px solid #e8eaed; }"
_CARD_HOVER = "QFrame { background: #eff6ff; border-radius: 10px; border: 1.5px solid #2563eb; }"


class _PresCard(QFrame):
    def __init__(self, name: str, nav_callback: Optional[Callable] = None):
        super().__init__()
        self._name = name
        self._nav = nav_callback
        self.setStyleSheet(_CARD_NORMAL)
        self.setMinimumSize(180, 90)
        if nav_callback is not None:
            self.setCursor(Qt.CursorShape.PointingHandCursor)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(6)

        lbl_name = QLabel(_format_name(name))
        lbl_name.setFont(QFont("Segoe UI", 11))
        lbl_name.setStyleSheet("color: #555; border: none;")
        lay.addWidget(lbl_name)

        self._lbl_value = QLabel("0.00 kPa")
        self._lbl_value.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        self._lbl_value.setStyleSheet("color: #1a2a3a; border: none;")
        lay.addWidget(self._lbl_value)

    def set_value(self, value: float) -> None:
        self._lbl_value.setText(f"{value:.2f} kPa")

    def enterEvent(self, event) -> None:
        if self._nav is not None:
            self.setStyleSheet(_CARD_HOVER)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self.setStyleSheet(_CARD_NORMAL)
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        if self._nav is not None and event.button() == Qt.MouseButton.LeftButton:
            self._nav("calibracion_sensor", {"tipo": "pressure", "sensor": self._name})
        super().mousePressEvent(event)


class PresionesView(_MonitorBase):
    _PRES_NAMES = list(EstadoAutoclave.map_pres.keys())

    _NAME_MAP = {
        "pres_camara":    "camara",
        "pres_chaqueta":  "chaqueta",
        "pres_empaque_1": "empaque_1",
        "pres_empaque_2": "empaque_2",
    }

    def __init__(self, nav_callback: Callable[[str], None]) -> None:
        super().__init__("SENSORES DE PRESIÓN", "io_menu", nav_callback)
        self._cards: dict[str, _PresCard] = {}
        for idx, name in enumerate(self._PRES_NAMES):
            card = _PresCard(name, nav_callback=nav_callback)
            self._cards[name] = card
            row, col = divmod(idx, 2)
            self._grid.addWidget(card, row, col)

    def _update_cards(self, status: dict) -> None:
        pres = status.get("sensors", {}).get("pressure", {})
        for name, card in self._cards.items():
            key = self._NAME_MAP.get(name, name)
            card.set_value(pres.get(key, 0.0) or 0.0)
```

- [ ] **Step 4: Ejecutar y verificar que pasan**

Run: `python -m pytest tests/test_io_temp_pres_clickable.py -v`
Expected: 2 passed

- [ ] **Step 5: Confirmar que las vistas de sensores siguen funcionando (aunque las pruebas de ese archivo estén rotas por rutas obsoletas, no relacionado con este cambio)**

Run: `python -m pytest tests/test_ciclo_sensores.py -v`
Expected: passed (no depende de las vistas PySide6, solo de `EstadoAutoclave`)

- [ ] **Step 6: Commit**

```bash
git add src/autoclave/ui_pyside/views/entrdas_salidas/io_temp.py src/autoclave/ui_pyside/views/entrdas_salidas/io_pres.py tests/test_io_temp_pres_clickable.py
git commit -m "feat: tarjetas de sensores clicables navegan al modo de calibracion"
```

---

### Task 9: `CalibracionSensorView` completa

**Files:**
- Modify: `src/autoclave/ui_pyside/views/entrdas_salidas/calibracion_sensor.py` (reemplaza el stub de Task 7)
- Test: `tests/test_calibracion_sensor_view.py`

**Interfaces:**
- Consumes: `BackendClient.get_calibration`/`save_calibration` (Task 6), `SessionManager` (existente), `calibration_tools.invert_user_calibration`/`fit_two_point` (Task 1, para la vista previa local).
- Produces: `CalibracionSensorView.set_context(tipo: str, sensor: str) -> None`.

- [ ] **Step 1: Escribir los tests que fallan**

Crear `tests/test_calibracion_sensor_view.py`:

```python
import sys
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture(scope="session", autouse=True)
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


def _make_view():
    from autoclave.ui_pyside.views.entrdas_salidas.calibracion_sensor import CalibracionSensorView
    calls = []
    view = CalibracionSensorView(nav_callback=lambda *a, **kw: calls.append((a, kw)))
    return view, calls


def test_sin_sesion_bloquea_formulario():
    from autoclave.ui_pyside.services.session_manager import SessionManager
    SessionManager.logout()
    view, _ = _make_view()
    with patch.object(view, "_client") as mock_client:
        mock_client.get_calibration.return_value = {
            "gain": 1.0, "offset": 0.0, "poly": None, "is_poly": False, "last_change": None,
        }
        view.set_context(tipo="pressure", sensor="pres_camara")
    assert view._formulario_visible() is False


def test_rol_operador_bloquea_formulario():
    from autoclave.ui_pyside.services.session_manager import SessionManager
    SessionManager.login({"id": 1, "nombre": "Juan", "usuario": "juan", "rol": "operador"})
    view, _ = _make_view()
    with patch.object(view, "_client") as mock_client:
        mock_client.get_calibration.return_value = {
            "gain": 1.0, "offset": 0.0, "poly": None, "is_poly": False, "last_change": None,
        }
        view.set_context(tipo="pressure", sensor="pres_camara")
    assert view._formulario_visible() is False
    SessionManager.logout()


def test_rol_admin_habilita_formulario_y_muestra_info():
    from autoclave.ui_pyside.services.session_manager import SessionManager
    SessionManager.login({"id": 1, "nombre": "Admin", "usuario": "admin", "rol": "admin"})
    view, _ = _make_view()
    with patch.object(view, "_client") as mock_client:
        mock_client.get_calibration.return_value = {
            "gain": 1.3466, "offset": -67.11, "poly": None, "is_poly": False,
            "last_change": {"usuario": "tecnico1", "timestamp": "2026-07-20 10:00"},
        }
        view.set_context(tipo="pressure", sensor="pres_camara")
    assert view._formulario_visible() is True
    assert "1.3466" in view._lbl_info.text()
    assert "tecnico1" in view._lbl_info.text()
    SessionManager.logout()


def test_preview_se_calcula_localmente_sin_llamar_backend():
    from autoclave.ui_pyside.services.session_manager import SessionManager
    SessionManager.login({"id": 1, "nombre": "Admin", "usuario": "admin", "rol": "admin"})
    view, _ = _make_view()
    with patch.object(view, "_client") as mock_client:
        mock_client.get_calibration.return_value = {
            "gain": 1.3466, "offset": -67.11, "poly": None, "is_poly": False, "last_change": None,
        }
        view.set_context(tipo="pressure", sensor="pres_camara")
        view._input_shown_low.setValue(12.0)
        view._input_real_low.setValue(9.54)
        view._input_shown_high.setValue(322.0)
        view._input_real_high.setValue(300.0)
        view._on_inputs_changed()
        mock_client.save_calibration.assert_not_called()
    assert round(view._preview_gain, 6) == pytest.approx(1.261721, abs=1e-6)
    assert view._btn_guardar.isEnabled() is True
    SessionManager.logout()


def test_preview_invalida_deshabilita_guardar():
    from autoclave.ui_pyside.services.session_manager import SessionManager
    SessionManager.login({"id": 1, "nombre": "Admin", "usuario": "admin", "rol": "admin"})
    view, _ = _make_view()
    with patch.object(view, "_client") as mock_client:
        mock_client.get_calibration.return_value = {
            "gain": 1.3466, "offset": -67.11, "poly": None, "is_poly": False, "last_change": None,
        }
        view.set_context(tipo="pressure", sensor="pres_camara")
        view._input_shown_low.setValue(12.0)
        view._input_real_low.setValue(9.54)
        view._input_shown_high.setValue(12.0)   # igual al bajo -> invalido
        view._input_real_high.setValue(300.0)
        view._on_inputs_changed()
    assert view._btn_guardar.isEnabled() is False
    SessionManager.logout()


def test_guardar_llama_save_calibration_con_usuario():
    from autoclave.ui_pyside.services.session_manager import SessionManager
    SessionManager.login({"id": 1, "nombre": "Tecnico Uno", "usuario": "tec1", "rol": "tecnico"})
    view, _ = _make_view()
    with patch.object(view, "_client") as mock_client:
        mock_client.get_calibration.return_value = {
            "gain": 1.3466, "offset": -67.11, "poly": None, "is_poly": False, "last_change": None,
        }
        mock_client.save_calibration.return_value = {"ok": True, "gain": 1.261721, "offset": -64.583518}
        view.set_context(tipo="pressure", sensor="pres_camara")
        view._input_shown_low.setValue(12.0)
        view._input_real_low.setValue(9.54)
        view._input_shown_high.setValue(322.0)
        view._input_real_high.setValue(300.0)
        view._on_inputs_changed()
        view._on_guardar()
        mock_client.save_calibration.assert_called_once_with(
            "pressure", "pres_camara",
            {
                "shown_low": 12.0, "real_low": 9.54,
                "shown_high": 322.0, "real_high": 300.0,
                "usuario": "Tecnico Uno",
            },
        )
    SessionManager.logout()
```

- [ ] **Step 2: Ejecutar y verificar que fallan**

Run: `python -m pytest tests/test_calibracion_sensor_view.py -v`
Expected: FAIL — `CalibracionSensorView` (stub de Task 7) no tiene `set_context`, `_formulario_visible`, ni los demás atributos

- [ ] **Step 3: Implementar**

Reemplazar completamente `src/autoclave/ui_pyside/views/entrdas_salidas/calibracion_sensor.py`:

```python
from collections.abc import Callable

from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from autoclave.hal.measures.calibration_tools import invert_user_calibration, fit_two_point
from autoclave.ui.service_ui.backend_client import BackendClient
from autoclave.ui_pyside.services.session_manager import SessionManager

_BACKEND_URL = "http://localhost:8000"

_BTN_BACK = """
    QPushButton {
        background: #f0f0f0; color: #333;
        border-radius: 8px; border: none;
        font-size: 20px; font-weight: bold;
    }
    QPushButton:hover { background: #e0e0e0; }
"""

_BTN_GUARDAR = """
    QPushButton { background: #2563eb; color: white; border-radius: 8px;
        border: none; font-size: 13px; font-weight: bold; padding: 0 20px; }
    QPushButton:hover { background: #1d4ed8; }
    QPushButton:disabled { background: #93c5fd; }
"""

_ROLES_PERMITIDOS = ("admin", "tecnico")


class CalibracionSensorView(QWidget):
    def __init__(self, nav_callback: Callable[[str], None]) -> None:
        super().__init__()
        self._nav = nav_callback
        self._client = BackendClient(_BACKEND_URL)
        self._tipo: str | None = None
        self._sensor: str | None = None
        self._back_target = "io_temp"
        self._preview_gain: float | None = None
        self._preview_offset: float | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        hdr = QHBoxLayout()
        btn_back = QPushButton("←")
        btn_back.setFixedSize(40, 40)
        btn_back.setStyleSheet(_BTN_BACK)
        btn_back.clicked.connect(lambda: self._nav(self._back_target))
        hdr.addWidget(btn_back)
        hdr.addSpacing(8)
        self._lbl_title = QLabel("CALIBRACIÓN DE SENSOR")
        self._lbl_title.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        self._lbl_title.setStyleSheet("color: #1a2a3a;")
        hdr.addWidget(self._lbl_title)
        hdr.addStretch()
        root.addLayout(hdr)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #e8eaed;")
        root.addWidget(sep)

        self._lbl_denegado = QLabel("No tienes permiso para calibrar sensores.")
        self._lbl_denegado.setStyleSheet("color: #ef4444; font-size: 14px;")
        self._lbl_denegado.hide()
        root.addWidget(self._lbl_denegado)

        self._lbl_info = QLabel("")
        self._lbl_info.setStyleSheet("color: #6b7280; font-size: 12px;")
        root.addWidget(self._lbl_info)

        self._form_widget = QWidget()
        form = QFormLayout(self._form_widget)
        form.setSpacing(8)

        self._input_shown_low = QDoubleSpinBox()
        self._input_real_low = QDoubleSpinBox()
        self._input_shown_high = QDoubleSpinBox()
        self._input_real_high = QDoubleSpinBox()
        for inp in (self._input_shown_low, self._input_real_low,
                    self._input_shown_high, self._input_real_high):
            inp.setDecimals(2)
            inp.setRange(-1000.0, 1000.0)
            inp.setValue(0.0)
            inp.valueChanged.connect(self._on_inputs_changed)

        form.addRow("Mostrado bajo:", self._input_shown_low)
        form.addRow("Real bajo (patrón):", self._input_real_low)
        form.addRow("Mostrado alto:", self._input_shown_high)
        form.addRow("Real alto (patrón):", self._input_real_high)

        self._lbl_preview = QLabel("—")
        self._lbl_preview.setStyleSheet("color: #1a2a3a; font-weight: bold;")
        form.addRow("Gain/Offset resultante:", self._lbl_preview)

        root.addWidget(self._form_widget)

        self._btn_guardar = QPushButton("Guardar")
        self._btn_guardar.setFixedHeight(36)
        self._btn_guardar.setStyleSheet(_BTN_GUARDAR)
        self._btn_guardar.setEnabled(False)
        self._btn_guardar.clicked.connect(self._on_guardar)
        root.addWidget(self._btn_guardar)

        root.addStretch()

    # ── Contexto / carga ─────────────────────────────────────────────

    def set_context(self, tipo: str, sensor: str, back_target: str | None = None) -> None:
        self._tipo = tipo
        self._sensor = sensor
        self._back_target = back_target or ("io_temp" if tipo == "temperature" else "io_pres")
        self._lbl_title.setText(f"CALIBRACIÓN — {sensor}")

        for inp in (self._input_shown_low, self._input_real_low,
                    self._input_shown_high, self._input_real_high):
            inp.blockSignals(True)
            inp.setValue(0.0)
            inp.blockSignals(False)
        self._preview_gain = None
        self._preview_offset = None
        self._lbl_preview.setText("—")
        self._btn_guardar.setEnabled(False)

        if not self._tiene_permiso():
            self._form_widget.hide()
            self._btn_guardar.hide()
            self._lbl_denegado.show()
            self._lbl_info.setText("")
            return

        self._lbl_denegado.hide()
        self._form_widget.show()
        self._btn_guardar.show()

        info = self._client.get_calibration(tipo, sensor)
        self._current_gain = info.get("gain", 1.0)
        self._current_offset = info.get("offset", 0.0)
        self._current_poly = info.get("poly")

        if info.get("is_poly"):
            calib_txt = "polinomio (5 puntos)"
        else:
            calib_txt = f"gain={self._current_gain}, offset={self._current_offset}"

        last = info.get("last_change")
        if last:
            audit_txt = f"Última modificación: {last['usuario']} · {last['timestamp']}"
        else:
            audit_txt = "Sin modificaciones previas"

        self._lbl_info.setText(f"Calibración actual: {calib_txt}\n{audit_txt}")

    def _tiene_permiso(self) -> bool:
        if not SessionManager.is_authenticated():
            return False
        return SessionManager.current_role() in _ROLES_PERMITIDOS

    def _formulario_visible(self) -> bool:
        return self._form_widget.isVisible()

    # ── Vista previa ─────────────────────────────────────────────────

    def _on_inputs_changed(self) -> None:
        shown_low = self._input_shown_low.value()
        real_low = self._input_real_low.value()
        shown_high = self._input_shown_high.value()
        real_high = self._input_real_high.value()

        if shown_low == shown_high:
            self._preview_gain = None
            self._preview_offset = None
            self._lbl_preview.setText("—")
            self._btn_guardar.setEnabled(False)
            return

        try:
            fv_low = invert_user_calibration(shown_low, self._current_gain, self._current_offset, self._current_poly)
            fv_high = invert_user_calibration(shown_high, self._current_gain, self._current_offset, self._current_poly)
            gain, offset = fit_two_point(fv_low, real_low, fv_high, real_high)
        except ValueError:
            self._preview_gain = None
            self._preview_offset = None
            self._lbl_preview.setText("—")
            self._btn_guardar.setEnabled(False)
            return

        self._preview_gain = gain
        self._preview_offset = offset
        self._lbl_preview.setText(f"gain={gain:.6f}  offset={offset:.6f}")
        self._btn_guardar.setEnabled(True)

    # ── Guardar ──────────────────────────────────────────────────────

    def _on_guardar(self) -> None:
        if self._preview_gain is None or self._tipo is None or self._sensor is None:
            return

        usuario = (
            SessionManager.current_user().get("nombre", "Desconocido")
            if SessionManager.is_authenticated()
            else "Desconocido"
        )

        body = {
            "shown_low": self._input_shown_low.value(),
            "real_low": self._input_real_low.value(),
            "shown_high": self._input_shown_high.value(),
            "real_high": self._input_real_high.value(),
            "usuario": usuario,
        }
        result = self._client.save_calibration(self._tipo, self._sensor, body)

        self._current_gain = result["gain"]
        self._current_offset = result["offset"]
        self._current_poly = None
        self._lbl_info.setText(
            f"Calibración actual: gain={result['gain']}, offset={result['offset']}\n"
            f"Última modificación: {usuario} · ahora"
        )
```

- [ ] **Step 4: Ejecutar y verificar que pasan**

Run: `python -m pytest tests/test_calibracion_sensor_view.py -v`
Expected: 6 passed

- [ ] **Step 5: Ejecutar la Tarea 7 de nuevo para confirmar que la vista completa sigue integrándose con `navigate_to`**

Run: `python -m pytest tests/test_main_window_navigate_payload.py -v`
Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
git add src/autoclave/ui_pyside/views/entrdas_salidas/calibracion_sensor.py tests/test_calibracion_sensor_view.py
git commit -m "feat: implementar pantalla completa de calibracion de sensor"
```

---

### Task 10: Suite completa

**Files:** ninguno (solo verificación)

- [ ] **Step 1: Ejecutar toda la suite de tests**

Run: `python -m pytest tests/ -v`
Expected: todos passed excepto los 19 ya conocidos de `tests/test_io_views.py` (archivo obsoleto, rutas de import de antes de la reestructuración de módulos — preexistente, fuera de alcance de este plan).
