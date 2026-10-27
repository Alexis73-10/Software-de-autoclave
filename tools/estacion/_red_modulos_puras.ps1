# _red_modulos_puras.ps1 - Funciones PURAS del paso 08 (red de los modulos
# de E/S, T20-05, tanda 20). Se carga con dot-sourcing desde
# 08_red_modulos.ps1 y 08_revertir_red_modulos.ps1:
#     . "$PSScriptRoot\_red_modulos_puras.ps1"
#
# Reglas de este archivo (las fija tests/test_t20_s3_red_modulos.py):
#   - sin efectos: no llama cmdlets de red (Get-NetAdapter, Set-NetIPInterface,
#     New-NetIPAddress...), no escribe en el registro ni en archivos y no
#     escribe el log; solo recibe objetos (los de Get-NetAdapter,
#     Get-NetIPAddress... u objetos [pscustomobject] con las mismas
#     propiedades) y devuelve valores;
#   - las pruebas lo cargan SOLO a el con datos ficticios (nunca los 08_*.ps1).
#
# Red fija de los modulos (decisiones 2 y 3 de la tanda 20): el modulo M31-U
# es 192.168.3.7; el PC queda en 192.168.3.10/24, sin puerta de enlace ni DNS.

Set-StrictMode -Version 2.0

$script:IpEstacionModulos = '192.168.3.10'
$script:RedModulos = '192.168.3.0'
$script:PrefijoModulos = 24
# NDIS_PHYSICAL_MEDIUM: 14 = NdisPhysicalMedium802_3 (Ethernet por cable);
# 9 = Native802_11 (Wi-Fi), 10 = Bluetooth, 0 = sin medio (virtuales, VPN)
$script:MedioEthernet = 14
# Estados de una direccion que no cuentan como aplicada
$script:EstadosDireccionInvalidos = @('Duplicate', 'Invalid', 'Deprecated')
# Limites de las metricas que se respaldan (V20-s3-09): la de la interfaz
# (InterfaceMetric) y la de cada ruta por defecto (RouteMetric, uint16)
$script:MetricaInterfazMaxima = 999999
$script:MetricaRutaMaxima = 65535

function Test-Propiedad($Objeto, [string]$Nombre) {
    <# True si el objeto tiene la propiedad (sin fallar con StrictMode). #>
    if ($null -eq $Objeto) { return $false }
    return ($Objeto.PSObject.Properties.Name -contains $Nombre)
}

function ConvertTo-MacNormalizada($Mac) {
    <# '00-54-04-84-9D-B1', '00:54:04:84:9d:b1' o '005404849DB1' ->
       '005404849DB1'; cualquier otra cosa (vacia, otro largo, otros
       caracteres) -> $null. #>
    if (-not ($Mac -is [string])) { return $null }
    $limpia = ($Mac.Trim() -replace '[-:]', '').ToUpperInvariant()
    if ($limpia -match '^[0-9A-F]{12}$') { return $limpia }
    return $null
}

function ConvertTo-NumeroIPv4($Ip) {
    <# '192.168.3.10' -> [uint32]; si no es una IPv4 en punto decimal, $null. #>
    if (-not ($Ip -is [string])) { return $null }
    if ($Ip -notmatch '^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$') { return $null }
    [uint32]$n = 0
    for ($i = 1; $i -le 4; $i++) {
        $o = [int]$Matches[$i]
        if ($o -gt 255) { return $null }
        $n = [uint32](($n * 256) + $o)
    }
    return $n
}

function Test-IPv4Valida($Ip) {
    return ($null -ne (ConvertTo-NumeroIPv4 $Ip))
}

function Test-Clave($Objeto, [string]$Nombre) {
    <# True si el objeto (hashtable o [pscustomobject] de ConvertFrom-Json)
       tiene esa clave o propiedad (sin fallar con StrictMode). #>
    if ($null -eq $Objeto) { return $false }
    if ($Objeto -is [hashtable]) { return $Objeto.ContainsKey($Nombre) }
    return (Test-Propiedad $Objeto $Nombre)
}

