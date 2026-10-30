# Auditoría planes vs. código — LOTE 4 (UI de ciclo y menú)

- **Fecha:** 2026-10-08
- **Norma:** NTC-IEC 62304:2019 (IEC 62304:2006), Clase C — cláusulas 5.2.6, 5.4.4, 8.2.3, 7.4.
- **Base auditada:** rama `audit/62304-snapshot`, commit **8d1884c** (2026-10-07 21:37, = `dev` e7bccf2 + cambios sin commit). Todas las citas `ruta:línea` se refieren a 8d1884c.
- **Alcance:**
  - `docs/mis_plans/planeacion_pantalla_ciclo_ui.md`
  - `docs/mis_plans/planeacion_pantalla_ciclo_en_curso.md`
  - `docs/mis_plans/planeacion_menu_principal.md`
  - `docs/mis_plans/planeacion_menu_principal_ui_qml.md`
- **Modo:** solo lectura. No se corrige ni se propone; no se decide quién tiene razón.
- **Criterio para la geometría:** las medidas en píxeles de los mockups no se califican una por una. Se verificó que cada elemento existe, su posición nominal en el código y su comportamiento. La comparación visual por captura queda NO VERIFICADO (no se ejecutó).

## Diferencias e7bccf2 → 8d1884c en rutas del lote

```
.../planeacion_pantalla_ciclo_en_curso.md          | 296 +++++++++
docs/mockups/menu_principal_v3.png                 | Bin 0 -> 527971 bytes
src/autoclave/backend/server.py                    | 699 +++++++++++++++++----
.../services/domain/logging/db_manager.py          | 197 +++++-
src/autoclave/ui_qml/assets/textos/es.json         |   1 +
src/autoclave/ui_qml/bridge/ui_bridge.py           |  13 +-
.../ui_qml/controllers/login_controller.py         |  12 +-
src/autoclave/ui_qml/domain/permisos_opciones.py   |   6 +-
.../ui_qml/qml/Componentes/BarraSuperior.qml       |  64 +-
src/autoclave/ui_qml/qml/Main.qml                  |   2 +-
src/autoclave/ui_qml/qml/NuevoUsuarioHost.qml      |  52 ++
.../ui_qml/qml/Pantallas/NuevoUsuario.qml          | 675 ++++++++++++++++++++
src/autoclave/ui_qml/qml/Pantallas/Opciones.qml    |   8 +-
.../ui_qml/qml/Pantallas/PantallaCicloEnCurso.qml  |  66 +-
.../ui_qml/qml/Pantallas/PantallaPreciclo.qml      |  58 +-
.../ui_qml/qml/Pruebas/PruebaCicloEnCurso.qml      |   1 +
16 files changed, 1940 insertions(+), 210 deletions(-)
```

---

## planeacion_pantalla_ciclo_ui (código @ 8d1884c)

**Estado:**
- Fecha: un solo commit, 0d6e944 (2026-09-29, "pantalla de ciclo (mockup-01) con parámetros desde el backend"), que trae plan y código juntos.
- Commits que lo citan: 0d6e944.
- Otra rama: no.
- Commits posteriores en el área (`PantallaPreciclo.qml`/`Ciclo.qml`, `ui_bridge.py`, `comandos_*.py`):
  - 2242a63 2026-09-29 arranque QML de doble pantalla, puerta e inicio de ciclo
  - fb74254 2026-10-01 insignia de ESTADO con check verde cuando el equipo está listo
  - bdc9bde 2026-10-01 renombrar `Ciclo.qml` a `PantallaPreciclo.qml`
  - 8d1884c snapshot

