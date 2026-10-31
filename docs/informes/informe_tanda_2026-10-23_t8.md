**HAY COMPILACIÓN C Y SE RECOMIENDA INSTALARLA: `entrega/2026-10-23_c/` (etiqueta `inst-2026-10-23-c`). En el equipo de pruebas, que ya tiene la B, se actualiza con la sección 8b de `entrega/LEEME_INSTALACION.md` (B → C), incluido el reemplazo a mano de 2 archivos de configuración.** La B queda de respaldo.

# Tanda 8 — Índice (22/23-oct-2026)

## Resumen (10 líneas)
1. Todas las etapas están hechas y unidas a `dev` (5a4b0df) con la suite en verde. Suite final: **6201 passed, 7 skipped, 3 xfailed** (línea base 5382).
2. S1 (★, D8-1): un transductor de presión sin señal ya no se lee como 0 kPa. Detección NAMUR sobre la cuenta cruda, «—» en la interfaz, FALLO propio con venteo solo por la lenta, e inicio bloqueado con «NO ABRIR».
3. S2a y S2b (★, D8-2.6 a 2.16): transiciones del ciclo de las preguntas de la tanda 7, con la planta simulada en los 4 programas y casos nuevos de banco y de riesgos.
4. R8 (★, D8-5.12): Opciones avanzadas = reasignación de E/S, solo para el ingeniero, con reautenticación, verificación por función y bloqueo de inicio hasta verificar (SEN-09).
5. V8a (★ D8-5.7) y V8b: tipo de carga Sólido/Líquido con modos 4/5/0, modos en lista, Reportes por tipo de fallo, barra flotante y textos sin abreviaturas ni mezcla de idiomas.
6. E1: canales de E/S según el perfil, aire atmosférico en modo prueba (★), apagado rechazado, texto final del asistente y LEEME de un monitor. E2: Hospitalario/Laboratorio. N8: Atrás con historial y Cerrar sesión → Login. M8: mantenimiento. U8: correo.
7. L8: lock solo del producto desde un entorno limpio. La C se compiló con él, desde PowerShell. D8: depuración, con 5 funciones muertas retiradas con `safety-reviewer`.
8. D8-3.18 (calibración neutra en la entrega) la hizo la sesión principal en K8: plantilla, `.spec` y verificador. Se comprobó sobre la C.
9. Ensayo B → C sobre una copia: los datos se conservan. Hay que reemplazar a mano `instances\ACV-2026-001.yaml` y `global_params.json`; sin eso no aparecen Cámara 2 ni `descompresion_lenta` (SP-5).
10. Cortes por el límite de uso (12:50-16:00, 17:45-21:00) y dos sesiones que terminaron con subagentes vivos. Desde las 22:11 se trabajó de a 4 sin terminar el turno con subagentes activos. Push: ver la sección "Push".

## Etapas
| Etapa | Estado | Informe |
|---|---|---|
| A0 | Hecha | `tanda8/estado.md` (línea base 5382 p) |
| H8 | Sin objeto (sección de hallazgos vacía) | `tanda8/estado.md` |
| S1 ★ | Unida (revisores sin Altos/Críticos abiertos) | `tanda8/S1_sensor_presion_sin_senal.md`, `tanda8/S1_ensayo_tabla.md` |
| S2a ★ | Unida (revisores sin Altos/Críticos abiertos) | `tanda8/S2a_transiciones_ciclo.md`, `tanda8/S2a_ensayo_tabla.md` |
| S2b ★ | Unida (revisores sin Altos/Críticos abiertos) | `tanda8/S2b_transiciones_ciclo.md`, `tanda8/S2b_ensayo_tabla.md` |
| N8 | Unida (las 6 reglas de navegación del 19-oct cumplen) | `tanda8/N8_navegacion_opciones.md` |
| R8 ★ | Unida (4 vueltas de revisores, 0 Altos/Críticos) | `tanda8/R8_reasignacion_es.md`, `tanda8/R8_ensayo_tabla.md` |
| V8a (★ D8-5.7) | Unida (0 Altos/Críticos) | `tanda8/V8a_observaciones_ui.md` |
| E1 (★ D8-3.19) | Unida (0 Altos/Críticos) | `tanda8/E1_equipo_instalacion.md` |
| E2 | Unida | `tanda8/E2_nombres_familia_modelo.md` |
| M8 | Unida | `tanda8/M8_mantenimiento.md` |
| U8 | Unida | `tanda8/U8_correo.md` |
| L8 | Unida | `tanda8/L8_dependencias.md` |
| D8 | Unida (P10/P11 a medias, ver preguntas) | `tanda8/D8_depuracion.md` |
| V8b | Unida la última | `tanda8/V8b_textos_traducciones.md` |
| K8 | Hecha (compilación C) | `tanda8/K8_compilacion_c.md` |
| Z | Hecha | este índice |

Suites de integración (una por unión): `tanda8/suites/integ_*.log`. Las de R8, E1 y D8 dieron 1 falla, siempre la misma: una prueba vieja que contaba Opciones avanzadas para el técnico. Se ajustó a D8-5.12 (33e4abc) y la suite final quedó en verde.

Decisiones de la sesión principal: `tanda8/DECISIONES_PARA_REVISAR.md` (SP-1 a SP-8). Las de cada etapa están en su informe.

