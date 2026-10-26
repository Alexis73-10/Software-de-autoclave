# R17 — Informe de la tanda 17: hallazgos de la instalación I

Fecha: 26-oct-2026. Rama `tanda-17` desde `dev` (84c146a). Fuente de verdad: `docs/mis_plans/decisiones_tanda_17.md`. Ejecutada sin supervisión.

Documentos de detalle de esta carpeta: `estado.md` (etapas y tabla de propiedad), `V_resumen.md` (V-01 a V-04 con archivo:línea), `P_resumen.md` (lo que hizo cada subagente), `R_hallazgos.md` (hallazgos de R y su resolución), `base_suite.txt` (línea base).

## 1. Etapas

| Etapa | Estado | Nota |
|---|---|---|
| A0 | Hecha | tanda-16 ⊂ dev; árbol limpio; rama `tanda-17`; `424e5d6` documentos; línea base 8234 passed, 4 failed (1 preexistente + 3 solo en paralelo), 8251 recolectadas |
| A1 | Hecha | `fca0102`, `af32dbd` (§2) |
| V | Hecha | 4 subagentes de solo lectura (`V_resumen.md`) |
| F | Hecha | F1 `7324847`, F2 `526a570` (+ `43ed55e`, `632e4b9`), F3 `f101b2e` (+ `cc11380`) |
| P | Hecha | s1 `892a29b`, s2 `10b9427`, s3 `8daaa0b`, s4 `783c968` |
| I | Hecha | merges s3, s1, s2, s4 sin conflictos; integración `32efe11` |
| R | Hecha | 4 revisores; 2 altos (V17-s1-01, V17-s1-03) corregidos; correcciones r1–r4 unidas |
| K | Hecha parcial | unión `584aa7a`; anomalías `a51a120`; **entrega no ejecutada** (el sistema detuvo el script por memoria baja; §8) |
| L | Hecha | §9 |
| Z | Hecha | este informe, CLAUDE.md, hoja de banco (bloque I), índice, push de `tanda-17` |

## 2. A1 — falla preexistente que bloqueó la entrega de la tanda 16

- `tests/test_ver_entrega.py::test_historial_entrada_debajo_de_la_marca` exigía que `docs/versiones/HISTORIAL_VERSIONES.md` no tuviera entradas bajo la marca («§5: sin entradas todavía»), lo que dejó de ser cierto al entregar la 1.0.0-alpha.1. Causa: la prueba dependía del contenido real del historial, no del código. Corrección (`fca0102`, la sugerida en R16 §8): la prueba comprueba que en el archivo real toda entrada está bajo la marca y que su cabecera no tiene entradas, y hace la inserción sobre esa cabecera sin entradas. Ni el historial ni `compilar_entrega.py` cambiaron.
- La línea base mostró una segunda falla en `dev` que también fallaba en serie: `tests/test_f1_registro_pruebas.py` exigía los bloques A–G de la hoja de banco y el cierre Z de la tanda 16 agregó el H. Corregida en `af32dbd` (sigue exigiendo el conjunto exacto; en Z pasa a A–I con el bloque nuevo).
- Las pruebas que fallan solo en paralelo (`test_main_window_navigate_payload.py` ×2 en la base; en las corridas de esta tanda también `test_e6_enlace_handshake.py::test_uptime_que_retrocede_es_reinicio` y `test_opciones_qml.py::test_ingeniero_edita_con_ciclo_en_curso`) pasan en serie. `compilar_entrega.py` corre la suite con `-n auto` y repite las rojas en serie con `--lf` (`correr_suite_real`): esas fallas no bloquean la entrega.

## 3. Respuestas de V

