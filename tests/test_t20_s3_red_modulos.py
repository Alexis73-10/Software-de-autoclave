"""Tanda 20, s3 (T20-05): paso 08 de la estación, red de los módulos de E/S
(tools/estacion/08_red_modulos.ps1, su inverso, las funciones puras de
_red_modulos_puras.ps1 y el puente estacion_setup.ps1).

Prohibido ejecutar los 08_*.ps1, el puente o cualquier cosa que cambie la red
o el registro. Por eso:
- `test_texto_*`: ESTÁTICAS, solo comprueban lo que declara el texto;
- `test_parser_*`: solo analizan los .ps1 con el parser de PowerShell;
- `test_puras_*`: cargan SOLO _red_modulos_puras.ps1 (sin efectos: no llama
  cmdlets de red) y lo llaman con objetos ficticios [pscustomobject].
Se saltan sin powershell.exe. La comprobación real queda en M-7 (banco)."""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
ESTACION = RAIZ / "tools" / "estacion"
INSTALADOR = RAIZ / "tools" / "instalador"

PASO08 = "08_red_modulos.ps1"
REVERTIR08 = "08_revertir_red_modulos.ps1"
PURAS = "_red_modulos_puras.ps1"

pytestmark = pytest.mark.req("T20-05")
CON_POWERSHELL = pytest.mark.skipif(shutil.which("powershell.exe") is None, reason="sin powershell.exe")

# cmdlets que cambian la red o el sistema: nunca en las funciones puras
CMDLETS_CON_EFECTOS = ("Set-Net", "New-Net", "Remove-Net", "Get-Net", "Set-Dns", "Get-Dns",
                       "Set-Content", "Add-Content", "Out-File", "Remove-Item", "New-Item",
                       "Write-Log", "Save-Respaldo", "Read-Respaldo", "New-ItemProperty", "netsh",
                       "Start-Process", "Invoke-Expression")


def _ps(nombre: str, carpeta: Path = ESTACION) -> str:
    return (carpeta / nombre).read_text(encoding="ascii")          # ASCII puro


def _cuerpo(texto: str) -> str:
    """Código del script sin el bloque de ayuda <# ... #> inicial."""
    return texto.split("#>", 1)[1]


def _sin_comentarios(texto: str) -> str:
    texto = re.sub(r"<#.*?#>", "", texto, flags=re.S)
    return "\n".join(l.split("#", 1)[0] if l.lstrip().startswith("#") else l for l in texto.splitlines())


def _funcion_ps(texto: str, nombre: str) -> str:
    i = texto.index(f"function {nombre}")
    j = texto.find("\nfunction ", i + 1)
    return texto[i:] if j < 0 else texto[i:j]


# ── Scripts del paso 08 ──────────────────────────────────────────────────────

def test_texto_scripts_existen_ascii_usan_comun_puras_y_whatif():
    for nombre in (PASO08, REVERTIR08):
        s = _ps(nombre)
        assert '. "$PSScriptRoot\\_comun.ps1"' in s, nombre
        assert '. "$PSScriptRoot\\_red_modulos_puras.ps1"' in s, nombre
        assert "[CmdletBinding(SupportsShouldProcess)]" in s, nombre
        assert "Assert-Administrador" in s, nombre
        assert "$Paso = '08_red_modulos'" in s, nombre
        assert "WhatIf=$WhatIfPreference" in s, nombre
        assert "$ErrorActionPreference = 'Stop'" in s, nombre
        assert "Read-Host" not in s and "ConfirmImpact" not in s, nombre
    assert "param(\n    [Parameter(Mandatory)][string]$Adaptador\n)" in _ps(PASO08).replace("\r\n", "\n")
    _ps(PURAS)                                                     # también ASCII


def test_texto_solo_ethernet_fisico_por_mac():
    s = _cuerpo(_ps(PASO08))
    assert "Find-AdaptadorPorMac @(Get-NetAdapter -Physical -ErrorAction Stop) $mac" in s
    assert "ConvertTo-MacNormalizada $Adaptador" in s
    puras = _ps(PURAS)
    filtro = _funcion_ps(puras, "Test-AdaptadorEthernetFisico")
    assert "$script:MedioEthernet" in filtro and "$script:MedioEthernet = 14" in puras
    assert "Virtual" in filtro                                    # rechaza virtuales
    assert "Select-AdaptadoresEthernet $Adaptadores" in _funcion_ps(puras, "Find-AdaptadorPorMac")


