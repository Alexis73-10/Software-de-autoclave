# tests/banco/t33_planta_tabla.py
#
# CAS-04 (tanda 33): tabla de la planta simulada (valores PROVISIONALES,
# tests/helpers/planta_vapor.py) para el criterio de liberación de la cascada
# de chaqueta. No es una prueba automática (la prueba es
# tests/test_t33_cas04_planta.py); imprime la tabla en Markdown.
#
#   python tests/banco/t33_planta_tabla.py
#   python tests/banco/t33_planta_tabla.py --raiz C:\...\autoclave_base \
#          --modulo tests.helpers.planta_vapor_t33 --json salida.json
#
# --raiz: árbol cuyo código se simula (se antepone <raiz> y <raiz>\src a
# sys.path); --modulo: módulo de la planta dentro de ese árbol.

import argparse
import importlib
import json
import logging
import sys
from pathlib import Path

K_VALORES = (1.00, 1.07, 0.95)
CAUDALES = ("restrictivo", "abierto")


def escenarios():
    """(nombre, carga, caudal, k, valores) de CAS-04."""
    for caudal in CAUDALES:
        for k in K_VALORES:
            for add_est in (15.0, 11.0):
                for add_liq in (15.0, 20.0):
                    for brecha in (0.3, 0.0):
                        yield (f"LIQ add_est={add_est:g} add_liq={add_liq:g} brecha={brecha:g}",
                               "liquidos", caudal, k,
                               {"esterilizacion__presion_add_esterilizacion": add_est,
                                "calentamiento__presion_add_liquido_calentamiento": add_liq,
                                "esterilizacion__brecha_segura_temperatura": brecha})
            yield ("134 sólidos", "134", caudal, k, {})
    yield ("134 sólidos (planta A14, paso 0,06)", "134", None, 1.00, {})


def correr(planta, nombre, carga, caudal, k, valores) -> dict:
    from autoclave.core.runtime.steam import p_saturacion_kpa
    programa, planta_kw, limite = planta.escenario_t33(carga, caudal, k, **valores)
    r = planta.simular("chaqueta", programa, limite_s=limite, planta_kw=planta_kw)
    t_est = r.t_est
    brecha_err = programa.get_param("esterilizacion", "brecha_error_presion")
    p_min_req = p_saturacion_kpa(t_est) - brecha_err + 1.5
    codigo = r.resultado if r.resultado == "COMPLETADO" else \
        f"{r.resultado} {r.alarma or ''} {r.motivo or ''}".strip()
    return {
        "escenario": nombre, "carga": carga, "caudal": caudal or "defecto_A14", "k": k,
        "resultado": codigo, "completado": r.resultado == "COMPLETADO",
        "p_min_ester": r.p_min_ester, "p_min_req": p_min_req,
        "aislamientos": r.aislamientos,
        "p_chq_max": r.p_chaqueta_max,
        "sobreimpulso_k": r.sobreimpulso_k,
        "conm_min": r.conmutaciones_por_min_ester(),
        "dur_ester_s": len(r.ester()) * planta.DT,
    }


def cumple(f: dict, corte_chq: float = 375.0, sobre_max: float = 0.59 + 0.2) -> bool:
    ok = (f["completado"] and f["p_min_ester"] is not None
          and f["p_min_ester"] >= f["p_min_req"] and f["aislamientos"] <= 1
          and f["p_chq_max"] < corte_chq)
    if f["carga"] == "134":
        ok = ok and f["sobreimpulso_k"] is not None and f["sobreimpulso_k"] <= sobre_max
    return ok


def _n(v, d=1):
    return "—" if v is None else f"{v:.{d}f}"


def tabla(filas) -> str:
    lineas = ["| Escenario | Caudal | k | Resultado | P mín ester (req) | Aisl. | Chq máx | "
              "Sobreimp. K | Conm./min | Cumple |",
              "|---|---|---|---|---|---|---|---|---|---|"]
    for f in filas:
        lineas.append(
            f"| {f['escenario']} | {f['caudal']} | {f['k']:.2f} | {f['resultado']} | "
            f"{_n(f['p_min_ester'])} ({_n(f['p_min_req'])}) | {f['aislamientos']} | "
            f"{_n(f['p_chq_max'])} | {_n(f['sobreimpulso_k'], 2)} | {_n(f['conm_min'])} | "
            f"{'sí' if cumple(f) else 'NO'} |")
    return "\n".join(lineas)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raiz", default=str(Path(__file__).resolve().parents[2]))
    ap.add_argument("--modulo", default="tests.helpers.planta_vapor")
    ap.add_argument("--json")
    ap.add_argument("--filtro", default="")
    args = ap.parse_args()
    raiz = Path(args.raiz).resolve()
    sys.path[:0] = [str(raiz / "src"), str(raiz)]
    logging.disable(logging.CRITICAL)
    planta = importlib.import_module(args.modulo)
    filas = []
    for esc in escenarios():
        if args.filtro and args.filtro not in f"{esc[0]} {esc[2]} {esc[3]}":
            continue
        filas.append(correr(planta, *esc))
        print(f"  {esc[0]} | {esc[2]} | k={esc[3]:.2f} -> {filas[-1]['resultado']}",
              file=sys.stderr, flush=True)
    print(tabla(filas))
    if args.json:
        Path(args.json).write_text(json.dumps(filas, indent=1, ensure_ascii=False),
                                   encoding="utf-8")


if __name__ == "__main__":
    main()
