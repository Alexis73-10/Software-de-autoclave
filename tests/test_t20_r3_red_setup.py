"""Tanda 20, r3: correcciones de la revisión del Setup y del paso 08
(V20-s3-01 a V20-s3-11) en tools/instalador/autoclave.iss,
tools/estacion/08_red_modulos.ps1, 08_revertir_red_modulos.ps1,
_red_modulos_puras.ps1 y los dos LEEME.

Prohibido ejecutar el Setup, ISCC, los 08_*.ps1 o el puente: las pruebas son
ESTÁTICAS (texto), réplicas en Python de funciones Pascal sencillas o llamadas
a las funciones PURAS de _red_modulos_puras.ps1 con datos ficticios (se
saltan sin powershell.exe). La comprobación real queda en M-7 (banco)."""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
INSTALADOR = RAIZ / "tools" / "instalador"
ESTACION = RAIZ / "tools" / "estacion"
ISS = (INSTALADOR / "autoclave.iss").read_text(encoding="utf-8-sig").replace("\r\n", "\n")
CODIGO = ISS[ISS.index("[Code]"):]
PASO08 = (ESTACION / "08_red_modulos.ps1").read_text(encoding="ascii").replace("\r\n", "\n")
REVERTIR08 = (ESTACION / "08_revertir_red_modulos.ps1").read_text(encoding="ascii").replace("\r\n", "\n")
PURAS = ESTACION / "_red_modulos_puras.ps1"
LEEME_INST = (INSTALADOR / "LEEME.md").read_text(encoding="utf-8")
LEEME_EST = (ESTACION / "LEEME.md").read_text(encoding="utf-8")

pytestmark = pytest.mark.req("T20-05")
CON_POWERSHELL = pytest.mark.skipif(shutil.which("powershell.exe") is None, reason="sin powershell.exe")


def _funcion(nombre: str) -> str:
    m = re.search(rf"^(function|procedure) {nombre}\b.*?(?=^(function|procedure) |\Z)", CODIGO, re.M | re.S)
    assert m, nombre
    return m.group(0)


def _mensaje(idioma: str, clave: str) -> str:
    m = re.search(rf"^{idioma}\.{clave}=(.*)$", ISS, re.M)
    assert m, f"{idioma}.{clave}"
    return m.group(1)


def _cuerpo(texto: str) -> str:
    return texto.split("#>", 1)[1]


# ── V20-s3-01: Reparar puede cambiar de adaptador ────────────────────────────

def test_s3_01_cambio_de_adaptador_revierte_antes_y_solo_aplica_si_salio_bien():
    arm = _funcion("AplicarRedModulos")
    i_anterior = arm.index("Anterior := AdaptadorGuardado08;")
    i_cond = arm.index("if (Anterior <> '') and (Anterior <> Mac) then")
    i_revertir = arm.index("if not EjecutarPaso('08', 'Revertir', '') then")
    i_marca = arm.index("MarcarPaso('08');")
    i_mac = arm.index("RegWriteStringValue(HKLM64, '{#ClaveEstacion}', 'Adaptador08', Mac);")
    i_aplica = arm.index("EjecutarPaso('08', 'Aplicar'")
    assert i_anterior < i_cond < i_revertir < i_marca < i_mac < i_aplica
    # si la reversión falla: se avisa, no se aplica ni se cambia Adaptador08
    fallo = arm[i_revertir:i_marca]
    assert "RedFallida := True;" in fallo and "CambioRedFallido := True;" in fallo
    assert "AdaptadorAnterior08 := Anterior;" in fallo
    assert "exit;" in fallo
    assert "RegWrite" not in fallo and "'Aplicar'" not in fallo
    # el aviso llega a la página del resultado, en los dos idiomas
    pm = _funcion("ProbarModulo")
    assert "if CambioRedFallido then" in pm
    assert "FmtMessage(CustomMessage('RedCambioFallido'), [AdaptadorAnterior08," in pm
    assert "NO se cambió de adaptador" in _mensaje("es", "RedCambioFallido")
    assert "NOT changed" in _mensaje("en", "RedCambioFallido")
    for idioma in ("es", "en"):
        assert "respaldo_08_red_modulos.json" in _mensaje(idioma, "RedCambioFallido")


