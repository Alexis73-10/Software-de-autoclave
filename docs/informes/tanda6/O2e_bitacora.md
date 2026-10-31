# O2e — Bitácora de auditoría (solo lectura)

## Qué se hizo
- **`GET /audit_log`** (admin, técnico e ingeniero; 401 sin token, 403 a otros roles):
  - paginación `pagina` y `por_pagina` (máximo 100), con `total` y `paginas`;
  - filtros `desde` y `hasta` (fechas; `hasta` incluye el día completo), `usuario` y `evento` (tipo);
  - listas `usuarios` y `tipos` para los filtros.
  - Cada fila trae `clave_texto` (`bitacora.ev.<evento>`, o `bitacora.ev_generico` si el evento no tiene texto propio) y los valores anterior y nuevo ya en la unidad vigente.
  - Con los parámetros del equipo, el valor se convierte según la unidad y la clase de `global_params.json`. Por ejemplo, 80 °C se muestra como 176 °F y un rango de 5 °C como 9 °F (diferencia).
- **Nadie edita ni borra.** No hay rutas de escritura (405), y `audit_log` ya es de solo anexar por los triggers de la migración v4.
- **Eventos agregados:**
  - `suspension_entra` y `suspension_sale`: `POST /ui/standby`, que `Standby` llama fuera del hilo de la GUI al cambiar de estado;
  - los de usuarios y operadores, que vienen de O2b.
  - `falla_reconocida` y `param_sistema_cambio` ya existían.
  - `calibracion_atm_ok`, `calibracion_atm_abortada` y `calibracion_atm_rechazada` ya tienen textos para cuando O2f los emita.
  - Fecha y hora no genera eventos, porque la pantalla es de solo lectura (O2c).
  - Una prueba exige que todo evento literal que audita `server.py` tenga texto propio.
- **Sección `bitacora`** para todos los roles con sesión.
  - `OpcionesBitacora.qml` sigue el mockup 9:
    - filtros Desde (teclado, AAAA-MM-DD), Usuario y Tipo (cada toque pasa a la opción siguiente, empezando por "Todos");
    - filas con la fecha y la hora a la izquierda y la frase con el usuario en negrita, con el texto escapado;
    - paginación "‹ Anterior · Página n de m · Siguiente ›".
  - Textos en `bitacora.*`, en es y en.

## Pruebas
Suite completa: 4860 passed / 2 skipped / 3 xfailed (una corrida previa abortó en `test_ciclo_controller.py::test_sondeo_http_backend_caido_queda_sin_conexion`, "Fatal Python error: Aborted" de Qt; ajena a O2e e intermitente: pasa sola 3 de 3 y en la corrida siguiente).

`tests/test_o2e_bitacora.py` (16 pruebas) cubre:
- la matriz de lectura por rol;
- que no haya escritura;
- la paginación y los filtros (con una fecha inválida, 422);
- la conversión de unidades por la API y en el formateo puro;
- la suspensión en el backend y en `Standby`;
- los textos de todos los eventos;
- la visibilidad;
- el controlador;
- la pantalla offscreen, incluido el escape del usuario.

## Captura
`O2e_1_bitacora.png`.

## Limitaciones
- La entidad se muestra con su clave interna; por ejemplo, `temp_max_apertura` y no su nombre traducido.
- Las tablas viejas `cycle_params_audit` y `sensor_calibration_audit` no se unifican en el visor (§3.9 lo pedía). Va como pregunta.
