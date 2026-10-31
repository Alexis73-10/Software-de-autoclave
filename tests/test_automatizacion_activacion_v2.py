"""Instalación por automatización: verificador de códigos v2 (activacion_v2), despachador v1/v2 y sello.

Vectores V1-V3 / N1-N4 / N11 de fabricación del generador (tests/vectores/vectores_formato_v2.json) con el
K_t ficticio de prueba (§7.1). Los vectores INSA/REIA esperan los finales del generador (skip); la
matriz de modos se prueba con códigos reales armados por `tests/helpers/codigo_doble.construir_codigo_v2`.
"""
import hashlib
import hmac
import json
import logging
from datetime import date
from pathlib import Path

import pytest

from autoclave.installation import activacion_v2 as v2
from autoclave.installation import activation
from autoclave.installation.activacion_v2 import Modo, ResultadoCodigo
from tests.helpers.codigo_doble import K_T_PRUEBA, acepta, con_control, construir_codigo_v2, rechaza

VECTORES = json.loads((Path(__file__).parent / "vectores" / "vectores_formato_v2.json").read_text(encoding="utf-8"))
POS = {v["id"]: v for v in VECTORES["positivos"]}
NEG = {n["id"]: n for n in VECTORES["negativos"]}
AUT = VECTORES["automatizacion"]
POS_A = {v["id"]: v for v in AUT["positivos"]}
K_E = {(k["serial"], k["generacion"]): bytes.fromhex(k["k_e_hex"]) for k in VECTORES["k_e"]}
SKIP_A = pytest.mark.skip(reason="esperan vectores INSA/REIA finales del generador")

SERIE = "ab-12 34"
MODELO = "Tuttnauer  2540 eka"
HOY = date(2026, 11, 5)


@pytest.fixture(autouse=True)
def _transporte_aislado(monkeypatch, tmp_path):
    monkeypatch.setenv("ESPECIFIKA_TRANSPORTE", str(tmp_path / "no_existe" / "activacion_v2.json"))
    v2.configurar_transporte(K_T_PRUEBA)
    yield
    v2.configurar_transporte(None)


def _f(iso):
    return date.fromisoformat(iso)


def _verificar(serial, codigo, modo=Modo.FABRICACION, *args, **kw):
    return v2.verificar_codigo_instalacion(serial, codigo, modo, *args, **kw)


def _ins(auto=False, **kw):
    """INS (o INSA) de SN260001 válido del 2026-11-03 al 2026-11-09."""
    base = dict(permanente=False, ventana=date(2026, 11, 3), P=60, G=10, orig=None, emerg=0)
    base.update(kw)
    return construir_codigo_v2("SN260001", K_E[("SN260001", 1)],
                               originales=(SERIE, MODELO) if auto else None, **base)


# ── constructor local = generador (V1-V3) ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("id_", ["V1", "V2", "V3"])
def test_constructor_reproduce_los_vectores_del_generador(id_):
    v = POS[id_]
    codigo = construir_codigo_v2(v["serial"], K_E[(v["serial"], v["generacion"])], permanente=v["permanente"],
                                 ventana=_f(v["ventana"]), P=v["P"], G=v["G"],
                                 orig=_f(v["orig"]) if v["orig"] else None, emerg=v["emerg"], agrupar=True)
    assert codigo == v["codigo"]


# ── fabricación v2: V1-V3 y N1-N4, N11 ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("id_", ["V1", "V2", "V3"])
def test_vectores_positivos_fabricacion(id_):
    v = POS[id_]
    for dia in (v["acepta_desde"], v["acepta_hasta"]):
        r = _verificar(v["serial"], v["codigo"], hoy=_f(dia))
        assert r == ResultadoCodigo(ok=True, motivo=None, formato="v2", tipo=v["tipo"], originales=None)


def test_codigo_con_minusculas_espacios_y_confusiones_se_normaliza():
    v = POS["V1"]
    tecleado = v["codigo"].lower().replace("-", " ").replace("o", "0").replace("i", "1").replace("b", "8")
    assert _verificar(v["serial"], tecleado, hoy=_f(v["acepta_desde"])).ok


