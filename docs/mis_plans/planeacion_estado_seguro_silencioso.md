# Estado seguro silencioso por sensor sin lectura (ESS)

Fecha: 2026-10-28. Base: `dev` en 1.0.0-alpha.8 (acb33873). Clase C.
Origen: requisito de Cristian del 26-oct (punto 5.1, "que actúe en silencio sin mostrarse en alarmas, solo se muestran las alertas del sensor"), implementado solo en parte por ESG-01 (tanda 17), y su respuesta del 28-oct.

## 1. Diagnóstico

ESG-01 (ff3bf9d0, 364e2ebb) solo dejó de activar CIC-10 cuando el estado seguro está detenido por la presión de cámara sin lectura. No hubo regresión: el resto nunca se implementó.

Evidencia (foto del 28-oct, 18:54, Preciclo, presión "—"; la campana marca 2):
- "Llevando la cámara a estado seguro": `filaEstadoSeguroEnCurso` en `SeccionEstadoSeguro.qml`.
- "Arranque con la cámara no segura…": `avisoCausaEstadoSeguro`.
- Botón "En curso…" y "NO ABRIR hasta que la cámara esté segura": `botonConfirmarEstadoSeguro` y `notaNoAbrirEnCurso`.
- Nota naranja con el texto largo de presión sin lectura: `avisoEstadoSeguroDetenido`. Lee `estado_seguro.bloqueado_motivo` de `/status`, que sigue incluyendo la presión (ESG-01 solo filtró CIC-10, no `/status`).
- "Sensor de presión de cámara sin lectura" (SEN-06): es la única que debe quedar.

Causas:
- `/status` publica `estado_seguro.detenido_sin_presion` (tanda 17), pero `ui_bridge.py` y el QML no lo leen.
- `filaNoAbrir` (fuera del estado seguro) tampoco distingue el motivo.
- Por V17-s3-02, con la presión perdida CIC-10 toma el siguiente motivo (p. ej. Principal sin lectura). ESG-01 solo cubría la presión.

## 2. Decisiones de Cristian (28-oct)

- D-1. Alcance: todos los sensores que activan o detienen el estado seguro, o que dejan la cámara no segura.
- D-2. A la alarma de cada uno de esos sensores se le agrega "No abrir la puerta", visible en el nombre de la fila.

## 3. Requisitos

### ESS-01 · Inventario (primero, informar en el reporte)
Listar en el código los sensores cuya falta de lectura:
1. dispara el protocolo de estado seguro;
2. lo detiene (`bloqueado_motivo`);
3. deja `camara_segura` en NO segura (códigos de `motivos.py`).

Referencia esperada (verificar): presión de cámara (SEN-04 en ciclo, SEN-06 fuera), Principal (SEN-02, SEN-03; `solo_lenta`, `sin_temp_camara`, `sensor_temp_indeterminado`), empaque (SEN-08, `sin_presion_empaque`) y chaqueta (SEN-05, SEN-07). No incluye la comunicación (`sin_datos_vigentes`, tarjeta o módulo desconectado, COM-xx): eso no es un sensor y sigue visible.

### ESS-02 · Backend: bandera única de silencio
- `/status` publica `estado_seguro.silencioso_por_sensor` (bool) y `camara_segura_motivo_es_sensor` (bool).
- `silencioso_por_sensor` es True si el estado seguro está activo, no hay paro ni confirmación pendiente, y su causa o su bloqueo vigente es solo un sensor del inventario.
- `camara_segura_motivo_es_sensor` es True si el motivo de NO segura es un código de sensor del inventario.
- Si coexiste un motivo que no es de sensor (cámara presurizada, temperatura alta, líquidos calientes con tiempo límite, cámara sellada), el valor es False y se muestra todo como hoy.
- `estado_seguro.bloqueado_motivo` deja de llevar el texto de presión sin lectura: usar `bloqueado_motivo_sin_presion`, coherente con CIC-10.
- Falla cerrada: ante error o dato ausente, False (se muestra).
- La lógica de seguridad no cambia: protocolo, válvulas, bloqueo de puertas, bloqueo de inicio y `no_abrir` siguen igual.

### ESS-03 · CIC-10 por sensor
- CIC-10 no se activa si el único motivo de bloqueo es un sensor del inventario (se extiende ESG-01 al Principal).
- Se conserva para cámara sellada con líquidos y para el tiempo límite con carga líquida caliente.

### ESS-04 · UI
- En `SeccionEstadoSeguro.qml` (y en el puente), con `silencioso_por_sensor` se ocultan `filaEstadoSeguroEnCurso`, `avisoCausaEstadoSeguro`, `botonConfirmarEstadoSeguro`, `notaNoAbrirEnCurso` y `avisoEstadoSeguroDetenido`.
- Con `camara_segura_motivo_es_sensor` se oculta `filaNoAbrir`.
- Ninguna de ellas cuenta en la insignia de la campana ni en los grupos. Con la foto de referencia la campana debe marcar 1.
- Nunca se silencian el paro, la confirmación pendiente, "sin conexión" ni la tarjeta o el módulo desconectado o sin datos.
- `botonAsignarSonda` (S4, Principal sin lectura): DECISIÓN SIN CONFIRMAR. Se mueve al detalle desplegable de la alarma del Principal (SEN-02/SEN-03), para no perder la vía de recuperación.

