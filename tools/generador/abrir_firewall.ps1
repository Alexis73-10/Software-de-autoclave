# tools/generador/abrir_firewall.ps1
#
# Regla de entrada del Firewall de Windows para el generador (G1, tanda 2):
# solo TCP al puerto del generador, solo en perfiles Privado y Dominio (nunca
# Público) y solo desde la subred local.
#
# Ejecutar en PowerShell COMO ADMINISTRADOR:
#   powershell -ExecutionPolicy Bypass -File .\abrir_firewall.ps1 -Puerto 8080
# Para quitarla:
#   Remove-NetFirewallRule -DisplayName "Especifika Generador de Codigos"

param(
    [int]$Puerto = 8080,
    [string]$Nombre = "Especifika Generador de Codigos"
)

$ErrorActionPreference = "Stop"
Get-NetFirewallRule -DisplayName $Nombre -ErrorAction SilentlyContinue | Remove-NetFirewallRule

New-NetFirewallRule -DisplayName $Nombre -Direction Inbound -Action Allow `
    -Protocol TCP -LocalPort $Puerto -Profile Private, Domain `
    -RemoteAddress LocalSubnet | Out-Null
Write-Host "Regla '$Nombre' creada: TCP $Puerto, perfiles Privado/Dominio, solo subred local."
Write-Host "Verifique que la red del PC está marcada como Privada (Configuración > Red)."
