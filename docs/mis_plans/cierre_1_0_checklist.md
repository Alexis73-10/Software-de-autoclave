# Cierre de la 1.0 — lista de lo que falta

Fecha: 30-oct-2026. Base: `dev` en 89ab62ef (`1.0.0-alpha.12`, compilada). Estado: **BORRADOR para Cristian**. Nada de esta lista está decidido ni implementado; las recomendaciones de la sección C son solo eso.

Fuentes leídas: `CLAUDE.md`; `docs/informes/tanda21/R21_informe.md`, `tanda23/R23_informe.md`, `tanda24/R24_informe.md` (preguntas abiertas y verificación en el equipo); `docs/riesgos/registro_riesgos.md`; `docs/versiones/anomalias_conocidas_1.0.0-alpha.4.md` (la última que existe); `docs/mis_plans/hoja_pruebas_banco_equipo_pruebas.md`; `docs/mis_plans/planeacion_licencia_pago.md`. Donde el informe y el código no coinciden, se leyó el código (se cita el archivo).

## Criterio propuesto para declarar la 1.0 (DECISIÓN SIN CONFIRMAR)

1. Todo lo de la sección A marcado **Bloquea 1.0** está hecho, con su prueba en la suite.
2. Todo lo de la sección B marcado **Bloquea 1.0** está aprobado en la hoja de banco, con el valor medido anotado.
3. Cada punto de la sección C tiene decisión escrita de Cristian (aceptar, cambiar o aplazar a la 1.1 con riesgo aceptado en el registro).
4. Suite `pytest tests -n auto` verde **sin** repetir en serie (ver A-04), y entrega compilada con `tools/entrega/compilar_entrega.py` desde `dev` limpio.
5. Anomalías conocidas de la 1.0 publicadas (A-06) y registro de riesgos aprobado (A-07 y C-01).

Uso clínico: hoy toda la 1.0.0-alpha es «sin uso clínico» (anomalías de la alpha.3 y alpha.4). Declarar la 1.0 **no** implica liberación clínica salvo que Cristian lo decida (C-01).

---

## Estado de los pendientes citados (resuelto / abierto)

| Pendiente | Estado | Evidencia |
|---|---|---|
| Permisos por pantalla en puertas (`source_door`) | **Resuelto en parte** (tanda 2, S3e): si viene `source_door`, otra puerta da 409 `puerta_ajena`; **ausente se acepta** como «desconocido». No hay autenticación de quién manda. | `src/autoclave/backend/rutas/puertas.py` líneas 29–58. La nota de memoria de sep-2026 está desactualizada. |
| Último mantenimiento y versión del módulo E/S en Información del equipo | **Resuelto** (mantenimiento: M1 tanda 3, `GET /maintenance`; versión: `ModbusLink.modulo_es()["version"]` en `/status.modulo_es`). Falta verlo en el equipo (B-12). | `src/autoclave/ui_qml/bridge/info_equipo.py` 101–157; `src/autoclave/backend/rutas/sistema.py` 225–239. |
| Indicador de puerta con trama DI vencida (R21, pregunta 1) | **Abierto.** `IndicadorPuerta.datosVigentes` = `UiBridge.connected` (solo la conexión con el backend); `/status.doors` publica `estado.estado_puertas` sin marca de vigencia. | `ui_qml/qml/Pantallas/PantallaPreciclo.qml` 60 y 766; `backend/rutas/sistema.py` 573–576. |
| CIC-19 sin debounce (R21, pregunta 2) | **Abierto** (decisión). Un solo tick con la Referencia en `None` o 0 aborta un ciclo de líquidos. | `state_machine/states/ciclo.py` 1187–1213. |
| `/cycle/abort`: doble cancelación y base ocupada (R21) | **Abierto.** No hay comprobación de bandera ya puesta: una segunda llamada escribe otra fila `ciclo_cancelado` y **sobrescribe `cancelado_por`** con el segundo usuario. La consulta a la base va después de poner la bandera. | `backend/rutas/ciclo.py` 404–427. |
| Tests de impresión que fallan con `-n auto` | **Abierto.** Registrados: `test_home_view.py::test_home_view_tarjeta_impresion_general_navega_a_impresion_menu` y `test_impresion_menu.py::test_impresion_menu_instancia_sin_crash` (R24: 2 fallos, 13 passed en serie). Cristian menciona 4: confirmar la lista con la salida de la entrega alpha.12. | `docs/informes/tanda24/CERRADO.txt`. |
| fc04 0x0000 ×16 del principal (R23, pregunta 1) | **Abierto, solo banco** (B-03). | `protocols/modbus_link.py`. |
| Reasignar el propio paro con el paro pulsado (R24, SAF-01) | **Mitigado en software** (inhibición de energía mientras `paro_emergencia` está sin verificar), **DECISIÓN SIN CONFIRMAR**; falta decidir si HAZ-IO-05 lo cubre (C-05). | R24 «Revisión R». |
| VCH-01, AIN-R3, M-2, `apertura_automatica` | **Abiertos, solo banco** (B-06, B-04, B-02, B-09). | Registro de riesgos; `CLAUDE.md`. |
| Licencia L1/L2 | **Sin implementar.** La planeación dice que es «condición para liberar la 1.0.0». Solo L0 está hecho. | `planeacion_licencia_pago.md` §4; `installation/secretos.py`. |
| Herramienta de entrega para una versión que no sea alpha | **Abierto.** `compilar_entrega.py` solo calcula `1.0.0-alpha.N` (expresión `^v1\.0\.0-alpha\.(\d+)$`). | `tools/entrega/compilar_entrega.py` 54, 342, 419. |

