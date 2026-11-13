# Tanda 33: control en cascada de la chaqueta (CAS-01..CAS-05) (7-nov-2026)

Responde e informa SOLO en español. Prioridad: velocidad por tarea; cambio mínimo. Máximo 4 subagentes a la vez, sin suite completa en los subagentes; 1 revisor de seguridad al final sobre el diff de CAS. Especificación: `docs/mis_plans/planeacion_control_cascada_chaqueta.md` (léela completa primero; manda sobre este prompt si difieren). Decisiones de Cristian: todas las de la especificación (7-nov), salvo las marcadas `DECISIÓN SIN CONFIRMAR`. Ante ambigüedad, lo seguro y `DECISIÓN SIN CONFIRMAR` en el informe. Cristian hace pruebas de banco por la mañana: la tanda debe terminar sola.

## Requisito previo
1. Rama actual `dev`, con el merge de M2-REC (`94ed7baf`) y la etiqueta `v1.0.0-alpha.24`. Sin cambios pendientes en `src/`, `tests/`, `tools/` ni `packaging/` (los archivos de `docs/`, `AJUSTES.md`, `habblaud/` y los `compilacion_*.log` de Cristian no cuentan; no los toques). Si algo no cuadra: `docs/informes/tanda33/CERRADO.txt` con `BLOQUEADO:` y el motivo, y termina.
2. Rama `tanda33` desde `dev`. Lleva `docs/informes/tanda33/estado.md` al día tras cada commit; al reanudar, sigue desde el primer paso pendiente.
3. Nota: la suite completa de la alpha.24 no se corrió (`docs/informes/m2_recuperacion/estado.md`). Corre la suite completa al inicio (base) y guárdala en `docs/informes/tanda33/suite_base.txt`, para separar fallos previos de los tuyos.

## Contexto de código
- `state_machine/cycle_phases/esterilizacion.py`: `_vapor_on`, `_control_vapor_pwm`, `_corte_consigna_chaqueta`, `_actualizar_exencion_m2`, bloque «4. Control de vapor», `_BANDA_PWM_BAJA`/`_ALTA`, `consigna_pwm`, VCH-AIS (`_vigilar_aislamiento`, `aislamiento_camara.py`).
- `state_machine/cycle_phases/calentamiento.py`: bloque PWM (pasos 5–7), `_corte_consigna_chaqueta`, `_en_sostenimiento`, `_t_obj_alcanzada`, `bajando_a_psat`, `p_techo_rampa`, `p_techo_ais`.
- `state_machine/cycle_phases/corte_chaqueta_consigna.py` (A14-M2, M2-REC-01), `core/managers/limites_equipo.py`, `states/ciclo.py` (corte D-CHQ, `inhibir_vapor_chaqueta`), `tests/helpers/planta_vapor.py`, pruebas `test_t28_a14_*`, `test_m2_rec_esterilizacion.py`, `test_r8_planta_simulada.py`, `test_s9_planta_simulada.py`.

## CAS-01 Componente puro
`cycle_phases/cascada_chaqueta.py` según §3 CAS-01 de la especificación (niveles, consigna con tope por techo, histéresis bajo la consigna, falla cerrada, log por cambio, publicación `estado.cascada_chaqueta`). Constantes con nombre: `HISTERESIS_KPA = 3.0`, `MARGEN_TECHO_KPA = 2.0`, umbrales de nivel reutilizando los de la banda PWM (−2/+1). Pruebas unitarias propias: los tres niveles, histéresis (no conmuta entre consigna−3 y consigna), cambio de nivel en el mismo tick, tope por techo, por D-CHQ − 10 y por suministro, `tope < p_ref + 1` (advertencia una vez, nunca supera el techo), sin lectura de cada presión, valores no finitos.

## CAS-02 ESTERILIZACION modo chaqueta
Según §3 CAS-02. La cascada reemplaza PWM + A14-M2 + exención M2-REC-01 solo en modo chaqueta. Retira el código de la exención que quede muerto (y `motivo_exencion` si nadie más lo usa); `corte_chaqueta_consigna.margen_kpa` y `debe_cortar` siguen para la rampa de CALENTAMIENTO. Modo cámara byte a byte igual en comportamiento (las pruebas de modo cámara no deben cambiar). Prevalencias: VCH-AIS > `inhibir_vapor_chaqueta` > cascada; corte duro de CICLO intacto.

## CAS-03 CALENTAMIENTO modo chaqueta
Según §3 CAS-03: cascada en ESTABLE_PREESTERILIZACION y, con carga líquida y empuje, desde el enclave `_t_obj_alcanzada` (incluye `bajando_a_psat`); `p_ref = Psat(t_obj)`, `p_techo` normal. Rampa previa sin cambio.

