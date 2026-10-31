# T10 — Texto de CIC-10 sin presión de cámara (tanda 10, D10-3)

Rama `tanda-10-t10` (parte de `tanda-10`, f73acf6). Subagente, 23-oct-2026.

## Qué se hizo (D10-3)

**Cómo se elegía el texto hasta ahora.** CIC-10 tiene una sola acción en el catálogo
(`catalogo.py` y `i18n/<idioma>.json → alarmas.CIC-10.accion`), la de la sonda Principal, sea
cual sea la causa. La causa solo se ve en el valor `motivo`, que es el texto que arma
`ProtocoloFallo.bloqueado_motivo`; `alarmas_i18n.clave_motivo_bloqueo()` ya lo traduce a la
clave `estado_seguro_motivos.<causa>` por su prefijo. Para distinguir la causa **no hizo falta
tocar la lógica**: se reutiliza esa clave.

**Cambios (solo textos y cómo se eligen):**

| Dónde | Cambio |
|---|---|
| `state_machine/cycle_phases/protocolo_fallo.py` | Solo el texto devuelto con `_presion_perdida`: «Sensor de presión de cámara sin lectura: sin el sensor de presión de cámara no se puede llevar la cámara a estado seguro. Revise la conexión del sensor de presión de cámara o llame a servicio técnico». Misma condición, mismo orden de prioridad. |
| `state_machine/alarms/catalogo.py` | Nueva constante `CIC_10_ACCION_SIN_PRESION` (acción en español de la causa presión). La definición de CIC-10 no cambia (su acción sigue siendo la de la sonda Principal). |
| `core/runtime/alarmas_i18n.py` | Prefijo del motivo acortado a «Sensor de presión de cámara sin lectura:» (vale para el texto nuevo y para el de la tanda 9 que quede en registros). Nueva `accion(definicion, valores)` y la tabla `_ACCIONES_POR_MOTIVO` (CIC-10 + `sin_presion_camara` → campo `accion_sin_presion`); `textos()` la usa: con esa causa nunca muestra la acción de la sonda Principal, ni en español ni en inglés. |
| `backend/server.py` (`_alarma_dto`) | El campo `accion` de `/status` sale de `alarmas_i18n.accion()` (antes, la acción fija del catálogo). |
| `i18n/es.json`, `i18n/en.json` | `estado_seguro_motivos.sin_presion_camara` con el texto nuevo; nueva `alarmas.CIC-10.accion_sin_presion`. La `accion` de CIC-10 y `sistema.estado_seguro_detenido_accion` quedan idénticas. |

Textos nuevos:
- es, acción: «No abra la puerta. Sin el sensor de presión de cámara no se puede llevar la cámara a estado seguro. Revise la conexión del sensor de presión de cámara o llame a servicio técnico.»
- en, motivo: «Chamber pressure sensor without reading: without the chamber pressure sensor the chamber cannot be brought to a safe state. Check the chamber pressure sensor connection or call technical service»
- en, acción: «Do not open the door. Without the chamber pressure sensor the chamber cannot be brought to a safe state. Check the chamber pressure sensor connection or call technical service.»

**Qué llega a cada pantalla:**
- Tarjeta de alarmas de Preciclo y filas de la campana (`FilaAlarma`): muestran el rol `description` (la descripción registrada, en español) = motivo nuevo + «. La cámara sigue sin considerarse segura.» No muestran la acción.
- Aviso del estado seguro detenido en la campana (`SeccionEstadoSeguro`): el motivo por su clave en el idioma vigente; como el motivo no contiene «Principal», `es_bloqueado_sonda` es False y no se añade la acción de asignar sonda ni su botón (igual que en la tanda 9).
- La acción de CIC-10 por causa queda en `/status` (`accion` y `textos.<idioma>.accion`) para quien la consuma.

Documentación: `docs/catalogo_alarmas.md` (fila CIC-10), `docs/mis_plans/hoja_pruebas_banco_equipo_pruebas.md`
(caso nuevo **C-05i** «Arranque sin sensor de presión de cámara: texto de CIC-10 según la causa»; el texto
esperado de C-05b se actualizó). `tests/cap9_capturas_banco.py`: motivo nuevo, destino opcional por
`CAP_DESTINO` y el resultado de Preciclo incluye las descripciones y el aviso.

## Commits

- `777d4a0` fix(tanda10-t10): texto de CIC-10 según la causa (sin presión de cámara)
- `21e29d7` docs(tanda10-t10): caso C-05i, catálogo de alarmas y capturas de Preciclo
- (este informe) docs(tanda10-t10): informe

## Pruebas

`autoclave.__file__` = `C:\Users\tecni\Documents\codigo_autoclave\.claude\worktrees\agent-a3d482a1c2c15e108\src\autoclave\__init__.py`

- `tests/test_t10_texto_cic10.py` (nuevo, 18 pruebas): primero **9 failed, 9 passed** (rojo); después **18 passed**. Cubre: sin presión la acción y la descripción (es y en) no mencionan la sonda Principal y sí el sensor de presión de cámara, el estado seguro, la conexión y servicio técnico; el motivo de la tanda 9 en un registro viejo también da la acción nueva; con las cuatro causas de sonda Principal la acción es idéntica a la anterior (es y en); `/status` (`_alarma_dto`); lo que reciben la tarjeta de Preciclo y la campana (`_normalizar_alarmas`, `UiBridge._seguridad_de`).
- Módulos que importan lo tocado (66 archivos: todo `tests/test_*.py` que use `alarmas_i18n`, `protocolo_fallo`, `alarms.catalogo`, CIC-10, `_alarma_dto` o `estado_seguro_motivos`, más `test_i18n.py` y `test_i18n_linea_base.py`): **1558 passed, 5 skipped** en 195 s.
- Capturas offscreen (`CAP_DESTINO=… python -X utf8 tests/cap9_capturas_banco.py preciclo`), sin avisos QML: `docs/informes/tanda10/capturas/t10/T10_es_preciclo_cic10_sin_presion.png` y `T10_en_…`. El aviso de estado seguro detenido sale con el texto nuevo en cada idioma; las filas de la lista, con la descripción en español.

## DECISIONES SIN CONFIRMAR

1. El **motivo** se cambió en el literal de `ProtocoloFallo.bloqueado_motivo` (es lo que la descripción en español muestra tal cual). Es solo el texto: condición y prioridad iguales. Se mantuvo el comienzo «Sensor de presión de cámara sin lectura:» para que se siga reconociendo y para que los registros de la tanda 9 se presenten con el texto nuevo.
2. La acción variante arranca con «No abra la puerta.» como la de la sonda Principal (NO ABRIR sigue vigente).
3. No se agregó la acción a la tarjeta de Preciclo ni a la campana (hoy no muestran la acción de ninguna alarma); el aviso de la campana ya lleva en el propio motivo «revise la conexión… o llame a servicio técnico».

## PREGUNTAS PARA CRISTIAN

Ninguna: no hizo falta tocar la lógica del protocolo.

## Pendientes (fuera de T10)

- **Fila de CIC-10 ilegible en la tarjeta de Preciclo** (ya visto en CAP9, punto 2): `fontSizeMode: Text.HorizontalFit` encoge el motivo largo hasta ser casi ilegible y se corta; con el texto nuevo, más largo, se nota más (ver captura). Toca `PantallaPreciclo.qml` (compartido): para el barrido de pantallas (U10) o decisión aparte.
- **Filas de alarmas en español con la interfaz en inglés** (CAP9, punto 1): la lista usa `description` (español) y no `textos.<idioma>`. Sin cambios aquí.
