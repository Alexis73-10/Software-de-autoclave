# S1 — SEN-01: transductor de presión sin señal (tanda 8, etapa ★)

Rama `tanda-8-s1` (worktree `.claude/worktrees/agent-a98cf543dd1b71cb2`), desde `tanda-8`. Fuente: D8-1 de `docs/mis_plans/decisiones_tanda_8.md`. La sesión se cortó una vez por límite de uso y se reanudó sin rehacer los commits previos.

## Qué se hizo, por punto

### D8-1.1 Detección sobre la señal cruda (d64636b, revisión ★ en el commit de correcciones)
- `hal/measures/converters.py::convert_pressures`: antes de filtrar, calibrar y recortar, cada muestra cruda se compara con los umbrales NAMUR NE43 de la calibración de fábrica del canal: bajo `adc_min − margen_falla_bajo·span` (defecto 0,025 = 3,6 mA), alto `adc_max + margen_falla_alto·span` (defecto 0,0625 = 21 mA). Márgenes y umbrales explícitos en cuentas (`adc_falla_bajo`, `adc_falla_alto`) son campos de `FactorySensorCalibration` (`config/schema.py`).
- 3 muestras seguidas fuera de rango declaran la falla y 3 dentro la levantan (`_DetectorLazo`). En falla el canal entrega `None`, nunca 0; una muestra fuera de rango sin falla declarada no entra al filtro (repite el último valor). Al recuperar, el filtro arranca limpio.
- El debounce cuenta tramas AI nuevas: `SerialLink` numera las tramas AI (`ai_seq`) y `Units` solo cuenta una muestra si `ai_seq` es mayor que la última (las notificaciones por DI/DO y las tramas viejas que llegan fuera de orden desde otro hilo no cuentan, TMG-02). Un salto grande hacia atrás (contador reiniciado) cuenta como nuevo para no congelar la presión.
- `Units` arranca con presión `None` (antes 0,0). La UI ya mostraba "—" (`SIN_DATO`) para `None`.
- Alta inactiva si el umbral calculado es ≥ 4095 (la tarjeta satura antes de 21 mA): pasa con la calibración actual (adc_max 4050).
- Piso de saturación: si el umbral bajo calculado queda ≤ 0, 0 cuentas es falla.
- **Piso calibrado (revisión ★, SAF-03/SEN-02):** con la calibración actual el umbral bajo queda < 0 y la calibración de usuario del canal 0 (gain 1,364, offset −75,3) pone el 0 kPa real en ≈546 cuentas: residuos de un lazo abierto (1..~480 cuentas) daban presión negativa y el recorte los dejaba en 0 kPa válido. Complemento: si la muestra cruda calibrada (fábrica + usuario, sin filtrar ni recortar) queda bajo `pres_falla_bajo_kpa` (defecto −10 kPa; un transductor absoluto nunca lee negativo) cuenta como fuera de rango, con el mismo debounce. `None` lo desactiva.

### D8-1.2 Con ciclo en curso (e876a67 + correcciones)
- `CicloState`: presión de cámara sin lectura → FALLO **SEN-04**; chaqueta (si `io_enabled` la declara) → **SEN-05**. Prioridad sobre SEN-02. `ProtocoloFallo.ejecutar(solo_lenta=True)`: todo apagado, solo la lenta; nunca rápida, chaqueta ni aire atmosférico. El FALLO no se revierte si la lectura vuelve.
- **Empaque (revisión ★, SAF-01/TMG-01/SEN-01, Alto):** el convertidor también entrega `None` en `pres_empaque_n`; `_verificar_puertas` lo omitía en silencio (antes daba 0 y disparaba PUE-03) y el ciclo seguía sin vigilancia del empaque. Ahora, en puertas con empaque (`revisa_empaque`), empaque sin lectura → FALLO **SEN-08** "Sensor de presión de empaque sin lectura" (es/en), solo la lenta. Un empaque bajo con lectura sigue en PUE-03.
- **Protocolo ya en marcha (revisión ★, SAF-02):** si la presión de cámara se pierde con el protocolo de fallo ya corriendo por otra causa, `ProtocoloFallo.update()` pasa a `solo_lenta` con el mismo enclavamiento y debounce que R1-P4 (Principal perdido): cierra rápida, chaqueta, contrapresión; abre la lenta con presión desconocida. También vale en el estado seguro, que usa el mismo protocolo.

