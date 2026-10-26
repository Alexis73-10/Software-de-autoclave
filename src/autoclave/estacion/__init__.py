# autoclave/estacion
#
# Herramientas de la estación Windows que corren dentro de Autoclave.exe sin
# Qt (tanda 17):
#   - cubierta_arranque: ventana negra a pantalla completa que tapa el
#     escritorio mientras arrancan el backend y las pantallas QML (EST-07);
#   - primer_cuadro: señal con nombre que las pantallas QML activan al mostrar
#     su primer cuadro y que cierra la cubierta (EST-07);
#   - asociar_tactiles + digimon: asociación de pantallas táctiles con su
#     monitor cuando Windows no trae MultiDigitizer.exe (EST-06).
#
# Nada de este paquete importa PySide ni la UI: la cubierta debe abrirse antes
# de importar Qt, y la herramienta de táctiles no depende de él.
