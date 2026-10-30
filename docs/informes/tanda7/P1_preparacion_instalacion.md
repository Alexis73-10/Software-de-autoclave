# P1 — Preparación de la instalación del 22-oct (tanda 7)

Rama: `tanda-7-p1`, creada desde `e8e42d7`. Revisé el flujo de mañana de punta a punta con el backend doble (TestClient), con QML offscreen y simulando el build congelado. No usé hardware ni abrí puertos COM.

## Resumen
Encontré y corregí **cinco fallas que habrían estorbado la instalación de mañana**. Todas tienen prueba que falla antes de la corrección:

1. **Modo prueba (E/S): el vigilante de la sesión dueña moría a los pocos segundos.** En `server.py`, `from datetime import time` tapaba el módulo `time`, y el hilo caía en `time.sleep` tras la primera pasada. Consecuencia: una sesión dueña vencida o cerrada ya no sacaba al equipo del modo prueba.
2. **E/S: la salida `aire_atmosferico_camara` respondía 404 y no se movía.** El nombre del YAML no pasaba por el alias de la errata `aire_admosferico_camara`.
3. **E/S: las salidas momentáneas (puertas, bomba de vacío) se cortaban a los 1-2 s, y un toque podía perderse.** El Repeater recreaba todas las tarjetas en cada refresco de 1 s.
4. **Calibración: la sonda de Referencia no se podía calibrar desde la pantalla táctil.** `/calibration/temperature/temp_referencia` daba 404 (alias de `temp_ref`).
5. **Arranque: la intro quedaba trabada para siempre si el backend tardaba más de 20 s.** Pasa, por ejemplo, en el primer arranque del `.exe` con antivirus, o con la espera de la tarjeta (15 s) más la construcción del control.

Además:
- U4 en E/S: sin tarjeta, la tarjeta del sensor ya no dice "revise el cableado" ni "ADC undefined".
- Apagar equipo: si Windows rechaza `shutdown`, el motivo queda en el log.
- Pruebas nuevas de cobertura, que no encontraron fallas:
  - rutas de datos del build instalado y portátil, con persistencia tras reinicio y tras actualización;
  - lanzador sin perfil: asistente y luego arranque;
  - primer usuario en una base nueva.
- `docs/instalacion/LEEME_INSTALACION.md`: la lista de comprobación para Cristian.

## Commits
| Hash | Asunto |
|---|---|
| 6479f65 | fix(backend): el vigilante del modo prueba moría tras la primera pasada |
| 3f5b2d3 | fix(io): la salida aire_atmosferico_camara no se podía accionar en modo prueba |
| 62ad00c | fix(ui_qml): E/S no recrea las tarjetas en cada refresco de 1 s |
| a4756c1 | fix(ui_qml): E/S sin tarjeta no culpa al cableado del sensor ni muestra 'ADC undefined' |
| 00e943d | fix(ui_qml): la intro ya no queda trabada si el backend tarda más de 20 s |
| f61fc64 | test(p1): rutas de datos del build instalado y portátil… |
| 023b023 | fix(backend): Apagar equipo deja en el log el rechazo de Windows; prueba del primer arranque |
| 21c2d23 | test(p1): primer ingreso en base nueva |
| 159a95c | fix(calibracion): la sonda de referencia no se podía calibrar desde la pantalla QML |
| a9b49ba | fix(p1): correcciones de la revisión (SAF-01/02, TMG-01/03/06) |
| 7634ec0 | docs(instalacion): LEEME_INSTALACION.md |

## Archivos modificados
- `src/autoclave/backend/server.py`:
  - `dt_time` en lugar de `time` de `datetime`;
  - alias en `PATCH /io/test/output`;
  - clave canónica en `GET`/`PATCH /calibration` y en `/restaurar`;
  - `_apagar_windows` con registro del rechazo y decodificación OEM.
- `src/autoclave/core/runtime/io_names.py`: `clave_estado()` pública; el alias `_clave_estado` se conserva.
- `src/autoclave/ui_qml/qml/Pantallas/OpcionesEntradasSalidas.qml`:
  - Repeaters de salidas y sensores con modelo entero y datos por índice;
  - salida momentánea fijada al pulsar;
  - texto sin enlace.
- `src/autoclave/ui_qml/qml/Pantallas/IntroArranque.qml`: el fallo por plazo sin progreso se retira solo con un avance real.
- Pruebas nuevas:
  - `tests/test_p1_instalacion_manana.py`
  - `tests/test_p1_salidas_momentaneas_qml.py`
  - `tests/test_p1_rutas_build_congelado.py`
  - `tests/test_p1_lanzador_primer_arranque.py`
