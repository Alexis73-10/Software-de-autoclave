# T3 — Sensores de temperatura del ciclo (backend)

Instrucción: tanda 2026-10-14 §1.1 y §2 T3. Base: `planeacion_sensores_ciclo.md` rev. 2 (RS-01 a RS-10), con los cambios de la tanda, que prevalecen.

## 1. Qué se hizo

**Módulo central** `core/runtime/sensores_ciclo.py`:
- Catálogo: `temp_camara` "Cámara 1", `temp_2_camara` "Cámara 2", `temp_ref` "Referencia" (solo ubicación física); tipo `camara`/`referencia`.
- Roles por programa: exactamente 1 `principal`, 0 a 2 `referencia`, el resto `no_en_uso` (`errores_asignacion`).
- Accesor `sensor_principal(programa)` (más `sensores_referencia`, `sensores_en_uso`, `temp_principal`). Con asignación inválida devuelve `temp_camara`, pero el programa no puede iniciar.
- Declaración por la instalación: `sonda_instalada` del perfil (A-2) y, para `temp_2_camara`, una clase con `has_liquid_sensor` (`mesa_b_lab`, `piso_lab`); sin perfil, los tres (C-6).
- Estados `disponible` / `sin_senal` / `no_instalado`; `verificar_inicio` (RS-06); `f0_disponible` (clase de laboratorio); `canonica` (JSON con claves ordenadas).

**Programas**: `Cycle.sensores` se carga de `cycle_temperature_sensors`, con migración perezosa del formato antiguo (`{"1": ..., "2": ...}` o campo ausente = asignación de fábrica, con advertencia en el log). `Cycle.copia()` copia la asignación: es la instantánea del ciclo (RS-03.4). Los 5 JSON de `cycles/` quedan en el formato nuevo con la asignación de fábrica (Principal = `temp_camara`).

**Dónde se usa el Principal** (del programa del ciclo en curso o, fuera de CICLO, del seleccionado; sin ninguno, `temp_camara`):

| Uso | Archivo |
|---|---|
| Control de vapor, saturación final, ventana de estabilidad | `calentamiento.py` |
| Control y las 4 fallas de temperatura | `esterilizacion.py` |
| Enfriamiento de los modos 4/5 | `descompresion.py` |
| Temperatura del protocolo de fallo | `protocolo_fallo.py` |
| Apertura automática | `ciclo.py` |
| Interlock de apertura de puertas (temperatura de apertura, cámara segura) | `ser_puertas.py` (provider `programa_para_sensores`) |
| F0 | `control_loop.py` |
| Ticket y temperatura final | `cycle_logger.py` |
| `/status.sensors.principal` | `server.py` |

"NO ABRIR" y `camara_segura` en `/status` son de T4 y usarán el mismo provider.

**Referencias** (tanda §1.1):
- (a) Entrada a esterilización: la ventana `tiempo_estable_preesterilizacion` de CALENTAMIENTO exige además que cada Referencia esté en la consigna (`T_ref >= temperatura_calentamiento`). DECISIÓN SIN CONFIRMAR: solo cota inferior (la Referencia puede ir más caliente sin bloquear), porque la regla es que no se comparan con el Principal ni entre sí.
- (b) En esterilización, una Referencia fuera de `[t_est − brecha_error_temperatura, t_est + rango_temperatura_ester]` con debounce de 3 lecturas activa **CIC-09 "Uniformidad térmica fuera de rango"** (AVISO, no bloqueante, una vez por sensor y fase; queda en el historial). No falla el ciclo; el conteo sigue con el Principal, que falla por sí mismo si sale de rango.

**Vigilancia**:
- En CICLO, `SENSOR_AUSENTE` (SEN-02 → FALLO) vigila los sensores en uso del programa en curso; se retiró la vigilancia fija de `temp_camara` (antiguo S-8). Un sensor `no_en_uso` no genera nada.
- Una Referencia caída también da `SENSOR_AUSENTE` → FALLO (DECISIÓN SIN CONFIRMAR de la propia tanda).
- En PREPARACION/PREPARADO, los tres sensores del ciclo, si están declarados y sin lectura (None, no finito o 0), dan **SEN-03** (AVISO, no bloqueante). `temp_drenaje` y las presiones siguen bloqueando con SEN-01. El TypeError por `None` en las bandas (OPC-29) ya estaba corregido desde E0 con `lectura_valida`.
- RS-06: `POST /cycle/start` responde 409 `ASIGNACION_SENSORES_INVALIDA` o `SENSOR_NO_DISPONIBLE`; la máquina de estados repite la verificación antes de pasar a CICLO (defensa en profundidad).