def test_texto_conflicto_antes_de_respaldo_y_respaldo_antes_de_aplicar():
    s = _cuerpo(_ps(PASO08))
    i_conflicto = s.index("Get-ConflictoSubred")
    i_throw_conflicto = s.index("throw", i_conflicto)
    i_respaldo = s.index("Save-Respaldo $Paso $nuevo")
    i_aplicar = s.index("Set-NetIPInterface -InterfaceIndex $indice -AddressFamily IPv4 -Dhcp Disabled")
    assert i_conflicto < i_throw_conflicto < i_respaldo < i_aplicar
    # el respaldo solo la primera vez y de un solo adaptador
    assert "if (-not $resp.ContainsKey('Mac'))" in s
    assert "-ne $mac" in s and "revierta primero" in s
    # sin respaldo escrito no se aplica nada
    bloque = s[s.index("$PSCmdlet.ShouldProcess("):i_aplicar]
    assert "Test-Path -LiteralPath (Get-RutaRespaldo $Paso)" in bloque and "throw" in bloque


def test_texto_aplica_sin_puerta_de_enlace_ni_dns():
    s = _sin_comentarios(_cuerpo(_ps(PASO08)))
    nueva = re.search(r"New-NetIPAddress(?:[^\n`]|`\n)*", s).group(0)    # con continuaciones `
    assert "-IPAddress $script:IpEstacionModulos" in nueva
    assert "-PrefixLength $script:PrefijoModulos" in nueva
    assert "DefaultGateway" not in s
    assert "New-NetRoute" not in s
    assert "-ServerAddresses" not in s                              # DNS sin servidores
    assert "Set-DnsClientServerAddress -InterfaceIndex $indice -ResetServerAddresses" in s
    assert "Remove-NetRoute" in s and "'0.0.0.0/0'" in s
    puras = _ps(PURAS)
    assert "$script:IpEstacionModulos = '192.168.3.10'" in puras
    assert "$script:PrefijoModulos = 24" in puras
    assert "$script:RedModulos = '192.168.3.0'" in puras


def test_texto_verifica_la_ip_en_ese_adaptador_y_falla_si_no():
    s = _cuerpo(_ps(PASO08))
    verif = s[s.index("# 4. Verificacion"):]
    assert "Test-DireccionAplicada $despues.Direcciones $indice" in verif
    assert "(-not $despues.Dhcp)" in verif and "$despues.Puertas.Count -eq 0" in verif
    assert "throw" in verif
    # APIPA no cuenta: solo 192.168.3.10/24 en un estado válido
    aplicada = _funcion_ps(_ps(PURAS), "Test-DireccionAplicada")
    assert "$script:IpEstacionModulos" in aplicada and "EstadosDireccionInvalidos" in aplicada


def test_texto_idempotente():
    s = _cuerpo(_ps(PASO08))
    assert s.index("Test-ConfiguracionModulos") < s.index("Set-NetIPInterface -InterfaceIndex $indice")
    assert "Sin cambio" in s


def test_texto_revertir_sin_respaldo_no_toca_nada():
    s = _sin_comentarios(_cuerpo(_ps(REVERTIR08)))
    i_sin = s.index("if (-not $resp.ContainsKey('Mac'))")
    i_return = s.index("return", i_sin)
    primer_cambio = min(s.index(c) for c in ("Remove-NetRoute", "Remove-NetIPAddress", "Set-NetIPInterface",
                                              "New-NetIPAddress", "Set-DnsClientServerAddress"))
    assert i_sin < i_return < primer_cambio
    assert "Get-Net" not in s[:i_return]                            # ni siquiera lee la red