- Pruebas ampliadas: `tests/test_intro_arranque_qml.py` (2 escenarios).
- `docs/instalacion/LEEME_INSTALACION.md` (nuevo).

**Archivos de choque:** no toqué `i18n/es.json` ni `en.json`, `Instalacion.qml`, `puente_instalacion.py`, `installation/` ni `db_manager.py`. No hay textos visibles nuevos: el aviso sin enlace reutiliza la clave existente `io.ui.enlace_perdido`.

## Pruebas
- **Antes:** línea base de la tanda, 5020 passed / 2 skipped / 3 xfailed. Todas las afectadas estaban en verde, pero no cubrían estos casos.
- **Después (suite completa en la rama):** 5081 passed, 2 skipped, 3 xfailed (18 min 46 s; corrida por la sesión principal el 22-oct, 06:05).
- **Aviso para quien corra pruebas en worktrees:** el paquete `autoclave` está instalado en modo editable apuntando a la **carpeta principal**. Sin `PYTHONPATH=<worktree>/src`, pytest prueba el código de la carpeta principal, no el del worktree. Todas las corridas de este informe usaron el `PYTHONPATH` del worktree.

## Revisores
Corrí `safety-reviewer`, `timing-auditor` y `sensor-role-auditor`. Ninguno dejó hallazgos Críticos ni Altos. Esto hice con el resto:
- **Corregidos (a9b49ba):**
  - SAF-01: momentánea fijada al pulsar; apagado al destruirse la tarjeta; no se renueva con `libre` en falso.
  - SAF-02 / TMG-01 (Medio): un retroceso no retira el fallo de la intro.
  - TMG-03: no se renueva tras un rechazo.
  - TMG-06: decodificación OEM de la salida de `shutdown`.
- **Pendientes (Bajos), sin corregir:**
  - TMG-02: renovación síncrona en el hilo de la GUI. Falla hacia apagado.
  - TMG-04: `time.sleep` fuera del `try` del vigilante. Ya lo cubre la prueba de varias pasadas.
  - TMG-05: el modo prueba no se cierra al iniciar el apagado.
  - SEN-02: `temp_drenaje_camara` se omite sin aviso en el log.
  - SEN-03: la auditoría de `/io/test/output` usa el nombre del YAML y la de calibración la clave canónica.
  - SEN-04: la QML podría mandar `estado_key`.
- **SEN-01 (Medio), no aplica mañana:** en `solids_liquids.yaml` la segunda sonda se llama `temp_camara_2` y no tiene alias hacia `temp_2_camara`, así que no se ve en la QML. Es el caso LIQ-01 ya conocido. Agregar el alias es trivial; lo dejo para quien retome Líquidos.

## DECISIONES SIN CONFIRMAR
1. **La intro retira el fallo "sin progreso" cuando el progreso del backend vuelve a avanzar** (00e943d, a9b49ba).
   - *Motivo:* la regla 4 de `planeacion_animacion_arranque.md` lo hacía permanente. Con eso, un backend que tardaba más de 20 s en responder la primera vez dejaba la intro trabada hasta reiniciar.
   - *Qué no cambia:* el fallo bloqueante que publica el backend sigue siendo permanente, y la intro no habilita nada.
   - *Alternativa:* subir `plazoSinProgresoMs`.
   - *Cómo revertir:* `git revert 00e943d a9b49ba`. a9b49ba trae también las otras correcciones de la revisión: revierta solo el bloque de `IntroArranque.qml`.
2. **El backend resuelve los alias de nombres del YAML** (`clave_estado`) en el PATCH de salidas y en calibración, en vez de cambiar la QML para que mande `estado_key`.
   - *Motivo:* es más robusto y no toca la QML, que M1 también edita en otras pantallas.
   - *Efecto en la bitácora:* la entidad de calibración queda con el nombre canónico (`temperature/temp_ref`), el mismo que usa el menú PySide.
   - *Cómo revertir:* `git revert 3f5b2d3 159a95c`.

