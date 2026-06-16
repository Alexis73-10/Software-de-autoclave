# Spec: Menú Principal PySide6 — v1 (3 opciones)

**Fecha:** 2026-06-16  
**Estado:** aprobado  
**Rama objetivo:** dev

---

## Contexto

La UI actual usa tkinter + customtkinter. Esta spec define la primera entrega de la migración a PySide6, que arrancará con un menú de 3 opciones funcionales. La ventana tkinter existente sigue corriendo en paralelo durante la transición; se migrará al completo cuando lleguen los SVGs y las curvas del ciclo.

El mockup de referencia es `src/autoclave/images/DISEÑO INTERFAZ -P1 mockup.jpg`. Se usa como guía visual; el diseño final se ajustará cuando llegue el PDF de curvas definitivo.

---

## Stack

| Librería | Rol |
|---|---|
| PySide6 | Framework base — ventana, eventos, threading |
| PySide6-Fluent-Widgets | FluentWindow, CardWidget, NavigationBar, badges, DatePicker |
| pyqtgraph | Gráficas en tiempo real (preparado, se integra en entrega futura) |
| PyInstaller | Empaquetado final |

Lo que **no cambia** en esta entrega: `BackendClient`, `UIServiceBackend`, `DoorCommandService`, backend FastAPI, DB SQLite, wizard de instalación, lógica de ClockGuard/HMAC.

---

## Arquitectura

### Estructura de archivos

```
src/autoclave/ui_pyside/
  ├── __init__.py
  ├── main_window.py          ← FluentWindow principal + header + footer
  ├── views/
  │   ├── __init__.py
  │   ├── home.py             ← menú con 3 cards
  │   ├── secado.py           ← agregar tiempo de secado
  │   ├── ciclos.py           ← historial e impresión de ciclos
  │   └── login.py            ← autenticación de usuario
  └── services/
      ├── __init__.py
      └── backend_client.py   ← importa y usa BackendClient de ui.service_ui directamente
```

`main.py` se actualiza para arrancar PySide6 en lugar de tkinter directamente.

### Punto de entrada (`main.py`)

Secuencia de arranque (en orden):

1. Verificar instalación — mismo `get_installation_profile()` / `ClockTamperedError` actual
2. Iniciar FastAPI backend como subprocess (solo `door_id=1`, igual que hoy)
3. Esperar backend con `wait_for_backend()` (misma función)
4. Lanzar `InterfazPrincipal` tkinter como subprocess (preserva monitoreo de ciclo)
5. Crear `QApplication` y abrir `MainWindowFluent`

### Ciclo de vida — `on_close`

```
1. BackendClient.reset_outputs()     ← apagar salidas digitales
2. Terminar proceso tkinter
3. Terminar proceso FastAPI
4. QApplication.quit() → sys.exit(0)
```

---

## Pantalla: Menú Principal (`home.py`)

### Layout

```
┌─────────────────────────────────────────────────────┐
│  [logo e-specifika]   16:00  12 oct 2026   🔔  ⚙    │
├─────────────────────────────────────────────────────┤
│                   MENÚ PRINCIPAL                    │
│                                                     │
│  ┌──────────────────────┐ ┌──────────────────────┐  │
│  │  ⏱  Tiempo de Secado │ │  🖨  Imprimir Ciclos  │  │
│  │  Ajusta el tiempo de │ │  Consulta e imprime   │  │
│  │  secado del ciclo    │ │  el historial         │  │
│  └──────────────────────┘ └──────────────────────┘  │
│                                                     │
│              ┌──────────────────────┐               │
│              │  👤  Login           │               │
│              │  Inicia sesión       │               │
│              └──────────────────────┘               │
└─────────────────────────────────────────────────────┘
│  [← Salir]          [🖥 Monitor]          v1.0      │
└─────────────────────────────────────────────────────┘
```

- Cards implementadas con `CardWidget` de PySide6-Fluent-Widgets
- Cada card hace `navigate_to(view)` al hacer clic
- Header fijo: logo Especifika, reloj actualizado cada segundo (`QTimer`), icono campana (sin acción en v1), icono engranaje (sin acción en v1)
- Footer: botón **Salir** (dispara `on_close`), botón **Monitor** (levanta/enfoca la ventana tkinter)

---

## Pantalla: Tiempo de Secado (`secado.py`)

### Comportamiento

- Al abrir: GET `http://localhost:8000/cycle` → extrae `parameters.tiempo_secado.value` y lo muestra en el spin box
- Control: `SpinBox` de Fluent-Widgets, rango 0–120 min, paso 1
- Botón **Guardar**: PATCH `http://localhost:8000/cycle/parameters` con `{"tiempo_secado": valor}`
  - Éxito: badge verde "Guardado" durante 3 s
  - Error (HTTP o conexión): badge rojo con texto del error
