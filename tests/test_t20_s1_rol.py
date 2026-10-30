# Tanda 20, s1 · T20-04: rol `--rol configurar-modulo`
# (estacion/configurar_modulo.py) contra el simulador M31 (solo 127.0.0.1,
# puerto libre). Solo contraseñas ficticias.

import json
import logging
import socket

import pytest

from autoclave import exe_unico
from autoclave.estacion import configurar_modulo as cm
from autoclave.protocols.modbus_link import FalloConexion
from tests.helpers import m31_simulado as m31
from tests.helpers.m31_simulado import M31Simulado

logging.getLogger("pymodbus").setLevel(logging.CRITICAL)

CLAVE = "Pr1eba"          # ficticia
CLAVES_JSON = {"ok", "codigo", "texto_es", "texto_en", "accion_es", "accion_en", "modelo",
               "composicion", "n_modulos", "firmware", "mac", "clave_cambiada"}


@pytest.fixture
def sim():
    s = M31Simulado()
    s.iniciar()
    yield s
    s.detener()


@pytest.fixture(autouse=True)
def sin_backend(monkeypatch):
    monkeypatch.setattr(cm, "backend_escuchando", lambda: False)


@pytest.fixture
def correr(sim, tmp_path):
    ruta = tmp_path / "resultado.json"

    def _correr(*extra, ip="127.0.0.1", puerto=None):
        argv = ["--resultado", str(ruta)]
        if ip is not None:
            argv += ["--ip", ip, "--puerto", str(puerto if puerto is not None else sim.puerto)]
        codigo = cm.main(argv + list(extra))
        texto = ruta.read_text(encoding="ascii")
        return codigo, json.loads(texto), texto

    return _correr


def _archivo_clave(tmp_path, contenido: bytes):
    p = tmp_path / "clave.tmp"
    p.write_bytes(contenido)
    return p


@pytest.mark.req("T20-04")
def test_rol_correcto_json_completo(sim, correr):
    sim.fijar_mac("005404849DB1")
    codigo, res, texto = correr()
    assert codigo == 0
    assert set(res) == CLAVES_JSON
    assert res["ok"] is True and res["codigo"] == "ok"
    assert res["modelo"] == "M31-XAXX0A00G-U"
    assert res["composicion"] == ("M31-GXAXX0A00-U,M31-GAXXXA000-U,M31-GXXAX00A0-U,"
                                  "M31-GXXAX00A0-U,M31-GXDXX0600-U")
    assert res["n_modulos"] == 5
    assert res["firmware"] == "9232-0-13 / v1.0,v1.0,v1.0,v1.0,-"   # FW-INF
    assert res["mac"] == "005404849DB1" and res["clave_cambiada"] is False
    assert "005404849DB1" in res["texto_es"] and "005404849DB1" in res["texto_en"]
    assert res["accion_es"] == "" and res["accion_en"] == ""
    # Una clave por línea, valores escalares, ASCII (Inno Setup)
    lineas = [ln for ln in texto.splitlines() if ln.strip() not in ("{", "}")]
    assert len(lineas) == len(CLAVES_JSON)
    assert all(not isinstance(v, (dict, list)) for v in res.values())
    texto.encode("ascii")
    # No escribe nada: ni bobinas, ni configuración, ni reinicio, ni 0x0C37
    assert sim.escrituras == [] and sim.escrituras_bobinas() == []
    assert sim.reinicios == 0


@pytest.mark.req("T20-04")
def test_rol_composicion_distinta(sim, correr):
    sim.fijar_modelos("M31-XAXX0A00G-U", list(m31.MODELOS_ESCLAVOS_DEFECTO[1:]))
    codigo, res, _ = correr()
    assert codigo == 4 and res["codigo"] == "composicion" and res["ok"] is False
    assert res["accion_es"] and res["accion_en"]
    assert "esclavo ID 0" in res["texto_es"]
    assert sim.escrituras == []


