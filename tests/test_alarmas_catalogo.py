import re

import pytest

from autoclave.state_machine.alarms import catalogo as cat
from autoclave.state_machine.alarms.catalogo import (
    CATALOGO, CODIGOS_CONSERVADOS, CODIGOS_TARJETA, DEFINICIONES, Despeje, Nivel,
    nombre_legible,
)

_AREAS = {"PUE", "CIC", "PRE", "COM", "SEN", "SUM", "SIS"}

# Valores de ejemplo por código: deben cubrir EXACTAMENTE los campos de la
# plantilla. Si una plantilla cambia, esta tabla tiene que cambiar con ella.
_EJEMPLOS = {
    "SIS-01": {"estado": "Preparación"},
    "SIS-02": {"error": "disk I/O error"},
    "SIS-03": {"error": "No space left on device"},
    "SUM-01": {"fase": "Esterilización"},
    "SUM-02": {}, "SUM-03": {}, "SUM-04": {}, "SUM-05": {},
    "SUM-06": {"estado": "Ciclo"},
    "PRE-01": {"pres": 250.0, "minimo": 270.0, "objetivo": 320.0, "rango": 50.0},
    "PRE-02": {"pres": 380.0, "maximo": 370.0, "objetivo": 320.0, "rango": 50.0},
    "PRE-03": {"pres": 70.0, "minimo": 81.3},
    "PRE-04": {"pres": 140.0, "maximo": 121.3},
    "PRE-05": {},
    "PRE-06": {"temp": 72.4, "maximo": 65.0},
    "PUE-01": {"puerta": "Puerta 1"},
    "PUE-02": {"puerta": "Puerta 1", "fase": "Prevacío"},
    "PUE-03": {"puerta": "Puerta 2", "pres": 150.0, "minimo": 180.0, "fase": "Secado"},
    "PUE-04": {"puerta": "Puerta 1"},
    "PUE-05": {"puerta": "Puerta 1"},
    "SEN-01": {"sensor": "Temperatura de cámara", "valor": 0},
    "SEN-02": {"sensores": "Temperatura de cámara", "fase": "Calentamiento"},
    "CIC-01": {"motivo": "x"}, "CIC-02": {"motivo": "x"}, "CIC-03": {"motivo": "x"},
    "CIC-04": {"motivo": "x"}, "CIC-05": {"motivo": "x"}, "CIC-06": {"motivo": "x"},
    "CIC-07": {"temp": 95.0, "maximo": 80.0, "minutos": 31.0},
    "CIC-08": {"puerta": "Puerta 2", "motivo": "bloqueo mecánico"},
    "COM-01": {},
    "COM-02": {"segundos": 5.0, "fase": "Calentamiento"},
    "COM-03": {"causa": "TARJETA_WATCHDOG", "motivo": "x.", "fase": "Secado"},
    "COM-04": {},
    "SEN-03": {"sensor": "Referencia", "valor": None},
    "SEN-04": {"fase": "Esterilización"},
    "SEN-05": {"fase": "Calentamiento"},
    "SEN-06": {}, "SEN-07": {},
    "SEN-08": {"puerta": "Puerta 2", "fase": "Esterilización"},
    "SEN-09": {"funciones": "Vapor cámara (DO 25)"},
    "SEN-10": {},          # S9 (tanda 9, D9-1.6): sin valores en el texto
    "CIC-09": {"sensor": "Referencia", "temp": 119.0, "minimo": 120.9, "maximo": 124.0},
    "CIC-10": {"motivo": "Sensor Principal sin lectura"},
    "CIC-11": {"segundos": 31.0, "maximo": 30},
    "SIS-04": {"motivo": "Mantenimiento vencido por fecha"},
    "SIS-05": {},
    # J12 (tanda 12, C-04.4): migración correctiva de un programa
    "SIS-06": {"programa": "Bowie & Dick", "parametro": "presion_add_calentamiento",
               "anterior": "99", "nuevo": "9"},
    "OPERANDO_SIN_BD": {},
    "CONFIGURACION_INVALIDA": {"motivo": "x"},
    **{codigo: {"motivo": "x"} for codigo in CODIGOS_TARJETA},
}


def test_codigos_unicos():
    assert len(DEFINICIONES) == len(CATALOGO)


@pytest.mark.parametrize("d", DEFINICIONES, ids=lambda d: d.codigo)
def test_formato_y_campos(d):
    if d.codigo not in CODIGOS_CONSERVADOS:   # ids previos sin renombrar
        assert re.fullmatch(r"[A-Z]{3}-\d{2}", d.codigo)
        assert d.codigo[:3] in _AREAS
    assert isinstance(d.nivel, Nivel) and isinstance(d.despeje, Despeje)
    assert d.titulo.strip() and d.descripcion.strip()
    if d.nivel is not Nivel.INFORMATIVO:
        assert d.accion.strip()


@pytest.mark.parametrize("d", DEFINICIONES, ids=lambda d: d.codigo)
def test_plantilla_coincide_con_ejemplo(d):
    ejemplo = _EJEMPLOS[d.codigo]
    assert d.campos() == set(ejemplo)
    texto = d.renderizar(ejemplo)
    assert "{" not in texto and "}" not in texto


def test_renderizar_sin_valores_lanza():
    with pytest.raises(KeyError):
        CATALOGO["PRE-01"].renderizar({})


