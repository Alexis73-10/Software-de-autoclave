# tests/test_o2f_calibracion_atm_qml.py
#
# O2f (tanda 6): pantalla de calibración atmosférica dentro de OPCIONES ›
# Mantenimiento (mockup 10), con el backend doble. Con TANDA6_CAPTURAS=1 guarda
# docs/informes/tanda6/capturas/O2f_*.png (1200x1920).

import pytest

pytest.importorskip("PySide6")

from tests.banco.opciones_qml_banco import correr, quieren_capturas  # noqa: E402

CONDS = {"puerta_abierta": True, "temp_baja": True, "fuera_de_ciclo": True, "lecturas_validas": True}
CRIT = {"promedio_min": 60, "promedio_max": 105, "dispersion_max": 1.5, "diferencia_confirmar": 5,
        "temp_max": 80}
REF = {"valor": 74.6, "usuario": "usuario_tecnico", "fecha": "2026-10-01T09:30:00"}


def _estado(estado="inactiva", muestras=0, t=0.0, motivo="", prom=None, disp=None, cond=None):
    return {"estado": estado, "motivo": motivo, "muestras": muestras, "muestras_total": 24,
            "transcurrido_s": t, "duracion_s": 120.0, "promedio": prom, "dispersion": disp,
            "valor_anterior": 74.6, "condiciones": cond or CONDS, "criterios": CRIT,
            "referencia": REF}


RUTAS = {"GET /maintenance": [200, {"estado": "ok", "configuracion": {"intervalo_dias": 365,
                                                                        "intervalo_ciclos": 1000}}],
         "GET /maintenance/atm-calibration": [200, _estado()],
         "POST /maintenance/atm-calibration/start": [200, _estado("midiendo", 9, 47.0, prom=74.81,
                                                                   disp=0.4)],
         "POST /maintenance/atm-calibration/cancel": [200, _estado("abortada", 9, 47.0, "cancelada",
                                                                    74.81, 0.4)]}

PASOS = r'''
raiz.setProperty("seccionActiva", "mantenimiento"); esperar()
mant = buscar("opcionesMantenimiento")
salida["botones"] = [buscar("botonMant_" + c, mant) is not None for c in ("calibrar", "prueba", "ganancias")]
capturar("O2f_1_mantenimiento.png")
mant.setProperty("vista", "calibracion_atm"); esperar(400)
cal = buscar("opcionesCalibracionAtm")
ctrl = cal.findChild(QObject, "calibracionAtmController")
salida["condiciones"] = [buscar("condicion_" + c, cal) is not None
                         for c in ("puerta_abierta", "temp_baja", "fuera_de_ciclo", "lecturas_validas")]
salida["iniciar_hab"] = buscar("botonIniciarCalibracionAtm", cal).property("habilitado")
capturar("O2f_2_condiciones.png")
rutas["GET /maintenance/atm-calibration"] = rutas["POST /maintenance/atm-calibration/start"]
ctrl.iniciar(); esperar(300)
salida["bloqueada"] = raiz.property("navegacionBloqueada")
salida["barra_atras"] = buscar("barraInferiorOpciones").property("atrasHabilitado")
salida["barra_inicio"] = buscar("barraInferiorOpciones").property("inicioActivo")
salida["cancelar_hab"] = buscar("botonCancelarCalibracionAtm", cal).property("habilitado")
salida["tiempo"] = buscar("tiempoCalibracionAtm", cal).property("text")
raiz.alternarCajon(); esperar()
salida["cajon"] = raiz.property("cajonAbierto")
raiz.atras(); esperar()
salida["sigue_en_cal"] = mant.property("vista")
capturar("O2f_3_midiendo.png")
rutas["GET /maintenance/atm-calibration"] = rutas["POST /maintenance/atm-calibration/cancel"]
ctrl.cancelar(); esperar(300)
salida["bloqueada_tras"] = raiz.property("navegacionBloqueada")
salida["resultado"] = buscar("resultadoCalibracionAtm", cal).property("text")
capturar("O2f_4_cancelada.png")
rutas["GET /maintenance/atm-calibration"] = [200, dict(rutas["POST /maintenance/atm-calibration/cancel"][1],
    estado="por_confirmar", motivo="diferencia_grande", muestras=24, transcurrido_s=120.0,
    promedio=68.2, dispersion=0.6)]
ctrl.cargar(); esperar(300)
salida["confirmar_visible"] = buscar("botonConfirmarCalibracionAtm", cal).isVisible()
capturar("O2f_5_por_confirmar.png")
rutas["GET /maintenance/atm-calibration"] = [200, dict(rutas["GET /maintenance/atm-calibration"][1],
    estado="inactiva", promedio=None, dispersion=None, muestras=0, transcurrido_s=0,
    condiciones={"puerta_abierta": False, "temp_baja": True, "fuera_de_ciclo": True,
                 "lecturas_validas": True})]
ctrl.cargar(); esperar(300)
salida["iniciar_hab_puerta"] = buscar("botonIniciarCalibracionAtm", cal).property("habilitado")
capturar("O2f_6_puerta_cerrada.png")
raiz.atras(); esperar()
salida["vuelve"] = mant.property("vista")
'''


