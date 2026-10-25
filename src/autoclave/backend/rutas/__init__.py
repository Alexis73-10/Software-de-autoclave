# autoclave/backend/rutas/__init__.py
#
# Rutas HTTP del backend, un APIRouter por área (ORG-12, tanda 15). Se
# registran en backend/server.py; ningún módulo de aquí importa server.py, pero
# se cargan a través de él (rutas/_comun.py carga server_reasignacion.py, que
# toma server.py de sys.modules): importar un router suelto falla.
