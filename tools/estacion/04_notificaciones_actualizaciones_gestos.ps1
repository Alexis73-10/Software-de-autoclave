<#
.SYNOPSIS
  Paso 4: sin notificaciones, Windows Update sin reinicio automatico, sin gestos de borde.
.DESCRIPTION
  Planeacion seccion 5. Todo por registro (HKLM, aplica a todas las cuentas):
  - Notificaciones: sin toasts ni centro de notificaciones.
  - Windows Update: horas activas amplias (por defecto 6 a 23, maximo de 18 h que
    admite Windows), no reiniciar con usuarios conectados, descarga sin instalar
    automatica (AUOptions=2: avisa, no instala) y, en Pro o superior, diferir
    calidad 30 dias y caracteristicas 365 dias. En Home las directivas de
    WindowsUpdate pueden ignorarse: verificarlo en la checklist.
  - Gestos de borde de la pantalla tactil: deshabilitados (AllowEdgeSwipe=0).
  Idempotente; inverso: 04_revertir_notificaciones_actualizaciones_gestos.ps1.
#>
[CmdletBinding(SupportsShouldProcess)]
param(
    [ValidateRange(0,23)][int]$HoraActivaInicio = 6,
    [ValidateRange(0,23)][int]$HoraActivaFin = 23
)
. "$PSScriptRoot\_comun.ps1"
Assert-Administrador
$Paso = '04_notificaciones_actualizaciones_gestos'
Write-Log "== Inicio $Paso (horas activas $HoraActivaInicio-$HoraActivaFin, WhatIf=$WhatIfPreference) =="

# Notificaciones
Set-RegValor -Paso $Paso -Ruta 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\Explorer' -Nombre 'DisableNotificationCenter' -Valor 1
Set-RegValor -Paso $Paso -Ruta 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\CurrentVersion\PushNotifications' -Nombre 'NoToastApplicationNotification' -Valor 1
Set-RegValor -Paso $Paso -Ruta 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\CloudContent' -Nombre 'DisableWindowsConsumerFeatures' -Valor 1
Set-RegValor -Paso $Paso -Ruta 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\CloudContent' -Nombre 'DisableSoftLanding' -Valor 1

# Windows Update
$wu = 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate'
$au = "$wu\AU"
Set-RegValor -Paso $Paso -Ruta $au -Nombre 'NoAutoRebootWithLoggedOnUsers' -Valor 1
Set-RegValor -Paso $Paso -Ruta $au -Nombre 'AUOptions' -Valor 2
Set-RegValor -Paso $Paso -Ruta $wu -Nombre 'SetActiveHours' -Valor 1
Set-RegValor -Paso $Paso -Ruta $wu -Nombre 'ActiveHoursStart' -Valor $HoraActivaInicio
Set-RegValor -Paso $Paso -Ruta $wu -Nombre 'ActiveHoursEnd' -Valor $HoraActivaFin
Set-RegValor -Paso $Paso -Ruta $wu -Nombre 'DeferQualityUpdates' -Valor 1
Set-RegValor -Paso $Paso -Ruta $wu -Nombre 'DeferQualityUpdatesPeriodInDays' -Valor 30
Set-RegValor -Paso $Paso -Ruta $wu -Nombre 'DeferFeatureUpdates' -Valor 1
Set-RegValor -Paso $Paso -Ruta $wu -Nombre 'DeferFeatureUpdatesPeriodInDays' -Valor 365
Set-RegValor -Paso $Paso -Ruta 'HKLM:\SOFTWARE\Microsoft\WindowsUpdate\UX\Settings' -Nombre 'ActiveHoursStart' -Valor $HoraActivaInicio
Set-RegValor -Paso $Paso -Ruta 'HKLM:\SOFTWARE\Microsoft\WindowsUpdate\UX\Settings' -Nombre 'ActiveHoursEnd' -Valor $HoraActivaFin

# Gestos de borde
Set-RegValor -Paso $Paso -Ruta 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\EdgeUI' -Nombre 'AllowEdgeSwipe' -Valor 0

Write-Log 'Para que las directivas se apliquen ya: gpupdate /force o reiniciar.'
Write-Log "== Fin $Paso =="
