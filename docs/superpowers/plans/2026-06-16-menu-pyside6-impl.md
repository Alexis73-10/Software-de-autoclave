# Menú Principal PySide6 — v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Crear el menú principal PySide6 con 3 vistas funcionales (Tiempo de Secado, Imprimir Ciclos, Login) que reemplaza tkinter como punto de entrada de la aplicación.

**Architecture:** `QMainWindow` con `QStackedWidget` para navegación entre vistas; widgets de PySide6-Fluent-Widgets para el look del mockup. La ventana tkinter existente sigue corriendo como subprocess para el monitoreo de ciclo. El backend FastAPI se comunica via `BackendClient` existente.

**Tech Stack:** PySide6, PySide6-Fluent-Widgets (`qfluentwidgets`), pyqtgraph (instalado, sin uso activo en v1), requests (ya presente), hashlib (stdlib), pytest.

**Spec:** `docs/superpowers/specs/2026-06-16-menu-pyside6-design.md`

---

## File Map

**Nuevos:**
- `src/autoclave/ui_pyside/__init__.py`
- `src/autoclave/ui_pyside/services/__init__.py`
- `src/autoclave/ui_pyside/services/session_manager.py`
- `src/autoclave/ui_pyside/services/backend_client.py`
- `src/autoclave/ui_pyside/views/__init__.py`
- `src/autoclave/ui_pyside/main_window.py`
- `src/autoclave/ui_pyside/views/home.py`
- `src/autoclave/ui_pyside/views/secado.py`
- `src/autoclave/ui_pyside/views/login.py`
- `src/autoclave/ui_pyside/views/ciclos.py`
- `tests/test_session_manager.py`
- `tests/test_usuarios_db.py`
- `tests/test_patch_cycle_parameters.py`

**Modificados:**
- `src/autoclave/services/domain/logging/db_manager.py` — tabla usuarios + métodos
- `src/autoclave/core/cycle_manager.py` — atributo `_path` en ciclos cargados
- `src/autoclave/backend/server.py` — endpoint `PATCH /cycle/parameters`
- `src/autoclave/ui/service_ui/backend_client.py` — método `patch()`
- `src/autoclave/main.py` — reemplaza arranque tkinter por PySide6

---

## Task 1: Instalar dependencias PySide6

**Files:**
- Modify: `pyproject.toml` o `requirements.txt` (el que exista)

- [ ] **Step 1: Verificar archivo de dependencias**

```bash
ls pyproject.toml requirements*.txt 2>/dev/null
```

- [ ] **Step 2: Instalar paquetes**

```bash
pip install PySide6 "PySide6-Fluent-Widgets[full]" pyqtgraph
```

- [ ] **Step 3: Verificar imports**

```bash
python -c "from PySide6.QtWidgets import QApplication; from qfluentwidgets import CardWidget, SubtitleLabel, InfoBar, PrimaryPushButton, LineEdit, PasswordLineEdit, TableWidget, CalendarPicker, DoubleSpinBox; import pyqtgraph; print('OK')"
```

Expected output: `OK`

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml   # o requirements.txt
git commit -m "chore: agregar dependencias PySide6, Fluent-Widgets, pyqtgraph"
```

---

## Task 2: DB — tabla `usuarios` + métodos `DbManager`

**Files:**
- Modify: `src/autoclave/services/domain/logging/db_manager.py`
- Create: `tests/test_usuarios_db.py`

- [ ] **Step 1: Escribir los tests**

Crear `tests/test_usuarios_db.py`:

```python
import pytest
import hashlib
from autoclave.services.domain.logging.db_manager import DbManager


@pytest.fixture
def db(tmp_path):
    return DbManager(db_path=tmp_path / "test.db")


def test_init_crea_tabla_usuarios(db):
    # No lanza excepción — tabla existe
    db._conn.execute("SELECT * FROM usuarios").fetchall()


def test_seed_admin_crea_usuario_por_defecto(db):
    user = db.get_usuario_by_username("admin")
    assert user is not None
    assert user["rol"] == "admin"
    assert user["activo"] == 1


def test_seed_admin_no_duplica_al_reiniciar_db(tmp_path):
    db1 = DbManager(db_path=tmp_path / "test.db")
    db2 = DbManager(db_path=tmp_path / "test.db")
    rows = db2._conn.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0]
    assert rows == 1


def test_crear_usuario_retorna_id(db):
    h = hashlib.sha256("pass123".encode()).hexdigest()
    uid = db.crear_usuario("Juan Pérez", "juanp", h, "operador")
    assert isinstance(uid, int)
    assert uid >= 1


def test_get_usuario_by_username_existe(db):
    h = hashlib.sha256("pass123".encode()).hexdigest()
    db.crear_usuario("Juan Pérez", "juanp", h, "operador")
    user = db.get_usuario_by_username("juanp")
    assert user["nombre"] == "Juan Pérez"
    assert user["rol"] == "operador"


def test_get_usuario_by_username_no_existe(db):
    assert db.get_usuario_by_username("fantasma") is None


def test_get_usuario_inactivo_no_se_devuelve(db):
    h = hashlib.sha256("pass".encode()).hexdigest()
    db.crear_usuario("Inactivo", "inactivo", h, "operador", activo=0)
    assert db.get_usuario_by_username("inactivo") is None


def test_get_ciclos_rango_sin_registros(db):
    assert db.get_ciclos_rango() == []


