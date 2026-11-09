# tests/banco/hor_escenarios_d.py
#
# Tanda horizontal, grupo D (Opciones y todas sus secciones). Lo ejecuta
# tests/banco/hor_capturas.py con qml(), arnes() y ACCIONES a la vista.
#
# Cada escenario «d_<sección>» carga Opciones.qml dentro de un Loader inactivo;
# la acción instala primero una sesión HTTP doble con datos de ejemplo (los
# programas de fábrica, los parámetros del equipo del ConfigManager, usuarios,
# bitácora, canales de E/S, reasignación...) y recién entonces activa el Loader
# y abre la sección, para que los controladores pidan sus datos a ese doble.
# Al cerrarse la ventana se restituye la sesión vacía del guion, así que los
# escenarios de los demás grupos no ven estos datos.

_D_QML = """
Loader {
    id: cargadorD
    objectName: "cargadorD"
    anchors.fill: parent
    active: false
    sourceComponent: Component {
        Opciones { objectName: "opcionesD"; anchors.fill: parent; puente: puenteFalso; teclado: tecD }
    }
}
PanelTeclado { id: tecD; objectName: "tec"; anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom; z: 10 }
"""

_D_CACHE = {}


def _d_rutas():
    """{"MÉTODO /ruta": (estado, datos)} y una función para rutas con parámetros."""
    if "rutas" in _D_CACHE:
        return _D_CACHE["rutas"]
    import glob as _g
    import json as _j
    from autoclave.core.managers.config_manager import ConfigManager, grupos_visibles
    from autoclave.core.runtime import bitacora
    from autoclave.core.runtime import asignacion_io as _aio  # noqa: F401
    from autoclave.core.runtime import io_names

    raiz = os.path.join(os.path.dirname(cfg["banco"]), "..", "src", "autoclave", "cycles", "factory")
    programas, secciones = [], {}
    for ruta in sorted(_g.glob(os.path.join(raiz, "*.json"))):
        d = _j.load(open(ruta, encoding="utf-8"))
        n = d.get("cycle_number")
        if n is None:
            continue
        params = d.get("parameters") or {}
        programas.append({"numero": n, "cycle_id": d.get("cycle_id"),
                          "nombre": d.get("display_name") or d.get("cycle_id"), "origen": "user",
                          "danado": False, "editable": True, "habilitado": n != 6,
                          "personalizado": False, "seleccionado": n == 2,
                          "secciones": [{"clave": s, "no_se_ejecuta": False} for s in params]})
        for s, nodo in params.items():
            hojas = []

            def rec(x, camino):
                if isinstance(x, dict) and "value" in x and not isinstance(x.get("value"), dict):
                    hojas.append((camino, x))
                    return
                if isinstance(x, dict):
                    for k, v in x.items():
                        rec(v, camino + [k])
            rec(nodo, [])
            if s == "descompresion":
                modo = (nodo.get("modo") or {}).get("value")
                hojas = [(c, h) for c, h in hojas if len(c) == 1 or c[0] == f"modo_{modo}"]
            secciones[(n, s)] = {
                "numero": n, "cycle_id": d.get("cycle_id"), "nombre": d.get("display_name"),
                "seccion": s, "editable": True,
                "parametros": [{"path": c, "clave": ".".join(c), "tipo": h.get("type") or "int",
                                "unidad": (h.get("unit") or "").replace("�", "°"),
                                "clase": h.get("clase"), "valor": h.get("value"),
                                "defecto": h.get("value"), "min": h.get("min"), "max": h.get("max"),
                                "opciones": h.get("options") or [], "modos": [],
                                "modificado": False, "ultima_modificacion": None}
                               for c, h in hojas]}
    programas.sort(key=lambda p: p["numero"])

    cm = ConfigManager()
    cm.load_config()
    grupos = grupos_visibles(False)
    parametros = [p for p in cm.describir() if p.get("grupo") in grupos]

    usuarios = [{"nombre": n, "usuario": u, "rol": r, "activo": a, "debe_cambiar_clave": False,
                 "cuenta_sistema": u in ("ingeniero", "especifika"), "creado_por": "ingeniero",
                 "creado_en": "2026-10-20T08:15:00", "ultimo_ingreso": "2026-11-08T14:02:00"}
                for n, u, r, a in [("Ingeniero", "ingeniero", "ingeniero", True),
                                   ("Especifika Servicio", "especifika", "ingeniero", True),
                                   ("Ana María Rodríguez", "arodriguez", "admin", True),
                                   ("Tomás Gutiérrez", "tgutierrez", "tecnico", True),
                                   ("Laura Pérez Castillo", "lperez", "operador", True),
                                   ("Carlos Ramírez", "cramirez", "operador", True),
                                   ("Sofía Hernández", "shernandez", "operador", False),
                                   ("Julián Martínez", "jmartinez", "tecnico", True)]]
    operadores = [{"id": i + 1, "nombre": n, "activo": i != 3}
                  for i, n in enumerate(["Marta López", "Pedro Suárez", "Diana Torres",
                                         "Andrés Gómez", "Valentina Ruiz"])]
    metas = {p["clave"]: p for p in cm.describir()}
    filas = []
    eventos = [("login", "arodriguez", "admin", "", None, None),
               ("param_ciclo_cambio", "tgutierrez", "tecnico", "134_instrumental/esterilizacion/tiempo_esterilizacion", "3.5", "4"),
               ("param_sistema_cambio", "ingeniero", "ingeniero", "timeout_puerta", "60", "90"),
               ("usuario_creado", "arodriguez", "admin", "cramirez", None, None),
               ("ciclo_cancelado", "lperez", "operador", "ciclo 128", None, None),
               ("respaldo_exportado", "ingeniero", "ingeniero", "", None, None),
               ("mantenimiento_registrado", "tgutierrez", "tecnico", "", None, None),
               ("programa_creado", "ingeniero", "ingeniero", "programa_7", None, None)]
    for i in range(20):
        ev, u, r, ent, a, b = eventos[i % len(eventos)]
        filas.append(bitacora.presentar({"id": 200 - i, "ts": f"2026-11-{9 - i // 6:02d}T1{i % 10}:2{i % 6}:05",
                                         "usuario": u, "rol": r, "evento": ev, "entidad": ent,
                                         "valor_anterior": a, "valor_nuevo": b, "detalle": None},
                                        metas, {}, None))
    rutas = {
        "GET /programas": (200, {"programas": programas}),
        "GET /system_params": (200, {"parametros": parametros, "grupos": grupos}),
        "GET /usuarios": (200, {"usuarios": usuarios, "gestionables": ["admin", "ingeniero", "operador", "tecnico"]}),
        "GET /operadores": (200, {"operadores": operadores}),
        "GET /audit_log": (200, {"filas": filas, "total": 143, "pagina": 1, "por_pagina": 20, "paginas": 8,
                                 "usuarios": sorted({f["usuario"] for f in filas}),
                                 "tipos": sorted({f["evento"] for f in filas}),
                                 "categorias": list(bitacora.CATEGORIAS)}),
        "GET /io/channels": (200, {"DI": io_names.canales_digitales("DI", profile=None),
                                   "DO": [dict(c, bloqueada=False) for c in io_names.canales_digitales("DO", profile=None)],
                                   "temperature": io_names.sensores("temperature", profile=None),
                                   "pressure": io_names.sensores("pressure", profile=None)}),
        "GET /maintenance": (200, {"estado": "ok", "proximo": "2027-03-14", "ultimo": "2026-03-14",
                                   "ciclos_restantes": 612, "dias_restantes": 125,
                                   "configuracion": {"intervalo_dias": 365, "intervalo_ciclos": 1000}}),
        "GET /system/info": (200, {"equipo": {"modelo": "AE-PISO-250-2P", "serie": "SN260001",
                                              "instalacion": "2026-10-20T08:00:00", "fuente_vapor": "boiler",
                                              "capacidad_litros": 250, "tipo_carga": "H", "clase": "PISO"},
                                   "software": {"version": "1.0.0-beta.1", "firmware": "9232-0-13 / v1.3",
                                                "id_modulo_es": "005404849DB1", "enlace_io": "modbus"},
                                   "uso": {"ciclos": 388, "mantenimiento": {"estado": "ok"}},
                                   "configuracion": {"idioma": "es", "unidades": {"temperatura": "C", "presion": "kPa"},
                                                     "impresora": "conectada", "red": "conectada"}}),
    }
    # Configuración de la máquina: idioma, tema, unidades e impresora vigentes
    rutas["GET /language"] = (200, {"idioma": cfg.get("idioma", "es")})
    rutas["GET /theme"] = (200, {"tema": cfg["tema"]})
    rutas["GET /units"] = (200, {"temperatura": "C", "presion": "kPa"})
    rutas["GET /printer/config"] = (200, {"habilitada": True})
    try:
        from autoclave.core.runtime import sensores_ciclo as sc
        roles = {"temp_camara": "principal", "temp_2_camara": "referencia", "temp_ref": "no_en_uso"}
        rutas["GET /cycle/sensors"] = (200, {
            "programa": 2, "cycle_id": "134_instrumental", "asignacion": roles, "errores": [],
            "formato_antiguo": False, "editable": True,
            "sensores": [{"id": x, "nombre": sc.NOMBRES[x], "tipo": sc.TIPOS[x], "estado": "disponible",
                          "lectura": 98.2 - i, "rol": roles[x]} for i, x in enumerate(sc.SENSORES)]})
        rutas["GET /cycle/display-inputs"] = (200, {
            "programa": 2, "entradas": ["temp_camara", "pres_camara", ""],
            "habilitadas": ["temp_camara", "temp_2_camara", "pres_camara", "pres_chaqueta"],
            "disponibles": ["temp_camara", "temp_2_camara", "pres_camara", "pres_chaqueta"],
            "no_en_uso": [], "editable": True})
    except Exception as ex:  # noqa: BLE001
        print("hor_escenarios_d: sin sensores", repr(ex))
    try:
        from tests.test_r8_reasignacion_banco_qml import _datos
        rutas["GET /io/assignment"] = (200, _datos())
    except Exception as ex:  # noqa: BLE001
        print("hor_escenarios_d: sin datos de reasignación", repr(ex))
    for modulo in ("tests.test_o2g_conectividad", "tests.test_o2h_respaldo"):
        try:
            for k, v in __import__(modulo, fromlist=["RUTAS"]).RUTAS.items():
                if k.startswith("GET "):
                    rutas[k] = tuple(v)
        except Exception as ex:  # noqa: BLE001
            print("hor_escenarios_d: sin", modulo, repr(ex))

    def resolver(metodo, ruta):
        base = ruta.split("?")[0]
        if metodo + " " + base in rutas:
            return rutas[metodo + " " + base]
        partes = base.strip("/").split("/")
        if metodo == "GET" and len(partes) == 4 and partes[0] == "programas" and partes[2] == "seccion":
            dato = secciones.get((int(partes[1]), partes[3]))
            if dato is not None:
                return 200, dato
        return 200, {}
    _D_CACHE["rutas"] = resolver
    return resolver