@pytest.mark.req("T20-04")
@pytest.mark.parametrize("preparar,codigo_esperado", [
    (lambda s: s.orden_incorrecto(codigo=True), "orden"),
    (lambda s: s.expansor_sin_respuesta(1), "expansor"),
])
def test_rol_otros_fallos_de_identidad(sim, correr, preparar, codigo_esperado):
    preparar(sim)
    codigo, res, _ = correr()
    assert codigo == 4 and res["codigo"] == codigo_esperado
    assert sim.escrituras == []


@pytest.mark.req("T20-04")
def test_rol_cambia_la_clave_y_borra_el_archivo(sim, correr, tmp_path, caplog, capsys):
    archivo = _archivo_clave(tmp_path, (CLAVE + "\r\n").encode("ascii"))
    with caplog.at_level(logging.DEBUG):
        codigo, res, texto = correr("--clave-archivo", str(archivo))
    assert codigo == 0 and res["clave_cambiada"] is True and res["codigo"] == "ok"
    assert not archivo.exists()
    assert sim.credenciales_web() == ("admin", CLAVE)
    # Solo escribe 0x758B (5) y 0x7590 (3) con la función 16; nada de bobinas
    assert sim.escrituras_bobinas() == []
    assert sorted((fc, d, len(v)) for fc, d, v in sim.escrituras) == \
        [(16, m31.WEB_USUARIO, 5), (16, m31.WEB_CLAVE, 3)]
    assert sim.reinicios == 0
    # La contraseña no aparece en el log, la salida ni el resultado
    salida = capsys.readouterr()
    assert CLAVE not in caplog.text
    assert CLAVE not in salida.out and CLAVE not in salida.err
    assert CLAVE not in texto


@pytest.mark.req("T20-04")
@pytest.mark.parametrize("contenido", [
    b"Pr1eba7",                       # 7 caracteres
    "Prñeba".encode("utf-8"),         # no ASCII
    b"",                              # vacía
    b"Pr\x01eb",                      # no imprimible
    b"Pr\neba",                       # salto de línea en medio
])
def test_rol_clave_invalida_no_escribe(sim, correr, tmp_path, contenido):
    archivo = _archivo_clave(tmp_path, contenido)
    codigo, res, texto = correr("--clave-archivo", str(archivo))
    assert codigo == 5 and res["codigo"] == "clave_invalida"
    assert res["clave_cambiada"] is False
    assert not archivo.exists()
    assert sim.escrituras == []
    assert sim.credenciales_web() == ("admin", m31.CLAVE_WEB_DEFECTO)
    assert res["modelo"] == "M31-XAXX0A00G-U"     # la conexión sí se probó


@pytest.mark.req("T20-04")
def test_rol_clave_que_no_queda(sim, correr, tmp_path):
    sim.registros_ignorados.update(m31.WEB_CLAVE + i for i in range(3))
    archivo = _archivo_clave(tmp_path, CLAVE.encode("ascii"))
    codigo, res, texto = correr("--clave-archivo", str(archivo))
    assert codigo == 6 and res["codigo"] == "clave_no_quedo"
    assert res["clave_cambiada"] is False and res["accion_es"]
    assert not archivo.exists() and CLAVE not in texto
    assert sim.escrituras_bobinas() == []


@pytest.mark.req("T20-04")
def test_rol_archivo_de_clave_se_borra_aunque_falle_la_conexion(sim, correr, tmp_path,
                                                                monkeypatch):
    monkeypatch.setattr(cm, "PRESUPUESTO_S", 0.5)
    archivo = _archivo_clave(tmp_path, CLAVE.encode("ascii"))
    sim.silencio = True
    codigo, res, texto = correr("--clave-archivo", str(archivo))
    assert codigo == 3 and res["codigo"] == "sin_conexion"
    assert not archivo.exists() and CLAVE not in texto


def _puerto_8000_en_escucha():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", 8000))
        s.listen(1)
        return s
    except OSError:
        s.close()
        return None


