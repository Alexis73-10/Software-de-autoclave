# tools/generador/quitar_inicio_automatico.ps1
#
# Quita la tarea programada del generador (G1, tanda 2). No borra datos.
# Ejecutar en PowerShell COMO ADMINISTRADOR:
#   powershell -ExecutionPolicy Bypass -File .\quitar_inicio_automatico.ps1

param([string]$Nombre = "Especifika Generador de Codigos")

$ErrorActionPreference = "Stop"
$tarea = Get-ScheduledTask -TaskName $Nombre -ErrorAction SilentlyContinue
if ($null -eq $tarea) {
    Write-Host "No existe la tarea '$Nombre'."
    exit 0
}
Stop-ScheduledTask -TaskName $Nombre -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName $Nombre -Confirm:$false
Write-Host "Tarea '$Nombre' eliminada. Los datos en C:\ProgramData\Especifika\Generador\ se conservan."