| # | Afirmación del plan (sección) | Estado | Evidencia código | Origen probable | Impacto |
|---|---|---|---|---|---|
| — | **COINCIDE ×20:**<ul><li>sin gráfica, barra de fases ni contador (§1);</li><li>un solo botón de puerta que alterna;</li><li>botón "Iniciar ciclo";</li><li>zona de alarmas en el espacio liberado;</li><li>avatar en la barra inferior (§1);</li><li>escala `s = ancho/1196` (§2);</li><li>fondo compartido (§3);</li><li>cabecera con logo, hora y fecha del reloj del sistema, campana con insignia `#08C9F9` y engranaje (§4);</li><li>la insignia cuenta las alarmas activas (§4);</li><li>panel contenedor 19,177,1159×1723, radio 30 (§5.1);</li><li>tarjeta de alarmas con título, línea, estado vacío y lista que se puebla sin mover la geometría (§5.4);</li><li>botón de puerta con degradado, círculo, iconos provisionales y texto (§6.1);</li><li>botón Iniciar con degradado verde y triángulo desplazado (§6.2);</li><li>zona central vacía (§6.3);</li><li>barra inferior con modelo/serie, avatar de 88 px, casa y versión (§6.4);</li><li>Iniciar llama a `start_cycle()` y, si se rechaza, solo deja advertencia en el log (§7);</li><li>unidad "kPa" en lugar de "°Kpa" como constante editable (PC-07).</li></ul> | COINCIDE | PantallaPreciclo.qml:41-72, 141-144, 202-281, 427-517, 520-715; comandos_ciclo.py:36-58; es.json:123 | — | — |
| 1 | §5.2 columna central: punto de estado y texto "Ejecutando" bajo el programa | DIFIERE | La columna central solo tiene rótulo y programa (PantallaPreciclo.qml:313-320) | indeterminado | FUNCIONAL |
| 2 | §5.2 columna izquierda: "No preparado" bajo el número de ciclo | DIFIERE | No existe ese texto (PantallaPreciclo.qml:304-311) | indeterminado | COSMÉTICO |
| 3 | §5.3: tarjeta de parámetros con **5** columnas (Temp. Ester., Tiempo Est., Tiempo Sec., Temp cámara, Presión) | DIFIERE | 6 columnas; se agrega "Temp referencia" (PantallaPreciclo.qml:363-425) | indeterminado | FUNCIONAL |
| 4 | §7: si el estado es `"ABIERTO"` se cierra, en cualquier otro caso se abre; un rechazo se muestra como aviso "Acción no permitida" | DIFIERE | `ABIERTO` **o `ABRIENDO`** cuentan como abierta, así que con la puerta abriéndose el botón envía cerrar (ui_bridge.py:27, 215; comandos_puerta.py:47-56). El motivo de rechazo se muestra 5 s en la zona de alarmas (comandos_puerta.py:70-77; PantallaPreciclo.qml:449-469) | indeterminado | SEGURIDAD |
| 5 | §6.4/PC-05: el destino del avatar está indefinido | DIFIERE | El avatar abre el login QML u OPCIONES (Main.qml:167 → `abrirConfiguracion`, Main.qml:78-80) | plan desactualizado probable (2d4ffa8) | FUNCIONAL |
| 6 | — | SIN DOCUMENTAR | Insignia de ESTADO con check verde en "listo" y "!" naranja en el resto (PantallaPreciclo.qml:51-53, 323-354; fb74254) | — | FUNCIONAL |
| 7 | — | SIN DOCUMENTAR | El botón INICIAR CICLO se oculta si `LISTO_PARA_CICLO` no está activo o no hay conexión (PantallaPreciclo.qml:614-618) | — | SEGURIDAD |
| 8 | — | SIN DOCUMENTAR | Sin conexión: valores en gris y botones deshabilitados (PantallaPreciclo.qml:48, 308, 531-533, 584) | — | SEGURIDAD |
| 9 | — | SIN DOCUMENTAR | Tocar el recuadro de modelo/serie abre el panel de información del equipo (PantallaPreciclo.qml:670-677) | — | COSMÉTICO |
| 10 | §8: render offscreen a 1196×1917, imagen de diferencia, umbral 8/255 y ±2 px | NO VERIFICADO | No se ejecutó; ningún test referencia `pantalla_ciclo_sin_grafica.png` | — | — |

**Resumen:** 30 afirmaciones: COINCIDE 20 · DIFIERE 5 · SIN DOCUMENTAR 4 · NO VERIFICADO 1.

---

## planeacion_pantalla_ciclo_en_curso (código @ 8d1884c)

**Estado:**
- Fecha: no versionado en `dev`; solo existe en 8d1884c. Modificación del archivo: 2026-10-01 18:59. El plan se fecha 2026-10-01.
- Commits que lo citan:
  - f5ece46, 12ad6b5, 6ba2bf0, bdc9bde, 410109f (2026-10-01)
  - 723bfef (2026-10-06)
- Otra rama: no.
- Commits posteriores en el área: 723bfef, 4bc822d, 2d4ffa8, e7bccf2, 8d1884c.

