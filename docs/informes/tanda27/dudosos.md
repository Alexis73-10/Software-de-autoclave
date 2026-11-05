# Tanda 27: elementos DUDOSOS para aprobación de Cristian

Fecha: 5-nov-2026. Rama `tanda27`. Fuente: los 4 inventarios de esta carpeta (`inventario_esp32.md`, `inventario_python.md`, `inventario_qml_rutas_i18n.md`, `inventario_tools_pyside.md`). Nada de esto se borra hasta que Cristian lo apruebe. Criterios de borrado: a) sin referencia desde un punto de entrada vivo; b) fuera de `.spec`/Setup/estación; c) nombre no aparece como cadena en código vivo, QML, JSON o YAML; d) ningún proceso vigente lo nombra; e) sin prueba con `req(id)` ni cita en trazabilidad/riesgos. Ante la duda: DUDOSO (el 1-dic se entrega un equipo funcional).

## Resumen de decisiones pedidas a Cristian

| Decisión | DEP | Propuesta |
|---|---|---|
| ¿Retirar `ui_pyside`? Faltan «Imprimir alarmas activas» y «Tiempo de secado» del ciclo activo en QML | 01, 02 | **No retirar en esta tanda.** Decidir si esas dos funciones se portan a QML o se descartan |
| Confirmar borrar `ResumenPeriodo.qml` (la tanda 25 lo dejó «conservado») y la clave `io.ui.atrapamiento_aviso` (la A4 trabaja el seguro de atrapamiento) | nota 1 | Confirmar los dos antes del borrado |
| Código de puertas, paro, alarmas y licencia sin llamador (zona protegida) | 05-08, 13 | Conservar; revisar con `auditor-iec62304` si se quiere borrar |
| Módulos `ui_qml/domain` del plan de alarmas B/C y WebSocket F3 | 03 | Conservar (plan pausado) o borrar con sus 3 pruebas |
| Rutas `/alarms/history`, `/db/estado`, `/io/test/force-exit` | 16-18 | Conservar las tres |
| Herramientas de campo (`declarar_*`, Tuttnauer, `registro_pruebas`, `demos_qml`, `generar_assets_arranque`) | 21-25 | Conservar |
| Documentos obsoletos (~100 archivos) y marcas en riesgos/trazabilidad | 28-30 | Aprobar mover a `docs/referencia/obsoleto/` con cabecera; aprobar texto «Obsoleto (tanda 20, retirado en la 27)» |

Nota 1: BORRABLES que piden confirmación expresa aunque cumplen a–e: `Componentes/ResumenPeriodo.qml` (decisión de conservarlo en `docs/informes/dashboard_reportes/R_informe.md:63,78`) y `io.ui.atrapamiento_aviso`.

---

## A. ui_pyside y dependencias

### DEP-01 (Media): `ui_pyside` no se retira todavía
- **Elemento:** `src/autoclave/ui_pyside/` (25 módulos, 4 547 líneas; `AutoclaveSettings.exe`). Nadie la abre desde la UI (`LanzadorAjustes.abrir()` sin llamadores; solo `Autoclave.exe --rol ajustes`), pero no hay equivalencia completa.
- **Motivo:** faltan equivalentes en QML (falla a/d/e de un borrado funcional): (1) «Imprimir alarmas activas» (ticket térmico, `impresion_menu.py::_build_alarms_ticket_lines`; en `ui_qml` no hay nada); (2) «Tiempo de secado» del ciclo activo (`secado.py`; la tarjeta se retiró en U5, `MenuPrincipal.qml:229`). Además parámetros del ciclo, E/S y calibración de sensor tienen equivalente solo «por nombre y controlador», sin comparación función por función.
- **Requisito afectado:** MES-04 (`test_t23_mes04_codigo_visible_ui.py`), reimpresión NO CONFORME (`test_t16_r_correcciones.py`); `docs/riesgos/lista_soup.md:27` y `registro_riesgos.md:306`.
- **Consecuencias (se quedan):** dependencia `PySide6-Fluent-Widgets[full]` y sus exclusivas (`PySideSix-Frameless-Window`, `darkdetect`, `colorthief`, `scipy` y su exención en `Autoclave.spec:115-118`/`test_b2_spec_excludes.py`); `packaging/AutoclaveSettings.spec` y su entrada en `compilar_entrega.SPECS`; el rol `ajustes` de `exe_unico.py`; `LanzadorAjustes`; `NuevoUsuarioBridge` importado desde `ui_qml/app.py:30` (código de producción ubicado en `ui_pyside/views/nuevo_usuario/puente.py`); el `taskkill` de `autoclave.iss:1951`; `numpy` (usado por `tools/generar_assets_arranque.py`, no declarado en `pyproject`).
- **Acción propuesta:** no retirar. En una tanda posterior: decidir las 2 funciones faltantes, comparar parámetros/E/S/calibración, mover `puente.py` a `ui_qml/bridge/nuevo_usuario.py` (reapuntar `app.py`, `test_i18n.py:38-39`, `tools/claves_sin_uso_i18n.py:31-32`, helpers y banco), y retirar en el orden del inventario con la suite verde en cada paso.