def test_texto_revertir_valida_respaldo_restaura_y_conserva_si_falla():
    s = _cuerpo(_ps(REVERTIR08))
    assert s.index("Test-RespaldoRedModulos $resp") < s.index("Remove-NetRoute")
    assert "Find-AdaptadorPorMac" in s
    assert "-Dhcp Enabled" in s and "-ResetServerAddresses" in s       # DHCP con DNS automático
    assert "-ServerAddresses $dns" in s and "-NextHop $g" in s          # fijo: DNS y puertas guardados
    # un fallo lanza antes de borrar el respaldo; el respaldo solo se borra al final
    i_catch = s.index("} catch {")
    assert "throw" in s[i_catch:s.index("Remove-Item -LiteralPath (Get-RutaRespaldo $Paso)")]
    assert s.rindex("Remove-Item -LiteralPath (Get-RutaRespaldo $Paso)") > i_catch


def test_texto_puras_sin_efectos():
    puras = _sin_comentarios(_ps(PURAS))
    for cmdlet in CMDLETS_CON_EFECTOS:
        assert cmdlet not in puras, cmdlet
    assert "_comun.ps1" not in puras


def test_texto_puente_admite_el_paso_08_con_adaptador():
    puente = _ps("estacion_setup.ps1", INSTALADOR)
    assert "ValidateSet('01', '02', '04', '05', '06', '07', '08')" in puente
    assert "'08' = @('08_red_modulos.ps1', '08_revertir_red_modulos.ps1')" in puente
    assert "[string]$Adaptador" in puente
    bloque = puente[puente.index("elseif ($Paso -eq '08' -and $Accion -eq 'Aplicar')"):]
    assert "throw 'Paso 08 sin -Adaptador.'" in bloque
    assert "& $ruta -Adaptador $Adaptador" in bloque


def test_texto_leeme_documenta_el_paso_08():
    leeme = (ESTACION / "LEEME.md").read_text(encoding="utf-8")
    for texto in (PASO08, REVERTIR08, PURAS, "respaldo_08_red_modulos.json", "192.168.3.10/24",
                  "NdisPhysicalMedium = 14", "08_revertir_red_modulos.ps1"):
        assert texto in leeme, texto


@CON_POWERSHELL
def test_parser_de_powershell_sin_errores():
    """Solo analiza (Parser::ParseFile): no ejecuta ningún script."""
    archivos = [str(ESTACION / n) for n in (PURAS, PASO08, REVERTIR08, "_comun.ps1")]
    archivos.append(str(INSTALADOR / "estacion_setup.ps1"))
    lista = ",".join(f"'{a}'" for a in archivos)
    orden = (
        f"$r=@(); foreach($f in @({lista})){{$t=$null;$e=$null;"
        "[void][System.Management.Automation.Language.Parser]::ParseFile($f,[ref]$t,[ref]$e);"
        "$r+=@{f=$f;n=$e.Count}}; $r | ConvertTo-Json -Compress"
    )
    salida = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", orden],
                            capture_output=True, text=True, timeout=120)
    datos = json.loads(salida.stdout)
    assert [d["n"] for d in datos] == [0] * len(archivos), datos


@CON_POWERSHELL
def test_analisis_estatico_si_hay_scriptanalyzer():
    """Invoke-ScriptAnalyzer (solo análisis estático) si el módulo está; si no, se salta."""
    hay = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
                          "if (Get-Module -ListAvailable PSScriptAnalyzer) { 'si' } else { 'no' }"],
                         capture_output=True, text=True, timeout=120).stdout.strip()
    if hay != "si":
        pytest.skip("PSScriptAnalyzer no está instalado")
    archivos = ",".join(f"'{ESTACION / n}'" for n in (PURAS, PASO08, REVERTIR08))
    orden = (f"@(foreach($f in @({archivos})){{ Invoke-ScriptAnalyzer -Path $f -Severity Error }}) | "
             "Select-Object ScriptName,Line,RuleName,Message | ConvertTo-Json -Compress")
    salida = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", orden],
                            capture_output=True, text=True, timeout=300).stdout.strip()
    assert salida in ("", "[]"), salida


# ── Funciones puras con datos ficticios ──────────────────────────────────────