def test_s3_01_adaptador_guardado_lee_paso08_y_adaptador08():
    ag = _funcion("AdaptadorGuardado08")
    assert "RegValueExists(HKLM64, '{#ClaveEstacion}', 'Paso08')" in ag
    assert "RegQueryStringValue(HKLM64, '{#ClaveEstacion}', 'Adaptador08', Guardada)" in ag
    assert "Result := NormalizarMac(Guardada);" in ag


def test_s3_01_validar_red_no_cuenta_al_guardado_con_solo_la_10():
    vr = _funcion("ValidarRed")
    assert "Guardado := AdaptadorGuardado08;" in vr
    assert ("(J <> I) and IpsEnRedModulos(AdapIps[J]) and\n"
            "        not ((Guardado <> '') and (NormalizarMac(AdapMac[J]) = Guardado) and "
            "SoloIpEstacionEnRed(AdapIps[J])) then") in vr
    sol = _funcion("SoloIpEstacionEnRed")
    assert "if Ip <> IpEstacionModulos then" in sol and "IpEnRedModulos(Ip)" in sol


def test_s3_01_replica_solo_ip_estacion_en_red():
    """Réplica de SoloIpEstacionEnRed (lista separada por ';')."""
    def en_red(ip: str) -> bool:
        ip = ip.strip()
        if not ip.startswith("192.168.3."):
            return False
        r = ip[len("192.168.3."):]
        return 1 <= len(r) <= 3 and r.isdigit() and int(r) <= 255

    def solo_10(ips: str) -> bool:
        resultado = False
        for ip in [p.strip() for p in ips.split(";")] if ips else []:
            if en_red(ip):
                if ip != "192.168.3.10":
                    return False
                resultado = True
        return resultado
    assert solo_10("192.168.3.10")
    assert solo_10("10.0.0.4;192.168.3.10")
    assert not solo_10("192.168.3.10;192.168.3.5")       # otra en la red: sí es conflicto
    assert not solo_10("192.168.3.5")
    assert not solo_10("10.0.0.4")
    assert not solo_10("")


# ── V20-s3-02: un fallo a mitad restaura desde el respaldo ───────────────────

def test_s3_02_paso08_respaldo_try_catch_con_restauracion_y_relanza():
    s = _cuerpo(PASO08)
    i_resp = s.index("Save-Respaldo $Paso $nuevo")
    i_try = s.index("    try {\n", i_resp)
    i_aplica = s.index("Set-NetIPInterface -InterfaceIndex $indice -AddressFamily IPv4 -Dhcp Disabled")
    i_dns = s.index("Set-DnsClientServerAddress -InterfaceIndex $indice -ResetServerAddresses")
    i_catch = s.index("} catch {", i_dns)
    assert i_resp < i_try < i_aplica < i_dns < i_catch
    catch = s[i_catch:s.index("Write-Log \"Aplicado:", i_catch)]
    i_rest = catch.index('& "$PSScriptRoot\\08_revertir_red_modulos.ps1" -WhatIf:$false')
    assert catch.index("throw", i_rest) > i_rest                    # relanza después de restaurar
    assert catch.count("throw") >= 2                                # con y sin restauración
    assert "08_revertir_red_modulos.ps1" in catch[catch.rindex("throw"):]


def test_s3_02_revertir_ultimo_recurso_dhcp_tras_quitar_las_ip():
    s = _cuerpo(REVERTIR08)
    i_flag = s.index("$quitando = $true")
    i_quita = s.index("Remove-NetIPAddress")
    assert s.index("$quitando = $false") < s.index("    try {") < i_flag < i_quita
    i_catch = s.index("    } catch {", i_quita)
    catch = s[i_catch:s.index("Remove-Item -LiteralPath (Get-RutaRespaldo $Paso)")]
    i_if = catch.index("if ($quitando) {")
    assert catch.index("Set-NetIPInterface -InterfaceIndex $indice -AddressFamily IPv4 -Dhcp Enabled", i_if) > i_if
    assert catch.index("Set-DnsClientServerAddress -InterfaceIndex $indice -ResetServerAddresses", i_if) > i_if
    assert catch.rindex("throw") > catch.index("-Dhcp Enabled")       # y relanza


