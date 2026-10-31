<#
.SYNOPSIS
  Paso 1: cuenta local ESTANDAR del operador con inicio de sesion automatico.
.DESCRIPTION
  Planeacion estacion Windows, seccion 3.1 y 4. Crea (si no existe) una cuenta
  local sin privilegios y configura Winlogon AutoAdminLogon para ella.
  La contrasena queda en el registro (riesgo aceptado en el plan, seccion 3.1).
  Idempotente: si la cuenta ya existe no la recrea; los valores de registro solo
  se cambian si difieren. Inverso: 01_revertir_cuenta_autologon.ps1.

  Sin interaccion (Setup, E9 tanda 9 / D9-11): el inicio automatico es con la
  cuenta que instala (decision de Cristian, 23-oct), que ya existe:
    -Usuario <cuenta> -Dominio <equipo o dominio> -NoCrearCuenta -ContrasenaDesdeEntorno
  La contrasena se toma de la variable de entorno AUTOCLAVE_CLAVE_AUTOLOGON del
  proceso (nunca de la linea de comandos, que otros procesos pueden leer) y se
  borra de ella al leerla. Con -NoCrearCuenta, si la cuenta local no existe el
  script falla sin cambiar nada.
.EXAMPLE
  .\01_cuenta_autologon.ps1 -WhatIf
  .\01_cuenta_autologon.ps1 -Usuario operador
#>
[CmdletBinding(SupportsShouldProcess)]
param(
    [string]$Usuario = 'operador',
    [securestring]$Contrasena,
    # Dominio de la cuenta (DefaultDomainName): el nombre del equipo para una cuenta local
    [string]$Dominio = $env:COMPUTERNAME,
    [switch]$ContrasenaDesdeEntorno,
    [switch]$NoCrearCuenta
)
. "$PSScriptRoot\_comun.ps1"
Assert-Administrador
$Paso = '01_cuenta_autologon'
Write-Log "== Inicio $Paso (usuario=$Dominio\$Usuario, WhatIf=$WhatIfPreference) =="

if ($ContrasenaDesdeEntorno) {
    $deEntorno = $env:AUTOCLAVE_CLAVE_AUTOLOGON
    Remove-Item Env:AUTOCLAVE_CLAVE_AUTOLOGON -ErrorAction SilentlyContinue
    if (-not $deEntorno) { throw 'Falta la contrasena (variable AUTOCLAVE_CLAVE_AUTOLOGON vacia): no se cambia nada.' }
    $Contrasena = ConvertTo-SecureString -String $deEntorno -AsPlainText -Force
    $deEntorno = $null
}
if (-not $Contrasena) { $Contrasena = Read-Host -AsSecureString "Contrasena para la cuenta '$Usuario'" }
$plano = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
    [Runtime.InteropServices.Marshal]::SecureStringToBSTR($Contrasena))

$esLocal = ($Dominio -eq $env:COMPUTERNAME)
$cuenta = if ($esLocal) { Get-LocalUser -Name $Usuario -ErrorAction SilentlyContinue } else { $null }
if (-not $esLocal) {
    Write-Log "Cuenta de dominio '$Dominio\$Usuario': no se comprueba ni se crea aqui."
} elseif ($cuenta) {
    Write-Log "La cuenta '$Usuario' ya existe: no se recrea."
    $admins = Get-LocalGroupMember -SID 'S-1-5-32-544' -ErrorAction SilentlyContinue |
              Where-Object { $_.Name -like "*\$Usuario" }
    if ($admins) { Write-Log "ATENCION: '$Usuario' pertenece a Administradores; el plan exige cuenta estandar." 'WARN' }
} elseif ($NoCrearCuenta) {
    throw "La cuenta local '$Usuario' no existe y se pidio no crearla: no se cambia nada."
} elseif ($PSCmdlet.ShouldProcess($Usuario, 'Crear cuenta local estandar')) {
    New-LocalUser -Name $Usuario -Password $Contrasena -FullName 'Operador autoclave' `
        -Description 'Cuenta de quiosco del autoclave (sin privilegios)' `
        -PasswordNeverExpires -UserMayNotChangePassword | Out-Null
    Add-LocalGroupMember -SID 'S-1-5-32-545' -Member $Usuario   # Usuarios
    $resp = Read-Respaldo $Paso; $resp['CuentaCreada'] = $Usuario; Save-Respaldo $Paso $resp
    Write-Log "Cuenta '$Usuario' creada en el grupo Usuarios."
}

$wl = 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon'
# AutoAdminLogon al final: si algo falla antes, no queda activado con datos a medias
Set-RegValor -Paso $Paso -Ruta $wl -Nombre 'DefaultUserName'   -Valor $Usuario     -Tipo String
Set-RegValor -Paso $Paso -Ruta $wl -Nombre 'DefaultDomainName' -Valor $Dominio     -Tipo String
Set-RegValor -Paso $Paso -Ruta $wl -Nombre 'DefaultPassword'   -Valor $plano       -Tipo String
Set-RegValor -Paso $Paso -Ruta $wl -Nombre 'AutoAdminLogon'    -Valor '1'          -Tipo String
# Windows 10/11: sin esto netplwiz/AutoAdminLogon pueden ignorarse con Windows Hello.
Set-RegValor -Paso $Paso -Ruta 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\PasswordLess\Device' `
    -Nombre 'DevicePasswordLessBuildVersion' -Valor 0

$plano = $null
Write-Log "== Fin $Paso =="
