# Informe de la tanda 14 al 17 de octubre de 2026

Instrucción: `docs/mis_plans/instruccion_claude_code_tanda_noche.md`. Estado de la tanda: `docs/informes/tanda/estado.md`. Cada etapa tiene su informe en `docs/informes/tanda/`, con los archivos tocados, los revisores, las decisiones, los pendientes y las comprobaciones manuales detalladas.

- **Ramas:** E-0 en `dev`; T1 a T12 en `dev-noche`.
- **Sin `git push`.** No se tocó hardware ni se compiló firmware.
- **Pruebas:** línea base de 2808; al final, ver la última fila de la tabla.

## 1. Índice de lo hecho

| Etapa | Commit(s) | Pruebas al cerrar | Revisores | Informe |
|---|---|---|---|---|
| E-0 Commits previos (dev) | `39bb723` F1, `d81d763` E6, `1339cd2` docs | 2818 | Sí (E6) | `E0_commits_previos.md` |
| T1 alarmas-parte-a | `e5c96ad` (merge) | 3001 | Sí | `T1_alarmas_parte_a.md` |
| T2 E1b vapor_source | `72d6aa3` | 3023 | — | `T2_vapor_source.md` |
| T3 Sensores (backend) | `74787d8` | 3119 | Sí | `T3_sensores_backend.md` |
| T4 E2 cámara segura | `0211880` | 3133 | Sí | `T4_camara_segura.md` |
| T5 E3 estado seguro | `605cb7d` | 3191 | Sí | `T5_estado_seguro.md` |
| T6 E4 arranque seguro | `120565b` | 3213 | Sí | `T6_arranque_seguro.md` |
| T7 E5 interfaz | `1026bf8` | 3239 | Sí | `T7_ui_e5.md` |
| T8 Modo sin BD | `adb631a` | 3290 | Sí | `T8_modo_sin_bd.md` |
| T9 Menú de instalación | `9df9d2d` | 3294 | Sí | `T9_menu_instalacion.md` |
| T10 Endurecimiento | `7624f18` | 3326 | No (fuera de la lista de la regla 7) | `T10_endurecimiento.md`, `docs/informes/limites_catalogo.md` |
| T11 Programas | `b19234c` | 3343 | Sí (Líquidos) | `T11_programas.md` |
| T12 Opciones F2–F4 | (último commit de `dev-noche`) | 3358 | No (fuera de la lista de la regla 7) | `T12_opciones_f2_f4.md` |

**Revisores:** en todas las etapas de seguridad se corrigieron los hallazgos Altos y Críticos antes del commit. Los Altos de T11 que dependen de decisiones de diseño (sonda Principal en Líquidos) quedan registrados como riesgo (HAZ-LIQ-01) y como decisión para Cristian (§3).

## 2. Bloqueadas

Ninguna. Todas las etapas se cerraron con la suite completa en verde.

## 2b. Decisiones confirmadas por Cristian (2026-10-16)

- **Líquidos (HAZ-LIQ-01): de acuerdo.** Las decisiones se toman con el Principal, con la sonda flexible dentro del líquido; los valores siguen siendo provisionales hasta el banco.
- **Tipo de puerta: cualquier tipo puede ir con cualquier equipo.** Por eso el asistente pide por separado el tipo de equipo y el tipo de puerta. No se agrega una matriz de tipos de puerta por clase; el aviso de cerrojo y de empaque del resumen queda solo como información (D-T9-5 cerrada).
- **Instalación: ok.** Tras el asistente se reinicia el equipo (D-T9-2 cerrada).

## 3. Decisiones sin confirmar (resumen; el detalle y la alternativa están en cada informe)

**Prioridad para Cristian (afectan seguridad o la instalación del 19-oct):**
1. **Líquidos (T11, HAZ-LIQ-01):** el enfriamiento a 80 °C, la rápida, la puerta y la meseta de 15 min se deciden con el Principal (`temp_camara`, fijado en 1.1). Depende de que la sonda flexible esté **dentro del líquido**. Alternativas: exigir `temp_2_camara` como Referencia en Líquidos, o un tiempo mínimo de enfriamiento por carga. Los valores de Líquidos son provisionales; la contrapresión se subió a 250 kPa (SAF-05).
2. **Tipo de puerta y cerrojo (T9, D-T9-5):** no hay una matriz de tipos de puerta por clase. El asistente solo avisa y pide confirmación cuando el tipo elegido no controla el cerrojo.
3. **Estado seguro (T5/T6):** FALLA espera el estado seguro antes de PREPARACION. Tras un reinicio con la cámara no segura, se exige confirmación.
4. **Modo sin BD (T8):** ciclo con confirmación explícita en cada inicio y respaldo JSONL obligatorio (sin respaldo escribible no se inicia). "Continuar sin operador" vuelve al menú, sin sesión.
5. **Apagar equipo (T7):** solo desde la puerta 1 y sin rol. El apagado real de Windows solo ocurre con el ejecutable o con `AUTOCLAVE_APAGADO_REAL=1`.
6. **Instalación (T9):** al terminar el asistente hay que reiniciar el equipo (el backend sigue en ARR_PERFIL). Un perfil inválido se aparta, no se borra.
7. **Catálogo (T10):** límites de `docs/informes/limites_catalogo.md` (temperatura de 1 a 200 °C; tiempos con mínimo 1, salvo los ceros válidos). `valor_anterior_esperado` es opcional.