| # | Afirmación del plan (sección) | Estado | Evidencia código | Origen probable | Impacto |
|---|---|---|---|---|---|
| — | **COINCIDE ×25:**<ul><li>renombre a `PantallaPreciclo`/`PantallaCicloEnCurso` (14.7);</li><li>encabezado con logo, hora, fecha y campana (§5.1);</li><li>ESTADO con engranaje y "En ejecución" (§5.2);</li><li>barra de 6 fases en orden, ocultando las que no aplican (§5.3);</li><li>la fase activa viene del backend;</li><li>"kPa";</li><li>"—" sin lectura (§2.7);</li><li>relojes de transcurrido y restante, con "—" si no se puede estimar (§5.6);</li><li>botón rojo CANCELAR CICLO (§5.7);</li><li>B1 `GET /cycle/current/progress` (sin ciclo `{"activo": false}`);</li><li>B2 `GET /cycle/current/graph` con `temp_ref` e incremental (`desde_id`);</li><li>B3 tabla `ciclo_fases`;</li><li>B4 mapeo de fases;</li><li>§7 referencia = último ciclo COMPLETADO del mismo programa;</li><li>`EXTENSION_MIN = 5` con la regla `5 min - ((e - d) mod 5 min)`;</li><li>restante total = activa + siguientes;</li><li>sin referencia → nulo;</li><li>§8 gráfica con QtQuick Shapes/`PathPolyline`, sin QtCharts;</li><li>cursor que se oculta a 5 s;</li><li>desplegable "Tiempos" y pantalla completa;</li><li>§9 entrada por estado CICLO y reapertura directa si la UI arranca en CICLO;</li><li>sin espera por inactividad en CICLO;</li><li>§10 cancelación con diálogo, anti doble toque y aviso sin navegar si falla;</li><li>`/cycle/abort` activa `CICLO_CANCELADO`;</li><li>§11 escala con `Escala`/`m()`.</li></ul> | COINCIDE | PantallaCicloEnCurso.qml:56-59, 94-99, 115, 247, 294-298, 343-404, 532-535, 618-748; progreso_ciclo.py:9-139; server.py:635-691, 933-950; db_manager.py:89-99, 533-551; GraficaCiclo.qml:2-17, 42, 403, 423-430; Main.qml:79-102, 104-114; standby.py:36; comandos_ciclo_en_curso.py:41-81; es.json:96, 102, 123, 166 | — | — |
| 1 | §5.1/§9: el engranaje abre la configuración PySide | DIFIERE | Abre el login QML u OPCIONES (Main.qml:184 → 78-80) | plan desactualizado probable (2d4ffa8, U-18) | FUNCIONAL |
| 2 | §5.7: el avatar abre el login PySide | DIFIERE | Abre el login QML u OPCIONES (Main.qml:185) | plan desactualizado probable (2d4ffa8) | FUNCIONAL |
| 3 | §5.4: tarjeta de parámetros con **5** valores ("Temp 1" = temperatura de referencia) | DIFIERE | 6 valores: agrega "Temp cámara" además de la de referencia (PantallaCicloEnCurso.qml:445-477) | indeterminado | FUNCIONAL |
| 4 | 14.1: PURGA y PRE_VACIO se mapean a "Vacío" | DIFIERE | PURGA ya no existe; solo `PRE_VACIO → vacio` (progreso_ciclo.py:12-19) | plan desactualizado probable (410109f) | COSMÉTICO |
| 5 | PCE-08: `/cycle/abort` sin autenticación y backend escuchando en todas las interfaces | DIFIERE | El backend escucha en `127.0.0.1` (backend/main.py:9, 33); `/cycle/abort` sigue sin token (server.py:933), como decide el plan de autenticación | plan desactualizado probable | SEGURIDAD |
| 6 | — | SIN DOCUMENTAR | Al terminar el ciclo la pantalla no sale sola: el botón pasa a CONFIRMAR, que envía `/cycle/acknowledge` y nunca se confirma automáticamente (PantallaCicloEnCurso.qml:23-25, 618-690; comandos_ciclo_en_curso.py:45-47). El plan lo dejaba abierto (14.2) | — | SEGURIDAD |
| 7 | — | SIN DOCUMENTAR | Un comentario de Main.qml:188-190 dice que el engranaje de la pantalla en curso abre el Menú Principal; el código abre la configuración (Main.qml:184) | — | COSMÉTICO |
| 8 | §15: verificación manual (comparación con PNG en 1200×1920 y 1080×1920, muestreo real ~1 s, dos UI simultáneas) | NO VERIFICADO | No se ejecutó; existen `test_progreso_ciclo.py` y `test_grafica_ejes_js.py`, sin correr | — | — |