def test_serial_en_minusculas_se_canoniza():
    assert _verificar("sn260001", POS["V1"]["codigo"], hoy=_f("2026-11-03")).ok


@pytest.mark.parametrize("id_", ["N1a", "N1b"])
def test_n1_fuera_de_ventana(id_):
    r = _verificar("SN260001", POS["V1"]["codigo"], hoy=_f(NEG[id_]["fecha"]))
    assert (r.ok, r.motivo, r.formato) == (False, "ventana", "v2")


def test_n2_serial_equivocado_es_etiqueta():
    r = _verificar(NEG["N2"]["serial"], POS["V1"]["codigo"], hoy=_f(NEG["N2"]["fecha"]))
    assert (r.ok, r.motivo) == (False, "etiqueta")


@pytest.mark.parametrize("id_", ["N3", "N4"])
def test_n3_n4_error_de_digitacion(id_):
    r = _verificar("SN260002", NEG[id_]["codigo"], hoy=_f(NEG[id_]["fecha"]))
    assert (r.ok, r.motivo) == (False, "digitacion")


def test_n11_version_distinta_de_cero_es_formato():
    cuerpo = POS["V1"]["codigo"].replace("-", "")[:-1]
    # versión 1 con el tipo INS: carácter de cabecera = (1 << 3) | 1 = 9 -> 'J'
    alterado = con_control("J" + cuerpo[1:])
    r = _verificar("SN260001", alterado, hoy=_f("2026-11-04"))
    assert (r.ok, r.motivo) == (False, "formato")


@pytest.mark.parametrize("cab", ["A", "D", "E", "F", "G", "H"])
def test_cabecera_de_otro_tipo_es_tipo(cab):
    # SOL, FIN, EMG, EXT y los tipos 6 y 7 sin asignar (versión 0), con control válido
    cuerpo = POS["V1"]["codigo"].replace("-", "")[:-1]
    r = _verificar("SN260001", con_control(cab + cuerpo[1:]), hoy=_f("2026-11-04"))
    assert (r.ok, r.motivo) == (False, "tipo")


def test_rango_invalido_con_etiqueta_correcta():
    # P = 0 en licencia no permanente: etiqueta válida (la firma el emisor) pero regla de rango incumplida
    codigo = construir_codigo_v2("SN260001", K_E[("SN260001", 1)], permanente=False, ventana=date(2026, 11, 3),
                                 P=0, G=0, orig=None, emerg=0)
    r = _verificar("SN260001", codigo, hoy=HOY)
    assert (r.ok, r.motivo) == (False, "rango")


# ── despachador por longitud ─────────────────────────────────────────────────────────────────────────

def _v1():
    return activation.generate_installation_code("SN260001", HOY)


def _no_llamar(*args):
    raise AssertionError("no debe llamarse")


def test_v1_valido_en_fabricacion_pasa_como_hoy():
    r = _verificar("SN260001", _v1(), hoy=HOY)
    assert r == ResultadoCodigo(ok=True, motivo=None, formato="v1", tipo=None, originales=None)
    assert _verificar("SN260001", _v1(), hoy=date(2026, 11, 6)).motivo == "v1_invalido"


def test_v1_con_guiones_y_minusculas_pasa():
    c = _v1()
    tecleado = f"{c[:4]}-{c[4:8]}-{c[8:]}".lower()
    assert _verificar("SN260001", tecleado, hoy=HOY).ok


def test_v1_fabricacion_llama_al_validador_inyectado_con_hoy():
    llamadas = []

    def validador(serial, codigo, hoy):
        llamadas.append((serial, codigo, hoy))
        return True

    r = _verificar("SN260001", "ABCD-EFGH-IJKL", hoy=HOY, validar_v1=validador)
    assert r.ok and r.formato == "v1"
    assert llamadas == [("SN260001", "ABCD-EFGH-IJKL", HOY)]


def test_v1_en_automatizacion_no_llama_al_validador():
    r = _verificar("SN260001", _v1(), Modo.AUTOMATIZACION, SERIE, MODELO, hoy=HOY, validar_v1=_no_llamar)
    assert (r.ok, r.motivo, r.formato) == (False, "v1_en_automatizacion", "v1")


