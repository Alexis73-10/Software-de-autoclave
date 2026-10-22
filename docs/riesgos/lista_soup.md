# Lista SOUP (D1, tanda 6, 21-oct-2026; versiones actualizadas en L1, tanda 7, 22-oct-2026)

Origen de las versiones: `requirements.lock.txt`, regenerado en L1 (tanda 7) a partir del `pip freeze` del Python 3.14.3 del sistema (Windows), el mismo con el que se compiló el ejecutable con PyInstaller 6.20.0 (etapa K1). Todas las versiones de esta tabla salen ahora del lock (columna "Origen de la versión" = `lock`), salvo Python, que sale del intérprete.

Cambios de versión respecto a la tabla del 21-oct: **ninguno**. Todas las versiones que ya estaban coinciden con el entorno de compilación. Las filas nuevas están marcadas con **(nueva)** en la columna "Origen de la versión".

La clase de riesgo es una propuesta según el uso. Las anomalías conocidas quedan por completar: no se revisaron las listas de errores de cada proyecto.

Revisión de uso (L1): se buscaron los `import` de terceros en `src/`. Los paquetes marcados con "(no se importa en `src/`)" en la columna "Uso" no aparecen en ningún `import` del código del programa; puede que solo se instalen como dependencia o que el uso descrito sea antiguo. Queda por confirmar si siguen siendo SOUP del producto.

| SOUP | Versión | Origen de la versión | Uso | Clase propuesta | Anomalías conocidas |
|---|---|---|---|---|---|
| Python (CPython) | 3.14.3 | entorno (intérprete) | Intérprete | C | Por completar |
| pyserial | 3.5 | lock | Comunicación con la ESP32 (control de actuadores) | C | Por completar |
| SQLAlchemy | 2.0.44 | lock | Registro de ciclos, alarmas y auditoría (no se importa en `src/`; el registro usa `sqlite3` de la biblioteca estándar) | B | Por completar |
| pydantic / pydantic_core | 2.12.5 / 2.41.5 | lock | Validación de perfiles y de la API | B | Por completar |
| FastAPI | 0.135.2 | lock | Backend HTTP (comandos de ciclo y puertas) | C | Por completar |
| starlette | 1.0.0 | lock | Base de FastAPI | C | Por completar |
| uvicorn | 0.42.0 | lock | Servidor ASGI | B | Por completar |
| python-multipart | 0.0.29 | lock | Formularios de la API (no se importa en `src/`; FastAPI lo carga si hay formularios) | A | Por completar |
| httpx | 0.28.1 | lock | Cliente HTTP de la UI al backend (no se importa en `src/`; el cliente usa `requests`) | B | Por completar |
| requests | 2.33.1 | lock **(nueva)** | Cliente HTTP de la UI al backend (comandos de puertas, arranque) | B | Por completar |
| PySide6 (+Addons, Essentials) | 6.11.1 | lock | UI QML/Widgets (avisos NO ABRIR, alarmas) | B | Por completar |
| shiboken6 | 6.11.1 | lock **(nueva)** | Enlace C++/Python de PySide6 | B | Por completar |
| PySide6-Fluent-Widgets (módulo `qfluentwidgets`) | 1.11.2 | lock | Widgets de la UI | A | Por completar |
| PySideSix-Frameless-Window | 0.8.1 | lock | Ventana de la UI (no se importa en `src/`; dependencia de qfluentwidgets) | A | Por completar |
| cryptography | 48.0.0 | lock | Autenticación y tokens (no se importa en `src/`) | B | Por completar |
| keyring | 25.7.0 | lock **(nueva)** | Guardar la contraseña del correo de reportes | A | Por completar |
| psutil | 7.2.2 | lock **(nueva)** | Estado de red y respaldo | A | Por completar |
| pywin32 | 311 | lock **(nueva)** | Impresión en Windows (`win32print`) | B | Por completar |
| python-escpos | 3.1 | lock | Impresión del ticket (marca de carga no estéril) | B | Por completar |
| qrcode | 8.2 | lock | QR en ticket y reportes (no se importa en `src/`) | A | Por completar |
| scipy | 1.17.1 | lock | qfluentwidgets lo importa al cargar (`image_utils` -> `scipy.ndimage`); no se importa en `src/` (ver `Autoclave.spec`, B2 tanda 4) | A | Por completar |
| numpy | 2.3.5 | lock | Cálculo numérico y gráficas (no se importa en `src/`) | A | Por completar |
| pandas | 2.3.3 | lock | Reportes (no se importa en `src/`) | A | Por completar |
| matplotlib | 3.10.7 | lock | Gráficas de reportes (no se importa en `src/`; excluido en `Autoclave.spec`) | A | Por completar |
| pillow | 12.0.0 | lock | Imágenes | A | Por completar |
| PyYAML | 6.0.3 | lock | Configuración | B | Por completar |
| ruamel.yaml | 0.19.1 | lock | Configuración | B | Por completar |
| customtkinter / tk | 5.2.2 / 0.1.0 | lock | UI antigua (no se importa en `src/`; uso residual: por completar) | A | Por completar |
| PyInstaller (+ bootloader) | 6.20.0 | lock **(nueva)** | Empaquetado del ejecutable; su bootloader va dentro del `.exe` entregado | B | Por completar |
| pyinstaller-hooks-contrib | 2026.5 | lock **(nueva)** | Hooks de empaquetado de PyInstaller | herramienta | — |
| altgraph / pefile | 0.17.5 / 2024.8.26 | lock **(nueva)** | Dependencias de PyInstaller durante la compilación (no se distribuyen) | herramienta | — |
| pytest | 9.0.3 | lock | Solo verificación (no se distribuye) | herramienta | — |

Firmware ESP32 (`Hardware/Comunicacion_esclava_ESP32_V3`), su núcleo Arduino y sus librerías: versiones por completar.
