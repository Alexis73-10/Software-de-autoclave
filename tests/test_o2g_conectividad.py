# tests/test_o2g_conectividad.py
#
# O2g (tanda 6): Conectividad. Red en solo lectura, correo de ciclos
# (destinatarios, interruptor, correo de prueba). Sin red ni SMTP reales:
# dobles para psutil/netsh y para el envío. La contraseña nunca sale.

import json
from unittest.mock import MagicMock

import pytest

from autoclave.core.runtime import estado_red as er
from autoclave.core.runtime.config_correo_equipo import ConfigCorreoEquipo, ErrorCorreo, normalizar
from tests.helpers.backend_doble import modulo_backend

NETSH_ES = """
Hay 1 interfaz en el sistema:

    Nombre                 : Wi-Fi
    Estado                 : conectado
    SSID                   : Especifika-Planta
    BSSID                  : aa:bb:cc:dd:ee:ff
    Señal                  : 82%
"""
NETSH_EN = """    Name                   : Wi-Fi
    State                  : connected
    SSID                   : Lab
    Signal                 : 40%
"""


def test_netsh_es_en_y_desconectado():
    assert er.interpretar_netsh(NETSH_ES) == {"ssid": "Especifika-Planta", "senal": 82, "conectado": True}
    assert er.interpretar_netsh(NETSH_EN)["senal"] == 40
    d = er.interpretar_netsh("    State : disconnected\n")
    assert d == {"ssid": None, "senal": None, "conectado": False}
    assert er.interpretar_netsh("")["conectado"] is False


def test_estado_red_cache_y_fallos():
    llamadas = []
    t = [0.0]

    def adaptadores():
        llamadas.append(1)
        return [{"nombre": "Ethernet", "conectado": True, "ipv4": "192.168.1.20",
                 "velocidad_mbps": 1000, "tipo": "ethernet"}]
    red = er.EstadoRed(adaptadores=adaptadores, netsh=lambda: NETSH_ES, reloj=lambda: t[0])
    d = red.leer()
    assert d["conectado"] and d["wifi"]["ssid"] == "Especifika-Planta" and d["editable"] is False
    red.leer()
    assert len(llamadas) == 1
    t[0] = er.CACHE_S + 1
    red.leer()
    assert len(llamadas) == 2

    def falla():
        raise OSError("x")
    d = er.EstadoRed(adaptadores=falla, netsh=falla).leer()
    assert d["adaptadores"] == [] and d["wifi"]["conectado"] is False and d["conectado"] is False


def test_tipo_de():
    assert er.tipo_de("Wi-Fi") == "wifi" and er.tipo_de("Ethernet 2") == "ethernet"


def test_config_correo_semilla_y_guardar(tmp_path):
    semilla = [{"nombre": "Admin", "correo": "a@b.co"}]
    c = ConfigCorreoEquipo(tmp_path / "c.json", semilla=lambda: semilla)
    assert c.leer() == {"envio_activo": True, "destinatarios": semilla, "personalizado": False}
    c.guardar(False, [{"nombre": "", "correo": "x@y.com"}])
    d = c.leer()
    assert d["envio_activo"] is False and d["destinatarios"] == [{"nombre": "x@y.com", "correo": "x@y.com"}]


@pytest.mark.parametrize("lista,codigo", [
    ([{"correo": "no-es-correo"}], "correo_invalido"),
    ([{"correo": "a@b.co"}, {"correo": "A@B.co"}], "duplicado"),
    ([{"correo": f"u{i}@b.co"} for i in range(11)], "demasiados"),
    ([{"nombre": "x" * 41, "correo": "a@b.co"}], "nombre_largo"),
    ("a@b.co", "validacion"),
])
def test_normalizar_rechaza(lista, codigo):
    with pytest.raises(ErrorCorreo) as e:
        normalizar(lista)
    assert e.value.codigo == codigo