def test_s3_02_red_fallo_dice_como_recuperar():
    for idioma, reparar in (("es", "Reparar"), ("en", "Repair")):
        texto = _mensaje(idioma, "RedFallo")
        assert "%1" in texto and "%2" in texto
        assert reparar in texto
        assert '-File "%2\\estacion\\08_revertir_red_modulos.ps1"' in texto
    pm = _funcion("ProbarModulo")
    assert "FmtMessage(CustomMessage('RedFallo'), [ArchivoLogEstacion,\n        ExpandConstant('{app}')])" in pm


# ── V20-s3-03: contraseña pedida y resultado distinto de ok ──────────────────

def test_s3_03_contrasena_no_cambiada_si_no_es_ok():
    assert _mensaje("es", "ModuloClaveNoCambiada") == "Contraseña web cambiada: no — repita con Reparar"
    assert _mensaje("en", "ModuloClaveNoCambiada") == "Web password changed: no — repeat with Repair"
    pm = _funcion("ProbarModulo")
    assert "ClavePedida := ConClave;" in pm
    assert pm.index("ClavePedida := ConClave;") < pm.index("EscribirArchivoClave(ArchivoClave)")
    rama = pm[pm.index("FmtMessage(CustomMessage('ModuloRes_' + Codigo), [])"):pm.index("if RedFallida then")]
    assert "if ClavePedida then" in rama
    assert "CustomMessage('ModuloClaveNoCambiada')" in rama
    # en "ok" sin cambio también se pide repetir
    assert "Reparar" in _mensaje("es", "ModuloClaveNo") and "Repair" in _mensaje("en", "ModuloClaveNo")
    ok = pm[pm.index("if Codigo = 'ok' then\n  begin"):pm.index("FmtMessage(CustomMessage('ModuloRes_ok')")]
    assert "if not ClavePedida then\n      CambioClave := CustomMessage('ModuloClaveNoPedida')" in ok


# ── V20-s3-04 / s3-06: ActiveStore y PersistentStore ─────────────────────────

def test_s3_04_consulta_del_setup_mira_los_dos_almacenes():
    cr = _funcion("ConsultarRed")
    assert "@(''ActiveStore'',''PersistentStore'')" in cr
    assert "-PolicyStore $s" in cr and "Select-Object -Unique" in cr


def test_s3_04_script_conflicto_y_la_10_en_los_dos_almacenes():
    s = _cuerpo(PASO08)
    i_conf = s.index("$conflictos = @(Get-ConflictoSubred $todas $indice)")
    previo = s[s.index("# 1. Conflicto"):i_conf]
    assert "Get-NetIPAddress -AddressFamily IPv4 -ErrorAction Stop" in previo
    assert "Get-NetIPAddress -AddressFamily IPv4 -PolicyStore PersistentStore" in previo
    # sin la .10 en la persistente: se quita de los dos almacenes y después se crea
    i_tiene = s.index("if ($tiene.Count -eq 0) {")
    bloque = s[i_tiene:s.index("Set-DnsClientServerAddress", i_tiene)]
    i_quita = bloque.index("foreach ($almacen in @('ActiveStore', 'PersistentStore'))")
    assert "Where-Object { $_.IPAddress -eq $script:IpEstacionModulos }" in bloque[i_quita:]
    assert bloque.index("Remove-NetIPAddress", i_quita) < bloque.index("New-NetIPAddress -InterfaceIndex")


# ── V20-s3-05: silencioso con el único adaptador con puerta de enlace ────────

def test_s3_05_silencioso_exige_adaptadorconfirmado():
    ini = _funcion("InitializeSetup")
    bloque = ini[ini.index("if AdvertirRed then"):ini.index("AdaptadorElegido := NormalizarMac(AdapMac[I]);")]
    assert "if WizardSilent and (Trim(ExpandConstant('{param:ADAPTADORCONFIRMADO|}')) <> '1') then" in bloque
    assert "CustomMessage('RedPerderaRedSilencioso')" in bloque
    assert bloque.index("Result := False;") < bloque.index("exit;")
    for idioma in ("es", "en"):
        assert "/ADAPTADORCONFIRMADO=1" in _mensaje(idioma, "RedPerderaRedSilencioso")
    assert "/ADAPTADORCONFIRMADO=1" in LEEME_INST and "/ADAPTADORCONFIRMADO=1" in LEEME_EST