### D8-1.3 Fuera de ciclo (c8370b5)
- PREPARACION y PREPARADO: SEN-06 (cámara) / SEN-07 (chaqueta), "llame a servicio", el equipo no queda listo; el canal sin lectura no recibe además SEN-01.
- `/cycle/start` rechaza con "Sensor de presión de cámara sin lectura: llame a servicio" (o chaqueta) antes que "no está listo"; un error al evaluar no inicia (`PRESION_NO_VERIFICABLE`).
- NO ABRIR ya fallaba cerrado sin presión de cámara (sin cambio, verificado en pruebas).

### D8-1.4 Alcance
- Cámara siempre; chaqueta si `io_enabled` la declara o si no se puede leer (falla cerrada). Empaque: ver SEN-08 arriba (solo puertas con empaque según el perfil).

### D8-1.5 Verificación (3f757e5)
- Ensayo con la planta simulada en los 4 programas de fábrica: `tests/test_s1_ensayo_simulador.py`, tabla en `docs/informes/tanda8/S1_ensayo_tabla.md` (cámara en prevacío —Líquidos: calentamiento—, cámara en esterilización, chaqueta en esterilización). En las 12 celdas: FALLO con código propio, `solo_lenta`, vapor cortado, sin aire atmosférico, rápida ni chaqueta mientras no lee, el FALLO no se revierte, FALLA sale a PREPARACION sin técnico.
- Hoja de banco: D-38 (en seco, con cuentas a anotar; paso 8 para el empaque en vacío), F-21 (cámara en ciclo), F-22 (chaqueta en ciclo; renumerados al unir: S2a ya usaba F-12 y F-13) en `docs/mis_plans/hoja_pruebas_banco_equipo_pruebas.md`.
- Registro de riesgos: HAZ-S1-01..04 (HAZ-S1-04: empaque sin lectura y presión perdida con el protocolo en marcha) en `docs/riesgos/registro_riesgos.md`.

## Commits
- d64636b feat: detección NAMUR (D8-1.1)
- e876a67 feat: FALLO propio en ciclo, solo la lenta (D8-1.2, 1.4)
- c8370b5 feat: fuera de ciclo bloquea el inicio (D8-1.3, 1.4)
- 3f757e5 test: ensayo con planta simulada, hoja de banco, registro de riesgos (D8-1.5)
- 15cb8c0 fix: correcciones de la revisión ★ (SEN-08, SAF-02, SAF-03, TMG-02)
- (último) fix + docs: Bajos de la re-revisión (motivo del solo_lenta, ai_seq 0), hoja de banco paso 8 y este informe

## Pruebas
Nuevas: `tests/test_s1_sen01_convertidor.py`, `tests/test_s1_sen01_ciclo.py`, `tests/test_s1_sen01_fuera_de_ciclo.py`, `tests/test_s1_ensayo_simulador.py`. Ajustadas (fixtures sin `pres_empaque_n`, que en el equipo real siempre se publican): `test_adenda_estados.py`, `test_ciclo_sensores.py`, `test_t2_p3_di_vencida.py`, más `test_alarmas_catalogo.py`, `test_o1_operador_ciclo.py`.

Por la regla 8 modificada (sesión principal), NO se corrió la suite completa: solo las pruebas de lo tocado, con `PYTHONPATH=<worktree>/src` y `autoclave.__file__` = `C:\Users\tecni\Documents\codigo_autoclave\.claude\worktrees\agent-a98cf543dd1b71cb2\src\autoclave\__init__.py`. Resultados en el worktree: no quedaron anotados (corte por límite de uso). Al unir (sesión principal) se corrieron las pruebas de S1, S2a, S2b y las afectadas sobre `tanda-8` (ver `estado.md`) y la suite completa (`suites/integ_s1.log`).

