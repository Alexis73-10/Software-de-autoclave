# Informe R24 — Tanda 24: reasignación sin bloqueos, verificación por lectura, motivo en pantalla y tipo «RTD»

Fecha: 30-oct-2026. Rama `tanda-24` (desde `dev` 9a933ff3), unida a `dev` en **60a338cb** (sin fast-forward, sin push). Spec: `docs/mis_plans/prompt_claude_code_tanda24.md` (RSB-01..08).

**No se compiló la entrega. Para compilarla: `python tools/entrega/compilar_entrega.py --con-generador` desde `dev` limpio.**

## Commits

| Commit | Contenido |
|---|---|
| 33b82347 | A0: prompt, `estado.md`, inventario RSB-04 |
| d4e80a4d | P1 backend (rama `tanda-24-backend`): RSB-01, 02, 03, 06 (backend y riesgos), 07 |
| 7948967e | P2 UI (rama `tanda-24-ui`): RSB-03 (UI), 04, 05, 06 (UI, i18n, CLAUDE.md), 07 (UI), 08 |
| 36f56b3e | Unión de P1 y P2 en `tanda-24` |
| dfca3de3 | Correcciones de la revisión R (SAF-01..06) |
| 60a338cb | Merge a `dev` |

Nota de proceso (DECISIÓN SIN CONFIRMAR): P1 y P2 se hicieron en la sesión principal, en ramas `tanda-24-backend` y `tanda-24-ui` del mismo árbol, y no en subagentes con worktree. El paquete `autoclave` está instalado en modo editable apuntando al árbol principal, así que las pruebas corridas en un worktree importarían el código del árbol principal y no el del worktree. La revisión R sí la hizo un subagente de solo lectura.

## Qué cambió, por RSB

### RSB-01 y RSB-02: bloqueos de la reasignación (`src/autoclave/backend/server_reasignacion.py`)

- `_motivo_bloqueo()` ya no recibe argumentos y solo rechaza, en este orden: `ciclo`, `estado` (fuera de PREPARACION/PREPARADO/FALLA), `modo_prueba` y `apagando`. Responde 409 `estado_no_permitido` con `motivo`.
- Se borraron:
  - `_motivo_sensor_seguridad`, es decir SAF-01 de ESS-07: presión de cámara, Principal, sondas calientes y límite de temperatura;
  - `_motivo_estado_seguro`: SAF-03 (paro o confirmación pendiente) y H1 (carga líquida o sellada);
  - los códigos `sensor_camara_no_segura`, `estado_seguro`, `estado_seguro_confirmar` y `estado_seguro_liquido`.
- `diferencias` ya no decide el bloqueo.
- Se conserva sin cambios:
  - solo el INGENIERO;
  - 428 `confirmacion_requerida` y el nombre escrito de las reforzadas;
  - reautenticación;
  - 422 de validación y de puerto sin calibración;
  - `_guardar_y_reiniciar`: relectura bajo `_sm_lock` (`guard_estado`), deshacer ante cualquier error e `iniciar_apagado` (ALL_OFF) antes de `reinicio.solicitar`;
  - SEN-09: la función queda sin verificar y bloquea el inicio de ciclo.
- `/factory` y `/verify` pasan por la misma `_comprobar_estado`.
- Comentario «Reglas» de la cabecera actualizado.

### RSB-03: aviso no bloqueante

- **Backend.** `aviso_camara()` devuelve True si:
  - `camara_segura.motivos(...)` no está vacío (mismos argumentos que usaba SAF-01: programas para seguridad, perfil, `presion_vigente`, `temp_max_tras_ciclo`);
  - o `PARO_EMERGENCIA` está activo (`is not False`);
  - o hay cualquier excepción.

  `GET /io/assignment` publica `aviso_camara`. La fila `reinicio_control` lleva `aviso_camara` en `detalle`; se calcula antes de escribir el archivo (revisión R, SAF-03).
- **UI.**
  - `ReasignacionController.avisoCamara` vale True si falta el campo.
  - `OpcionesReasignacion.qml` añade `reasignacion.aviso_camara` (es y en) a los diálogos de reinicio de Aplicar y de Restaurar fábrica.
  - Los dos diálogos recargan los datos antes de abrirse (revisión R, SAF-05).
  - No cambia botones ni pasos.

### RSB-04 y RSB-05: motivo real en pantalla

