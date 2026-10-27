# Estación Windows del autoclave — scripts de configuración

Scripts para dejar el PC industrial en modo quiosco según `docs/mis_plans/planeacion_estacion_windows.md`.
**Escritos en la tanda 6 (W1) y nunca ejecutados**: solo se validó que PowerShell los analiza sin errores de sintaxis. La primera ejecución debe hacerse en el PC industrial (o en una máquina de prueba), siempre primero con `-WhatIf`.

## Requisitos

- PowerShell 5.1 (viene con Windows 10/11), consola **como administrador**.
- Permitir la ejecución solo en esa consola: `Set-ExecutionPolicy -Scope Process Bypass`.
- Edición de Windows anotada (plan §10.1). En **Home** se ignoran las directivas de Windows Update y quizá `NoLockScreen`; los scripts las escriben igual, pero hay que comprobarlas en la lista de abajo.
- `Autoclave.exe` instalado. Desde la tanda 17 (INS-02) el Setup lo instala en `X:\Especifika\Autoclave\programa\` (`RutaPrograma` en `HKLM\SOFTWARE\Especifika\Autoclave`); antes, en `%ProgramFiles%\Especifika\Autoclave\`. Pasar `-Ejecutable` al paso 3 si no está en la ruta por defecto del script.

## Orden de ejecución

Primero simular cada uno con `-WhatIf`; luego sin él. Reiniciar al final.

| # | Script | Qué hace | Plan |
|---|---|---|---|
| 1 | `01_cuenta_autologon.ps1 [-Usuario operador]` | Cuenta local estándar e inicio de sesión automático (pide la contraseña) | §3.1, §4 |
| 2 | `02_arranque_silencioso.ps1` | Copia del BCD, `bootux disabled`, sin pantalla de bloqueo ni contraseña al reanudar | §3.3, §3.4 |
| 3 | `03_tarea_autoclave.ps1 [-Usuario operador] [-Ejecutable ruta]` | Tarea "al iniciar sesión" que lanza `Autoclave.exe`, 3 reintentos cada minuto | §3.2, §8 |
| 4 | `04_notificaciones_actualizaciones_gestos.ps1 [-HoraActivaInicio 6 -HoraActivaFin 23]` | Sin notificaciones, Windows Update sin reinicio automático y diferido, sin gestos de borde | §5 |
| 5 | `05_plan_energia.ps1` | Sin suspensión, hibernación ni apagado de pantalla; botón de encendido "no hacer nada" | §7 |
| 6 | `06_asociar_tactiles.ps1 [-MinutosEspera 10]` | Asocia cada pantalla táctil con su monitor: abre `%windir%\System32\MultiDigitizer.exe` y pide tocar cada pantalla una vez. Solo con 2 o más monitores | D11-5 (tanda 11) |
| 7 | `07_escritorio_estacion.ps1 [-Usuario cuenta -Dominio equipo] [-Imagen ruta]` | Escritorio de la estación en el perfil de la cuenta del inicio automático: fondo de Especifika (Rellenar, todos los monitores, tipo «Imagen»), barra de tareas con «Ocultar automáticamente» e íconos del escritorio ocultos. Ver «Paso 7» abajo | EST-09 (tanda 18) |
| 8 | `08_red_modulos.ps1 -Adaptador <MAC>` | Red de los módulos de E/S: el adaptador Ethernet dedicado (elegido por su MAC) queda en `192.168.3.10/24`, sin puerta de enlace ni DNS y sin DHCP. Ver «Paso 8» abajo | T20-05 (tanda 20) |

Ejemplo:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
cd C:\ruta\tools\estacion
.\01_cuenta_autologon.ps1 -WhatIf
.\01_cuenta_autologon.ps1
```

`_comun.ps1` no se ejecuta: lo cargan los demás (log, respaldo y restauración de valores).

## Paso 7: escritorio de la estación (EST-09, tanda 18)

