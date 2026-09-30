import sys

# Entrada anterior de la UI QML. Se conserva como alias de app.py para que
# `python -m autoclave.ui_qml.main` siga funcionando con el puente y los textos.
from autoclave.ui_qml.app import main

if __name__ == "__main__":
    sys.exit(main())
