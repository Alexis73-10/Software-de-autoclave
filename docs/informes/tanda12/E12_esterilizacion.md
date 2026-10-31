# E12 — ESTERILIZACION (tanda 12)

Rama `tanda-12-e12`, desde `tanda-12` (c462114). Fecha: 24-oct-2026.

## Commits
- `c0fd654` feat(tanda12-e12): C-03, C-07.2, C-08 y C-10 en ESTERILIZACION
- `fa8dc37` feat(tanda12-e12): C-13 excursión de Referencia y C-13.7b Referencia sin lectura
- (este informe) docs(tanda12-e12)

## Qué se hizo, por punto

### C-07.2 Debounce por tiempo
`esterilizacion.py`: `_DEBOUNCE_FALLA_S = 5.0` (monotonic). Las 4 fallas del Principal (temp alta/baja, pres alta/baja, siempre contra `T_est` fija) y las de C-03 exigen 5 s continuos; una lectura dentro de rango reinicia el conteo (`_sostenida()`). Se eliminó `_DEBOUNCE_LECTURAS`. La confirmación de una excursión de Referencia (C-13.2) usa la misma constante.

### C-03 Falla de saturación (solo sólidos)
`dT = t_saturacion_c(P) - T_principal`; `dT > +2 K` 5 s → FALLO **CIC-12** (aire / gases no condensables); `dT < -2 K` 5 s → FALLO **CIC-13** (vapor sobrecalentado o falla de la sonda). Constante `_UMBRAL_SATURACION_K = 2.0`. Mecanismo de CIC-11: `self.alarma_fallo = (CIC_xx, {...})` + motivo de `motivos_fase` (`est_aire`, `est_sobrecalentado`). Se aplica si `globals.tipo_carga != "liquido"` (defecto "solido"). Se evalúa después de las 4 fallas clásicas (si coinciden en el mismo tick, gana la clásica).

### C-08 Histéresis y techo en RECUPERACION
- Entrada a RECUPERACION sin cambios (inmediata).
- Salida a PWM: `T >= T_est + brecha_segura_temperatura + 0.3` y `P >= Psat(T_est) - brecha_segura_presion + 1.0` (`_HIST_RECUP_TEMP_K`, `_HIST_RECUP_PRES_KPA`).
- En RECUPERACION, `P >= P_control_max` → vapor OFF, **con histéresis de 2 kPa** (`_HIST_TECHO_KPA`): queda OFF hasta `P < P_control_max - 2`. Ver DECISIÓN SIN CONFIRMAR 1.

### C-10 Sin exposición sin medición válida
- C-10.1: verificado con pruebas sobre `CicloState`: §4 corre antes de `fase.update()`; con el Principal en `None` → FALLO SEN-02 y la fase no se llama (el fin de exposición no cambia); con la presión en `None` → SEN-04 igual.
- C-10.2: en la fase, si `temp` o `pres` es `None`, se abre un tramo; al volver la lectura, `_timer_fin` se corre lo que duró (desde el primer tick sin lectura), sin sumar a `pausa_total_s` (tope de CIC-11). Se acumula en `fase.sin_lectura_s` (solo informativo). El encabezado del módulo ya no dice "riesgo aceptado": queda la defensa propia y la falla de CicloState.

### C-13 Referencia fuera de banda
- Banda `[T_est - brecha_error_temperatura, T_est + rango_temperatura_ester]` por Referencia con lectura.
- Excursión confirmada a los 5 s continuos (desde la primera lectura fuera) → conteo detenido (`exposicion_detenida`). CIC-09 se sigue activando una vez por sensor y ciclo, al confirmarse.
- Al volver (primera lectura dentro) y sin otra excursión activa: `_timer_fin = now + tiempo_esterilizacion`. F0 no se toca; `_timer_timeout_max` (2×tiempo, F0) no cambia (C-13.8): reinicios repetidos terminan en `ESTERILIZACION_TIMEOUT_F0` (prueba).
- Sin retorno en `esterilizacion.timeout_excursion_referencia` (defecto en código 5 min, recorte 1–30, inválido → 5), contado desde la primera lectura fuera → FALLO **CIC-14**.
- Ticket (C-13.5): al cerrarse cada excursión confirmada (o al fallar la fase con ella abierta) se agrega a `estado.avisos_ciclo` `{"clave": "ticket_ciclo.aviso_excursion", "sensor", "duracion" (s), "temp_min"}`, o `aviso_excursion_alta` con `temp_max` si salió por arriba. Reemplaza al aviso único `aviso_uniformidad` (ya no se escribe; la clave i18n se conserva para reimprimir ciclos viejos). `ticket_formatter.aviso_ticket` ahora convierte a la unidad del ticket toda clave `temp`/`temp_*`.
- C-13.6: Principal fuera de banda sigue fallando (prueba).
- C-13.7 (tiempo restante de la UI): la fase publica `estado.exposicion_restante_s` (con la exposición detenida vale el tiempo completo, porque volverá a empezar). `progreso_ciclo.armar_progreso(..., restante_exposicion_s=None)` y `tiempo_restante(..., restante_activa=None)` lo usan con la esterilización activa en vez de la estimación por historial. **Falta pasarlo desde el endpoint** (ver NECESITA DE OTRA ETAPA 1).