# ── V20-s3-07: adaptadores deshabilitados ────────────────────────────────────

def test_s3_07_adaptador_deshabilitado_rechazado_con_mensaje_propio():
    vr = _funcion("ValidarRed")
    i_desh = vr.index("if AdaptadorDeshabilitado(I) then")
    assert i_desh < vr.index("for J := 0")
    assert "CustomMessage('RedAdaptadorDeshabilitado')" in vr[i_desh:vr.index("for J := 0")]
    assert "CompareText(AdapEstado[I], 'Disabled') = 0" in _funcion("AdaptadorDeshabilitado")
    assert "deshabilitado" in _mensaje("es", "RedAdaptadorDeshabilitado")
    assert "disabled" in _mensaje("en", "RedAdaptadorDeshabilitado")
    # NextButtonClick y /ADAPTADOR= pasan por ValidarRed (que lo rechaza)
    assert "ValidarRed(Indice, Advertir)" in _funcion("NextButtonClick")
    assert "ValidarRed(I, AdvertirRed)" in _funcion("InitializeSetup")


# ── V20-s3-08: riesgo documentado ────────────────────────────────────────────

def test_s3_08_exec_del_rol_sin_tope_documentado():
    i = LEEME_INST.index("V20-s3-08")
    tramo = LEEME_INST[i - 200:i + 800]
    assert "DECISIÓN SIN CONFIRMAR" in tramo and "ewWaitUntilTerminated" in tramo and "30 s" in tramo


# ── V20-s3-09: métricas y limitación de los DNS ──────────────────────────────

def test_s3_09_paso08_respalda_metricas_y_revertir_las_restaura():
    s = _cuerpo(PASO08)
    assert "MetricaAutomatica = ([string]$ipif.AutomaticMetric -eq 'Enabled')" in s
    assert "MetricaInterfaz   = [int]$ipif.InterfaceMetric" in s
    assert "Metrica = [int]$_.RouteMetric" in s
    assert "-MetricaAutomatica $antes.MetricaAutomatica -MetricaInterfaz $antes.MetricaInterfaz -Rutas $antes.Rutas" in s
    r = _cuerpo(REVERTIR08)
    assert "$ruta['RouteMetric'] = [int]$p.Metrica" in r and "New-NetRoute @ruta" in r
    assert "-AutomaticMetric Enabled" in r and "-InterfaceMetric ([int]$plan.MetricaInterfaz)" in r
    assert "Limitación de los DNS (V20-s3-09)" in LEEME_EST


# ── V20-s3-11: listas como arreglos ──────────────────────────────────────────

def test_s3_11_revertir_convierte_a_arreglo():
    r = _cuerpo(REVERTIR08)
    assert "$plan = Get-PlanRestauracion $resp" in r
    assert "$ipv4 = @($plan.IPv4)" in r and "$puertas = @($plan.Puertas)" in r and "$dns = @($plan.Dns)" in r
    puras = PURAS.read_text(encoding="ascii")
    plan = puras[puras.index("function Get-PlanRestauracion"):]
    assert "@(@($Respaldo['IPv4'])" in plan and "@(@($Respaldo['PuertasEnlace'])" in plan
    assert "@(@($Respaldo['Dns'])" in plan


# ── Funciones puras con datos ficticios ──────────────────────────────────────

def _puras(script: str):
    ruta = str(PURAS).replace("'", "''")
    orden = f"$ErrorActionPreference='Stop'; . '{ruta}'; {script}; $r | ConvertTo-Json -Depth 6 -Compress"
    salida = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", orden],
                            capture_output=True, text=True, timeout=120)
    assert salida.returncode == 0, salida.stderr
    return json.loads(salida.stdout)


ADAPTADOR = "$ad=[pscustomobject]@{Name='Ethernet';MacAddress='40-C2-BA-A6-D0-80';NdisPhysicalMedium=14;Virtual=$false;ifIndex=9}"