class _SesionD:
    sinConexion = False
    generacion = 0

    def enviar(self, metodo, ruta, cuerpo=None):
        estado, datos = _d_rutas()(metodo, ruta)
        if 200 <= estado < 300:
            return sesion_backend.Resultado("ok", datos, estado)
        return sesion_backend.Resultado((datos or {}).get("codigo") or "error_generico", datos, estado)

    def _peticion(self, metodo, ruta, cuerpo=None, token=None, plazo=None):
        return lambda: self.enviar(metodo, ruta, cuerpo)

    def __getattr__(self, n):
        return lambda *a, **k: sesion_backend.Resultado("ok", {}, 200)


def _d_abrir(win, h, seccion, despues=None):
    original = sesion_backend.ventana
    _d_rutas()
    sesion_backend.ventana = lambda: _SesionD()
    win.visibleChanged.connect(lambda v: None if v else setattr(sesion_backend, "ventana", original))
    for o in h.por_nombre("cargadorD"):
        o.setProperty("active", True)
    h.QTest.qWait(500)
    op = h.por_nombre("opcionesD")[0]
    if seccion:
        op.setProperty("seccionActiva", seccion)
    h.QTest.qWait(700)
    if despues:
        despues(win, h, op)
        h.QTest.qWait(500)


def _d_buscar(h, nombre):
    r = h.por_nombre(nombre)
    if r:
        return r[0]
    # delegados (Repeater, GridView): se buscan en el árbol de ítems
    pila = list(h.por_nombre("lienzo")[:1])
    while pila:
        it = pila.pop()
        if it.objectName() == nombre and it.isVisible():
            return it
        pila.extend(it.childItems())
    return None