def test_get_ciclos_rango_filtra_por_fecha(db):
    db._conn.execute(
        "INSERT INTO ciclos (numero_ciclo, fecha_inicio, tipo_ciclo, nombre_ciclo,"
        " temp_esterilizacion, tiempo_esterilizacion, modelo, serie, version_sw)"
        " VALUES (1,'2026-06-01T10:00:00','user','Ciclo A',134.0,3.5,'M','S','1.0')"
    )
    db._conn.execute(
        "INSERT INTO ciclos (numero_ciclo, fecha_inicio, tipo_ciclo, nombre_ciclo,"
        " temp_esterilizacion, tiempo_esterilizacion, modelo, serie, version_sw)"
        " VALUES (2,'2026-06-15T10:00:00','user','Ciclo B',134.0,3.5,'M','S','1.0')"
    )
    db._conn.commit()
    rows = db.get_ciclos_rango(desde="2026-06-10", hasta="2026-06-20")
    assert len(rows) == 1
    assert rows[0]["numero_ciclo"] == 2


def test_init_no_rompe_datos_existentes(tmp_path):
    db1 = DbManager(db_path=tmp_path / "test.db")
    h = hashlib.sha256("pass".encode()).hexdigest()
    db1.crear_usuario("Test", "testuser", h)
    db2 = DbManager(db_path=tmp_path / "test.db")
    assert db2.get_usuario_by_username("testuser") is not None
