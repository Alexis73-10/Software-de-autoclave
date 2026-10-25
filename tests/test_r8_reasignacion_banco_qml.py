# tests/test_r8_reasignacion_banco_qml.py
#
# R8 (tanda 8, D8-5.12): Opciones avanzadas = reasignación de E/S dentro de
# OPCIONES, con el backend doble (tests/banco/opciones_qml_banco.py). Recorre la tabla,
# los cambios, el selector de puerto, la alerta de criticidad, la confirmación
# reforzada, "Se reiniciará el control", un conflicto, el bloqueo en ciclo y la
# verificación tras reiniciar, en español y en inglés. Con R8_CAPTURAS=1 guarda
# docs/informes/tanda8/capturas/R8_<idioma>_*.png (1200x1920).

import os

import pytest

pytest.importorskip("PySide6")

from tests.banco import opciones_qml_banco as banco  # noqa: E402
from autoclave import i18n  # noqa: E402
from autoclave.core.runtime import asignacion_io as aio  # noqa: E402

CAPTURAS = banco.RAIZ / "docs" / "informes" / "tanda8" / "capturas"


def _clave(funcion, tipo):
    clave = f"io.{tipo.lower()}.{funcion}"
    return clave if i18n.existe(clave, "es") else f"reasignacion.funcion_{funcion}"


def _datos(editable=True, motivo="", verificacion=None, reinicio_pendiente=False, pendientes=()):
    f = aio.fabrica_codigo()
    filas = []
    for tipo in aio.TIPOS:
        for funcion, puerto in f[tipo].items():
            filas.append({"funcion": funcion, "tipo": tipo, "i18n": _clave(funcion, tipo),
                          "puerto_actual": puerto, "id_actual": aio.etiqueta(tipo, puerto),
                          "puerto_guardado": puerto, "puerto_fabrica": puerto,
                          "id_fabrica": aio.etiqueta(tipo, puerto),
                          "critica": funcion in aio.CRITICAS, "reforzada": funcion in aio.REFORZADAS,
                          "temperatura": tipo == "AI" and aio.es_temperatura(funcion),
                          "habilitada": funcion not in ("vapor_caldera", "vapor_generador")})
    return {"filas": filas,
            "puertos": {"DI": list(aio.PUERTOS_DI), "DO": list(aio.PUERTOS_DO),
                        "AI_TEMP": list(aio.PUERTOS_AI_TEMP), "AI_PRES": list(aio.PUERTOS_AI_PRES)},
            "ocupados": {t: {str(p): fn for fn, p in f[t].items()} for t in aio.TIPOS},
            "cambios_guardados": {}, "reinicio_pendiente": reinicio_pendiente, "error_archivo": "",
            "bloqueo": "", "verificacion": verificacion or {"estado": "sin_cambios", "funciones": {}},
            "editable": editable, "motivo": motivo, "reinicio_disponible": True,
            "pendientes": list(pendientes)}


_LIBRE_DO = next(p for p in aio.PUERTOS_DO if p not in aio.fabrica_codigo()["DO"].values())
_LIBRE_DI = next(p for p in aio.PUERTOS_DI if p not in aio.fabrica_codigo()["DI"].values())