---

## (A) Software que se puede hacer sin hardware

Cada punto: qué, criterio de aceptación, prueba. «Bloquea 1.0» es una propuesta.

### A-01 — Indicador de puerta con datos del módulo E/S vencidos (R21, pregunta 1) · Bloquea 1.0
- **Qué.** `IndicadorPuerta` muestra «PUERTA CERRADA» solo con conexión al backend **y** `estadoModuloEs == "ok"` **y** trama DI vigente. Si el backend no marca la vigencia de `doors`, añadir esa marca en `/status` (p. ej. `doors_vigentes`, falla cerrada a False).
- **Aceptación.** Con el módulo E/S desconectado o con la trama DI vencida, el indicador muestra «PUERTA —» (gris), nunca «CERRADA». Sin el campo nuevo en `/status`, también «PUERTA —».
- **Prueba.** `tests/test_t21_indicador_puerta_qml.py` (casos nuevos: `estadoModuloEs` = `desconectada` / `sin_tramas_validas`, falta el campo) y una prueba de backend de `/status` con DI vencida.
- **Riesgo.** HAZ-FC-02 (sensor de puerta inválido = abierta). Pasar por `safety-reviewer`.

### A-02 — Registro de riesgos: entradas que quedaron desactualizadas tras RSB-07 · Bloquea 1.0
- **Qué.** **AIN-R3** dice «una función reasignada no se verifica sin calibrarla en el puerto nuevo (SEN-09, «Falta: calibrar el sensor en su puerto nuevo»)», y **HAZ-IO-02** dice «la analógica reasignada no se puede verificar… sin una calibración a dos puntos». Desde la tanda 24 (RSB-07) eso **ya no existe**: basta lectura válida y la calibración nominal cuenta. El texto `falta_calibracion_requerida` se retiró del catálogo.
- **Aceptación.** AIN-R3 y HAZ-IO-02 describen el control vigente (lectura visible en el diálogo, nombre escrito, auditoría con `metodo: "lectura"`) y su residual se reevalúa: hoy es como mínimo MEDIO y depende solo del procedimiento del técnico. Remiten a HAZ-IO-05 (g).
- **Prueba.** Revisión documental; `tests/test_r8_reasignacion_api.py` ya prueba el comportamiento.
- **Nota.** Es un hallazgo de seguridad documental: el registro promete un control que el código ya no tiene.

### A-03 — Hoja de banco al día con las tandas 21–24 · Bloquea 1.0
- **Qué.** Editar `docs/mis_plans/hoja_pruebas_banco/pruebas.py` y regenerar:
  - retirar o reescribir **H-08 «Ciclo NO CONFORME»** (FC-08 retiró NO CONFORME; hoy es «COMPLETADO con observación» en sólidos y CIC-19 en líquidos);
  - añadir un **bloque T24** con los 5 pasos de «Qué verificar en el equipo» de R24;
  - añadir los pasos de banco de R21 (Referencia desconectada en sólido y en líquido; cancelar con y sin sesión; indicador de puerta con el módulo desconectado);
  - marcar **D-R8-04** como condicionado (R23, decisión 9).