function ConvertTo-EnteroEnRango($Valor, [int]$Minimo, [int]$Maximo) {
    <# [int] si $Valor es un entero (numero o texto de digitos) entre $Minimo
       y $Maximo; si no, $null (nunca lanza). #>
    if ($null -eq $Valor) { return $null }
    if ($Valor -is [bool]) { return $null }
    $n = 0
    if (-not [int]::TryParse([string]$Valor, [ref]$n)) { return $null }
    if (($n -lt $Minimo) -or ($n -gt $Maximo)) { return $null }
    return $n
}

function Test-IpEnSubred {
    <# True si $Ip es una IPv4 valida dentro de $Red/$Prefijo (por defecto
       192.168.3.0/24, la red de los modulos). #>
    param($Ip, [string]$Red = $script:RedModulos, [int]$Prefijo = $script:PrefijoModulos)
    if (($Prefijo -lt 0) -or ($Prefijo -gt 32)) { return $false }
    $n = ConvertTo-NumeroIPv4 $Ip
    $r = ConvertTo-NumeroIPv4 $Red
    if (($null -eq $n) -or ($null -eq $r)) { return $false }
    if ($Prefijo -eq 0) { return $true }
    $bloque = [uint32][math]::Pow(2, 32 - $Prefijo)
    return ([math]::Floor($n / $bloque) -eq [math]::Floor($r / $bloque))
}

function Test-AdaptadorEthernetFisico($Adaptador) {
    <# Ethernet por cable fisico: NdisPhysicalMedium = 14 (802.3), no virtual
       (si el objeto trae Virtual) y con una MAC valida. Rechaza Wi-Fi (9),
       Bluetooth (10) y virtuales o VPN (0 o Virtual = True). #>
    if ($null -eq $Adaptador) { return $false }
    if (-not (Test-Propiedad $Adaptador 'NdisPhysicalMedium')) { return $false }
    if ([int]$Adaptador.NdisPhysicalMedium -ne $script:MedioEthernet) { return $false }
    if ((Test-Propiedad $Adaptador 'Virtual') -and [bool]$Adaptador.Virtual) { return $false }
    if (-not (Test-Propiedad $Adaptador 'MacAddress')) { return $false }
    return ($null -ne (ConvertTo-MacNormalizada ([string]$Adaptador.MacAddress)))
}

function Select-AdaptadoresEthernet($Adaptadores) {
    <# Solo los adaptadores Ethernet fisicos (Test-AdaptadorEthernetFisico),
       por la tuberia (el que llama los junta con @(...)). #>
    @($Adaptadores) | Where-Object { Test-AdaptadorEthernetFisico $_ }
}

function Find-AdaptadorPorMac($Adaptadores, $Mac) {
    <# El adaptador Ethernet fisico con esa MAC, o $null (tambien si la MAC
       no es valida, si no hay ninguno o si hubiera mas de uno). #>
    $buscada = ConvertTo-MacNormalizada $Mac
    if ($null -eq $buscada) { return $null }
    $hallados = @(Select-AdaptadoresEthernet $Adaptadores | Where-Object {
        (ConvertTo-MacNormalizada ([string]$_.MacAddress)) -eq $buscada })
    if ($hallados.Count -ne 1) { return $null }
    return $hallados[0]
}

function Get-ConflictoSubred($Direcciones, $IndiceElegido) {
    <# Direcciones IPv4 de OTRAS interfaces (InterfaceIndex distinto del
       elegido) dentro de 192.168.3.0/24. Con alguna, el paso 08 no se aplica
       (dos adaptadores en la misma red rompen la ruta hacia el modulo).
       Devuelve por la tuberia cadenas 'IP (alias)' sin repetir (V20-s3-04:
       el que llama junta ActiveStore y PersistentStore, y la misma direccion
       suele estar en los dos; las junta con @(...)). #>
    @($Direcciones) | Where-Object {
        ($null -ne $_) -and (Test-Propiedad $_ 'IPAddress') -and (Test-Propiedad $_ 'InterfaceIndex') -and
        ([int]$_.InterfaceIndex -ne [int]$IndiceElegido) -and (Test-IpEnSubred ([string]$_.IPAddress))
    } | ForEach-Object {
        $alias = ''
        if (Test-Propiedad $_ 'InterfaceAlias') { $alias = [string]$_.InterfaceAlias }
        '{0} ({1})' -f $_.IPAddress, $alias
    } | Select-Object -Unique
}

