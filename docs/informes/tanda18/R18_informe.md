# Informe R18 — Tanda 18: hallazgos de la instalación de la 1.0.0-alpha.2

Fecha: 27-oct-2026. Fuente de verdad: `docs/mis_plans/decisiones_tanda_18.md`. Ejecutada en sesión interactiva («ejecuta tanda 18»); no había prompt ni instrucción propios, así que se siguió la estructura de la tanda 17 (A0 → P → I → R → K → L → Z) sin redactar esos archivos.

## 1. Alcance

| ID | Qué | Dónde |
|---|---|---|
| ARR-06 | Intro de arranque también sin perfil (o con perfil inválido), en las dos pantallas | `ui_qml/app.py`, `bridge/progreso_arranque.py` (`ProgresoArranqueSinPerfil`), `bridge/puente_instalacion.py` (`motivo_instalacion`), `InstalacionVentana.qml`, `ReposoInstalacionVentana.qml`, `exe_unico.py` (log) |
| REI-01 | Cuenta regresiva de 10 s y reinicio del PC al terminar el asistente | `Pantallas/Instalacion.qml`, `ReposoInstalacionVentana.qml`, `ui_qml/app.py` (`avisar_fin_instalacion`), `exe_unico.py` (`reinicio_pc_activo`, `reiniciar_pc`, `esperar_reinicio_pc`) |
| EST-08 | Retiro de la cubierta de arranque (EST-07), conservando `Delay PT0S` | `estacion/cubierta_arranque.py` y `primer_cuadro.py` borrados; `exe_unico.py`, `ui_qml/app.py`, `packaging/Autoclave.spec`, comentarios de `estacion/*`, `03_tarea_autoclave.ps1`, `tarea_arranque.ps1` |
| EST-09 | Paso 07 de la estación: escritorio de la estación | `tools/estacion/07_*.ps1`, `_comun.ps1`, `tools/instalador/autoclave.iss`, `estacion_setup.ps1`, los dos `LEEME.md` |

## 2. Etapas

| Etapa | Resultado | Commit |
|---|---|---|
| A0 | Rama `tanda-18` desde `dev` (ddb4978); decisiones en commit. Línea base en worktree limpio de `dev`: **8488 passed**, 10 skipped, 3 xfailed (`base_suite.txt`). | ee8d32f |
| P-s1 (subagente, worktree) | EST-09 | b34087c |
| P (sesión principal) | ARR-06, REI-01, EST-08 | bb951e7 |
| I | Merge de `tanda-18-s1` sin conflictos; i18n sin claves huérfanas nuevas (`tools/claves_sin_uso_i18n.py`). | c677a6d |
| Hoja de banco | I-07 → I-07b; I-13, I-14, I-15 | 2ec2509 |
| R | 1 revisor de seguridad: 0 altos, 2 medios, 6 bajos (§5) | — |
| Correcciones R | V18-01, V18-02, V18-03, V18-04 | 453b65e |
| K, L, Z | §7 | — |

Tabla de propiedad: s1 = `tools/estacion/07_*`, `_comun.ps1`, `tools/instalador/autoclave.iss`, `estacion_setup.ps1`, los `LEEME.md` y `tests/test_t18_s1_*`; sesión principal = todo lo demás.

## 3. Detalle

### ARR-06
- `requiere_instalacion()` no cambia. `motivo_instalacion()` distingue «sin_perfil» (no existe el archivo) e «invalido» (existe pero no vale, o no se puede comprobar).
- `ProgresoArranqueSinPerfil` publica fracción 0, proceso `sin_perfil_instalacion` / `perfil_invalido_instalacion` (textos de la sección `arranque`), nunca fallo. Al llamar la intro a `reiniciarVista()` (barra visible) sostiene el mensaje `MENSAJE_SIN_PERFIL_MS` = 2000 y termina; tope de 15 s desde `iniciar()` para no quedar nunca en la intro (menor que el plazo de 20 s de la intro, que cuenta desde su primer cuadro). Temporizadores de Qt (monotónicos).
- Las dos ventanas sin perfil cargan `IntroArranque` encima (Loader) y la descargan al terminar. La cuenta regresiva del asistente no corre mientras se ve la intro (`activo`).
- Sin bitácora: ni la fuente ni las ventanas abren la base. Colores: solo los de la intro (D-08).
- Lanzador: anota en `lanzador.log` «Sin perfil…» o «Perfil de instalación inválido…».

