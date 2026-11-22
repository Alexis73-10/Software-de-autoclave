# Revisión visual (RV): inventario de pantallas y escenarios

Etapa B, 19-nov. Fuente: `src/autoclave/ui_qml/qml/Pantallas/` (26 archivos), los componentes de `Componentes/` que se muestran como modal, panel o diálogo, y los escenarios de `tests/banco/hor_escenarios_a..f.py` más los base de `tests/banco/hor_capturas.py` (137 escenarios en total; `python tests/banco/hor_capturas.py --listar --plataforma offscreen` los imprime).

## Pantallas y escenarios que las cubren

- IntroArranque: `intro`, `intro_final`, `barra_reinicio`.
- Reposo: `reposo`, `reposo_aviso`.
- Login: `login`, `login_teclado`, `login_teclado_num`, `login_teclado_clave`, `login_sin_bd`.
- CambioClave: `cambio_clave`, `cambio_clave_teclado`, `e_cambio_clave_teclado`.
- NuevoUsuario: `nuevo_usuario`, `nuevo_usuario_roles`, `nuevo_usuario_teclado`, `e_nuevo_usuario_teclado`.
- Instalacion (asistente): `instalacion`, `inst_activacion_auto`, `inst_equipo`, `inst_puertas`, `inst_puertas_una`, `inst_camara`, `inst_enfriamiento`, `inst_vapor`, `inst_datos`, `inst_contrasenas`, `inst_resumen`, `inst_resumen_auto`, `inst_listo`, `inst_teclado_codigo`, `inst_teclado_clave`.
- MenuPrincipal y sus ventanas flotantes: `menu`, `menu_ultimo_ciclo`, `menu_mantenimiento`, `menu_ciclos_hoy`, `menu_historial`, `menu_historial_ciclo`, `menu_ciclos_hoy_ciclo`, `menu_historial_destino`.
- PantallaPreciclo: `preciclo_preparado`, `preciclo_alarma`, `b_preciclo_puerta2`, `b_preciclo_puerta2_manual`, `b_preciclo_modo_prueba`, `b_preciclo_falla`, `b_preciclo_sin_conexion`, `b_preciclo_muchas_alarmas`, `b_preciclo_programa_largo`, `b_preciclo_selector`.
- PantallaCicloEnCurso: `ciclo_grafica`, `ciclo_completo`, `fin_fallido`, `ciclo_demo`, `b_ciclo_pantalla_completa`, `b_ciclo_tiempos`, `b_ciclo_zoom_lupa`, `b_ciclo_sin_conexion`, `b_fin_fallido_grafica`, `b_fin_observaciones_pildora`, `b_fin_observaciones_panel`, `b_fin_estado_seguro_modal`, `b_ciclo_espera_entrega`, `b_ciclo_espera_entrega_ingeniero`.
- Reportes: `reportes`, `reportes_abajo`, `reportes_dia`, `reportes_panel`, `reportes_medio`, `reportes_selector`, `reportes_anio`, `reportes_alarmas`, `reportes_correo`, `reportes_ciclo`, `reportes_fallo`.
- Opciones (marco y cajón): `opciones`, `d_cajon`.
- Secciones de Opciones, solas y sin datos (`Opciones<Sección>`, 15 escenarios) y con datos de ejemplo: `d_usuarios`, `d_usuarios_seleccion`, `d_usuarios_operadores`, `d_parametros_ciclo`, `d_parametros_ciclo_fase`, `d_ciclo_sensores`, `d_ciclo_entradas`, `d_ciclo_ajuste`, `d_parametros_equipo`, `d_parametros_equipo_maquina`, `opciones_equipo_maquina`, `d_equipo_chaqueta`, `d_equipo_impresion`, `d_equipo_ajuste`, `d_fecha_hora`, `d_info_sistema`, `d_bitacora`, `d_bitacora_tipo`, `d_mantenimiento`, `d_calibracion_atm`, `d_conectividad`, `d_respaldo`, `d_entradas_salidas`, `d_es_salidas`, `d_es_temperatura`, `d_es_presion`, `d_calibracion_sensor`, `d_avanzadas`, `d_avanzadas_programa`, `d_reasignacion`.
- Teclados en pantalla: `teclado_alfa`, `teclado_num` y los `*_teclado*` de cada pantalla.
- Modales, paneles y diálogos (grupo E): `e_notificaciones` (PanelNotificaciones), `e_detalle_alarma` (VentanaDetalleAlarma), `e_equipo` y `e_equipo_apagar` (PanelEquipo), `e_modal_confirmacion` (ModalConfirmacion), `e_dialogo_confirmacion` (DialogoConfirmacion), `e_modal_operador` (ModalOperador), `e_main_sin_conexion` (Main.qml completo sin backend).

## Escenarios nuevos de esta revisión (grupo F, `tests/banco/hor_escenarios_f.py`)

Cada uno abre el modal con un toque real sobre su botón, con los datos de ejemplo del grupo D:

- `f_bitacora_calendario`: calendario táctil del filtro Desde de la Bitácora.
- `f_usuarios_eliminar`: confirmación de eliminar usuario.
- `f_usuarios_rol`: selector de rol nuevo.
- `f_usuarios_restablecer`: contraseña temporal con el teclado alfanumérico abierto.
- `f_usuarios_desactivar`: confirmación de desactivar usuario.

Se probaron y se descartaron dos: el diálogo de habilitar el modo prueba (el botón está deshabilitado sin enlace con el módulo E/S en el doble) y el de restaurar fábrica en Reasignación (el botón no abre el diálogo con los datos de ejemplo); los dos quedan para la etapa E.

## Estados relevantes y su cobertura

- Sin datos: las 15 secciones `Opciones<Sección>` sin doble de datos, `login_sin_bd`.
- Sin conexión: `b_preciclo_sin_conexion`, `b_ciclo_sin_conexion`, `e_main_sin_conexion`.
- Modo prueba: `b_preciclo_modo_prueba` (deslizador oculto). Entradas/Salidas en modo prueba queda para la etapa E.
- Alarmas activas: `preciclo_alarma`, `b_preciclo_muchas_alarmas`, `b_preciclo_falla`, `e_notificaciones`, `e_detalle_alarma`.
- Teclado abierto: ver «Teclados en pantalla».
- Ciclo en curso: `ciclo_grafica`, `ciclo_demo`, `b_ciclo_*`.
- Fin de ciclo: `ciclo_completo`, `fin_fallido`, `b_fin_*`, `b_ciclo_espera_entrega*`.

## Sin escenario

- El aviso «abrir la puerta de descarga» que CLAUDE.md describe en los ajustes del 9-nov (`sistema.abrir_puerta_descarga`, `UiBridge.vaciadoChaquetaPendiente`) no existe en el QML de `dev` (no aparece en `src/autoclave/ui_qml/qml/`), así que no se pudo capturar. Pasa al informe como pregunta.
- PruebaMovimiento.qml y GaleriaMenuPrincipal.qml son arneses de desarrollo, no pantallas del equipo.

## Combinaciones capturadas

1200x1920 y 1920x1200, temas claro y oscuro, idiomas es y en (8 combinaciones por escenario), en `base/<WxH>_<idioma>/`; además `tests/banco/i4_truncado_banco.py` a 1024 × 1638 en es y en (`base/1024x1638/`).
