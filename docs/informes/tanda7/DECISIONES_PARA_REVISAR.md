# Tanda 7 — Decisiones para revisar

## Resumen
- **Instalar `entrega/2026-10-22_b/`** (compilación B). Respaldo: la A.
- Unidas a `dev`: L1, P1, M1, C2, M2, Q1 (antes de K2) y D2 (después de K2). Suite final en verde.
- Q1: revisores sin Altos/Críticos abiertos tras las correcciones; SEN-01 (Alto preexistente en `dev`) va como PREGUNTA (SP-7).
- Las decisiones de cada etapa están en su informe (secciones "DECISIONES SIN CONFIRMAR"); aquí van las de la sesión principal.
- Preguntas para Cristian y problemas conocidos para mañana: en el índice `docs/informes/informe_tanda_2026-10-22_t7.md`.

Formato: decisión, motivo, alternativa, commit, cómo revertir.

## Sesión principal (A0, K1)

### SP-1. Tanda 6 tratada como cerrada aunque su `estado.md` dice Z "En curso"
- **Decisión (DECISIÓN SIN CONFIRMAR):** no se aplicó la regla 10 (tanda 6 activa).
- **Motivo:** `tanda-6` contenida en `dev`; commits de cierre f631f35/1d6cf98 empujados (dev = origin/dev); árbol sin cambios rastreados; el lanzador registró "Tanda 6 cerrada" a las 23:46. Los archivos con fecha reciente eran los del propio cierre, ya commiteados.
- **Alternativa:** trabajar solo en worktrees desde `tanda-6` hasta las 12:30.
- **Commit:** 0cfb4cc. **Revertir:** no aplica (solo se creó `tanda-7` desde `dev`).

### SP-2. Specs compilados: `Autoclave.spec` y `GeneradorCodigos.spec`
- **Decisión:** no se compilaron `AutoclaveBackend.spec` ni `AutoclaveSettings.spec`.
- **Motivo:** el ejecutable único (`exe_unico.py`, tanda 2 R1 / tanda 4) los reemplazó; el generador hace falta para el código de activación del día.
- **Alternativa:** compilar también los viejos (no se usan en la instalación).
- **Revertir:** compilar el spec adicional.

### SP-3. Prueba de humo con `--portable`
- **Decisión:** se respondió "No" a "¿Instalar Autoclave en este PC?" y se probó con `--portable`, para no instalar software en el PC de desarrollo (regla 3).
- **Alternativa:** instalar en Archivos de programa (prohibido en esta tanda).

### SP-4. M2 se ejecuta
- **Decisión:** la decisión 1.4 decía que el Mantenimiento E1 no entraba; Cristian corrigió la instrucción a las 00:30 (sin commit, en el árbol) para que E1 entre. Se commiteó su corrección (e8e42d7) y se lanzó M2.

## Sesión principal (reanudación del 22-oct, 06:10)

### SP-5. Suite "tras cada unión" corrida en paralelo sobre cada punto de unión
- **Decisión:** se hicieron las 6 uniones (L1→P1→M1→C2→M2→Q1) en una rama de ensayo (`tanda-7-integ`) y se corrió la suite completa en cada commit de unión, las 6 a la vez, en worktrees separados. Todas en verde. Después se avanzó `tanda-7` con `--ff-only` hasta esos mismos commits.
- **Motivo:** la regla pide la suite en verde tras cada unión; en serie eran ~2 h, en paralelo 20 min. Los commits probados son exactamente los que quedaron en `tanda-7`.
- **Revertir:** no aplica.

### SP-6. Choque de numeración REQ-19 en `matriz_trazabilidad.md`
- **Decisión:** M1 y Q1 usaron los dos REQ-19. Se conservó Q1 en REQ-19 a REQ-26 y la fila de M1 pasó a **REQ-27** (también en su informe).
- **Motivo:** Q1 cita su rango (REQ-19 a REQ-26) en más documentos.

### SP-7. Q1 se une con un Alto preexistente abierto (SEN-01) — DECISIÓN SIN CONFIRMAR
- **Decisión:** el sensor-role-auditor reportó SEN-01 (ALTO): `convert_pressures` recorta a 0,0 kPa un transductor de presión de cámara sin señal y el ciclo y el protocolo de fallo lo toman como lectura válida. Ese defecto **ya está en `dev`** (no lo introduce Q1, y Q1 no lo empeora). Se une Q1 igual; SEN-01 queda como PREGUNTA PARA CRISTIAN.
- **Motivo:** la regla de los revisores busca que la etapa no introduzca Altos; no unir Q1 no cierra SEN-01, que sigue en `dev`. Corregirlo cambia una transición de ciclo (presión 0 → sensor ausente → protocolo), y lo no definido en transiciones va como pregunta (regla 4).
- **Alternativa:** dejar Q1 en su rama hasta resolver SEN-01.
- **Revertir:** `git revert -m 1 <merge de tanda-7-q1>`.

### SP-8. Correcciones de la revisión de Q1 hechas por un subagente de la sesión principal
- **Decisión:** se corrigieron TMG-01 (Alto: F0 acreditado tras un corte del enlace), SAF-01/SEN-02/TMG-07 (debounce de 3 lecturas para `solo_lenta`), TMG-06/SEN-04, SAF-03, SAF-04/SEN-07, SAF-05 y, tras la re-revisión, RR-01 (F0 no suma durante la pausa por DI vencida). La re-revisión de safety-reviewer y timing-auditor quedó en **0 Altos/Críticos abiertos**. El detalle está en `Q1_preguntas_abiertas.md`, sección "Revisión de la sesión principal".
- **No se cambió:** la regla de `permite_salir_de_falla` con R1-P4 (pregunta), ni la pausa T2-a en desconexión total de menos de 5 s (pregunta).

### SP-9. `docs/mis_plans/planeacion_mantenimiento.md` sin rastrear en la carpeta principal
- **Decisión:** el archivo sin rastrear era idéntico byte a byte al que commiteó M2 (c38e29c). Se movió a `C:\Users\tecni\Documents\_respaldo_t7\` para poder avanzar `tanda-7`; el contenido queda en git.

### SP-10. Prueba de humo de K2 limitada al paso 1 del asistente
- **Decisión:** la pantalla del PC de la oficina (1536×864) no muestra el teclado en pantalla ni el botón Siguiente de la interfaz de 1200×1920, y el teclado físico no escribe en esos campos. La prueba adicional (solo Piso / Piso laboratorio y paso Cámara) se comprobó con el código de la etiqueta y las pruebas QML de M1, no en la ventana. Queda "verificar en sitio".

### SP-11. Informe de Q1 cerrado por la sesión principal
- **Decisión:** el subagente de correcciones de Q1 dejó su informe sin commit (su suite en segundo plano se cortó). La sesión principal lo completó con el resultado de la suite de la unión (que incluye exactamente su código, 88858a0) y lo commiteó (e7e21f4).
