# Tanda 35: cascada integral (CRI-01..04). Informe

Fecha: 9-nov-2026. Rama `tanda35` sobre `dev` (alpha.26). Commits: `6b17cb6b` (línea base), `536f0b56` (CRI-01..04), `275d3191` (planta antes/después), `9b758b3d` (corrección de la revisión: ALTA-1 y MEDIA-2), `2f35ba33` (MEDIA-A y MEDIA-B). Especificación: `docs/mis_plans/planeacion_cascada_integral.md`. Entrega NO compilada (comando: `python tools/entrega/compilar_entrega.py`). Planta simulada PROVISIONAL (`tests/helpers/planta_vapor.py`).

## 1. Cambios por CRI

- **CRI-01 (`cycle_phases/cascada_chaqueta.py`, usado por `esterilizacion.py` y `calentamiento.py`):** `dp` integral (`KI_CRI` 0,15, `DP_MIN_KPA` 3, `DT_MAX_S` 2; acotado a `[DP_MIN, tope_baja - p_ref]`); consigna de banda `min(p_ref + dp, tope_baja)` sin el tope `techo - 2`; `dp` inicial `margen_chaqueta_est`; herencia de CALENTAMIENTO a ESTERILIZACION como `max(heredado, margen_chaqueta_est)`; antiembalamiento condicional (en «baja» no integra error positivo; `solo_bajar` con VCH-AIS aislado o `inhibir_vapor_chaqueta`; `congelar` sin lecturas o sin Principal en ESTERILIZACION); `estado.cascada_chaqueta` publica `dp`.
- **CRI-02:** `brecha_segura_presion` sobre Psat en RECUPERACION (los dos modos; entra con `P < Psat + brecha`, sale con `+ 1,0`); en ESTERILIZACION modo chaqueta el nivel «baja» usa `p_baja = min(Psat(T_est) + brecha, p_ref - 1)`.
- **CRI-03:** PAM-06 retirado con todos sus usos; regla `COHERENCIA_BRECHA_RECUPERACION` (`brecha_segura_presion < presion_add_esterilizacion - 3`), rechazo al guardar, aviso SIS-06 y log al cargar.
- **CRI-04:** migración `migrado_cri` con una fila de auditoría `param_ciclo_cambio` por programa, sin SIS-06; rótulo y ayuda «Margen de recuperación sobre Psat» es/en.
- Pruebas nuevas: `tests/test_cri_cascada.py`, `test_cri_recuperacion.py`, `test_cri_coherencia.py`, `test_cri_migracion.py`, `test_cri_planta.py`; barrido `python tests/banco/cri_barrido_planta.py`.
- Documentación: `CLAUDE.md`, `docs/riesgos/registro_riesgos.md` (HAZ-CRI-01/02), `matriz_trazabilidad.md` (REQ-102..REQ-105), bloque CRI en `docs/mis_plans/hoja_pruebas_banco_equipo_pruebas.md`.

## 2. Planta: 16 combinaciones, antes (alpha.26) y después (CRI)

Escenario de `base_planta.md` (desde ESTERILIZACION, modo chaqueta, Líquidos 121 °C con los valores del equipo, Principal 0,6 K baja, desfase heredado 7 kPa, T de carga 121,6 °C, `dp` inicial 20 sin herencia). CIC-04 a 203,0 kPa. «Después» = commit `536f0b56`; tras la corrección `9b758b3d` ningún resultado cambia (los `dp` máximos sí, ver `planta_despues.md`).

| # | Paso | Pérdida | Llenado | Alpha.26 | CRI | P mín antes → después | Aisl. |
|---|---|---|---|---|---|---|---|
| 1 | 0,100 | 0,4 | 4,0 | COMPLETADO | COMPLETADO | 209,9 → 211,7 | 0 → 0 |
| 2 | 0,100 | 0,4 | 1,5 | COMPLETADO | COMPLETADO | 209,5 → 211,7 | 0 → 0 |
| 3 | 0,100 | 0,8 | 4,0 | COMPLETADO | COMPLETADO | 209,4 → 211,6 | 0 → 0 |
| 4 | 0,100 | 0,8 | 1,5 | CIC-04 (T baja) 142 s | CIC-04 (T baja) 235 s | 205,8 → 206,0 | 0 → 0 |
| 5 | 0,030 | 0,4 | 4,0 | COMPLETADO | COMPLETADO | 209,3 → 211,2 | 0 → 0 |
| 6 | 0,030 | 0,4 | 1,5 | COMPLETADO | COMPLETADO | 207,7 → 209,4 | 0 → 0 |
| 7 | 0,030 | 0,8 | 4,0 | COMPLETADO | COMPLETADO | 207,3 → 208,0 | 0 → 0 |
| 8 | 0,030 | 0,8 | 1,5 | CIC-04 (P baja) 23 s | CIC-04 (P baja) 28 s | 202,0 → 202,5 | 0 → 0 |
| 9 | 0,015 | 0,4 | 4,0 | COMPLETADO | COMPLETADO | 208,2 → 207,9 | 0 → 0 |
| 10 | 0,015 | 0,4 | 1,5 | COMPLETADO | COMPLETADO | 204,7 → 206,2 | 0 → 0 |
| 11 | 0,015 | 0,8 | 4,0 | COMPLETADO | COMPLETADO | 203,8 → 204,2 | 0 → 0 |
| 12 | 0,015 | 0,8 | 1,5 | CIC-04 (P baja) 18 s | CIC-04 (P baja) 18 s | 200,5 → 200,7 | 0 → 0 |
| 13 | 0,008 | 0,4 | 4,0 | COMPLETADO | COMPLETADO | 206,2 → 205,4 | 0 → 0 |
| 14 | 0,008 | 0,4 | 1,5 | CIC-04 (P baja) 29 s | CIC-04 (P baja) 34 s | 202,0 → 202,3 | 0 → 0 |
| 15 | 0,008 | 0,8 | 4,0 | CIC-04 (P baja) 18 s | CIC-04 (P baja) 18 s | 200,8 → 201,0 | 0 → 0 |
| 16 | 0,008 | 0,8 | 1,5 | CIC-04 (P baja) 16 s | CIC-04 (P baja) 17 s | 199,5 → 199,6 | 0 → 0 |