function Test-DireccionAplicada($Direcciones, $IndiceElegido) {
    <# True si la interfaz elegida tiene 192.168.3.10/24 en un estado valido
       (no Duplicate/Invalid/Deprecated). Una 169.254.x.x (APIPA) no cuenta:
       es lo que queda cuando Windows no aplico la IP fija (leccion del banco). #>
    foreach ($d in @($Direcciones)) {
        if ($null -eq $d) { continue }
        if (-not ((Test-Propiedad $d 'IPAddress') -and (Test-Propiedad $d 'InterfaceIndex'))) { continue }
        if ([int]$d.InterfaceIndex -ne [int]$IndiceElegido) { continue }
        if ([string]$d.IPAddress -ne $script:IpEstacionModulos) { continue }
        if ((Test-Propiedad $d 'PrefixLength') -and ([int]$d.PrefixLength -ne $script:PrefijoModulos)) { continue }
        if ((Test-Propiedad $d 'AddressState') -and ($script:EstadosDireccionInvalidos -contains [string]$d.AddressState)) { continue }
        return $true
    }
    return $false
}

function Test-ConfiguracionModulos {
    <# True si la interfaz ya esta exactamente como la deja el paso 08:
       DHCP desactivado, solo 192.168.3.10/24 en IPv4, sin puerta de enlace y
       sin DNS. Sirve para la idempotencia (no tocar lo que ya esta bien). #>
    param($Direcciones, $IndiceElegido, [bool]$DhcpHabilitado, $PuertasEnlace, $Dns)
    if ($DhcpHabilitado) { return $false }
    if (@($PuertasEnlace | Where-Object { $_ }).Count -gt 0) { return $false }
    if (@($Dns | Where-Object { $_ }).Count -gt 0) { return $false }
    $propias = @(@($Direcciones) | Where-Object {
        ($null -ne $_) -and (Test-Propiedad $_ 'InterfaceIndex') -and ([int]$_.InterfaceIndex -eq [int]$IndiceElegido) })
    if ($propias.Count -ne 1) { return $false }
    return (Test-DireccionAplicada $propias $IndiceElegido)
}

