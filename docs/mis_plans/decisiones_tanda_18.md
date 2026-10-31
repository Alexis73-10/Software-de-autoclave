# Decisiones — Tanda 18: hallazgos de la instalación de la 1.0.0-alpha.2 (27-oct)

Origen: primera instalación de `entrega\v1.0.0-alpha.2_2026-10-26\Autoclave_Setup_1.0.0-alpha.2.exe` en el equipo de pruebas (desinstalada la alpha.1, instalación limpia, casilla «Configurar este PC como estación» marcada). Este archivo es la fuente de verdad de la tanda y prevalece sobre `decisiones_tanda_17.md` donde choque (en particular EST-07).

Observaciones de Cristian en el equipo:
1. Sin perfil de instalación (primer arranque) no se mostró la intro de arranque: solo el texto «Iniciando… / Starting…» de la cubierta EST-07 y luego el asistente.
2. En el arranque normal (con perfil) aparece «Iniciando… / Starting…» antes de la animación de arranque.

Causa (revisión del código, 27-oct):
- `exe_unico.py` (rol lanzador, ~l. 369): si `requiere_instalacion()` es verdadero, abre directamente el asistente en la puerta 1 y el Reposo de instalación en la puerta 2, sin intro y sin backend. Diseño vigente desde la compilación A, no una regresión.
- La cubierta EST-07 (`estacion/cubierta_arranque.py`, `TITULO`/`TEXTO`, l. 49–50) pinta «e-specifika» e «Iniciando… / Starting…» desde que se abre el lanzador hasta el primer cuadro de las pantallas QML.

## Decisiones de Cristian (no reabrir)

### ARR-06 · Intro de arranque también sin perfil de instalación
- Sin perfil (o con perfil inválido), el arranque muestra la **intro completa** (animación y barra) en las **dos pantallas**, igual que un arranque normal, antes de pasar al asistente.
- La barra recorre solo las etapas de origen lanzador (`ETAPAS_ARRANQUE` en `backend/arranque/registro.py`: `verificando_instalacion`, `liberando_procesos`). Las etapas del backend no se muestran porque el backend no arranca sin perfil (se conserva).
- En `verificando_instalacion` la barra se detiene y muestra:
  - sin perfil: «Sin perfil de instalación: se abre el asistente» / «No installation profile: opening the setup wizard»;
  - perfil presente pero inválido: «Perfil de instalación inválido: se abre el asistente» / «Invalid installation profile: opening the setup wizard».
  El mensaje se sostiene ~2 s (DECISIÓN SIN CONFIRMAR: duración) y luego la intro hace su salida normal: la puerta 1 pasa al asistente y la puerta 2 al Reposo de instalación en curso (W10/D10-4, sin cambios).
- **No se escribe nada en la bitácora** (coherente con BIT: mientras la instalación no termina no se escribe). Solo el log de desarrollo (`lanzador.log`, `ui_puerta*.log`).
- No es un fallo de arranque bloqueante ni una alarma: es el camino normal de un PC nuevo. No usa colores de alarma (D-08).
- La distinción «sin perfil» / «inválido» usa el mismo criterio que `requiere_instalacion()` (`ui_qml/bridge/puente_instalacion.py`); si hoy no distingue, Code agrega la distinción sin cambiar el resultado booleano.

### REI-01 · Reinicio del PC al terminar el asistente (aprobado 1–5, 27-oct)
1. **Pantalla final del asistente:** «Instalación completada. El equipo se reiniciará en 10 s» con cuenta regresiva visible, botón **«Reiniciar ahora»** y **sin cancelar** (el perfil ya quedó grabado y bloqueado). La puerta 2 (Reposo de instalación) muestra el mismo aviso. Se retira el texto actual «Reinicie el software» de esa pantalla. Bilingüe.
2. **Quién reinicia:** el **lanzador**, al recibir del asistente `CODIGO_INSTALACION_TERMINADA` (y comprobar que `requiere_instalacion()` ya es falso), ejecuta `shutdown /r /t 0`. Reemplaza el camino actual «seguir al arranque normal sin reiniciar» (`exe_unico.py`, tras `asistente.wait()`). El backend no interviene (no está corriendo). La cuenta regresiva vive en la pantalla del asistente; el asistente sale con el código al llegar a 0 o al pulsar «Reiniciar ahora».
3. **Si Windows niega o falla el reinicio** (código distinto de 0, excepción o tiempo agotado): se anota en `lanzador.log` y se sigue con el **arranque normal** como hoy, para que el equipo no quede detenido.
4. **Solo en el ejecutable compilado** (`sys.frozen`) y en Windows. En desarrollo no reinicia el PC: se anota en el log y se sigue con el arranque normal. Una variable de entorno (`AUTOCLAVE_REINICIO_PC=1`) lo activa a propósito y `=0` lo desactiva siempre (mismo patrón que la antigua `AUTOCLAVE_CUBIERTA`).
5. **PC sin estación configurada:** tras el reinicio queda en el inicio de sesión de Windows y Autoclave arranca al entrar si la tarea de arranque existe. Es lo esperado; no se fuerza nada más.
- Aplica a toda salida exitosa del asistente, también a la reinstalación del perfil (LEEME §7).
- Sin bitácora propia: la fila `equipo_instalado` (BIT) ya se escribe al terminar el asistente, antes del reinicio. Code verifica que esa escritura termine (y la base quede cerrada) antes de `shutdown`.