- **Vía de los códigos.** `sesion_backend.codigos_conocidos(ruta)` acepta `_CODIGOS_REASIGNACION` solo en `/io/assignment` y `/io/assignment/*`.
  - Códigos: `conflicto`, `puerto_inexistente`, `funcion_desconocida`, `fabrica_invalida`, `asignacion_invalida`, `archivo_ilegible`, `archivo_invalido`, `sin_cambios`, `confirmacion_requerida`, `confirmacion_reforzada`, `nombre_no_coincide`, `puerto_sin_calibracion`, `no_se_pudo_guardar`, `reinicio_en_curso`, `reinicio_pendiente`, `no_pendiente`, `sin_cambio_observado`, `sin_prueba_de_salida`, `sin_lectura` y `error`.
  - En las demás rutas el resultado de `interpretar` no cambia. Es la «vía equivalente y documentada» que permite la spec, en lugar de `_CLAVES` global. Así se evita cambiar otras pantallas que reciben `confirmacion_requerida` (respaldo, E/S) o `archivo_invalido` (respaldo). DECISIÓN SIN CONFIRMAR.
- **Textos.** `reasignacion_controller._MENSAJES` tiene texto para todos los códigos.
  - Un 409 `estado_no_permitido` muestra `reasignacion.motivo_<motivo>` (función `_texto_rechazo`).
  - Textos nuevos (es y en): `err_fabrica_invalida`, `err_asignacion_invalida`, `err_archivo`, `err_validacion`, `err_confirmacion_requerida`, `err_confirmacion_reforzada` (antes caía en «el nombre no coincide»), `err_configuracion_invalida`, `err_reinicio_pendiente`, `falta_puerto_sin_calibracion` y `falta_error`.
  - `sesion_invalida` y `clave_pendiente` usan las claves `sesion.*`.
  - El genérico queda solo para lo desconocido.
- **Prueba de regla.** `tests/test_t24_codigos_reasignacion.py` extrae por AST los códigos de `RechazoApi`/`_rechazar`/`_Rechazo` (incluidas las ramas `a if c else b`), de `.get("codigo", x)` y de las devoluciones de `_evidencia_que_falta`, en `server_reasignacion.py` (sin las funciones de respaldo) y `dependencias.py`, además de los `"codigo"` de `asignacion_io.py`. Exige que cada código esté en `codigos_conocidos` de las 3 rutas, en `_MENSAJES` y en es/en. Otra prueba exige que los motivos de `_motivo_bloqueo` estén en `_MOTIVOS`.

### RSB-06: limpieza y documentación

- **Retirado de `_MENSAJES`/`_MOTIVOS`/`_FALTAS` y del catálogo es/en:**
  - `motivo_estado_seguro`, `motivo_estado_seguro_confirmar` y `motivo_estado_seguro_liquido`;
  - `err_sensor_camara_no_segura`;
  - `falta_calibracion_requerida` y `verificar_texto_ai`.

  Ninguna prueba de i18n exigía conservarlas. Se conserva `motivo_estado_seguro` de **otra** sección del catálogo, que es otra cosa.
- **Documentación.** Se actualizaron `CLAUDE.md` (sección nueva «Reasignación de E/S sin bloqueos (tanda 24)») y `docs/riesgos/registro_riesgos.md`. HAZ-IO-05 pasa a riesgo aceptado por Cristian, con las mitigaciones y la nota del paro. El residual queda ALTO en (a) H1 y (e) lectura sin verificar.

### RSB-07: verificación de una analógica sin calibrar de nuevo

- **Condiciones de `_evidencia_que_falta` (AI):**
  - calibración vigente del puerto (la nominal cuenta); si falta, `puerto_sin_calibracion`;
  - lectura válida (`aio.responde`), dentro del rango que publica el control (0 < T ≤ 200 °C; −10…450 kPa; revisión R, SAF-02); si no, `sin_lectura`;
  - sin puerto en memoria → `error` (SAF-06).

  Ya no existe `calibracion_requerida`.
- **Ganchos retirados:** `evidencia_ai`, `anular_evidencia_ai` y `anular_evidencias_ai`, con sus llamadas en `rutas/io.py` (PATCH y restaurar calibración) y `rutas/respaldo.py`. DO sigue con `_evidencias()`/`evidencia_do`, y DI no cambia.
- **Se conservan** contraseña, nombre escrito, `no_pendiente`, `reinicio_pendiente` y la relectura bajo `_lock_escritura`/`srv._lock_archivos`. Esa relectura usa ahora una sola instantánea de `units.get_all()` para la evidencia y para la auditoría (SAF-04).
- **Lectura publicada.** `asignacion_io.lectura()` es nueva y pura. `GET` publica `verificacion.funciones[f].lectura`.
- **Pantalla y auditoría.** El diálogo de Verificar de una analógica muestra la lectura actual (`reasignacion.verificar_texto_lectura`, recargada al abrir) y ya no pide calibrar. La auditoría `reasignacion_io_verificada` lleva `metodo: "lectura"`, `lectura` y `unidad`.

