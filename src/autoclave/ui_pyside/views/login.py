import hashlib

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    InfoBar,
    InfoBarPosition,
    LineEdit,
    PasswordLineEdit,
    PrimaryPushButton,
    PushButton,
    SubtitleLabel,
)


def _hash_pw(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


class LoginView(QWidget):
    def __init__(self, nav_callback):
        super().__init__()
        self._nav = nav_callback

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 30, 40, 30)
        layout.setSpacing(16)

        # Barra superior
        header = QHBoxLayout()
        btn_back = PushButton("← Volver")
        btn_back.clicked.connect(lambda: self._nav("home"))
        header.addWidget(btn_back)
        header.addStretch()
        layout.addLayout(header)

        layout.addWidget(SubtitleLabel("LOGIN"))

        # Formulario centrado
        form = QVBoxLayout()
        form.setSpacing(12)

        form.addWidget(BodyLabel("Nombre de usuario"))
        self._username = LineEdit()
        self._username.setPlaceholderText("usuario")
        self._username.setFixedWidth(320)
        form.addWidget(self._username)

        form.addWidget(BodyLabel("Contraseña"))
        self._password = PasswordLineEdit()
        self._password.setPlaceholderText("contraseña")
        self._password.setFixedWidth(320)
        form.addWidget(self._password)

        btn_login = PrimaryPushButton("Iniciar Sesión")
        btn_login.setFixedWidth(320)
        btn_login.clicked.connect(self._do_login)
        self._password.returnPressed.connect(self._do_login)
        form.addWidget(btn_login)

        layout.addLayout(form)
        layout.addStretch()

    def _do_login(self) -> None:
        from autoclave.services.domain.logging.db_manager import DbManager
        from autoclave.ui_pyside.services.session_manager import SessionManager

        username = self._username.text().strip()
        password = self._password.text()

        if not username or not password:
            InfoBar.warning(
                title="Campos vacíos",
                content="Ingresa usuario y contraseña",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self,
            )
            return

        db   = DbManager()
        user = db.get_usuario_by_username(username)

        if user is None or user["hash_pw"] != _hash_pw(password):
            InfoBar.error(
                title="Acceso denegado",
                content="Usuario o contraseña incorrectos",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=4000,
                parent=self,
            )
            return

        SessionManager.login(user)
        self._password.clear()

        InfoBar.success(
            title="Sesión iniciada",
            content=f"Bienvenido, {user['nombre']}",
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=3000,
            parent=self,
        )
        self._nav("home")
