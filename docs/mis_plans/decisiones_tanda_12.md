# Decisiones — Tanda 12 (correcciones de proceso: CALENTAMIENTO y ESTERILIZACION, 24-oct)

Fuente de verdad de la tanda 12. Pedido de Cristian del 24-oct (C-01..C-13). Las DSC propuestas por el asistente fueron **confirmadas por Cristian el 24-oct (17:21)**, con los ajustes incorporados abajo (marcados "Confirmado 24-oct"). Lo que siga marcado **DSC** es nuevo y está pendiente de revisión.

## Reglas generales
- Presión siempre en **kPa absolutos**. Psat/Tsat solo con `core/runtime/steam.py`: `p_saturacion_kpa(T)` y la nueva `t_saturacion_c(p)` (inversa exacta de la misma ecuación de Antoine; fuera de 99–145 °C / su rango de presión equivalente devuelve el valor calculado sin recortar, igual que `p_saturacion_kpa`; `p<=0` o no finito → `ValueError`).
- Contexto físico confirmado: la cámara se alimenta desde la chaqueta; `temp_camara` (Principal) está en la zona más fría de la cámara (parte inferior, opuesta a la entrada de vapor).
- Cada tarea C-xx con prueba propia (nombre `test_t12_<cxx>_*.py` o dentro del archivo del módulo). Un test existente que falle por la semántica nueva se actualiza y se lista en el informe con el porqué; nunca se borra un test de seguridad.
- Temporizadores con `time.monotonic()`.
- Límites físicos (Confirmado 24-oct para esta tanda: constantes en `catalogo_parametros.py`, una sola fuente): `PRESION_FONDO_ESCALA = 400`, `PRESION_SUMINISTRO = 350` (Confirmado 24-oct: suministro regulado a **40 psig** = 275.8 kPa manométricos + 74.6 kPa de atmósfera local en Bogotá ≈ 350 kPa abs; dejar el cálculo en el comentario), `PRESION_ALIVIO_CAMARA = 385`, `PRESION_ALIVIO_CHAQUETA = 385` kPa abs. El suministro (350) solo genera advertencias, nunca rechazo; el rechazo es por alivio (385, por debajo del fondo de escala 400). **Deuda registrada (DEU-01):** estos límites deben venir del perfil de instalación o de Parámetros del equipo (rango del transductor, regulador, alivios), con estos valores como predeterminados; el suministro en absoluto depende de la atmósfera del sitio (40 psig a nivel del mar ≈ 377 kPa abs). No se implementa en esta tanda; va al índice.
- **Líquidos (Confirmado 24-oct):** C-02 y C-03 se aplican solo con `globals.tipo_carga = "solido"` (defecto). Con líquidos el Principal es la sonda del líquido, que va minutos detrás del vapor: la coherencia T–P nunca se cumpliría (timeout) y la falla de saturación dispararía siempre. Quedan para el lazo de presión de C-11.

## C-01. `presion_add_calentamiento` es solo techo (CALENTAMIENTO)
1. `p_obj = Psat(T_obj)` (sin sumar `presion_add`). Afecta a `duty_proximidad`, `sobrepaso` y a los logs.
2. Entrada a ESTABLE_PREESTERILIZACION: `T >= T_obj` y `P >= p_obj - 2 kPa`.
3. Banda de sostenimiento: `T_obj <= T <= T_obj + rango_temp_estabilizacion` y `p_obj - 2 <= P <= Psat(T_obj) + presion_add` (más C-02).
4. Techo independiente: `P >= Psat(T_obj) + presion_add` → duty 0 (hoy es `Psat + 2·presion_add`).
5. `duty_calidad_vapor`: exige `P >= Psat(T) - 2 kPa` (sin sumar `presion_add`).
6. La tolerancia de 2 kPa es constante de módulo `_TOLERANCIA_PSAT_KPA = 2.0`.