**F0**: solo en equipos de laboratorio (`has_liquid_sensor`, clases `*_lab`; no se creó flag nuevo porque coincide). Fuera de lab: el lazo no acumula, esterilización no exige F0 y `PATCH /cycle/parameter` rechaza activarlo con 422 `f0_no_disponible`. Todos los programas lo traen desactivado.

**Endpoints**:
- `GET /cycle/sensors?programa=N` (N = `cycle_number`): id, nombre, tipo, estado, lectura, rol; los `no_instalado` solo si tienen rol activo; además `errores`, `formato_antiguo`, `editable`.
- `PUT /cycle/sensor-roles`: cuerpo `{programa, asignacion, asignacion_anterior_esperada}`. Todo o nada; 422 `ASIGNACION_INVALIDA`, 422 `SENSOR_NO_DISPONIBLE` (invariante 4), 409 `asignacion_desfasada`, 409 `programa_de_fabrica`; técnico fuera de CICLO, ingeniero también en CICLO; escritura atómica del JSON (`.tmp` + `fsync` + `os.replace`); auditoría `ROLES_SENSOR` con valores anterior y nuevo en JSON canónico.

**Permisos** (C-5, §1.1): asignar roles y calibrar = técnico e ingeniero. `PATCH /calibration` pasa de "solo ingeniero" a técnico (fuera de CICLO) e ingeniero; la vista PySide de calibración permite `tecnico` e `ingeniero` (se quitó `admin`). Biomédico no existe como rol válido.

**Registro (RS-08, C-7)**: migración de BD **v2**: `ciclos.asignacion_sensores`, `ciclos.f0_final`, `ciclos.numero_programa`, `lecturas.temp_principal`, `lecturas_grafica.temp_2_camara`. La fila del ticket imprime la temperatura del Principal; la columna `lecturas.temp_camara` sigue guardando la lectura cruda de `temp_camara`.

**i18n**: `sensores_ciclo.*` y los tres códigos de validación en es/en (registrados como sin revisar).

**Riesgos**: se creó `docs/riesgos/registro_riesgos.md` (no existía archivo ISO 14971) con HAZ-SEN-01 (Principal = sonda fría → "NO ABRIR" optimista, sin advertencia en UI, por decisión de Cristian), HAZ-SEN-02 a 04 y HAZ-VAP-01 (de T2).

## 2. Pruebas

- Nuevas: `test_t3_sensores_ciclo.py` (72) y `test_t3_endpoints_sensores.py` (21). Las del módulo central y de endpoints se vieron fallar antes (ImportError / 404).
- Ajustadas por cambio de comportamiento aprobado: `test_e0_lecturas_invalidas` y `test_adenda_estados` (el bloqueo por sonda caída queda solo para `temp_drenaje`), `test_control_loop_f0` (F0 con el Principal, no el mínimo; F0 no acumula fuera de lab), `test_ciclo_alarmas_fallo` (nombre "Cámara 1"), `test_db_audit_log` (esquema v2), `test_cycle_logger_printer` (firma de `cerrar_ciclo`), `test_backend_autenticacion` y `test_calibracion_sensor_view` (técnico calibra), `test_t17_copia_programa` (el inicio exige lectura del Principal), `test_alarmas_catalogo` (SEN-03 y CIC-09).
- Suite completa: ver `estado.md`.

## 3. Revisores

Ver §6.

## 4. DECISIONES SIN CONFIRMAR

- D-T3-1: Referencias en consigna = solo cota inferior (§1 (a)).
- D-T3-2: uniformidad térmica en esterilización con el rango de falla del Principal (`brecha_error_temperatura` / `rango_temperatura_ester`) como rango de las Referencias.
- D-T3-3: SEN-03 nuevo (AVISO no bloqueante) en vez de cambiar el nivel de SEN-01, que sigue bloqueando para presiones y drenaje.
- D-T3-4: sin perfil se declaran los tres sensores y F0 está disponible (compatibilidad con pruebas y arranques sin perfil; en producción el arranque exige perfil).
- D-T3-5: la migración de BD toma la versión 2, que estaba reservada para `planeacion_backend_parametros.md`; esa pasa a v3 o posterior (las versiones son secuenciales y no admiten huecos).
- D-T3-6: los nombres legibles del catálogo de alarmas para los tres sensores pasan a "Cámara 1", "Cámara 2", "Referencia".
- D-T3-7: `GET /cycle/sensors` y `PUT /cycle/sensor-roles` identifican el programa por `cycle_number`.