**Resumen:** 33 afirmaciones: COINCIDE 25 · DIFIERE 5 · SIN DOCUMENTAR 2 · NO VERIFICADO 1.

---

## planeacion_menu_principal (v0.3) (código @ 8d1884c)

**Estado:**
- Fecha: un solo commit, 2a00d1e (2026-09-29). El plan se fecha 2026-09-24.
- Commits que lo citan: 723bfef (2026-10-06).
- Otra rama: no.
- Commits posteriores en el área (menú, `Main.qml`, puentes):
  - 723bfef 2026-10-06 menú principal con historial, impresión y correo
  - 4bc822d 2026-10-06 Reportes
  - 9a94de4 2026-10-06 reporte consolidado
  - 2d4ffa8 2026-10-07 OPCIONES
  - 8d1884c snapshot
- **Nota:** `planeacion_menu_principal_ui_qml.md` D-18 dice que las secciones de este plan que contradice "quedan marcadas como reemplazadas"; el archivo v0.3 no contiene ninguna marca.

| # | Afirmación del plan (sección) | Estado | Evidencia código | Origen probable | Impacto |
|---|---|---|---|---|---|
| — | **COINCIDE ×12 (hechos y brechas vigentes):**<ul><li>no hay endpoint de pausa;</li><li>`/cycle/start` solo con `LISTO_PARA_CICLO`;</li><li>`ciclos.operador` nunca se llena (B-02);</li><li>`PERMISSIONS` niega `start_cycle` a `OPERATOR_BACK` (B-01);</li><li>sin fuente de mantenimiento (B-03);</li><li>`Arranque.qml` sin renombrar (B-10);</li><li>`/cycles` sin orden explícito (B-14);</li><li>UI-09: `request_open`/`request_close` no invocan `can_open`/`can_open_from_context`;</li><li>§10: ambas pantallas pasan a la de ciclo por el estado del backend;</li><li>sesión independiente por proceso;</li><li>§8: aviso sin conexión.</li></ul> | COINCIDE | server.py:570-575, 723-725, 912-930; permissions.py:11-15; resumen_sistema.py:210-211; Pantallas/Arranque.qml; ser_puertas.py:60-88, 107-129; Main.qml:79-102; opciones_controller.py:9-11; PantallaPreciclo.qml:458-463 | — | — |
| 1 | §6.1, §7: Inicio con bloque de ciclo (selección de programa, parámetros, Iniciar ciclo) | DIFIERE | El menú QML no tiene bloque de ciclo; tiene Iniciar sesión, Historial, Reportes, Información y secado (MenuPrincipal.qml:187-252). La selección e inicio siguen en `PantallaPreciclo` | plan desactualizado probable (`planeacion_menu_principal_ui_qml` D-01) | FUNCIONAL |
| 2 | §6.4/B-11: Historial sin envío por correo (función de red bloqueada por H-03) | DIFIERE | Historial y Reportes envían por SMTP (acciones_ciclos.py:3-22; exportacion/correo.py); la contraseña sale de keyring (config_correo.py:6-8, 33-35) | indeterminado | SEGURIDAD |
| 3 | §11.2: roles admin, técnico, biomédico, ingeniero | DIFIERE | Sin biomédico (roles.py:10-23) | plan desactualizado probable (D25) | FUNCIONAL |
| 4 | UI-08: semilla `admin`/`admin1234` y SHA-256 sin sal | DIFIERE | PBKDF2 y semillas con cambio obligatorio (contrasenas.py:14-28; db_manager.py:115-126) | plan desactualizado probable | SEGURIDAD |
| 5 | B-05: ninguna ruta expone el total de ciclos | DIFIERE | `GET /cycle/summary` → `ciclos_totales` = último `numero_ciclo` (server.py:729-739) | plan desactualizado probable (723bfef) | FUNCIONAL |
| 6 | B-12: no existe número de programa | DIFIERE | `cycle_number` en los JSON y `Cycle.number` (cycle_manager.py:12-25; factory/instrumental_134.json:3) | plan desactualizado probable | FUNCIONAL |
| 7 | §11.1.2: cierre de sesión por 5 min de inactividad fuera de los menús de rol | DIFIERE | La sesión se cierra al entrar en standby (Main.qml:84-88), no con una regla de 5 min | indeterminado | SEGURIDAD |
| 8 | §9: identificación de operador por nombre y tabla `operadores` | NO IMPLEMENTADO | db_manager.py:35-112; server.py:723-725 | — | SEGURIDAD |
| 9 | §6.2: Reset de falla y Reconocer alarma en la UI | NO IMPLEMENTADO | No existen en QML (`git grep` en ui_qml sin un botón que llame a `/fault/reset`) | — | SEGURIDAD |
| 10 | §8: aviso `sistema.modo_prueba` en Inicio | NO IMPLEMENTADO | La clave existe (es.json:308) pero ninguna pantalla la usa | — | SEGURIDAD |
| 11 | §6.5: rango 1-10/11+, no reutilizar números, orden por número | NO IMPLEMENTADO | cycle_manager.py:79-99 solo descarta números repetidos; `/cycles` sin orden | — | FUNCIONAL |
| 12 | UI-10: repositorio público con base de datos e historial expuestos | NO VERIFICADO | No se consultó GitHub | — | — |

