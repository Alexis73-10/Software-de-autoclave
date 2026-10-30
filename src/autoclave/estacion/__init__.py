# autoclave/estacion
#
# Herramientas de la estación Windows que corren dentro de Autoclave.exe sin
# Qt (tanda 17):
#   - asociar_tactiles + digimon: asociación de pantallas táctiles con su
#     monitor cuando Windows no trae MultiDigitizer.exe (EST-06).
#
#   - instancia_unica: un solo lanzador por sesión (V17-s2-01).
#
# EST-08 (tanda 18): se retiraron la cubierta de arranque y la señal de primer
# cuadro de EST-07; _ventanas se conserva para la herramienta de táctiles.
#
# Nada de este paquete importa PySide ni la UI: el lanzador lo usa antes de
# importar Qt, y la herramienta de táctiles no depende de él.