- **Aceptación.** Ningún paso de la hoja describe un comportamiento retirado; cada pregunta abierta de banco de R21/R23/R24 tiene su paso.
- **Prueba.** `tests/test_f1_registro_pruebas.py` (ya vigila la hoja; actualizar lo que espere).

### A-04 — Suite verde con `-n auto` sin repetir en serie · Bloquea 1.0
- **Qué.** Aislar los tests de impresión que caen el trabajador de xdist (PySide): `xdist_group` o un marcador que los corra en un solo trabajador, o corregir la causa (estado compartido de Qt). Confirmar primero si son 2 o 4.
- **Aceptación.** 3 corridas seguidas de `pytest tests -n auto` sin fallos; `compilar_entrega.py` no necesita la repetición en serie (o la conserva solo como respaldo, con aviso).
- **Prueba.** La propia suite; anotar las 3 corridas en el informe.

### A-05 — `/cycle/abort` idempotente · Recomendado para 1.0
- **Qué.** Si `CICLO_CANCELADO` ya está puesto, responder 200 `ya_cancelado` sin escribir otra fila ni cambiar `cancelado_por`. Que una base ocupada no haga responder error después de haber puesto la bandera (la consulta de número de ciclo con tope corto, o la respuesta antes de la consulta).
- **Aceptación.** Dos llamadas en el mismo tick → 1 fila `ciclo_cancelado`, `cancelado_por` = primer usuario. Con la base bloqueada, la respuesta es 200 y la cancelación se procesa.
- **Prueba.** Casos nuevos en `tests/test_t21_fin_de_ciclo_backend.py`.
- **Riesgo.** Bajo (trazabilidad). Sin BD, la fila sigue sin número de ciclo: dejarlo escrito en anomalías.

### A-06 — Anomalías conocidas de la 1.0 · Bloquea 1.0
- **Qué.** `docs/versiones/anomalias_conocidas_1.0.0.md` consolidado: la última es la de la alpha.4. Revisar AN-01..AN-36: cerrar las que ya no aplican (p. ej. **AN-04 y AN-18** hablan de NO CONFORME, retirado en FC-08) y agregar lo abierto de las tandas 21–24 (CIC-19 sin debounce, doble cancelación, indicador de puerta, gráfica que tapa el aviso, HAZ-ESS-01 residual en puertas manuales, HAZ-IO-05 residual ALTO).
- **Aceptación.** Cada anomalía tiene efecto, mitigación y destino (1.0 / 1.1 / decisión). Exigido por IEC 62304 §5.8.2–5.8.3.
- **Prueba.** Revisión de Cristian.

### A-07 — Registro de riesgos: estimación de probabilidad y severidad · Bloquea 1.0
- **Qué.** El registro está como «BORRADOR» y dice «Por completar global: estimación de probabilidad/severidad (ISO 14971 §5) de todas las entradas; aprobación de Cristian». Completar las entradas con «por completar» (HAZ-FC-04, HAZ-FC-06, HAZ-TAR-01, HAZ-I18N-01, HAZ-BD-01) y migrar la tabla a un formato con P, S y nivel antes y después.
- **Aceptación.** Ninguna celda «por completar»; criterio de aceptabilidad escrito; lista de residuales ALTOS con su decisión (ver C-01).
- **Prueba.** Revisión documental; actualizar `docs/riesgos/matriz_trazabilidad.md` (REQ ↔ riesgo ↔ prueba) con las tandas 21–24 y comprobar `docs/riesgos/lista_soup.md` (pymodbus 3.16.1).

### A-08 — Herramienta de entrega para `1.0.0-rc.N`, `1.0.0` y `1.1.0-alpha.N` · Bloquea 1.0
- **Qué.** `compilar_entrega.py` solo sabe hacer `1.0.0-alpha.N`; el cuarto campo de AppVerNum ya prevé beta/rc/final (`_NUM_ETAPA`, «final = 9000»). Añadir la etapa y la versión base como argumentos (p. ej. `--etapa rc`, `--final`, `--base 1.1.0`), sin romper la regla de fuente única (`_version.py`, `tests/test_ver_version.py`).
- **Aceptación.** Desde `dev` limpio se puede compilar `1.0.0-rc.1`, luego `1.0.0` (etiqueta `v1.0.0`), y después `1.1.0-alpha.1`; AppVerNum crece siempre (un Setup nuevo actualiza al anterior).
- **Prueba.** `tests/test_ver_*` con casos nuevos (orden de etiquetas, AppVerNum, rechazo de una versión menor que la instalada).

