# Etapa 4 — SAF-01: cierre de la sesión por inactividad (y estabilidad de la suite)

**Fecha:** 2026-10-08 · **Rama:** `dev` · **Commit:** `0958f78`.
**Suite:** 2131 en verde en tres corridas completas seguidas (5 min 17 s – 5 min 42 s).

## Decisión (Cristian, 2026-10-08)

Opción 1 de SAF-01: límite de inactividad propio de la sesión, válido en cualquier estado del equipo (también CICLO, FALLA y EMERGENCIA, donde el standby no actúa).
- **5 minutos** sin actividad.
- **Solo cuenta la actividad de esta pantalla** (toques y teclas en esta ventana); la otra puerta no la mantiene viva.
- **Al vencer:** logout (`/auth/logout`) y, si estaba en OPCIONES, Nuevo usuario, Cambio de clave o el Login, vuelta a la pantalla principal según estado. El siguiente login muestra "Sesión cerrada por inactividad; inicie sesión de nuevo" (`sesion.sesion_expirada`, texto aprobado por Cristian el 2026-10-08).

## Implementación

| Pieza | Cambio |
|---|---|
| `ui_qml/sesion_backend.py` | `SESION_INACTIVIDAD_S = 300`; `SesionVentana` filtra toques y teclas de la ventana (`eventFilter`, nunca consume el evento), mide con `time.monotonic()` y un `QTimer` que solo corre con sesión abierta; al vencer cierra con logout y emite `cierrePorInactividad`. El login reinicia el conteo. |
| `ui_qml/app.py` | `ventana.installEventFilter(sesion)` |
| `Main.qml` | `onCierrePorInactividad` → pantalla principal |
| `es.json` | `sesion.sesion_expirada` |

## Fallo fatal intermitente de la suite: causa y corrección

Al probar SAF-01 apareció de forma reproducible el aborto que antes salía de vez en cuando ("Fatal Python error" en una prueba del backend sin relación). Dos causas:

1. **Hilos de trabajo que retenían objetos Qt** (`sesion_backend.py`): las tareas del hilo capturaban `self`; si el hilo soltaba la última referencia, Python destruía el `QObject` (con sus `QTimer`) fuera del hilo de la GUI. Ahora las tareas reciben solo datos simples (`_peticion`), el resultado vuelve por una cola de Python que el hilo de la GUI vacía con un `QTimer` (el hilo nunca toca Qt), y el aviso diferido de 401 lleva el objeto como contexto (`QTimer.singleShot(0, self, ...)`) para que Qt lo cancele si se destruye antes.
2. **Recolección de basura en hilos ajenos** (pruebas): los objetos Qt que las pruebas de UI dejan en ciclos de referencias se recolectaban en el hilo que reservara memoria en ese momento, p. ej. el de AnyIO del `TestClient` de una prueba del backend. Nuevo `tests/conftest.py`: recolecta en el hilo principal tras cada prueba de los módulos que importan PySide6 (recolectar tras todas triplicaba la duración). La bisección mostró que no hay un archivo culpable: dependía de cuánta basura se acumulaba.

En producción el riesgo es bajo: la UI crea sus objetos Qt una vez al arrancar y los conserva, y los controladores de QML son de propiedad del motor QML.

## Pruebas nuevas

- `test_sesion_backend.py`: 5 min exactos cierran con logout y dejan el aviso; un toque reinicia el conteo y un repintado no; el login reinicia el conteo.
- `test_navegacion_sesion_qml.py`: con plazo reducido, OPCIONES → pantalla principal con logout.

## Verificación visual sugerida

Con el simulador: iniciar sesión, entrar a OPCIONES, no tocar la pantalla 5 minutos → vuelve a preciclo; al abrir el login aparece el aviso de inactividad. Tocar la pantalla dentro de esos 5 minutos reinicia el conteo.
