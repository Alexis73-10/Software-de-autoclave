"""
autoclave.config.schema
-----------------------
Define la estructura de configuración global del sistema,
incluyendo calibraciones de fábrica, usuario, límites y parámetros generales.
"""

from pydantic import BaseModel, Field
from typing import List, Optional

# ---------------------------------------------------------------------
# Calibraciones de usuario
# ---------------------------------------------------------------------
class SensorCalibration(BaseModel):
    """Calibración simple de usuario (gain/offset)"""
    offset: float = Field(0.0, description="Desplazamiento del sensor")
    gain: float = Field(1.0, description="Ganancia o factor de escala")
    poly: Optional[List[float]] = Field(None, description="Coeficientes polinomiales opcionales")


# ---------------------------------------------------------------------
# Calibraciones de fábrica
# ---------------------------------------------------------------------
class FactorySensorCalibration(SensorCalibration):
    """Calibración de fábrica con límites ADC → ingeniería"""
    adc_min: Optional[int] = Field(None, description="Valor ADC mínimo")
    adc_max: Optional[int] = Field(None, description="Valor ADC máximo")
    temp_min: Optional[float] = Field(None, description="Valor mínimo °C")
    temp_max: Optional[float] = Field(None, description="Valor máximo °C")
    pres_min: Optional[float] = Field(None, description="Valor mínimo de presión")
    pres_max: Optional[float] = Field(None, description="Valor máximo de presión")
    

# ---------------------------------------------------------------------
# Contenedores por tipo de sensor
# ---------------------------------------------------------------------
class FactoryCalibration(BaseModel):
    temperature: List[FactorySensorCalibration] = Field(default_factory=lambda: [FactorySensorCalibration() for _ in range(8)])
    pressure: List[FactorySensorCalibration] = Field(default_factory=lambda: [FactorySensorCalibration() for _ in range(8)])


class UserCalibration(BaseModel):
    temperature: List[SensorCalibration] = Field(default_factory=lambda: [SensorCalibration() for _ in range(8)])
    pressure: List[SensorCalibration] = Field(default_factory=lambda: [SensorCalibration() for _ in range(8)])


# ---------------------------------------------------------------------
# Configuración de calibración completa
# ---------------------------------------------------------------------
class CalibrationConfig(BaseModel):
    factory: FactoryCalibration = Field(default_factory=FactoryCalibration)
    user: UserCalibration = Field(default_factory=UserCalibration)


# ---------------------------------------------------------------------
# Configuración principal de la app
# ---------------------------------------------------------------------
class AppConfig(BaseModel):
    """Configuración global del autoclave."""
    calibration: CalibrationConfig = Field(default_factory=CalibrationConfig)
    name: str = "Autoclave Principal"
    sampling_interval_ms: int = Field(
        500,
        ge=100, le=5000,
        description="Intervalo de muestreo en milisegundos (100–5000 ms)"
    )