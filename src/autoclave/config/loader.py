"""
autoclave.config.loader
-----------------------
Carga, valida y entrega objetos de configuración Pydantic desde archivos YAML.

Permite manejar tanto configuraciones principales (AppConfig)
como parámetros globales (GlobalParams).
"""

import yaml
from pathlib import Path
from typing import Union, Type, TypeVar
from pydantic import ValidationError

from autoclave.config.schema import AppConfig, GlobalParams

# Tipo genérico (para aceptar AppConfig o GlobalParams)
T = TypeVar("T", AppConfig, GlobalParams)


def load_yaml(path: Union[str, Path]) -> dict:
    """Carga un archivo YAML y lo devuelve como diccionario."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"❌ Archivo YAML no encontrado: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def validate_and_save_config(path: Union[str, Path], model: Type[T]) -> T:
    """
    Lee un archivo YAML, valida su estructura con Pydantic y devuelve el modelo.

    Args:
        path: Ruta al archivo YAML.
        model: Clase Pydantic a usar para la validación (AppConfig o GlobalParams).

    Returns:
        Instancia validada del modelo Pydantic.
    """
    try:
        data = load_yaml(path)
        config = model(**data)
        print(f"✅ Configuración válida: {path}")
        return config
    except ValidationError as e:
        print(f"❌ Error de validación en {path}:")
        print(e)
        raise
    except Exception as e:
        print(f"⚠️ Error al cargar configuración desde {path}: {e}")
        raise


# -------------------------------------------------------------------------
# Funciones prácticas de uso común
# -------------------------------------------------------------------------

def load_app_config(env: str = "production") -> AppConfig:
    """
    Carga la configuración principal (AppConfig) según el entorno.
    """
    path = Path(f"config/{env}.yaml")
    return validate_and_save_config(path, AppConfig)


def load_global_params() -> GlobalParams:
    """
    Carga los parámetros globales del autoclave (GlobalParams).
    """
    path = Path("config/global_params.yaml")
    return validate_and_save_config(path, GlobalParams)
