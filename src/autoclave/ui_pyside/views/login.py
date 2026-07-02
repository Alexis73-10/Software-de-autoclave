import hashlib

from PySide6.QtCore import QSettings, QSize, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import InfoBar, InfoBarPosition


def _hash_pw(pw: str) -> str:
    return hashlib.sha256(pw.encode("utf-8")).hexdigest()


_CARD_STYLE = """
    QFrame#loginCard {
        background: white;
        border-radius: 20px;
    }
"""
_FIELD_FRAME = """
    QFrame {
        background: #f5f6fa;
        border-radius: 10px;
        border: 1.5px solid #e0e0e0;
    }
"""
_FIELD_INPUT = """
    QLineEdit {
        background: transparent;
        border: none;
        color: #333;
        font-size: 14px;
    }
"""
_ICON_LABEL = "background: transparent; border: none; color: #aaa; font-size: 18px;"
_BTN_LOGIN = """
    QPushButton {
        background: #2563eb;
        color: white;
        border-radius: 10px;
        border: none;
        font-size: 13px;
        font-weight: bold;
        letter-spacing: 1px;
    }
    QPushButton:hover   { background: #1d4ed8; }
    QPushButton:pressed { background: #1e40af; }
"""


class LoginView(QWidget):
    def __init__(self, nav_callback):
        super().__init__()
        self._nav = nav_callback

        # Fondo degradado
        self.setStyleSheet("""
            LoginView {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 #1a3a5c, stop:1 #3a6fa8
                );
            }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.addStretch(1)

        # ── Card blanca centrada ──────────────────────────────────────
        card = QFrame()
        card.setObjectName("loginCard")
        card.setStyleSheet(_CARD_STYLE)
        card.setMaximumWidth(420)
        card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)

        cl = QVBoxLayout(card)
        cl.setContentsMargins(32, 28, 32, 28)
        cl.setSpacing(14)

        # Título
        title = QLabel("LOGIN")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: #1a2a3a; background: transparent;")
        cl.addWidget(title)

        # Avatar circular
        avatar = QLabel("👤")
        avatar.setFixedSize(110, 110)
        avatar.setFont(QFont("Segoe UI", 46))
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar.setStyleSheet(
            "QLabel { background: #e8eaed; border-radius: 55px; color: #888; }"
        )
        cl.addWidget(avatar, alignment=Qt.AlignmentFlag.AlignHCenter)

        # Subtítulo
        sub = QLabel("Inicie sesión para continuar")
        sub.setFont(QFont("Segoe UI", 11))
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet("color: #666; background: transparent;")
        cl.addWidget(sub)

        cl.addSpacing(4)

        # Campo usuario
        self._username = self._make_field("👤", "Nombre Usuario", secret=False)
        cl.addWidget(self._username[0])

        # Campo contraseña
        pw_row, self._password, eye = self._make_field("🔒", "Contraseña", secret=True)
        cl.addWidget(pw_row)

        # Recordar usuario
        self._remember = QCheckBox("Recordar Usuario")
        self._remember.setStyleSheet("""
            QCheckBox {
                color: #555; font-size: 13px; background: transparent;
            }
            QCheckBox::indicator {
                width: 18px; height: 18px;
                border-radius: 4px;
                border: 2px solid #2563eb;
            }
            QCheckBox::indicator:checked {
                background: #2563eb;
                border: 2px solid #2563eb;
                image: url();
            }
        """)
        cl.addWidget(self._remember)

        # Botón iniciar sesión
        btn = QPushButton("   INICIAR SESIÓN")
        btn.setFixedHeight(48)
        btn.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        btn.setStyleSheet(_BTN_LOGIN)
        btn.clicked.connect(self._do_login)
        self._password.returnPressed.connect(self._do_login)
        cl.addWidget(btn)

        # Link olvidó contraseña
        forgot = QLabel(
            '<a href="#" style="color:#2563eb; text-decoration:none;">'
            "¿Olvidó su contraseña?</a>"
        )
        forgot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        forgot.setStyleSheet("background: transparent;")
        cl.addWidget(forgot)

        # Centrar card
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(card)
        row.addStretch()
        root.addLayout(row)
        root.addStretch(1)

        # Cargar usuario recordado
        cfg = QSettings("Especifika", "Autoclave")
        if cfg.value("login/remember", False, type=bool):
            self._username[1].setText(cfg.value("login/last_user", ""))
            self._remember.setChecked(True)

    # ── Construcción de campos con icono ─────────────────────────────

    def _make_field(self, icon_text: str, placeholder: str, secret: bool):
        frame = QFrame()
        frame.setStyleSheet(_FIELD_FRAME)
        h = QHBoxLayout(frame)
        h.setContentsMargins(12, 0, 12, 0)
        h.setSpacing(8)

        icon = QLabel(icon_text)
        icon.setStyleSheet(_ICON_LABEL)
        h.addWidget(icon)

        field = QLineEdit()
        field.setPlaceholderText(placeholder)
        field.setFixedHeight(44)
        field.setStyleSheet(_FIELD_INPUT)
        if secret:
            field.setEchoMode(QLineEdit.EchoMode.Password)
        h.addWidget(field)

        eye = None
        if secret:
            eye = QPushButton("👁")
            eye.setFixedSize(28, 28)
            eye.setCheckable(True)
            eye.setStyleSheet(
                "QPushButton { background:transparent; border:none; color:#aaa; font-size:16px; }"
                "QPushButton:checked { color:#555; }"
            )
            eye.toggled.connect(
                lambda on, f=field: f.setEchoMode(
                    QLineEdit.EchoMode.Normal if on else QLineEdit.EchoMode.Password
                )
            )
            h.addWidget(eye)

        return frame, field, eye

    # ── Lógica de login ───────────────────────────────────────────────

    def _do_login(self) -> None:
        from autoclave.services.domain.logging.db_manager import DbManager
        from autoclave.ui_pyside.services.session_manager import SessionManager

        username = self._username[1].text().strip()
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

        # Guardar "recordar usuario"
        cfg = QSettings("Especifika", "Autoclave")
        if self._remember.isChecked():
            cfg.setValue("login/last_user", username)
            cfg.setValue("login/remember", True)
        else:
            cfg.setValue("login/last_user", "")
            cfg.setValue("login/remember", False)

        SessionManager.login(user)
        self._password.clear()
        self._nav("admin_menu")
