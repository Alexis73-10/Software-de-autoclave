# tests/banco/rv_backend_simulado.py
#
# Revisión visual (RV, etapa E1, 19-nov): backend REAL contra el módulo E/S
# SIMULADO (tests/helpers/m31_simulado.py, solo 127.0.0.1), para los flujos que
# el simulador de la UI no cubre (Opciones, usuarios, modo prueba, Entradas/
# Salidas). Se ejecuta SOLO desde el worktree aislado de la etapa E (su propia
# copia de data/): se niega a correr en el repositorio principal.
#
#   python tests/banco/rv_backend_simulado.py [--puerto-modbus 15020]
#
# 1. levanta M31Simulado en 127.0.0.1:<puerto-modbus> con la configuración de
#    seguridad ya precargada (no hace falta reiniciarlo);
# 2. reescribe src/autoclave/config/modbus_link.json DEL WORKTREE con
#    127.0.0.1:<puerto-modbus> y comprueba que la IP es de loopback;
# 3. arranca `python -m autoclave.backend.main` (127.0.0.1:8000) con el
#    PYTHONPATH del worktree y AUTOCLAVE_REINICIO_PC=0, y espera hasta Ctrl+C
#    o hasta que exista <worktree>/_rv_detener.txt.

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--puerto-modbus", type=int, default=15020)
    a = ap.parse_args()
    if not (RAIZ / ".git").is_file():
        print("Se niega: no es un worktree (rv_backend_simulado solo corre en el worktree aislado)")
        return 2
    sys.path.insert(0, str(RAIZ)); sys.path.insert(0, str(RAIZ / "src"))
    from tests.helpers.m31_simulado import M31Simulado

    sim = M31Simulado()
    sim.precargar_configuracion()
    # equipo en reposo: paro liberado y atrapamientos libres (contactos NC,
    # io_names.NC_POR_OMISION: DI 11, 07 y 08 en 1), puertas cerradas (DI 03 y
    # 05) y todas las presiones a la atmosférica de Bogotá (~75 kPa: 7000 µA
    # con 4-20 mA = 0-400 kPa)
    for i in (10, 6, 7, 2, 4):
        sim.di[i] = True
    sim.corrientes = [7000] * 16
    puerto = sim.iniciar(a.puerto_modbus)
    cfg_path = RAIZ / "src" / "autoclave" / "config" / "modbus_link.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    cfg["ip"], cfg["puerto"] = "127.0.0.1", puerto
    cfg_path.write_text(json.dumps(cfg, indent=4), encoding="utf-8")
    assert json.loads(cfg_path.read_text(encoding="utf-8"))["ip"] == "127.0.0.1"
    print("M31 simulado en 127.0.0.1:%d" % puerto, flush=True)

    env = {**os.environ, "PYTHONPATH": str(RAIZ / "src") + os.pathsep + str(RAIZ),
           "AUTOCLAVE_REINICIO_PC": "0"}
    env.pop("AUTOCLAVE_BACKEND_URL", None)
    backend = subprocess.Popen([sys.executable, "-m", "autoclave.backend.main"], cwd=str(RAIZ), env=env)
    detener = RAIZ / "_rv_detener.txt"
    try:
        mando = RAIZ / "_rv_m31.json"
        while backend.poll() is None and not detener.exists():
            time.sleep(0.5)
            # cambios del módulo simulado pedidos por el arnés:
            # {"di": {"10": false}, "corrientes": {"0": 7000}, "temperaturas": {"0": 1340}}
            if mando.exists():
                try:
                    orden = json.loads(mando.read_text(encoding="utf-8"))
                    for clave in ("di", "corrientes", "temperaturas"):
                        for k, v in (orden.get(clave) or {}).items():
                            getattr(sim, clave)[int(k)] = v
                    print("M31: aplicado", orden, flush=True)
                except Exception as ex:  # noqa: BLE001
                    print("M31: orden inválida", repr(ex), flush=True)
                mando.unlink()
    except KeyboardInterrupt:
        pass
    finally:
        if backend.poll() is None:
            backend.terminate()
            try:
                backend.wait(15)
            except subprocess.TimeoutExpired:
                backend.kill()
        sim.detener()
        if detener.exists():
            detener.unlink()
    print("backend detenido; escrituras de bobinas:", len(sim.escrituras_bobinas()), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
