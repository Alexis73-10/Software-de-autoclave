# T7 — E5: interfaz de seguridad

Instrucción: tanda 2026-10-14 §2 T7; `planeacion_fin_de_ciclo_y_puertas.md` §5, §15 y §16; I18N-28.

## 1. Qué se hizo

- **Avisos de seguridad sobre todas las pantallas** (`Componentes/AvisosSeguridad.qml`, montado en `Main.qml` arriba, sobre el `StackView`; no se muestra durante la intro de arranque). Es PROVISIONAL, sin diseño del diseñador:
  - paro activo: "PARO DE EMERGENCIA — NO ABRIR";
  - cámara no segura: "NO ABRIR" con el motivo que da el backend, en cualquier estado (§5);
  - paro liberado con el estado seguro pendiente: "Paro liberado. Verifique que no hay fuga…" y el botón **"Confirmar y llevar a estado seguro"** (cualquier operador, sin rol, §15.2); con el ciclo aún pendiente, la confirmación es el CONFIRMAR de la pantalla de ciclo (fusionadas, T5);
  - estado seguro en curso: aviso informativo;
  - **MODO PRUEBA ACTIVO — los ciclos no son válidos para carga estéril** (`sistema.modo_prueba`, I18N-28).
- **Puente** (`UiBridge`): `noAbrir`, `noAbrirMotivo`, `modoPrueba`, `paroActivo`, `estadoSeguroActivo` y `estadoSeguroRequiereConfirmacion`, leídos del caché de `/status`. Sin conexión o sin dato, `noAbrir = true` (falla cerrada, igual que el backend).
- **Comandos** (`bridge/comandos_sistema.py`): `confirmarEstadoSeguro()` (`POST /safe-state/confirm`) y `apagarEquipo()` (`POST /system/shutdown`, solo puerta 1). Corren fuera del hilo de la GUI; si el backend rechaza, se muestra el motivo.
- **Apagar equipo (§16, D-20)**:
  - `POST /system/shutdown` exige `ventana="principal"` (si no, 403), estado distinto de CICLO, ningún estado seguro en curso y cámara segura con datos vigentes; si no, 409 con el motivo.
  - Secuencia, en un hilo propio: `control_loop.stop()` (detiene el lazo, luego ALL_OFF y cierre del puerto serial), cierre del historial de alarmas, `DbManager.close()` y `shutdown /s /t 0`. El apagado real de Windows **solo** corre en el ejecutable empaquetado (`sys.frozen`) o con `AUTOCLAVE_APAGADO_REAL=1`: nunca desde las pruebas ni en desarrollo.
  - Queda `apagar_equipo` en `audit_log`.
  - UI: botón "Apagar equipo" en el panel de Información del sistema, visible solo en la ventana principal (puerta 1), con diálogo de confirmación.
- **Barra inferior del login uniforme**: Login usa la misma `BarraInferiorMenu` del Menú Principal y de Opciones (Salir deshabilitado sin sesión, Inicio activo) con la versión real (`app.version`), en vez de la `BarraInferior` con "V: 1.0" fija.
- **Versión e ID de tarjeta**: verificado que solo están en Información del sistema (`info_equipo.py`, filas `version_tarjeta`, `id_tarjeta` y emparejamiento). Sin cambios.

## 2. Pruebas

`test_t7_apagar_equipo.py` (7), `test_t7_ui_seguridad.py` (14) y `test_t7_avisos_qml.py` (renderizado offscreen de las franjas, sin avisos de QML). Ajustadas: `test_ui_bridge` (lectura `get_campo`) y `test_cancelacion_ciclo_en_curso_qml` (hay un segundo diálogo de confirmación, el de apagar). Suite completa: ver `estado.md`.

## 3. DECISIONES SIN CONFIRMAR

