# tests/banco/cri_barrido_planta.py
#
# CRI (tanda 35, docs/mis_plans/planeacion_cascada_integral.md §1.4 y §6.3):
# barrido de la planta simulada (valores PROVISIONALES,
# tests/helpers/planta_vapor.py) en esterilización de líquidos desde el inicio
# de la fase. No es una prueba automática (la prueba será
# tests/test_cri_planta.py); imprime la tabla en Markdown. Misma interfaz antes
# y después de los cambios de CRI, para comparar.
#
#   python tests/banco/cri_barrido_planta.py
#   python tests/banco/cri_barrido_planta.py --json salida.json
#   python tests/banco/cri_barrido_planta.py --t-carga 122.06   (variante)
#   python tests/banco/cri_barrido_planta.py --perdidas 0.2     (§1.4, 0,2 kPa/s)
#
# Escenario (§1.4): cámara 212 kPa, chaqueta 215 kPa, Principal 0,6 K bajo la
# sonda real, desfase heredado de CALENTAMIENTO 7 kPa (estado.desfase_trabajo,
# PAM-04), programa Líquidos 121 °C con los valores del equipo SN260001:
# presion_add_esterilizacion 11, brecha_segura_temperatura 0,
# margen_chaqueta_est 20. Planta de líquidos (AJUSTES_LIQUIDOS) con
# PASO_CAMARA × PERDIDA_CAMARA × LLENADO_CHAQUETA variables.
#
# Supuesto propio del barrido (la especificación no lo fija): la carga y la
# sonda real arrancan en --t-carga (defecto 121,6 °C, la Principal lee 121,0 =
# T_est, como al enclavar t_obj en CALENTAMIENTO).

import argparse
import importlib
import json
import logging
import sys
from pathlib import Path

PASOS = (0.1, 0.03, 0.015, 0.008)
PERDIDAS = (0.4, 0.8)
LLENADOS = (4.0, 1.5)

P_CAMARA_INICIAL = 212.0
P_CHAQUETA_INICIAL = 215.0
DESFASE_SONDA_K = 0.6
DESFASE_HEREDADO_KPA = 7.0
T_CARGA_DEFECTO = 121.6
VALORES_EQUIPO = {
    "esterilizacion__presion_add_esterilizacion": 11.0,
    "esterilizacion__brecha_segura_temperatura": 0.0,
    "esterilizacion__margen_chaqueta_est": 20.0,
}


def combinaciones(pasos=PASOS, perdidas=PERDIDAS, llenados=LLENADOS):
    for paso in pasos:
        for perdida in perdidas:
            for llenado in llenados:
                yield paso, perdida, llenado


def _clases(pv, desfase_k, desfase_heredado):
    class _Planta(pv.PlantaVapor):
        """La Principal (temp_camara) lee `desfase_k` bajo la sonda real."""

        def publicar(self, estado):
            super().publicar(estado)
            estado.sensores_temp["temp_camara"] = self.t_sonda - desfase_k

    class _Ester(pv.EsterilizacionFase):
        """Publica el desfase heredado de CALENTAMIENTO (PAM-04) antes del
        primer tick, como lo deja CalentamientoFase al enclavar."""

        def update(self):
            if not self._inicializado:
                self.estado.desfase_trabajo = desfase_heredado
                self.estado.presion_trabajo = None
            return super().update()

    return _Planta, _Ester