### DEP-02 (Media): pruebas con `req` que dependen de `ui_pyside`
- **Elemento:** `tests/test_t16_r_correcciones.py:184` (`test_reimpresion_pyside_lleva_no_conforme`) y `tests/test_t23_mes04_codigo_visible_ui.py:67` (`test_ticket_de_alarmas_activas_con_codigo_visible`); `test_nuevo_usuario_qml.py:32` usa `NuevoUsuarioView`. Otras ~16 pruebas solo-PySide (sin `req`).
- **Motivo:** criterio e (`req`); su requisito también se cumple en QML/`ticket_formatter`, pero habría que reasignar la prueba.
- **Acción:** conservar mientras exista `ui_pyside`; al retirarla, reasignar a la ruta equivalente en vez de borrar.

### DEP-03 (Baja): módulos de dominio QML sin importador de producto
- **Elemento:** `ui_qml/domain/alarmas.py`, `reconexion.py`, `telemetria.py` (solo `test_alarmas_domain.py`, `test_reconexion.py`, `test_telemetria_validacion.py`, sin `req`).
- **Motivo:** falla d: `planeacion_ui_dual_pantalla.md` (F3, F8) y `analisis_sistema_alarmas.md` los citan como base de las partes B/C de alarmas (pausadas); `D2_depuracion` (tanda 7) recomendó conservarlos.
- **Requisito:** plan de alarmas B/C, WebSocket F3.
- **Acción:** conservar; si Cristian cancela esos planes, borrar los 3 módulos y las 3 pruebas.

---

## B. Python (`src/autoclave`)

### DEP-04 (Baja): `ui_qml/historial_ejemplo.py`
- Lo usan `tests/helpers/reportes_ejemplo.py`, `textos_caben_qml.py`, `test_v8b_textos.py`, `tests/banco/rep_capturas_reportes.py`, `tools/demos_qml/prueba_menu_principal.py`. Falla c y d (apoyo de pruebas y capturas). Sin `req`. Acción: conservar (o moverlo a `tests/helpers/` en otra tanda).

### DEP-05 (Media): 16 métodos de puerta en `devices/io/set_io.py` (230–332)
- `abrir/cerrar/bloqueo/desbloqueo_puerta_{1,2}_on/_off`: 0 referencias, pero es código de puertas (interlock). Falla: zona protegida (no se pudo comprobar que no haya uso por `getattr` ni evaluar el impacto IEC 62304). Requisito: seguridad de puertas. Acción: conservar; solo borrar tras `auditor-iec62304` y revisión.

### DEP-06 (Media): `can_open` / `can_close` en `services/domain/puertas/ser_puertas.py`
- 0 referencias; `D8_depuracion` (tanda 8) y `D2_depuracion` (tanda 7) los conservan (barrera de permisos por rol pendiente; ver memoria «backend ignora source_door»). Falla d. Acción: conservar.

