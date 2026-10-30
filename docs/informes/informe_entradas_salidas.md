# Informe — Opciones › Entradas / Salidas y barra inferior (20-oct-2026)

Rama: `tanda-4`. **Sin commit**: todo queda en el árbol de trabajo para que Cristian lo revise. La suite completa quedó en verde: **3977 pruebas pasan, 1 se omite**.

## Qué se hizo del plan `planeacion_opciones_entradas_salidas.md`

### Backend (`backend/server.py`)
| Id | Cambio | Pruebas |
|---|---|---|
| B-ES-9 / D-ES-15 | Se retiró R-02 de `PATCH /io/test/output/{name}` y se borró `_motivo_r02` junto con sus ayudantes (ya no tenían otro uso). | `tests/test_io_endpoints.py` |
| D-ES-16 / §6.7 | Seguro de atrapamiento: con la entrada activa (NC, `0` = atrapada), `cerrar_puerta_N` apaga el cierre y enciende `abrir_puerta_N`. Si la señal se libera con el dedo pulsado, el cierre no se reanuda hasta soltar (P-ES-8). Una sola entrada de bitácora `atrapamiento_orden_invertida` por pulsación. | ídem |
| B-ES-1 | `GET /status` expone `sensors.adc` (cuentas crudas por sensor). | `tests/test_io_test_mode_endpoints.py` |
| B-ES-2 | Módulo `core/runtime/io_names.py` y `GET /io/channels` (13 DI, 18 DO, 3 temperatura y 4 presión en ACV-2026-001), con id físico, clave i18n, `momentanea` y `bloqueada`. | `tests/test_io_names.py` |
| B-ES-3 | `origen_lectura` en el PATCH de calibración, validado y guardado en `audit_log.detalle`. | `tests/test_backend_calibration_endpoints.py` |
| B-ES-4 | `POST /calibration/{tipo}/{sensor}/restaurar` (`ultimo` / `defecto`), con las mismas reglas de rol y estado, y con reversión del archivo si falla la auditoría. | ídem |
| B-ES-5 / P-ES-3 | Salidas momentáneas: campo `momentanea`, caducidad de 1.5 s sin renovación y registro solo del primer y último pulso. | `tests/test_io_momentaneas_keepalive.py` |
| B-ES-6 / P-ES-4 | `POST /io/test/keepalive` y salida automática del modo prueba a los 90 s sin actividad de la sesión dueña. | ídem |
| B-ES-7 | Ya existía: el cierre de sesión de la sesión dueña sale del modo prueba (cubierto por pruebas previas). | sin cambio |
| B-ES-8 | `POST /io/test/exit` acepta una causa de una lista cerrada, que se guarda en `modo_prueba_sale`. | `tests/test_io_test_mode_endpoints.py` |

### Interfaz (QML, ES-F1 a ES-F3)
- `ui_qml/domain/entradas_salidas.py`: formato de datos sin inventar ceros ("Sin datos") y fórmula de calibración. Pruebas en `tests/test_es_dominio.py`.
- `ui_qml/domain/permisos_opciones.py`: `puede_modo_prueba` y `puede_calibrar` (matriz de §3, OPC-28).
- `ui_qml/controllers/entradas_salidas_controller.py` (registrado en `controllers/__init__.py`). Pruebas en `tests/test_es_controlador.py`.
- `Pantallas/OpcionesEntradasSalidas.qml`: selector de 4 segmentos, tarjetas de entradas y salidas, banner y diálogo de advertencia del modo prueba, botones sostenidos y de mantener pulsado (renovación cada 500 ms), keepalive cada 30 s, cierre del modo prueba por abandono o por 5 min sin actividad, sensores de temperatura y presión con ADC y botón Calibrar.
- `Pantallas/OpcionesCalibracionSensor.qml`: lectura en vivo, ganancia/offset, puntos bajo y alto con captura o escritura, resultado, restaurar con confirmación y diálogo de rango. Prueba de carga en `tests/test_es_pantallas_qml.py`.
- i18n: bloque `io` en `es.json` y `en.json` (`io.di.*`, `io.do.*`, `io.ai.*`, `io.ui.*`, `io.err_*`). Se amplió `test_i18n_linea_base.py` para los textos de tres niveles, igual que se hizo con `alarmas`.
- `sesion_backend.py`: se añadieron los códigos nuevos del backend al mapa para que la UI muestre el motivo (antes caían en "error genérico").

## Qué NO se hizo (y por qué)