## C-02. Coherencia T–P para entrar a esterilizar (solo sólidos)
Se agrega a la banda de sostenimiento (C-01.3): `|Tsat(P) - T_principal| <= 1.0 K` (constante `_COHERENCIA_TP_K = 1.0`). Fuera de coherencia = fuera de banda: reinicia la ventana y arma el timeout de recuperación existente. Log con Tsat(P), T y la diferencia.

## C-03. Falla de saturación durante la exposición (ESTERILIZACION, solo sólidos)
1. `dT = Tsat(P) - T_principal`.
2. `dT > +2 K` sostenido 5 s → FALLO, alarma nueva "aire / gases no condensables en la cámara".
3. `dT < -2 K` sostenido 5 s → FALLO, alarma nueva "vapor sobrecalentado o falla de la sonda".
4. Alarmas nuevas en `state_machine/alarms/catalogo.py` con los siguientes códigos CIC libres, texto es/en, mismo mecanismo que CIC-11 (`self.alarma_fallo = (CIC_xx, {...})` + `motivos_fase`). Umbral ±2 K en constante de módulo.

## C-04. Bowie & Dick de usuario y validación de `presion_add`
1. `cycles/user/bowe_dick.json`: `presion_add_calentamiento` 99 → **9** (confirmado).
2. Catálogo: `presion_add_calentamiento` y `presion_add_esterilizacion` máximo **30** kPa.
3. Coherencia al guardar (y al cargar, vía `errores_programa`), para todo tipo de carga, con `techo = Psat(temperatura_calentamiento) + presion_add_calentamiento` y `techo = Psat(temperatura_esterilizacion) + presion_add_esterilizacion` (Confirmado 24-oct, mismo criterio que la chaqueta):
   - **se rechaza** si el techo es `>= 385` (alivio de cámara; queda por debajo del fondo de escala 400), con mensaje que da el valor máximo admisible;
   - entre 350 (suministro) y 385 se guarda con **advertencia no bloqueante** ("la cámara no alcanzará el techo de presión: la válvula de vapor de cámara quedará abierta en ese tramo") y se registra en el log al iniciar el ciclo.
4. Programa ya instalado con `presion_add_* > 30` (Confirmado 24-oct): `migrar_parametros` lo baja a 9 al cargar y además:
   - registra el cambio en la **auditoría de parámetros** (programa, parámetro, valor anterior y nuevo, origen "migración tanda 12");
   - activa un **aviso no bloqueante** (código nuevo del catálogo de alarmas, texto es/en) que aparece en la bandeja de Preciclo y en la campana (`PanelNotificaciones`), para que técnico/ingeniero lo revise. No basta el log.
   Este mismo mecanismo (auditoría + aviso) es el de "migración correctiva" que usa C-05.9. Un programa que tras migrar siga violando la regla 3 sigue el camino actual de programa inválido (no debe romper el arranque).
5. Ningún programa de fábrica puede quedar rechazado (prueba existente de T10).