### RSB-08: tipo «RTD» en Reasignación

- `reasignacion_controller.tipo_visible(fila)` devuelve «RTD» para `AI_TEMP`, «AI» para `AI_PRES` y DI/DO sin cambio; sin `grupo`, se deduce de `temperatura`.
- Se publica como `filas[].tipo_visible` y `verificacion[].tipoVisible`. La columna Tipo usa `fila.dato.tipo_visible`.
- El tipo interno `"AI"`, los grupos, la API, `asignacion_io.json`, la bitácora y la auditoría no cambian.
- **Otras pantallas revisadas con grep** (Entradas/Salidas, Calibración de sensor, Información del equipo, `ui_pyside`, i18n): ninguna muestra «AI» como tipo de una sonda de temperatura. Entradas/Salidas ya muestra «RTD 01» como id del puerto (`io_names`). No hubo nada más que cambiar.

## Revisión R (subagente de solo lectura) y correcciones

Lo que se debía conservar está intacto:

- RSB-02 y SEN-09;
- RSB-07: una analógica sin lectura no se verifica;
- el reinicio con ALL_OFF;
- RSB-08 sin tocar el tipo interno;
- nada fuera de la reasignación cambió.

Hallazgos y correcciones (commit dfca3de3):

- **SAF-01 (ALTO): reasignar el propio `paro_emergencia` con el paro pulsado.**
  - Riesgo: RSB-01 lo permite ahora. Tras el reinicio, el puerto nuevo, sin verificar, podría leer «liberado» sin serlo, y los lazos de PREPARACION/PREPARADO podrían encender vapor.
  - Corrección: mientras `paro_emergencia` (DI) esté pendiente de verificar, `context._inhibir_salidas_sin_verificar` inhibe también las salidas de energía, igual que con una AI pendiente. El venteo sigue.
  - DECISIÓN SIN CONFIRMAR. Toca `backend/context.py`, que es parte del mecanismo SEN-09 de la reasignación.
  - Atenúa el riesgo: el paro es NC (`devices/paro_emergencia`: DI en 0 o sin dato = activo). Un puerto nuevo sin cablear se lee como paro activo.
- **SAF-02:** rango de plausibilidad en la lectura que verifica.
- **SAF-03:** `aviso_camara` se calcula antes de escribir el archivo.
- **SAF-04:** una sola instantánea para la evidencia y la auditoría.
- **SAF-05:** los diálogos recargan el aviso al abrirse.
- **SAF-06:** código `error` en lugar de `puerto_sin_calibracion` sin puerto.

## Comportamiento con el paro activo tras el reinicio (verificado en el código)

1. **Antes de reiniciar.** `iniciar_apagado` detiene el lazo y manda `link.all_off()`.
2. **Al arrancar.** `ParoEmergencia` empieza activo (`PARO_EMERGENCIA` True, `PARO_REAL` False) hasta leer la DI.
3. **Si la cámara no es segura.** `ControlLoop._procesar_recuperacion` arranca el estado seguro S9 con `ProtocoloFallo.ejecutar(abrir_valvulas=False, solo_lenta=True)`: `reset_all_outputs()` y el log «Protocolo fallo: paro de emergencia — salidas apagadas, sin válvulas».
   - Ese mensaje sale en todo arranque S9, con o sin paro, porque el arranque siempre usa `abrir_valvulas=False`. Es engañoso cuando no hay paro, pero el texto ya era así antes de esta tanda.
4. **Mientras el paro siga activo.** `ProtocoloEstadoSeguro.update()` hace pausa y `return` antes de `protocolo.update()`: **no se mueve ninguna válvula**. Con un paro real (`PARO_REAL`), al soltarlo exige «Confirmar y llevar a estado seguro». Sin paro real, al volver los datos reanuda solo la lenta.
5. **Inhibición.** La función reasignada queda sin verificar (SEN-09, sin ciclos). Si era el paro, el control automático tampoco aporta energía (SAF-01).

## Pruebas