El PC tiene una sola cuenta (la que instala y entra con el inicio automático). El paso 7 cambia tres ajustes **del perfil de esa cuenta** (HKCU). Como corre elevado, no usa el HKCU del proceso: resuelve la cuenta (`-Usuario`/`-Dominio`; si no llegan, `Winlogon\DefaultUserName`/`DefaultDomainName` del paso 1; si tampoco, la cuenta que ejecuta) y escribe en `HKEY_USERS\<SID>`. Con la sesión de esa cuenta cerrada carga su `NTUSER.DAT` (`reg load` en `HKU\EspecifikaEstacion07`) y lo descarga al terminar. La imagen es `fondo_estacion.png` junto al script (el Setup la instala en `{app}\estacion\`, copia de `src/autoclave/ui_qml/assets/fondos/fondo-arranque.png`); suelto en el repositorio usa esa imagen de la intro.

| Ajuste | Valor de registro / API | Fuente | Cuándo surte efecto |
|---|---|---|---|
| Fondo, modo Rellenar | `HKCU\Control Panel\Desktop`: `WallpaperStyle="10"`, `TileWallpaper="0"`, `Wallpaper=<ruta>` (REG_SZ) | Microsoft Learn: «Desktop wallpaper» (directiva) y `SystemParametersInfoW` | Al aplicar la API (abajo); si no, en el siguiente inicio de sesión |
| Fondo en todos los monitores, en el acto | `user32!SystemParametersInfoW(SPI_SETDESKWALLPAPER, 0, ruta, SPIF_UPDATEINIFILE \| SPIF_SENDCHANGE)` | Microsoft Learn: `SystemParametersInfoW` | En el acto, **solo si el script corre con la cuenta de la estación** (si no, cambiaría el fondo de otra cuenta) |
| Tipo de fondo «Imagen» (sin presentación ni Spotlight) | `HKCU\...\Explorer\Wallpapers`: `BackgroundType=0` (REG_DWORD; 1 color, 2 presentación, 3 Spotlight) | Valor que escribe Configuración › Personalización › Fondo; no documentado formalmente (DECISIÓN SIN CONFIRMAR) | Siguiente inicio de sesión |
| Barra «Ocultar automáticamente» | `HKCU\...\Explorer\StuckRects3\Settings` (REG_BINARY): byte 8, bit `0x01` (`0x03` activa, `0x02` desactiva); solo cambia ese bit | Formato del Explorador, no documentado (DECISIÓN SIN CONFIRMAR) | Siguiente inicio de sesión |
| Barra, en el acto | `shell32!SHAppBarMessage(ABM_SETSTATE, ABS_AUTOHIDE \| ABS_ALWAYSONTOP)` | Microsoft Learn: «ABM_SETSTATE message» | En el acto, solo con la cuenta de la estación (el Explorador guarda el estado él mismo; no se reinicia el Explorador) |
| Íconos del escritorio ocultos | `HKCU\...\Explorer\Advanced`: `HideIcons=1` (REG_DWORD), el de «Ver › Mostrar iconos del escritorio» | Valor del Explorador (DECISIÓN SIN CONFIRMAR) | Siguiente inicio de sesión (o al reiniciar el Explorador) |

- Si `StuckRects3\Settings` no existe (perfil en el que el Explorador nunca corrió), el paso lo anota como aviso y no fija la barra; Reparar o repetir el paso lo vuelve a intentar.
- El ocultamiento total de la barra mientras corre Autoclave (`ui_qml/barra_tareas.py`) sigue igual.
- Respaldo: `respaldo_07_escritorio_estacion.json`, con el SID de la cuenta y cada valor original (también si no existía). Los valores que puede tocar el paso (y restaurar el inverso) son solo los de `ValoresUsuarioGestionados` de `_comun.ps1`. Si el respaldo es de otra cuenta, el paso no cambia nada y pide revertir primero.

## Paso 8: red de los módulos de E/S (T20-05, tanda 20)

El módulo M31-U está fijo en `192.168.3.7:502` (decisión 3 de `docs/mis_plans/decisiones_tanda_20.md`); el PC necesita un adaptador Ethernet dedicado en la misma red. `08_red_modulos.ps1 -Adaptador <MAC>` (MAC con `-`, `:` o sin separadores; no es secreta):

- Busca el adaptador **solo entre los Ethernet físicos**: `Get-NetAdapter -Physical` con `NdisPhysicalMedium = 14` (802.3). Rechaza Wi-Fi (`9`), Bluetooth (`10`) y adaptadores virtuales o VPN (`Virtual = True` o medio `0`).
- Si **otro** adaptador ya tiene una IPv4 en `192.168.3.0/24`, en la configuración activa **o en la persistente** (`PersistentStore`: una IP fija con el cable desconectado solo está ahí; V20-s3-04), termina con error **sin cambiar nada** (dos adaptadores en esa red rompen la ruta al módulo).
- Respaldo **antes** de cambiar nada, solo la primera vez: `respaldo_08_red_modulos.json` en `<RutaDatos>\estacion\` (nombre por la convención `respaldo_<paso>.json` de `_comun.ps1`; la decisión T20-05 lo llamaba `respaldo_08.json`), con MAC, alias, DHCP sí/no, IPv4 manuales con prefijo, puertas de enlace, DNS y métricas (V20-s3-09: `MetricaAutomatica`/`MetricaInterfaz` de la interfaz y `MetricasRuta` de cada ruta por defecto; un respaldo anterior sin ellas sigue valiendo). Si el respaldo es de otro adaptador, no cambia nada y pide revertir primero (el Setup, al cambiar de adaptador, revierte antes: V20-s3-01).
- Aplica: DHCP desactivado (`Set-NetIPInterface -Dhcp Disabled`), quita las rutas `0.0.0.0/0` y las demás IPv4 del adaptador, `New-NetIPAddress 192.168.3.10 -PrefixLength 24` **sin** `-DefaultGateway` (si la `.10` no está en la configuración persistente, antes la quita de los dos almacenes, para que `New-NetIPAddress` no falle con «ya existe») y DNS sin servidores (`Set-DnsClientServerAddress -ResetServerAddresses`).
- Si algo falla **a mitad** de la aplicación (V20-s3-02), restaura desde el respaldo llamando a `08_revertir_red_modulos.ps1` y relanza el error (el puente devuelve 1). Si la restauración también falla, el inverso deja el adaptador en DHCP con DNS automático como último recurso.
- Verifica después (hasta 15 s) que `192.168.3.10/24` quedó en **ese** adaptador, con DHCP desactivado y sin puerta de enlace; una `169.254.x.x` no cuenta (lección del banco: la ventana de Windows a veces no aplicaba la IP fija). Con el cable desconectado acepta la dirección de la configuración persistente. Si no quedó, termina con error.
- Idempotente («Sin cambio» si ya está así). Cualquier fallo termina con error (el puente devuelve 1).
- Las funciones sin efectos (validación de la MAC y de la subred, filtro de adaptadores, conflicto, respaldo) están en `_red_modulos_puras.ps1`, que las pruebas cargan solas con datos ficticios.
- Inverso: `08_revertir_red_modulos.ps1` restaura desde el respaldo (DHCP con DNS automático si estaba en DHCP; si no, las IPv4, puertas de enlace con su métrica y DNS fijos guardados; y la métrica de la interfaz si el respaldo la trae). Sin respaldo no toca nada; con un respaldo de forma inválida, si el adaptador ya no está o si algo falla, termina con error y **conserva** el respaldo. Si falla después de empezar a quitar las IPv4, como último recurso deja DHCP y DNS automático (`Set-NetIPInterface -Dhcp Enabled` y `Set-DnsClientServerAddress -ResetServerAddresses`) y relanza el error.
- **Limitación de los DNS (V20-s3-09):** `Get-DnsClientServerAddress` no distingue los DNS escritos a mano de los que dio el DHCP, y el script no lee el registro para saberlo. Por eso, un adaptador que estaba en **DHCP con DNS manuales** vuelve con DNS **automático** (hay que reescribirlos a mano); con IP fija, los DNS guardados sí se restauran.

## Desde el Setup (tanda 9, D9-11)

El Setup de Inno (`tools/instalador/`) aplica los pasos 01, 04, 05 y 07 (EST-09, tanda 18: después del 05 y antes del 06, sin casilla propia; un fallo del 07 no interrumpe los demás) con la casilla "Configurar este PC como estación del autoclave", el 06 con su subcasilla "Asociar cada pantalla táctil con su monitor" (tanda 11, D11-5; solo aparece con 2 o más monitores, no se reaplica al Reparar y no corre en un Setup silencioso) y el 02 con la casilla "Arranque sin logo", sin interacción, a través de `tools/instalador/estacion_setup.ps1`; el desinstalador ejecuta los inversos de los pasos aplicados. El 08 (T20-05, tanda 20) no depende de la casilla de la estación: lo aplica la página «Red de los módulos de E/S» con el adaptador elegido (`estacion_setup.ps1 -Paso 08 -Accion Aplicar -Adaptador <MAC>`), Reparar lo reaplica con el adaptador guardado (`Adaptador08`; si se elige otro, primero revierte el 08 en el anterior y, si esa reversión falla, no cambia de adaptador: V20-s3-01) y el desinstalador lo revierte primero. Sin asistente, `/ADAPTADOR=<MAC>`; si ese adaptador es el único con puerta de enlace, el Setup se detiene salvo con `/ADAPTADORCONFIRMADO=1` (V20-s3-05; ver `tools/instalador/LEEME.md`). Para eso:
- `01_cuenta_autologon.ps1` acepta `-Dominio` (por defecto el nombre del equipo), `-NoCrearCuenta` (falla sin cambiar nada si la cuenta local no existe) y `-ContrasenaDesdeEntorno` (toma la contraseña de la variable `AUTOCLAVE_CLAVE_AUTOLOGON` del proceso y la borra). Sin esos parámetros se comporta como antes (pide la contraseña). `AutoAdminLogon` se activa al final, después de usuario, dominio y contraseña.
- La carpeta de la estación (`<RutaDatos>\estacion\`, ver «Log y respaldos») queda solo para Administradores y SYSTEM (dueño Administradores, sin herencia), porque la carpeta de datos tiene Modificar para Usuarios y los inversos corren como administrador con lo que diga `respaldo_<paso>.json`. Se aplica también al simular con `-WhatIf`.
- Los inversos solo restauran los valores de registro de la lista `ValoresGestionados` de `_comun.ps1` (un respaldo alterado no puede escribir otra clave), y `05_revertir…` solo importa el `.pow` de esa carpeta. Un paso nuevo que escriba otro valor debe agregarlo a esa lista (`tests/test_t9_e9_setup_estacion.py` lo comprueba).
- El log muestra `DefaultPassword` como `********`.

## Log y respaldos

- Carpeta de la estación (tanda 17, INS-02): `<RutaDatos>\estacion\`, con `RutaDatos` leído por `_comun.ps1` de `HKLM\SOFTWARE\Especifika\Autoclave` en la vista de 64 bits (p. ej. `D:\Especifika\Autoclave\datos\estacion\`). El Setup escribe esa clave antes de correr los pasos. **Sin la clave** (scripts sueltos en un PC sin el Setup nuevo, o una instalación anterior): `%ProgramData%\Especifika\Autoclave\estacion\`, como antes. Los inversos deben correr con la misma clave que los pasos (si se desinstala Autoclave antes de revertir a mano, la clave ya no está: buscar los respaldos en `datos\estacion\` y copiarlos a la carpeta de respaldo, o volver a escribir la clave).
- Log de todas las ejecuciones (también las simuladas): `estacion.log` en esa carpeta.
- Valores originales que cambia cada paso: `respaldo_<paso>.json` en la misma carpeta. Se guardan solo la primera vez, así que correr un script dos veces no pierde el valor original.
- Copia del BCD (`bcd_respaldo.bcd`) y del plan de energía (`plan_energia_respaldo.pow`) en la misma carpeta.

Todos los scripts son idempotentes: si el valor ya está, lo anotan como "Sin cambio" y siguen.

## Cómo revertir

En orden inverso (8 → 1), como administrador, también con `-WhatIf` primero:

```powershell
.\08_revertir_red_modulos.ps1
.\07_revertir_escritorio_estacion.ps1
.\06_revertir_asociar_tactiles.ps1
.\05_revertir_plan_energia.ps1
.\04_revertir_notificaciones_actualizaciones_gestos.ps1
.\03_revertir_tarea_autoclave.ps1
.\02_revertir_arranque_silencioso.ps1
.\01_revertir_cuenta_autologon.ps1 [-EliminarCuenta]
```

- Cada inverso usa el `respaldo_<paso>.json`: si un valor no existía antes, lo borra; si existía, le devuelve su valor.
- `01_revertir…` solo borra la cuenta con `-EliminarCuenta` y solo si la creó el paso 1; el perfil de `C:\Users` queda.
- `05_revertir…` reimporta el plan original con un GUID nuevo; el plan modificado queda en la lista (`powercfg /list`, borrar con `powercfg /delete`).
- `06_revertir…` borra solo las asociaciones táctil-monitor que creó el paso 6 y devuelve su dato a las que cambió (según `respaldo_06_asociar_tactiles.json`); las que ya había antes quedan. Sin ese respaldo no borra nada. **Ojo:** "creada por el paso" quiere decir "que no estaba antes de la primera vez que corrió el paso 6", así que también borra las asociaciones rehechas después (a mano desde el Panel de control, al cambiar un táctil o al repetir el paso). Tras desinstalar o revertir, hay que volver a asociar las pantallas. Si un valor no se puede revertir, el script termina con error y conserva el respaldo para reintentarlo.
- `07_revertir…` devuelve el fondo, el modo de la barra y la visibilidad de los íconos a lo respaldado en `respaldo_07_escritorio_estacion.json` (si un valor no existía, lo borra), en el perfil del SID respaldado. Con la cuenta de la estación vuelve a aplicar el fondo y la barra en el acto; los íconos (y, sin esa sesión, todo) vuelven en el siguiente inicio de sesión. Si un valor falla, termina con error y conserva el respaldo.
- `08_revertir…` devuelve el adaptador de los módulos a lo respaldado en `respaldo_08_red_modulos.json` (DHCP y DNS automático, o la configuración fija anterior, con las métricas si se respaldaron). Sin respaldo no toca nada; si falla, termina con error y conserva el respaldo (tras empezar a quitar las IPv4, deja antes DHCP y DNS automático como último recurso).
- Si el arranque falla tras el paso 2: desde el entorno de recuperación, `bcdedit /import <carpeta de la estación>\bcd_respaldo.bcd` (p. ej. `D:\Especifika\Autoclave\datos\estacion\bcd_respaldo.bcd`; antes de la tanda 17, `%ProgramData%\Especifika\Autoclave\estacion\`).

## Lo que no cubren los scripts

- **AnyDesk**: el plan (§6) define instalarlo **sin acceso desatendido por defecto**, que es su configuración de fábrica. No hay script: instalar a mano y no activar el acceso desatendido salvo durante un mantenimiento, con contraseña fuerte y lista blanca de ID.
- **Shell Launcher / Assigned Access** y **Keyboard Filter** (requieren Pro/Enterprise/Education; edición sin confirmar).
- Ocultar el administrador de tareas, `cmd`, PowerShell y el Explorador para la cuenta del operador (§4): falta decidir cómo entra el técnico; aplicarlo antes podría dejarlo fuera.
- BIOS "restaurar tras pérdida de energía = encendido", UPS, permisos de `%ProgramData%`, exclusión del antivirus y tareas de respaldo/limpieza (§5, §7, §8).

## Lista de comprobación en el PC industrial

- [ ] Edición de Windows anotada: ________
- [ ] Cada script corrido primero con `-WhatIf`, revisado el log, luego sin `-WhatIf`.
- [ ] La cuenta del operador es **estándar** (no está en Administradores) y existe una cuenta de técnico administradora distinta.
- [ ] Arranque en frío: de encendido a pantallas en < 90 s, sin logo, sin login, sin pantalla de bloqueo.
- [ ] `Autoclave.exe` arranca solo; si se cierra a la fuerza, la tarea lo relanza (hasta 3 veces).
- [ ] Ninguna notificación de Windows aparece sobre las pantallas.
- [ ] Deslizar desde los bordes de la pantalla táctil no abre nada.
- [ ] Windows Update: horas activas 6–23 visibles en Configuración; una actualización pendiente no reinicia el equipo con la sesión abierta. En Home anotar si las directivas se ignoran.
- [ ] Sin suspensión ni apagado de pantalla tras 30 min sin uso; hibernación desactivada (`powercfg /a`).
- [ ] El botón físico de encendido no hace nada; "Apagar equipo" del software sí apaga.
- [ ] Corte de energía (hojas C-03 y F-03): el equipo vuelve solo (ajuste de BIOS) y el software pide el estado seguro si corresponde.
- [ ] Dos monitores con la barra de tareas oculta en ambos.
- [ ] Pantallas táctiles asociadas (paso 6): tocar cada pantalla responde en esa misma pantalla; `estacion.log` dice `Asociaciones tactiles en ...: 2` (o más). **Puertos USB marcados** (ver abajo).
- [ ] Tras reiniciar el PC, cada táctil sigue respondiendo en su pantalla.
- [ ] AnyDesk instalado sin acceso desatendido; una sesión remota exige aceptación en sitio.
- [ ] Escritorio de la estación (paso 7, I-07b): tras iniciar sesión solo se ve el fondo de Especifika (Rellenar, en los dos monitores), sin íconos y con la barra de tareas oculta; Configuración › Personalización › Fondo dice «Imagen».
- [ ] Red de los módulos (paso 8, M-7): `Get-NetIPAddress -AddressFamily IPv4` muestra `192.168.3.10/24` en el adaptador dedicado, sin puerta de enlace (`Get-NetRoute -DestinationPrefix 0.0.0.0/0`), y `ping 192.168.3.7` responde.
- [ ] Reversión probada al menos una vez en una máquina de prueba (los 8 inversos), con el log revisado (I-15: `Revertir paso 07 ... terminado`; fondo, barra e íconos originales).

## Pantallas táctiles: marcar los puertos USB (paso 6)

Windows guarda la asociación de cada táctil con su monitor **por puerto USB** (`HKLM\SOFTWARE\Microsoft\Wisp\Pen\Digimon`). Con dos paneles idénticos no hay otra forma de distinguirlos.

- Después de asociar, **marcar en el PC el puerto USB de cada táctil** y en cada cable la pantalla a la que va (por ejemplo, "Táctil pantalla 1 / puerto USB trasero superior"), y anotarlo en la hoja del equipo.
- **Cambiar el cable de un táctil a otro puerto deshace la asociación**: el toque de una pantalla aparece en la otra. Si pasa, devolver el cable a su puerto marcado o repetir la asociación como administrador: `"<RutaPrograma>\Autoclave.exe" --rol asociar-tactiles` (herramienta propia, EST-06 de la tanda 17) o `06_asociar_tactiles.ps1` (con `MultiDigitizer.exe`, si ese Windows lo trae: Panel de control › Configuración de Tablet PC › Configurar).
- Cambiar de puerto el cable de video también puede cambiar el orden de los monitores: marcar también los cables de video.