```

- [ ] **Step 2: Ejecutar — verificar que FALLA**

```bash
pytest tests/test_usuarios_db.py -v
```

Expected: varios `FAILED` con `AttributeError` o `OperationalError` (tabla no existe, métodos no definidos).

- [ ] **Step 3: Agregar esquema de usuarios a `_SCHEMA` en `db_manager.py`**

Localizar `_SCHEMA` (línea 25) y agregar al final, antes del cierre `"""`:

```python
CREATE TABLE IF NOT EXISTS usuarios (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre   TEXT NOT NULL,
    usuario  TEXT UNIQUE NOT NULL,
    hash_pw  TEXT NOT NULL,
    rol      TEXT DEFAULT 'operador',
    activo   INTEGER DEFAULT 1
);
```

- [ ] **Step 4: Agregar métodos a `DbManager` (después de `close()`)**

```python
# ------------------------------------------------------------------
# Usuarios
# ------------------------------------------------------------------

def crear_usuario(
    self,
    nombre: str,
    usuario: str,
    hash_pw: str,
    rol: str = "operador",
    activo: int = 1,
) -> int:
    with self._lock:
        cur = self._conn.execute(
            "INSERT INTO usuarios (nombre, usuario, hash_pw, rol, activo)"
            " VALUES (?,?,?,?,?)",
            (nombre, usuario, hash_pw, rol, activo),
        )
        self._conn.commit()
        return cur.lastrowid

def get_usuario_by_username(self, usuario: str) -> dict | None:
    with self._lock:
        row = self._conn.execute(
            "SELECT * FROM usuarios WHERE usuario=? AND activo=1",
            (usuario,),
        ).fetchone()
    return dict(row) if row else None

def seed_admin_if_empty(self) -> None:
    import hashlib
    with self._lock:
        count = self._conn.execute(
            "SELECT COUNT(*) FROM usuarios"
        ).fetchone()[0]
        if count == 0:
            admin_hash = hashlib.sha256(
                "admin1234".encode("utf-8")
            ).hexdigest()
            self._conn.execute(
                "INSERT INTO usuarios (nombre, usuario, hash_pw, rol, activo)"
                " VALUES (?,?,?,?,?)",
                ("Administrador", "admin", admin_hash, "admin", 1),
            )
            self._conn.commit()

def get_ciclos_rango(
    self,
    desde: str | None = None,
    hasta: str | None = None,
    limite: int = 100,
) -> list:
    with self._lock:
        conditions: list[str] = []
        params: list = []
        if desde:
            conditions.append("fecha_inicio >= ?")
            params.append(desde)
        if hasta:
            conditions.append("fecha_inicio <= ?")
            params.append(hasta + "T23:59:59")
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        params.append(limite)
        return self._conn.execute(
            f"SELECT * FROM ciclos {where} ORDER BY id DESC LIMIT ?",
            params,
        ).fetchall()
```

- [ ] **Step 5: Llamar `seed_admin_if_empty()` desde `__init__` (después de `_apply_schema()`)**

Localizar línea `self._apply_schema()` (~línea 87) y agregar justo después:

```python
self._apply_schema()
self.seed_admin_if_empty()
```

- [ ] **Step 6: Ejecutar — verificar que PASA**

```bash
pytest tests/test_usuarios_db.py -v
```

Expected: todos `PASSED`.

- [ ] **Step 7: Verificar que los tests existentes siguen pasando**

```bash
pytest tests/ -v --ignore=tests/test_session_manager.py --ignore=tests/test_patch_cycle_parameters.py
```

Expected: sin regresiones.

- [ ] **Step 8: Commit**

```bash
git add src/autoclave/services/domain/logging/db_manager.py tests/test_usuarios_db.py
git commit -m "feat: tabla usuarios en DB + métodos crear/get/seed/rango_ciclos"
```

---

## Task 3: SessionManager

**Files:**
- Create: `src/autoclave/ui_pyside/__init__.py`
- Create: `src/autoclave/ui_pyside/services/__init__.py`
- Create: `src/autoclave/ui_pyside/services/session_manager.py`
- Create: `tests/test_session_manager.py`

- [ ] **Step 1: Crear directorios y `__init__.py` vacíos**

```bash
mkdir -p src/autoclave/ui_pyside/services
echo "" > src/autoclave/ui_pyside/__init__.py
echo "" > src/autoclave/ui_pyside/services/__init__.py
```

- [ ] **Step 2: Escribir tests**

Crear `tests/test_session_manager.py`:

```python
import pytest
from autoclave.ui_pyside.services.session_manager import SessionManager, hash_password


@pytest.fixture(autouse=True)
def reset():
    SessionManager.logout()
    yield
    SessionManager.logout()


def test_is_authenticated_false_por_defecto():
    assert not SessionManager.is_authenticated()


def test_current_role_none_sin_sesion():
    assert SessionManager.current_role() is None


def test_current_user_none_sin_sesion():
    assert SessionManager.current_user() is None


def test_login_autentica():
    SessionManager.login({"id": 1, "nombre": "Admin", "usuario": "admin", "rol": "admin"})
    assert SessionManager.is_authenticated()


def test_login_guarda_rol():
    SessionManager.login({"id": 1, "nombre": "Admin", "usuario": "admin", "rol": "admin"})
    assert SessionManager.current_role() == "admin"


def test_login_guarda_nombre_y_usuario():
    SessionManager.login({"id": 2, "nombre": "Ope", "usuario": "op1", "rol": "operador"})
    u = SessionManager.current_user()
    assert u["nombre"] == "Ope"
    assert u["usuario"] == "op1"


def test_logout_cierra_sesion():
    SessionManager.login({"id": 1, "nombre": "Admin", "usuario": "admin", "rol": "admin"})
    SessionManager.logout()
    assert not SessionManager.is_authenticated()
    assert SessionManager.current_user() is None


def test_login_sobrescribe_sesion_anterior():
    SessionManager.login({"id": 1, "nombre": "A", "usuario": "a", "rol": "admin"})
    SessionManager.login({"id": 2, "nombre": "B", "usuario": "b", "rol": "operador"})
    assert SessionManager.current_user()["usuario"] == "b"


def test_hash_password_determinista():
    assert hash_password("abc123") == hash_password("abc123")


def test_hash_password_diferencia_passwords():
    assert hash_password("abc123") != hash_password("abc124")


def test_hash_password_es_sha256_hex():
    import hashlib
    expected = hashlib.sha256("test".encode()).hexdigest()
    assert hash_password("test") == expected
```

- [ ] **Step 3: Ejecutar — verificar que FALLA**

```bash
pytest tests/test_session_manager.py -v
```

Expected: `ModuleNotFoundError` o `ImportError`.

- [ ] **Step 4: Implementar `session_manager.py`**

Crear `src/autoclave/ui_pyside/services/session_manager.py`:

```python
import hashlib


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


class SessionManager:
    _current_user: dict | None = None

    @classmethod
    def login(cls, user_dict: dict) -> None:
        cls._current_user = {
            "id":      user_dict["id"],
            "nombre":  user_dict["nombre"],
            "usuario": user_dict["usuario"],
            "rol":     user_dict["rol"],
        }

    @classmethod
    def logout(cls) -> None:
        cls._current_user = None

    @classmethod
    def is_authenticated(cls) -> bool:
        return cls._current_user is not None

    @classmethod
    def current_role(cls) -> str | None:
        return cls._current_user["rol"] if cls._current_user else None

    @classmethod
    def current_user(cls) -> dict | None:
        return cls._current_user
```

- [ ] **Step 5: Ejecutar — verificar que PASA**

```bash
pytest tests/test_session_manager.py -v
```

Expected: todos `PASSED`.

- [ ] **Step 6: Commit**

```bash
git add src/autoclave/ui_pyside/ tests/test_session_manager.py
git commit -m "feat: SessionManager con login/logout/hash en ui_pyside"
```

---

## Task 4: `BackendClient.patch()` + `CycleManager._path` + `PATCH /cycle/parameters`

**Files:**
- Modify: `src/autoclave/ui/service_ui/backend_client.py`
- Modify: `src/autoclave/core/cycle_manager.py`
- Modify: `src/autoclave/backend/server.py`
- Create: `tests/test_patch_cycle_parameters.py`

- [ ] **Step 1: Escribir tests**

Crear `tests/test_patch_cycle_parameters.py`:

```python
import json
import pytest
from unittest.mock import MagicMock, patch
from autoclave.ui.service_ui.backend_client import BackendClient
from autoclave.core.cycle_manager import CycleManager


# ── BackendClient.patch() ────────────────────────────────────────────

def test_patch_envia_body_correcto():
    client = BackendClient("http://localhost:8000")
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"ok": True}
    mock_resp.raise_for_status = MagicMock()

    with patch("requests.patch", return_value=mock_resp) as mock_req:
        result = client.patch("/cycle/parameters", {"tiempo_secado": 15.0})
        mock_req.assert_called_once_with(
            "http://localhost:8000/cycle/parameters",
            json={"tiempo_secado": 15.0},
            timeout=0.8,
        )
        assert result == {"ok": True}


def test_patch_body_none_envia_dict_vacio():
    client = BackendClient("http://localhost:8000")
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"ok": True}
    mock_resp.raise_for_status = MagicMock()

    with patch("requests.patch", return_value=mock_resp) as mock_req:
        client.patch("/cycle/parameters")
        mock_req.assert_called_once_with(
            "http://localhost:8000/cycle/parameters",
            json={},
            timeout=0.8,
        )


# ── CycleManager._path ───────────────────────────────────────────────

def test_cycle_manager_asigna_path_al_cargar(tmp_path):
    cycle_data = {
        "cycle_id": "ciclo_test",
        "display_name": "Test",
        "parameters": {
            "esterilizacion": {
                "tiempo_secado": {
                    "value": 2.0, "type": "float", "unit": "min", "min": 0, "max": 120
                }
            }
        },
    }
    cycle_file = tmp_path / "ciclo_test.json"
    cycle_file.write_text(json.dumps(cycle_data), encoding="utf-8")

    cm = CycleManager()
    cm._load_from_folder(str(tmp_path), source="user")

    cycle = cm.cycles.get("ciclo_test")
    assert cycle is not None
    assert hasattr(cycle, "_path")
    assert cycle._path == str(cycle_file)
    assert cycle.source == "user"


def test_cycle_manager_asigna_source_factory(tmp_path):
    cycle_data = {
        "cycle_id": "ciclo_fab",
        "display_name": "Fábrica",
        "parameters": {},
    }
    (tmp_path / "ciclo_fab.json").write_text(json.dumps(cycle_data), encoding="utf-8")

    cm = CycleManager()
    cm._load_from_folder(str(tmp_path), source="factory")

    assert cm.cycles["ciclo_fab"].source == "factory"
```

- [ ] **Step 2: Ejecutar — verificar que FALLA**

```bash
pytest tests/test_patch_cycle_parameters.py -v
```

Expected: `AttributeError: 'BackendClient' object has no attribute 'patch'` + `AssertionError` en los tests de `_path`.

- [ ] **Step 3: Agregar `patch()` a `BackendClient`**

En `src/autoclave/ui/service_ui/backend_client.py`, después del método `post()`:

```python
def patch(self, path: str, body: dict | None = None, **kwargs) -> dict:
    r = requests.patch(
        f"{self.base_url}{path}",
        json=body or {},
        timeout=0.8,
        **kwargs,
    )
    r.raise_for_status()
    return r.json()
```

- [ ] **Step 4: Agregar `_path` en `CycleManager._load_from_folder()`**

En `src/autoclave/core/cycle_manager.py`, localizar la línea `cycle.source = source` (~línea 59) y agregar justo debajo:

```python
cycle.source = source
cycle._path  = full_path
```

- [ ] **Step 5: Agregar endpoint `PATCH /cycle/parameters` a `server.py`**

En `src/autoclave/backend/server.py`, agregar al final del archivo:

```python
@app.patch("/cycle/parameters")
def update_cycle_parameters(body: dict = Body(...)):
    """Actualiza parámetros del ciclo seleccionado en memoria y persiste si es ciclo user."""
    cycle = context.cycle_manager.get_selected_cycle()

    if "tiempo_secado" in body:
        try:
            value = float(body["tiempo_secado"])
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=422,
                detail="tiempo_secado debe ser numérico",
            )
        if not (0.0 <= value <= 120.0):
            raise HTTPException(
                status_code=422,
                detail="tiempo_secado fuera de rango (0-120 min)",
            )
        cycle.parameters["esterilizacion"]["tiempo_secado"]["value"] = value

    if getattr(cycle, "source", "") == "user" and hasattr(cycle, "_path"):
        _save_cycle_json(cycle)

    return {"ok": True}


def _save_cycle_json(cycle) -> None:
    """Escribe cycle.parameters de vuelta al JSON del ciclo (solo ciclos user)."""
    import json as _json
    from pathlib import Path as _Path

    path = _Path(cycle._path)
    with open(path, "r", encoding="utf-8") as f:
        data = _json.load(f)
    data["parameters"] = cycle.parameters
    with open(path, "w", encoding="utf-8") as f:
        _json.dump(data, f, indent=4, ensure_ascii=False)
```

- [ ] **Step 6: Ejecutar — verificar que PASA**

```bash
pytest tests/test_patch_cycle_parameters.py -v
```

Expected: todos `PASSED`.

- [ ] **Step 7: Verificar suite completa sin regresiones**

```bash
pytest tests/ -v
```

Expected: todos los tests previos siguen pasando.

- [ ] **Step 8: Commit**

```bash
git add src/autoclave/ui/service_ui/backend_client.py \
        src/autoclave/core/cycle_manager.py \
        src/autoclave/backend/server.py \
        tests/test_patch_cycle_parameters.py
git commit -m "feat: BackendClient.patch(), _path en ciclos, PATCH /cycle/parameters"
```

---

## Task 5: Estructura del paquete `ui_pyside` + re-export `BackendClient`

**Files:**
- Create: `src/autoclave/ui_pyside/views/__init__.py`
- Create: `src/autoclave/ui_pyside/services/backend_client.py`

- [ ] **Step 1: Crear `views/__init__.py`**

```bash
mkdir -p src/autoclave/ui_pyside/views
echo "" > src/autoclave/ui_pyside/views/__init__.py
```

- [ ] **Step 2: Crear `services/backend_client.py`**

Crear `src/autoclave/ui_pyside/services/backend_client.py`:

```python
from autoclave.ui.service_ui.backend_client import BackendClient

__all__ = ["BackendClient"]
```

- [ ] **Step 3: Smoke test de imports**

```bash
python -c "
from autoclave.ui_pyside.services.backend_client import BackendClient
from autoclave.ui_pyside.services.session_manager import SessionManager, hash_password
print('imports OK')
"
```

Expected: `imports OK`

- [ ] **Step 4: Commit**

```bash
git add src/autoclave/ui_pyside/views/__init__.py \
        src/autoclave/ui_pyside/services/backend_client.py
git commit -m "feat: estructura paquete ui_pyside y re-export BackendClient"
```

---

## Task 6: `MainWindowFluent` — shell principal

**Files:**
- Create: `src/autoclave/ui_pyside/main_window.py`

- [ ] **Step 1: Crear `main_window.py`**

Crear `src/autoclave/ui_pyside/main_window.py`:

```python
import subprocess
import sys
from datetime import datetime

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QFrame,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import PushButton, setTheme, Theme


class MainWindowFluent(QMainWindow):
    BACKEND_URL = "http://localhost:8000"

    def __init__(self, tkinter_proc=None):
        super().__init__()
        self._tkinter_proc = tkinter_proc
        setTheme(Theme.DARK)
        self.setWindowTitle("Especifika — Autoclave")
        self.setMinimumSize(800, 600)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_header())

        self._stack = QStackedWidget()
        root.addWidget(self._stack, stretch=1)

        root.addWidget(self._build_footer())

        # Importar vistas aquí para evitar imports circulares al importar main_window
        from autoclave.ui_pyside.views.home   import HomeView
        from autoclave.ui_pyside.views.secado import SecadoView
        from autoclave.ui_pyside.views.login  import LoginView
        from autoclave.ui_pyside.views.ciclos import CiclosView

        self._home   = HomeView(nav_callback=self.navigate_to)
        self._secado = SecadoView(nav_callback=self.navigate_to)
        self._login  = LoginView(nav_callback=self.navigate_to)
        self._ciclos = CiclosView(nav_callback=self.navigate_to)

        for view in (self._home, self._secado, self._login, self._ciclos):
            self._stack.addWidget(view)

        self._stack.setCurrentWidget(self._home)

        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self._tick_clock)
        self._clock_timer.start(1000)
        self._tick_clock()

    # ── Header ────────────────────────────────────────────────────────

    def _build_header(self) -> QFrame:
        header = QFrame()
        header.setFixedHeight(64)
        header.setStyleSheet("background-color: #1a2a3a;")

        layout = QHBoxLayout(header)
        layout.setContentsMargins(20, 0, 20, 0)

        logo = QLabel("e-specifika")
        logo.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        logo.setStyleSheet("color: white;")
        layout.addWidget(logo)

        layout.addStretch()

        self._lbl_time = QLabel("--:--")
        self._lbl_time.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
        self._lbl_time.setStyleSheet("color: white;")
        layout.addWidget(self._lbl_time)

        self._lbl_date = QLabel("")
        self._lbl_date.setFont(QFont("Segoe UI", 11))
        self._lbl_date.setStyleSheet("color: #aaccee; margin-left: 10px;")
        layout.addWidget(self._lbl_date)

        layout.addStretch()

        return header

    # ── Footer ────────────────────────────────────────────────────────

    def _build_footer(self) -> QFrame:
        footer = QFrame()
        footer.setFixedHeight(56)
        footer.setStyleSheet("background-color: #5789a7;")

        layout = QHBoxLayout(footer)
        layout.setContentsMargins(20, 0, 20, 0)

        btn_salir = PushButton("Salir")
        btn_salir.clicked.connect(self.close)
        layout.addWidget(btn_salir)

        layout.addStretch()

        lbl_ver = QLabel("v1.0")
        lbl_ver.setStyleSheet("color: white;")
        layout.addWidget(lbl_ver)

        layout.addStretch()

        btn_monitor = PushButton("Monitor")
        btn_monitor.clicked.connect(self._open_monitor)
        layout.addWidget(btn_monitor)

        return footer

    # ── Navegación ───────────────────────────────────────────────────

    def navigate_to(self, view_name: str) -> None:
        views = {
            "home":   self._home,
            "secado": self._secado,
            "login":  self._login,
            "ciclos": self._ciclos,
        }
        target = views.get(view_name)
        if target:
            self._stack.setCurrentWidget(target)

    # ── Reloj ────────────────────────────────────────────────────────

    def _tick_clock(self) -> None:
        now = datetime.now()
        self._lbl_time.setText(now.strftime("%H:%M"))
        self._lbl_date.setText(now.strftime("%d %b %Y"))

    # ── Monitor tkinter ──────────────────────────────────────────────

    def _open_monitor(self) -> None:
        if self._tkinter_proc is None or self._tkinter_proc.poll() is not None:
            self._tkinter_proc = subprocess.Popen(
                [sys.executable, "-m", "autoclave.ui.main"],
            )

    # ── Cierre ──────────────────────────────────────────────────────

    def closeEvent(self, event) -> None:
        self._clock_timer.stop()
        if self._tkinter_proc and self._tkinter_proc.poll() is None:
            self._tkinter_proc.terminate()
        event.accept()
```

- [ ] **Step 2: Smoke test de import (sin QApplication)**

```bash
python -c "import autoclave.ui_pyside.main_window; print('import OK')"
```

Expected: `import OK`

- [ ] **Step 3: Commit**

```bash
git add src/autoclave/ui_pyside/main_window.py
git commit -m "feat: MainWindowFluent — shell PySide6 con header, footer y navegación"
```

---

## Task 7: Vista Home (3 cards)

**Files:**
- Create: `src/autoclave/ui_pyside/views/home.py`

- [ ] **Step 1: Crear `home.py`**

Crear `src/autoclave/ui_pyside/views/home.py`:

```python
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, CardWidget, SubtitleLabel


class HomeView(QWidget):
    def __init__(self, nav_callback):
        super().__init__()
        self._nav = nav_callback

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 30, 40, 30)
        layout.setSpacing(20)

        title = SubtitleLabel("MENÚ PRINCIPAL")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        cards_data = [
            (
                "⏱  Tiempo de Secado",
                "Ajusta el tiempo de secado del ciclo activo",
                "secado",
            ),
            (
                "🖨  Imprimir Ciclos",
                "Consulta e imprime el historial de ciclos",
                "ciclos",
            ),
            (
                "👤  Login",
                "Inicia sesión en el sistema",
                "login",
            ),
        ]

        grid = QGridLayout()
        grid.setSpacing(20)

        for idx, (title_text, desc_text, view_name) in enumerate(cards_data):
            card = self._make_card(title_text, desc_text, view_name)
            row, col = divmod(idx, 2)
            grid.addWidget(card, row, col)

        # Centrar la tercera card si hay número impar
        if len(cards_data) % 2 == 1:
            last_row = len(cards_data) // 2
            grid.setColumnStretch(0, 1)
            grid.setColumnStretch(1, 1)

        wrapper = QWidget()
        wrapper.setLayout(grid)
        layout.addWidget(wrapper, stretch=1)

    def _make_card(self, title_text: str, desc_text: str, view_name: str) -> CardWidget:
        card = CardWidget()
        card.setMinimumSize(280, 140)
        card.setCursor(Qt.CursorShape.PointingHandCursor)

        inner = QVBoxLayout(card)
        inner.setContentsMargins(24, 20, 24, 20)
        inner.setSpacing(8)

        lbl_title = SubtitleLabel(title_text)
        lbl_desc  = BodyLabel(desc_text)
        lbl_desc.setWordWrap(True)

        inner.addWidget(lbl_title)
        inner.addWidget(lbl_desc)
        inner.addStretch()

        # Capturar view_name en el closure con argumento default
        card.mousePressEvent = lambda e, vn=view_name: self._nav(vn)

        return card
```

- [ ] **Step 2: Smoke test**

```bash
python -c "from autoclave.ui_pyside.views.home import HomeView; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/autoclave/ui_pyside/views/home.py
git commit -m "feat: HomeView con 3 cards de navegación"
```

---

## Task 8: Vista Secado

**Files:**
- Create: `src/autoclave/ui_pyside/views/secado.py`

- [ ] **Step 1: Crear `secado.py`**

Crear `src/autoclave/ui_pyside/views/secado.py`:

```python
import requests
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    DoubleSpinBox,
    InfoBar,
    InfoBarPosition,
    PrimaryPushButton,
    PushButton,
    SubtitleLabel,
)


class SecadoView(QWidget):
    BACKEND_URL = "http://localhost:8000"

    def __init__(self, nav_callback):
        super().__init__()
        self._nav = nav_callback

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 30, 40, 30)
        layout.setSpacing(20)

        # Barra superior con botón volver
        header = QHBoxLayout()
        btn_back = PushButton("← Volver")
        btn_back.clicked.connect(lambda: self._nav("home"))
        header.addWidget(btn_back)
        header.addStretch()
        layout.addLayout(header)

        layout.addWidget(SubtitleLabel("Tiempo de Secado"))
        desc = BodyLabel("Ajusta el tiempo de secado para el ciclo activo (0 – 120 min).")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # SpinBox
        spin_row = QHBoxLayout()
        spin_row.addWidget(BodyLabel("Tiempo de secado (min):"))
        self._spin = DoubleSpinBox()
        self._spin.setRange(0.0, 120.0)
        self._spin.setSingleStep(0.5)
        self._spin.setDecimals(1)
        self._spin.setFixedWidth(140)
        spin_row.addWidget(self._spin)
        spin_row.addStretch()
        layout.addLayout(spin_row)

        btn_save = PrimaryPushButton("Guardar")
        btn_save.setFixedWidth(160)
        btn_save.clicked.connect(self._save)
        layout.addWidget(btn_save)

        layout.addStretch()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._load_current()

    def _load_current(self) -> None:
        try:
            r = requests.get(f"{self.BACKEND_URL}/cycle", timeout=1.5)
            r.raise_for_status()
            value = (
                r.json()["parameters"]["esterilizacion"]["tiempo_secado"]["value"]
            )
            self._spin.setValue(float(value))
        except Exception:
            pass  # mantiene valor actual si el backend no está disponible

    def _save(self) -> None:
        value = self._spin.value()
        try:
            r = requests.patch(
                f"{self.BACKEND_URL}/cycle/parameters",
                json={"tiempo_secado": value},
                timeout=2.0,
            )
            r.raise_for_status()
            InfoBar.success(
                title="Guardado",
                content=f"Tiempo de secado actualizado a {value:.1f} min",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self,
            )
        except requests.HTTPError as e:
            detail = ""
            try:
                detail = e.response.json().get("detail", str(e))
            except Exception:
                detail = str(e)
            InfoBar.error(
                title="Error al guardar",
                content=detail,
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=4000,
                parent=self,
            )
        except Exception:
            InfoBar.warning(
                title="Sin conexión",
                content="No se pudo conectar al backend",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=4000,
                parent=self,
            )
```

- [ ] **Step 2: Smoke test**

```bash
python -c "from autoclave.ui_pyside.views.secado import SecadoView; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/autoclave/ui_pyside/views/secado.py
git commit -m "feat: SecadoView — editar tiempo de secado via PATCH backend"
```

---

## Task 9: Vista Login

**Files:**
- Create: `src/autoclave/ui_pyside/views/login.py`

- [ ] **Step 1: Crear `login.py`**

Crear `src/autoclave/ui_pyside/views/login.py`:

```python
import hashlib

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    InfoBar,
    InfoBarPosition,
    LineEdit,
    PasswordLineEdit,
    PrimaryPushButton,
    PushButton,
    SubtitleLabel,
)


def _hash_pw(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


class LoginView(QWidget):
    def __init__(self, nav_callback):
        super().__init__()
        self._nav = nav_callback

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 30, 40, 30)
        layout.setSpacing(16)

        # Barra superior
        header = QHBoxLayout()
        btn_back = PushButton("← Volver")
        btn_back.clicked.connect(lambda: self._nav("home"))
        header.addWidget(btn_back)
        header.addStretch()
        layout.addLayout(header)

        layout.addWidget(SubtitleLabel("LOGIN"))

        # Formulario centrado
        form = QVBoxLayout()
        form.setSpacing(12)

        form.addWidget(BodyLabel("Nombre de usuario"))
        self._username = LineEdit()
        self._username.setPlaceholderText("usuario")
        self._username.setFixedWidth(320)
        form.addWidget(self._username)

        form.addWidget(BodyLabel("Contraseña"))
        self._password = PasswordLineEdit()
        self._password.setPlaceholderText("contraseña")
        self._password.setFixedWidth(320)
        form.addWidget(self._password)

        btn_login = PrimaryPushButton("Iniciar Sesión")
        btn_login.setFixedWidth(320)
        btn_login.clicked.connect(self._do_login)
        self._password.returnPressed.connect(self._do_login)
        form.addWidget(btn_login)

        layout.addLayout(form)
        layout.addStretch()

    def _do_login(self) -> None:
        from autoclave.services.domain.logging.db_manager import DbManager
        from autoclave.ui_pyside.services.session_manager import SessionManager

        username = self._username.text().strip()
        password = self._password.text()

        if not username or not password:
            InfoBar.warning(
                title="Campos vacíos",
                content="Ingresa usuario y contraseña",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self,
            )
            return

        db   = DbManager()
        user = db.get_usuario_by_username(username)

        if user is None or user["hash_pw"] != _hash_pw(password):
            InfoBar.error(
                title="Acceso denegado",
                content="Usuario o contraseña incorrectos",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=4000,
                parent=self,
            )
            return

        SessionManager.login(user)
        self._password.clear()

        InfoBar.success(
            title="Sesión iniciada",
            content=f"Bienvenido, {user['nombre']}",
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=3000,
            parent=self,
        )
        self._nav("home")
```

- [ ] **Step 2: Smoke test**

```bash
python -c "from autoclave.ui_pyside.views.login import LoginView; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/autoclave/ui_pyside/views/login.py
git commit -m "feat: LoginView — autenticación con hash SHA-256 y SessionManager"
```

---

## Task 10: Vista Ciclos

**Files:**
- Create: `src/autoclave/ui_pyside/views/ciclos.py`

- [ ] **Step 1: Crear `ciclos.py`**

Crear `src/autoclave/ui_pyside/views/ciclos.py`:

```python
from datetime import datetime

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QTextDocument
from PySide6.QtPrintSupport import QPrintDialog, QPrinter
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    BodyLabel,
    CalendarPicker,
    PrimaryPushButton,
    PushButton,
    SubtitleLabel,
    TableWidget,
)


class CiclosView(QWidget):
    def __init__(self, nav_callback):
        super().__init__()
        self._nav = nav_callback

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        # Barra superior
        header_row = QHBoxLayout()
        btn_back = PushButton("← Volver")
        btn_back.clicked.connect(lambda: self._nav("home"))
        header_row.addWidget(btn_back)
        header_row.addStretch()
        layout.addLayout(header_row)

        layout.addWidget(SubtitleLabel("Historial de Ciclos"))

        # Filtro de fecha
        filter_row = QHBoxLayout()
        filter_row.addWidget(BodyLabel("Desde:"))
        self._desde = CalendarPicker()
        self._desde.setDate(QDate.currentDate().addDays(-30))
        filter_row.addWidget(self._desde)

        filter_row.addWidget(BodyLabel("Hasta:"))
        self._hasta = CalendarPicker()
        self._hasta.setDate(QDate.currentDate())
        filter_row.addWidget(self._hasta)

        btn_filter = PushButton("Filtrar")
        btn_filter.clicked.connect(self._load_data)
        filter_row.addWidget(btn_filter)
        filter_row.addStretch()
        layout.addLayout(filter_row)

        # Tabla
        self._table = TableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels(
            ["#", "Programa", "Fecha inicio", "Duración (min)", "Resultado"]
        )
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self._table, stretch=1)

        # Botón imprimir
        btn_print = PrimaryPushButton("Imprimir")
        btn_print.setFixedWidth(160)
        btn_print.clicked.connect(self._print_table)
        layout.addWidget(btn_print, alignment=Qt.AlignmentFlag.AlignRight)

        self._load_data()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._load_data()

    def _load_data(self) -> None:
        from autoclave.services.domain.logging.db_manager import DbManager

        desde_q = self._desde.getDate()
        hasta_q = self._hasta.getDate()
        desde = desde_q.toString("yyyy-MM-dd") if desde_q.isValid() else None
        hasta = hasta_q.toString("yyyy-MM-dd") if hasta_q.isValid() else None

        rows = DbManager().get_ciclos_rango(desde=desde, hasta=hasta, limite=200)

        self._table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            inicio = row["fecha_inicio"] or ""
            fin    = row["fecha_fin"] or ""
            try:
                t0  = datetime.fromisoformat(inicio)
                t1  = datetime.fromisoformat(fin)
                dur = str((t1 - t0).seconds // 60)
            except Exception:
                dur = "—"

            self._table.setItem(i, 0, QTableWidgetItem(str(row["numero_ciclo"])))
            self._table.setItem(i, 1, QTableWidgetItem(row["nombre_ciclo"] or ""))
            self._table.setItem(i, 2, QTableWidgetItem(inicio[:19]))
            self._table.setItem(i, 3, QTableWidgetItem(dur))
            self._table.setItem(i, 4, QTableWidgetItem(row["resultado"] or ""))

    def _print_table(self) -> None:
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        dialog  = QPrintDialog(printer, self)
        if dialog.exec() != QPrintDialog.DialogCode.Accepted:
            return
        doc = QTextDocument()
        doc.setHtml(self._build_html())
        doc.print_(printer)

    def _build_html(self) -> str:
        headers = ["#", "Programa", "Fecha inicio", "Duración (min)", "Resultado"]
        th_cells = "".join(
            f"<th style='padding:6px 8px; background:#5789a7; color:white;"
            f" border:1px solid #5789a7;'>{h}</th>"
            for h in headers
        )
        rows_html = ""
        for r in range(self._table.rowCount()):
            cells = "".join(
                f"<td style='padding:4px 8px; border:1px solid #ccc;'>"
                f"{self._table.item(r, c).text() if self._table.item(r, c) else ''}</td>"
                for c in range(self._table.columnCount())
            )
            rows_html += f"<tr>{cells}</tr>"

        return (
            "<html><body>"
            "<h2 style='font-family:Segoe UI;'>Historial de Ciclos — Especifika</h2>"
            "<table style='border-collapse:collapse; font-family:Segoe UI;"
            " font-size:12px; width:100%;'>"
            f"<thead><tr>{th_cells}</tr></thead>"
            f"<tbody>{rows_html}</tbody>"
            "</table></body></html>"
        )
```

- [ ] **Step 2: Smoke test**

```bash
python -c "from autoclave.ui_pyside.views.ciclos import CiclosView; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/autoclave/ui_pyside/views/ciclos.py
git commit -m "feat: CiclosView — historial con filtro de fecha e impresión"
```

---

## Task 11: Actualizar `main.py` — PySide6 como punto de entrada

**Files:**
- Modify: `src/autoclave/main.py`

- [ ] **Step 1: Leer `main.py` antes de editar**

Revisar `src/autoclave/main.py` para identificar el bloque `# ── 3. Arrancar UI` (aproximadamente desde línea 101).

- [ ] **Step 2: Reemplazar el bloque de arranque UI**

Localizar desde `# ── 3. Arrancar UI` hasta el final del archivo y reemplazar con:

```python
    # ── 3. Arrancar UI (PySide6) ────────────────────────────────────────────
    import sys
    from PySide6.QtWidgets import QApplication
    from autoclave.ui_pyside.main_window import MainWindowFluent
    from autoclave.ui.service_ui.backend_client import BackendClient as _BC

    # Lanzar ventana tkinter como subprocess para monitoreo de ciclo
    tkinter_proc = subprocess.Popen(
        [sys.executable, "-m", "autoclave.ui.main"],
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )

    qt_app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindowFluent(tkinter_proc=tkinter_proc)
    window.showMaximized()

    def on_quit():
        logger.info("Cerrando aplicación...")
        try:
            _BC(BACKEND_URL).post("/outputs/reset")
            logger.info("Salidas digitales apagadas")
        except Exception as e:
            logger.warning("No se pudieron apagar las salidas: %s", e)
        if tkinter_proc.poll() is None:
            tkinter_proc.terminate()
        if backend_process:
            backend_process.terminate()
            try:
                backend_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                backend_process.kill()

    qt_app.aboutToQuit.connect(on_quit)
    logger.info("UI PySide6 iniciada")
    sys.exit(qt_app.exec())
```

> **Nota:** eliminar las líneas de `backend`, `ui_service`, `door_commands`, `on_close` y `app = InterfazPrincipal(...)` del bloque original que ya no se usan. El `on_close` queda reemplazado por `on_quit`.

- [ ] **Step 3: Smoke test de import (sin ejecutar)**

```bash
python -c "import ast; ast.parse(open('src/autoclave/main.py').read()); print('sintaxis OK')"
```

Expected: `sintaxis OK`

- [ ] **Step 4: Ejecutar la aplicación completa**

```bash
python -m autoclave.main
```

Verificar visualmente:
- Ventana PySide6 abre con header (logo + reloj), 3 cards en el centro, footer con Salir / Monitor
- Botón **Monitor** abre la ventana tkinter existente
- Card **Tiempo de Secado** → muestra valor actual del backend, guarda con PATCH
- Card **Login** → credenciales `admin` / `admin1234` funcionan
- Card **Imprimir Ciclos** → tabla con historial (vacía si no hay ciclos), filtros de fecha responden

- [ ] **Step 5: Ejecutar suite de tests final**

```bash
pytest tests/ -v
```

Expected: todos los tests previos siguen pasando + los nuevos.

- [ ] **Step 6: Commit**

```bash
git add src/autoclave/main.py
git commit -m "feat: main.py arranca PySide6 — menú principal con 3 vistas funcionales"
```

---

## Self-Review

### Spec coverage

| Requisito spec | Task |
|---|---|
| Stack: PySide6 + Fluent-Widgets + pyqtgraph + PyInstaller | Task 1 |
| main.py reemplaza tkinter | Task 11 |
| Tkinter como subprocess | Task 11 |
| Header logo + reloj | Task 6 |
| Footer Salir + Monitor | Task 6 |
| 3 cards en home | Task 7 |
| Tiempo secado GET actual + PATCH | Task 4 + Task 8 |
| Tabla ciclos con filtro fecha | Task 2 + Task 10 |
| Impresión QPrinter | Task 10 |
| Login SHA-256 + DB | Task 2 + Task 3 + Task 9 |
| Tabla usuarios en DB | Task 2 |
| Admin por defecto admin/admin1234 | Task 2 |
| SessionManager en memoria | Task 3 |
| on_close apaga salidas + procesos | Task 11 |
| BackendClient.patch() | Task 4 |
| CycleManager._path para persistencia | Task 4 |

Todos los requisitos cubiertos.