@pytest.mark.req("T20-04")
def test_rol_con_backend_escuchando_no_actua(sim, correr, monkeypatch, tmp_path):
    escucha = _puerto_8000_en_escucha()
    if escucha is not None:
        monkeypatch.setattr(cm, "backend_escuchando", _real_backend_escuchando)
    else:       # el puerto ya está ocupado (otro proceso): se simula
        monkeypatch.setattr(cm, "backend_escuchando", lambda: True)
    try:
        archivo = _archivo_clave(tmp_path, CLAVE.encode("ascii"))
        codigo, res, _ = correr("--clave-archivo", str(archivo))
    finally:
        if escucha is not None:
            escucha.close()
    assert codigo == 2 and res["codigo"] == "backend_activo"
    assert sim.contador() == 0
    assert not archivo.exists()


# Copia de la función real, tomada antes del parche autouse del módulo.
_real_backend_escuchando = cm.backend_escuchando


@pytest.mark.req("T20-04")
def test_rol_ip_distinta_de_local_usa_la_fija(monkeypatch, tmp_path, caplog):
    llamadas = []

    class _Falso:
        def leer_identidad(self, cerrar=True):
            raise FalloConexion(None, "sin socket (prueba)", "sin_conexion")

        def get_diagnostico(self):
            return {"modulos": {}}

    def _crear(ip, puerto, presupuesto_s):
        llamadas.append((ip, puerto))
        return _Falso()

    monkeypatch.setattr(cm, "_crear_enlace", _crear)
    monkeypatch.setattr(cm, "PRESUPUESTO_S", 0.5)
    ruta = tmp_path / "r.json"
    with caplog.at_level(logging.WARNING):
        codigo = cm.main(["--resultado", str(ruta), "--ip", "10.0.0.1", "--puerto", "1234"])
    assert codigo == 3
    assert llamadas and set(llamadas) == {("192.168.3.7", 502)}
    assert "solo se aceptan" in caplog.text
    assert cm.destino("127.0.0.1", 1502) == ("127.0.0.1", 1502)
    assert cm.destino(None, None) == ("192.168.3.7", 502)


@pytest.mark.req("T20-04")
def test_rol_sin_conexion(monkeypatch, tmp_path):
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    puerto = s.getsockname()[1]
    s.close()           # puerto cerrado
    monkeypatch.setattr(cm, "PRESUPUESTO_S", 1.0)
    ruta = tmp_path / "r.json"
    codigo = cm.main(["--resultado", str(ruta), "--ip", "127.0.0.1", "--puerto", str(puerto)])
    res = json.loads(ruta.read_text(encoding="ascii"))
    assert codigo == 3 and res["codigo"] == "sin_conexion" and res["ok"] is False
    assert res["accion_es"] and res["accion_en"]


@pytest.mark.req("T20-04")
def test_rol_argumentos_invalidos(tmp_path):
    ruta = tmp_path / "r.json"
    assert cm.main(["--resultado", str(ruta), "--desconocido"]) == 7
    assert json.loads(ruta.read_text(encoding="ascii"))["codigo"] == "argumentos"
    assert cm.main([]) == 7          # sin --resultado: no lanza


@pytest.mark.req("T20-04")
def test_exe_unico_admite_el_rol_y_sus_argumentos():
    args = exe_unico._parse_args(["--rol", "configurar-modulo", "--resultado", "r.json",
                                  "--clave-archivo", "c.tmp", "--ip", "127.0.0.1",
                                  "--puerto", "1502", "--idioma", "en"])
    assert args.rol == "configurar-modulo"
    assert args.sobrantes == ["--resultado", "r.json", "--clave-archivo", "c.tmp", "--ip",
                              "127.0.0.1", "--puerto", "1502", "--idioma", "en"]
    with pytest.raises(SystemExit):
        exe_unico._parse_args(["--rol", "backend", "--resultado", "r.json"])


@pytest.mark.req("T20-04")
def test_exe_unico_despacha_antes_del_instalador(monkeypatch):
    vistos = []
    monkeypatch.setattr(exe_unico, "_log_a_archivo", lambda nombre: vistos.append(nombre))
    monkeypatch.setattr(cm, "main", lambda argv: (vistos.append(list(argv)), 3)[1])
    monkeypatch.setattr(exe_unico.sys, "frozen", True, raising=False)
    assert exe_unico.main(["--rol", "configurar-modulo", "--resultado", "r.json"]) == 3
    assert vistos == ["configurar_modulo.log", ["--resultado", "r.json"]]