## C-05. Chaqueta acoplada al programa (`_mantener_chaqueta`, CICLO)
1. `techo_camara = Psat(T_est) + presion_add_esterilizacion`.
2. `consigna = max(Psat(T_est + delta_temp_chaqueta), techo_camara + margen_flujo_chaqueta)`.
3. Parámetros nuevos en `globals` de los 8 JSON: `delta_temp_chaqueta` = 1.5 K (clase diferencia, 0–5) y `margen_flujo_chaqueta` = 15 kPa (clase diferencia, 0–40). Migración: programa sin las claves → valores por defecto.
4. Banda fija **±10 kPa** (constante `_BANDA_CHAQUETA_KPA`): ON si `P < consigna - 10`, OFF si `P > consigna + 10`, sin cambio dentro.
5. Coherencia al guardar/cargar (Confirmado 24-oct): solo se **rechaza** si `consigna + 10 >= 385` (alivio de chaqueta), con mensaje que da la consigna calculada. Que la consigna quede **por encima del suministro (350) está permitido**: solo significa que `vapor_chaqueta` queda abierta durante todo el proceso. En ese caso, al guardar se devuelve una advertencia no bloqueante ("la válvula de vapor de chaqueta quedará abierta durante el ciclo") y se registra en el log al iniciar el ciclo; no se rechaza ni se migra nada.
6. Ejemplo de prueba: 134 °C, `presion_add` 9 → techo 311.3, consigna ≈ 326.3 kPa (≈ 136.6 °C). 121 °C/11 → ≈ 230.3 kPa.
7. Se mantiene todo lo demás de `_mantener_chaqueta` (secado excluido, enfriamiento modos 4/5, sin dato → OFF, SUM-06).
8. Confirmado 24-oct: `globals.presion_chaqueta` / `rango_presion_chaqueta` siguen rigiendo PREPARACION/PREPARADO (`control_banda.py`) sin cambios de control; en CICLO los reemplaza la consigna calculada. La consigna se registra en el log al iniciar el ciclo.
9. Confirmado 24-oct: a `presion_chaqueta` y `rango_presion_chaqueta` se les aplica la misma regla que a la consigna (C-05.5): se rechaza si `presion_chaqueta + rango_presion_chaqueta >= 385`; por encima de 350 solo advertencia no bloqueante. Los de fábrica (300 + 50) y los de usuario `instrumental_134` / `bowe_dick` (350 + 25 = 375) quedan válidos: **no se modifican ni se migran**.

## C-06. temp_ref como Referencia en sólidos de fábrica — NO se implementa (Confirmado 24-oct)
**Hallazgo menor registrado (PRG-01), no se implementa en esta tanda:** al cargar un programa, validar que cada rol asignado (Principal/Referencia) corresponda a una sonda cableada en el perfil de instalación; si no, rechazar el programa o pasar el rol a No en uso con aviso. Va al índice como pendiente.

## C-07. Margen de control y debounce por tiempo (ESTERILIZACION)
1. `brecha_segura_temperatura` 0.3 → **1.0 K** en los 8 JSON (el control apunta a T_est + 1 K, dentro de la banda +3 K).
2. Las 4 fallas (temp alta/baja, pres alta/baja) y las de C-03 pasan de 3 lecturas a **5 s continuos** (`_DEBOUNCE_FALLA_S = 5.0`, monotonic). La condición debe mantenerse sin interrupción; una lectura dentro de rango reinicia el conteo.

## C-08. Histéresis RECUPERACION ↔ PWM y techo en RECUPERACION
1. Entrada a RECUPERACION: igual que hoy (`T < T_est + brecha_segura_temperatura` o `P < Psat(T_est) - brecha_segura_presion`), reacción inmediata.
2. Salida a PWM_ACTIVO (Confirmado 24-oct): `T >= T_est + brecha_segura_temperatura + 0.3 K` **y** `P >= Psat(T_est) - brecha_segura_presion + 1.0 kPa` (constantes `_HIST_RECUP_TEMP_K`, `_HIST_RECUP_PRES_KPA`). Histéresis solo en la salida para no retrasar la reacción.
3. En RECUPERACION, `P >= P_control_max` (`Psat(T_est) + presion_add_esterilizacion`) → vapor OFF, igual que en PWM.

## C-09. Tope de calidad de vapor en grados, no en %
`_FACTOR_TOPE_TEMPERATURA = 0.97` se reemplaza por `T >= T_obj - 3 K` (constante `_MARGEN_CALIDAD_VAPOR_K = 3.0`).

## C-10. Sin exposición sin medición válida
1. Verificar (prueba) que en CicloState la vigilancia SENSOR_AUSENTE (§4 de `ciclo.py`) corre **antes** de `fase.update()` en el mismo tick y que con el Principal o la presión sin lectura el ciclo pasa a FALLO sin que ESTERILIZACION cuente ese tick.
2. Defensa propia en la fase (Confirmado 24-oct): si `temp` (Principal) o `pres` es `None`, el fin de exposición se corre el tiempo transcurrido sin datos (mismo efecto que `pausar_exposicion`, sin sumarlo al tope de `pausa_total_s` de CIC-11). Prueba unitaria.

