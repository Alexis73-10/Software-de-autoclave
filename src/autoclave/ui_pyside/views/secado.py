# src/autoclave/ui_pyside/views/secado.py
import requests
from autoclave.ui_pyside.services.backend_client import BackendClient
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    DoubleSpinBox,
    InfoBar,
    InfoBarPosition,
    PrimaryPushButton,
    PushButton,
    SpinBox,
    SubtitleLabel,
)


class SecadoView(QWidget):
    BACKEND_URL = "http://127.0.0.1:8000"

    def __init__(self, nav_callback):
        super().__init__()
        self._nav = nav_callback
        self._cycle_id = None
        self._cargados = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 30, 40, 30)
        layout.setSpacing(20)

        header = QHBoxLayout()
        btn_back = PushButton("← Volver")
        btn_back.clicked.connect(lambda: self._nav("home"))
        header.addWidget(btn_back)
        header.addStretch()
        layout.addLayout(header)

        layout.addWidget(SubtitleLabel("Configuración de Secado"))

        # ── Modo ─────────────────────────────────────────────────────────
        modo_row = QHBoxLayout()
        modo_row.addWidget(BodyLabel("Modo (1=Vacío, 2=Vacío+Aire, 3=Pulsado):"))
        self._spin_modo = SpinBox()
        self._spin_modo.setRange(1, 3)
        self._spin_modo.setFixedWidth(100)
        self._spin_modo.valueChanged.connect(self._on_modo_changed)
        modo_row.addWidget(self._spin_modo)
        modo_row.addStretch()
        layout.addLayout(modo_row)

        # ── Tiempo ───────────────────────────────────────────────────────
        tiempo_row = QHBoxLayout()
        tiempo_row.addWidget(BodyLabel("Tiempo de secado (min):"))
        self._spin_tiempo = DoubleSpinBox()
        self._spin_tiempo.setRange(0.0, 120.0)
        self._spin_tiempo.setSingleStep(0.5)
        self._spin_tiempo.setDecimals(1)
        self._spin_tiempo.setFixedWidth(140)
        tiempo_row.addWidget(self._spin_tiempo)
        tiempo_row.addStretch()
        layout.addLayout(tiempo_row)

        # ── Presión chaqueta ─────────────────────────────────────────────
        chaqueta_row = QHBoxLayout()
        chaqueta_row.addWidget(BodyLabel("Presión chaqueta secado (kPa):"))
        self._spin_chaqueta = SpinBox()
        self._spin_chaqueta.setRange(0, 500)
        self._spin_chaqueta.setFixedWidth(120)
        chaqueta_row.addWidget(self._spin_chaqueta)
        chaqueta_row.addStretch()
        layout.addLayout(chaqueta_row)

        # ── Parámetros modo 3 (ocultos por defecto) ───────────────────────
        self._modo3_widget = QWidget()
        modo3_layout = QVBoxLayout(self._modo3_widget)
        modo3_layout.setContentsMargins(0, 0, 0, 0)
        modo3_layout.setSpacing(12)

        pres_baja_row = QHBoxLayout()
        pres_baja_row.addWidget(BodyLabel("Presión baja pulso (kPa):"))
        self._spin_pres_baja = SpinBox()
        self._spin_pres_baja.setRange(0, 200)
        self._spin_pres_baja.setFixedWidth(120)
        pres_baja_row.addWidget(self._spin_pres_baja)
        pres_baja_row.addStretch()
        modo3_layout.addLayout(pres_baja_row)

        pres_alta_row = QHBoxLayout()
        pres_alta_row.addWidget(BodyLabel("Presión alta pulso (kPa):"))
        self._spin_pres_alta = SpinBox()
        self._spin_pres_alta.setRange(0, 300)
        self._spin_pres_alta.setFixedWidth(120)
        pres_alta_row.addWidget(self._spin_pres_alta)
        pres_alta_row.addStretch()
        modo3_layout.addLayout(pres_alta_row)

        layout.addWidget(self._modo3_widget)
        self._modo3_widget.setVisible(False)

        # ── Guardar ──────────────────────────────────────────────────────
        btn_save = PrimaryPushButton("Guardar")
        btn_save.setFixedWidth(160)
        btn_save.clicked.connect(self._save)
        layout.addWidget(btn_save)

        layout.addStretch()
        # C1a (tanda 6): teclado en pantalla al tocar cada campo (equipo táctil)
        from autoclave.ui_pyside.views._teclado_pantalla import conectar_todos
        conectar_todos(self)

    def _on_modo_changed(self, value: int) -> None:
        self._modo3_widget.setVisible(value == 3)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._load_current()

    def _load_current(self) -> None:
        self._cycle_id = None
        self._cargados = {}
        try:
            data = BackendClient(self.BACKEND_URL).get("/cycle")
            secado = data["parameters"]["secado"]
            self._spin_modo.setValue(int(secado["modo"]["value"]))
            self._spin_tiempo.setValue(float(secado["tiempo_secado"]["value"]))
            self._spin_chaqueta.setValue(int(secado["presion_chaqueta_secado"]["value"]))
            self._spin_pres_baja.setValue(int(secado["presion_baja_secado"]["value"]))
            self._spin_pres_alta.setValue(int(secado["presion_alta_secado"]["value"]))
            self._on_modo_changed(self._spin_modo.value())
            self._cycle_id = data["id"]
            self._cargados = self._valores_actuales()
        except Exception:
            pass

    def _valores_actuales(self) -> dict:
        valores = {
            "modo":                    self._spin_modo.value(),
            "tiempo_secado":           self._spin_tiempo.value(),
            "presion_chaqueta_secado": self._spin_chaqueta.value(),
        }
        if self._spin_modo.value() == 3:      # los de pulso solo aplican al modo 3
            valores["presion_baja_secado"] = self._spin_pres_baja.value()
            valores["presion_alta_secado"] = self._spin_pres_alta.value()
        return valores

    @staticmethod
    def _motivo_rechazo(exc) -> tuple[str, str]:
        """(categoría, motivo) de un HTTPError del backend. Categoría "permiso"
        (401/403) o "rechazo" (409/422/503/otro) con el motivo del servidor."""
        resp = getattr(exc, "response", None)
        estado = getattr(resp, "status_code", None)
        try:
            datos = resp.json()
        except Exception:
            datos = {}
        detalle = datos.get("detail") if isinstance(datos, dict) else None
        if not isinstance(detalle, str) or not detalle:
            detalle = str(exc)
        if estado in (401, 403):
            return "permiso", ("Sesión vencida o sin permiso para editar el secado: "
                               "salga e inicie sesión de nuevo (técnico o ingeniero).")
        return "rechazo", detalle

    def _aviso(self, nivel: str, titulo: str, contenido: str, ms: int = 5000) -> None:
        getattr(InfoBar, nivel)(
            title=titulo, content=contenido, orient=Qt.Orientation.Horizontal,
            isClosable=True, position=InfoBarPosition.TOP, duration=ms, parent=self)

    def _save(self) -> None:
        """Guarda cada campo que cambió por PATCH /cycle/parameter (un parámetro
        por petición, con token y rol; B1 de la tanda 4). Un rechazo del backend
        (409/422/403/503) se muestra con su motivo y no cuenta como guardado."""
        if not self._cycle_id:
            self._aviso("warning", "Sin conexión",
                        "No se pudo leer el programa del backend: nada se guardó.")
            return
        # P3 (tanda 5): ante un 401 pide login y
        # reintenta con los mismos valores

        from autoclave.ui_pyside.services import renovacion_sesion
        client = BackendClient(self.BACKEND_URL)
        guardados, rechazados = [], []
        for nombre, valor in self._valores_actuales().items():
            if self._cargados.get(nombre) == valor:
                continue
            try:
                guardado = renovacion_sesion.guardar_con_reintento(
                    lambda: client.patch("/cycle/parameter", {"cycle_id": self._cycle_id,
                                                              "fase": "secado",
                                                              "path": [nombre], "value": valor}),
                    lambda: renovacion_sesion.pedir_credenciales_dialogo(self))
                if guardado.estado != renovacion_sesion.GUARDADO:
                    self._aviso("warning", "Sesión vencida", renovacion_sesion.mensaje_de(guardado))
                    return
            except requests.HTTPError as e:
                categoria, motivo = self._motivo_rechazo(e)
                if categoria == "permiso":
                    self._aviso("error", "Sin permiso", motivo)
                    return
                rechazados.append(f"{nombre}: {motivo}")
                continue
            except requests.RequestException:
                self._aviso("warning", "Sin conexión",
                            "No se pudo conectar al backend: el cambio no se guardó.")
                return
            self._cargados[nombre] = valor
            guardados.append(nombre)
        if rechazados:
            self._aviso("error", "Error al guardar", "; ".join(rechazados))
        elif guardados:
            self._aviso("success", "Guardado", "Configuración de secado actualizada", 3000)
        else:
            self._aviso("info", "Sin cambios", "No hay cambios que guardar", 3000)