## CAS-04 Planta simulada (criterio de liberación)
- Extiende `tests/helpers/planta_vapor.py` con: (a) error de ganancia de la lectura de `pres_chaqueta` (`lectura = p_atm + (real − p_atm) · k`; k = 1,00, 1,07 y 0,95); (b) una variante de caudal chaqueta→cámara alto (válvula de asiento sin restricción, volumen casi único). Valores provisionales, documentados en el docstring.
- Escenarios, cada uno con k = 1,00 / 1,07 / 0,95 y las dos variantes de caudal: Líquidos 121 °C de fábrica (con `presion_add_esterilizacion` 15 y también 11; `presion_add_liquido_calentamiento` 15 y 20; `brecha_segura_temperatura` 0,3 y 0,0); 134 °C sólidos (regresión A14).
- Criterio para seguir: todos COMPLETADO; presión mínima de cámara en esterilización ≥ 204,5 kPa a 121 °C (1,5 kPa sobre el fallo) y el equivalente a 134 °C; aislamientos ≤ 1 por ciclo; chaqueta máxima < `presion_max_chaqueta_control`; sobreimpulso a 134 °C no peor que el de A14 (0,59 K) en más de 0,2 K. Reporta además conmutaciones de `vapor_chaqueta` por minuto en esterilización (antes y después).
- Compara contra la alpha.24 (mismos escenarios) en una tabla del informe.
- Si un escenario con k = 1,00 no cumple: ajusta solo `HISTERESIS_KPA` (2–5) o `MARGEN_TECHO_KPA` (1–4), documenta cada intento, y si ninguno cumple, NO hagas merge: `CERRADO.txt` con `BLOQUEADO:` y los datos. Si solo fallan escenarios con k ≠ 1,00, sigue y repórtalo como dependencia de calibración (HAZ-CAS-02).

## CAS-05 Programas
`esterilizacion.presion_add_esterilizacion` 11 → 15 en `cycles/factory/liquidos.json` y `cycles/user/liquidos.json`. Verifica COHERENCIA_RECUPERACION, `aviso_banda_pwm_techo`, alivio y máximo. Sin migración de programas instalados. Ningún parámetro nuevo ni retirado.

## Hallazgo a investigar (solo reportar, no cambiar)
En cada arranque del equipo aparece «Programa con esterilizacion.brecha_segura_temperatura = 1.0: migrado a 0.3 °C (migración tanda 28 (M3))» aunque los programas de usuario ya tienen `migrado_t28_m3`. Probable: el programa de fábrica `textiles` se migra en memoria y nunca se reescribe. Confírmalo y anótalo en el informe.

## Cierre
- Pruebas: CAS-01 unitarias; CAS-02/03 de integración por fase (niveles, prevalencias VCH-AIS / D-CHQ / sin lectura, modo cámara sin cambio, log sin repetición); CAS-04 planta; CAS-05 coherencia. Actualiza o retira las pruebas de M2-REC-01 y A14-M2 que dejen de aplicar en modo chaqueta ESTERILIZACION, dejando constancia de cada una en el informe. Suite completa en verde (comparada con `suite_base.txt`).
- `CLAUDE.md`: sección «Tanda 33: control en cascada de la chaqueta» y nota en las viñetas de A14 (M1/M2) y M2-REC-01 de «CONTROL DE VAPOR POR CHAQUETA» de que en modo chaqueta las sustituye la cascada (en CALENTAMIENTO solo en sostenimiento y tras el enclave).
- `docs/riesgos/registro_riesgos.md`: HAZ-CAS-01 y HAZ-CAS-02 (§7 de la especificación); HAZ-M2-REC-01 marcado como superado en modo chaqueta. Trazabilidad REQ nueva. Hoja de banco: bloque T33 (calibración de `pres_chaqueta` contra patrón como primer paso, o transferencia contra la cámara; ciclo Líquidos 121 °C; ciclo 134 °C sólidos; Bowie & Dick; en el `backend.log`: líneas «Cascada chaqueta», número de «cámara AISLADA», presión mínima de cámara, chaqueta máxima).
- Informe `docs/informes/tanda33/R33_informe.md`: resumen en lenguaje llano para Cristian (qué cambió y qué mirar en el banco), tabla de la planta, todas las `DECISIÓN SIN CONFIRMAR`, pruebas cambiadas o retiradas, hallazgo M3.
- Revisor de seguridad sobre el diff de CAS; corrige los hallazgos bloqueantes antes del merge y lista los demás en el informe.
- Merge a `dev`.
- **Compilación (excepción autorizada por Cristian para esta tanda):** solo si la suite completa está en verde y el revisor no deja bloqueantes, corre `python tools/entrega/compilar_entrega.py` desde `dev` (genera la alpha.25). Si la herramienta se niega (árbol no limpio, falta `activacion_v2.json` u otro motivo), NO toques archivos de Cristian ni fuerces nada: anota el motivo y el comando en el informe y en `CERRADO.txt`. Si compila, indica la ruta de la entrega y del `Autoclave_Setup_*.exe`.
- Último acto: `docs/informes/tanda33/CERRADO.txt` (fecha, commit del merge, resultado de la suite, compilación hecha o no y por qué). Bloqueo que necesite a Cristian: igual, con `BLOQUEADO:` en la primera línea.