def correr(pv, paso, perdida, llenado, t_carga=T_CARGA_DEFECTO,
           desfase_k=DESFASE_SONDA_K, desfase_heredado=DESFASE_HEREDADO_KPA) -> dict:
    from autoclave.core.runtime.steam import p_saturacion_kpa
    planta_orig, ester_orig = pv.PlantaVapor, pv.EsterilizacionFase
    _Planta, _Ester = _clases(pv, desfase_k, desfase_heredado)
    pv.PlantaVapor, pv.EsterilizacionFase = _Planta, _Ester
    try:
        programa = pv.programa_liquidos(**VALORES_EQUIPO)
        ajustes = dict(pv.AJUSTES_LIQUIDOS)
        ajustes.update(PASO_CAMARA=paso, PERDIDA_CAMARA=perdida, LLENADO_CHAQUETA=llenado)
        planta_kw = dict(ajustes=ajustes, t_inicial=t_carga, t_sonda_inicial=t_carga,
                         # p = p_v + p_aire (0,1 tras el prevacío)
                         p_camara_inicial=P_CAMARA_INICIAL - 0.1,
                         p_chaqueta_inicial=P_CHAQUETA_INICIAL)
        tiempo = programa.get_param("esterilizacion", "tiempo_esterilizacion")
        limite = tiempo * 60.0 * 2 + 600.0
        r = pv.simular("chaqueta", programa, limite_s=limite, planta_kw=planta_kw,
                       desde_esterilizacion=True)
    finally:
        pv.PlantaVapor, pv.EsterilizacionFase = planta_orig, ester_orig
    t_est = r.t_est
    p_cic04 = p_saturacion_kpa(t_est) - programa.get_param("esterilizacion",
                                                          "brecha_error_presion")
    if r.resultado == "COMPLETADO":
        codigo = "COMPLETADO"
    else:
        # ESTERILIZACION: alarma_fallo None = CIC-04 (fallas de T/P de la fase)
        alarma = r.alarma[0] if r.alarma else "CIC-04"
        motivo = str(r.motivo or "")
        tipo = ("T baja" if motivo.startswith("Temperatura baja") else
                "P baja" if motivo.startswith("Presi") and "baja" in motivo else "")
        codigo = f"{r.resultado} {alarma}" + (f" ({tipo})" if tipo else "")
    return {
        "paso": paso, "perdida": perdida, "llenado": llenado,
        "resultado": codigo, "completado": r.resultado == "COMPLETADO",
        "motivo": r.motivo, "p_min_ester": r.p_min_ester, "p_cic04": p_cic04,
        "aislamientos": r.aislamientos, "p_chq_max": r.p_chaqueta_max_ester,
        "dur_ester_s": len(r.ester()) * pv.DT,
    }


def _n(v, d=1):
    return "—" if v is None else f"{v:.{d}f}".replace(".", ",")


def tabla(filas) -> str:
    lineas = ["| # | Paso (1/s) | Pérdida (kPa/s) | Llenado (kPa/s) | Resultado | "
              "P mín cámara (CIC-04) | Aisl. VCH-AIS | Chq máx | Duración (s) |",
              "|---|---|---|---|---|---|---|---|---|"]
    for i, f in enumerate(filas, 1):
        lineas.append(
            f"| {i} | {_n(f['paso'], 3)} | {_n(f['perdida'])} | {_n(f['llenado'])} | "
            f"{f['resultado']} | {_n(f['p_min_ester'])} ({_n(f['p_cic04'])}) | "
            f"{f['aislamientos']} | {_n(f['p_chq_max'])} | {_n(f['dur_ester_s'], 0)} |")
    fallos = sum(1 for f in filas if not f["completado"])
    lineas.append("")
    lineas.append(f"Fallan {fallos} de {len(filas)}.")
    return "\n".join(lineas)


def _lista(texto, defecto):
    return tuple(float(x) for x in texto.split(",")) if texto else defecto


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raiz", default=str(Path(__file__).resolve().parents[2]))
    ap.add_argument("--modulo", default="tests.helpers.planta_vapor")
    ap.add_argument("--json")
    ap.add_argument("--t-carga", type=float, default=T_CARGA_DEFECTO)
    ap.add_argument("--pasos", default="")
    ap.add_argument("--perdidas", default="")
    ap.add_argument("--llenados", default="")
    ap.add_argument("--motivos", action="store_true", help="imprime el motivo de cada fallo")
    args = ap.parse_args()
    raiz = Path(args.raiz).resolve()
    sys.path[:0] = [str(raiz / "src"), str(raiz)]
    logging.disable(logging.CRITICAL)
    pv = importlib.import_module(args.modulo)
    filas = []
    for paso, perdida, llenado in combinaciones(_lista(args.pasos, PASOS),
                                                _lista(args.perdidas, PERDIDAS),
                                                _lista(args.llenados, LLENADOS)):
        filas.append(correr(pv, paso, perdida, llenado, t_carga=args.t_carga))
        print(f"  paso={paso} perdida={perdida} llenado={llenado} -> "
              f"{filas[-1]['resultado']}", file=sys.stderr, flush=True)
    print(tabla(filas))
    if args.motivos:
        for f in filas:
            if not f["completado"]:
                print(f"- paso {f['paso']}, pérdida {f['perdida']}, llenado {f['llenado']}: "
                      f"{f['motivo']}")
    if args.json:
        Path(args.json).write_text(json.dumps(filas, indent=1, ensure_ascii=False),
                                   encoding="utf-8")


if __name__ == "__main__":
    main()