**Resumen:** 24 afirmaciones: COINCIDE 12 · DIFIERE 7 · NO IMPLEMENTADO 4 · NO VERIFICADO 1.

---

## planeacion_menu_principal_ui_qml (v1.4) (código @ 8d1884c)

**Estado:**
- Fecha: un solo commit, 723bfef (2026-10-06), que trae plan y código juntos.
- Commits que lo citan: 723bfef.
- Otra rama: no.
- Commits posteriores en el área:
  - 4bc822d 2026-10-06 Reportes
  - 9a94de4 2026-10-06 consolidado
  - 2d4ffa8 2026-10-07 login QML y OPCIONES
  - e7bccf2
  - 8d1884c

| # | Afirmación del plan (sección) | Estado | Evidencia código | Origen probable | Impacto |
|---|---|---|---|---|---|
| — | **COINCIDE ×12:**<ul><li>D-01/D-02/D-03: tarjetas Iniciar sesión (ancha), Historial, Reportes, Información y secado;</li><li>D-04/MP-11: "Tiempo adicional de secado" muestra "—" con `TODO(MP-11)`;</li><li>D-05: resumen con Ciclos totales, Próximo mantenimiento, Ciclos hoy y Último ciclo;</li><li>D-14: Ciclos totales = último `numero_ciclo` con `TODO(MP-06a)`;</li><li>D-17: campana con contador;</li><li>D-20/D-21: tarjetas de resumen como botones con ventana flotante;</li><li>D-23: `/cycle/summary` y `/cycle/history/{id}/graph`;</li><li>D-24: operador "—" con `TODO(MP-14b)`;</li><li>D-12: Salir deshabilitado con `TODO(MP-03)`;</li><li>§6.5: actualización cada 10 s;</li><li>MP-12: el reinicio de falla no existe en QML;</li><li>mockup v3 copiado a `docs/mockups/`.</li></ul> | COINCIDE | MenuPrincipal.qml:113, 187-320, 335, 376-396; resumen_sistema.py:6, 210-217; server.py:729-739, 842-864; db_manager.py:375-384; `docs/mockups/menu_principal_v3.png` | — | — |
| 1 | D-11/MP-01/§8: Fase 4 (cableado a `Main.qml`) DIFERIDA; el menú solo en arnés | DIFIERE | Cableado: el engranaje de preciclo abre el menú (Main.qml:166, 188-206) | indeterminado (mismo commit 723bfef) | FUNCIONAL |
| 2 | D-07/§6.1: el engranaje abre la configuración PySide | DIFIERE | En preciclo abre el Menú Principal; en ciclo en curso abre el login QML u OPCIONES (Main.qml:166, 184) | plan desactualizado probable (2d4ffa8) | FUNCIONAL |
| 3 | D-12/MP-07/§6.2: Iniciar sesión abre el login PySide | DIFIERE | Abre el login QML (Main.qml:206 → 78-80) | plan desactualizado probable (2d4ffa8) | FUNCIONAL |
| 4 | D-13: Historial, Reportes e Información visibles pero atenuadas y deshabilitadas | DIFIERE | Habilitadas: Historial y Reportes abren ventanas con listado, impresión y correo; Información abre el panel del equipo (MenuPrincipal.qml:199-240) | plan desactualizado probable (4bc822d) | FUNCIONAL |
| 5 | MP-14: Ciclos totales y Ciclos hoy deshabilitadas hasta definir su contenido | DIFIERE | Ciclos hoy está habilitada y abre el listado del día (MenuPrincipal.qml:295-305) | indeterminado | FUNCIONAL |
| 6 | — | SIN DOCUMENTAR | Reportes: resumen por periodo con impresión y envío por correo de PDF (MenuPrincipal.qml:212-222; acciones_ciclos.py:3-22) | — | SEGURIDAD |
| 7 | — | SIN DOCUMENTAR | Información abre el mismo panel de equipo que el recuadro de modelo/serie (MenuPrincipal.qml:223-240) | — | COSMÉTICO |
| 8 | §9/Fase 5: comparación visual con v3 y suite de pruebas en verde | NO VERIFICADO | No se ejecutó | — | — |

