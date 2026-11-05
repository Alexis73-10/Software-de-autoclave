# R27 — Tanda 27: ajustes de la Parte A y depuración del repositorio (5-nov-2026)

Rama `tanda27` desde `dev` c3b4e1dc. Etiqueta local de respaldo: `respaldo-pre-depuracion`. Sin push. **Entrega no compilada**: el comando es `python tools/entrega/compilar_entrega.py` desde `dev` limpio. Detalle: `A_informe.md` (Parte A), `inventario*.md`, `dudosos.md` (DEP-01..36), `verificacion_paso6.md`, `AJUSTES.md` (raíz).

## Parte A (resumen; ver `A_informe.md`)
- A1 unidades sincronizadas entre pantallas (`iniciar_sondeo` en `app.py`); A2 sin standby con modo prueba; A3 deslizador INICIAR oculto con modo prueba; A4 puertas y bomba de vacío como interruptor sin tope + enclavamiento abrir/cerrar + vigilancia por tick del atrapamiento + HAZ-IO-07.
- A4 pasó por revisor: 1.ª pasada **rechazada** (atrapamiento solo evaluado al recibir la orden), corregida y **aceptada** en la 2.ª.
- A7 (instrucción añadida por Cristian al prompt durante la ejecución): códigos y mensajes de incoherencia por regla en Parámetros del equipo (`incoherente_empaque`, `incoherente_limites`), con rango válido efectivo calculado por el backend; sin cambiar reglas ni márgenes. Revisor: aceptar. Pruebas: `tests/test_t27_a7_incoherencia_parametros.py`.
- **A5 y A6 aparecen mencionadas en el prompt (encabezado `A1..A7` y «junto con A6») pero no están definidas en el texto: no se implementaron. Pregunta para Cristian.**

## Depuración: qué se retiró (por categoría)
| Categoría | Retirado | Archivos / líneas |
|---|---|---|
| QML | `Componentes/BarraInferior.qml` | 1 archivo, −45 |
| Rutas | `GET /cycles`, `GET /cycle/current/readings`, `GET /cycle/history/{id}/readings`; métodos de cliente `get_current_cycle_readings`, `list_user_cycles`; copias del simulador; 3 pruebas | 6 archivos, −157 |
| Base de rutas t15 | solo esas 3 rutas en `rutas.json` y `openapi.json` (`roles.json` igual) | 3 archivos, −101 |
| Símbolos Python | `CERO_VALIDO`, `CLAVES_LIMITES`, `_entradas_previas` (escritura), `BEEP_AVISO`, import en `preparacion.py`, 7 métodos de `ui_service_backend`, `_ventanas.{cambiar_texto,reafirmar}`, `faseCiclo`, `simboloTemp/Pres`, `referenciaUsuario`, `redConectada`, `INACTIVIDAD_UI_S` | 11 archivos, −57 |
| Herramientas | `ensayo_actualizacion_{b_d,f_g,g_h,i}.py`, `medir_contador_ciclos.py` | 5 archivos borrados (≈ −574) |
| i18n | 32 claves, es y en | 2 archivos, −68 |
| ESP32 | comentarios, docs vigentes, fixtures, renombre `ALARMAS_SOLO_SERIAL → ALARMAS_RETIRADAS_HISTORIAL`, 7 documentos a `docs/referencia/obsoleto/`, riesgos y trazabilidad marcados obsoletos, `tests/test_t27_sin_esp32.py` | 53 archivos |

Fuera de `docs/`, la diferencia de la depuración es de 70 archivos, +206/−998.

Pruebas retiradas con el código que probaban: `test_list_cycles_incluye_todos_con_source` (`GET /cycles`), `test_list_user_cycles_filtra_solo_source_user` y `test_list_user_cycles_retorna_vacio_si_falla_backend` (`UIServiceBackend.list_user_cycles`); en `test_t16_s5` se quitó la ruta `readings` de un bucle (la cubre `/ticket`).