Ver `V_resumen.md`. Lo decisivo:
- **V-01:** todo `src/` cuelga de `utils/paths.app_root()` → `raiz_datos_exe()`. `instalador_exe.py` **sí** se usa en tiempo de ejecución (`exe_unico.py` ofrece instalarse si `esta_instalado_aqui()` es falso): se adaptó en s1 y en R1.
- **V-02:** el Setup no tenía `[Run]` ni parámetros propios; el paso 06 hacía `throw` sin `MultiDigitizer.exe`; la tarea de arranque tenía `Delay PT10S` en `tarea_arranque.ps1:32` y `03_tarea_autoclave.ps1:43`.
- **V-03:** las sondas No en uso ya se leían y publicaban en `/status`: el filtro O11 estaba en la presentación y en `gestion_programas`. Vacío al empaque = `bomba_vacio` (+`agua_bomba`) junto con `desbloqueo_puerta_N`.
- **V-04 (BIT-03):** el bloqueo de usuario **no** cuenta filas de `audit_log`: usa `ControlIntentos` en memoria (`backend/autenticacion.py`). Retirar `login_fallido` no cambia el bloqueo (prueba de comportamiento en `tests/test_t17_f2_bitacora.py`).

## 4. Tabla de propiedad de archivos

En `estado.md` (sección «Tabla de propiedad de archivos (P)»). UI-VER pasó de s4 a la sesión principal (F3): retirar `app.version` rompía todas las pantallas que la usaban.

## 5. Qué se implementó

- **F1 (INS-02):** `raiz_datos_exe` con el orden registro → regla anterior → carpeta del .exe; constantes compartidas.
- **F2 (BIT-01..04):** filtro central en `DbManager` (`registrar_auditoria`, lote y tras cierre); `EVENTOS_RETIRADOS` al log de desarrollo; la vista oculta filas viejas de retirados; supresión durante la instalación (sin perfil válido, enclavada); `equipo_instalado` al terminar el asistente (serie, modelo, versión, zona horaria leída del registro sin modificarlo).
- **F3:** claves i18n es/en de la tanda; UI-VER.
- **s1:** INS-01 e INS-02 en el Setup (zona, unidad, disposición, ACL verificadas, registro, actualización, bloqueo de la disposición anterior, limpia y desinstalador sobre `datos`), `_comun.ps1`, `instalador_exe`, `TactilesRepetir`.
- **s2:** EST-06 (herramienta `--rol asociar-tactiles`) y EST-07 (`PT0S`, cubierta de arranque, señal de primer cuadro, instancia única).
- **s3:** SON-01, ESG-01, ESG-02 (protecciones permanentes 1–3, corte en el mismo tick), backend de BIT-05 (`categoria`).
- **s4:** PRC-01, MPR-01, ALM-01, BIT-05 en la UI (desplegables y calendario), «(monitoreo)», VER-08 (prueba).
- **I:** contrato `avisos_corte_prueba` entre backend y UI; códigos de rechazo ESG-02 en la UI; serie `temp_2_camara` del PDF; OpenAPI de referencia con `categoria`; claves nuevas con uso real.

### Tabla evento → categoría (BIT-05, `core/runtime/bitacora.py`)

| Categoría | Eventos (los retirados, en cursiva, no se muestran) |
|---|---|
| Seguridad | falla_reconocida, ciclo_interrumpido, apagar_equipo, modo_prueba_entra, modo_prueba_salida_forzada, aire_atmosferico_cortado_prueba, atrapamiento_orden_invertida, apagado_windows_rechazado, ciclo_no_conforme_reconocido, arranque_camara_no_segura, salidas_sin_confirmar, salidas_confirmadas, salidas_confirmadas_tras_reintento, *modo_prueba_sale*, *salida_prueba*, *salida_prueba_cortada*, *inicio_descartado_por_modo_prueba* |
| Configuración | param_sistema_cambio, idioma_configurado, unidades_configuradas, impresora_configurada, param_ciclo_cambio, param_ciclo_no_aplicado_en_curso, ROLES_SENSOR, correo_configurado, programa_creado, programa_duplicado, programa_habilitado, programa_borrado, reasignacion_io, reasignacion_io_fabrica, reasignacion_io_rechazada, reasignacion_io_verificada, *entradas_mostradas* |
| Usuarios y sesión | login_ok, login_bloqueado, cambio_clave, usuario_creado, usuario_desactivado, usuario_reactivado, clave_restablecida, operador_creado, operador_desactivado, operador_reactivado, usuario_renombrado, cuenta_sistema_rechazada, *login_fallido*, *logout*, *contrasena_fijada_instalacion* |
| Mantenimiento y calibración | mantenimiento_registrado, mantenimiento_configurado, mantenimiento_migrado, calibracion_atm_ok, calibracion_atm_abortada, calibracion_atm_rechazada, calibracion_cambio |
| Sistema | correo_enviado, respaldo_exportado, respaldo_rechazado, respaldo_restaurado, reinicio_control, software_reiniciado, equipo_instalado, ciclo_reimportado, ciclo_completado_desde_respaldo, tarjeta_conectada (y cualquier evento sin clasificar) |

