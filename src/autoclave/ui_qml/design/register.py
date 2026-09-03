# ui_qml/design/register.py
#
# Registra Tokens.qml (generado por generate_tokens.py) como singleton QML
# importable — `import Autoclave.Design 1.0` — para que cualquier
# componente pueda leer `Tokens.color...`/`Tokens.space...` en vez de
# declarar valores propios (§0.2/§7.2 del sistema de diseño: "prohibido
# declarar hexadecimales en cualquier componente"). Efecto secundario al
# importar este módulo, igual que los controllers (qmlRegisterType) — debe
# importarse antes de cargar cualquier QML que use `import Autoclave.Design`.

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtQml import qmlRegisterSingletonType

_TOKENS_QML = Path(__file__).parent / "Tokens.qml"

qmlRegisterSingletonType(QUrl.fromLocalFile(str(_TOKENS_QML)), "Autoclave.Design", 1, 0, "Tokens")
