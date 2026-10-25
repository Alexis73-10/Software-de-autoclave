# tests/

Pruebas automáticas del software del autoclave (`pytest tests -n auto`).

| Ruta | Qué va ahí |
|---|---|
| `test_*.py` | Pruebas automáticas. Convención para las nuevas: `test_<modulo>_<aspecto>.py`. |
| `conftest.py` | Configuración común de pytest (secretos de prueba de la licencia, etc.). |
| `helpers/` | Dobles y ayudantes que importan las pruebas: `backend_doble` (carga `autoclave.backend.server` con un contexto falso; `modulo_backend`, `fijar_en_backend`, `parchear_en_backend`, `parche_en_backend` y `fuente_backend` para el backend partido en `backend/rutas/`), `serial_doble`, `smtp_falso`, `alarmas_helpers`, `opciones_qml_doble`, `t12_e12_apoyo`, `textos_caben_qml`. Se importan como `from tests.helpers.<x> import ...`. |
| `banco/` | Bancos y guiones de capturas (`*_banco.py`, `*_capturas.py`) que no son pruebas automáticas; algunos los usan pruebas QML como arnés (`from tests.banco.<x> import ...`). Los guiones se lanzan a mano desde la raíz. |
| `js/` | Pruebas de JavaScript de la interfaz. |

Trazabilidad (IEC 62304 7.3.3): las pruebas nuevas que verifican un requisito llevan el marcador `req` con su identificador, por ejemplo `@pytest.mark.req("CIC-14")`. El marcador está registrado en `pyproject.toml`.

Reglas de cambio: una prueba no se borra, salta ni relaja para que una reorganización quede en verde; si cambia un import o el destino de un parche, se anota en el informe de la tanda.