**Otras:**
- E-0: D-E0-1 a D-E0-4.
- T1: merge `--no-ff`; COM-03 para fallas de tarjeta en ciclo.
- T2: perfil sin `vapor_source` = ambas salidas.
- T3: D-T3-1 a D-T3-5 (Referencias, solo cota inferior; SEN-03; versión de migración).
- T4: tope global de 120 °C.
- T5: D-T5-1 a D-T5-6.
- T6: D-T6-1 a D-T6-4.
- T7: D-T7-1 a D-T7-5.
- T8: D-T8-1 a D-T8-5.
- T9: D-T9-1 a D-T9-5.
- T10: D-T10-1 a D-T10-4.
- T11: D-T11-1 a D-T11-3.
- T12: D-T12-1 a D-T12-4 (vistas dentro de OPCIONES; etiquetas provisionales; la última modificación muestra el login).

## 4. Pendientes principales

**Seguridad o proceso:**
- Líquidos en banco: volumen, equilibrado, enfriamiento y aire residual sin prevacío (T11 TMG-05).
- Vigilar en el banco el corte por calidad de vapor del calentamiento: con una sonda rápida o con fugas puede oscilar entre el 97 % y el objetivo.
- DO1/DO2 (generador): no está definido quién ni cuándo las enciende (T2).
- `/cycle/select` sigue sin sesión y está permitido en FALLA (T3).
- Calibración sin límites de plausibilidad (T3).
- Salida autorizada cuando el estado seguro no puede terminar (CIC-10, T5).
- Validar que SECADO alcanza atm − rango con la bomba y las válvulas cerradas (T5).
- Base de datos que falla en caliente: no activa OPERANDO_SIN_BD (T8 SAF-03).
- El fsync del respaldo sigue en el tick (T8).
- `wizard.py` (ruta tkinter) no escribe `vapor_source` (T9 SAF-02). Hay que definir el punto de entrada de producción y retirar la ruta antigua.
- Significado de `door_id` con dos pantallas en un solo PC, junto con `source_door` (T9 SAF-03).

**Pendientes de producto:**
- Diseño final de los avisos de seguridad (T7), del modo sin BD (T8), del asistente (T9) y de Opciones (T12).
- Catálogo de etiquetas, pasos y decimales de los parámetros (especificación 3).
- Directorio persistente para `cycles/user` (RB-04.5).
- Fase 5 de Opciones (retiro de PySide).
- Revisión lingüística y técnica de todas las traducciones nuevas (`revision_traducciones.md`).

## 5. Comprobaciones manuales de Cristian (para la instalación del 19-oct)

1. **Arranque:**
   - con la tarjeta conectada, ALL_OFF al conectar;
   - un ciclo interrumpido por corte queda como INTERRUMPIDO;
   - si la cámara no es segura, el estado seguro pide confirmación (T6).
2. **NO ABRIR y paro:**
   - con la cámara caliente o presurizada se ve "NO ABRIR" en las dos pantallas;
   - al soltar el paro aparece "Confirmar y llevar a estado seguro" (T4, T5, T7).
3. **Ciclo Instrumental 134 (o 121) completo** en el equipo de pruebas:
   - verificar las fases, el ticket con la temperatura del Principal y el resultado;
   - verificar la apertura de puerta solo con la cámara segura.
4. **Líquidos en banco con vidrio real:**
   - sonda en el líquido;
   - sin prevacío ni secado;
   - enfriamiento con contrapresión de aire comprimido hasta 80 °C antes de la rápida.
5. **Sensores:** asignar los roles desde OPCIONES › Parámetros del ciclo › Sensores de temperatura. Un sensor en uso sin lectura impide iniciar (T3, T12).
6. **Modo sin BD:**
   - con una base no SQLite: se aparta, aparece la marca `BD_BLOQUEADA` y la alarma "Operando sin base de datos";
   - el ciclo pide confirmación y el ticket imprime "SIN OPERADOR / SIN BD";
   - al restaurar la base, los ciclos del respaldo se reimportan (T8).
7. **Instalación:**
   - sin `installation_profile.json`, la puerta 1 abre el asistente;
   - el perfil se escribe con `vapor_source = generator` y `locked`;
   - el resumen indica si hay cerrojo (T9).
8. **Apagar equipo:** solo desde la puerta 1, con la cámara segura (T7).
9. **Parámetros:** como técnico, editar un parámetro en PREPARADO (se guarda y se audita) y verificar que se rechaza durante un ciclo (T10, T12).
10. **Alarmas de la tarjeta:**
    - desconectar el USB en PREPARADO da FALLA recuperable;
    - en ciclo da COM-03 con su causa (T1).
11. **Pantallas:** revisar en el equipo real el tamaño de los textos y de las áreas táctiles de las vistas provisionales (avisos de seguridad, login sin BD, asistente y Opciones).

Siguiente paso para integrar: revisar `dev-noche` (12 commits sobre `dev`) y unirla a `dev` cuando se apruebe. Hacer `git push` solo por decisión de Cristian.