## PREGUNTAS PARA CRISTIAN
**Para la instalación de la C:**
- **SP-5:** ¿el instalador debe refrescar `programa\autoclave\config\instances\` al actualizar, igual que `cycles\factory\`? Hoy hay que reemplazar el archivo a mano (LEEME 8b). Es la misma pregunta que E1-6.
- **SP-3:** "calibración neutra" se entendió como calibración de usuario 1/0, conservando la sección de fábrica (escala ADC). ¿Correcto?
- **D-38 (S1, E1):** faltan las cuentas ADC reales de la prueba de banco: atmosférica, lazo abierto y corto, para cámara y chaqueta. Con ellas se fijan `adc_falla_bajo`/`adc_falla_alto` y el piso calibrado. La calibración de fábrica actual (`adc_min` 5/50) no parece corresponder a 4 mA.

**Seguridad / ciclo (de los informes ★):**
- **¿Hay válvula de seguridad mecánica en la cámara, y a qué presión está tarada?** Sin ella, la protección contra sobrepresión del sellado de líquidos (D8-2.10) sería solo por software (S2a, SAF-08/09).
- D8-2.10: ¿se repone aire comprimido durante la espera sellada? ¿El drenaje solo no basta para ventear? ¿Se extiende el sellado a otras fases? (S2a 1-3).
- Líquidos sin presión de cámara: hoy se ventea por la lenta (D8-1.2 gana a D8-2.10, HAZ-S1-05). ¿Y SEN-05/SEN-08 con líquido? (S1 1 y 6).
- D8-2.6 con causa original de E/S o de puerta; tope de pausas fuera de ESTERILIZACION; alivio con paro (S2a 5-8).
- Timeouts de fase y `timeout_pulso` durante la pausa; modo prueba desde FALLA; ACK del ALL_OFF del firmware; avisos de uniformidad en el idioma de la reimpresión (S2b 1-8).
- R8: nivel de un DI sin cablear; si la calibración sigue a la función o al puerto; inhibir `bomba_vacio` cuando `agua_bomba` está pendiente; puertos DI 15-48 y DO 25-32 poblados (R8 1-7).
- V8a: modo 1 al volver a Sólido; segunda barrera en `descompresion.py` para líquido; la recuperación de un ciclo interrumpido sin revalidar el modo (V8a 1-5).
- E1: antirretorno o filtro en la entrada de aire atmosférico; cadencia AI de 500 ms del firmware (E1 1-5).

**Interfaz y textos:**
- ¿D8-5.4 (sin abreviaturas) aplica también al ticket de 32 columnas? (V8b)
- La letra mínima bajó a 14 px para no recortar (DECISIÓN SIN CONFIRMAR de V8b). Revisar `revision_traducciones.md` y el glosario `parametros.*`.
- La regla U-2 ("dos líneas" en el cajón de Opciones) ya no se cumple tal cual con D8-5.4.
- E2: "Familia" o "Tipo de equipo" en Información del sistema; dónde van familia, capacidad y carga en el PDF.
- N8: ¿apilar también el cambio de programa o de fase dentro de Parámetros del ciclo?

**Depuración y dependencias:**
- D8: ¿se autoriza `git worktree remove --force` para `roles-sensor-temperatura` (solo artefactos) y `anuncios-voz`, y luego `git branch -D`? ¿Qué hacer con la versión nueva del plan `2026-08-12-anuncios-voz.md` que está sin seguimiento? ¿Se cablean `can_open`/`can_close`?
- L8: compilar siempre desde PowerShell/cmd (ya quedó así en K8). ¿Lista SOUP propia para el generador de códigos?

## Lo que quedó sin hacer y dónde está
- **D8, P10/P11:** las ramas `feature/roles-sensor-temperatura` y `worktree-anuncios-voz` están archivadas con las etiquetas `archivo/*` en `origin`, pero sus worktrees y ramas locales siguen: `git worktree remove` pidió `--force`.
- **V8b:** no se regeneraron las capturas después de unir `tanda-8`. La pantalla de reasignación no está en el banco de capturas. Las capturas salen sin backend.
- **Hallazgos Medios/Bajos abiertos** de los revisores, en cada informe ★: V8a TMG-01/SAF-01/02, R8 SAF-04, y Bajos de E1, S1, S2a y S2b.
- **Ticket y motivos de fallo de las fases:** siguen en español con la interfaz en inglés (V8b).
- Prueba intermitente conocida, de temporización QML bajo carga: `test_opciones_qml.py::test_tecnico_entra_a_opciones[PREPARADO-False]`. Falló una vez en la suite de S2a y pasó aislada 3/3. No se repitió en la suite final.

## Push
Ver el final de `tanda8/estado.md` (se completa al empujar).

## Limpieza
- Se quitaron los worktrees de trabajo de la sesión principal: `_suites_t8/*`, `_build_c` y `_t8_b`.
- Los worktrees de los subagentes (`.claude/worktrees/agent-*`, ramas `tanda-8-*`, todas unidas) **no se quitaron**: tienen `data/` sin seguimiento generado por sus pruebas, y quitarlos exigiría `--force`. Se pueden quitar a mano.
- Fuera del repositorio quedan `C:\Users\tecni\Documents\_t8_tools` (guiones del ensayo B → C y logs del build), `_t8_tmp_bc` y `_t8_tmp_meipass_c`. Se pueden borrar.
