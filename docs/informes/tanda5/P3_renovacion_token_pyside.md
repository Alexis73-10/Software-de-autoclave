# P3 — Renovación del token en PySide ★ (safety-reviewer)

- `ui_pyside/services/renovacion_sesion.py`:
  - `RenovadorSesion` (reloj inyectable) avisa con `GET /auth/sesion` como máximo cada 30 s, siempre que haya habido actividad en los últimos 5 min. Usa las mismas constantes que B7 (`core/runtime/sesion_inactividad.py`).
  - Si el backend responde 401, cierra la sesión local. Si no responde, no hace nada.
  - `instalar_en()` lo engancha a la ventana PySide con un filtro de clics, teclas y toques y un QTimer de 5 s.
- `guardar_con_reintento()`: ante un 401 pide login y reintenta una sola vez el mismo guardado. Si se cancela o el login falla, no se guarda y se muestra el motivo. Se aplica en calibración por sensor, parámetros del ciclo y secado.
- Las acciones de seguridad no usan token (ver R0).

**DECISIÓN SIN CONFIRMAR P3-1:** el diálogo de login es un `QInputDialog` (usuario y contraseña) y no el teclado en pantalla, porque la UI PySide no tiene un teclado reutilizable fuera de su LoginView. En una pantalla táctil sin teclado físico hace falta el teclado de Windows. Para revertir: reemplazar `pedir_credenciales_dialogo`.

## Revisión (safety-reviewer)
Sin Críticos ni Altos. El backend audita con el usuario del token (no con el campo `usuario` del cuerpo), y el 401 sale de `requiere_rol` antes de escribir, así que el reintento no duplica nada.
- Medio SAF-01: el diálogo admitía a otro usuario y la ventana cambiaba de persona sin aviso. **Corregido:** si había sesión al empezar, solo el mismo usuario puede reingresar (`OTRO_USUARIO`). Si no, el cambio no se guarda y se dice el motivo.
- Medio SAF-02: la etiqueta "Última modificación" de calibración usaba el nombre calculado antes del login. **Corregido:** se lee de la sesión después de guardar.
- Bajo SAF-03 (secado guardado a medias si se cancela el login a mitad del recorrido): **PENDIENTE**. El mensaje dice "NO se guardó" aunque algunos campos sí se guardaron.
- Bajo SAF-04 (al caducar en la renovación, el encabezado sigue mostrando al usuario): **PENDIENTE**.
- Bajo SAF-05 (la consulta de renovación corre en el hilo de la UI, hasta 2 s cada 30 s si el backend no responde): **PENDIENTE**.

Pruebas:
- `tests/test_p3_renovacion_pyside.py`: renovación en uso, inactividad mayor al plazo, sin sesión, 401 en la renovación, backend caído, 401 con reintento exitoso que conserva lo editado, 401 cancelado, login fallido y otros errores.
- `test_401_pide_login_y_cancelado_no_guarda` en `test_b1_secado_pyside.py`.
- `tests/conftest.py` cancela el diálogo en todas las pruebas, para que un 401 no deje la suite bloqueada en un diálogo modal.