@CON_POWERSHELL
def test_puras_s3_11_ida_y_vuelta_json_con_una_sola_ipv4():
    """Como Save-Respaldo (ConvertTo-Json -Depth 5) y Read-Respaldo
    (ConvertFrom-Json a una tabla): una IPv4 de un solo elemento sigue siendo
    una lista y el plan de restauración tiene exactamente esa dirección."""
    r = _puras(
        ADAPTADOR + ";"
        "$resp=New-RespaldoRedModulos -Adaptador $ad -DhcpHabilitado $false "
        "-Direcciones @([pscustomobject]@{IPAddress='10.0.0.5';PrefixLength=8;PrefixOrigin='Manual'}) "
        "-PuertasEnlace @('10.0.0.1') -Dns @('8.8.8.8');"
        "$texto=$resp | ConvertTo-Json -Depth 5;"
        "$obj=$texto | ConvertFrom-Json; $tabla=@{}; foreach($p in $obj.PSObject.Properties){ $tabla[$p.Name]=$p.Value };"
        "$plan=Get-PlanRestauracion $tabla;"
        # JSON a mano con la IPv4 como objeto suelto (no arreglo): el plan la convierte igual
        "$suelto='{\"Mac\":\"40C2BAA6D080\",\"Alias\":\"Ethernet\",\"Dhcp\":false,"
        "\"IPv4\":{\"Ip\":\"10.0.0.5\",\"Prefijo\":8},\"PuertasEnlace\":\"10.0.0.1\",\"Dns\":\"8.8.8.8\"}' | ConvertFrom-Json;"
        "$t2=@{}; foreach($p in $suelto.PSObject.Properties){ $t2[$p.Name]=$p.Value };"
        "$plan2=Get-PlanRestauracion $t2;"
        "$r=@{json=($texto | ConvertFrom-Json); valida=Test-RespaldoRedModulos $tabla; n=@($plan.IPv4).Count;"
        "ip=@($plan.IPv4)[0].Ip; pref=@($plan.IPv4)[0].Prefijo; ng=@($plan.Puertas).Count; g=@($plan.Puertas)[0].Puerta;"
        "nd=@($plan.Dns).Count; valida2=Test-RespaldoRedModulos $t2; n2=@($plan2.IPv4).Count; ip2=@($plan2.IPv4)[0].Ip;"
        "ng2=@($plan2.Puertas).Count; nd2=@($plan2.Dns).Count}"
    )
    assert isinstance(r["json"]["IPv4"], list) and len(r["json"]["IPv4"]) == 1
    assert isinstance(r["json"]["PuertasEnlace"], list) and isinstance(r["json"]["Dns"], list)
    assert r["valida"] == ""
    assert (r["n"], r["ip"], r["pref"], r["ng"], r["g"], r["nd"]) == (1, "10.0.0.5", 8, 1, "10.0.0.1", 1)
    assert r["valida2"] == ""
    assert (r["n2"], r["ip2"], r["ng2"], r["nd2"]) == (1, "10.0.0.5", 1, 1)


@CON_POWERSHELL
def test_puras_s3_10_ipv4_sin_prefijo_no_lanza_con_strictmode():
    r = _puras(
        "$base=@{Mac='40C2BAA6D080';Dhcp=$false;PuertasEnlace=@();Dns=@()};"
        "$sinPref=$base.Clone(); $sinPref['IPv4']=@(('{\"Ip\":\"10.0.0.5\"}' | ConvertFrom-Json));"
        "$sinPrefTabla=$base.Clone(); $sinPrefTabla['IPv4']=@(@{Ip='10.0.0.5'});"
        "$prefTexto=$base.Clone(); $prefTexto['IPv4']=@(@{Ip='10.0.0.5';Prefijo='abc'});"
        "$prefCero=$base.Clone(); $prefCero['IPv4']=@(@{Ip='10.0.0.5';Prefijo=0});"
        "$prefBien=$base.Clone(); $prefBien['IPv4']=@(('{\"Ip\":\"10.0.0.5\",\"Prefijo\":8}' | ConvertFrom-Json));"
        "$r=@{a=Test-RespaldoRedModulos $sinPref; b=Test-RespaldoRedModulos $sinPrefTabla;"
        "c=Test-RespaldoRedModulos $prefTexto; d=Test-RespaldoRedModulos $prefCero; e=Test-RespaldoRedModulos $prefBien}"
    )
    assert r["a"] == "direccion sin Prefijo" and r["b"] == "direccion sin Prefijo"
    assert r["c"].startswith("prefijo invalido") and r["d"].startswith("prefijo invalido")
    assert r["e"] == ""