@pytest.mark.parametrize("n", [1, 11, 13, 47, 49, 60])
def test_longitudes_distintas_de_12_y_48_son_formato(n):
    for modo in Modo:
        r = _verificar("SN260001", "A" * n, modo, SERIE, MODELO, hoy=HOY, validar_v1=_no_llamar)
        assert (r.ok, r.motivo, r.formato) == (False, "formato", None)


def test_v1_valido_con_sufijo_ya_no_pasa():
    # activation.py:114 (v1) lo aceptaba por el [:12]; el despachador exige longitud exacta
    r = _verificar("SN260001", _v1() + "AA", hoy=HOY)
    assert (r.ok, r.motivo) == (False, "formato")


def test_doce_caracteres_con_un_nueve_es_formato():
    r = _verificar("SN260001", "ABCDEFGHIJK9", hoy=HOY, validar_v1=_no_llamar)
    assert (r.ok, r.motivo) == (False, "formato")


def test_vacio_y_none_son_formato():
    assert _verificar("SN260001", "", hoy=HOY).motivo == "formato"
    assert _verificar("SN260001", None, hoy=HOY).motivo == "formato"


def test_cuarenta_y_ocho_con_caracter_fuera_del_alfabeto_es_formato():
    codigo = POS["V1"]["codigo"].replace("-", "")[:-1] + "9"
    assert _verificar("SN260001", codigo, hoy=_f("2026-11-04")).motivo == "formato"


# ── serial y transporte ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("serial", ["ABC123", "SN12345", "SN1234567", "SNAA1234", "", "SN 260001x"])
def test_serial_que_no_es_sn_mas_seis_digitos_con_v2(serial):
    r = _verificar(serial, POS["V1"]["codigo"], hoy=_f("2026-11-03"))
    assert (r.ok, r.motivo, r.formato) == (False, "serial_formato", "v2")


def test_serial_libre_sigue_valido_con_v1():
    c = activation.generate_installation_code("ABC123", HOY)
    assert _verificar("ABC123", c, hoy=HOY).ok


def test_sin_transporte_v2_falla_cerrado_y_v1_intacto(caplog):
    v2.configurar_transporte(b"")
    with caplog.at_level(logging.ERROR, logger=v2.logger.name):
        r = _verificar("SN260001", POS["V1"]["codigo"], hoy=_f("2026-11-03"))
    assert (r.ok, r.motivo, r.formato) == (False, "sin_transporte", "v2")
    assert any("transporte" in m for m in caplog.messages)
    assert _verificar("SN260001", _v1(), hoy=HOY).ok            # v1 como siempre
    assert _verificar("SN260001", _v1(), Modo.AUTOMATIZACION, SERIE, MODELO, hoy=HOY).motivo == "v1_en_automatizacion"
    assert not v2.transporte_disponible()


def test_sin_transporte_automatizacion_tambien_falla_cerrado():
    v2.configurar_transporte(b"")
    r = _verificar("SN260001", _ins(True), Modo.AUTOMATIZACION, SERIE, MODELO, hoy=HOY)
    assert (r.ok, r.motivo) == (False, "sin_transporte")


def test_k_t_explicito_prevalece_sobre_el_cache():
    v2.configurar_transporte(b"")
    assert _verificar("SN260001", POS["V1"]["codigo"], hoy=_f("2026-11-03"), k_t=K_T_PRUEBA).ok
    assert _verificar("SN260001", POS["V1"]["codigo"], hoy=_f("2026-11-03"), k_t=bytes(32)).motivo == "etiqueta"