### A-09 — Aviso «sin conexión / módulo E/S sin datos» sobre la gráfica a pantalla completa (R21, pregunta 3) · Recomendado para 1.0
- **Qué.** La capa de avisos (`capaAvisos`) también por encima de la gráfica a pantalla completa.
- **Aceptación.** Con la gráfica ampliada y el módulo desconectado, el aviso se ve.
- **Prueba.** `tests/test_t21_pantalla_fin_ciclo_qml.py` o una prueba QML nueva offscreen.

### A-10 — Texto de log engañoso en el arranque S9 · Opcional
- **Qué.** «Protocolo fallo: paro de emergencia — salidas apagadas, sin válvulas» sale en todo arranque S9, con o sin paro (R24, paso 3). Cambiarlo según la causa.
- **Aceptación.** Sin paro, el log no dice «paro de emergencia».
- **Prueba.** Aserción de log en `tests/test_s9_estado_seguro_arranque.py`.

### A-11 — Textos menores de anomalías · Opcional
- AN-17: SIS-06 dice «kPa» para la migración de `brecha_segura_temperatura` (°C).
- Prueba: i18n del aviso con la unidad del parámetro.

### A-12 — `parametros_software.accdb` versionado (LIC-03) · Recomendado para 1.0
- **Qué.** Sigue en `docs/referencia/parametros_software.accdb` (git). Revisar su contenido y, si tiene algo sensible, sacarlo del repositorio.
- **Aceptación.** Revisión escrita del contenido; decisión de Cristian si hay que reescribir la historia (ver C-11).

### A-13 — Prueba de humo dentro del script de entrega (AN-13) · Opcional
- **Qué.** Arrancar el .exe compilado con el simulador en 127.0.0.1, esperar `/status` y cerrar.
- **Aceptación.** La entrega falla si el .exe no arranca.

---

## (B) Verificaciones solo de banco o equipo

Quién: **Cristian** (o el técnico que él designe) en el equipo de pruebas. Cada paso se anota en la hoja de banco con el valor medido. Orden: los en seco antes de los de operación (orden de la hoja).

### B-01 — Primer ciclo real (mañana) · Bloquea 1.0
1. Antes: bloques A, B, C y D en seco aprobados, en especial **B-01 paro, B-03 NO ABRIR, B-04 puertas, A-04 DO1/DO2** (regla 2 de la hoja).
2. Ciclo E-01 «Instrumental 134» completo, sin carga crítica.
3. **Esperado:** COMPLETADO; exposición 7 min con la temperatura del Principal dentro de los umbrales de falla, 133,9 (`t_est − brecha_error_temperatura`) a 137 °C (`t_est + rango_temperatura_ester`); presión entre `Psat(134) − 2` ≈ 302,2 y `Psat(134) + 30` ≈ 334,2 kPa abs; sin CIC-12/13; ticket y PDF coherentes con la pantalla.
4. Registrar: temperatura real con la presión en el techo, diferencia Principal–Referencia y oscilación pico a pico (AN-14, H-06, H-07). Sin esos datos no se pueden confirmar D-14.1, D-14.3 ni D-14.6.

### B-02 — M-2: qué esclavo es cada posición de firmware · Recomendado para 1.0
1. Leer 0x0C1F y las 5 posiciones de 0x0D80 (Información del sistema o `configurar-modulo`).
2. Comparar con la página web de cada expansión (Device Info).
3. **Esperado:** se sabe a qué módulo corresponde cada valor (hoy 0x0100 ×4 y 0x0000) y por qué uno da 0x0000. Si las versiones no coinciden con la web, anotarlo (MED-05 y la nota ADB-02).

### B-03 — fc04 0x0000 ×16 del principal (R23, pregunta 1) · Bloquea 1.0
1. Con la alpha.12 instalada, Entradas/Salidas: AI 01–16 con lectura (las no cableadas en falla de lazo, «—»).
2. Ver en `modbus_link.log` que no hay excepción de fc04.
3. **Esperado:** ninguna excepción; RTD 01–06 con lectura. Si hay excepción, el equipo queda sin AI (falla cerrada, pero inutilizable): volver a ×8 antes de la 1.0.

