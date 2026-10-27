<#
.SYNOPSIS
  Paso 8: red de los modulos de E/S (T20-05, tanda 20). Deja el adaptador
  Ethernet dedicado (elegido por su MAC) en 192.168.3.10/24, sin puerta de
  enlace ni DNS y con DHCP desactivado, para hablar con el modulo M31-U
  (192.168.3.7, decisiones 2 y 3 de docs/mis_plans/decisiones_tanda_20.md).
.DESCRIPTION
  - Adaptador: -Adaptador es la MAC ('00-54-04-84-9D-B1', con ':' o sin
    separadores; no es secreta). Se busca SOLO entre los Ethernet fisicos
    (Get-NetAdapter -Physical con NdisPhysicalMedium = 14, 802.3): un Wi-Fi
    (9), Bluetooth (10) o un adaptador virtual se rechazan.
  - Si OTRO adaptador ya tiene una IPv4 en 192.168.3.0/24 (en la
    configuracion activa o en la persistente, V20-s3-04), el paso termina
    con error y no cambia nada (dos rutas a la misma red).
  - Respaldo (solo la primera vez; volver a correr el paso no pisa el
    original): respaldo_08_red_modulos.json en <RutaDatos>\estacion (solo
    Administradores y SYSTEM; nombre por la convencion respaldo_<paso>.json
    de _comun.ps1), con MAC, alias, DHCP si/no, IPv4 manuales con prefijo,
    puertas de enlace, DNS y metricas (de la interfaz y de cada ruta por
    defecto, V20-s3-09). Se escribe ANTES de cambiar nada. Si el respaldo
    es de otro adaptador, no cambia nada y pide revertir primero.
  - Aplica: DHCP desactivado (Set-NetIPInterface -Dhcp Disabled), quita las
    rutas por defecto (0.0.0.0/0) y las demas IPv4 del adaptador, agrega
    192.168.3.10/24 sin -DefaultGateway (New-NetIPAddress; si no esta en la
    configuracion persistente, antes la quita de los dos almacenes) y deja
    el DNS sin servidores (Set-DnsClientServerAddress -ResetServerAddresses).
  - Si algo falla a mitad de la aplicacion (V20-s3-02), restaura desde el
    respaldo con 08_revertir_red_modulos.ps1 (que, si tampoco puede, deja el
    adaptador en DHCP con DNS automatico) y relanza el error.
  - Verifica despues (hasta 15 s) que 192.168.3.10/24 quedo en ESE adaptador
    (y no una 169.254.x.x: en el banco la ventana de Windows a veces no
    aplicaba la IP fija), con DHCP desactivado y sin puerta de enlace; si no,
    termina con error. Con el cable desconectado se acepta la direccion de la
    configuracion persistente (PersistentStore).
  - Idempotente: si el adaptador ya esta exactamente asi, anota "Sin cambio".
  - Cualquier fallo lanza error (el puente estacion_setup.ps1 devuelve 1 y el
    Setup lo muestra en la lista de fallas). -WhatIf simula (solo lee).
  Inverso: 08_revertir_red_modulos.ps1.
.EXAMPLE
  .\08_red_modulos.ps1 -Adaptador 00-54-04-84-9D-B1 -WhatIf
#>
[CmdletBinding(SupportsShouldProcess)]
param(
    [Parameter(Mandatory)][string]$Adaptador
)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\_comun.ps1"
. "$PSScriptRoot\_red_modulos_puras.ps1"
Assert-Administrador
$Paso = '08_red_modulos'
Write-Log "== Inicio $Paso (WhatIf=$WhatIfPreference) =="

$mac = ConvertTo-MacNormalizada $Adaptador
if ($null -eq $mac) { throw "MAC invalida '$Adaptador': no se cambia nada." }

$elegido = Find-AdaptadorPorMac @(Get-NetAdapter -Physical -ErrorAction Stop) $mac
if ($null -eq $elegido) {
    throw "No hay un adaptador Ethernet fisico con la MAC $mac (los Wi-Fi y los virtuales no se aceptan): no se cambia nada."
}
$indice = [int]$elegido.ifIndex
Write-Log "Adaptador: '$($elegido.Name)' ($($elegido.InterfaceDescription)), MAC $mac, indice $indice, estado $($elegido.Status)."