### ESS-05 · Textos (D-2)
- El nombre visible de las alarmas del inventario termina en " — No abrir la puerta", en es y en (en: " — Do not open the door").
- Cumplir FC-10: el texto nunca se sale ni se recorta, y la letra baja hasta `Escala.fuenteMinima`.
- Las acciones que ya dicen "No abra la puerta" se conservan.

### ESS-06 · Bitácora y log
Sin cambios en `audit_log`. El evento de silencio va al log de desarrollo una vez por episodio, como en ESG-01.

## 4. Riesgo (ISO 14971), agregar a `docs/riesgos/registro_riesgos.md`

HAZ-ESS-01. Con un sensor sin lectura, el operador ya no ve "estado seguro en curso" ni "NO ABRIR" como fila propia. Con puertas manuales podría abrir la cámara presurizada.

Mitigaciones:
- "No abrir la puerta" en el nombre de la alarma del sensor.
- Bloqueo de puertas del backend sin cambios.
- Enclavamiento mecánico por presión en el equipo de pruebas.

Residual: medio en equipos de puertas manuales sin enclavamiento mecánico. Anotar en las anomalías conocidas de la próxima versión.

## 5. Pruebas
- Actualizar `test_t17_s3_esg.py`, `test_s9_estado_seguro_arranque.py` y las pruebas QML de `SeccionEstadoSeguro`.
- Casos nuevos:
  - Arranque sin presión: solo SEN-06, campana 1.
  - Principal perdido en ciclo: sin CIC-10 ni filas de estado seguro.
  - Presión perdida y cámara sellada con líquidos: CIC-10 visible.
  - Paro con sensor perdido: el paro se ve.
  - Motivo mixto (presurizada y sensor): se muestra todo.
  - `/status` sin el campo: se muestra (falla cerrada).
- Banco: repetir la foto de referencia (desconectar el transductor de cámara y arrancar).

## 6. ESS-07 · Cierre de cambios rápidos sin prueba ni revisión

Pedido de Cristian (28-oct): en la misma sesión se cierran los cambios rápidos que quedaron sin pruebas o sin revisión.

### 6.1 Inventario
- Buscar en `git log` de `dev` desde el merge de la tanda 21 (3531c194) los commits con «urgente», «sin pruebas», «sin revisión» o «Pendiente:» en el mensaje.
- Buscar en `src/` comentarios «PENDIENTE: análisis de riesgo» o «PENDIENTE: … pruebas».
- Listar cada uno en el informe con su estado de pruebas, riesgo y revisión.

Encontrado al redactar esto:
- **acb33873**, reasignación de E/S en FALLA y con el estado seguro actuando (`server_reasignacion.py`). Prompt: `prompt_claude_code_reasignacion_sin_estado_seguro.md`.
- **3be8252d** ya ajustó `test_r8_reasignacion_api.py`.
- La versión **1.0.0-alpha.9** se compiló con esos dos commits.

Pendiente de ese cambio, según el commit y el comentario de cabecera:
- análisis de riesgo en `registro_riesgos.md`;
- revisión NTC-IEC 62304;
- quitar el «PENDIENTE» del comentario de cabecera.

### 6.2 Revisión de seguridad de acb33873
Puntos mínimos:
- **Reinicio del backend con el protocolo actuando.** El reinicio que sigue a la reasignación apaga las salidas a mitad del venteo. Verificar que al volver arranque el estado seguro de arranque (S9, solo la lenta) y que no se pierda ninguna de estas condiciones: `solo_lenta`, cámara sellada con líquidos (D8-2.10), tiempo límite con carga caliente. Si se pierde alguna, es un hallazgo.
- **Reasignación en FALLA con la cámara presurizada.** Durante el reinicio la cámara queda sin vigilancia. Medir cuánto dura esa ventana y confirmar que «NO ABRIR» y el bloqueo de puertas vuelven antes de que se pueda operar una puerta.
- **Pruebas de salidas.** La verificación con evidencia de las funciones movidas sigue exigiéndose antes de iniciar un ciclo (SEN-09).
- **Interacción con ESS.** Una reasignación que devuelve la lectura del sensor debe resolver el silencio y mostrar de nuevo el estado real.
- **Pruebas que faltan:** reinicio con el protocolo activo y presión vigente, reinicio con presión sin lectura, y reinicio en FALLA con carga líquida.

### 6.3 Resultado
- Riesgo HAZ-IO-04 (o el siguiente libre) en `registro_riesgos.md`.
- Comentario de cabecera actualizado.
- Si la revisión encuentra un hallazgo Alto, no corregirlo: reportarlo como DECISIÓN PARA CRISTIAN con la opción más segura y reversible.