### B-04 — AIN-R3: calibrar en sitio las AI que se usen de 09 a 16 · Bloquea 1.0 si hay transmisores en AI 09–16
1. Confirmar si hay transmisores cableados en AI 09–16 (R23, pregunta 3).
2. Si los hay: calibración de sensor a dos puntos contra patrón (p. ej. 100 y 300 kPa abs).
3. **Esperado:** error ≤ 1,5 kPa tras calibrar (MED-02). Sin transmisores en 09–16, anotar «no aplica».

### B-05 — M-4: exactitud de PT100 y AI · Bloquea la liberación clínica
- PT100 a 121 y 134 °C contra patrón, antes y después de la calibración de usuario; AI a 100, 200 y 300 kPa abs.
- **Esperado:** decidir MED-01 (±1,1 °C de especificación frente a `brecha_error_temperatura` 0,1 °C) y MED-02. Ver C-03.

### B-06 — VCH-01: reajuste de parámetros en modo chaqueta · Bloquea 1.0 solo en equipos con chaqueta
1. Confirmar la clase del equipo de pruebas (`modo_vapor`: `"chaqueta"` solo PISO/PISO_LAB con `vapor_chaqueta` y `pres_chaqueta`). Si el equipo de pruebas está en modo cámara, VCH-01 **no se puede cerrar en él**.
2. Si aplica: bloque H (H-01 a H-07) con registro de sobrepaso, tiempo de calentamiento, aislamientos (CIC-15/16) y corte de chaqueta a 375 kPa.
3. **Esperado:** ciclo 134 °C completo sin aislamientos repetidos; ajuste de `factor_calentamiento`, `factor_esterilizacion` y `histeresis_cierre_camara` anotado.

### B-07 — Verificaciones de R24 (reasignación) · Recomendado para 1.0
Los 5 pasos de «Qué verificar en el equipo» de R24 (A-03 los lleva a la hoja). En especial el paso 5: si se reasigna el paro, vapor y aire comprimido no se encienden solos hasta verificarlo.

### B-08 — Verificaciones de R21 (fin de ciclo) · Recomendado para 1.0
1. Desconectar la Referencia en ESTERILIZACION con carga sólida → COMPLETADO, píldora ámbar, nota en el modal, línea en ticket/PDF/correo, sin apertura automática.
2. Con carga líquida → FALLO CIC-19.
3. Cancelar con sesión y sin sesión → «Cancelado por <usuario>» / sin usuario.
4. Desconectar el cable del módulo con Preciclo abierto en una puerta sin actuador → anotar qué dice el indicador (cierra la pregunta 1 de R21 y valida A-01).

### B-09 — `apertura_automatica` en campo · No bloquea 1.0 (queda en `false`)
1. Solo si Cristian decide habilitarla (C-07): un programa de prueba con `apertura_automatica=true`, puerta de descarga con actuador.
2. **Esperado:** espera `tiempo_espera_apertura`, abre solo con `temp_camara` y `pres_camara` seguras, CICLO_CONFIRMADO solo con la puerta observada en ABRIENDO/ABIERTO; con el bloqueo mecánico activo, `APERTURA_AUTOMATICA_DENEGADA` a los 60 s.
3. El equipo de pruebas tiene puertas abatibles manuales (hoja de banco): **no se puede validar ahí**.

### B-10 — Bloque M pendiente: M-1, M-5, M-5b, M-7 · Bloquea 1.0
- M-1 corte por desconexión (el relé abre solo a ≤ 1,0 s), M-5b prueba aislada de ADB-04 (¿hace falta reiniciar el módulo?), M-7 Setup con Modbus en un PC real (AN-35).
- **Esperado:** según cada paso de la hoja.

### B-11 — Bloque T23 (T23-01..04) · Bloquea 1.0
- La presión de cámara lee lo mismo antes y después de actualizar (AIN-R2); ningún texto con «tarjeta».

### B-12 — Información del equipo · Recomendado
- Último mantenimiento, ciclos restantes y versión del módulo E/S con valor real (no «No disponible»).

### B-13 — Paro largo con cámara presurizada y puertas avanzadas (HAZ-B9-02) · Solo en un equipo con puertas avanzadas
- Medir la presión del empaque durante el paro. No aplica al equipo de pruebas (puertas manuales).

### B-14 — Líquidos con vidrio real (bloque G) · Bloquea la 1.0 para programas de líquidos
- HAZ-LIQ-01: valores provisionales (volumen, equilibrado, enfriamiento). Al final y con detención ante ebullición o rotura.