def test_calibracion_atm_pantalla_tecnico():
    d = correr("tecnico", PASOS, RUTAS, capturas=quieren_capturas())
    assert d["avisos"] == []
    assert d["botones"] == [True, True, True] and all(d["condiciones"])
    assert d["iniciar_hab"] is True
    assert d["bloqueada"] is True and d["barra_atras"] is False and d["barra_inicio"] is False
    assert d["cancelar_hab"] is True and d["tiempo"] == "00:47 / 02:00"
    assert d["cajon"] is False and d["sigue_en_cal"] == "calibracion_atm"
    assert d["bloqueada_tras"] is False and "cancelada" in d["resultado"].lower()
    assert d["confirmar_visible"] is True
    assert d["iniciar_hab_puerta"] is False and d["vuelve"] == ""
    assert ["POST", "/maintenance/atm-calibration/start", None] in d["enviados"]


PASOS_IMPRESION = r'''
raiz.setProperty("seccionActiva", "mantenimiento"); esperar()
mant = buscar("opcionesMantenimiento")
imp = mant.findChild(QObject, "impresionesMantenimiento")
salida["prueba"] = imp.imprimirPrueba(); esperar()
salida["msg_ok"] = imp.property("mensaje")
rutas["POST /maintenance/print/calibration"] = [503, {"detail": {"impresora": "sin_papel"}}]
salida["ganancias"] = imp.imprimirGanancias(); esperar()
salida["msg_503"] = imp.property("mensaje")
rutas["POST /maintenance/print/calibration"] = [409, {"detail": "ciclo"}]
imp.imprimirGanancias(); esperar()
salida["msg_409"] = imp.property("mensaje")
capturar("O2f_7_impresion_sin_papel.png") if False else None
'''


def test_impresiones_mensajes():
    d = correr("ingeniero", PASOS_IMPRESION, RUTAS)
    assert d["prueba"] is True and d["msg_ok"] == "calibracion_atm.impreso"
    assert d["ganancias"] is False and d["msg_503"] == "calibracion_atm.err_impresora"
    assert d["msg_409"] == "calibracion_atm.err_impresion_ciclo"
    assert ["POST", "/printer/test-page", None] in d["enviados"]


def test_botones_deshabilitados_en_ciclo_tecnico():
    d = correr("tecnico", r'''
raiz.setProperty("seccionActiva", "mantenimiento"); esperar()
mant = buscar("opcionesMantenimiento")
salida["hab"] = buscar("botonMant_calibrar", mant).property("habilitado")
''', RUTAS, estado="CICLO")
    assert d["hab"] is False
