<#
.SYNOPSIS
  Inverso del paso 8 (T20-05): devuelve el adaptador de la red del modulo E/S
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
    enlace (ruta 0.0.0.0/0, con su metrica si se respaldo) y los DNS
    guardados (sin DNS guardados, sin DNS);
  - V20-s3-09: la metrica de la interfaz (automatica, o la fija guardada),
    si el respaldo la trae (los respaldos anteriores no la traen).
  Si algo falla, termina con error y CONSERVA el respaldo (el puente devuelve
  1, el desinstalador lo avisa y conserva los pasos anotados). V20-s3-02: si
  falla despues de empezar a quitar las IPv4, como ultimo recurso deja el
  adaptador en DHCP con DNS automatico (para no dejarlo sin configuracion) y
  relanza el error. Si todo sale bien, borra el respaldo. -WhatIf simula
  (solo lee). Tambien lo llama 08_red_modulos.ps1 si su aplicacion falla a
  mitad.
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
# listas siempre como arreglos (@(...) en Get-PlanRestauracion): un respaldo
# con una sola IPv4 llega de ConvertFrom-Json como un escalar
$plan = Get-PlanRestauracion $resp
$dhcp = [bool]$plan.Dhcp
$ipv4 = @($plan.IPv4)
$puertas = @($plan.Puertas)
$dns = @($plan.Dns)
Write-Log ("Restaurar '{0}' (MAC {1}): DHCP={2}; IPv4={3}; puertas de enlace={4}; DNS={5}; metrica automatica={6}; metrica de la interfaz={7}." -f
    $adaptador.Name, $mac, $dhcp,
    (($ipv4 | ForEach-Object { "$($_.Ip)/$($_.Prefijo)" }) -join ', '),
    (($puertas | ForEach-Object { "$($_.Puerta) (metrica $($_.Metrica))" }) -join ', '), ($dns -join ', '),
    $plan.MetricaAutomatica, $plan.MetricaInterfaz)

if ($PSCmdlet.ShouldProcess("$($adaptador.Name) ($mac)", 'Restaurar la configuracion IPv4 respaldada')) {
    $quitando = $false
    try {
        # quita lo que dejo el paso 08 (IP fija y cualquier ruta por defecto);
        # desde aqui, un fallo deja el adaptador a medias (V20-s3-02)
        $quitando = $true
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
            foreach ($p in $puertas) {
                $g = [string]$p.Puerta
                $ruta = @{ InterfaceIndex = $indice; AddressFamily = 'IPv4'; DestinationPrefix = '0.0.0.0/0' }
                if ($null -ne $p.Metrica) { $ruta['RouteMetric'] = [int]$p.Metrica }
                New-NetRoute @ruta -NextHop $g -ErrorAction Stop | Out-Null
            }
            if ($dns.Count -gt 0) {
                Set-DnsClientServerAddress -InterfaceIndex $indice -ServerAddresses $dns -ErrorAction Stop
            } else {
                Set-DnsClientServerAddress -InterfaceIndex $indice -ResetServerAddresses -ErrorAction Stop
            }
            Write-Log "Restaurado: configuracion IPv4 fija anterior en '$($adaptador.Name)'."
        }
        # la configuracion IPv4 ya quedo restaurada: un fallo con la metrica
        # no debe disparar el ultimo recurso (DHCP borraria la IP fija)
        $quitando = $false
        # V20-s3-09: metrica de la interfaz (solo si el respaldo la trae)
        if ($plan.MetricaAutomatica -eq $true) {
            Set-NetIPInterface -InterfaceIndex $indice -AddressFamily IPv4 -AutomaticMetric Enabled -ErrorAction Stop
            Write-Log "Restaurado: metrica automatica en '$($adaptador.Name)'."
        } elseif (($plan.MetricaAutomatica -eq $false) -and ($null -ne $plan.MetricaInterfaz)) {
            Set-NetIPInterface -InterfaceIndex $indice -AddressFamily IPv4 -InterfaceMetric ([int]$plan.MetricaInterfaz) -ErrorAction Stop
            Write-Log "Restaurado: metrica de la interfaz $($plan.MetricaInterfaz) en '$($adaptador.Name)'."
        }
    } catch {
        $errorRestaurar = $_.Exception.Message
        $recurso = ''
        if ($quitando) {
            # V20-s3-02: ultimo recurso, para no dejar el adaptador sin
            # configuracion: DHCP y DNS automatico
            try {
                Set-NetIPInterface -InterfaceIndex $indice -AddressFamily IPv4 -Dhcp Enabled -ErrorAction Stop
                Set-DnsClientServerAddress -InterfaceIndex $indice -ResetServerAddresses -ErrorAction Stop
                $recurso = ' Como ultimo recurso se dejo el adaptador en DHCP con DNS automatico.'
                Write-Log "Ultimo recurso: DHCP y DNS automatico en '$($adaptador.Name)'." 'ERROR'
            } catch {
                $recurso = " Tampoco se pudo dejar en DHCP ($($_.Exception.Message))."
                Write-Log "Ultimo recurso fallido en '$($adaptador.Name)': $($_.Exception.Message)" 'ERROR'
            }
        }
        # el respaldo se conserva para volver a intentarlo; el puente devuelve 1 y el desinstalador avisa
        throw "No se pudo restaurar la red del paso 08 ($errorRestaurar): se conserva el respaldo $(Get-RutaRespaldo $Paso).$recurso"
    }
    Remove-Item -LiteralPath (Get-RutaRespaldo $Paso) -Force -ErrorAction SilentlyContinue
}
Write-Log "== Fin revertir $Paso =="