Fallan 6 de 16 antes y 6 de 16 después (los mismos). CRI no rescata ninguno: en los 6 la cota de lazo abierto (todo abierto desde el inicio) tampoco sostiene la cámara sobre CIC-04 o la Principal sobre 120,9 °C; son límite físico (pérdida total ≈ 0,93 kPa/s > capacidad estacionaria ≈ 0,90 en 4, 8, 12 y 16; transitorio en 14 y 15). Detalle en `planta_despues.md`. Los 10 que completaban siguen completando, sin aislamientos nuevos.

### Ciclos completos

`python -m pytest tests/test_t33_cas04_planta.py tests/test_pam_planta.py`: alpha.26 64 passed, 13 xfailed; CRI 65 passed, 12 xfailed (sin XPASS). Cambia `test_pam_planta.py::test_desfase_de_sonda_0_6_k_llega_a_esterilizar[liquidos|restrictivo|chaqueta]`, que pasa a cumplir. Los 11 xfail de CAS-04 y el de Instrumental 121 restrictivo chaqueta siguen (timeout de CALENTAMIENTO por A14-M2 o k = 1,07, fuera de alcance). 134 °C sin CIC-16 (`test_134_sin_cic16`, caudal A14 abierto y restrictivo: ≤ 1 aislamiento). Herencia de `dp` en ciclo completo: `test_herencia_dp_en_ciclo_completo` (en producción `CicloState` llama `reset()` al cambiar de fase; `planta_vapor.simular` solo al inicio). Tras la corrección, las pruebas dedicadas (CRI, T33, PAM, esterilización, calentamiento): 723 passed, 12 xfailed.

## 3. Pruebas existentes modificadas y motivo

(`git diff 6b17cb6b..9b758b3d --stat -- tests`: 13 archivos existentes más 5 nuevos.)

| Prueba | Motivo |
|---|---|
| `test_esterilizacion_fase.py` | RECUPERACION mide `brecha_segura_presion` sobre Psat (CRI-02): presiones de entrada/salida ajustadas (Psat + 1,6 no dispara; P_sp − 2,5 ya sale de RECUPERACION). |
| `test_t12_c08_histeresis_recuperacion.py` | `p_ref = Psat + 1,5` en lugar de `Psat − 1,5` (CRI-02). |
| `test_t16_s1_esterilizacion.py` | Consigna de banda CRI-01: `min(P_sp + dp, 350)` con `dp` 8 (≈317,6 kPa) en lugar de `min(P_sp + 8, techo − 2)` (313,2). |
| `test_t33_cascada_chaqueta.py` | `evaluar` pide `ahora`; se retira el parámetro `p_techo` y el tope `techo − 2` de la banda (CRI-01). |
| `test_t33_cas02_esterilizacion.py` | Banda sin `techo − 2` (CRI-01) y nivel «baja» bajo `min(Psat + brecha, P_sp − 1)` (CRI-02); constantes y consignas ajustadas. |
| `test_t33_cas03_calentamiento.py` | Consigna de banda `P_OBJ + margen` sin tope `techo − 2`; `estado.cascada_chaqueta` lleva `dp`. |
| `test_pam_planta.py` | El caso líquidos restrictivo chaqueta sale de la lista de no cumplen (completa con CRI-01). |
| `test_pam_presion_trabajo.py` | Se retiran las pruebas de PAM-06 (pasan a `tests/test_cri_coherencia.py`). |
| `test_t12_c04_migracion_aviso.py`, `test_t12_v12_migracion_reintento.py` | La fila de auditoría de `brecha_segura_presion` (CRI-04) se excluye del conteo de filas `param_ciclo_cambio` de esas migraciones. |
| `test_t28_a12_prevacio.py`, `test_t32_catalogo_migraciones.py` | La marca `brecha_segura_presion` (CRI-04) es la única migración «agregada» extra; los programas de fábrica la repiten en cada carga. |
| `test_t28_a14_m3_brecha.py` | CRI-04 reescribe el archivo una vez (marca `migrado_cri`) y deja `.bak`; ya no se exige archivo idéntico. |

