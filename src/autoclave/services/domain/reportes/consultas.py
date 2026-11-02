# services/domain/reportes/consultas.py
#
# Armado de las respuestas de solo lectura de Reportes (/report/dashboard,
# /report/calendar, /report/day-cycles). Lo usan el backend real
# (backend/rutas/reportes.py) y el simulador (simulador/reportes_sim.py); no
# depende del contexto del backend: recibe la base, los números de programa y
# el ciclo activo.

import logging
from datetime import date, datetime, timedelta
from datetime import time as dt_time

from autoclave.services.domain.reportes import dashboard, resumen_periodo
from autoclave.utils import periodos

logger = logging.getLogger("autoclave.backend.server")


def _iso(dia: date) -> str:
    return datetime.combine(dia, dt_time()).isoformat()


def _ultimo_dia(hasta_excl: date) -> str:
    return (hasta_excl - timedelta(days=1)).isoformat()


def _conteo_resultados(filas) -> list[dict]:
    """Filas por (tipo_ciclo, resultado) con la forma de get_conteo_resultados,
    para reutilizar resumen_periodo.resumir. El nombre es el del ciclo más
    reciente del periodo (las filas vienen por inicio e id)."""
    cuentas: dict[tuple, int] = {}
    nombres: dict[str, str] = {}
    for f in filas:
        tipo = f["tipo_ciclo"] or ""
        cuentas[(tipo, f["resultado"])] = cuentas.get((tipo, f["resultado"]), 0) + 1
        nombres[tipo] = f["nombre_ciclo"]
    return [{"tipo_ciclo": t, "resultado": r, "cantidad": n, "nombre_ciclo": nombres[t]}
            for (t, r), n in cuentas.items()]


def _indicadores_json(filas) -> dict:
    ind = dashboard.indicadores(filas)
    media, excluidas = dashboard.duracion_media(filas)
    ind["duracion_media_s"] = None if media is None else round(media, 1)
    ind["duraciones_excluidas"] = excluidas
    return ind


def _titulo_alarma(codigo: str, guardado):
    """Título del catálogo de textos en el idioma activo (alarmas.<código>.titulo);
    código desconocido: el título guardado (DR-H05)."""
    from autoclave import i18n
    clave = f"alarmas.{codigo}.titulo"
    if codigo and "." not in codigo and i18n.existe(clave):
        return i18n.t(clave)
    return guardado


def armar_dashboard(db, periodo: str, fecha: date, numeros: dict) -> dict:
    """Cuerpo de GET /report/dashboard (compartido con el simulador, solo lectura)."""
    ini, fin = periodos.rango(periodo, fecha)
    a_ini, a_fin = dashboard.periodo_anterior(periodo, fecha)
    filas = db.get_ciclos_periodo(_iso(ini), _iso(fin))
    previas = db.get_ciclos_periodo(_iso(a_ini), _iso(a_fin))
    alarmas = [{**a, "titulo": _titulo_alarma(a["codigo"], a["titulo"])}
               for a in db.get_alarmas_periodo(_iso(ini), _iso(fin))]
    resumen = resumen_periodo.resumir(_conteo_resultados(filas), numeros)
    operadores = dashboard.agrupar_operadores(filas)
    return {
        "periodo": periodo,
        "desde": ini.isoformat(),
        "hasta": _ultimo_dia(fin),
        "anterior": {"desde": a_ini.isoformat(), "hasta": _ultimo_dia(a_fin)},
        "indicadores": _indicadores_json(filas),
        "indicadores_anterior": _indicadores_json(previas) if previas else None,
        "serie": dashboard.serie(filas, periodo, ini, fin),
        "por_programa": resumen["por_programa"],
        "causas_fallo": resumen["causas_fallo"],
        "alarmas": dashboard.agrupar_alarmas(alarmas),
        "operadores": operadores["operadores"],
        "operadores_otros": operadores["otros"],
    }


def _con_programa(filas, numeros: dict) -> list[dict]:
    """Copias de las filas con `_n` (número efectivo de programa, DR-H02) y `_dia`
    (día local de inicio, o None si la fecha no se puede leer)."""
    salida = []
    for f in filas:
        try:
            dia = date.fromisoformat(str(f["fecha_inicio"])[:10])
        except ValueError:
            dia = None
        salida.append({**f, "_n": dashboard.numero_programa_efectivo(f, numeros), "_dia": dia})
    return salida


