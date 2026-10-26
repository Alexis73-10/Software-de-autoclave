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

Ejemplo:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
cd C:\ruta\tools\estacion
.\01_cuenta_autologon.ps1 -WhatIf
.\01_cuenta_autologon.ps1
```

`_comun.ps1` no se ejecuta: lo cargan los demás (log, respaldo y restauración de valores).

## Desde el Setup (tanda 9, D9-11)

El Setup de Inno (`tools/instalador/`) aplica los pasos 01, 04 y 05 con la casilla "Configurar este PC como estación del autoclave", el 06 con su subcasilla "Asociar cada pantalla táctil con su monitor" (tanda 11, D11-5; solo aparece con 2 o más monitores, no se reaplica al Reparar y no corre en un Setup silencioso) y el 02 con la casilla "Arranque sin logo", sin interacción, a través de `tools/instalador/estacion_setup.ps1`; el desinstalador ejecuta los inversos de los pasos aplicados. Para eso:
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

En orden inverso (6 → 1), como administrador, también con `-WhatIf` primero:

```powershell
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
- [ ] Reversión probada al menos una vez en una máquina de prueba (los 6 inversos), con el log revisado.

## Pantallas táctiles: marcar los puertos USB (paso 6)

Windows guarda la asociación de cada táctil con su monitor **por puerto USB** (`HKLM\SOFTWARE\Microsoft\Wisp\Pen\Digimon`). Con dos paneles idénticos no hay otra forma de distinguirlos.

- Después de asociar, **marcar en el PC el puerto USB de cada táctil** y en cada cable la pantalla a la que va (por ejemplo, "Táctil pantalla 1 / puerto USB trasero superior"), y anotarlo en la hoja del equipo.
- **Cambiar el cable de un táctil a otro puerto deshace la asociación**: el toque de una pantalla aparece en la otra. Si pasa, devolver el cable a su puerto marcado o repetir la asociación como administrador: `"<RutaPrograma>\Autoclave.exe" --rol asociar-tactiles` (herramienta propia, EST-06 de la tanda 17) o `06_asociar_tactiles.ps1` (con `MultiDigitizer.exe`, si ese Windows lo trae: Panel de control › Configuración de Tablet PC › Configurar).
- Cambiar de puerto el cable de video también puede cambiar el orden de los monitores: marcar también los cables de video.