def test_historial_usa_destinatarios_del_equipo(tmp_path, monkeypatch):
    """El envío del Historial toma los destinatarios guardados y respeta el interruptor."""
    from autoclave.ui_qml.exportacion import config_correo
    base = tmp_path / "correo.json"
    base.write_text(json.dumps({"remitente": "r@x.co", "servidor_smtp": "smtp.x.co", "puerto": 587,
                                "destinos": [{"nombre": "F", "correo": "f@x.co"}]}), encoding="utf-8")
    equipo = tmp_path / "correo_equipo.json"
    c = config_correo.cargar(base, contrasena=lambda r: "secreta", ruta_equipo=equipo)
    assert c.destinos == [{"nombre": "F", "correo": "f@x.co"}] and c.configurado
    ConfigCorreoEquipo(equipo).guardar(True, [{"nombre": "N", "correo": "n@x.co"}])
    c = config_correo.cargar(base, contrasena=lambda r: "secreta", ruta_equipo=equipo)
    assert c.destinos == [{"nombre": "N", "correo": "n@x.co"}]
    ConfigCorreoEquipo(equipo).guardar(False, [{"nombre": "N", "correo": "n@x.co"}])
    c = config_correo.cargar(base, contrasena=lambda r: "secreta", ruta_equipo=equipo)
    assert c.configurado is False and c.envio_activo is False


# ── API ─────────────────────────────────────────────────────────────────────

