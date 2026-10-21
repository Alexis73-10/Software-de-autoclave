# Estación Windows del autoclave — scripts de configuración

Scripts para dejar el PC industrial en modo quiosco según `docs/mis_plans/planeacion_estacion_windows.md`.
**Escritos en la tanda 6 (W1) y nunca ejecutados**: solo se validó que PowerShell los analiza sin errores de sintaxis. La primera ejecución debe hacerse en el PC industrial (o en una máquina de prueba), siempre primero con `-WhatIf`.

## Requisitos

- PowerShell 5.1 (viene con Windows 10/11), consola **como administrador**.
- Permitir la ejecución solo en esa consola: `Set-ExecutionPolicy -Scope Process Bypass`.
- Edición de Windows anotada (plan §10.1). En **Home** se ignoran las directivas de Windows Update y quizá `NoLockScreen`; los scripts las escriben igual, pero hay que comprobarlas en la lista de abajo.
- `Autoclave.exe` instalado en `%ProgramFiles%\Especifika\Autoclave\` (o pasar `-Ejecutable` al paso 3).

## Orden de ejecución

Primero simular cada uno con `-WhatIf`; luego sin él. Reiniciar al final.

| # | Script | Qué hace | Plan |
|---|---|---|---|
| 1 | `01_cuenta_autologon.ps1 [-Usuario operador]` | Cuenta local estándar e inicio de sesión automático (pide la contraseña) | §3.1, §4 |
| 2 | `02_arranque_silencioso.ps1` | Copia del BCD, `bootux disabled`, sin pantalla de bloqueo ni contraseña al reanudar | §3.3, §3.4 |
| 3 | `03_tarea_autoclave.ps1 [-Usuario operador] [-Ejecutable ruta]` | Tarea "al iniciar sesión" que lanza `Autoclave.exe`, 3 reintentos cada minuto | §3.2, §8 |
| 4 | `04_notificaciones_actualizaciones_gestos.ps1 [-HoraActivaInicio 6 -HoraActivaFin 23]` | Sin notificaciones, Windows Update sin reinicio automático y diferido, sin gestos de borde | §5 |
| 5 | `05_plan_energia.ps1` | Sin suspensión, hibernación ni apagado de pantalla; botón de encendido "no hacer nada" | §7 |

Ejemplo:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
cd C:\ruta\tools\estacion
.\01_cuenta_autologon.ps1 -WhatIf
.\01_cuenta_autologon.ps1
```

`_comun.ps1` no se ejecuta: lo cargan los demás (log, respaldo y restauración de valores).

## Log y respaldos

- Log de todas las ejecuciones (también las simuladas): `%ProgramData%\Especifika\Autoclave\estacion\estacion.log`.
- Valores originales que cambia cada paso: `respaldo_<paso>.json` en la misma carpeta. Se guardan solo la primera vez, así que correr un script dos veces no pierde el valor original.
- Copia del BCD (`bcd_respaldo.bcd`) y del plan de energía (`plan_energia_respaldo.pow`) en la misma carpeta.

Todos los scripts son idempotentes: si el valor ya está, lo anotan como "Sin cambio" y siguen.

## Cómo revertir

En orden inverso (5 → 1), como administrador, también con `-WhatIf` primero:

```powershell
.\05_revertir_plan_energia.ps1
.\04_revertir_notificaciones_actualizaciones_gestos.ps1
.\03_revertir_tarea_autoclave.ps1
.\02_revertir_arranque_silencioso.ps1
.\01_revertir_cuenta_autologon.ps1 [-EliminarCuenta]
```

- Cada inverso usa el `respaldo_<paso>.json`: si un valor no existía antes, lo borra; si existía, le devuelve su valor.
- `01_revertir…` solo borra la cuenta con `-EliminarCuenta` y solo si la creó el paso 1; el perfil de `C:\Users` queda.
- `05_revertir…` reimporta el plan original con un GUID nuevo; el plan modificado queda en la lista (`powercfg /list`, borrar con `powercfg /delete`).
- Si el arranque falla tras el paso 2: desde el entorno de recuperación, `bcdedit /import %ProgramData%\Especifika\Autoclave\estacion\bcd_respaldo.bcd`.

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
- [ ] AnyDesk instalado sin acceso desatendido; una sesión remota exige aceptación en sitio.
- [ ] Reversión probada al menos una vez en una máquina de prueba (los 5 inversos), con el log revisado.
