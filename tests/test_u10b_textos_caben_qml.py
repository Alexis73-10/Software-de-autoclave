# tests/test_u10b_textos_caben_qml.py
#
# U10b (tanda 10, D10-1.4 y D10-1.5 extendida): barrido de TODAS las pantallas
# QML, en es y en, en las resoluciones del equipo, con la revisión genérica de
# tests/textos_caben_qml.py (que U10b amplía con «recortado», «encogido» y
# «desborda_alto»):
#
#   1. cada pantalla cargada sola (con el doble de la sesión HTTP para las de
#      Opciones): ningún texto visible se sale de su cuadro, se recorta o se
#      achica;
#   2. Main.qml completo en Preciclo, con las alarmas reales CIC-10 (motivo
#      largo, texto de T10) y SEN-06: la tarjeta de alarmas y el panel de la
#      campana muestran el motivo COMPLETO (con ajuste de línea, sin achicar ni
#      recortar) y en el idioma de la interfaz (textos de alarmas_i18n que el
#      servidor manda en el DTO; antes salían en español con la interfaz en
#      inglés, hallazgo 1 de CAP9).

import pytest

pytest.importorskip("PySide6")

from tests.textos_caben_qml import RESOLUCIONES, revisar, revisar_main  # noqa: E402

IDIOMAS = ("es", "en")

PANTALLAS = (
    "IntroArranque", "Login", "CambioClave", "NuevoUsuario", "MenuPrincipal",
    "PantallaPreciclo", "PantallaCicloEnCurso", "Instalacion", "Reposo", "Opciones",
    "OpcionesAvanzadas", "OpcionesParametrosCiclo", "OpcionesParametrosEquipo",
    "OpcionesUsuarios", "OpcionesFechaHora", "OpcionesInfoSistema", "OpcionesBitacora",
    "OpcionesCalibracionAtm", "OpcionesCalibracionSensor", "OpcionesConectividad",
    "OpcionesRespaldo", "OpcionesEntradasSalidas", "OpcionesMantenimiento",
    "OpcionesManejoCiclos", "OpcionesReasignacion",
)

# Avisos del motor QML que ya existían antes de U10b, con el doble de sesión
# que responde 200 {} (sin datos): no son de textos y no se tocan aquí.
AVISOS_PREVIOS = {
    "OpcionesBitacora": ("Binding loop",),
    "OpcionesCalibracionSensor": ("TypeError: Cannot read property",),
}


@pytest.fixture(scope="module",
                params=[(p, i, r) for p in PANTALLAS for i in IDIOMAS for r in RESOLUCIONES],
                ids=lambda c: f"{c[0]}-{c[1]}-{c[2][0]}")
def pantalla(request):
    nombre, idioma, (ancho, alto) = request.param
    return nombre, revisar(nombre, idioma, ancho, alto, sesion="ingeniero")


def test_pantalla_sin_textos_fuera_de_su_cuadro(pantalla):
    nombre, r = pantalla
    problemas = [p for paso in r["pasos"] for p in paso["problemas"]]
    assert problemas == [], nombre


def test_pantalla_carga_sin_avisos_nuevos(pantalla):
    nombre, r = pantalla
    previos = AVISOS_PREVIOS.get(nombre, ())
    assert [a for a in r["avisos"] if not any(p in a for p in previos)] == [], nombre


# ── Preciclo con alarmas reales (Main.qml completo) ────────────────────────

# Motivo literal que arma ProtocoloFallo con la presión de cámara sin lectura
# y el estado seguro activo (T10, D10-3), igual que tests/cap9_capturas_banco.py
MOTIVO = ("Sensor de presión de cámara sin lectura: sin el sensor de presión de "
          "cámara no se puede llevar la cámara a estado seguro. Revise la conexión "
          "del sensor de presión de cámara o llame a servicio técnico")

PASOS_ALARMAS = [
    {"campos": {"estado_seguro": {"activo": True, "requiere_confirmacion": False,
                                  "causa": "arranque", "bloqueado_motivo": MOTIVO}},
     "pres_camara": None,
     "alarmas": [["CIC-10", {"motivo": MOTIVO}], ["SEN-06", {}]]},
    {"campana": True},
]


def _descripcion(codigo, valores, idioma):
    from autoclave import i18n
    from autoclave.core.runtime import alarmas_i18n
    from autoclave.state_machine.alarms.catalogo import CATALOGO
    i18n.cargar()
    return alarmas_i18n.textos(CATALOGO[codigo], valores, idioma)["descripcion"]


@pytest.fixture(scope="module", params=[(i, r) for i in IDIOMAS for r in RESOLUCIONES],
                ids=lambda c: f"{c[0]}-{c[1][0]}")
def preciclo_alarmas(request):
    idioma, (ancho, alto) = request.param
    return idioma, revisar_main(idioma, ancho, alto, pasos=PASOS_ALARMAS)