`tests/test_t17_f2_bitacora.py::test_todo_evento_literal_del_codigo_esta_clasificado` exige que todo evento literal del código esté en permitidos o retirados.

## 6. Pruebas

Suite final en `tanda-17` (= árbol de `dev` tras la unión): **8486 passed**, 10 skipped, 3 xfailed y 2 que fallan solo en paralelo y pasan en serie; recolectadas **8501** = base 8251 + 250 nuevas. Ninguna prueba se borró ni se saltó.

Pruebas nuevas (marcador `req`): `test_t17_f1_ruta_datos.py`, `test_t17_f2_bitacora.py`, `test_t17_s1_setup.py`, `test_t17_s1_instalador_exe.py`, `test_t17_s2_asociar_tactiles.py`, `test_t17_s2_cubierta_arranque.py`, `test_t17_s3_son01.py`, `test_t17_s3_esg.py`, `test_t17_s3_bitacora.py`, `test_t17_s4_alarmas_qml.py`, `test_t17_s4_opciones_qml.py`, `test_t17_s4_ver08.py`, `test_t17_s4r_capas_qml.py`.

Pruebas existentes tocadas (solo la aserción que cambia por una decisión de Cristian, con comentario que la cita):

| Prueba | Decisión |
|---|---|
| `test_ver_entrega.py` (`test_historial_entrada_debajo_de_la_marca`) | A1 (R16 §8) |
| `test_f1_registro_pruebas.py` | A1 / Z: bloques A–I |
| `test_backend_autenticacion.py` (401 genérico, 5 fallos, paralelo, logout, salida del modo prueba ×2), `test_db_audit_log.py`, `test_a9_bitacora_d9_6.py`, `test_login_qml_autenticacion.py` | BIT-03 / BIT-01 (`login_fallido`, `logout`, `modo_prueba_sale`) |
| `test_revision_tanda4.py` (2), `test_b8_salida_forzada_modo_prueba.py` | BIT-01: `modo_prueba_sale` va al log de desarrollo (se comprueba ahí, con el dueño y el motivo) |
| `test_l0_contrasenas_instalacion.py` | BIT-02 |
| `test_i18n_linea_base.py` | BIT-05: tercer nivel `bitacora.categoria` (como `bitacora.ev`/`tipo`) |
| `test_i18n.py` | BIT-05: listas `fecha.meses_largos` y `calendario.dias_cortos` leídas con `I18n.valor` |
| `test_ui_qml_app.py` | UI-VER |
| `test_o11_entradas_mostradas.py` (12 aserciones), `test_o3_entradas_mostradas.py` (3), `test_ciclo_en_curso_dominio.py`, `test_backend_ciclo_en_curso_endpoints.py` | SON-01 |
| `test_s9_estado_seguro_arranque.py` (2), `test_s9_planta_simulada.py:360` | ESG-01 (y R3) |
| `test_s9_revision_1.py` (6), `test_s9_planta_simulada.py:375` | ESG-02 (reemplaza SAF-01 de S9) |
| `test_t9_e9_setup_estacion.py:137`, `test_t11_n11_instalador_limpia_tactiles.py:130,175` | INS-02 (literales del `.iss`) |
| `test_c9_manejo_ciclos_banco_qml.py:52,83` | PRC-01 |
| `test_u10b_textos_caben_qml.py:116`, `test_ui_bridge.py:189,203,240` | ALM-01 |
| `test_o2e_bitacora.py:168` | BIT-05 |

Foto de la API: `docs/informes/tanda15/base/openapi.json` actualizada solo con el parámetro `categoria` de `GET /audit_log` (como en la tanda 16, se actualiza la foto y no la prueba).

Claves i18n: sin huérfanas nuevas salvo `bitacora.desde_formato` (el campo de fecha con teclado lo reemplazó el calendario; D-19 prohíbe borrar claves sin autorización: **para Cristian**) y `bitacora.ev.equipo_instalado` (la usa el backend, como las demás `bitacora.ev.*`, que la herramienta ya listaba).