def _d_ciclo_seccion(win, h, op):
    vista = _d_buscar(h, "parametrosCiclo")
    ctrl = _d_buscar(h, "parametrosCicloController")
    if ctrl is not None and vista is not None:
        ctrl.abrirSeccion("esterilizacion")
        h.QTest.qWait(300)
        vista.setProperty("vista", "seccion")


def _d_equipo_grupo(grupo):
    def f(win, h, op):
        ctrl = _d_buscar(h, "parametrosEquipoController")
        if ctrl is not None:
            ctrl.abrirGrupo(grupo)
    return f


def _d_ciclo_vista(vista_nombre):
    def f(win, h, op):
        vista = _d_buscar(h, "parametrosCiclo")
        ctrl = _d_buscar(h, "parametrosCicloController")
        if ctrl is None or vista is None:
            return
        if vista_nombre == "sensores":
            ctrl.cargarSensores(); h.QTest.qWait(300)
            h.QMetaObject.invokeMethod(vista, "_prepararSensores")
        else:
            ctrl.cargarEntradas(); h.QTest.qWait(300)
            h.QMetaObject.invokeMethod(vista, "_prepararEntradas")
        vista.setProperty("vista", vista_nombre)
    return f


def _d_pulsar(nombre):
    def f(win, h, op):
        o = _d_buscar(h, nombre)
        if o is not None:
            h.tocar(o)
        else:
            print("hor_escenarios_d: no se encontró", nombre)
    return f


