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
    

    return AppConfig(**data)

