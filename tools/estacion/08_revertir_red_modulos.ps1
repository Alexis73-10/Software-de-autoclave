<#
.SYNOPSIS
  Inverso del paso 8 (T20-05): devuelve el adaptador de la red de los modulos
  a la configuracion IPv4 respaldada.
.DESCRIPTION
  Usa respaldo_08_red_modulos.json (en <RutaDatos>\estacion, solo
  Administradores y SYSTEM; lo escribe 08_red_modulos.ps1 antes de cambiar
  nada):
  - sin respaldo: no toca nada (el paso 08 nunca cambio el adaptador);
  - respaldo con forma invalida (Test-RespaldoRedModulos): error, no toca
    nada y conserva el respaldo;
  - el adaptador se busca por la MAC respaldada entre los Ethernet fisicos;
    si ya no esta: error y conserva el respaldo;
  - estaba en DHCP: quita las IPv4 y la puerta de enlace fijas, activa DHCP
    y deja el DNS automatico (Set-DnsClientServerAddress -ResetServerAddresses);
  - estaba fijo: DHCP desactivado, las IPv4 con su prefijo, las puertas de
    enlace (ruta 0.0.0.0/0) y los DNS guardados (sin DNS guardados, sin DNS).
  Si algo falla, termina con error y CONSERVA el respaldo (el puente devuelve
  1, el desinstalador lo avisa y conserva los pasos anotados). Si todo sale
  bien, borra el respaldo. -WhatIf simula (solo lee).
#>
[CmdletBinding(SupportsShouldProcess)]
param()
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\_comun.ps1"
. "$PSScriptRoot\_red_modulos_puras.ps1"
Assert-Administrador
$Paso = '08_red_modulos'
Write-Log "== Inicio revertir $Paso (WhatIf=$WhatIfPreference) =="

$resp = Read-Respaldo $Paso
if (-not $resp.ContainsKey('Mac')) {
    Write-Log "Sin respaldo de '$Paso': nada que restaurar (no se toca la red)."
    Write-Log "== Fin revertir $Paso =="
    return
}
$motivo = Test-RespaldoRedModulos $resp
if ($motivo -ne '') { throw "El respaldo del paso 08 no tiene la forma esperada ($motivo): no se restaura nada y se conserva." }

$mac = ConvertTo-MacNormalizada ([string]$resp['Mac'])
$adaptador = Find-AdaptadorPorMac @(Get-NetAdapter -Physical -ErrorAction Stop) $mac
if ($null -eq $adaptador) {
    throw "No se encuentra el adaptador Ethernet con la MAC ${mac}: no se restaura nada y se conserva el respaldo."
}
$indice = [int]$adaptador.ifIndex
$dhcp = [bool]$resp['Dhcp']
$ipv4 = @($resp['IPv4'] | Where-Object { $null -ne $_ })
$puertas = @($resp['PuertasEnlace'] | Where-Object { $_ } | ForEach-Object { [string]$_ })
$dns = @($resp['Dns'] | Where-Object { $_ } | ForEach-Object { [string]$_ })
Write-Log ("Restaurar '{0}' (MAC {1}): DHCP={2}; IPv4={3}; puertas de enlace={4}; DNS={5}." -f $adaptador.Name, $mac, $dhcp,
    (($ipv4 | ForEach-Object { "$($_.Ip)/$($_.Prefijo)" }) -join ', '), ($puertas -join ', '), ($dns -join ', '))

if ($PSCmdlet.ShouldProcess("$($adaptador.Name) ($mac)", 'Restaurar la configuracion IPv4 respaldada')) {
    try {
        # quita lo que dejo el paso 08 (IP fija y cualquier ruta por defecto)
        foreach ($almacen in @('ActiveStore', 'PersistentStore')) {
            Get-NetRoute -InterfaceIndex $indice -AddressFamily IPv4 -DestinationPrefix '0.0.0.0/0' -PolicyStore $almacen -ErrorAction SilentlyContinue |
                Remove-NetRoute -Confirm:$false -ErrorAction Stop
            Get-NetIPAddress -InterfaceIndex $indice -AddressFamily IPv4 -PolicyStore $almacen -ErrorAction SilentlyContinue |
                Remove-NetIPAddress -Confirm:$false -ErrorAction Stop
        }
        if ($dhcp) {
            Set-NetIPInterface -InterfaceIndex $indice -AddressFamily IPv4 -Dhcp Enabled -ErrorAction Stop
            Set-DnsClientServerAddress -InterfaceIndex $indice -ResetServerAddresses -ErrorAction Stop
            Write-Log "Restaurado: DHCP activado y DNS automatico en '$($adaptador.Name)'."
        } else {
            Set-NetIPInterface -InterfaceIndex $indice -AddressFamily IPv4 -Dhcp Disabled -ErrorAction Stop
            foreach ($d in $ipv4) {
                New-NetIPAddress -InterfaceIndex $indice -AddressFamily IPv4 -IPAddress ([string]$d.Ip) `
                    -PrefixLength ([int]$d.Prefijo) -ErrorAction Stop | Out-Null
            }
            foreach ($g in $puertas) {
                New-NetRoute -InterfaceIndex $indice -AddressFamily IPv4 -DestinationPrefix '0.0.0.0/0' -NextHop $g -ErrorAction Stop | Out-Null
            }
            if ($dns.Count -gt 0) {
                Set-DnsClientServerAddress -InterfaceIndex $indice -ServerAddresses $dns -ErrorAction Stop
            } else {
                Set-DnsClientServerAddress -InterfaceIndex $indice -ResetServerAddresses -ErrorAction Stop
            }
            Write-Log "Restaurado: configuracion IPv4 fija anterior en '$($adaptador.Name)'."
        }
    } catch {
        # el respaldo se conserva para volver a intentarlo; el puente devuelve 1 y el desinstalador avisa
        throw "No se pudo restaurar la red del paso 08 ($($_.Exception.Message)): se conserva el respaldo $(Get-RutaRespaldo $Paso)."
    }
    Remove-Item -LiteralPath (Get-RutaRespaldo $Paso) -Force -ErrorAction SilentlyContinue
}
Write-Log "== Fin revertir $Paso =="
