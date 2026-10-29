"""D8-3.18 (tanda 8): comprueba que la compilación lleva la calibración NEUTRA.

Uso: python tools/verificar_calibracion_neutra.py <carpeta dist/Autoclave>

Tanda 19 (MOD-04): la compilación debe traer la calibración del enlace Modbus
(`calibration_modbus.yaml`; enlace único desde la tanda 20, T20-03): su
calibración de usuario debe ser neutra (gain 1.0, offset 0.0, sin
polinomio; 8 sensores de temperatura y 16 de presión desde la tanda 23,
AIN-04) y la de fábrica debe ser la nominal de MOD-04 (temperatura, canales
0-7: adc 0/1000 -> 0/100 °C; presión, canales 0-15: adc 4000/20000 -> 0/400
kPa con adc_piso_senal 3850; gain 1.0, offset 0.0, sin
adc_falla_* y con los márgenes por defecto). Revisión R (V19-s2-01): si falta,
la verificación FALLA (antes solo avisaba).
Tanda 20 (T20-03): la calibración serial (`calibration.yaml` y su plantilla
neutra) se retiró; si la compilación todavía trae `calibration.yaml`, FALLA.
Sale con 0 si todo está bien y con 1 (y el motivo) si algo falta o difiere: la
entrega no se publica con la calibración del banco."""
import hashlib
import sys
from pathlib import Path

NOMBRE_MODBUS = "calibration_modbus.yaml"
# Calibración del enlace serial, retirada en la tanda 20 (T20-03).
NOMBRE_SERIAL_RETIRADA = "calibration.yaml"


def _sha(ruta: Path) -> str:
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


# Fábrica nominal de MOD-04 por canal (8 de temperatura, 16 de presión).
FABRICA_TEMPERATURA = {"adc_min": 0, "adc_max": 1000, "temp_min": 0, "temp_max": 100,
                       "gain": 1.0, "offset": 0.0}
FABRICA_PRESION = {"adc_min": 4000, "adc_max": 20000, "pres_min": 0, "pres_max": 400,
                   "adc_piso_senal": 3850, "gain": 1.0, "offset": 0.0}
# Campos opcionales que pueden estar escritos solo con su valor por defecto
# del esquema (config/schema.FactorySensorCalibration): márgenes NAMUR, piso
# calibrado y polinomio. adc_falla_* no se admite (ni siquiera en None
# explícito: la fábrica nominal no los lleva).
# Tanda 23 (AIN-04): canales por tipo (presión = AI 1-16 del principal).
CANALES = {"temperature": 8, "pressure": 16}
_OPCIONALES_POR_DEFECTO = {"margen_falla_bajo": (0.025,), "margen_falla_alto": (0.0625,),
                           "pres_falla_bajo_kpa": (-10.0,), "poly": (None, [])}


def _igual(a, b) -> bool:
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return float(a) == float(b)
    return a == b


def errores_canal_fabrica(canal, nominal: dict) -> list[str]:
    """Motivos por los que un canal de fábrica no es el nominal (vacío si lo es)."""
    if not isinstance(canal, dict):
        return [f"no es un mapa: {canal!r}"]
    errores = []
    for clave, valor in nominal.items():
        if clave not in canal:
            errores.append(f"falta {clave}")
        elif not _igual(canal[clave], valor):
            errores.append(f"{clave}={canal[clave]!r} (nominal {valor!r})")
    for clave, valor in canal.items():
        if clave in nominal:
            continue
        defectos = _OPCIONALES_POR_DEFECTO.get(clave)
        if defectos is None:
            errores.append(f"campo no nominal {clave}={valor!r}")
        elif not any(_igual(valor, d) for d in defectos):
            errores.append(f"{clave}={valor!r} (por defecto {defectos[0]!r})")
    return errores


def errores_modbus_neutra(ruta: Path) -> list[str]:
    """Motivos por los que `ruta` (calibration_modbus.yaml) no es la de la
    entrega: usuario neutro y fábrica nominal de MOD-04."""
    import yaml
    try:
        datos = yaml.safe_load(ruta.read_text(encoding="utf-8"))
        cal = datos["calibration"]
        user, factory = cal["user"], cal["factory"]
    except Exception as e:
        return [f"{ruta} ilegible ({type(e).__name__})"]
    errores = []
    for tipo, nominal in (("temperature", FABRICA_TEMPERATURA),
                          ("pressure", FABRICA_PRESION)):
        sensores = user.get(tipo) if isinstance(user, dict) else None
        n = CANALES[tipo]
        if not isinstance(sensores, list) or len(sensores) != n:
            errores.append(f"usuario {tipo}: se esperaban {n} sensores")
        else:
            for i, s in enumerate(sensores):
                if s != {"gain": 1.0, "offset": 0.0}:
                    errores.append(f"usuario {tipo}[{i}] no es neutro: {s!r}")
        canales = factory.get(tipo) if isinstance(factory, dict) else None
        if not isinstance(canales, list) or len(canales) != n:
            errores.append(f"fábrica {tipo}: se esperaban {n} canales")
        else:
            for i, c in enumerate(canales):
                motivos = errores_canal_fabrica(c, nominal)
                if motivos:
                    errores.append(f"fábrica {tipo}[{i}] no es la nominal: "
                                   + ", ".join(motivos))
    return errores


def main(argv) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    if len(argv) != 2:
        print(__doc__)
        return 2
    config = Path(argv[1]) / "_internal" / "autoclave" / "config"
    serial = config / NOMBRE_SERIAL_RETIRADA
    if serial.exists():
        print(f"FALLA: la compilación trae {serial} (calibración del enlace "
              f"serial, retirado en la tanda 20)")
        return 1
    modbus = config / NOMBRE_MODBUS
    if not modbus.is_file():
        print(f"FALLA: no existe {modbus} (calibración del enlace Modbus)")
        return 1
    errores = errores_modbus_neutra(modbus)
    if errores:
        print(f"FALLA: {modbus} no es la de la entrega: " + "; ".join(errores))
        return 1
    print(f"OK: calibración Modbus neutra empaquetada (sha256 {_sha(modbus)})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