## Revisores ★
Primera ronda (safety-reviewer, timing-auditor, sensor-role-auditor en paralelo; sus informes los recibió la sesión principal): 1 Alto común (empaque sin lectura omitido en ciclo) — **corregido** (SEN-08). Medios corregidos: SAF-02, SAF-03/SEN-02, TMG-02. 

Re-revisión (los tres, sobre 15cb8c0): **0 Altos/Críticos abiertos.** Alto del empaque, SAF-02, SAF-03/SEN-02 y TMG-02 verificados como corregidos. Corregidos además en el último commit: SAF-03 (Bajo) — el evento `estado_seguro_solo_lenta` registra la causa real (`ProtocoloFallo.motivo_solo_lenta`: Principal, presión de cámara o ambos); TMG-02 (Bajo) — `ai_seq` 0 (foto inicial de `SerialLink` con AI en ceros) no cuenta como muestra.

Quedan de la re-revisión (documentados, no corregidos):
- safety SAF-01 (Medio): el piso de −10 kPa deja un hueco de ≈472-546 cuentas en la cámara (−10..0 kPa calibrados, recortados a 0 válido). No se subió a −3 kPa porque el sensor-role-auditor (SEN-03) advierte que el empaque podría leer ≈ −9,3 kPa con 0 kPa reales: subir el piso por defecto arriesga un SEN-08 falso. DECISIÓN SIN CONFIRMAR: se queda en −10 kPa y se ajusta por canal tras D-38.
- safety SAF-02 (Medio): SEN-08 fuerza solo la lenta y anula la contrapresión de los modos 4/5 con líquido. PREGUNTA 6.
- sensor-role SEN-03 (Medio): ver PREGUNTA 5. SEN-04 (Bajo): el piso calibrado se evalúa sobre la muestra cruda sin la mediana (solo el debounce de 3): aceptado.
- timing TMG-01 (Medio, residuo de TMG-02): una foto vieja de `SerialLink` aún sobrescribe `_raw_ai`, temperaturas, DI y `_connected` en `Units` (el filtro por `ai_seq` solo protege el debounce de presión). Impacto bajo: `ControlLoop` usa `link.is_connected()` y `_di_vigente()`, no `Units`. Arreglo propuesto (secuencia global o lock de notificación en `SerialLink._notificar`) fuera del alcance de S1.
- timing TMG-03 (Bajo): la pérdida de presión con el protocolo en marcha suma 3 ticks de debounce del protocolo a las 3 tramas del convertidor; durante esos ticks las válvulas de descompresión quedan como estaban. Conservador; aceptado.

Medios/Bajos no corregidos (documentados):
- SEN-03 (preexistente): `advanced_door.presion_empaque()` convierte `None` en 0,0. Ver PREGUNTA 4.
- SAF-02 parcial: con el protocolo en marcha, la pérdida de presión pasa a solo la lenta pero no activa una alarma SEN-04 ni `bloqueado_motivo` propios; NO ABRIR se mantiene igual (sin presión la cámara no es segura) y al salir a PREPARACION se activa SEN-06. La válvula de reposo tras COMPLETADO no se tocó.
- TMG-03/SAF-05: hasta 2 tramas congeladas (último valor) mientras el debounce confirma la falla (≈1 s). Aceptado: es el precio del debounce de 3 pedido por D8-1.1.
- TMG-04: `SerialLink._connect` no limpia `ai` ni los detectores al reconectar; la detección se rehace con las tramas nuevas.
- TMG-05/SAF-06: `_ai_habilitadas` usa `lru_cache`: un cambio de `io_enabled` en caliente no se ve hasta reiniciar; un error de lectura se cachea como `None` (= vigilar chaqueta, falla cerrada).
- SEN-04 (rev.): alta inactiva con la calibración actual (4095 se toma como válido).
- SEN-05/SAF-04: un canal sin calibración de fábrica (sin adc_min/adc_max) deja inactiva la detección en cuentas sin registrar aviso (el piso calibrado sí aplica si hay calibración de fábrica).
- TMG-06, TMG-07: menores, sin efecto en la seguridad.