PASOS = r'''
from autoclave import i18n as _i18n
from tests.test_r8_reasignacion_banco_qml import _datos, _LIBRE_DO as LIBRE_DO, _LIBRE_DI as LIBRE_DI
DATOS_CICLO = _datos(editable=False, motivo="ciclo")
DATOS_VERIF = _datos(verificacion={"estado": "trama_presente", "funciones": {
    "vapor_camara": {"estado": "trama_presente", "falta": "sin_prueba_de_salida"},
    "paro_emergencia": {"estado": "trama_presente", "falta": ""},
    "pres_camara": {"estado": "sin_respuesta", "falta": "sin_lectura"},
    "temp_camara": {"estado": "verificada", "falta": ""}}},
    pendientes=["vapor_camara", "paro_emergencia", "pres_camara"])
rutas["GET /io/assignment"] = (200, _datos())
_i18n.fijar_idioma(IDIOMA); esperar(100)
raiz.setProperty("seccionActiva", "opciones_avanzadas"); esperar(400)
# C9 (tanda 9, D9-10): Opciones avanzadas abre en Manejo de ciclos; el
# ingeniero elige la parte de reasignación
buscar("opcionesAvanzadas").setProperty("segmento", "reasignacion"); esperar(400)
p = buscar("opcionesReasignacion")
ctrl = p.findChild(QObject, "reasignacionController")
salida["pantalla"] = p is not None
salida["proximamente"] = buscar("textoProximamente").isVisible()
salida["barra"] = buscar("barraInferiorOpciones").isVisible()
salida["filas"] = len(ctrl.property("filas"))
capturar(f"R8_{IDIOMA}_1_tabla.png")
ctrl.elegirPuerto("vapor_camara", LIBRE_DO); ctrl.elegirPuerto("paro_emergencia", LIBRE_DI); esperar()
salida["aplicar_hab"] = buscar("botonAplicarReasignacion", p).property("habilitado")
p.setProperty("funcionEnEleccion", "")
capturar(f"R8_{IDIOMA}_2_cambios.png")
p.abrirSelector("bomba_vacio"); esperar()
salida["selector"] = buscar("selectorPuerto", p).isVisible()
capturar(f"R8_{IDIOMA}_3_selector.png")
buscar("selectorPuerto", p).setProperty("visible", False)
p.iniciarAplicar(); esperar()
salida["alerta"] = buscar("dialogoAlertaReasignacion", p).isVisible()
capturar(f"R8_{IDIOMA}_4_alerta.png")
buscar("dialogoAlertaReasignacion", p).setProperty("visible", False)
p._pasoReforzada(0); esperar()
salida["reforzada"] = buscar("dialogoReforzadaReasignacion", p).isVisible()
capturar(f"R8_{IDIOMA}_5_reforzada.png")
buscar("dialogoReforzadaReasignacion", p).setProperty("visible", False)
p._pasoReforzada(1); esperar()
salida["reinicio"] = buscar("dialogoReinicioReasignacion", p).isVisible()
capturar(f"R8_{IDIOMA}_6_reinicio.png")
buscar("dialogoReinicioReasignacion", p).setProperty("visible", False)
ctrl.elegirPuerto("bomba_vacio", LIBRE_DO); esperar()
salida["conflictos"] = len(ctrl.property("conflictos"))
salida["aplicar_hab_conflicto"] = buscar("botonAplicarReasignacion", p).property("habilitado")
capturar(f"R8_{IDIOMA}_7_conflicto.png")
ctrl.descartar()
rutas["GET /io/assignment"] = (200, DATOS_CICLO)
ctrl.cargar(); esperar()
salida["editable_ciclo"] = ctrl.property("editable")
salida["aplicar_hab_ciclo"] = buscar("botonAplicarReasignacion", p).property("habilitado")
capturar(f"R8_{IDIOMA}_8_en_ciclo.png")
rutas["GET /io/assignment"] = (200, DATOS_VERIF)
ctrl.cargar(); esperar()
salida["verificacion"] = buscar("verificacionReasignacion", p).isVisible()
salida["boton_verif_paro"] = buscar("botonVerificar_paro_emergencia", p).property("habilitado")
salida["boton_verif_vapor"] = buscar("botonVerificar_vapor_camara", p).property("habilitado")
capturar(f"R8_{IDIOMA}_9_verificacion.png")
p.iniciarVerificacion([x for x in ctrl.property("verificacion") if x["funcion"] == "paro_emergencia"][0])
esperar()
salida["dialogo_verif"] = buscar("dialogoVerificarReasignacion", p).isVisible()
capturar(f"R8_{IDIOMA}_10_verificar.png")
'''


@pytest.mark.parametrize("idioma", ["es", "en"])
def test_recorrido_de_la_pantalla(idioma, monkeypatch):
    monkeypatch.setattr(banco, "CAPTURAS", CAPTURAS)
    capturas = os.environ.get("R8_CAPTURAS") == "1"
    if capturas:
        CAPTURAS.mkdir(parents=True, exist_ok=True)
    r = banco.correr("ingeniero", f"IDIOMA = {idioma!r}\n" + PASOS, capturas=capturas)
    assert r["pantalla"] and r["barra"] and not r["proximamente"]
    assert r["filas"] == len(aio.funciones())
    assert r["aplicar_hab"] is True
    assert r["selector"] and r["alerta"] and r["reforzada"] and r["reinicio"]
    assert r["conflictos"] == 1 and r["aplicar_hab_conflicto"] is False
    assert r["editable_ciclo"] is False and r["aplicar_hab_ciclo"] is False
    assert r["verificacion"] is True
    assert r["boton_verif_paro"] is True and r["boton_verif_vapor"] is False
    assert r["dialogo_verif"] is True
    assert r["avisos"] == []