1. **Cableado en `Opciones.qml` (ES-F4): hecho después, a petición de Cristian**, con cuatro ediciones pequeñas en el archivo que la otra sesión tiene abierto: un `Loader` (`cargadorEntradasSalidas`), la condición de "Próximamente", Atrás sube un nivel de la calibración y salir de OPCIONES cierra el modo prueba. No se añadió el diálogo de confirmación de Cerrar sesión con modo prueba activo (el backend apaga las salidas al cerrar sesión de todos modos).
2. **Instrucción de la barra flotante (T1 a T5).** Omitida por completo: `Login.qml`, `CambioClave.qml`, `NuevoUsuario.qml` y `BarraInferiorMenu.qml` ya tienen cambios de la otra sesión. No se tocó ningún archivo de esa tarea ni se capturó nada.
3. **B-ES-10** (renombrar `presion_admosferica` → `presion_atmosferica`). Toca `global_params.json`, `validacion_config.py`, `camara_segura.py` y `advanced_door.py` (código de seguridad) y requiere migrar la configuración guardada. Tras retirar R-02, el servidor ya no lee esa clave. Queda como tarea separada.
4. **Método de ganancia y offset directos** (§5.4). El backend no tiene endpoint para eso (solo calibra por puntos); no estaba en la tabla B-ES.
5. **"Último guardado" (S-ES-1)** no se muestra como columna: la tabla muestra Actual y Por defecto, y la fecha y usuario de la última calibración.
6. **Vencimiento de calibración** (P-ES-5) y retiro de `ui_pyside/views/entrdas_salidas/*` (Fase 5): no se tocaron.

## Decisiones sin confirmar
- **`origen_lectura` es opcional en el backend** (el plan lo pedía obligatorio): la UI PySide actual no lo envía y se rompería. Si falta, no se guarda; si viene inválido, 422.
- P-ES-3 (1.5 s de caducidad, renovación a 500 ms) y P-ES-4 (keepalive 30 s, salida a los 90 s) se implementaron como se proponían, aún sin confirmar. Las constantes son `CADUCIDAD_MOMENTANEA_S` e `INACTIVIDAD_MODO_PRUEBA_S` en `server.py`.
- El diálogo de modo prueba reutiliza `DialogoConfirmacion` con el texto de §6.1.
- `GET /io/channels` exige técnico o ingeniero (admin recibe 403), siguiendo D-ES-11.
- Las pantallas usan `enviar` síncrono, como Mantenimiento; con el backend caído, cada tick de 1 s puede esperar hasta el plazo de 5 s. Conviene pasarlo a una operación asíncrona si molesta en el banco.
- **Riesgo aceptado (ES-09):** con R-02 retirado se puede abrir una puerta con la cámara presurizada o accionar vapor con puertas abiertas. Falta registrarlo en el fichero de gestión de riesgos.

## Pendiente de la otra tarea
- Falta verificar P-ES-1 (finales de carrera de las puertas automáticas); sin ellos, un motor en ON sostenido no tiene freno.
- Falta una prueba de banco de las salidas momentáneas con hardware real.
- `test_intro_arranque_qml::test_arranque_normal_dura_3_5_s...` falló una vez en la línea base y pasó en la corrida completa: es intermitente y no tiene relación con este trabajo.

## Cómo revertir
Todo está sin commit. Archivos nuevos: `core/runtime/io_names.py`, `ui_qml/domain/entradas_salidas.py`, `ui_qml/controllers/entradas_salidas_controller.py`, las dos pantallas QML y seis archivos `tests/test_es_*.py` / `test_io_names.py` / `test_io_momentaneas_keepalive.py`. Archivos modificados: `backend/server.py`, `config/calibration_writer.py` (parámetro `nota`), `ui_qml/sesion_backend.py`, `ui_qml/controllers/__init__.py`, `ui_qml/domain/permisos_opciones.py`, `i18n/es.json` y `en.json` (bloque `io`), y las pruebas `test_io_endpoints.py`, `test_io_test_mode_endpoints.py`, `test_backend_calibration_endpoints.py` y `test_i18n_linea_base.py`. Los archivos de la otra sesión (`Opciones.qml`, `Login.qml`, etc.) no se tocaron. `i18n/es.json` y `en.json` ya tenían cambios de la otra sesión antes de empezar; ahí solo se añadió el bloque `io`, así que para esos dos archivos hay que deshacer a mano ese bloque y no usar `git checkout`.