- **`tests/test_ess07_reasignacion_reinicio.py`, sección 6 nueva:**
  - se acepta (nunca 409 por sensores, paro ni estado seguro) con presión sin lectura, Principal sin lectura, ninguna sonda, sonda caliente, cámara presurizada, sin datos vigentes, paro activo, confirmación pendiente, estado seguro sobre carga líquida y sellada, y tipo de carga ilegible; también en Restaurar fábrica;
  - 428/422 siguen rigiendo;
  - 409 en CICLO, en un estado no permitido, en modo prueba y apagando, en las 3 rutas, y en ese orden;
  - `aviso_camara` True, False y ante una excepción, y en la auditoría.

  Los 2 `xfail(strict)` de H1 siguen, con el motivo actualizado: ahora es riesgo aceptado.
- **`tests/test_r8_reasignacion_api.py`:**
  - se retiran las pruebas de ESS-07 (SAF-01/03, H1) y de los ganchos AI;
  - verificación sin calibrar de presión y de temperatura, con la auditoría `metodo: "lectura"`;
  - `sin_lectura` sin lectura y fuera de rango (0,0 °C, 250 °C, 500 kPa);
  - `puerto_sin_calibracion`;
  - nunca `calibracion_requerida`;
  - la relectura bajo los locks.
- **`tests/test_r8_arranque.py`:** el paro pendiente inhibe la energía (SAF-01).
- **`tests/test_t24_codigos_reasignacion.py`, nuevo:**
  - la regla RSB-05;
  - cada código muestra su texto en las 3 rutas;
  - el motivo de `estado_no_permitido`;
  - lo desconocido sigue siendo genérico y las demás rutas no cambian;
  - RSB-06;
  - `aviso_camara` aparece y desaparece en los dos diálogos, en QML real offscreen;
  - el diálogo de Verificar muestra la lectura y no pide calibrar;
  - la columna Tipo con «RTD»/«AI»/«DO» en pantalla.
- **Suite** (`pytest tests -n auto`, sobre `tanda-24` con las correcciones de R): 9275 passed, 11 skipped, 7 xfailed y 2 failed. Fallaron `test_home_view.py::test_home_view_tarjeta_impresion_general_navega_a_impresion_menu` y `test_impresion_menu.py::test_impresion_menu_instancia_sin_crash`, caídas de trabajador xdist ya conocidas (en la tanda 23, `test_home_view`). En serie: 13 passed.

## Decisiones sin confirmar

1. Los códigos de la reasignación se reconocen por ruta (`codigos_conocidos`) y no en `_CLAVES` global, para no cambiar otras pantallas.
2. SAF-01: el paro de emergencia reasignado sin verificar inhibe las salidas de energía del control automático.
3. SAF-02: la lectura que verifica debe estar en el rango de publicación del control (0,0 °C cuenta como sin lectura).
4. `reasignacion.alerta_analogicas` («…usa la calibración de su puerto nuevo: calíbrela antes de usar el equipo») se conserva. Es una recomendación metrológica (AIN-R3: AI 09–16 nominales hasta calibrar en sitio), no un requisito para verificar.
5. P1 y P2 sin worktree (ver «Nota de proceso»).
6. La lectura se muestra con punto decimal y una cifra («101.3 kPa»), igual en es y en.

## Qué verificar en el equipo

1. Sin ningún sensor conectado y con el paro activo, reasignar la presión de cámara a otro puerto:
   - debe aceptarse;
   - el diálogo de reinicio debe mostrar el aviso de verificar en el manómetro;
   - el control se reinicia con las salidas apagadas;
   - con el paro activo no se mueve ninguna válvula;
   - Preciclo no deja iniciar un ciclo (SEN-09).
2. Forzar rechazos y ver su motivo, no «No se pudo aplicar la reasignación»:
   - entrar en modo prueba: «Salga primero del modo prueba de salidas»;
   - contraseña mala;
   - nombre de una reforzada mal escrito;
   - puerto ocupado.
3. Conectar el transductor en el puerto nuevo, con lectura. Verificar la presión de cámara sin calibrarla: el diálogo muestra la lectura actual (kPa); al confirmar, queda verificada y la bitácora guarda la lectura. Sin transductor, «Falta: una lectura válida del sensor en el puerto nuevo» y el botón Verificar deshabilitado.
4. Columna Tipo de Reasignación: «RTD» en las temperaturas, «AI» en las presiones, DI/DO igual.
5. Si se reasigna el paro de emergencia: hasta verificarlo, el vapor y el aire comprimido no deben encenderse solos.

No se compiló la entrega. Para compilarla: `python tools/entrega/compilar_entrega.py --con-generador` desde `dev` limpio.