function New-RespaldoRedModulos {
    <# Objeto de respaldo (lo guarda Save-Respaldo de _comun.ps1) con la
       configuracion IPv4 anterior del adaptador: MAC normalizada, alias,
       DHCP si/no, direcciones manuales (sin APIPA 169.254/16 ni las de DHCP:
       con DHCP vuelven solas), puertas de enlace y DNS. V20-s3-09: si se
       pasan, tambien la metrica de la interfaz (MetricaAutomatica si/no y
       MetricaInterfaz) y la de cada ruta por defecto (MetricasRuta, con
       Puerta y Metrica); un respaldo sin ellas sigue siendo valido. #>
    param(
        [Parameter(Mandatory)]$Adaptador,
        [bool]$DhcpHabilitado,
        $Direcciones,
        $PuertasEnlace,
        $Dns,
        $MetricaAutomatica = $null,
        $MetricaInterfaz = $null,
        $Rutas = $null
    )
    $mac = ConvertTo-MacNormalizada ([string]$Adaptador.MacAddress)
    if ($null -eq $mac) { throw 'El adaptador no tiene una MAC valida.' }
    $ipv4 = @(@($Direcciones) | Where-Object {
        ($null -ne $_) -and (Test-IPv4Valida ([string]$_.IPAddress)) -and
        (-not (Test-IpEnSubred ([string]$_.IPAddress) '169.254.0.0' 16)) -and
        (-not ((Test-Propiedad $_ 'PrefixOrigin') -and ([string]$_.PrefixOrigin -eq 'Dhcp')))
    } | ForEach-Object { @{ Ip = [string]$_.IPAddress; Prefijo = [int]$_.PrefixLength } })
    $gw = @(@($PuertasEnlace) | Where-Object { Test-IPv4Valida ([string]$_) } | ForEach-Object { [string]$_ })
    $servidores = @(@($Dns) | Where-Object { Test-IPv4Valida ([string]$_) } | ForEach-Object { [string]$_ })
    $alias = ''
    if (Test-Propiedad $Adaptador 'Name') { $alias = [string]$Adaptador.Name }
    $tabla = @{
        Mac           = $mac
        Alias         = $alias
        Dhcp          = $DhcpHabilitado
        IPv4          = $ipv4
        PuertasEnlace = $gw
        Dns           = $servidores
    }
    if ($MetricaAutomatica -is [bool]) { $tabla['MetricaAutomatica'] = $MetricaAutomatica }
    $mi = ConvertTo-EnteroEnRango $MetricaInterfaz 0 $script:MetricaInterfazMaxima
    if ($null -ne $mi) { $tabla['MetricaInterfaz'] = $mi }
    if ($null -ne $Rutas) {
        $tabla['MetricasRuta'] = @(@($Rutas) | Where-Object {
            ($null -ne $_) -and (Test-Clave $_ 'Puerta') -and (Test-Clave $_ 'Metrica') -and
            (Test-IPv4Valida ([string]$_.Puerta)) -and
            ($null -ne (ConvertTo-EnteroEnRango $_.Metrica 0 $script:MetricaRutaMaxima))
        } | ForEach-Object {
            @{ Puerta = [string]$_.Puerta; Metrica = (ConvertTo-EnteroEnRango $_.Metrica 0 $script:MetricaRutaMaxima) }
        })
    }
    return $tabla
}

function Test-RespaldoRedModulos($Respaldo) {
    <# '' si el respaldo (hashtable de Read-Respaldo) tiene la forma esperada;
       si no, el motivo. El inverso no aplica nada de un respaldo invalido
       (un respaldo alterado no puede poner una IP o una ruta cualquiera
       fuera de lo que es una configuracion IPv4 normal). #>
    if (-not ($Respaldo -is [hashtable])) { return 'el respaldo no es una tabla' }
    foreach ($k in @('Mac', 'Dhcp', 'IPv4', 'PuertasEnlace', 'Dns')) {
        if (-not $Respaldo.ContainsKey($k)) { return "falta '$k'" }
    }
    if ($null -eq (ConvertTo-MacNormalizada ([string]$Respaldo['Mac']))) { return 'MAC invalida' }
    if (-not ($Respaldo['Dhcp'] -is [bool])) { return 'Dhcp no es verdadero/falso' }
    foreach ($d in @($Respaldo['IPv4'])) {
        if ($null -eq $d) { continue }
        if (-not (Test-Clave $d 'Ip')) { return 'direccion sin Ip' }
        if (-not (Test-IPv4Valida ([string]$d.Ip))) { return "IPv4 invalida '$($d.Ip)'" }
        # V20-s3-10: con StrictMode, leer una propiedad que no existe lanza
        if (-not (Test-Clave $d 'Prefijo')) { return 'direccion sin Prefijo' }
        if ($null -eq (ConvertTo-EnteroEnRango $d.Prefijo 1 32)) { return "prefijo invalido '$($d.Prefijo)'" }
    }
    foreach ($g in @($Respaldo['PuertasEnlace'])) {
        if ($null -eq $g) { continue }
        if (-not (Test-IPv4Valida ([string]$g))) { return "puerta de enlace invalida '$g'" }
    }
    foreach ($s in @($Respaldo['Dns'])) {
        if ($null -eq $s) { continue }
        if (-not (Test-IPv4Valida ([string]$s))) { return "DNS invalido '$s'" }
    }
    # V20-s3-09: metricas (opcionales; un respaldo anterior no las tiene)
    if ($Respaldo.ContainsKey('MetricaAutomatica') -and ($null -ne $Respaldo['MetricaAutomatica']) -and
            (-not ($Respaldo['MetricaAutomatica'] -is [bool]))) {
        return 'MetricaAutomatica no es verdadero/falso'
    }
    if ($Respaldo.ContainsKey('MetricaInterfaz') -and ($null -ne $Respaldo['MetricaInterfaz']) -and
            ($null -eq (ConvertTo-EnteroEnRango $Respaldo['MetricaInterfaz'] 0 $script:MetricaInterfazMaxima))) {
        return "metrica de interfaz invalida '$($Respaldo['MetricaInterfaz'])'"
    }
    if ($Respaldo.ContainsKey('MetricasRuta')) {
        foreach ($m in @($Respaldo['MetricasRuta'])) {
            if ($null -eq $m) { continue }
            if (-not ((Test-Clave $m 'Puerta') -and (Test-Clave $m 'Metrica'))) { return 'metrica de ruta sin Puerta o Metrica' }
            if (-not (Test-IPv4Valida ([string]$m.Puerta))) { return "puerta de la metrica invalida '$($m.Puerta)'" }
            if ($null -eq (ConvertTo-EnteroEnRango $m.Metrica 0 $script:MetricaRutaMaxima)) { return "metrica de ruta invalida '$($m.Metrica)'" }
        }
    }
    return ''
}