## C-11 [SPEC] Líquidos — control en dos lazos
Solo especificación en `docs/mis_plans/planeacion_liquidos_dos_lazos.md`: lazo de cámara por presión (`vapor_camara` hacia `Psat(T_est + offset)`); la sonda del líquido solo decide inicio/pérdida de exposición y F0, no mueve la válvula. Hallazgo de origen: LIQ-01 (control de vapor con la temperatura del líquido → oscila y falla por presión alta). Incluir (Confirmado 24-oct): en líquidos, la coherencia temperatura–presión (C-02) y la falla de saturación (C-03) usan una **sonda en el vapor** (`temp_ref` sin contacto con el líquido), nunca la sonda del líquido; especificar el rol/asignación de sensor necesario y qué pasa si esa sonda no está cableada o no lee.

## C-12 [SPEC] Líquidos — eliminación de aire
En el mismo documento: Opción A (purga con drenaje abierto hasta `temp_ref > 95 °C`) y Opción B (prevacío solo con el líquido frío), con riesgos, parámetros, interlocks y recomendación. Hecho de origen: sin quitar el aire, la cámara a 226 kPa queda en ~106 °C reales.

## C-13. Referencia fuera de banda durante la exposición
1. Banda: `[T_est - brecha_error_temperatura, T_est + rango_temperatura_ester]` para cada Referencia en uso con lectura.
2. Excursión confirmada tras **5 s continuos** fuera de banda (Confirmado 24-oct: mismo debounce que C-07, por el ruido de la PT100). Al confirmarse: el conteo de exposición se **detiene**.
3. Al volver a la banda (primera lectura dentro), el conteo se **reinicia desde cero** (`_timer_fin = now + tiempo_esterilizacion`). F0 NO se reinicia.
4. El control sigue igual (no falla). Si no vuelve a la banda en `timeout_excursion_referencia` (parámetro nuevo, sección `esterilizacion`, 5 min, rango 1–30) → FALLO con alarma nueva (código CIC libre, es/en).
5. Cada excursión se registra en el ticket vía `estado.avisos_ciclo` (clave i18n nueva): sensor, duración (s) y temperatura mínima (y máxima si salió por arriba). Reemplaza al aviso único de CIC-09 para esa Referencia; CIC-09 sigue activándose una vez por sensor.
6. Sin cambios: Principal fuera de banda → FALLO.
7b. **Referencia sin lectura — opción B (Confirmado 24-oct), reemplaza la DECISIÓN SIN CONFIRMAR de la tanda §1.1:**
   - Principal sin lectura (o la presión) → FALLO SEN-02 / código de presión, **sin cambios**.
   - Referencia sin lectura → el ciclo **continúa** con las sondas que sí leen y se activa una alarma no bloqueante (SEN-02 en variante no bloqueante o código nuevo, con el sensor; se elige lo que no rompa el catálogo existente). `ciclo.py` §4 debe distinguir Principal de Referencia.
   - El ciclo queda marcado **"NO CONFORME: punto de referencia sin verificar"** (bandera en `CicloState`/estado, clave i18n es/en): aparece en el ticket y en el registro del ciclo aunque la Referencia vuelva a leer.
   - Mientras una Referencia no lee, no participa en C-13 (no detiene ni reinicia la exposición) ni en la ventana de CALENTAMIENTO (`refs_en_consigna` ignora las Referencias sin lectura en vez de bloquear la ventana).
   - DSC: un ciclo NO CONFORME no usa apertura automática (`_mantener_apertura_automatica`): pasa al flujo manual de confirmación.
7. El tiempo restante que muestra la UI (`progreso_ciclo.py` / `ciclo.py:287`) debe reflejar el reinicio; verificar y probar.
8. Con F0 activo, el timeout 2×`tiempo_esterilizacion` no cambia (DSC): reinicios repetidos terminan en FALLO por ese timeout.