def test_carga_perezosa_desde_archivo_y_aviso_una_sola_vez(monkeypatch, tmp_path, caplog):
    ruta = tmp_path / "activacion_v2.json"
    ruta.write_text(json.dumps({"version": 2, "transporte": K_T_PRUEBA.hex(), "huella_maestro": "00000000"}))
    monkeypatch.setenv("ESPECIFIKA_TRANSPORTE", str(ruta))
    v2.configurar_transporte(None)
    assert _verificar("SN260001", POS["V1"]["codigo"], hoy=_f("2026-11-03")).ok
    # sin archivo: una sola advertencia
    monkeypatch.setenv("ESPECIFIKA_TRANSPORTE", str(tmp_path / "nada.json"))
    v2.configurar_transporte(None)
    with caplog.at_level(logging.WARNING, logger=v2.logger.name):
        for _ in range(3):
            assert _verificar("SN260001", POS["V1"]["codigo"], hoy=_f("2026-11-03")).motivo == "sin_transporte"
    assert sum("sin transporte" in m for m in caplog.messages) == 1


def test_configurar_transporte_rechaza_largo_incorrecto():
    with pytest.raises(ValueError):
        v2.configurar_transporte(b"corto")


def test_el_cache_v2_no_comparte_estado_con_el_v1():
    activation.configurar_secretos()          # olvida los secretos v1
    assert v2.transporte_disponible()
    v2.configurar_transporte(b"")
    activation.configurar_secretos(b"i" * 32, b"f" * 32)
    assert not v2.transporte_disponible() and activation.secretos_disponibles()


# ── automatización: INSA / REIA con códigos armados en la prueba ──────────────────────────────────────

def test_insa_valida_solo_en_automatizacion_con_los_mismos_originales():
    codigo = _ins(auto=True)
    r = _verificar("SN260001", codigo, Modo.AUTOMATIZACION, SERIE, MODELO, hoy=HOY)
    assert r.ok and r.formato == "v2" and r.tipo == "INS"
    assert r.originales == ("AB-1234", "TUTTNAUER 2540 EKA")
    # los mismos originales tecleados de otro modo (normalización) también valen
    assert _verificar("SN260001", codigo, Modo.AUTOMATIZACION, "AB-1234", "tuttnauer 2540 eka", hoy=HOY).ok
    # un INSA no valida en fabricación (ni con originales ignorados)
    r = _verificar("SN260001", codigo, Modo.FABRICACION, SERIE, MODELO, hoy=HOY)
    assert (r.ok, r.motivo) == (False, "etiqueta")


def test_ins_no_valida_en_automatizacion_y_viceversa():
    ins = _ins()
    assert _verificar("SN260001", ins, Modo.FABRICACION, hoy=HOY).ok
    r = _verificar("SN260001", ins, Modo.AUTOMATIZACION, SERIE, MODELO, hoy=HOY)
    assert (r.ok, r.motivo) == (False, "etiqueta")


@pytest.mark.parametrize("serie,modelo", [("AB-1235", MODELO), (SERIE, "Tuttnauer 2540 ek"), ("X", "Y")])
def test_insa_con_otros_originales_es_etiqueta(serie, modelo):
    r = _verificar("SN260001", _ins(auto=True), Modo.AUTOMATIZACION, serie, modelo, hoy=HOY)
    assert (r.ok, r.motivo) == (False, "etiqueta")


def test_reia_matriz_con_rei():
    k_e = K_E[("SN260002", 2)]
    kw = dict(permanente=False, ventana=date(2027, 2, 1), P=90, G=10, orig=date(2026, 11, 5), emerg=1)
    reia = construir_codigo_v2("SN260002", k_e, originales=(SERIE, MODELO), **kw)
    rei = construir_codigo_v2("SN260002", k_e, **kw)
    hoy = date(2027, 2, 3)
    assert _verificar("SN260002", reia, Modo.AUTOMATIZACION, SERIE, MODELO, hoy=hoy).tipo == "REI"
    assert _verificar("SN260002", rei, Modo.FABRICACION, hoy=hoy).tipo == "REI"
    assert _verificar("SN260002", reia, Modo.FABRICACION, hoy=hoy).motivo == "etiqueta"
    assert _verificar("SN260002", rei, Modo.AUTOMATIZACION, SERIE, MODELO, hoy=hoy).motivo == "etiqueta"
    assert _verificar("SN260001", reia, Modo.AUTOMATIZACION, SERIE, MODELO, hoy=hoy).motivo == "etiqueta"