- D-T7-1: los avisos van como franjas arriba, sobre el encabezado de cada pantalla (sin diseño). Alternativa: integrarlos en cada pantalla.
- D-T7-2: la ventana principal es la de la puerta 1.
- D-T7-3: el botón "Apagar equipo" va en Información del sistema. No exige rol (§16 no lo pide), solo la confirmación del software.
- D-T7-4: el apagado de Windows exige el ejecutable congelado o `AUTOCLAVE_APAGADO_REAL=1`. Si en el equipo se corre desde Python, hay que fijar esa variable.
- D-T7-5: "barra inferior del login uniforme" se interpretó como usar la misma barra del Menú Principal y de Opciones. CambioClave sigue con la anterior.

## 4. PENDIENTES

- Diseño final de los avisos y del botón de apagar (diseñador).
- Verificación visual en la pantalla real (no se ejecutó la UI completa).

## 5. Revisores (resultado)

**timing-auditor**: 0 hallazgos críticos, 1 alto, 3 medios y 3 bajos. **safety-reviewer**: 0 críticos, 0 altos, 2 medios y 3 bajos.

Corregidos:
- **TMG-01 (alto) / SAF-01 (medio)**: había una carrera entre la validación y el apagado. Un `START_CICLO` pendiente o recién llegado podía pasar a CICLO y abrir un ciclo, que luego quedaba cortado sin cierre. Corrección:
  - El endpoint llama a `ControlLoop.iniciar_apagado()` dentro del mismo bloque del guard, sin soltar `_sm_lock`. Ese método marca `apagando`, borra `START_CICLO` y detiene el lazo.
  - Un tick que ya esperaba el lock sale sin tocar la máquina de estados.
  - `/cycle/start` responde 409 `apagado_en_curso`.
- **TMG-05 / TMG-06 (bajos)**:
  - Un segundo apagado se rechaza con 409 `apagado_en_curso`.
  - Tras un apagado aceptado, el botón queda deshabilitado.
- **TMG-02 (medio)**: el apagado usa un timeout de 10 s. Sin respuesta HTTP, la UI muestra "el apagado puede estar en curso" y no lo presenta como rechazo.
- **SAF-02 (medio)**: el motivo del rechazo se toma de `detail`, el campo que devuelve `RechazoApi`. Antes la pantalla mostraba el texto crudo del error HTTP.
- **SAF-05 (bajo)**: con el modo prueba activo, el apagado se rechaza (409 `modo_prueba_activo`).
- **TMG-04 (medio)**: en `stop()`, si el ALL_OFF no se confirma se reintenta una vez y se registra en el log. También queda en el log si el hilo del lazo no terminó en 3 s. El respaldo final sigue siendo el watchdog de la tarjeta.

Pendientes (no son altos ni críticos):
- TMG-03: después de `db.close()`, las rutas que usan la BD responden 500 en lugar de 503. Solo pasa en desarrollo, sin apagado real.
- TMG-07: el refresco del puente mezcla varias lecturas de caché, y `/status` no indica "apagando".
- SAF-03: "solo ventana principal" lo declara el propio cliente; es una restricción de la interfaz, no del servidor.
- SAF-04: la cámara segura para apagar se evalúa con una sola lectura, sin debounce de 3.
- Preguntas de los revisores:
  - ¿Queda alguna fuente de vapor o calefacción alimentada por hardware después de apagar?
  - ¿El apagado debe exigir las puertas en reposo?

## 6. Comprobaciones manuales de Cristian

- Con la cámara caliente, debe verse "NO ABRIR" con el motivo en ambas pantallas.
- Pulsar y soltar el paro fuera de ciclo, con el estado seguro en curso: debe aparecer el botón "Confirmar y llevar a estado seguro".
- Activar el modo prueba: debe verse la franja amarilla de modo prueba en ambas pantallas.
- "Apagar equipo" desde la puerta 1, con la cámara segura: el PC se apaga (solo con el ejecutable o con `AUTOCLAVE_APAGADO_REAL=1`). Con la cámara caliente se rechaza y se muestra el motivo. En la puerta 2 el botón no aparece.
