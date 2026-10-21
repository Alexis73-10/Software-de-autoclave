# Lista SOUP (D1, tanda 6, 21-oct-2026)

Origen de las versiones: `requirements.lock.txt`. Para los paquetes que no están en el lock se usó `pip list` del entorno de desarrollo (Python 3.14.3, Windows) el 21-oct. El lock está desactualizado: no incluye PySide6, FastAPI, etc. Queda por completar su regeneración.
La clase de riesgo es una propuesta según el uso. Las anomalías conocidas quedan por completar: no se revisaron las listas de errores de cada proyecto.

| SOUP | Versión | Origen de la versión | Uso | Clase propuesta | Anomalías conocidas |
|---|---|---|---|---|---|
| Python (CPython) | 3.14.3 | entorno | Intérprete | C | Por completar |
| pyserial | 3.5 | lock | Comunicación con la ESP32 (control de actuadores) | C | Por completar |
| SQLAlchemy | 2.0.44 | lock | Registro de ciclos, alarmas y auditoría | B | Por completar |
| pydantic / pydantic_core | 2.12.5 / 2.41.5 | lock | Validación de perfiles y de la API | B | Por completar |
| FastAPI | 0.135.2 | entorno | Backend HTTP (comandos de ciclo y puertas) | C | Por completar |
| starlette | 1.0.0 | entorno | Base de FastAPI | C | Por completar |
| uvicorn | 0.42.0 | entorno | Servidor ASGI | B | Por completar |
| python-multipart | 0.0.29 | entorno | Formularios de la API | A | Por completar |
| httpx | 0.28.1 | entorno | Cliente HTTP de la UI al backend | B | Por completar |
| PySide6 (+Addons, Essentials) | 6.11.1 | entorno | UI QML/Widgets (avisos NO ABRIR, alarmas) | B | Por completar |
| PySide6-Fluent-Widgets | 1.11.2 | entorno | Widgets de la UI | A | Por completar |
| PySideSix-Frameless-Window | 0.8.1 | entorno | Ventana de la UI | A | Por completar |
| cryptography | 48.0.0 | entorno | Autenticación y tokens | B | Por completar |
| python-escpos | 3.1 | entorno | Impresión del ticket (marca de carga no estéril) | B | Por completar |
| qrcode | 8.2 | entorno | QR en ticket y reportes | A | Por completar |
| scipy | 1.17.1 | entorno | Por completar (spec B2, tanda 4) | Por completar | Por completar |
| numpy | 2.3.5 | lock | Cálculo numérico y gráficas | A | Por completar |
| pandas | 2.3.3 | lock | Reportes | A | Por completar |
| matplotlib | 3.10.7 | lock | Gráficas de reportes | A | Por completar |
| pillow | 12.0.0 | lock | Imágenes | A | Por completar |
| PyYAML | 6.0.3 | lock | Configuración | B | Por completar |
| ruamel.yaml | 0.19.1 | entorno | Configuración | B | Por completar |
| customtkinter / tk | 5.2.2 / 0.1.0 | lock | UI antigua (uso residual: por completar) | A | Por completar |
| pytest | 9.0.3 | entorno | Solo verificación (no se distribuye) | herramienta | — |

Firmware ESP32 (`Hardware/Comunicacion_esclava_ESP32_V3`), su núcleo Arduino y sus librerías: versiones por completar.
