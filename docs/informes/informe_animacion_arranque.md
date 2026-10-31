# Informe — Animación de arranque (ejecución de `planeacion_animacion_arranque.md` v1.1)

Fecha: 12-oct-2026 · Sin commit (cambios en el árbol de trabajo).

## Qué se hizo

| Archivo | Cambio |
|---|---|
| `src/autoclave/ui_qml/qml/Pantallas/IntroArranque.qml` | **Nuevo.** Intro y splash. Todo se deriva de un único reloj `t` (0–3,5 s) y de `s` (salida, 0–1 en 1 s). Por eso, congelar ante un fallo bloqueante es solo pausar esas dos animaciones. Sigue la composición de §3 y la línea de tiempo de §4 tal cual (curvas OutCubic / InOutQuad / OutQuad). No se puede saltar: un `MouseArea` cubre todo. |
| `tools/generar_assets_arranque.py` | **Nuevo.** Genera `halo_arranque.png` (512 px, radial `fondoCieloNucleo` → transparente) y `voluta_vapor.png` (256 × 512, blanca). Usa numpy y PIL. |
| `src/autoclave/ui_qml/assets/fondos/halo_arranque.png`, `voluta_vapor.png` | **Nuevos.** Los genera el script anterior. |
| `src/autoclave/ui_qml/bridge/progreso_arranque.py` | **Nuevo.** `SimuladorProgresoArranque`: expone `fraccion`, `proceso`, `terminado` y `falloBloqueante` (§6). Recorre las 4 etapas del video de referencia: Iniciando servicios → Conectando con la tarjeta de E/S → Verificando sensores → Abriendo base de datos. No está conectado al flujo real. |
| `src/autoclave/ui_qml/qml/Main.qml` | `Loader` con la intro encima de la pila. La pantalla de reposo ya queda debajo; al terminar, la intro se descarga. Se agregaron las propiedades `progresoArranque`, `versionSoftware` e `introTerminada`. Sin `progresoArranque` (pruebas) no hay intro. Capa **provisional** de alarma de arranque con `FilaAlarma`, prioridad alta. |
| `src/autoclave/ui_qml/app.py` | Crea e inicia el simulador desde t = 0, en paralelo con todo lo demás, y lo detiene al salir. Inyecta `progresoArranque` y `versionSoftware` (`version_software()`, que ya existía en `info_equipo.py`). |
| `src/autoclave/ui_qml/qml/Tema/Colores.qml` | Token nuevo `textoFechaReposo: "#C7DCFD"` (D-08). `Arranque.qml` lo usa ahora en vez del hex. |
| `src/autoclave/ui_qml/assets/textos/es.json` | Sección `arranque`: los 4 procesos y 3 textos de fallo. |
| `tests/test_progreso_arranque.py`, `tests/test_intro_arranque_qml.py` | **Nuevos** (19 pruebas). |

### Decisiones de implementación (no fijadas por el plan)

- **Vigilante de 20 s (regla 4).** Vive en la intro: propiedad `plazoSinProgresoMs`, con defecto 20000. Se reinicia con cada cambio de `fraccion` o `proceso`. No vive en el objeto de progreso porque debe detectar justamente que ese objeto no avanza.
- **Salida.** También se desvanece el logo. Así se cumple "queda solo el fondo" (§4 y criterio 2), porque el logo del reposo tiene otro tamaño y otra posición.
- **Fondo de la intro.** Va dentro de una `AreaFija`, igual que el de reposo. Así el último cuadro coincide también en pantallas 9:16.
- **Pruebas manuales de fallo sin tocar código.** Variable `AUTOCLAVE_INTRO_SIMULACION`, con los valores `fallo:<s>` (p. ej. `fallo:1.5`) y `sin_progreso`.
- **Brillo de la barra.** En el video, la barra tiene un brillo que se desplaza en bucle. No se implementó, porque D-09 prohíbe los efectos repetidos.

## Verificación

- Pruebas nuevas: **19 pasan**. Cubren lo siguiente:
  - Arranque normal: 3,5 s de intro más 1 s de salida, y relevo a la pantalla de reposo.
  - Fallo en t = 0,3 / 1,5 / 3,0 s: la alarma aparece en menos de 200 ms, la intro se congela y no pasa a reposo.
  - Sin progreso: aparece el fallo al vencer el plazo.
  - Sin inyección no hay intro.
  - El pie muestra solo la versión cuando falta el modelo.
  - Ninguna prueba produce avisos de QML.
- Suite QML/UI existente: **180 pasan**.
- La suite completa no se pudo recolectar por un error de importación previo y ajeno a este cambio: `test_adenda_estados.py` no encuentra `TEMPERATURE_PROBE_KEYS` en `installation/profile.py`, archivo que ya estaba modificado en el árbol.
- `python -m autoclave.ui_qml.app` arranca en offscreen sin avisos de QML.
- Comparación visual con `intro_arranque_preview.mp4`, fijando `t` cuadro a cuadro: la secuencia coincide (halo → revelado → línea y logo → riel → eslogan → proceso y pie).

## Pendiente / no hecho

1. **`en.json` no existe** y la UI no tiene selector de idioma: `app.py` solo carga `es.json`. No creé un `en.json` parcial. Por eso el criterio 6 no se puede verificar hasta que exista el plan de idiomas.
2. **ARR-01 (renombrar `Arranque.qml` → `Reposo.qml`).** No lo hice: es un hallazgo con recomendación y requiere tu orden.
3. **ARR-03.** El progreso es simulado. Falta el plan de la secuencia de arranque real, que incluye los fallos *degradables* (regla 3b), hoy sin fuente.
4. **Capa de alarma provisional.** No existe aún una capa de alarmas en QML: la Parte A del sistema de alarmas sigue en su rama sin unir. Cuando exista, debe reemplazar el rectángulo `alarmaArranque` de `Main.qml`.
5. **Toques durante la intro.** No se pueden saltar, pero el filtro de eventos del standby igual los cuenta como actividad. Si alguien toca la pantalla durante la intro, al terminar se ve la pantalla principal en vez del reposo. No lo cambié.
6. **Criterios 1, 2, 7 y 8.** Hay que medirlos en el PC industrial, con las dos pantallas reales.