def test_insa_fuera_de_ventana():
    r = _verificar("SN260001", _ins(auto=True), Modo.AUTOMATIZACION, SERIE, MODELO, hoy=date(2026, 11, 10))
    assert (r.ok, r.motivo) == (False, "ventana")


def test_originales_invalidos_dan_su_propio_motivo():
    codigo = _ins(auto=True)
    casos = [("", MODELO, "serie_original"), (None, MODELO, "serie_original"), ("AB|12", MODELO, "serie_original"),
             ("ÁB12", MODELO, "serie_original"), ("x" * 41, MODELO, "serie_original"),
             (SERIE, "   ", "modelo_original"), (SERIE, None, "modelo_original"),
             (SERIE, "Modelo|X", "modelo_original"), (SERIE, "m" * 81, "modelo_original")]
    for serie, modelo, motivo in casos:
        r = _verificar("SN260001", codigo, Modo.AUTOMATIZACION, serie, modelo, hoy=HOY)
        assert (r.ok, r.motivo, r.formato) == (False, motivo, "v2"), (serie, modelo)


def test_originales_invalidos_se_ignoran_en_fabricacion():
    r = _verificar("SN260001", POS["V1"]["codigo"], Modo.FABRICACION, "AB|12", "", hoy=_f("2026-11-03"))
    assert r.ok and r.originales is None


@pytest.mark.parametrize("modo", ["fabricacion", "automatizacion"])
def test_modo_acepta_su_valor_de_texto(modo):
    assert Modo(modo).value == modo and Modo(modo) == modo


# vectores finales de automatización del generador (VA1-VA3, NA1-NA7): esperan la versión final
@SKIP_A
@pytest.mark.parametrize("id_", ["VA1", "VA2", "VA3"])
def test_vectores_positivos_automatizacion(id_):
    v = POS_A[id_]
    r = _verificar(v["serial"], v["codigo"], Modo.AUTOMATIZACION, v["serie_tecleada"], v["modelo_tecleado"],
                   hoy=_f(v["acepta_desde"]))
    assert r.ok and r.originales == (v["serie_n"], v["modelo_n"])
    # y el código de fabricación con los mismos campos no vale como INSA
    r = _verificar(v["serial"], v["codigo_fabricacion_mismos_campos"], Modo.AUTOMATIZACION,
                   v["serie_tecleada"], v["modelo_tecleado"], hoy=_f(v["acepta_desde"]))
    assert r.motivo == "etiqueta"


@SKIP_A
@pytest.mark.parametrize("id_", ["NA1", "NA2", "NA3", "NA4", "NA5", "NA6", "NA7"])
def test_vectores_negativos_automatizacion(id_):
    n = next(x for x in AUT["negativos"] if x["id"] == id_)
    base = POS_A.get(n["base"]) or POS[n["base"]]
    codigo = n.get("codigo") or base["codigo"]
    serial = n.get("serial") or base["serial"]
    orig = n.get("originales")
    if orig is None and n["base"].startswith("VA"):
        orig = None                      # NA1 y NA6: verificado sin originales (modo fabricación)
    modo = Modo.AUTOMATIZACION if orig else Modo.FABRICACION
    r = _verificar(serial, codigo, modo, *(orig or (None, None)), hoy=_f(n["fecha"]))
    assert (r.ok, r.motivo) == (False, n["esperado"])


@SKIP_A
@pytest.mark.parametrize("i", range(5))
def test_normalizacion_de_originales_contra_el_generador(i):
    n = AUT["normalizacion"][i]
    assert v2.normalizar_originales(n["serie_tecleada"], n["modelo_tecleado"]) == (n["serie_n"], n["modelo_n"])
    assert v2.huella_originales(n["serie_tecleada"], n["modelo_tecleado"]) == n["h_orig"]


@SKIP_A
@pytest.mark.parametrize("r", AUT["rechazos_normalizacion"], ids=lambda r: r["id"])
def test_rechazos_de_normalizacion_contra_el_generador(r):
    with pytest.raises(v2.OriginalInvalido) as e:
        v2.normalizar_originales(r["serie_tecleada"], r["modelo_tecleado"])
    assert e.value.campo == r["campo"]


