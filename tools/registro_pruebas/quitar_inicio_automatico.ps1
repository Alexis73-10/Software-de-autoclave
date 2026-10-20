# tools/registro_pruebas/quitar_inicio_automatico.ps1
# Quita la tarea de inicio automático (PowerShell COMO ADMINISTRADOR).
param([string]$Nombre = "Especifika Registro de Pruebas")
Unregister-ScheduledTask -TaskName $Nombre -Confirm:$false
Write-Host "Tarea '$Nombre' eliminada."