### C-13.7b Referencia sin lectura (opción B)
`ciclo.py` §4: Principal sin lectura → SEN-02 como hoy (solo lenta; si también falta una Referencia, se listan ambas). Presión sin lectura → como hoy. **Solo Referencias sin lectura (None o 0)** → el ciclo continúa: `_marcar_referencias_sin_lectura()` activa **SEN-11** (AVISO, no bloquea, despeje manual, con el sensor y la fase) y agrega `{"clave": "ticket_ciclo.no_conforme_referencia", "sensor"}` a `estado.avisos_ciclo`, una vez por sensor y ciclo. La bandera es la propiedad `CicloState.no_conforme`, derivada de `avisos_ciclo` (que `reset()` ya vacía): persiste aunque la Referencia vuelva a leer y llega al ticket, a la base (`avisos_ticket`) y al respaldo sin tocar `CycleLogger`. `_mantener_apertura_automatica()` sale de inmediato si `no_conforme` (flujo manual). En la fase, una Referencia sin lectura no participa en C-13. Se eligió código nuevo SEN-11 y no una variante de SEN-02 (SEN-02 es FALLO_CRITICO bloqueante; una variante habría cambiado su semántica en el catálogo y en el historial).

### Catálogo, i18n, motivos
- `catalogo.py`: `SEN_11`, `CIC_12`, `CIC_13`, `CIC_14` (CIC: ALARMA, bloquea, manual, como CIC-11), cada uno junto a sus vecinos SEN/CIC, sin reordenar.
- `es.json`/`en.json`: `alarmas.SEN-11/CIC-12/CIC-13/CIC-14`; `motivos_fase.est_aire/est_sobrecalentado/est_excursion_referencia`; `ticket_ciclo.aviso_excursion/aviso_excursion_alta/no_conforme_referencia` (es: "NO CONFORME: punto de referencia sin verificar (…)").
- `motivos_fase.CODIGOS`: los 3 códigos nuevos.
- `ciclo.py` (`_registrar_fallo_de_fase`): acepta `alarma_fallo` con CIC-11..14 (`_ALARMAS_PROPIAS_FASE`). Import en línea propia para no chocar con J12.

## Pruebas
`autoclave.__file__` = `C:\Users\tecni\Documents\codigo_autoclave\.claude\worktrees\agent-a03ac33aa2e6eeaa0\src\autoclave\__init__.py`.