## PREGUNTAS PARA CRISTIAN
1. **`io_enabled` de `ACV-2026-001.yaml`.** Hoy no incluye:
   - en salidas: `descompresion_lenta`, `vapor_caldera`, `aire_comprimido_chaqueta`, `aire_comprimido_camara`, `agua_chaqueta` ni `buzer_alarma`;
   - en temperatura: **`temp_2_camara`**;
   - en entradas: `suministro_electrico`.

   El asistente pide la sonda Cámara 2, pero la pantalla de E/S no la muestra ni deja calibrarla. Tampoco se puede probar `descompresion_lenta` desde E/S. No lo cambié porque la spec (ES-02) lo da como configuración del equipo. ¿Se agregan al YAML del repo? El rodeo para mañana está en el LEEME §6.1.
2. **Calibración que viaja con el programa.** `config/calibration.yaml` lleva valores de banco (presión de cámara 1,364 / −75,35; temperatura de cámara 1,079 / −6,16; presión de canales 1 a 5 ≠ neutro), y en un equipo nuevo se siembra como `data\calibration.yaml`. ¿Las compilaciones de entrega deben llevar la calibración de usuario neutra? Para mañana el LEEME indica "Restaurar por defecto" si no cuadra.
3. **Modo prueba y `aire_atmosferico_camara`.** Ahora sí se puede activar con la cámara presurizada (D-ES-15 permite todas las salidas en modo prueba). ¿Está analizado el riesgo de salida de vapor por esa vía? (pregunta del safety-reviewer)
4. **Un solo monitor.** El lanzador abre siempre las dos pantallas. No lo hago automático (detectar monitores al arrancar puede perder la pantalla 2 si el monitor despierta tarde). ¿Hace falta?
5. **Apagar equipo cuando Windows rechaza el apagado.** El control queda detenido y el PC encendido, y solo queda la línea del log. ¿Se avisa en pantalla?
6. **Texto final del asistente.** Dice "Reinicie el software para continuar", pero el programa sigue solo con Continuar. No lo cambié porque M1 está tocando el asistente y ese archivo es de choque. ¿Se ajusta en M1?

## PROBLEMAS CONOCIDOS PARA MAÑANA (con rodeo)
| Problema | Rodeo |
|---|---|
| Canales fuera de `io_enabled` (Cámara 2, `descompresion_lenta`, …) no aparecen en E/S | Con Autoclave cerrado, agregarlos a `C:\ProgramData\Especifika\Autoclave\programa\autoclave\config\instances\ACV-2026-001.yaml` (LEEME §6.1) |
| La calibración inicial no es neutra | "Restaurar por defecto" en el sensor antes de calibrar (LEEME §6.2) |
| Presión: los puntos deben quedar a ≥ 50 kPa uno del otro (la atmósfera de Bogotá, ~75 kPa abs, y 120 kPa se rechazan) | Punto alto ≥ 125 kPa abs. Cómo obtenerlo: verificar en sitio |
| Calibrar exige la tarjeta conectada en la pantalla táctil | Menú de ajustes `Autoclave.exe --rol ajustes` (valores escritos). El engrane ya no lo abre |
| Con el paro de emergencia activo, OPCIONES no abre | Liberar el paro o cablearlo cerrado |
| Un solo monitor: la ventana de la puerta 2 tapa la de la puerta 1 | Acceso directo con `--una-pantalla` |
| Reloj adelantado al instalar → ARR_RELOJ al corregirlo | Ajustar la hora antes del asistente; si ya pasó, reinstalar el perfil (LEEME §7) |
| Compilación A sin las correcciones P1 | Rodeos de la A en el LEEME ("A frente a B") |

## Comprobaciones manuales para Cristian (en sitio)
- Tras el asistente, pulsar **Continuar** y ver que el programa siga solo hasta la pantalla principal.
- Con la tarjeta desconectada: ver "tarjeta desconectada" sin paro de emergencia; en E/S, sensores con "Sin enlace con la tarjeta de E/S".
- Mantener pulsado "abrir puerta" más de 3 s en modo prueba: la puerta debe moverse todo ese tiempo. Al soltar, se detiene. *(Solo con la B o la rama P1 unida.)*
- Accionar `aire_atmosferico_camara` y calibrar la Referencia desde la pantalla táctil *(B)*.
- Probar los caminos de salida del modo prueba (LEEME §6.1, punto 4).
- Calibrar un sensor, cerrar, abrir y ver la misma ganancia y offset.
- Calibrar la presión atmosférica con una puerta abierta.
- Revisar la Información del sistema.
- Apagar el equipo desde el software y comprobar que Windows se apaga.

## Nota
Al depurar una prueba creé por error la carpeta `C:\tmpx2` (copia de `config/` y `cycles/`, sin datos sensibles). No pude borrarla: el permiso fue denegado. Se puede eliminar a mano.