---

## (C) Decisiones que son de Cristian

No se toman aquí. Cada una: opciones, recomendación (marcada) y riesgo de cada opción.

### C-01 — Alcance de la «1.0»: ¿versión del equipo de pruebas o liberación clínica?
- **Opción 1:** 1.0 = versión estable para el equipo de pruebas, sin uso clínico. Los residuales ALTOS (HAZ-IO-05 (a) y (e), MED-01) quedan aceptados solo para pruebas.
  - Riesgo: bajo para pacientes (no hay uso clínico); queda deuda documental para la liberación.
- **Opción 2:** 1.0 = liberación clínica.
  - Riesgo: exige cerrar MED-01..04, VCH-01, la licencia (C-02) y la aprobación formal del registro de riesgos; hoy no se cumple.
- **Recomendación:** opción 1, y dejar la liberación clínica como hito de la 1.1 o de una 1.0.x con su propio checklist.

### C-02 — Licencia L1/L2: ¿dentro de la 1.0?
- La planeación la pone como «condición para liberar la 1.0.0». Hoy solo está L0, y el ejecutable lleva el secreto empaquetado (`config/activacion_secretos.json`), riesgo aceptado «hasta L1».
- **Opción 1:** 1.0 sin licencia; L1 en la 1.1. Riesgo: un ejecutable copiado sirve para instalar otro equipo; ningún riesgo para el paciente.
- **Opción 2:** L1 dentro de la 1.0. Riesgo: retrasa la 1.0 (esfuerzo L) y añade una pantalla de bloqueo con interacción con el estado seguro (DL-10) justo antes de cerrar.
- **Recomendación:** opción 1 si la 1.0 es la del equipo de pruebas (C-01, opción 1); opción 2 si se va a vender un equipo con la 1.0.

### C-03 — MED-01: PT100 ±1,1 °C frente a `brecha_error_temperatura` 0,1 °C
- **Opción 1:** aceptar con calibración de usuario y los datos de M-4. Riesgo: si el error tras calibrar sigue cerca de 1 °C, una carga puede pasar con la temperatura real por debajo de la consigna.
- **Opción 2:** cambiar el módulo PT100 o usar transmisores de temperatura de mejor clase. Riesgo: hardware nuevo, otra adenda de banco.
- **Opción 3:** ajustar umbrales (control a `T_est + brecha_segura` mayor). Riesgo: más tiempo y más energía por ciclo; no corrige el error.
- **Recomendación:** decidir después de M-4 (B-05); hasta entonces, sin uso clínico.

### C-04 — CIC-19 sin debounce (R21, pregunta 2)
- **Opción 1:** confirmar sin debounce. Riesgo: un `None` aislado (código de diagnóstico del PT100) aborta un ciclo de líquidos; seguro, pero baja la disponibilidad.
- **Opción 2:** `DebounceAcumulado(5, 10)` como el resto de ESTERILIZACION. Riesgo: hasta 5 s de exposición con la Referencia sin lectura antes de abortar.
- **Recomendación:** opción 2 (mismo criterio que las fallas de esterilización), con prueba de que una pérdida sostenida sigue abortando.

### C-05 — ¿La aceptación de HAZ-IO-05 cubre reasignar la entrada del paro con el paro pulsado? (R24, SAF-01)
- Hoy: permitido; mitigado por la inhibición de energía mientras `paro_emergencia` esté sin verificar (DECISIÓN SIN CONFIRMAR) y porque el paro es NC (puerto sin cablear = paro activo).
- **Opción 1:** confirmar la mitigación tal como está. Riesgo: un puerto nuevo mal cableado que lea «liberado» deja el paro inoperante para las salidas que no son de energía (puertas, venteo) hasta verificar.
- **Opción 2:** rechazar con 409 la reasignación de `paro_emergencia` mientras `PARO_EMERGENCIA` esté activo. Riesgo: si la entrada del paro es la que está dañada, no se puede reasignar sin puentearla.
- **Recomendación:** opción 2 solo para el paro (es la función de seguridad que la persona usa para detener el equipo); el resto de HAZ-IO-05 como está.

### C-06 — Tolerancia de DI vencida de 4 s con Modbus (HAZ-T2-03, AN-34)
- **Opción 1:** dejar 4 s. Riesgo: ninguno conocido (el módulo corta las salidas a 1,0 s sin tráfico), pero el valor ya no tiene su justificación original.
- **Opción 2:** bajarla (p. ej. 1,5 s, igual que la vigencia de AI). Riesgo: más FALLO_CONEXION por cortes breves de red.
- **Recomendación:** opción 1 con la justificación nueva escrita en el registro, revisable tras M-1.

