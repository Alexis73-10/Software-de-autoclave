# C1 — Correcciones de la tanda 5

## C1a. Reingreso táctil en PySide (P3-1) ★
- **Módulo nuevo:** `ui_pyside/views/_teclado_pantalla.py`, con estilo de qfluentwidgets.
  - Teclado alfanumérico: mayúsculas, capa ?123 y la ñ.
  - Teclado numérico: 7-8-9 arriba, signo, punto y validación del rango en vivo.
  - `DialogoCredenciales`, `pedir_texto`, `pedir_numero`, `conectar_teclado` y `conectar_todos`.
- **Reutiliza la lógica** de `ui_qml/domain/teclado_alfanumerico.py` y `teclado_numerico.py`, la misma de los teclados QML.
- **Tamaño de tecla:** 96 × 88, radio 12 y separación 14, como en `Tema/Teclado.qml` (TEC-D11). Se escala por el ancho de la pantalla, con 1200 px de referencia.
- **Dónde se usa:**
  - `renovacion_sesion.pedir_credenciales_dialogo` ya no usa `QInputDialog`.
  - Todos los QLineEdit y spinboxes de login, los dos diálogos de correo, secado, parámetros del ciclo y calibración por sensor abren el teclado al tocarlos.
- **Textos nuevos (es/en):** `sesion.vencida_titulo` y `sesion.vencida_mensaje`.
- **Pruebas:** `tests/test_c1a_teclado_pyside.py` (19).

**Revisión (safety-reviewer):** sin Críticos ni Altos.
- **SAF-01 (Medio, defecto anterior a C1a):** cuando la renovación cerraba la sesión por un 401, el reingreso ya no se limitaba al mismo usuario. **Corregido:** se recuerda el usuario caducado (`usuario_para_reingreso`) y la regla OTRO_USUARIO se sigue aplicando.
- **SAF-02 (Medio):** el usuario previo se podía editar en el diálogo. **Corregido:** el campo queda fijo.
- **SAF-03 (Bajo):** en el teclado numérico, lo tecleado se añadía al valor inicial (con "1" en pantalla, teclear 2 daba 12). **Corregido:** la primera tecla reemplaza el valor inicial.
- **SAF-04 (Bajo):** el teclado podía abrirse dos veces con un toque y el clic de ratón que genera. **Corregido:** el teclado no se vuelve a abrir mientras está abierto.
- **SAF-05 (Bajo):** con la contraseña vacía, Confirmar no avisa de nada, y en login hay que pulsar además Entrar. **PENDIENTE.**

## C1b. Admin en solo lectura en Parámetros del equipo (decisión 1.5)
- En `permisos_opciones.py` el admin ve `parametros_sistema`, y `edicion_permitida` le devuelve False en esa sección en cualquier estado.
- `motivo_solo_lectura` devuelve "rol" o "estado". El aviso muestra `opciones.solo_lectura_rol` (es/en).
- `seccion_inicial`: el admin sigue entrando por Usuarios.
- El backend ya devolvía 403 al admin en `PUT /printer/config` y en `PUT /units`. Las pruebas lo fijan.
- **Pruebas:** `tests/test_c1b_admin_parametros_equipo.py`. Se actualizaron `test_permisos_opciones`, `test_opciones_qml` y `test_opciones_controller`.

## C1c. Clase explícita de parámetro en U1 ★
- Se agregó `"clase"` a las 340 hojas de °C, °C/min, kPa y kPa/min de `cycles/factory`, `cycles/user` y `config/global_params.json`. `cycles/defecto` no existe en el repositorio; la prueba lo recorre si aparece.
  - La inserción fue textual y conserva el formato.
  - Las clases son las mismas que deducían los prefijos, así que la conversión no cambia.
- **`unidades.clase_de_unidad(unidad, nombre, clase)`** usa la clase.
  - Sin clase, aplica la migración por prefijo y registra una advertencia en el log.
  - Con una clase desconocida, no convierte y avisa una sola vez.
- El backend devuelve `clase` en `/programas/{n}/seccion/{s}`. El bridge `Unidades` y `OpcionesParametrosCiclo.qml` la pasan.
- **`rango_calentamiento` = "sin_conversion".** `calentamiento.py` lo usa a la vez como banda de temperatura (`t_obj - temp`) y de presión (`p_obj - pres`), así que no es una diferencia de una sola magnitud. Sigue abierta la pregunta de la tanda 5: separarlo en dos parámetros.
- "El catálogo" (`catalogo_parametros.py`) no tiene hojas propias. Una prueba exige que sus entradas absolutas tengan clase "absoluto" en los JSON.
- **Pruebas:** `tests/test_c1c_clase_parametros.py`. Falla si alguna hoja de presión o temperatura no tiene `clase`.

**Revisión (safety-reviewer):** sin Críticos, Altos ni Medios. Agregar `clase` no afecta la carga, la validación, el guardado ni el control.
- **Bajo 1:** el aviso por clase desconocida se repetía. **Corregido:** se deduplica.
- **Bajo 2:** la unidad "kPa" de `rango_calentamiento` es engañosa. Es un problema anterior; queda pendiente.
- **Bajo 3:** una clase válida pero equivocada en un JSON editado a mano no se detecta al cargar. Queda pendiente.

## C1d. Chaqueta absoluta (decisión 1.2)
- `presion_chaqueta` y `presion_chaqueta_secado` tienen clase "absoluto" en los 8 programas.
- En psig: psig = (P_abs − P_atm) / 6,894757. La lectura viva de chaqueta se formatea con `Unidades.pres`, que es absoluta.
- En `docs/informes/tanda5/U1_unidades.md`, la pregunta 1 queda marcada como resuelta.
- **Pruebas:** `tests/test_c1d_chaqueta_absoluta.py`.

## Decisiones
C1-1 a C1-8 en `DECISIONES_PARA_REVISAR.md`. Todas son DECISIÓN SIN CONFIRMAR.

## Riesgo (para el fichero de `docs/riesgos/`, que mantiene D1)
- **HAZ-UNI-02:** una clase de parámetro equivocada haría que el valor se muestre o se teclee con o sin desplazamiento, y en psi o °F la cifra sería engañosa.
  - Control: `clase` explícita en cada hoja y prueba de cobertura y coherencia con el catálogo. Sin clase, se usa la migración con advertencia.
  - Verificación: `test_c1c_*`, `test_c1d_*`.
- **HAZ-UI-03:** sin teclado físico no se puede reingresar ni cambiar parámetros en PySide; antes, un `QInputDialog` dejaba el guardado sin hacer. Además, un reingreso con otro usuario atribuiría el cambio a otra persona.
  - Control: teclado en pantalla, usuario previo fijo y regla OTRO_USUARIO también tras una caducidad por renovación.
  - Verificación: `test_c1a_*`.
- **HAZ-PERM-02:** el admin podría modificar Parámetros del equipo.
  - Control: solo lectura en la UI y 403 en el backend.
  - Verificación: `test_c1b_*`.

## Preguntas para Cristian
- ¿Se reescriben con `clase` los programas duplicados antes de C1c, o basta con la migración con advertencia?
- ¿El transductor de empaque mide en absoluto? Hoy `vacio_empaque` y `presion_empaque` están como "absoluto".