## Dudosos
36 elementos en `dudosos.md` (DEP-01..36). Destacan: **DEP-01 ui_pyside** y los 4 `.docx` de `docs/arquitectura/` (DEP-33) que aún describen el ESP32.

## ui_pyside
**No se retira.** Faltan equivalentes en QML de «Imprimir alarmas activas» (ticket térmico) y «Tiempo de secado» del ciclo activo, y parámetros, E/S y calibración no están comparados función por función. Es inalcanzable desde la UI (solo `--rol ajustes`). `ui_qml/app.py:30` importa `NuevoUsuarioBridge` desde `ui_pyside`. Se conservan `AutoclaveSettings.spec` y `PySide6-Fluent-Widgets`.

## Dependencias y SOUP
Sin cambios de dependencias ni del lock; nota fechada en `docs/riesgos/lista_soup.md`.

## Diferencias con la base
- Rutas/OpenAPI: solo las 3 rutas retiradas (la prueba `test_t15_rutas_equivalentes` pasa); A7 no cambia el OpenAPI.
- TOC de `Autoclave.spec`: **idéntico** (2328 módulos; no faltan ni sobran). `AutoclaveBackend.spec` compila (salida 0). `AutoclaveSettings.spec` y `GeneradorCodigos.spec` no se recompilaron (no cambian).
- QML: 0 advertencias nuevas en los 11 arneses de `tests/banco` y 891 pruebas QML iguales (base `af2a3fb0`); tema oscuro cubierto solo por `osc_capturas.py` y `test_tema_oscuro.py`.
- Simulador: login, ciclo hasta COMPLETADO y Reportes (200) verificados; no se manejó la UI sin pantalla.
- Búsqueda `esp32|pyserial|serial_link|\.ino\b`: solo las excepciones explícitas de `tests/test_t27_sin_esp32.py`.

## Suite
- Parte A: 10964 pasadas.
- Depuración (antes de A7): 10962 pasadas, 2 rojas: una por una ruta retirada en `test_t16_s5` (corregida) y `test_t21_pantalla_fin_ciclo_qml::test_la_cuenta_se_detiene_con_un_modal` (intermitente en paralelo, pasa en serie).
- Final con A7: ver `suite_final.txt` / `CERRADO.txt`.

## Revisiones y ajustes
Revisor de seguridad: A4 (rechazo → corrección → aceptar), diff de directorios de control y `rutas/respaldo.py` (rechazo por una prueba que llamaba a una ruta retirada → corregido; solo comentarios y código muerto), A7 (aceptar). Ver `AJUSTES.md`.

## Hallazgos y preguntas para Cristian
- **AJ27-A4-01 (Media):** con la pantalla abierta el keepalive de 30 s y el rearme de inactividad impiden que venza el respaldo de 90 s: motor de puerta o bomba pueden quedar encendidos sin tope. Opciones: tope de tiempo para el movimiento de puerta, o que la inactividad no se rearme con puerta/bomba en ON.
- AJ27-A7-01..05 (bajas): ver informe de A7 en `A_informe.md`; además Baja-1 (`_rango_efectivo` con valores de más de 2 decimales pegados a un borde, el guardado vuelve a validar) y Baja-2 (un `NaN` en `global_params.json` podría dar 500 en lugar de 422), sin corregir.
- DECISIÓN SIN CONFIRMAR: enclavamiento abrir/cerrar; terminar la inversión D-ES-16 con una orden propia de abrir; reglas de A3 (falla cerrada, cierre de la confirmación «sin registro»); reglas añadidas en A7 (`empaque_*`, `sin_referencia`).
- Pendiente de banco: puerta con actuador real (HAZ-IO-07), T27-A7-01 en pantalla (también en psi), arranque real de la 2.ª ventana (A1).
- Pregunta: A5 y A6.
- Hoja de banco: se añadió el bloque T27 a mano en el `.md`; el `.html` no se regeneró y el generador borra el bloque T26 del `.md` (no se usó).