## DECISIONES SIN CONFIRMAR
1. Umbral bajo ≤ 0 → piso de saturación (0 cuentas = falla).
2. Piso calibrado `pres_falla_bajo_kpa` = −10 kPa (revisión ★, SAF-03): complemento de la detección en cuentas, hasta tener las cuentas reales de la prueba de banco D-38.
3. Empaque sin lectura en ciclo = FALLO SEN-08 con solo la lenta (código nuevo, mismo criterio que SEN-04/05).
4. La chaqueta se vigila también si `io_enabled` no se puede leer (falla cerrada).

## PREGUNTAS PARA CRISTIAN
1. SEN-05 (chaqueta sin lectura) fuerza solo la lenta y anula la contrapresión de los modos 4/5 con líquido: ¿es lo que quiere, o con la cámara leyendo debería seguir el modo del programa?
2. `ACV-2026-001.yaml` declara `pres_empaque_1/2` en `io_enabled` aunque D8-1.4 dice que el equipo de pruebas no tiene sensor de empaque: si la puerta no es `simple`, sin sensor el inicio queda bloqueado (SEN-01) como ya pasaba con el 0. ¿Se corrige el perfil?
3. Cuentas reales de la prueba de banco (atmosférica, lazo abierto, corto) para fijar `adc_falla_bajo`/`adc_falla_alto` o los márgenes y el piso calibrado. La calibración de fábrica actual (adc_min 5/50) no parece corresponder a 4 mA reales (la de usuario pone el 0 kPa en ≈546 cuentas).
4. `advanced_door.presion_empaque()` convierte `None` en 0,0 (preexistente, no tocado): ¿se cambia a "sin lectura"?
5. (SEN-03 de la re-revisión, Medio) Los comentarios de patrón de `calibration.yaml` (empaques 55→10 y 296→337; también cámara y chaqueta) no cuadran con el gain/offset cargados. Si los comentarios son los reales, con el empaque en vacío (0 kPa reales) se leería ≈ −9,3 kPa, a 15-20 cuentas del piso calibrado de −10 kPa: posible SEN-08 falso. En ciclo el empaque debería estar presurizado, pero hay que verificarlo en la prueba de banco (paso 8 de D-38) y, si hace falta, ajustar `pres_falla_bajo_kpa` por canal (ya es un campo por canal de la calibración de fábrica). ¿Cuál de los dos (comentario o gain/offset) es el vigente?

6. (SAF-02 de la re-revisión) Con SEN-08 (empaque sin lectura) en un ciclo de líquidos de modo 4/5: ¿solo la lenta (criterio actual, igual que SEN-04/05) o mantener la contrapresión del programa? ¿Y se acepta que, como con SEN-04/05, FALLA pase a PREPARACION sin técnico (el inicio queda bloqueado por SEN-01 mientras el empaque no lea)?
7. Ruido del ADC crudo del canal de cámara a 5-10 kPa y con el lazo abierto (anotarlo en D-38) para confirmar el margen del piso calibrado.

## Puntos de choque
- i18n: `src/autoclave/i18n/es.json` y `en.json` (claves `ciclo.presion_*_sin_lectura`, `ciclo.presion_no_verificable`, alarmas SEN-04..SEN-08).
- `db_manager.py`: no tocado, sin migración.
- QML: ninguno.
- Otros compartidos: `state_machine/states/ciclo.py`, `preparado.py`, `preparacion.py`, `cycle_phases/protocolo_fallo.py`, `state_machine/estado_seguro.py`, `alarms/catalogo.py`, `backend/server.py` (`_validar_inicio`), `hal/measures/converters.py`, `units.py`, `protocols/serial_link.py`, `config/schema.py`, hoja de banco y registro de riesgos.

## Pendientes
- Prueba de banco D-38 / F-21 / F-22 y ajuste de umbrales.
- Suite completa: la corre la sesión principal al unir.