Nuevas (62, todas con reloj monotonic simulado; apoyo en `tests/t12_e12_apoyo.py`):
- `test_t12_c03_saturacion_esterilizacion.py` (7): +2.5 K 4.9 s no falla / 5.0 s CIC-12; −2.5 K 5 s CIC-13; lectura dentro reinicia; ±2 K no falla; líquido no aplica; sólido explícito; CicloState registra CIC-12/13/14.
- `test_t12_c07_debounce_tiempo_esterilizacion.py` (13): cada una de las 4 fallas: 10 lecturas en 4.9 s no fallan, 5 s fallan, una lectura dentro reinicia.
- `test_t12_c08_histeresis_recuperacion.py` (11): T oscilando entre T_est+1.0 y +1.2 no conmuta (desde RECUPERACION y desde PWM); histéresis de T y de P; techo en RECUPERACION; histéresis del techo (T = 135.0 con P oscilando ±0.3 alrededor del techo 134/9: OFF sostenido; vuelve a ON bajo techo − 2).
- `test_t12_c10_sin_medicion.py` (5): 60 s sin datos corren el fin 60 s (sin tocar `pausa_total_s`); presión `None` igual; no completa sin datos; CicloState: Principal `None` → SEN-02 sin llamar a la fase; presión `None` → SEN-04.
- `test_t12_c13_excursion_referencia.py` (15): >5 s detiene y al volver reinicia desde cero; <5 s no detiene; no termina con Referencia fuera aún sin confirmar; F0 y su timeout no cambian; reinicios repetidos con F0 → timeout F0; sin retorno → CIC-14 (y la excursión abierta queda en el ticket); defecto/recorte del timeout; ticket con sensor, duración y mínima (es y en, °F); máxima si sale por arriba; CIC-09 una vez y sin aviso de uniformidad; Principal fuera sigue fallando; Referencia sin lectura no detiene; excursión confirmada que pierde lectura sigue su timeout; restante de la UI (fase y `progreso_ciclo`).
- `test_t12_c13_7b_referencia_sin_lectura.py` (11): continúa sin protocolo; 0 = sin lectura; SEN-11 AVISO no bloqueante con el sensor; NO CONFORME una sola vez y aunque vuelva a leer; textos es/en y pie del ticket; reset limpia; Principal → SEN-02 (solo lenta); Principal y Referencia → SEN-02 con ambas; presión → SEN-04; apertura automática: conforme sí, NO CONFORME no.

Corridas: los 204 módulos de `tests/` que importan lo tocado (esterilización, `ciclo`, catálogo, motivos, ticket, progreso, i18n) + las nuevas, con `-n auto`: tras corregir las existentes de abajo, **todo en verde** (corrida completa previa: 4212 passed, 9 skipped, 13 fallas esperadas, todas corregidas; recorrida de los 5 módulos corregidos: 561 passed; recorrida final de E12 + fase + progreso + ticket: 177 passed). No se corrió la suite completa (regla 9).

## Pruebas existentes modificadas (y por qué)
- `tests/test_esterilizacion_fase.py`: reloj simulado (`_Reloj`/`_reloj`); 6 pruebas de falla pasan de "3.ª lectura" a 5 s continuos (renombradas `..._sostenida_5_s`, la de brecha de presión conserva su nombre); `test_presion_dentro_del_margen...` entra primero a PWM (por la histéresis de C-08.2). Motivo: C-07.2 y C-08.
- `tests/test_t3_sensores_ciclo.py`: `test_referencia_sin_lectura_tambien_falla` → `test_referencia_sin_lectura_no_falla_y_queda_no_conforme` (C-13.7b); `test_referencia_fuera_de_rango_alerta_una_vez_y_no_falla` con reloj (5 s); `test_cic09_anota_aviso_del_ciclo` ahora espera `aviso_excursion` (C-13.5).
- `tests/test_t2_p2_principal_perdido.py`: `test_referencia_perdida_usa_el_protocolo_normal` → `test_referencia_perdida_no_aborta_ni_ejecuta_el_protocolo` (C-13.7b). Las de Principal perdido (solo lenta) siguen iguales.
- `tests/test_alarmas_catalogo.py`: ejemplos y niveles de SEN-11/CIC-12/13/14.
- `tests/test_i1_i18n_backend.py`, `tests/test_i4_ingles_backend.py`: valores de ejemplo `tsat`/`dt` (las plantillas nuevas usan `:.1f`).
Ningún test de seguridad se borró.