@CON_POWERSHELL
def test_puras_s3_09_metricas_en_el_respaldo_y_en_el_plan():
    r = _puras(
        ADAPTADOR + ";"
        "$resp=New-RespaldoRedModulos -Adaptador $ad -DhcpHabilitado $false -Direcciones @() "
        "-PuertasEnlace @('10.0.0.1','10.0.0.2') -Dns @() -MetricaAutomatica $false -MetricaInterfaz 25 "
        "-Rutas @(@{Puerta='10.0.0.1';Metrica=5}, @{Puerta='basura';Metrica=3}, @{Puerta='10.0.0.2';Metrica=99999});"
        "$tabla=@{}; $obj=($resp | ConvertTo-Json -Depth 5 | ConvertFrom-Json); foreach($p in $obj.PSObject.Properties){ $tabla[$p.Name]=$p.Value };"
        "$plan=Get-PlanRestauracion $tabla;"
        "$viejo=@{Mac='40C2BAA6D080';Dhcp=$true;IPv4=@();PuertasEnlace=@();Dns=@()};"
        "$planViejo=Get-PlanRestauracion $viejo;"
        "$malAuto=$resp.Clone(); $malAuto['MetricaAutomatica']='si';"
        "$malInt=$resp.Clone(); $malInt['MetricaInterfaz']=-1;"
        "$malRuta=$resp.Clone(); $malRuta['MetricasRuta']=@(@{Puerta='10.0.0.1';Metrica=70000});"
        "$malRuta2=$resp.Clone(); $malRuta2['MetricasRuta']=@(@{Puerta='10.0.0.1'});"
        "$r=@{resp=$resp; v=Test-RespaldoRedModulos $tabla; vViejo=Test-RespaldoRedModulos $viejo;"
        "puertas=@($plan.Puertas); auto=$plan.MetricaAutomatica; mi=$plan.MetricaInterfaz;"
        "autoViejo=$planViejo.MetricaAutomatica; miViejo=$planViejo.MetricaInterfaz;"
        "vMalAuto=Test-RespaldoRedModulos $malAuto; vMalInt=Test-RespaldoRedModulos $malInt;"
        "vMalRuta=Test-RespaldoRedModulos $malRuta; vMalRuta2=Test-RespaldoRedModulos $malRuta2}"
    )
    resp = r["resp"]
    assert resp["MetricaAutomatica"] is False and resp["MetricaInterfaz"] == 25
    assert resp["MetricasRuta"] == [{"Puerta": "10.0.0.1", "Metrica": 5}]     # sin la puerta inválida ni 99999
    assert r["v"] == "" and r["vViejo"] == ""
    assert r["puertas"] == [{"Puerta": "10.0.0.1", "Metrica": 5}, {"Puerta": "10.0.0.2", "Metrica": None}]
    assert r["auto"] is False and r["mi"] == 25
    assert r["autoViejo"] is None and r["miViejo"] is None                   # respaldo anterior: no se tocan
    for clave in ("vMalAuto", "vMalInt", "vMalRuta", "vMalRuta2"):
        assert r[clave] != "", clave


@CON_POWERSHELL
def test_puras_s3_04_conflicto_sin_repetir_entre_almacenes():
    r = _puras(
        "$d=@("
        "[pscustomobject]@{IPAddress='192.168.3.5';InterfaceIndex=10;InterfaceAlias='Wi-Fi'},"
        "[pscustomobject]@{IPAddress='192.168.3.5';InterfaceIndex=10;InterfaceAlias='Wi-Fi'},"
        "[pscustomobject]@{IPAddress='192.168.3.10';InterfaceIndex=12;InterfaceAlias='Ethernet 2'});"
        "$r=@{con=@(Get-ConflictoSubred $d 12)}"
    )
    assert r["con"] == ["192.168.3.5 (Wi-Fi)"]


@CON_POWERSHELL
def test_parser_sin_errores_tras_r3():
    """Solo analiza (Parser::ParseFile): no ejecuta ningún script."""
    archivos = [str(ESTACION / n) for n in ("_red_modulos_puras.ps1", "08_red_modulos.ps1",
                                            "08_revertir_red_modulos.ps1")]
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