- Botón **← Volver**: regresa a home sin guardar

### Endpoint requerido en el backend

Si `PATCH /cycle/parameters` no existe aún, se crea en esta entrega en `server.py`.

---

## Pantalla: Imprimir Ciclos (`ciclos.py`)

### Comportamiento

- Lee de `autoclave.db` usando `DbManager` / `CycleLogger` existente
- Tabla con columnas: `#`, `Programa`, `Fecha inicio`, `Duración (min)`, `Resultado`
- Filtro de fecha: `DateRangePicker` de Fluent-Widgets (opcional aplicar, por defecto últimos 30 días)
- Botón **Imprimir**:
  - Abre diálogo `QPrintDialog` del sistema
  - Renderiza la tabla filtrada como HTML via `QPrinter` → genera PDF o envía a impresora física
- Botón **← Volver**: regresa a home

---

## Pantalla: Login (`login.py`)

### Modelo de datos — tabla `usuarios`

```sql
CREATE TABLE IF NOT EXISTS usuarios (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre   TEXT NOT NULL,
    usuario  TEXT UNIQUE NOT NULL,
    hash_pw  TEXT NOT NULL,
    rol      TEXT DEFAULT 'operador',
    activo   INTEGER DEFAULT 1
);
```

Se crea via `DbManager.init_db()` con `CREATE TABLE IF NOT EXISTS` — no rompe tablas existentes.

**Usuario por defecto** (creado si la tabla queda vacía tras `init_db`):
- usuario: `admin`
- contraseña: `admin1234`
- rol: `admin`

### Hash de contraseña

`hashlib.sha256` — sin dependencia extra. Formato almacenado: `sha256(password.encode()).hexdigest()`.

### Sesión

Singleton `SessionManager` en memoria:

```python
class SessionManager:
    _current_user: dict | None = None   # {"usuario": ..., "rol": ..., "nombre": ...}

    @classmethod
    def login(cls, user_dict): ...
    @classmethod
    def logout(cls): ...
    @classmethod
    def is_authenticated(cls) -> bool: ...
    @classmethod
    def current_role(cls) -> str | None: ...
```

No persiste entre reinicios de la app. En v1 solo valida que la sesión existe; la autorización por rol se construye en entregas futuras.

### Comportamiento del formulario

- Campos: `LineEdit` usuario, `PasswordLineEdit` contraseña (Fluent-Widgets)
- Botón **Iniciar Sesión**: busca usuario en DB, compara hash, llama `SessionManager.login()` si correcto
  - Éxito: navega a home, badge verde "Sesión iniciada" en header
  - Error: `InfoBar` roja "Usuario o contraseña incorrectos"
- Botón **← Volver**: regresa a home sin autenticar

---

## Integración con sistema existente

### BackendClient

Las vistas en `ui_pyside/` importan `BackendClient` directamente desde `autoclave.ui.service_ui.backend_client`. No se duplica lógica de HTTP; el archivo `services/backend_client.py` solo re-exporta la clase para mantener imports limpios dentro del módulo.

### Ventana tkinter durante transición

`main.py` lanza `InterfazPrincipal` como subprocess con `subprocess.Popen`. El botón **Monitor** del footer PySide6 hace `Popen` si el proceso no está vivo, o lo enfoca si ya corre. La ventana tkinter mantiene toda la funcionalidad actual de monitoreo (sensores, puertas, inicio de ciclo).

### Endpoint PATCH `/cycle/parameters`

Si no existe en `backend/server.py`, se agrega en esta entrega:

```python
@app.patch("/cycle/parameters")
async def update_cycle_parameters(params: dict):
    # actualiza parametros del ciclo activo en context
    ...
```

---

## Testing

| Caso | Tipo |
|---|---|
| Tiempo de secado: GET muestra valor actual | integración (backend mock) |
| Tiempo de secado: PATCH guarda y badge aparece | integración |
| Login: credenciales correctas → sesión activa | unit |
| Login: credenciales incorrectas → InfoBar error | unit |
| Login: usuario inactivo rechazado | unit |
| Ciclos: tabla muestra registros de DB | integración (DB real) |
| `init_db` crea tabla usuarios sin romper otras | unit |
| SessionManager: login/logout/is_authenticated | unit |

---

## Fuera de alcance (v1)

- Sidebar/nav lateral (se agrega cuando lleguen más vistas)
- Icono campana con notificaciones reales
- Icono engranaje con opciones
- Autorización por rol (admin vs operador)
- Impresión de PDF con firma digital
- Gráficas pyqtgraph (entrega futura, cuando lleguen curvas)
- Migración completa de CycleWindow a PySide6
