# tools/registro_pruebas/abrir_firewall.ps1
#
# Regla de entrada del Firewall de Windows para la app de registro de pruebas
# (F1, tanda 3): solo TCP al puerto de la app, solo en perfiles Privado y
# Dominio (nunca Público) y solo desde la subred local. NUNCA exponer a internet.
#
# Ejecutar en PowerShell COMO ADMINISTRADOR:
#   powershell -ExecutionPolicy Bypass -File .\abrir_firewall.ps1 -Puerto 8090
# Para quitarla:
#   Remove-NetFirewallRule -DisplayName "Especifika Registro de Pruebas"

param(
    [int]$Puerto = 8090,
    [string]$Nombre = "Especifika Registro de Pruebas"
)

$ErrorActionPreference = "Stop"
Get-NetFirewallRule -DisplayName $Nombre -ErrorAction SilentlyContinue | Remove-NetFirewallRule

New-NetFirewallRule -DisplayName $Nombre -Direction Inbound -Action Allow `
    -Protocol TCP -LocalPort $Puerto -Profile Private, Domain `
    -RemoteAddress LocalSubnet | Out-Null
Write-Host "Regla '$Nombre' creada: TCP $Puerto, perfiles Privado/Dominio, solo subred local."
Write-Host "Verifique que la red del PC está marcada como Privada (Configuración > Red)."
Write-Host "Si el teléfono no abre la página, el punto de acceso puede aislar a los clientes (AP isolation)."