### REI-01
- Asistente: título «INSTALACIÓN COMPLETADA», «El equipo ha sido registrado correctamente.», «Instalación completada. El equipo se reiniciará en N s» y botón «Reiniciar ahora» (mismo `objectName` `botonContinuar`), sin cancelar; al llegar a 0 o al pulsar sale con el código 3. Se retiró `instalacion.continuar`.
- Puerta 2: bajo el ejecutable único sondea el perfil cada 2 s; con perfil válido muestra el mismo aviso con su cuenta (solo informa). Fuera del ejecutable único sigue saliendo sola (W10).
- Lanzador: con código 3 y perfil ya válido → si hay un backend escuchando, no reinicia (V18-02); si no, `reiniciar_pc()`: activo solo en Windows y por defecto solo compilado (`AUTOCLAVE_REINICIO_PC=1/0`); ejecuta `%SystemRoot%\System32\shutdown.exe /r /t 0` con tope de 30 s. Código distinto de 0, excepción o tiempo agotado → log y arranque normal. Código 0 → espera hasta 120 s (`esperar_reinicio_pc`, reloj monotónico) a que Windows cierre el proceso; si sigue vivo, log y arranque normal (V18-01).
- `equipo_instalado`: se escribe en `PuenteInstalacion.instalar()` de forma síncrona y con la base cerrada en `finally`, antes de que el asistente pueda salir; el lanzador reinicia después de que el proceso del asistente terminó. Verificado en el código (`puente_instalacion.registrar_equipo_instalado`).

### EST-08
- Borrados `estacion/cubierta_arranque.py`, `estacion/primer_cuadro.py`, `AvisoPrimerCuadro`/`avisar_primer_cuadro` de `ui_qml/app.py`, `_abrir_cubierta`/`_cerrar_cubierta` y la reapertura tras el asistente en `exe_unico.py` (`_lanzador_con_cubierta` → `_lanzador_principal`), y la entrada del `.spec`. `_ventanas.py`, `_win32.py` e `instancia_unica.py` se conservan. `PT0S` se conserva (prueba).
- Prueba retirada: `tests/test_t17_s2_cubierta_arranque.py`, excepción autorizada por EST-08 (la funcionalidad deja de existir). Sus pruebas del lanzador se reemplazaron por las de `test_t18_arranque_instalacion.py` (el lanzador no importa nada de la cubierta, también en el camino del asistente).

### EST-09 (subagente)

| Ajuste | Valor / API | Fuente | Efecto |
|---|---|---|---|
| Fondo, Rellenar | `HKCU\Control Panel\Desktop`: `Wallpaper`, `WallpaperStyle="10"`, `TileWallpaper="0"` | Microsoft Learn (directiva «Desktop wallpaper», `SystemParametersInfoW`) | Inmediato con la API; si no, próximo inicio de sesión |
| Mismo fondo en todos los monitores | `SystemParametersInfoW(SPI_SETDESKWALLPAPER, …, SPIF_UPDATEINIFILE\|SPIF_SENDCHANGE)` | Microsoft Learn | Inmediato, solo si corre con la cuenta de la estación |
| Tipo «Imagen» | `HKCU\…\Explorer\Wallpapers\BackgroundType=0` | Valor de Configuración › Fondo (no documentado) | Próximo inicio de sesión |
| Barra, ocultar automáticamente | `HKCU\…\Explorer\StuckRects3\Settings`, byte 8 bit 0x01; `SHAppBarMessage(ABM_SETSTATE)` | Formato no documentado; Microsoft Learn (ABM_SETSTATE) | Inmediato con la API; si no, próximo inicio de sesión |
| Íconos ocultos | `HKCU\…\Explorer\Advanced\HideIcons=1` | Valor del Explorador | Próximo inicio de sesión o reinicio del Explorador |

- Escribe en `HKU\<SID>` de la cuenta de la estación (`-Usuario`, si no `Winlogon\DefaultUserName`, si no la que ejecuta); carga `NTUSER.DAT` si la sesión está cerrada y lo descarga en `finally`. Respaldo por valor una sola vez (también la ausencia), reversión por lista blanca y SID. No reinicia el Explorador.
- Setup: copia los scripts y `fondo-arranque.png` como `{app}\estacion\fondo_estacion.png`; aplica el 07 tras el 05 y antes del 06; fallo solo a la lista (`es.Paso07`/`en.Paso07`); Reparar lo reaplica sin contraseña; el desinstalador revierte 07, 06, 05, 04, 02, 01. ISCC compiló el `.iss` (código 0) sin instalar.
- Verificado aparte en Windows PowerShell 5.1: `ConvertTo-Json`/`ConvertFrom-Json` de un `byte[]` da un arreglo de números y la ida y vuelta es exacta (pregunta 4 de R).

