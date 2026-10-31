# Informe — Fase B, primer paso: arranque del backend por etapas y `GET /arranque`

Fecha: 12-oct-2026 · Sin commit. Implementa la propuesta aprobada (`propuesta_fase_b_arranque_backend.md`, D-1 a D-8 aprobadas).

## Qué se hizo

| Archivo | Cambio |
|---|---|
| `backend/arranque/registro.py` | **Nuevo.** `RegistroArranque` con lock. Contiene las 9 etapas con los pesos provisionales de §7 y su origen. Solo avanza (`ok`, `degradado` y `fallo` son finales). `instantanea()` devuelve el contrato §5. `terminado` excluye la etapa 9 (UI). Cada transición se registra en el log con su duración. |
| `backend/arranque/secuencia.py` | **Nuevo.** `ejecutar_arranque()` recorre las etapas 1 a 8 y define los códigos `ARR_*`. Un fallo bloqueante en las etapas 1, 4 o 5 detiene la secuencia sin abrir el serial. La etapa 7 construye el control, avisa que el contexto es operable y espera las E/S. A los 15 s sin E/S anota `ARR_SIN_ES` y sigue reintentando. La etapa 8 es provisional: `ok` con aviso en el log. |
| `backend/arranque/sin_bd.py` | **Nuevo.** `BdNoDisponible`, provisional hasta el modo sin BD: cualquier llamada lanza `BdNoDisponibleError`. |
| `backend/context.py` | El constructor ya no hace E/S: solo crea `estado` y `alarm_manager`, el resto queda en `None`. La construcción pasa a métodos por etapa: `verificar_instalacion`, `cargar_configuracion`, `verificar_calibracion`, `abrir_base_datos`, `construir_control` (registra el aviso de paro antes de `start()`) y `es_conectada`. `_validar_configuracion` ahora devuelve el motivo y solo bloquea el loop si ya existe. Se conservan los cambios sin commit que ya tenía el archivo. |
| `backend/server.py` | `registro_arranque`, `preparar_arranque()` e `iniciar_arranque()`. Middleware que responde 503 (`arranque_en_curso` / `arranque_fallido`) en todo salvo `/arranque` y `/ui/activity`. `GET /arranque` sin token. `BdNoDisponibleError` se traduce en 503 `sin_base_de_datos`. `/cycle/start` responde 409 `sin_base_de_datos` sin BD. El registro del aviso de paro salió del import. El apagado tolera `control_loop is None`. |
| `backend/main.py` | Usa `uvicorn.Server`. Activa la compuerta antes de abrir el puerto y dispara el arranque solo cuando `server.started` es verdadero (`arrancar_cuando_escuche`). |
| `devices/factory/factory.py` | `build_hardware` se divide en `build_serial` y `build_doors_cfg`. `build_hardware` sigue igual para quien ya lo usa. |
| `core/managers/cycle_manager.py` | Lista `errores_carga` con los JSON de ciclo que no cargaron. Se usa para degradar la etapa 4. |
| `docs/catalogo_alarmas.md` | Alarma `OPERANDO_SIN_BD`, `CONFIGURACION_INVALIDA` actualizada y nueva tabla §2.1 de códigos de arranque. |
| `tests/test_backend_autenticacion.py` | 3 pruebas ajustadas: el host fijo ahora se verifica con `uvicorn.Server`, y el aviso de paro se toma de `srv._prueba_cancelada_por_paro` en vez de la llamada en el import. |
| `tests/test_registro_arranque.py`, `test_secuencia_arranque.py`, `test_endpoint_arranque.py` | **Nuevos**, 58 pruebas. |

Un agregado sobre la propuesta: el código `ARR_RELOJ` (etapa 1, reloj alterado). `get_installation_profile()` ya lanza `ClockTamperedError` y §5 lo clasifica como bloqueante.

## Verificación

- Las 3 pruebas nuevas: **58 pasan**.
- Las pruebas de backend que ya existían, en los archivos que importan `server`, `BackendContext`, `build_hardware` o `CycleManager`: **411 pasan**. Solo cambiaron las 3 pruebas mencionadas.
- Suite completa: 2551 pasan, 19 fallan y hay 14 errores. **Los 33 fallos no vienen de este cambio.** Alguien renombró `qml/Pantallas/Arranque.qml` a `Reposo.qml` (ARR-01), pero `Main.qml:308` sigue instanciando `Arranque`, así que `Main.qml` no carga. Además, 7 archivos de prueba buscan el tipo `Arranque_QML`: `test_intro_arranque_qml`, `test_main_menu_principal_qml`, `test_navegacion_ciclo_en_curso`, `test_navegacion_sesion_qml`, `test_opciones_qml`, `test_reconocer_falla` y `test_ui_qml_app`. Lo comprobé cambiando `Main.qml` de forma temporal: lo que sigue fallando es esa búsqueda de tipo. `Main.qml` quedó revertido y no toqué la UI.
- `tests/test_adenda_estados.py` sigue sin recolectar por el error previo `TEMPERATURE_PROBE_KEYS` en `installation/profile.py`, ajeno a este cambio.

## Pendiente
1. **Terminar el renombrado ARR-01** en `Main.qml` y en las 7 pruebas. No es de este paso; espera tu orden.
2. **Prueba manual en el equipo.** Arrancar `python -m autoclave.backend.main` y consultar `GET /arranque` mientras avanza: con y sin tarjeta (ver `ARR_SIN_ES` a los 15 s), sin BD y con el puerto 8000 ocupado (el serial no debe abrirse).
3. **Siguientes pasos del §11:** etapas 1 y 2 del lanzador, `ProgresoArranqueReal`, textos de las 9 etapas, verificación real de sensores (etapa 8), modo sin BD (§7) y medición de pesos.