def _puras(script: str):
    """Carga SOLO _red_modulos_puras.ps1 y evalúa `script` (que deja un objeto
    en $r); devuelve $r como JSON."""
    ruta = str(ESTACION / PURAS).replace("'", "''")
    orden = f"$ErrorActionPreference='Stop'; . '{ruta}'; {script}; $r | ConvertTo-Json -Depth 6 -Compress"
    salida = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", orden],
                            capture_output=True, text=True, timeout=120)
    assert salida.returncode == 0, salida.stderr
    return json.loads(salida.stdout)


ADAPTADORES = (
    "$a=@("
    "[pscustomobject]@{Name='Wi-Fi';MacAddress='04-68-74-2D-57-61';NdisPhysicalMedium=9;Virtual=$false;ifIndex=10},"
    "[pscustomobject]@{Name='Ethernet';MacAddress='40-C2-BA-A6-D0-80';NdisPhysicalMedium=14;Virtual=$false;ifIndex=9},"
    "[pscustomobject]@{Name='Ethernet 2';MacAddress='00-54-04-84-9D-B1';NdisPhysicalMedium=14;Virtual=$false;ifIndex=12},"
    "[pscustomobject]@{Name='Tailscale';MacAddress='';NdisPhysicalMedium=0;Virtual=$true;ifIndex=41},"
    "[pscustomobject]@{Name='vEthernet';MacAddress='00-15-5D-00-00-01';NdisPhysicalMedium=14;Virtual=$true;ifIndex=50},"
    "[pscustomobject]@{Name='Bluetooth';MacAddress='04-68-74-2D-57-62';NdisPhysicalMedium=10;Virtual=$false;ifIndex=3})"
)


@CON_POWERSHELL
def test_puras_mac_e_ipv4():
    r = _puras(
        "$r=@{"
        "m1=ConvertTo-MacNormalizada '00-54-04-84-9d-b1'; m2=ConvertTo-MacNormalizada '00:54:04:84:9D:B1';"
        "m3=ConvertTo-MacNormalizada '005404849DB1'; m4=ConvertTo-MacNormalizada '00-54-04-84-9D';"
        "m5=ConvertTo-MacNormalizada '00-54-04-84-9D-BG'; m6=ConvertTo-MacNormalizada '';"
        "m7=ConvertTo-MacNormalizada '00-54-04-84-9D-B1\" -X'; m8=ConvertTo-MacNormalizada $null;"
        "s1=Test-IpEnSubred '192.168.3.10'; s2=Test-IpEnSubred '192.168.3.0'; s3=Test-IpEnSubred '192.168.3.255';"
        "s4=Test-IpEnSubred '192.168.4.10'; s5=Test-IpEnSubred '192.168.3.256'; s6=Test-IpEnSubred '192.168.3';"
        "s7=Test-IpEnSubred 'fe80::1'; s8=Test-IpEnSubred '10.1.2.3' '10.0.0.0' 8; s9=Test-IpEnSubred '169.254.3.3' '169.254.0.0' 16;"
        "s10=Test-IpEnSubred '192.168.2.255'; s11=Test-IpEnSubred '255.255.255.255' '0.0.0.0' 0}"
    )
    assert r["m1"] == r["m2"] == r["m3"] == "005404849DB1"
    assert r["m4"] is None and r["m5"] is None and r["m6"] is None and r["m7"] is None and r["m8"] is None
    assert (r["s1"], r["s2"], r["s3"]) == (True, True, True)
    assert (r["s4"], r["s5"], r["s6"], r["s7"], r["s10"]) == (False, False, False, False, False)
    assert r["s8"] is True and r["s9"] is True and r["s11"] is True