## 4. Pruebas
- Nuevas: `tests/test_t18_arranque_instalacion.py` (ARR-06, REI-01, EST-08; con QML offscreen en subproceso) y `tests/test_t18_s1_escritorio_estacion.py` (EST-09, 19 pruebas de texto/estructura y parser de PowerShell).
- Retirada: `tests/test_t17_s2_cubierta_arranque.py` (EST-08).
- Tocadas (aserción por decisión, citada en comentario):
  - `tests/test_t8_e1_asistente_texto_final.py`: el botón pasa de «Continuar» a «Reiniciar ahora» (REI-01); el código 3 se mantiene.
  - `tests/test_t11_n11_instalador_limpia_tactiles.py::test_scripts_06_instalados_y_en_el_puente`: el `ValidateSet` del puente incluye `'07'` (EST-09).
- Suite completa de `tanda-18`: ver §7.

## 5. Revisión R (revisor de seguridad, solo lectura)

| ID | Sev. | Hallazgo | Estado |
|---|---|---|---|
| V18-01 | Media | Código 0 de `shutdown` sin `/f`: si una aplicación bloquea o alguien cancela, el lanzador ya había salido y el equipo quedaba sin Autoclave. | Corregido: espera 120 s y sigue con el arranque normal (DECISIÓN SIN CONFIRMAR: 120 s y no usar `/f`). |
| V18-02 | Media | La rama sin perfil reiniciaba sin comprobar que no hubiera un backend vivo (huérfano). | Corregido: con backend respondiendo o puerto ocupado no reinicia. |
| V18-03 | Baja | El tope de 10 s de la intro podía vencer antes de verse la barra en un arranque en frío lento. | Corregido: 15 s. |
| V18-04 | Baja | Pruebas que no probaban la salida por cuenta o botón, `activo`, ni el camino del asistente sin cubierta. | Corregido: pruebas agregadas. |
| V18-05 | Baja | Pruebas del paso 07 solo de texto. | Residual (AN-26); cubierto en banco (I-15). |
| V18-06 | Baja | Reversión no exacta con fondos por monitor, presentación/Spotlight o sesión abierta con otro proceso. | Residual (AN-26), documentado. |
| V18-07 | Baja | Sin `-Usuario` ni `DefaultUserName`, el 07 actúa sobre la cuenta que ejecuta. | Residual (AN-26): el PC tiene una sola cuenta. |
| V18-08 | Baja | CLAUDE.md describía la cubierta como vigente. | Corregido en Z. |

Preguntas abiertas del revisor para Cristian: (1) ¿la tarjeta de E/S tiene watchdog que apague salidas sin comunicación? (relevante para cualquier reinicio con backend vivo; mitigado por V18-02); (2) ¿`SPIF_SENDCHANGE` puede colgar la difusión `WM_SETTINGCHANGE` y dejar el Setup esperando al paso 07? (medir en banco); (3) ¿REI-01 acepta reinicio sin `/f`?

## 6. Evaluación IEC 62304 / ISO 14971
- Solicitud de cambio: `decisiones_tanda_18.md` (ARR-06, REI-01, EST-08, EST-09), aprobadas por Cristian el 27-oct.
- Peligros:
  - REI-01 — reinicio no deseado del PC. Controles: solo con `CODIGO_INSTALACION_TERMINADA` y perfil válido; sin perfil no hay backend ni salidas, y ahora además se comprueba que no haya un backend escuchando; desactivado en desarrollo. Residual: reinicio bloqueado → hasta 120 s sin pantallas y arranque normal.
  - EST-08 — sin absorción de toques sobre el escritorio durante el arranque. Control: EST-09 (sin íconos ni barra). Residual: AN-28.
  - EST-09 — cambios de configuración del PC del usuario; reversible con respaldo. Residual: AN-26.
  - ARR-06 — ninguno nuevo (solo presentación; sin bitácora ni alarma).
- Regresión: suite completa (§7) frente a la base de `dev` (8488).

## 7. K, L y Z
Ver `docs/informes/informe_tanda_2026-10-27_t18.md` (índice) y `estado.md`.

## 8. DECISIONES SIN CONFIRMAR
- ARR-06: mensaje sostenido 2 s; tope de 15 s.
- REI-01: sin `/f`; espera de 120 s tras el código 0; no reiniciar con un backend escuchando; tope de 30 s para el comando; en la puerta 2 la cuenta empieza al detectar el perfil (hasta 2 s después que la de la puerta 1).
- EST-09: no reiniciar el Explorador; `BackgroundType=0` sin tocar `DesktopSpotlight`; sin `StuckRects3` solo aviso; respaldo de otro SID → no cambia y pide revertir; el PNG se copia desde `src/.../fondo-arranque.png`.

## 9. Pruebas manuales pendientes (hoja de banco, bloque I)
I-13 (ARR-06), I-14 (REI-01), I-07b (EST-08/09, sustituye a I-07), I-15 (EST-09), más: Reparar (`Aplicar paso 07 ... terminado`), perfil sin `StuckRects3`, Setup elevado con otra cuenta, reversión desde un fondo con presentación o Spotlight, y los dos scripts con `-WhatIf`.