## 5. PENDIENTES

- Pantalla de roles de sensor y la de ciclo con Principal + Referencias (C-2): T12/T7.
- El ticket no identifica qué sensor fue el Principal (cambio visible del formato: requiere aprobación, RS-08.5). Queda registrado en `ciclos.asignacion_sensores`.
- Los YAML `config/instances` y `config/models` no se tocaron (OPC-31, ningún código los lee).
- La rama `feature/roles-sensor-temperatura` no se integró (solo referencia), como pide la tanda.

## 6. Revisores (resultado)

`safety-reviewer`: 1 Alto, corregido.
- **SAF-01 (Alto)**: fuera de CICLO, el interlock tomaba el Principal del programa *seleccionado*; seleccionar otro programa (o cambiar roles) tras un ciclo podía pasar a medir con una sonda fría con la carga caliente. **Corrección**: `temp_seguridad` = máximo de los Principales del programa seleccionado y del último ciclo ejecutado (este último hasta que la cámara sea segura; se conserva en `ControlLoop._programa_ultimo_ciclo`, sobrevive a `set_active_cycle`); si falta una lectura, o el Principal no está declarado por la instalación (SAF-07), no es segura; si el provider falla, no es segura (SAF-08). Aplica al interlock de puertas y a `camara_segura`. Registrado como HAZ-SEN-05. DECISIÓN SIN CONFIRMAR: se aparta de la letra de §1.1 ("Principal del programa seleccionado") solo en ese tramo, del lado seguro.
- Corregidos (Medio/Bajo): SAF-02 (el registro de riesgos decía "hardware y software"; ahora "mecánico, D-02, no verificable por software"); SAF-03 (b) (la calibración del técnico re-verifica que no haya ciclo antes de recargar); SAF-04 (CIC-09 deja "Aviso: Uniformidad térmica fuera de rango" en el pie del ticket); SAF-05 (PUT de roles re-verifica estado y rol al fijar la asignación y revierte el archivo); SAF-06 (F0 se rechaza con cualquier valor verdadero; el ticket solo imprime F0 en lab); SAF-09 (0 °C = sin lectura en todos los puntos).
- Pendientes: SAF-03 (a) sin límites de plausibilidad de ganancia/desplazamiento en la calibración (decisión de valores, para Cristian); SAF-10 el rechazo de RS-06 en la máquina de estados no genera alarma (la UI ya recibe el 409 de `/cycle/start`).

`timing-auditor`: sin Crítico ni Alto. Corregidos: TMG-02 (la escritura de `/cycle/parameter` también es atómica: función común `_escribir_json_programa`, borra el `.tmp` si falla, TMG-06); TMG-03 (migración con `BEGIN IMMEDIATE` y `timeout=10` en la conexión SQLite); TMG-04 (= SAF-05); TMG-05 (`/status` lee una sola instantánea de la asignación). Pendientes: TMG-01 (SENSOR_AUSENTE de una Referencia sin debounce: es la regla de la tanda, "mismo flujo"); TMG-07 (auditoría de rechazos con `_lock_archivos` tomado; sin riesgo de interbloqueo); TMG-08 (hueco de F0 en desconexiones < 5 s, previo a T3).

Preguntas abiertas de los revisores para Cristian: ¿`/cycle/select` debe pedir sesión y prohibirse en FALLA?; ¿una Referencia ausente debe abortar (hoy sí, sin debounce)?; la consigna de las Referencias en calentamiento es `temperatura_calentamiento` (vinculada a la de esterilización).

## 7. Comprobaciones manuales de Cristian

- Con el equipo de pruebas (`piso_lab`): `GET /cycle/sensors?programa=2` debe listar Cámara 1, Cámara 2 y Referencia.
- Desconectar Cámara 2 en PREPARADO: aparece "Sensor de temperatura sin señal" y el equipo sigue listo para un programa que no la use.
- Asignar Cámara 2 como Referencia y desconectarla: el inicio del ciclo debe rechazarse con "Un sensor en uso no tiene lectura o no está instalado".
- Ciclo con Referencia colocada en un punto frío: revisar que la entrada a esterilización espere a que la Referencia llegue a la consigna y que, si cae, aparezca la alerta de uniformidad térmica sin abortar.
