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
       Devuelve por la tuberia cadenas 'IP (alias)' (el que llama las junta
       con @(...)). #>
    @($Direcciones) | Where-Object {
        ($null -ne $_) -and (Test-Propiedad $_ 'IPAddress') -and (Test-Propiedad $_ 'InterfaceIndex') -and
        ([int]$_.InterfaceIndex -ne [int]$IndiceElegido) -and (Test-IpEnSubred ([string]$_.IPAddress))
    } | ForEach-Object {
        $alias = ''
        if (Test-Propiedad $_ 'InterfaceAlias') { $alias = [string]$_.InterfaceAlias }
        '{0} ({1})' -f $_.IPAddress, $alias
    }
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
       con DHCP vuelven solas), puertas de enlace y DNS. #>
    param(
        [Parameter(Mandatory)]$Adaptador,
        [bool]$DhcpHabilitado,
        $Direcciones,
        $PuertasEnlace,
        $Dns
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
    return @{
        Mac           = $mac
        Alias         = $alias
        Dhcp          = $DhcpHabilitado
        IPv4          = $ipv4
        PuertasEnlace = $gw
        Dns           = $servidores
    }
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
        if (-not ((Test-Propiedad $d 'Ip') -or (($d -is [hashtable]) -and $d.ContainsKey('Ip')))) { return 'direccion sin Ip' }
        if (-not (Test-IPv4Valida ([string]$d.Ip))) { return "IPv4 invalida '$($d.Ip)'" }
        $p = [int]$d.Prefijo
        if (($p -lt 1) -or ($p -gt 32)) { return "prefijo invalido '$($d.Prefijo)'" }
    }
    foreach ($g in @($Respaldo['PuertasEnlace'])) {
        if ($null -eq $g) { continue }
        if (-not (Test-IPv4Valida ([string]$g))) { return "puerta de enlace invalida '$g'" }
    }
    foreach ($s in @($Respaldo['Dns'])) {
        if ($null -eq $s) { continue }
        if (-not (Test-IPv4Valida ([string]$s))) { return "DNS invalido '$s'" }
    }
    return ''
}