function Get-EstadoInterfaz([int]$Indice) {
    <# Configuracion IPv4 actual de la interfaz (solo lectura). #>
    $ipif = Get-NetIPInterface -InterfaceIndex $Indice -AddressFamily IPv4 -ErrorAction Stop
    $rutas = @(Get-NetRoute -InterfaceIndex $Indice -AddressFamily IPv4 -DestinationPrefix '0.0.0.0/0' -ErrorAction SilentlyContinue)
    return @{
        Dhcp        = ([string]$ipif.Dhcp -eq 'Enabled')
        # V20-s3-09: metricas que se respaldan y el inverso restaura
        MetricaAutomatica = ([string]$ipif.AutomaticMetric -eq 'Enabled')
        MetricaInterfaz   = [int]$ipif.InterfaceMetric
        Rutas       = @($rutas | ForEach-Object { @{ Puerta = [string]$_.NextHop; Metrica = [int]$_.RouteMetric } })
        Direcciones = @(Get-NetIPAddress -InterfaceIndex $Indice -AddressFamily IPv4 -ErrorAction SilentlyContinue)
        Persistentes = @(Get-NetIPAddress -InterfaceIndex $Indice -AddressFamily IPv4 -PolicyStore PersistentStore -ErrorAction SilentlyContinue)
        Puertas     = @($rutas | ForEach-Object { [string]$_.NextHop })
        Dns         = @((Get-DnsClientServerAddress -InterfaceIndex $Indice -AddressFamily IPv4 -ErrorAction Stop).ServerAddresses)
    }
}

# 1. Conflicto: otra interfaz ya en 192.168.3.0/24 -> error sin cambiar nada.
#    V20-s3-04: tambien la configuracion persistente (una IP fija de un
#    adaptador con el cable desconectado solo esta en PersistentStore).
$todas = @(Get-NetIPAddress -AddressFamily IPv4 -ErrorAction Stop) +
    @(Get-NetIPAddress -AddressFamily IPv4 -PolicyStore PersistentStore -ErrorAction SilentlyContinue)
$conflictos = @(Get-ConflictoSubred $todas $indice)
if ($conflictos.Count -gt 0) {
    throw "Otro adaptador ya esta en la red de los modulos (192.168.3.0/24): $($conflictos -join ', '). Quitele esa direccion o elija ese adaptador. No se cambia nada."
}

$antes = Get-EstadoInterfaz $indice
Write-Log ("Antes: DHCP={0}; IPv4={1}; puertas de enlace={2}; DNS={3}." -f $antes.Dhcp,
    (($antes.Direcciones | ForEach-Object { "$($_.IPAddress)/$($_.PrefixLength)" }) -join ', '),
    ($antes.Puertas -join ', '), ($antes.Dns -join ', '))

# 2. Respaldo ANTES de aplicar (solo la primera vez)
$resp = Read-Respaldo $Paso
if ($resp.ContainsKey('Mac') -and ((ConvertTo-MacNormalizada ([string]$resp['Mac'])) -ne $mac)) {
    throw "El respaldo del paso 08 es de otro adaptador ($($resp['Mac'])): revierta primero con 08_revertir_red_modulos.ps1. No se cambia nada."
}
if (-not $resp.ContainsKey('Mac')) {
    $nuevo = New-RespaldoRedModulos -Adaptador $elegido -DhcpHabilitado $antes.Dhcp `
        -Direcciones $antes.Direcciones -PuertasEnlace $antes.Puertas -Dns $antes.Dns `
        -MetricaAutomatica $antes.MetricaAutomatica -MetricaInterfaz $antes.MetricaInterfaz -Rutas $antes.Rutas
    if (-not $WhatIfPreference) {
        Save-Respaldo $Paso $nuevo
        Write-Log "Respaldo guardado en $(Get-RutaRespaldo $Paso)."
    }
}