# ── sello de identidad ───────────────────────────────────────────────────────────────────────────────

def _perfil(**kw):
    d = {"tipo_instalacion": "automatizacion", "serial_number": "SN260001", "serial_original": "AB-1234",
         "modelo_original": "TUTTNAUER 2540 EKA"}
    d.update(kw)
    d["sello_identidad"] = v2.sellar_identidad(
        d["tipo_instalacion"], d["serial_number"], d["serial_original"], d["modelo_original"])
    return d


def test_sello_es_hex_de_64_determinista_y_verifica():
    p = _perfil()
    assert len(p["sello_identidad"]) == 64 and int(p["sello_identidad"], 16) >= 0
    assert p["sello_identidad"] == v2.sellar_identidad("automatizacion", "SN260001", "AB-1234", "TUTTNAUER 2540 EKA")
    assert v2.verificar_sello_identidad(p)
    assert v2.verificar_sello_identidad(p, k_t=K_T_PRUEBA)


def test_sello_sigue_la_definicion_del_diseno():
    k_p = hmac.new(K_T_PRUEBA, b"ESPK2|AUTOCLAVE|PERFIL", hashlib.sha256).digest()
    esperado = hmac.new(k_p, b"1|automatizacion|SN260001|AB-1234|TUTTNAUER 2540 EKA", hashlib.sha256).hexdigest()
    assert _perfil()["sello_identidad"] == esperado


@pytest.mark.parametrize("campo,valor", [("tipo_instalacion", "fabricacion"), ("serial_number", "SN260002"),
                                         ("serial_original", "AB-1235"), ("modelo_original", "TUTTNAUER 2540 EK")])
def test_sello_detecta_cualquier_alteracion(campo, valor):
    p = _perfil()
    p[campo] = valor
    assert not v2.verificar_sello_identidad(p)


def test_sello_alterado_o_ausente_o_mal_tipado():
    p = _perfil()
    assert not v2.verificar_sello_identidad({**p, "sello_identidad": "0" * 64})
    assert not v2.verificar_sello_identidad({**p, "sello_identidad": p["sello_identidad"].upper()})
    assert not v2.verificar_sello_identidad({k: v for k, v in p.items() if k != "sello_identidad"})
    assert not v2.verificar_sello_identidad({k: v for k, v in p.items() if k != "serial_original"})
    assert not v2.verificar_sello_identidad({**p, "modelo_original": None})
    assert not v2.verificar_sello_identidad({**p, "sello_identidad": "é" * 64})
    assert not v2.verificar_sello_identidad(None)


def test_sello_con_otro_k_t_no_verifica():
    assert not v2.verificar_sello_identidad(_perfil(), k_t=bytes(32))


def test_sello_sin_transporte_falla_cerrado():
    p = _perfil()
    v2.configurar_transporte(b"")
    assert not v2.verificar_sello_identidad(p)
    with pytest.raises(v2.TransporteNoDisponible):
        v2.sellar_identidad("automatizacion", "SN260001", "A", "B")
    assert v2.sellar_identidad("automatizacion", "SN260001", "A", "B", k_t=K_T_PRUEBA)


# ── doble de verificador ─────────────────────────────────────────────────────────────────────────────

def test_dobles_tienen_la_firma_del_verificador_real():
    ok = acepta(Modo.AUTOMATIZACION, ("S", "M"))
    r = ok("SN260001", "x", Modo.AUTOMATIZACION, "a", "b", hoy=HOY, k_t=None, validar_v1=None)
    assert r == ResultadoCodigo(ok=True, formato="v2", tipo="INS", originales=("S", "M"))
    assert ok.llamadas[0]["serie_original"] == "a"
    no = rechaza("etiqueta")
    r = no("SN260001", "x")
    assert (r.ok, r.motivo) == (False, "etiqueta")
    # acepta() sin modo toma el de la llamada; en fabricación no devuelve originales
    libre = acepta()
    assert libre("S", "c", Modo.AUTOMATIZACION, "AB", "MO").originales == ("AB", "MO")
    assert libre("S", "c", Modo.FABRICACION, "AB", "MO").originales is None