### DEP-07 (Media): `state_machine/machine/parametros_globales.py`
- Constantes (`PRESION_ATMOSFERICA`, `RANGO_PRES_ATMOSFERICA`, `TEMP_DRENAJE`, `MARGEN_MINIMO_ENTRADA_ESTERILIZACION`) que nadie lee; `ser_puertas.py:33` y `preparacion.py:2` importan la clase sin usarla. El handoff 2026-07-22 documenta `MARGEN_MINIMO...`. Zona state_machine; no se pudo comprobar que los valores vivan ya en otro sitio. Acción: conservar el módulo; el import sin uso de `preparacion.py:2` se puede limpiar (BORRABLE de una línea) tras comprobarlo a mano.

### DEP-08 (Baja): `base_fase._temp_camara_2` (89) y `modbus_link.REG_NEGOCIACION` (126)
- 0 referencias. `_temp_camara_2`: CLAUDE.md lo deja «pendiente» (sensor de líquido secundario). `REG_NEGOCIACION`: mapa de registros del módulo E/S. Acción: conservar.

### DEP-09 (Media): `paro_emergencia` (`rising_edge`, `falling_edge`, `AVISO_CABLEADO_NC`) y `alarm_manager` (`has_emergency`, `has_active_alarms`)
- Solo pruebas. Paro y alarmas: zona de seguridad; `D2_depuracion` conserva los de alarmas. Acción: conservar.

### DEP-10 (Baja): símbolos solo probados, con `req`
- `hal/measures/converters.py` (`presion_en_falla`, `reiniciar_presiones`: `test_t19_s2_conversion`, `test_t23_ain_*`), `core/runtime/asignacion_io.py` (`canal_crudo`, `restablecer_memoria_fabrica_codigo`, `limpiar_pendiente`), `catalogo_parametros.errores_recuperacion` (`test_t16_s4_programas.py`), `_version.semver_a_pep440`/`pep440_a_semver` (`test_ver_version.py`). Falla e. Acción: conservar.

### DEP-11 (Baja): bloque de ~90 símbolos solo usados por pruebas
- Lista en `inventario_python.md` §3 (p. ej. `build_hardware`, `programas_del_respaldo`, `ESQUEMA_VERSION`, `CODIGOS_CONSERVADOS`, propiedades de controladores QML, `TIPOS_HISTORICOS`). Sin llamador de producto, pero borrarlos obliga a editar pruebas; riesgo/beneficio desfavorable. Acción: conservar; borrar uno a uno con su prueba solo si Cristian lo pide.

### DEP-12 (Media): licencia y activación
- `installation/activation.py` (`configurar_secretos`, `huella_instalacion`, `validate_factory_key`) y `installation/secretos.py` (`entrada_compilacion*`, VIVO por los `.spec`). `validate_factory_key` solo en `tests/test_activation.py`. Zona de licencia/activación (AUT-R1..R8, LIC-01). Acción: conservar.

### DEP-13 (Baja): `installation/cambio_perfil.py`
- Sin importador en `src`, pero lo usan 3 `tools/` (`declarar_*`, `emparejar_modulo_es.py`), 2 pruebas; CLAUDE.md cita `CAMPOS_DE_IDENTIDAD`; riesgos AUT. Falla d y e. Vivo vía herramientas. Acción: conservar.

---

## C. QML

### DEP-14 (Baja): `qml/Pruebas/` (10 archivos)
- `GaleriaMenuPrincipal`, `PruebaCicloEnCurso`, `PruebaCicloEnCursoBackend`, `PruebaFinDeCiclo`, `PruebaInstalacion`, `PruebaMenuPrincipal`, `PruebaMovimiento`, `PruebaReportes`, `PruebaTecladoAlfanumerico`, `PruebaTecladoNumerico`. Son arneses de pruebas y banco (falla c y d: CLAUDE.md nombra `PruebaCicloEnCurso`/`PruebaFinDeCiclo`). `PruebaCicloEnCursoBackend` y `PruebaInstalacion` solo los abren demos manuales (`tools/demos_qml/`). El `.spec` empaqueta la carpeta QML entera (se distribuyen). Acción: conservar; ver DEP-21 para las demos.