# 3. Aplicar (idempotente)
if (Test-ConfiguracionModulos -Direcciones $antes.Direcciones -IndiceElegido $indice `
        -DhcpHabilitado $antes.Dhcp -PuertasEnlace $antes.Puertas -Dns $antes.Dns) {
    Write-Log "Sin cambio: el adaptador ya esta en $($script:IpEstacionModulos)/$($script:PrefijoModulos) sin puerta de enlace ni DNS."
} elseif ($PSCmdlet.ShouldProcess("$($elegido.Name) ($mac)", "IPv4 estatica $($script:IpEstacionModulos)/$($script:PrefijoModulos) sin puerta de enlace ni DNS, DHCP desactivado")) {
    if ((-not $resp.ContainsKey('Mac')) -and (-not (Test-Path -LiteralPath (Get-RutaRespaldo $Paso)))) {
        throw 'No se pudo guardar el respaldo del paso 08: no se cambia nada.'
    }
    # V20-s3-02: el respaldo ya esta escrito; si algo falla a mitad, se
    # restaura desde el respaldo (08_revertir_red_modulos.ps1, que si no puede
    # deja DHCP con DNS automatico) y se relanza el error.
    try {
        Set-NetIPInterface -InterfaceIndex $indice -AddressFamily IPv4 -Dhcp Disabled -ErrorAction Stop
        foreach ($almacen in @('ActiveStore', 'PersistentStore')) {
            Get-NetRoute -InterfaceIndex $indice -AddressFamily IPv4 -DestinationPrefix '0.0.0.0/0' -PolicyStore $almacen -ErrorAction SilentlyContinue |
                Remove-NetRoute -Confirm:$false -ErrorAction Stop
            Get-NetIPAddress -InterfaceIndex $indice -AddressFamily IPv4 -PolicyStore $almacen -ErrorAction SilentlyContinue |
                Where-Object { ($_.IPAddress -ne $script:IpEstacionModulos) -or ([int]$_.PrefixLength -ne $script:PrefijoModulos) } |
                Remove-NetIPAddress -Confirm:$false -ErrorAction Stop
        }
        $tiene = @(Get-NetIPAddress -InterfaceIndex $indice -AddressFamily IPv4 -PolicyStore PersistentStore -ErrorAction SilentlyContinue |
            Where-Object { $_.IPAddress -eq $script:IpEstacionModulos })
        if ($tiene.Count -eq 0) {
            # V20-s3-04/06: si la .10 quedo solo en la configuracion activa,
            # New-NetIPAddress fallaria ("ya existe"): se quita de los dos
            # almacenes antes de crearla
            foreach ($almacen in @('ActiveStore', 'PersistentStore')) {
                Get-NetIPAddress -InterfaceIndex $indice -AddressFamily IPv4 -PolicyStore $almacen -ErrorAction SilentlyContinue |
                    Where-Object { $_.IPAddress -eq $script:IpEstacionModulos } |
                    Remove-NetIPAddress -Confirm:$false -ErrorAction Stop
            }
            New-NetIPAddress -InterfaceIndex $indice -AddressFamily IPv4 -IPAddress $script:IpEstacionModulos `
                -PrefixLength $script:PrefijoModulos -ErrorAction Stop | Out-Null
        }
        Set-DnsClientServerAddress -InterfaceIndex $indice -ResetServerAddresses -ErrorAction Stop
    } catch {
        $errorAplicar = $_.Exception.Message
        Write-Log "Fallo a mitad de la aplicacion ($errorAplicar): se restaura desde el respaldo." 'ERROR'
        $restaurado = $false
        try {
            & "$PSScriptRoot\08_revertir_red_modulos.ps1" -WhatIf:$false
            $restaurado = $true
        } catch {
            Write-Log "La restauracion tambien fallo: $($_.Exception.Message)" 'ERROR'
        }
        if ($restaurado) {
            throw "No se pudo aplicar la red de los modulos en '$($elegido.Name)' ($errorAplicar): se restauro la configuracion anterior del adaptador."
        }
        throw ("No se pudo aplicar la red de los modulos en '$($elegido.Name)' ($errorAplicar) ni restaurar la configuracion anterior: " +
            "revierta como administrador con 08_revertir_red_modulos.ps1 o ejecute el Setup otra vez (Reparar).")
    }
    Write-Log "Aplicado: $($script:IpEstacionModulos)/$($script:PrefijoModulos) en '$($elegido.Name)', sin puerta de enlace ni DNS, DHCP desactivado."
}

# 4. Verificacion (tambien en Sin cambio): la IP quedo en ESE adaptador
if (-not $WhatIfPreference) {
    $ok = $false
    $limite = (Get-Date).AddSeconds(15)
    do {
        $despues = Get-EstadoInterfaz $indice
        $conectado = ([string](Get-NetAdapter -InterfaceIndex $indice -ErrorAction Stop).Status -eq 'Up')
        $direccionOk = (Test-DireccionAplicada $despues.Direcciones $indice) -or
            ((-not $conectado) -and (Test-DireccionAplicada $despues.Persistentes $indice))
        $ok = $direccionOk -and (-not $despues.Dhcp) -and ($despues.Puertas.Count -eq 0)
        if (-not $ok) { Start-Sleep -Milliseconds 500 }
    } while ((-not $ok) -and ((Get-Date) -lt $limite))
    if (-not $ok) {
        throw ("La IP fija no quedo aplicada en '{0}': DHCP={1}; IPv4={2}; puertas de enlace={3}. El respaldo se conserva; revise el adaptador o revierta con 08_revertir_red_modulos.ps1." -f
            $elegido.Name, $despues.Dhcp,
            (($despues.Direcciones | ForEach-Object { "$($_.IPAddress)/$($_.PrefixLength) $($_.AddressState)" }) -join ', '),
            ($despues.Puertas -join ', '))
    }
    Write-Log "Verificado: $($script:IpEstacionModulos)/$($script:PrefijoModulos) en '$($elegido.Name)' (cable conectado=$conectado)."
}
Write-Log "== Fin $Paso =="