## DECISIONES SIN CONFIRMAR
1. **Histéresis del techo en RECUPERACION (`_HIST_TECHO_KPA = 2.0`)**, pedida por la sesión principal a partir del hallazgo de L12, verificado con `steam.py`: con 134/9, `P_control_max = 311.26 kPa` y su Tsat es **135.01 °C**; con 134/11, 135.23 °C; la salida de C-08.2 exige 135.3 °C. En vapor saturado la fase nunca sale de RECUPERACION y, sin histéresis, C-08.3 conmutaría la válvula en cada tick en el techo. Solo reduce vapor; no cambia C-08.1/C-08.2.
2. **Referencia sin lectura marca NO CONFORME en cualquier fase del CICLO** (no solo en CALENTAMIENTO/ESTERILIZACION), igual que antes fallaba en cualquier fase. Es lo más conservador; la alternativa sería limitarlo a las fases que verifican el punto de referencia.
3. **Sin lectura en la fase = estado congelado de las fallas**: un tick con Principal/presión en `None` no reinicia ni confirma el debounce de 5 s; si al volver la condición sigue fuera y el conteo ya pasó 5 s, falla en ese tick. (En la práctica CicloState falla antes con SEN-02/SEN-04.)
4. **Referencia sin lectura durante una excursión**: si aún no estaba confirmada, se descarta; si estaba confirmada, la exposición sigue detenida y su timeout (CIC-14) sigue corriendo — solo una lectura dentro de la banda la cierra. Evita que la fase quede detenida sin límite (sin F0 no hay otro timeout).
5. **No se termina la exposición con una Referencia fuera de banda aunque la excursión no esté confirmada** (espera como mucho 5 s a confirmarla o a que vuelva). Así ninguna ruta libera la exposición con una sonda fuera de banda.
6. El timeout de excursión se cuenta desde la **primera lectura fuera** (no desde la confirmación). La duración del ticket, igual.
7. SEN-11: AVISO, no bloquea el inicio, **despeje manual** (queda en la bandeja hasta reconocerla aunque la Referencia vuelva).
8. `tipo_carga` desconocido se trata como sólido (C-03 se vigila).

## PREGUNTAS PARA CRISTIAN
1. (De la DSC 1) ¿Se acepta la histéresis de 2 kPa del techo en RECUPERACION, o se ajusta la salida de C-08.2 al techo (p. ej. salir a PWM también si `P >= P_control_max - x` con T ≥ T_est + brecha)? Con los valores actuales, en vapor saturado la exposición corre siempre en RECUPERACION pegada al techo (ON/OFF por la histéresis), nunca en PWM.
2. Sin F0 no hay timeout global de la fase: excursiones repetidas, cada una menor que `timeout_excursion_referencia`, pueden reiniciar la exposición indefinidamente. ¿Se quiere un tope (p. ej. 2×tiempo también sin F0, o un número máximo de reinicios)?
3. ¿El ticket de un ciclo NO CONFORME debe cambiar el "Estado" (hoy dice COMPLETADO más la línea "NO CONFORME…") o llevar la marca "CARGA NO ESTÉRIL"?

## NECESITA DE OTRA ETAPA (lo resuelve la sesión principal al unir)
1. **C-13.7, endpoint** (`backend/server.py`, sin dueño en la tabla; no lo toqué): en `get_current_cycle_progress`, pasar el restante de la fase:
   ```python
   **progreso_ciclo.armar_progreso(aplicables, filas, fase_ciclo, transcurrido, referencias,
       restante_exposicion_s=getattr(context.estado, "exposicion_restante_s", None)),
   ```
   Sin esto la UI sigue mostrando la estimación por historial (no refleja el reinicio). `EstadoAutoclave` no usa `__slots__`; la fase crea el atributo en `reset()`. Conviene declararlo `None` en `core/runtime/status.py` (tampoco es mío).
2. P12 (`calentamiento.py`): `refs_en_consigna` debe ignorar Referencias sin lectura (C-13.7b en la ventana). CicloState ya no aborta por ellas, así que hasta que P12 lo haga, una Referencia sin lectura **bloquearía** la ventana de CALENTAMIENTO (terminaría en su timeout, no en una liberación indebida).
3. Choques de unión previsibles: `catalogo.py` y `es.json`/`en.json` (J12 agrega SIS-06; mis entradas van junto a SEN-10 y CIC-11, sin reordenar); `tests/test_alarmas_catalogo.py` (`_EJEMPLOS` y niveles, si J12 también los toca); `states/ciclo.py` (toqué: import en línea propia, `_ALARMAS_PROPIAS_FASE`, `_registrar_fallo_de_fase`, §4 de `run()`, la nueva sección NO CONFORME antes de `_mantener_apertura_automatica` y esta última; no toqué `_mantener_chaqueta` ni `reset()`).
4. `CLAUDE.md` (Z): ESTERILIZACION ya no tiene "riesgo aceptado" por sensor en `None`; debounce por tiempo; C-03/C-08/C-13; la histéresis del techo.

## Pendientes
- Hoja de banco (L12): la exposición en RECUPERACION pegada al techo (pregunta 1) es lo primero que se verá el lunes en la gráfica de vapor de cámara.