### EST-08 · Se retira la cubierta de arranque (revierte EST-07, salvo `Delay PT0S`)
- Se elimina por completo la cubierta Win32 negra: `estacion/cubierta_arranque.py`, `estacion/primer_cuadro.py`, `AvisoPrimerCuadro`/`avisar_primer_cuadro` en `ui_qml/app.py`, `_abrir_cubierta`/`_cerrar_cubierta` y su reapertura tras el asistente en `exe_unico.py`, y la variable `AUTOCLAVE_CUBIERTA`.
- `estacion/_ventanas.py` (`VentanasTexto`) **se conserva**: la usa `estacion/asociar_tactiles.py` (EST-06).
- Se conserva `Delay PT0S` de la tarea de arranque (EST-07, primera viñeta).
- `tests/test_t17_s2_cubierta_arranque.py`: se retira junto con el código que prueba, citando EST-08 en el commit y en el informe (excepción autorizada a la regla de no borrar pruebas: la funcionalidad deja de existir por decisión de Cristian). Las demás pruebas que mencionen la cubierta se ajustan citando EST-08.
- Lo que se ve entre el inicio de sesión y la intro pasa a resolverlo EST-09.
- La prueba manual I-07 de la hoja de banco queda sustituida por I-07b (EST-09).

### EST-09 · Paso 07 de la estación: escritorio de la estación (aprobado 1–5, 27-oct)
Contexto: el PC tiene **una sola cuenta** (la principal, que instala y se usa con el inicio automático). No se reemplaza el shell ni se crea una cuenta de operador.

Nuevo par de scripts en `tools/estacion/`: `07_escritorio_estacion.ps1` y `07_revertir_escritorio_estacion.ps1`, con el mismo patrón que los pasos 01–06 (`_comun.ps1`, `-WhatIf`, log en `datos\estacion\estacion.log`, respaldo de los valores originales en `datos\estacion\`, idempotentes). Aplicados a la cuenta del inicio automático (la que instala).
1. **Fondo de pantalla:** la misma imagen de fondo de la intro (`ui_qml/assets/fondos/fondo-arranque.png`), instalada como `{app}\estacion\fondo_estacion.png` (carpeta `programa`, solo administradores escriben). Modo **Rellenar**, la misma imagen en todos los monitores. Tipo de fondo «Imagen» (no presentación ni Windows Spotlight).
2. **Barra de tareas:** «Ocultar automáticamente» desde Windows, permanente para la sesión. Se mantiene además el ocultamiento total mientras corre Autoclave (`ui_qml/barra_tareas.py`, sin cambios).
3. **Íconos del escritorio:** ocultos.
4. **Reversión:** el script de reversión y el desinstalador devuelven el fondo, el modo de la barra y la visibilidad de los íconos a los valores respaldados.
5. Code documenta en el script y en el informe qué valor de registro o API usa para cada ajuste, con la fuente (p. ej. `Control Panel\Desktop` + `SystemParametersInfo(SPI_SETDESKWALLPAPER)`, `Explorer\Advanced\HideIcons`, `Explorer\StuckRects3`), y cómo se aplica sin reiniciar o si queda para el siguiente inicio de sesión (el Setup ya pide reiniciar).

Integración en el Setup (`tools/instalador/autoclave.iss`, `estacion_setup.ps1`):
- Se aplica con la casilla «Configurar este PC como estación» (sin casilla propia), después del paso 05 y antes del 06.
- Se anota en `HKLM\SOFTWARE\Especifika\Autoclave\Estacion` (`Paso07`), con `[CustomMessages]` `es.Paso07`/`en.Paso07` («escritorio de la estación (paso 07)» / «station desktop (step 07)») en la lista de fallas.
- El desinstalador lo revierte primero (orden inverso: 07, 06, 05, 04, 02, 01).
- **Reparar** lo vuelve a aplicar (no pide contraseña, como 04/05/02).
- Un fallo del paso 07 no interrumpe los demás pasos ni la instalación (como el 06).
- `tools/estacion/LEEME.md` y `tools/instalador/LEEME.md` (lista de verificación) se actualizan.

## Pruebas manuales nuevas (hoja de banco, bloque I)
- **I-13 (ARR-06):** sin perfil, la intro se ve en las dos pantallas, la barra se detiene en «Sin perfil de instalación…» y pasa al asistente (puerta 1) y al Reposo (puerta 2).
- **I-14 (REI-01):** al terminar el asistente, cuenta regresiva de 10 s en las dos pantallas, «Reiniciar ahora» funciona, el PC reinicia; tras el reinicio: inicio automático, escritorio de la estación y arranque normal con intro y barra completas.
- **I-07b (EST-08/EST-09, sustituye a I-07):** desde que entra Windows hasta la intro solo se ve el fondo de Especifika, sin barra de tareas ni íconos, y sin el texto «Iniciando… / Starting…»; medir con cronómetro el tiempo desde el inicio de sesión hasta la intro.
- **I-15 (EST-09):** desinstalar devuelve el fondo, la barra y los íconos originales (`estacion.log`: `Revertir paso 07 ... terminado`).

## Riesgo (para el informe, ISO 14971 / IEC 62304)
- REI-01: un reinicio no deseado del PC. Control: solo tras `CODIGO_INSTALACION_TERMINADA` con perfil válido, nunca con un ciclo posible (sin perfil no hay backend ni salidas); en desarrollo desactivado. Residual: si el reinicio falla, se sigue como hoy.
- EST-08: se pierde la absorción de toques sobre el escritorio durante el arranque. Control: EST-09 (sin íconos ni barra visibles); el escritorio solo es accesible antes de que abra la intro. Residual: anotado como anomalía conocida de la entrega.

## Ejecución
- Sin supervisión, con `lanzar_tanda.ps1 -Tanda 18`.
- **Hasta 4 subagentes a la vez.**
- Cierra con **K**: entrega 1.0.0-alpha.3.