### DEP-15 (Baja): `ReporteResumen` y `Main.reporte`
- `ui_qml/bridge/reporte_resumen.py` se crea en `app.py:307` y se inyecta en `Main.qml:49`, pero ningún QML lo lee. Lo prueban `test_reporte_resumen_puente.py` y `test_v8a_reportes_fallos_puente.py` (sin `req`); la tanda 25 lo deja «para una etapa posterior». Acción: conservar; retirar en una etapa posterior con sus pruebas.

### DEP-16 (Baja): propiedades/señales QML sin lector (15)
- Lista en `inventario_qml_rutas_i18n.md` §1.2 (`animando`, `anchoContenido`, `versionAlAbrir`, `iniciarCiclo`, colores de `Colores.qml`…). Varias las leen pruebas (`desborda`: 17 usos; `test_tema_oscuro.py` exige los claros iguales a `dev`). Criterio conservador del guion. Acción: conservar; ninguna se borra sin revisión manual.

---

## D. Rutas del backend

### DEP-17 (Baja): `GET /alarms/history`
- 0 llamadores; `tests/test_alarms_endpoints.py:42,52` (sin `req`); prevista para la pantalla de historial de alarmas de las partes B/C (`docs/superpowers/plans/2026-10-07-sistema-alarmas-parte-a.md`). Falla d (aprox.). Borrarla exige regenerar `docs/informes/tanda15/base/`. Acción: conservar.

### DEP-18 (Baja): `GET /db/estado`
- 0 llamadores; `test_endpoint_arranque.py:126-128`, `test_b7_caducidad_tokens.py:155`; diseño en `planeacion_arranque_y_modo_sin_bd.md`; diagnóstico útil con curl en el banco. Acción: conservar.

### DEP-19 (Media): `POST /io/test/force-exit`
- 0 llamadores en código, pero la nombra la hoja de pruebas de banco (`hoja_pruebas_banco_equipo_pruebas.md:966`, `pruebas.py:287`): falla d. Función de seguridad del modo prueba (ESG-02); pruebas `test_b8_salida_forzada_modo_prueba.py`, `test_q1_r1p1_ack_salida_prueba.py`, `test_revision_tanda4.py`. Acción: conservar.

---

## E. i18n

### DEP-20 (Baja): `ciclo.rol_sonda_no_activa`
- Sin uso en código, pero `tests/test_t16_s4_programas.py:570-573` exige que exista (`req("T16-S4")`; PRG-01). Falla e. Acción: conservar.

### DEP-21 (Baja): `ticket_ciclo.aviso_uniformidad`
- Ya no se produce (C-13.5), pero ciclos guardados antes de la tanda 12 pueden traerla y la reimpresión la traduce (`test_x9_d9_13_4_ticket_motivos_idioma.py`). Falla c (dato persistido). Acción: conservar.

### DEP-22 (Baja): claves `alarmas.TARJETA_*` de alarmas ya no emitidas
- `TARJETA_SIN_ACK`, `TARJETA_ALL_OFF_SIN_CONFIRMAR`, `TARJETA_REINICIO` (y `TARJETA_SIN_TRAMA_VALIDA`): catálogo conservado por el historial (CLAUDE.md, MOD-12). Falla c. Acción: conservar; ver DEP-31 para `ALARMAS_HANDSHAKE`.

---

## F. tools

### DEP-23 (Baja): `tools/demos_qml/` (4 `prueba_*.py`)
- Nadie los importa ni los ejecuta una prueba; son el único lanzador de `qml/Pruebas/*` y de `historial_ejemplo.py`. Sus cabeceras QML citan una ruta vieja. Acción: conservar; si se borran, borrar también los QML de `Pruebas/` que solo ellos abren (DEP-14) y DEP-04.

### DEP-24 (Baja): `tools/generar_assets_arranque.py`
- Regenera `halo_arranque.png`/`voluta_vapor.png` de `IntroArranque.qml:16`; usa numpy (no declarado). Acción: conservar o documentar en `docs/`.

### DEP-25 (Baja): `declarar_entradas_suministro.py`, `declarar_sondas_temperatura.py`
- Pruebas `test_declarar_entradas_suministro.py`, `test_adenda_herramientas_perfil.py`; procedimiento de campo (declarar hardware); escriben su nombre como `herramienta` en el registro del perfil. Falla d. Acción: conservar.

