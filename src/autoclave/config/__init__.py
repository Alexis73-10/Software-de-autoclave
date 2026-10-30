import yaml
import logging
from pathlib import Path
from autoclave.config.schema import AppConfig

logger=logging.getLogger(__name__)

def load_config(calibration_path: str | Path) -> AppConfig:
    """
    Carga y valida las configuraciones YAML del autoclave.
    Combina parámetros globales y de calibración en un único AppConfig.
    """
    #logger.info(f"ruta yaml: {calibration_path}")

    calibration_path = Path(calibration_path)

    with open(calibration_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    # Tanda 23 (AIN-04): una calibración con 8 entradas de presión se completa
    # a 16 con las nominales (canales 8-15), sin tocar los canales 0-7
    from autoclave.config.completar_presion import completar_presion
    completar_presion(data, str(calibration_path))

    return AppConfig(**data)