## 7. Hallazgos de R

Ver `R_hallazgos.md`. Resumen: R1 2 altos (V17-s1-01 ACL con entradas explícitas ajenas; V17-s1-03 `Autoclave.exe` desde una USB se instalaba en la disposición anterior) — **corregidos**; R1 3 medios y 2 bajos corregidos; R2 1 medio (segunda instancia del lanzador) y 5 bajos corregidos; R3 1 medio (supresión de la bitácora que releía el perfil y podía perder eventos) corregido, 5 bajos corregidos o anotados; R4 3 medios (ventanas emergentes que tapaban las acciones de seguridad, rechazo de DESPEJAR invisible) y 4 bajos corregidos. Ningún alto queda abierto.

## 8. K — unión y entrega

1. `git checkout dev` y `git merge --no-ff tanda-17` → `584aa7a` (sin conflictos). El árbol de `dev` quedó idéntico al de `tanda-17` ya probado (`git diff tanda-17 dev` vacío): suite 8486 passed + 2 que fallan solo en paralelo y pasan en serie.
2. `a51a120` (en `dev`): `docs/versiones/anomalias_conocidas_1.0.0-alpha.2.md` con las correcciones de la tanda 17, las protecciones permanentes del modo prueba (ESG-02), las DECISIONES SIN CONFIRMAR de ESG-02, EST-06, EST-07 y ALM-01 (AN-20 a AN-24), la lista de pruebas manuales en el PC de prueba y el aviso de que la alpha.2 exige desinstalar e instalar en limpio. Uso previsto: igual que la alpha.1, sin uso clínico.
3. `python tools/entrega/compilar_entrega.py --con-generador` se lanzó desde `dev` limpio y **lo detuvo el sistema por memoria baja** mientras corría la suite de sus verificaciones previas. No dejó nada: sin commit `chore(ver)`, sin etiqueta y sin carpeta en `entrega/`. Por la indicación del entorno no se relanzó sin orden. Las condiciones del script se cumplen (rama `dev`, sin cambios versionados ni archivos sin versionar en las carpetas del producto, Python de compilación `..\_venv_t8_producto` e ISCC presentes; las rojas en paralelo pasan en serie y el script las repite con `--lf`).
   - **Versión entregada: ninguna.** No hay SHA-256 ni comando de push de etiqueta.
   - **Para Cristian:** con memoria libre (cerrar otras aplicaciones), desde `dev` limpio: `python tools/entrega/compilar_entrega.py --con-generador`. Saldrá la `1.0.0-alpha.2` (incluye las tandas 16 y 17); el script imprime al final `git push origin dev v1.0.0-alpha.2`.

## 9. L — limpieza

- Worktrees quitados (sin cambios ni archivos sin seguimiento): los 4 de esta tanda (`agent-a542728c…`, `agent-a9f214ab…`, `agent-aac0894d…`, `agent-ad824077…`); `git worktree prune`. Los worktrees de tandas anteriores en `.claude/worktrees/` tienen `data/` sin seguimiento: no se quitaron (la regla prohíbe borrar archivos sin seguimiento), y por eso sus ramas `tanda-16-s2..s5` siguen.
- Ramas borradas con `git branch -d` (todas unidas a `dev`): `tanda-16`, `tanda-17-s1..s4`, `tanda-17-r1..r4` y las 4 `worktree-agent-*` de esta tanda.

## 10. Evaluación IEC 62304