def _por_dia(filas) -> dict:
    mapa: dict = {}
    for f in filas:
        if f["_dia"] is not None:
            mapa.setdefault(f["_dia"], []).append(f)
    return mapa


def _estado_del_dia(delante: list, dia: date, programa, activo, hoy: date):
    """(estado, intentos reales del programa, éxitos) del día `dia`. `delante`:
    las filas de ese día (de cualquier programa)."""
    del_programa = [f for f in delante if programa is not None and f["_n"] == programa]
    n_dia = sum(1 for f in delante if activo is None or f["id"] != activo)
    estado = dashboard.estado_dia(del_programa, n_dia, programa == 1, activo, hoy, dia)
    reales = [f for f in del_programa if activo is None or f["id"] != activo]
    return estado, reales, sum(1 for f in reales if dashboard.es_exito(f))


def _lista_programas(filas_periodo, numeros: dict, ciclos) -> list[dict]:
    """DR-D06: programas con algún ciclo en el periodo (número efectivo) y el 01
    si el equipo lo tiene y el periodo tiene algún ciclo; el 01 primero."""
    nombres: dict[int, tuple] = {}
    for f in filas_periodo:           # por inicio e id: el último gana
        if f["_n"] is not None:
            nombres[f["_n"]] = (f["tipo_ciclo"], f["nombre_ciclo"])
    if filas_periodo and 1 in numeros.values():
        nombres.setdefault(1, (None, None))
    actuales = {n: tipo for tipo, n in numeros.items() if n is not None}
    lista = []
    for n in sorted(nombres, key=lambda n: (n != 1, n)):
        tipo, nombre = nombres[n]
        if n in actuales:
            tipo = actuales[n]
            nombre = getattr(ciclos.get(tipo), "name", None) or nombre or tipo
        lista.append({"numero": n, "programa_id": tipo or "", "nombre": nombre or tipo or ""})
    return lista


def armar_calendario(db, periodo, fecha, programa, numeros, ciclos, activo, hoy) -> dict:
    """Cuerpo de GET /report/calendar (compartido con el simulador, solo lectura)."""
    p_ini, p_fin = periodos.rango(periodo, fecha)
    if periodo == "anio":
        c_ini, c_fin = p_ini, p_fin
    else:
        c_ini = fecha.replace(day=1)
        c_fin = (c_ini + timedelta(days=32)).replace(day=1)
    filas = _con_programa(db.get_ciclos_periodo(_iso(c_ini), _iso(c_fin)), numeros)
    en_periodo = [f for f in filas if f["_dia"] is not None and p_ini <= f["_dia"] < p_fin]
    programas = _lista_programas(en_periodo, numeros, ciclos)
    disponibles = [p["numero"] for p in programas]
    if programa in disponibles:
        elegido = programa
    elif 1 in disponibles:
        elegido = 1
    else:
        elegido = disponibles[0] if disponibles else None
    por_dia = _por_dia(filas)
    dias = []
    for k in range((c_fin - c_ini).days):
        dia = c_ini + timedelta(days=k)
        estado, reales, exitos = _estado_del_dia(por_dia.get(dia, []), dia, elegido, activo, hoy)
        dias.append({"fecha": dia.isoformat(), "estado": estado,
                     "intentos": len(reales), "exitos": exitos})
    return {"periodo": periodo, "desde": c_ini.isoformat(), "hasta": _ultimo_dia(c_fin),
            "programas": programas, "programa": elegido, "dias": dias}


def armar_dia(db, programa, fecha, numeros, activo, hoy, ciclo_json) -> dict:
    """Cuerpo de GET /report/day-cycles (compartido con el simulador, solo lectura)."""
    delante = _con_programa(
        db.get_ciclos_periodo(_iso(fecha), _iso(fecha + timedelta(days=1))), numeros)
    estado, _, _ = _estado_del_dia(delante, fecha, programa, activo, hoy)
    ciclos = [{**ciclo_json(f), "programa_numero": f["_n"]} for f in delante if f["_n"] == programa]
    return {"fecha": fecha.isoformat(), "estado": estado, "ciclos": ciclos}