def _d_luego(*pasos):
    def f(win, h, op):
        for paso in pasos:
            paso(win, h, op)
            h.QTest.qWait(500)
    return f


def _d_fijar(objeto, prop, valor):
    def f(win, h, op):
        for o in h.por_nombre(objeto):
            o.setProperty(prop, valor)
    return f


def _d_tocar_en(contenedor, nombre):
    def f(win, h, op):
        for c in h.por_nombre(contenedor):
            for o in c.findChildren(QObject, nombre):
                h.tocar(o)
                return
    return f


def _d_reasignacion(win, h, op):
    for o in h.por_nombre("opcionesAvanzadas"):
        o.setProperty("segmento", "reasignacion")


_D_SECCIONES = {
    "d_usuarios": ("usuarios", None),
    "d_parametros_ciclo": ("parametros_ciclo", None),
    "d_parametros_ciclo_fase": ("parametros_ciclo", _d_ciclo_seccion),
    "d_parametros_equipo": ("parametros_sistema", None),
    "d_parametros_equipo_maquina": ("parametros_sistema", _d_equipo_grupo("maquina")),
    "d_fecha_hora": ("fecha_hora", None),
    "d_info_sistema": ("info_sistema", None),
    "d_bitacora": ("bitacora", None),
    "d_mantenimiento": ("mantenimiento", None),
    "d_conectividad": ("conectividad", None),
    "d_respaldo": ("respaldo", None),
    "d_entradas_salidas": ("entradas_salidas", None),
    "d_avanzadas": ("opciones_avanzadas", None),
    "d_reasignacion": ("opciones_avanzadas", _d_reasignacion),
    "d_cajon": ("parametros_ciclo", lambda win, h, op: h.QMetaObject.invokeMethod(op, "abrirCajon")),
    "d_ciclo_sensores": ("parametros_ciclo", _d_ciclo_vista("sensores")),
    "d_ciclo_entradas": ("parametros_ciclo", _d_ciclo_vista("entradas")),
    "d_ciclo_ajuste": ("parametros_ciclo", _d_luego(_d_ciclo_seccion, _d_pulsar("param_temperatura_esterilizacion"))),
    "d_equipo_chaqueta": ("parametros_sistema", _d_equipo_grupo("chaqueta")),
    "d_equipo_impresion": ("parametros_sistema", _d_equipo_grupo("impresion")),
    "d_equipo_ajuste": ("parametros_sistema", _d_luego(_d_equipo_grupo("puerta"),
                                                       _d_pulsar("paramEquipo_timeout_puerta"))),
    "d_usuarios_seleccion": ("usuarios", _d_fijar("opcionesUsuarios", "seleccionado", "tgutierrez")),
    "d_usuarios_operadores": ("usuarios", _d_fijar("opcionesUsuarios", "pestana", "operadores")),
    "d_es_salidas": ("entradas_salidas", _d_fijar("opcionesEntradasSalidas", "segmento", "salidas")),
    "d_es_temperatura": ("entradas_salidas", _d_fijar("opcionesEntradasSalidas", "segmento", "temperatura")),
    "d_es_presion": ("entradas_salidas", _d_fijar("opcionesEntradasSalidas", "segmento", "presion")),
    "d_calibracion_atm": ("mantenimiento", _d_fijar("opcionesMantenimiento", "vista", "calibracion_atm")),
    "d_calibracion_sensor": ("entradas_salidas", _d_luego(
        _d_fijar("opcionesEntradasSalidas", "segmento", "temperatura"),
        _d_fijar("opcionesEntradasSalidas", "segmentoOrigen", "temperatura"),
        _d_fijar("opcionesEntradasSalidas", "sensorEnCalibracion", "temp_camara"))),
    "d_bitacora_tipo": ("bitacora", _d_tocar_en("filtroTipo", "botonDesplegable")),
    "d_avanzadas_programa": ("opciones_avanzadas", lambda win, h, op: [
        h.QMetaObject.invokeMethod(o, "elegirPrograma", h.Q_ARG("QVariant", 2))
        for o in h.por_nombre("opcionesManejoCiclos")]),
}

for _n, (_s, _f) in _D_SECCIONES.items():
    ACCIONES[_n] = (lambda s, f: (lambda win, h: _d_abrir(win, h, s, f)))(_s, _f)
    qml(_n, _D_QML, accion="py:" + _n)