- **Solicitud de cambio:** hallazgos de la instalación de la compilación I en el equipo de pruebas (decisiones de Cristian del 26-oct, `decisiones_tanda_17.md`). Clase C. Afecta al instalador, la estación de Windows, el arranque, la lógica del modo prueba y del estado seguro, la presentación de sondas, la bitácora y la UI.
- **Peligros nuevos o actualizados (ISO 14971):**
  - **ESG-02 (modo prueba con estado seguro):** se liberan salidas que antes estaban bloqueadas con el estado seguro activo. Control del riesgo: solo con lectura vigente de presión; protecciones permanentes 1–3 que fallan cerradas (puerta/desbloqueo con la cámara fuera de atmosférica o sin lectura; vapor de cámara con una puerta no confirmada cerrada, con corte en el mismo tick); se conserva el corte de aire atmosférico. Riesgo residual: sin datos de presión o de puerta el modo prueba queda más restringido. Verificación: `test_t17_s3_esg.py`, `test_s9_*`, revisión R3, banco I-10.
  - **INS-02 (ACL):** un software Clase C modificable por un usuario estándar (raíz de D: con «crear/modificar» para usuarios autenticados). Control: DACL protegida reemplazada entera y verificada por SID y máscara; el Setup se detiene si no se puede verificar; `estacion` solo administradores. Residual: verificación como administrador pendiente en el PC (I-03).
  - **BIT-03 (bitácora):** riesgo de cambiar el bloqueo de usuario o perder eventos de seguridad. Control: el bloqueo no depende de `audit_log` (prueba de comportamiento); filtro central con lista de retirados explícita y escaneo del código; un evento desconocido se registra; la supresión de la instalación se enclava al ver un perfil válido.
  - **EST-07 (cubierta):** pantalla negra que impida ver alarmas. Control: tope de 180 s con respaldo, instancia única, fallo solo al log. Residual: DECISIÓN SIN CONFIRMAR, banco I-07.
  - **ESG-01:** CIC-10 suprimido sin presión. Control: NO ABRIR y el bloqueo de inicio se mantienen; CIC-10 por los demás motivos.
- **Regresión:** suite completa en verde (8486 + 2 solo en paralelo); pruebas de arquitectura de capas, rutas y OpenAPI equivalentes; 4 revisiones independientes.

## 11. DECISIONES SIN CONFIRMAR

- A1: corrección de la prueba de historial por la vía de R16 §8.
- BIT: evento desconocido se registra (con aviso); `inicio_descartado_por_modo_prueba` y `salida_prueba_cortada` retirados por BIT-01 literal (V17-s3-03, **para confirmar**); la salida del modo prueba por paro queda solo en el log de desarrollo; las filas viejas se ocultan.
- INS-01/02 (s1 y R1): ver `P_resumen.md` y `R_hallazgos.md` (respaldos de la limpia en `X:\Especifika\Autoclave_respaldos`, NTFS/ReFS obligatorio, mínimo también al actualizar, `/ZONA=` inválido detiene, exclusión de buses USB/SD/MMC, `estacion` preexistente apartada, reversión fallida conserva rutas, `AUTOCLAVE_RUTA_DATOS`, exe desde USB solo avisa).
- EST-06/07: todo EST-07; formato Digimon `20-`; gracia de 15 s; un solo lanzador (el segundo sale con 0).
- SON-01: gráfica/PDF/correo con todas las sondas declaradas por el perfil; `temp_2_camara` en el PDF solo con lecturas.
- ESG-01: la trama AI vencida cuenta como presión sin lectura.
- ESG-02: criterio de puerta incluye el vacío; regla de puertas por temperatura conservada; recuperación de arranque pendiente también liberada con presión; `bomba_vacio` sin bloqueo propio.
- ALM-01: «Confirmar y llevar a estado seguro» fuera de la ventana; sin botón «reconocer» en el detalle; capas cerradas en las dos pantallas ante seguridad urgente.
- PRC-01: el mismo selector en Manejo de ciclos (con tarjeta del programa elegido).
- UI-VER: la intro de arranque sigue mostrando la versión (D-07 previo).

## 12. Pruebas manuales pendientes (PC de prueba)

Hoja de banco, bloque I (I-01 a I-12) y `tools/instalador/LEEME.md`: zona horaria; unidad D: (sin USB); ACL de `programa` con `D:\Especifika` creada antes por un usuario estándar y `AplicarAcl` con código 0 como administrador; actualización con la unidad fija; bloqueo de la disposición anterior; instalación limpia y desinstalación (reversión fallida); táctiles sin MultiDigitizer (exportación de Digimon) y reversión; cubierta de arranque (segunda instancia, 15 s/180 s) y medición del hueco autologon → tarea; SON-01; ESG-01; ESG-02 en operación; pantallas; bitácora.

**Importante:** la alpha.2 no actualiza la compilación I ni la alpha.1 (disposición anterior): hay que desinstalar e instalar en limpio, sin migración de datos.
