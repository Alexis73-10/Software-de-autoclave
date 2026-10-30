# W1 — Scripts de la estación Windows (tanda 6)

Fecha: 2026-10-21. Base: `docs/mis_plans/planeacion_estacion_windows.md`. **Ningún script se ejecutó.**

## Entregables (`tools/estacion/`)

| Paso | Script | Inverso |
|---|---|---|
| — | `_comun.ps1` (log, respaldo/restauración de registro, verificación de administrador) | — |
| 1 | `01_cuenta_autologon.ps1` | `01_revertir_cuenta_autologon.ps1` |
| 2 | `02_arranque_silencioso.ps1` | `02_revertir_arranque_silencioso.ps1` |
| 3 | `03_tarea_autoclave.ps1` | `03_revertir_tarea_autoclave.ps1` |
| 4 | `04_notificaciones_actualizaciones_gestos.ps1` | `04_revertir_notificaciones_actualizaciones_gestos.ps1` |
| 5 | `05_plan_energia.ps1` | `05_revertir_plan_energia.ps1` |
| — | `LEEME.md` (orden, reversión, lista de comprobación) | — |

Todos: `[CmdletBinding(SupportsShouldProcess)]` (`-WhatIf`), idempotentes (no cambian lo que ya está; el valor original se respalda solo la primera vez), log en `%ProgramData%\Especifika\Autoclave\estacion\estacion.log`.

## Validación estática

`pwsh` no está instalado. Se usó `[System.Management.Automation.Language.Parser]::ParseFile` desde Windows PowerShell 5.1 (solo análisis sintáctico): **11 archivos, 0 errores**. No se probó el comportamiento: eso queda para el PC industrial con `-WhatIf` (ver checklist del LEEME).

## DECISIÓN SIN CONFIRMAR

1. **Tarea programada y no Shell Launcher** para lanzar `Autoclave.exe`: funciona en cualquier edición; la edición del PC no está confirmada (plan §10.1).
2. **AnyDesk sin script**: el plan define "sin acceso desatendido por defecto" (configuración de fábrica), así que no hay nada que automatizar; queda en la checklist.
3. **Bloqueos de la cuenta del operador (administrador de tareas, cmd, Explorador) no incluidos**: depende de cómo entra el técnico (plan §4, pendiente); aplicarlos podría dejarlo fuera.
4. **Windows Update**: horas activas 6–23 por defecto (parámetro), `AUOptions=2` (avisar, no instalar solo), diferir 30/365 días. En Home las directivas pueden ignorarse.
5. **Botón de encendido "no hacer nada"** (plan §7: el software hoy no hace cierre ordenado desde ese evento). También tapa y suspensión; inicio rápido desactivado (depende de la hibernación).
6. **Contraseña de autologon en texto plano en Winlogon** (`DefaultPassword`), riesgo aceptado en el plan §3.1; no se usó LSA secret (Sysinternals Autologon) para no depender de software externo.
7. Usuario por defecto `operador`; ruta por defecto `%ProgramFiles%\Especifika\Autoclave\Autoclave.exe`.