**Resumen:** 20 afirmaciones: COINCIDE 12 · DIFIERE 5 · SIN DOCUMENTAR 2 · NO VERIFICADO 1.

---

## 1. Resumen del lote

| Plan | Afirm. | COINCIDE | DIFIERE | NO IMPL. | EN OTRA RAMA | SIN DOC. | NO VERIF. |
|---|---|---|---|---|---|---|---|
| planeacion_pantalla_ciclo_ui | 30 | 20 | 5 | 0 | 0 | 4 | 1 |
| planeacion_pantalla_ciclo_en_curso | 33 | 25 | 5 | 0 | 0 | 2 | 1 |
| planeacion_menu_principal (v0.3) | 24 | 12 | 7 | 4 | 0 | 0 | 1 |
| planeacion_menu_principal_ui_qml (v1.4) | 20 | 12 | 5 | 0 | 0 | 2 | 1 |
| **Total** | **107** | **69** | **22** | **4** | **0** | **8** | **4** |

## 2. Discrepancias con impacto SEGURIDAD, por criticidad aparente

1. **Botón de puerta:** con la puerta en `ABRIENDO`, el botón envía **cerrar** (el plan solo trata `ABIERTO` como abierta). El rechazo del backend se muestra 5 s en la zona de alarmas, no como aviso (CIU 4).
2. **Permisos por estación (UI-09):** `request_open`/`request_close` no aplican `PERMISSIONS`; `OPERATOR_BACK` sigue sin `start_cycle` (fila COINCIDE de v0.3).
3. **Acciones de falla y alarma:** "Reset de falla" y "Reconocer alarma" no existen en la UI QML (MP v0.3 9); el aviso de modo prueba no se muestra en ninguna pantalla (MP v0.3 10).
4. **Operador:** sin identificación de operador ni registro en `ciclos.operador`; la trazabilidad de quién inició el ciclo no existe (MP v0.3 8).
5. **Fin de ciclo:** la pantalla en curso pide confirmación manual (CONFIRMAR → `/cycle/acknowledge`); el comportamiento no está en el plan (ECC 6).
6. **Correo:** envío por SMTP desde Historial y Reportes, en contra de B-11 del plan v0.3, que lo excluía por red (MP v0.3 2; MPQ 6).
7. **Sesión:** se cierra por standby y no por la regla de 5 min del plan v0.3 (MP v0.3 7).
8. **Inicio de ciclo y estado sin conexión** sin documentar: el botón INICIAR se oculta si el equipo no está listo; sin conexión todo queda en gris y deshabilitado (CIU 7, 8).
9. **Hallazgos de seguridad desactualizados en los planes:** PCE-08 (escucha en todas las interfaces) y UI-08 (SHA-256 / `admin1234`) ya no describen el código (ECC 5; MP v0.3 4).

## 3. Qué no se pudo verificar y por qué

- **Comparación visual:** no se renderizaron las pantallas ni se compararon con los mockups (`pantalla_ciclo_sin_grafica.png`, `pantalla_ciclo_con_grafica_editada.png`, `menu_principal_v3.png`). Las medidas en píxeles quedan sin calificar.
- **Pruebas no ejecutadas:** no se corrió pytest (`test_progreso_ciclo.py`, `test_grafica_ejes_js.py`, `test_comandos_*.py`, `test_main_menu_principal_qml.py`). No se califica la verificación de cambios (8.2.3).
- **Comportamiento en ejecución:** no se midió la frecuencia real de muestreo de la gráfica ni se probaron dos UI simultáneas.
- **UI-10:** no se consultó GitHub (visibilidad del repositorio).
- **Comparación de colores y tipografías:** solo se revisaron los valores en el código.