### C-07 — `apertura_automatica`
- **Opción 1:** la 1.0 sale con `false` en todos los perfiles y la función marcada «no validada». Riesgo: ninguno nuevo.
- **Opción 2:** validarla en un equipo con puerta con actuador antes de la 1.0. Riesgo: depende de un equipo que no es el de pruebas.
- **Recomendación:** opción 1.

### C-08 — HAZ-IO-03: CONFIGURACION_INVALIDA bloquea también el estado seguro tras un corte
- Con `asignacion_io.json` dañado no corre la recuperación de ciclo interrumpido ni el estado seguro: con la cámara presurizada queda sin venteo hasta restaurar (MEDIO, «PREGUNTA PARA CRISTIAN» desde la tanda 8).
- **Opción 1:** aceptar. Riesgo: cámara presurizada sin venteo por software (el enclavamiento mecánico D-02 sigue).
- **Opción 2:** con la asignación inválida, correr el estado seguro con la asignación de fábrica solo para la lenta y la presión de cámara. Riesgo: usar la fábrica es justo lo que HAZ-IO-03 quería evitar (puerto dañado).
- **Recomendación:** opción 1 para la 1.0, con el procedimiento de servicio escrito; revisar en la 1.1.

### C-09 — Preguntas abiertas de seguridad que siguen sin respuesta
Cada una con su entrada en el registro. Para cada una: aceptar (y escribirlo) o pasarla a la 1.1.
- HAZ-B9-02 (paro largo sin reponer aire al empaque) y **HAZ-B9-03** (una puerta en movimiento reanuda sola al soltar el paro). No aplican a puertas manuales. Recomendación: aceptar para el equipo de pruebas y llevar B9-03 a la 1.1 (ver planeación).
- HAZ-S9-02 (arranque con la presión desconocida no ventea). Recomendación: aceptar (falla cerrada; NO ABRIR se mantiene).
- HAZ-S1-05 y HAZ-S2A-05 (líquidos sin presión o sin reposición de aire). Recomendación: decidir después del bloque G.
- HAZ-X9-01, SAF-02 (corte entre escribir el JSON y la bitácora). Recomendación: aceptar como anomalía conocida.
- HAZ-ESS-01 (silencio del estado seguro en equipos de puertas manuales sin enclavamiento mecánico). Recomendación: anotar en anomalías (la propia planeación lo pide).
- «Reiniciar software» aplica una asignación pendiente sin el flujo de Aplicar (abierto en HAZ-IO-05). Recomendación: que pase por el mismo aviso RSB-03, en la 1.1.

### C-10 — Decisiones sin confirmar acumuladas (AN-14, AN-20, AN-23..25, AN-29, AN-33, R21 1–11, R23 1–9, R24 1–6)
- **Opción 1:** confirmarlas en bloque para la 1.0 (todas fallan cerradas). Riesgo: alguna interpretación equivocada queda como requisito.
- **Opción 2:** revisarlas una por una. Riesgo: tiempo.
- **Recomendación:** revisar una por una las que afectan control o actuadores (AN-14, AN-29, R21-11 (SAF-02), R24-2 (SAF-01)) y confirmar en bloque las de textos y presentación.

### C-11 — Repositorio y secretos (LIC-01, LIC-03)
- Confirmar que el repositorio de GitHub es privado y que los secretos se rotaron (L0 lo pedía a Cristian). Decidir si `parametros_software.accdb` se saca de la historia (reescribirla rompe los clones existentes).
- Recomendación: privado sí o sí; reescribir la historia solo si A-12 encuentra algo sensible.

### C-12 — Ramas para preparar la 1.1
- Hoy `dev` lleva todo y no tiene push de varias tandas; `main` existe.
- **Opción 1:** etiqueta `v1.0.0` en `dev`, `main` = `v1.0.0`, rama `soporte-1.0` para correcciones y `dev` sigue con la 1.1.
- **Opción 2:** todo en `dev` y correcciones de la 1.0 como 1.1.0-alpha.
- **Recomendación:** opción 1 (las correcciones de seguridad de la 1.0 instalada no deben arrastrar funciones nuevas). Requiere A-08.