@CON_POWERSHELL
def test_puras_filtra_wifi_virtuales_y_busca_por_mac():
    r = _puras(
        ADAPTADORES + ";"
        "$r=@{eth=@(Select-AdaptadoresEthernet $a | ForEach-Object { $_.Name });"
        "porMac=(Find-AdaptadorPorMac $a '00:54:04:84:9d:b1').Name;"
        "wifi=$null -eq (Find-AdaptadorPorMac $a '04-68-74-2D-57-61');"
        "virtual=$null -eq (Find-AdaptadorPorMac $a '00-15-5D-00-00-01');"
        "bt=$null -eq (Find-AdaptadorPorMac $a '04-68-74-2D-57-62');"
        "nada=$null -eq (Find-AdaptadorPorMac $a 'AA-BB-CC-DD-EE-FF');"
        "invalida=$null -eq (Find-AdaptadorPorMac $a 'xx');"
        "duplicada=$null -eq (Find-AdaptadorPorMac @($a[1],$a[1]) '40-C2-BA-A6-D0-80');"
        "sinMedio=Test-AdaptadorEthernetFisico ([pscustomobject]@{Name='x';MacAddress='40-C2-BA-A6-D0-81'})}"
    )
    assert r["eth"] == ["Ethernet", "Ethernet 2"]
    assert r["porMac"] == "Ethernet 2"
    assert r["wifi"] and r["virtual"] and r["bt"] and r["nada"] and r["invalida"] and r["duplicada"]
    assert r["sinMedio"] is False


@CON_POWERSHELL
def test_puras_conflicto_con_otro_adaptador_en_la_subred():
    r = _puras(
        "$d=@("
        "[pscustomobject]@{IPAddress='192.168.3.5';InterfaceIndex=10;InterfaceAlias='Wi-Fi'},"
        "[pscustomobject]@{IPAddress='192.168.3.10';InterfaceIndex=12;InterfaceAlias='Ethernet 2'},"
        "[pscustomobject]@{IPAddress='10.0.0.4';InterfaceIndex=9;InterfaceAlias='Ethernet'},"
        "[pscustomobject]@{IPAddress='127.0.0.1';InterfaceIndex=1;InterfaceAlias='Loopback'});"
        "$r=@{con=@(Get-ConflictoSubred $d 12); propia=@(Get-ConflictoSubred @($d[1],$d[2],$d[3]) 12);"
        "otra=@(Get-ConflictoSubred $d 10)}"
    )
    assert r["con"] == ["192.168.3.5 (Wi-Fi)"]
    assert r["propia"] == []                     # la del adaptador elegido no es conflicto
    assert r["otra"] == ["192.168.3.10 (Ethernet 2)"]


@CON_POWERSHELL
def test_puras_direccion_aplicada_rechaza_apipa_y_estados_invalidos():
    r = _puras(
        "$ok=[pscustomobject]@{IPAddress='192.168.3.10';InterfaceIndex=12;PrefixLength=24;AddressState='Preferred'};"
        "$tent=[pscustomobject]@{IPAddress='192.168.3.10';InterfaceIndex=12;PrefixLength=24;AddressState='Tentative'};"
        "$dup=[pscustomobject]@{IPAddress='192.168.3.10';InterfaceIndex=12;PrefixLength=24;AddressState='Duplicate'};"
        "$apipa=[pscustomobject]@{IPAddress='169.254.10.3';InterfaceIndex=12;PrefixLength=16;AddressState='Preferred'};"
        "$pref=[pscustomobject]@{IPAddress='192.168.3.10';InterfaceIndex=12;PrefixLength=16;AddressState='Preferred'};"
        "$r=@{ok=Test-DireccionAplicada @($ok) 12; tent=Test-DireccionAplicada @($tent) 12;"
        "dup=Test-DireccionAplicada @($dup) 12; apipa=Test-DireccionAplicada @($apipa) 12;"
        "pref=Test-DireccionAplicada @($pref) 12; otra=Test-DireccionAplicada @($ok) 9;"
        "conf=Test-ConfiguracionModulos -Direcciones @($ok) -IndiceElegido 12 -DhcpHabilitado $false -PuertasEnlace @() -Dns @();"
        "confDhcp=Test-ConfiguracionModulos -Direcciones @($ok) -IndiceElegido 12 -DhcpHabilitado $true -PuertasEnlace @() -Dns @();"
        "confGw=Test-ConfiguracionModulos -Direcciones @($ok) -IndiceElegido 12 -DhcpHabilitado $false -PuertasEnlace @('192.168.3.1') -Dns @();"
        "confDns=Test-ConfiguracionModulos -Direcciones @($ok) -IndiceElegido 12 -DhcpHabilitado $false -PuertasEnlace @() -Dns @('8.8.8.8');"
        "confDos=Test-ConfiguracionModulos -Direcciones @($ok,$apipa) -IndiceElegido 12 -DhcpHabilitado $false -PuertasEnlace @() -Dns @()}"
    )
    assert r["ok"] and r["tent"]
    assert not r["dup"] and not r["apipa"] and not r["pref"] and not r["otra"]
    assert r["conf"] is True
    assert not r["confDhcp"] and not r["confGw"] and not r["confDns"] and not r["confDos"]