function Get-PlanRestauracion($Respaldo) {
    <# Lo que aplica el inverso, a partir de un respaldo YA validado con
       Test-RespaldoRedModulos (hashtable de Read-Respaldo; sus listas vienen
       de ConvertFrom-Json y una de un solo elemento puede llegar como
       escalar: por eso todo se convierte a arreglo con @(...)).
       Devuelve una tabla (no por la tuberia, para no desenrollar arreglos):
         Dhcp; IPv4 (@{Ip; Prefijo}); Puertas (@{Puerta; Metrica o $null});
         Dns; MetricaAutomatica y MetricaInterfaz ($null si no se respaldaron). #>
    $ipv4 = @(@($Respaldo['IPv4']) | Where-Object { $null -ne $_ } | ForEach-Object {
        @{ Ip = [string]$_.Ip; Prefijo = (ConvertTo-EnteroEnRango $_.Prefijo 1 32) }
    })
    $metricas = @{}
    if ($Respaldo.ContainsKey('MetricasRuta')) {
        foreach ($m in @($Respaldo['MetricasRuta'])) {
            if ($null -eq $m) { continue }
            $metricas[[string]$m.Puerta] = ConvertTo-EnteroEnRango $m.Metrica 0 $script:MetricaRutaMaxima
        }
    }
    $puertas = @(@($Respaldo['PuertasEnlace']) | Where-Object { $_ } | ForEach-Object {
        $g = [string]$_
        $metrica = $null
        if ($metricas.ContainsKey($g)) { $metrica = $metricas[$g] }
        @{ Puerta = $g; Metrica = $metrica }
    })
    $dns = @(@($Respaldo['Dns']) | Where-Object { $_ } | ForEach-Object { [string]$_ })
    $automatica = $null
    if ($Respaldo.ContainsKey('MetricaAutomatica') -and ($Respaldo['MetricaAutomatica'] -is [bool])) {
        $automatica = [bool]$Respaldo['MetricaAutomatica']
    }
    $interfaz = $null
    if ($Respaldo.ContainsKey('MetricaInterfaz')) {
        $interfaz = ConvertTo-EnteroEnRango $Respaldo['MetricaInterfaz'] 0 $script:MetricaInterfazMaxima
    }
    return @{
        Dhcp              = [bool]$Respaldo['Dhcp']
        IPv4              = $ipv4
        Puertas           = $puertas
        Dns               = $dns
        MetricaAutomatica = $automatica
        MetricaInterfaz   = $interfaz
    }
}