## 4. Hallazgos del revisor

Primera pasada (subagente revisor, sobre CRI-01/02):
- **ALTA-1** (embalamiento de la integral con la consigna saturada): corregida en `9b758b3d` con antiembalamiento condicional.
- **MEDIA-2** (`dp` heredado bajo el margen hace fallar casos que completaban, sensibilidad con `dp` 4: casos 10 y 11): corregida con `max(heredado, margen_chaqueta_est)`.
- **MEDIA-1** (piso de `p_baja`): corregida como MEDIA-B (ver segunda pasada).
- **BAJA-1** (modo cámara sin tope de la brecha): abierta.
- **BAJA-2 y BAJA-3**: abiertas.
- **Residual caso 4 de planta:** corregido con MEDIA-A (ver segunda pasada): `dp` final 20 kPa (antes 133).

Segunda pasada del revisor: sin ALTA nuevas. ALTA-1 y MEDIA-2 verificadas corregidas. Hallazgos nuevos corregidos en `2f35ba33`:
- **MEDIA-A** (windup en «banda» con el actuador saturado, residual del caso 4): `actuador_saturado(pj)` (válvula ON en el tick anterior en «banda» y `pj <= consigna_anterior − HISTERESIS`: solo integra hacia abajo). Precisión: solo cuenta la consigna anterior de «banda»; contando la de «baja» (350) el caso 11 pasaba de COMPLETADO a CIC-04.
- **MEDIA-B** (sin piso de `p_baja`): `PISO_P_BAJA_KPA` = 1,5, `p_baja = max(min(Psat + brecha, P_sp − 1), Psat + 1,5)`, log una vez por fase; brecha ilegible → 1,5 kPa con aviso (constante local `_BRECHA_SEGURA_PRESION_DEFECTO_KPA`; el catálogo no tiene defecto).
- Barrido tras las correcciones: mismos 6 de 16 fallan (límite físico), 0 aislamientos; caso 4 con `dp` final 20 (antes 133); caso 11 completa a 0,9 kPa de CIC-04 (límite). Caso nuevo de pérdida de suministro de 150 s con llenado 0,8 kPa/s: los 3 completan con 0 aislamientos (sin la corrección, aislamientos y CIC-16); con llenado 0 terminan en CIC-04 (límite físico). Pruebas modificadas nuevas: `tests/test_cri_cascada.py`, `test_cri_planta.py`, `test_cri_recuperacion.py` (`git diff 9b758b3d~1..HEAD --stat -- tests`; lista en `planta_despues.md`).
- Residuales abiertos: BAJA-1 (modo cámara sin tope de la brecha frente a la banda PWM), BAJA-2, BAJA-3 y el mínimo del catálogo de `brecha_segura_presion` en 0 (pendiente).

Hallazgo preexistente (no es de CRI): 3 fallos de `tests/test_t12_v12_ventana_referencia_en_cero.py::test_referencia_sin_senal_no_bloquea_la_ventana[0|0.0|nan]` ocurren en `dev` limpio (verificado en worktree); son de CALENTAMIENTO.

Pruebas corridas: dedicadas (CRI, T33, PAM, esterilización, calentamiento), no la suite completa. No se compiló: la compilación beta se hace después de la tanda 35 y del Prion.

## 5. DECISIÓN SIN CONFIRMAR

- Línea base 6/16 fallos en lugar de 7/16: la especificación no fija la temperatura de la carga inicial (§1.4); se usó 121,6 °C. Ninguna variante probada da 7 (`base_planta.md`).
- `KI_CRI` 0,15, `DP_MIN_KPA` 3, `DT_MAX_S` 2.
- `p_baja = min(Psat + brecha, p_ref − 1)` con recorte (registro en el log una vez por fase).
- `ahora` obligatorio en `evaluar` (componente puro con reloj inyectado).
- Herencia de `dp` por diccionario en `estado.cascada_chaqueta`.
- Los valores no finitos de `brecha_segura_presion` o `presion_add_esterilizacion` no se rechazan en CRI-03.
- La marca `migrado_cri` no persiste en `factory/*.json`: la fila de auditoría se repite en cada arranque de los programas de fábrica (mismo hallazgo M3 de la tanda 33); en los de usuario hay una reescritura única con `.bak`.
- Canal `agregadas` para auditar sin SIS-06.
- Principal sin lectura detiene la integral del todo (`congelar`).
- Planta provisional: los resultados de §2 no sustituyen el banco (CRI-00 a CRI-04 de la hoja de pruebas).
- `PISO_P_BAJA_KPA` 1,5; brecha ilegible = 1,5 kPa; saturación del actuador solo contra la consigna de «banda»; caso 11 al límite (0,9 kPa de CIC-04).
- Sin compilar.