def test_todos_los_codigos_tienen_constante():
    constantes = {v for k, v in vars(cat).items() if re.fullmatch(r"[A-Z]{3}_\d{2}", k)}
    assert constantes | set(CODIGOS_CONSERVADOS) == set(CATALOGO)


def test_niveles_reconocimiento_y_compat():
    assert Nivel.ALARMA.requiere_reconocimiento
    assert Nivel.FALLO_CRITICO.requiere_reconocimiento
    assert not Nivel.AVISO.requiere_reconocimiento
    assert not Nivel.INFORMATIVO.requiere_reconocimiento
    assert Nivel.AVISO.nombre_compat == "ALERTA"
    assert Nivel.ALARMA.nombre_compat == "FALLA"
    assert Nivel.FALLO_CRITICO.nombre_compat == "EMERGENCIA"


def test_niveles_migrados_iguales_a_hoy():
    # Niveles del catálogo; los cambios explícitos van comentados (D9-2).
    esperado = {
        "SIS-01": Nivel.FALLO_CRITICO, "SUM-01": Nivel.FALLO_CRITICO,
        "SEN-02": Nivel.FALLO_CRITICO, "COM-02": Nivel.FALLO_CRITICO,
        # S1 (tanda 8): presión sin lectura en ciclo, mismo nivel que SEN-02
        "SEN-04": Nivel.FALLO_CRITICO, "SEN-05": Nivel.FALLO_CRITICO,
        "SEN-08": Nivel.FALLO_CRITICO,
        "PUE-02": Nivel.ALARMA, "PUE-03": Nivel.ALARMA, "COM-01": Nivel.ALARMA,
        # D8-2.11 (tanda 8): alarma nueva, FALLA bloqueante como COM-01
        "COM-04": Nivel.ALARMA,
        # E6 decisión 9 y arranque: FALLA fuera de ciclo, EMERGENCIA en ciclo
        "COM-03": Nivel.FALLO_CRITICO,
        **{codigo: Nivel.ALARMA for codigo in CODIGOS_CONSERVADOS},
        **{f"CIC-0{i}": Nivel.ALARMA for i in range(1, 7)},
        # D8-2.8 (tanda 8): código nuevo, mismo nivel que el fallo de fase CIC-04
        "CIC-11": Nivel.ALARMA,
        # D9-2 (tanda 9, H3): pasan de AVISO a ALARMA conservando su bloqueo
        "SEN-01": Nivel.ALARMA, "SEN-03": Nivel.ALARMA, "SEN-06": Nivel.ALARMA,
        "SEN-07": Nivel.ALARMA, "CIC-10": Nivel.ALARMA,
        # S9 (tanda 9, D9-1.6): código nuevo, ALARMA que bloquea el inicio
        "SEN-10": Nivel.ALARMA,
    }
    for codigo, d in CATALOGO.items():
        assert d.nivel is esperado.get(codigo, Nivel.AVISO), codigo


@pytest.mark.parametrize("codigo, bloquea", [
    ("SEN-01", True), ("SEN-03", False), ("SEN-06", True), ("SEN-07", True),
    ("CIC-10", False),
])
def test_d9_2_alarma_conserva_bloqueo_y_despeje(codigo, bloquea):
    # D9-2: solo cambia el nivel; el bloqueo de inicio y el despeje automático
    # (se resuelven solas al volver la lectura) siguen como antes.
    d = CATALOGO[codigo]
    assert d.nivel is Nivel.ALARMA
    assert d.nivel.requiere_reconocimiento
    assert d.nivel.nombre_compat == "FALLA"
    assert d.bloquea_inicio is bloquea
    assert d.despeje is Despeje.AUTOMATICO


@pytest.mark.parametrize("clave", [
    "temp_camara", "temp_2_camara", "temp_ref", "temp_chaqueta",
    "temp_drenaje_cam", "temp_drenaje", "pres_camara", "pres_chaqueta",
    "pres_empaque_1", "pres_empaque_2",
    "PRECALENTAMIENTO", "PRE_VACIO", "CALENTAMIENTO", "ESTERILIZACION",
    "DESCOMPRESION", "SECADO",
])
def test_nombres_legibles_cubren_claves_actuales(clave):
    assert nombre_legible(clave) != clave


def test_nombre_legible_desconocido_devuelve_la_clave():
    assert nombre_legible("sensor_raro") == "sensor_raro"


def test_sis01_no_promete_salidas_apagadas():
    texto = CATALOGO["SIS-01"].renderizar({"estado": "Ciclo"})
    assert texto.startswith("Paro de emergencia activo en estado Ciclo.")
    assert "apag" not in texto
    assert "normalmente cerrado (NC)" in texto    # E1 (PF-21)


def test_com02_muestra_segundos_con_un_decimal():
    texto = CATALOGO["COM-02"].renderizar({"segundos": 5.5, "fase": "Secado"})
    assert "más de 5.5 s" in texto


def test_ids_de_la_tarjeta_que_emite_el_enlace_estan_en_el_catalogo():
    # SAF-01 de T1: activar() lanza con un código desconocido; todo id que
    # emite serial_link.py debe existir en el catálogo.
    import pathlib
    fuente = pathlib.Path(__file__).parents[1] / "src/autoclave/protocols/serial_link.py"
    ids = set(re.findall(r'"((?:TARJETA_|DISCREPANCIA_)[A-Z_]+)"', fuente.read_text(encoding="utf-8")))
    assert ids and ids <= set(CATALOGO)
    assert ids == set(CODIGOS_TARJETA)