### DEP-26 (Baja): `asignar_programas_tuttnauer.py`, `importar_ciclo_tuttnauer.py`
- Último commit 2-nov (3 días), `test_importar_tuttnauer_programas.py`, HISTORIAL (programa Textiles). Reciente y de datos de otro equipo. Acción: conservar.

### DEP-27 (Media): `tools/registro_pruebas/`
- App web de registro del banco; `test_f1_registro_pruebas.py`, `tests/js/cola.test.js`; lee `docs/mis_plans/hoja_pruebas_banco/pruebas.py`. En uso por Cristian en el banco. Acción: NO borrar sin decisión expresa.

---

## G. ESP32 / enlace serial (rastros)

### DEP-28 (Media): documentos a mover a `docs/referencia/obsoleto/` (~100 archivos, clase E)
- `docs/plan_modificaciones_adc_ino.md`, `docs/instalacion/LEEME_INSTALACION.md` (compilación I), 35 de `docs/mis_plans/` (solo contados), 11 de `docs/superpowers/` (los dos de reconexión de tarjeta), 47 de `docs/informes/` no-tanda (`informe_e6_firmware.md`, `lotes_auditoria`…), `inventario_cadenas_i18n.{md,csv}`. No se pudo comprobar uno por uno cuáles siguen vigentes por ubicación. Afecta `docs/README.md:18`. Acción: aprobar mover los claramente históricos con cabecera «Obsoleto»; `docs/informes/` y `mis_plans/` quedan como excepción de la prueba `test_t27_sin_esp32.py`.

### DEP-29 (Media): marcas en riesgos y trazabilidad (clase F)
- `registro_riesgos.md:77, 167-169, 175, 177, 193` (HAZ-TAR-01, HAZ-T2-03, AN-31), `matriz_trazabilidad.md:16` (REQ-10), `lista_soup.md:18, 68`. Documentos regulatorios (IEC 62304): no se editan sin aprobación. Acción: marcar «Obsoleto (tanda 20, retirado en la 27)»; conservar SOUP y la nota de retiro. `HAZ-T2-03` además alimenta el comentario de `ciclo.py:70` (tolerancia 4 s de DI vencida): reescribir con MOD-08, sin cambiar el valor.

### DEP-30 (Baja): `ALARMAS_SOLO_SERIAL` (`protocols/enlace.py:54-59`) y `ALARMAS_HANDSHAKE`
- `ALARMAS_SOLO_SERIAL` sin uso en `src` (solo `test_t20_s2_retiro_serial.py:196-201`); se conserva por el historial (clase C). `ALARMAS_HANDSHAKE` incluye alarmas que ya no se emiten. Los códigos no se tocan. Acción: renombrar a `ALARMAS_SOLO_HISTORIAL` y adaptar la prueba; marcar el comentario de `ALARMAS_HANDSHAKE`; no borrar.

### DEP-31 (Baja): literal vivo `backend/rutas/respaldo.py:222`
- `Path(tmp)/"calibration.yaml"`: nombre temporal para validar; el rechazo `calibracion_otro_enlace` es vigente. No se comprobó si el nombre puede cambiar sin afectar la lectura de respaldos de equipos serial. Acción: dejar el literal; reescribir solo los comentarios (líneas 64, 229).

### DEP-32 (Baja): excepciones de `tests/test_t27_sin_esp32.py`
- Tolerar: `tests/test_t20_s2_retiro_serial.py`, la propia prueba, `docs/informes/`, `docs/mis_plans/`, `docs/superpowers/`, `docs/referencia/obsoleto/`, `docs/versiones/*`, registro de riesgos/matriz/SOUP, la nota de retiro de `docs/catalogo_alarmas.md`, `src/logs/`. El `'serial'` de `excludes` de los `.spec` no coincide con el patrón. Acción: aprobar la lista; `tools/ensayo_actualizacion_*.py` (BORRABLES) arrastran el bloque `calibration.yaml`: si no se borran, reescribir.