def test_preciclo_con_alarmas_carga_sin_avisos(preciclo_alarmas):
    _, r = preciclo_alarmas
    assert r["avisos"] == []


def test_tarjeta_y_campana_sin_textos_fuera_de_su_cuadro(preciclo_alarmas):
    _, r = preciclo_alarmas
    for paso in r["pasos"]:
        assert paso["problemas"] == []


def test_motivo_completo_y_en_el_idioma_de_la_interfaz(preciclo_alarmas):
    idioma, r = preciclo_alarmas
    cic10 = _descripcion("CIC-10", {"motivo": MOTIVO}, idioma)
    sen06 = _descripcion("SEN-06", {}, idioma)
    for paso in r["pasos"]:               # tarjeta de Preciclo y panel de la campana
        assert cic10 in paso["vistos"]
        assert sen06 in paso["vistos"]
    if idioma != "es":
        cic10_es = _descripcion("CIC-10", {"motivo": MOTIVO}, "es")
        assert cic10 != cic10_es
        for paso in r["pasos"]:
            assert cic10_es not in paso["vistos"]


# ── Menú Principal con datos de ejemplo y sus ventanas (Historial, Reportes…) ─

from tests.textos_caben_qml import VENTANAS_MENU, revisar_menu  # noqa: E402


@pytest.fixture(scope="module", params=[(i, r) for i in IDIOMAS for r in RESOLUCIONES],
                ids=lambda c: f"{c[0]}-{c[1][0]}")
def menu(request):
    idioma, (ancho, alto) = request.param
    return revisar_menu(idioma, ancho, alto)


def test_menu_y_ventanas_cargan_sin_avisos(menu):
    assert menu["avisos"] == []


def test_menu_y_ventanas_sin_textos_fuera_de_su_cuadro(menu):
    assert [p["ventana"] for p in menu["pasos"]] == list(VENTANAS_MENU)
    for paso in menu["pasos"]:
        assert paso["problemas"] == [], paso["ventana"]


def test_menu_abreviado_solo_si_el_completo_no_cabe(menu):
    ajustables = [a for paso in menu["pasos"] for a in paso["ajustables"]]
    assert ajustables, "Reportes usa TextoAjustable en el encabezado de su tabla"
    for a in ajustables:
        cabe = a["anchoCompleto"] <= a["anchoDisponible"]
        assert a["mostrado"] == (a["completo"] if cabe or not a["abreviado"] else a["abreviado"]), a


# ── Opciones con datos (banco de CAP9): cada sección, Reasignación y Manejo ─
# de ciclos con sus diálogos, con la revisión de textos en cada captura.

from tests import opciones_qml_banco as banco  # noqa: E402
from tests import test_c9_manejo_ciclos_banco_qml as c9  # noqa: E402
from tests.test_r8_reasignacion_banco_qml import PASOS as PASOS_R8  # noqa: E402

PASOS_SECCIONES = r'''
from autoclave import i18n as _i18n
_i18n.fijar_idioma(IDIOMA); esperar(100)
capturar(f"OPC_{IDIOMA}_menu.png")
for s in raiz.property("secciones"):
    raiz.setProperty("seccionActiva", s["clave"]); esperar(500)
    capturar(f"OPC_{IDIOMA}_{s['clave']}.png")
'''

CASOS_OPCIONES = (
    ("secciones", "ingeniero", PASOS_SECCIONES, None),
    ("reasignacion", "ingeniero", PASOS_R8, None),
    ("manejo_tecnico", "tecnico", c9.PASOS_TECNICO, c9.RUTAS),
    ("manejo_ingeniero", "ingeniero", c9.PASOS_INGENIERO, c9.RUTAS),
)


@pytest.fixture(scope="module",
                params=[(c, i, r) for c in CASOS_OPCIONES for i in IDIOMAS for r in RESOLUCIONES],
                ids=lambda p: f"{p[0][0]}-{p[1]}-{p[2][0]}")
def opciones(request):
    (nombre, rol, pasos, rutas), idioma, (ancho, alto) = request.param
    return nombre, banco.correr(rol, f"IDIOMA = {idioma!r}\n" + pasos, rutas=rutas,
                                ancho=ancho, alto=alto, revisar=True)


def test_opciones_con_datos_sin_textos_fuera_de_su_cuadro(opciones):
    nombre, r = opciones
    revisiones = r.get("revisiones", {})
    assert revisiones, (nombre, r)
    for captura, rv in revisiones.items():
        assert rv["problemas"] == [], captura


def test_opciones_con_datos_sin_avisos_nuevos(opciones):
    _, r = opciones
    assert [a for a in r["avisos"] if "Binding loop" not in a
            or "OpcionesBitacora" not in a] == []