@pytest.fixture
def api(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from autoclave.services.domain.logging.db_manager import DbManager
    from autoclave.state_machine.machine.enum_global import GlobalState
    from autoclave.ui_qml.exportacion.config_correo import ConfigCorreo
    from tests.helpers.backend_doble import cabecera, cargar_servidor
    ctx = MagicMock()
    ctx.db = DbManager(db_path=tmp_path / "t.db")
    ctx.sin_base_de_datos = False
    ctx.config_correo_equipo = ConfigCorreoEquipo(
        tmp_path / "ce.json", semilla=lambda: [{"nombre": "Admin", "correo": "a@b.co"}])
    ctx.estado_red = er.EstadoRed(adaptadores=lambda: [], netsh=lambda: NETSH_EN)
    srv, _ = cargar_servidor(ctx)
    ctx.estado.get_machine_state.return_value = GlobalState.PREPARADO
    enviados = []
    monkeypatch.setattr(modulo_backend("rutas.reportes"), "_cargar_config_correo", lambda: ConfigCorreo(
        remitente="r@x.co", servidor="smtp.x.co", puerto=587,
        destinos=ctx.config_correo_equipo.leer()["destinatarios"], contrasena="SECRETA-123",
        envio_activo=ctx.config_correo_equipo.leer()["envio_activo"]))
    monkeypatch.setattr(modulo_backend("rutas.reportes"), "_enviar_correo", lambda config, mensaje: enviados.append(mensaje))
    yield TestClient(srv.app), srv, ctx, cabecera, enviados
    ctx.db.close()


ROLES = ["operador", "admin", "tecnico", "ingeniero"]
LECTURA = {"operador": 403, "admin": 200, "tecnico": 200, "ingeniero": 200}
ESCRITURA = {"operador": 403, "admin": 200, "tecnico": 403, "ingeniero": 200}


@pytest.mark.parametrize("rol", ROLES)
def test_matriz_lectura(api, rol):
    client, srv, ctx, cab, _ = api
    r = client.get("/email/config", headers=cab(srv, rol))
    assert r.status_code == LECTURA[rol]
    if r.status_code == 200:
        texto = json.dumps(r.json())
        assert "SECRETA" not in texto and "contrasena\"" not in texto
        assert r.json()["contrasena_configurada"] is True
    assert client.get("/network/status", headers=cab(srv, rol)).status_code == LECTURA[rol]


@pytest.mark.parametrize("rol", ROLES)
def test_matriz_escritura(api, rol):
    client, srv, ctx, cab, enviados = api
    cuerpo = {"envio_activo": True, "destinatarios": [{"nombre": "N", "correo": "n@x.co"}]}
    r = client.put("/email/config", json=cuerpo, headers=cab(srv, rol))
    assert r.status_code == ESCRITURA[rol]
    guardados = ctx.config_correo_equipo.leer()["destinatarios"]
    if r.status_code == 200:
        assert guardados == cuerpo["destinatarios"]
        fila = ctx.db.get_auditoria(evento="correo_configurado")[0]
        assert fila["usuario"] == f"usuario_{rol}"
    else:
        assert guardados == [{"nombre": "Admin", "correo": "a@b.co"}]
    r = client.post("/email/test", headers=cab(srv, rol))
    assert r.status_code == ESCRITURA[rol]
    assert len(enviados) == (1 if ESCRITURA[rol] == 200 else 0)


def test_sin_token_401(api):
    client, *_ = api
    assert client.get("/email/config").status_code == 401
    assert client.put("/email/config", json={"envio_activo": True, "destinatarios": []}).status_code == 401
    assert client.post("/email/test").status_code == 401
    assert client.get("/network/status").status_code == 401


def test_validacion_422(api):
    client, srv, ctx, cab, _ = api
    h = cab(srv, "admin")
    r = client.put("/email/config", json={"envio_activo": True,
                                          "destinatarios": [{"correo": "malo"}]}, headers=h)
    assert r.status_code == 422 and r.json()["codigo"] == "correo_invalido"
    r = client.put("/email/config", json={"envio_activo": "si", "destinatarios": []}, headers=h)
    assert r.status_code == 422


def test_409_en_ciclo(api):
    from autoclave.state_machine.machine.enum_global import GlobalState
    client, srv, ctx, cab, _ = api
    ctx.estado.get_machine_state.return_value = GlobalState.CICLO
    r = client.put("/email/config", json={"envio_activo": False, "destinatarios": []},
                   headers=cab(srv, "ingeniero"))
    assert r.status_code == 409


def test_prueba_va_a_los_guardados_sin_bitacora(api):
    client, srv, ctx, cab, enviados = api
    h = cab(srv, "ingeniero")
    client.put("/email/config", json={"envio_activo": True, "destinatarios": [
        {"nombre": "A", "correo": "a@x.co"}, {"nombre": "B", "correo": "b@x.co"}]}, headers=h)
    r = client.post("/email/test", headers=h)
    assert r.status_code == 200 and r.json()["enviados"] == 2
    assert sorted(m["To"] for m in enviados) == ["a@x.co", "b@x.co"]
    assert "SECRETA" not in str(enviados[0])
    assert not ctx.db.get_auditoria(evento="correo_prueba")   # D9-6 (tanda 9): solo log


def test_prueba_rechazos(api, monkeypatch):
    client, srv, ctx, cab, enviados = api
    h = cab(srv, "admin")
    client.put("/email/config", json={"envio_activo": False, "destinatarios": [
        {"nombre": "A", "correo": "a@x.co"}]}, headers=h)
    r = client.post("/email/test", headers=h)
    assert r.status_code == 409 and r.json()["codigo"] == "envio_desactivado"
    client.put("/email/config", json={"envio_activo": True, "destinatarios": []}, headers=h)
    assert client.post("/email/test", headers=h).json()["codigo"] == "sin_destinatarios"
    client.put("/email/config", json={"envio_activo": True, "destinatarios": [
        {"nombre": "A", "correo": "a@x.co"}]}, headers=h)

    def falla(config, mensaje):
        raise OSError("SECRETA-123 conexión rechazada")
    monkeypatch.setattr(modulo_backend("rutas.reportes"), "_enviar_correo", falla)
    r = client.post("/email/test", headers=h)
    assert r.status_code == 502 and r.json()["codigo"] == "envio_fallido"
    assert "SECRETA" not in r.text


def test_red_solo_lectura(api):
    client, srv, ctx, cab, _ = api
    d = client.get("/network/status", headers=cab(srv, "tecnico")).json()
    assert d["editable"] is False and d["wifi"]["ssid"] == "Lab"
    assert client.put("/network/status", json={}, headers=cab(srv, "ingeniero")).status_code == 405


# ── UI ──────────────────────────────────────────────────────────────────────

def test_motivo_destinatarios():
    from autoclave.ui_qml.domain.permisos_opciones import motivo_destinatarios
    assert motivo_destinatarios("admin", "PREPARADO") == ""
    assert motivo_destinatarios("ingeniero", "PREPARADO") == ""
    assert motivo_destinatarios("tecnico", "PREPARADO") == "rol"
    assert motivo_destinatarios("operador", "PREPARADO") == "rol"
    assert motivo_destinatarios("admin", "CICLO") == "ciclo"


CORREO = {"envio_activo": True, "destinatarios": [{"nombre": "Administrativo", "correo": "adm@x.co"},
                                                   {"nombre": "Mantenimiento", "correo": "mant@x.co"}],
          "remitente": "equipo@x.co", "servidor": "smtp.x.co", "puerto": 587,
          "contrasena_configurada": True, "max_destinatarios": 10}
RED = {"adaptadores": [{"nombre": "Wi-Fi", "conectado": True, "ipv4": "192.168.0.40",
                        "velocidad_mbps": 144, "tipo": "wifi"},
                       {"nombre": "Ethernet", "conectado": False, "ipv4": None,
                        "velocidad_mbps": None, "tipo": "ethernet"}],
       "wifi": {"ssid": "Especifika-Planta", "senal": 82, "conectado": True},
       "conectado": True, "editable": False}
RUTAS = {"GET /email/config": [200, CORREO], "GET /network/status": [200, RED],
         "PUT /email/config": [200, dict(CORREO, destinatarios=CORREO["destinatarios"][:1])],
         "POST /email/test": [200, {"ok": True, "enviados": 2}]}

PASOS = r'''
raiz.setProperty("seccionActiva", "conectividad"); esperar(400)
p = buscar("opcionesConectividad")
ctrl = p.findChild(QObject, "conectividadController")
salida["editable"] = p.property("editable")
salida["dest"] = sum(1 for i in range(5) if buscar("destinatario_%d" % i, p) is not None)
salida["agregar"] = buscar("botonAgregarDestinatario", p).property("habilitado")
salida["prueba"] = buscar("botonCorreoPrueba", p).property("habilitado")
salida["aviso"] = buscar("avisoSoloLecturaCorreo", p).isVisible()
salida["textos"] = textos(p)
capturar("O2g_" + cfg["rol"] + ".png")
if salida["editable"]:
    salida["quitar"] = ctrl.quitar(1); esperar()
    salida["tras_quitar"] = len(ctrl.property("destinatarios"))
    salida["envio"] = ctrl.enviarPrueba(); esperar()
    salida["msg"] = ctrl.property("mensaje")
    capturar("O2g_" + cfg["rol"] + "_prueba.png")
'''


@pytest.mark.parametrize("rol,editable", [("admin", True), ("ingeniero", True), ("tecnico", False)])
def test_pantalla_por_rol(rol, editable):
    pytest.importorskip("PySide6")
    from tests.banco.opciones_qml_banco import correr, quieren_capturas
    d = correr(rol, PASOS, RUTAS, capturas=quieren_capturas() and rol != "ingeniero")
    assert d["avisos"] == []
    assert d["editable"] is editable and d["dest"] == 2
    assert d["agregar"] is False          # el banco no tiene teclado
    assert d["prueba"] is editable and d["aviso"] is (not editable)
    assert not any("SECRETA" in (t or "") for t in d["textos"])
    assert "Especifika-Planta · 82 %" in d["textos"] or any("Especifika-Planta" in (t or "") for t in d["textos"])
    if editable:
        assert d["tras_quitar"] == 1 and d["envio"] is True and d["msg"] == "conectividad.prueba_enviada"
        assert any(e[0] == "PUT" and e[1] == "/email/config"
                   and e[2]["destinatarios"] == CORREO["destinatarios"][:1] for e in d["enviados"])
    else:
        assert not any(e[0] in ("PUT", "POST") for e in d["enviados"])
