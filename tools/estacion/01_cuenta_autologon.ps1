<#
.SYNOPSIS
  Paso 1: cuenta local ESTANDAR del operador con inicio de sesion automatico.
.DESCRIPTION
  Planeacion estacion Windows, seccion 3.1 y 4. Crea (si no existe) una cuenta
  local sin privilegios y configura Winlogon AutoAdminLogon para ella.
  La contrasena queda en el registro (riesgo aceptado en el plan, seccion 3.1).
  Idempotente: si la cuenta ya existe no la recrea; los valores de registro solo
  se cambian si difieren. Inverso: 01_revertir_cuenta_autologon.ps1.
.EXAMPLE
  .\01_cuenta_autologon.ps1 -WhatIf
  .\01_cuenta_autologon.ps1 -Usuario operador
#>
[CmdletBinding(SupportsShouldProcess)]
param(
    [string]$Usuario = 'operador',
    [securestring]$Contrasena
)
. "$PSScriptRoot\_comun.ps1"
Assert-Administrador
$Paso = '01_cuenta_autologon'
Write-Log "== Inicio $Paso (usuario=$Usuario, WhatIf=$WhatIfPreference) =="

if (-not $Contrasena) { $Contrasena = Read-Host -AsSecureString "Contrasena para la cuenta '$Usuario'" }
$plano = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
    [Runtime.InteropServices.Marshal]::SecureStringToBSTR($Contrasena))

$cuenta = Get-LocalUser -Name $Usuario -ErrorAction SilentlyContinue
if ($cuenta) {
    Write-Log "La cuenta '$Usuario' ya existe: no se recrea."
    $admins = Get-LocalGroupMember -SID 'S-1-5-32-544' -ErrorAction SilentlyContinue |
              Where-Object { $_.Name -like "*\$Usuario" }
    if ($admins) { Write-Log "ATENCION: '$Usuario' pertenece a Administradores; el plan exige cuenta estandar." 'WARN' }
} elseif ($PSCmdlet.ShouldProcess($Usuario, 'Crear cuenta local estandar')) {
    New-LocalUser -Name $Usuario -Password $Contrasena -FullName 'Operador autoclave' `
        -Description 'Cuenta de quiosco del autoclave (sin privilegios)' `
        -PasswordNeverExpires -UserMayNotChangePassword | Out-Null
    Add-LocalGroupMember -SID 'S-1-5-32-545' -Member $Usuario   # Usuarios
    $resp = Read-Respaldo $Paso; $resp['CuentaCreada'] = $Usuario; Save-Respaldo $Paso $resp
    Write-Log "Cuenta '$Usuario' creada en el grupo Usuarios."
}

$wl = 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon'
Set-RegValor -Paso $Paso -Ruta $wl -Nombre 'AutoAdminLogon'    -Valor '1'          -Tipo String
Set-RegValor -Paso $Paso -Ruta $wl -Nombre 'DefaultUserName'   -Valor $Usuario     -Tipo String
Set-RegValor -Paso $Paso -Ruta $wl -Nombre 'DefaultDomainName' -Valor $env:COMPUTERNAME -Tipo String
Set-RegValor -Paso $Paso -Ruta $wl -Nombre 'DefaultPassword'   -Valor $plano       -Tipo String
# Windows 10/11: sin esto netplwiz/AutoAdminLogon pueden ignorarse con Windows Hello.
Set-RegValor -Paso $Paso -Ruta 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\PasswordLess\Device' `
    -Nombre 'DevicePasswordLessBuildVersion' -Valor 0

$plano = $null
Write-Log "== Fin $Paso =="
