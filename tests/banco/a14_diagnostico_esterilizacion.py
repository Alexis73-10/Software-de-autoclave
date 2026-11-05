"""A14 (tanda 28): diagnóstico del sobreimpulso de ESTERILIZACION y del
fallo por aislamiento CIC-16 con la planta simulada (tests/helpers/planta_vapor).

Uso (desde la raíz del worktree, PYTHONPATH=<worktree>\\src):
    python tests/banco/a14_diagnostico_esterilizacion.py --etiqueta antes
    python tests/banco/a14_diagnostico_esterilizacion.py --etiqueta despues

Corre el programa de fábrica de 134 °C en modo chaqueta y en modo cámara con
las variantes de `VARIANTES`, imprime una tabla Markdown con las métricas y
guarda una gráfica T/P/duty por corrida en docs/informes/tanda28/a14/. No es
una prueba automática (la prueba es tests/test_t28_a14_esterilizacion.py)."""

import argparse
import logging
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from tests.helpers.planta_vapor import programa_134, simular  # noqa: E402

SALIDA = RAIZ / "docs" / "informes" / "tanda28" / "a14"

# (nombre, modo, valores del programa); tiempo de exposición de 15 min para
# ver el régimen (el de fábrica, 3,5 min, se corre aparte)
VARIANTES = [
    ("chaqueta_vigente", "chaqueta", {}),
    ("camara_vigente", "camara", {}),
    ("chaqueta_vigente_15min", "chaqueta", {"esterilizacion__tiempo_esterilizacion": 15}),
    ("camara_vigente_15min", "camara", {"esterilizacion__tiempo_esterilizacion": 15}),
    ("chaqueta_brecha_1_0_15min", "chaqueta", {"esterilizacion__tiempo_esterilizacion": 15,
                                               "esterilizacion__brecha_segura_temperatura": 1.0}),
    ("camara_brecha_1_0_15min", "camara", {"esterilizacion__tiempo_esterilizacion": 15,
                                           "esterilizacion__brecha_segura_temperatura": 1.0}),
    ("chaqueta_brecha_0_3_15min", "chaqueta", {"esterilizacion__tiempo_esterilizacion": 15,
                                               "esterilizacion__brecha_segura_temperatura": 0.3}),
    ("camara_brecha_0_3_15min", "camara", {"esterilizacion__tiempo_esterilizacion": 15,
                                           "esterilizacion__brecha_segura_temperatura": 0.3}),
]


def _duty(serie, ventana_s=30.0, dt=0.5):
    n = max(1, int(ventana_s / dt))
    valores, suma, salida = [], 0, []
    for m in serie:
        valores.append(m[5])
        suma += m[5]
        if len(valores) > n:
            suma -= valores.pop(0)
        salida.append(suma / len(valores))
    return salida


def _grafica(nombre, res, programa, ruta):
    from autoclave.core.runtime.steam import p_saturacion_kpa
    datos = res.serie
    desde = max(0.0, (res.inicio_ester_s or 0.0) - 120.0)
    datos = [m for m in datos if m[0] >= desde]
    if not datos:
        return
    t = [(m[0] - (res.inicio_ester_s or 0.0)) / 60 for m in datos]
    fig, (a1, a2, a3) = plt.subplots(3, 1, figsize=(10, 9), sharex=True)
    t_est = res.t_est
    a1.plot(t, [m[2] for m in datos], label="T sonda (°C)")
    a1.axhline(t_est, color="gray", ls="--", lw=0.8, label="T_est")
    brecha = programa.get_param("esterilizacion", "brecha_segura_temperatura")
    a1.axhline(t_est + brecha + 0.3, color="orange", ls=":", lw=0.8,
               label="salida RECUPERACION")
    a1.axhline(t_est - programa.get_param("esterilizacion", "brecha_error_temperatura"),
               color="red", ls=":", lw=0.8, label="falla temp baja")
    a1.set_ylabel("°C")
    a1.set_ylim(t_est - 1.0, t_est + 2.5)
    a1.legend(fontsize=7, loc="lower right")
    a2.plot(t, [m[3] for m in datos], label="P cámara")
    if res.modo == "chaqueta":
        a2.plot(t, [m[4] for m in datos], label="P chaqueta", alpha=0.7)
    a2.axhline(res.p_control_max, color="red", ls="--", lw=0.8, label="P_control_max")
    a2.axhline(p_saturacion_kpa(t_est), color="gray", ls="--", lw=0.8, label="Psat(T_est)")
    a2.set_ylabel("kPa abs")
    a2.set_ylim(p_saturacion_kpa(t_est) - 15, res.p_control_max + 30)
    a2.legend(fontsize=7, loc="lower right")
    a3.plot(t, _duty(datos), label="duty del actuador (media 30 s)")
    a3.plot(t, [m[7] for m in datos], label="aislamiento", alpha=0.6)
    a3.set_ylabel("0–1")
    a3.set_xlabel("min desde la entrada a ESTERILIZACION")
    a3.legend(fontsize=7, loc="upper right")
    fig.suptitle(f"A14 {nombre}: {res.resultado} {res.alarma[0] if res.alarma else ''}")
    fig.tight_layout()
    fig.savefig(ruta, dpi=90)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--etiqueta", default="antes")
    args = parser.parse_args()
    logging.disable(logging.CRITICAL)
    SALIDA.mkdir(parents=True, exist_ok=True)
    print("| corrida | resultado | aislamientos | T máx (°C) | sobreimpulso (K) | T mín exp. (°C) "
          "| P máx (kPa) | en banda [T_est, T_est+1] |")
    print("|---|---|---|---|---|---|---|---|")
    for nombre, modo, valores in VARIANTES:
        programa = programa_134(**valores)
        res = simular(modo, programa)
        alarma = f" {res.alarma[0]}" if res.alarma else ""
        fmt = lambda v, d=2: "—" if v is None else f"{v:.{d}f}"
        banda = res.fraccion_en_banda()
        print(f"| {nombre} | {res.resultado}{alarma} | {res.aislamientos} | "
              f"{fmt(res.t_max_ester)} | {fmt(res.sobreimpulso_k)} | {fmt(res.t_min_ester)} | "
              f"{fmt(res.p_max_ester, 1)} | {'—' if banda is None else f'{banda:.0%}'} |")
        _grafica(nombre, res, programa, SALIDA / f"{args.etiqueta}_{nombre}.png")


if __name__ == "__main__":
    main()