@CON_POWERSHELL
def test_puras_respaldo_y_su_validacion():
    r = _puras(
        ADAPTADORES + ";"
        "$dirs=@([pscustomobject]@{IPAddress='10.0.0.5';PrefixLength=8;PrefixOrigin='Manual'},"
        "[pscustomobject]@{IPAddress='169.254.3.3';PrefixLength=16;PrefixOrigin='WellKnown'},"
        "[pscustomobject]@{IPAddress='192.168.1.40';PrefixLength=24;PrefixOrigin='Dhcp'});"
        "$fijo=New-RespaldoRedModulos -Adaptador $a[1] -DhcpHabilitado $false -Direcciones $dirs "
        "-PuertasEnlace @('10.0.0.1','basura') -Dns @('8.8.8.8','') ;"
        "$dhcp=New-RespaldoRedModulos -Adaptador $a[2] -DhcpHabilitado $true -Direcciones @() -PuertasEnlace @() -Dns @();"
        "$json=($fijo | ConvertTo-Json -Depth 5 | ConvertFrom-Json); $tabla=@{};"
        "foreach($p in $json.PSObject.Properties){ $tabla[$p.Name]=$p.Value };"
        "$malo=$fijo.Clone(); $malo['Mac']='zz';"
        "$malaIp=$fijo.Clone(); $malaIp['IPv4']=@(@{Ip='300.1.1.1';Prefijo=8});"
        "$malGw=$fijo.Clone(); $malGw['PuertasEnlace']=@('a.b.c.d');"
        "$sinDhcp=$fijo.Clone(); $sinDhcp.Remove('Dhcp');"
        "$malPref=$fijo.Clone(); $malPref['IPv4']=@(@{Ip='10.0.0.5';Prefijo=40});"
        "$r=@{fijo=$fijo; dhcp=$dhcp; vFijo=Test-RespaldoRedModulos $fijo; vJson=Test-RespaldoRedModulos $tabla;"
        "vDhcp=Test-RespaldoRedModulos $dhcp; vMalo=Test-RespaldoRedModulos $malo; vMalaIp=Test-RespaldoRedModulos $malaIp;"
        "vMalGw=Test-RespaldoRedModulos $malGw; vSinDhcp=Test-RespaldoRedModulos $sinDhcp;"
        "vMalPref=Test-RespaldoRedModulos $malPref; vNoTabla=Test-RespaldoRedModulos 'x'}"
    )
    fijo = r["fijo"]
    assert fijo["Mac"] == "40C2BAA6D080" and fijo["Alias"] == "Ethernet" and fijo["Dhcp"] is False
    ipv4 = fijo["IPv4"] if isinstance(fijo["IPv4"], list) else [fijo["IPv4"]]
    assert ipv4 == [{"Ip": "10.0.0.5", "Prefijo": 8}]       # sin APIPA ni la de DHCP
    gw = fijo["PuertasEnlace"] if isinstance(fijo["PuertasEnlace"], list) else [fijo["PuertasEnlace"]]
    dns = fijo["Dns"] if isinstance(fijo["Dns"], list) else [fijo["Dns"]]
    assert gw == ["10.0.0.1"] and dns == ["8.8.8.8"]
    assert r["dhcp"]["Mac"] == "005404849DB1" and r["dhcp"]["Dhcp"] is True
    assert r["vFijo"] == "" and r["vJson"] == "" and r["vDhcp"] == ""
    for clave in ("vMalo", "vMalaIp", "vMalGw", "vSinDhcp", "vMalPref", "vNoTabla"):
        assert r[clave] != "", clave
