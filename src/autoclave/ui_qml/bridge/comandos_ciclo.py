# ui_qml/bridge/comandos_ciclo.py
#
# Botón "INICIAR CICLO" de la pantalla de ciclo (la misma lógica que tenía la
# UI anterior, retirada en R1 de la tanda 2):
#   - solo se acepta con LISTO_PARA_CICLO activo (en QML, además, el botón
#     desaparece cuando no lo está);
#   - envía UIServiceBackend.start_cycle() (POST /cycle/start); si el backend
#     lo rechaza, solo se registra en el log.
# El backend vuelve a validar LISTO_PARA_CICLO (409 si no está listo).
# La petición HTTP corre fuera del hilo de la GUI.
#
# T30-01 (tanda 30): operador obligatorio sin sesión. El backend decide: si
# responde 409 `operador_requerido` (sin sesión válida y con operadores
# activos), se lee la lista de activos y se abre la elección
# (`eligiendoOperador`, `operadores`); elegir uno vuelve a enviar con
# `operador_id`; Cancelar no inicia. Con sesión (token de la ventana) o sin
# operadores activos el inicio va directo, como antes. Sin poder leer la
# lista no se inicia (falla cerrada). QML solo dibuja: `mensajeClave` es la
# clave i18n del aviso dentro de la elección.

import logging
import threading

from PySide6.QtCore import Property, QObject, Signal, Slot

from autoclave.ui_qml import sesion_backend

logger = logging.getLogger(__name__)

_RUTA = "/cycle/start"
_CODIGOS_OPERADOR = frozenset({"operador_requerido", "operador_invalido",
                               "operador_no_verificable"})


def _en_hilo(tarea) -> None:
    threading.Thread(target=tarea, daemon=True, name="iniciar-ciclo").start()


class ComandoIniciarCiclo(QObject):
    ocupadoChanged = Signal()
    eleccionChanged = Signal()
    _terminado = Signal(object)   # emitida desde el hilo de trabajo (dict)

    def __init__(self, puente, ui_service, parent=None, ejecutar=_en_hilo):
        super().__init__(parent)
        self._puente = puente
        self._ui = ui_service
        self._ejecutar = ejecutar
        self._ocupado = False
        self._eligiendo = False
        self._operadores: list[dict] = []
        self._mensaje_clave = ""
        self._terminado.connect(self._al_terminar)

    @Slot()
    def iniciar(self) -> None:
        self._iniciar(False)

    @Slot()
    def iniciarSinRegistro(self) -> None:
        """T8 (§7.6): sin base de datos, tras la confirmación explícita del
        operador ("Continuar sin registro"), en cada ciclo."""
        self._iniciar(True)

    @Slot(int)
    def iniciarConOperador(self, operador_id: int) -> None:
        """T30-01: inicio con el operador elegido en la lista (obligatorio)."""
        if not self._eligiendo:
            return
        if not any(o["id"] == operador_id for o in self._operadores):
            self._fijar_mensaje("operador_ciclo.err_requerido")
            return
        self._iniciar(False, operador_id)

    @Slot()
    def cancelarOperador(self) -> None:
        """T30-01: Cancelar (o el control de inicio desaparece): no se inicia."""
        self._fijar_eleccion(False, self._operadores)
        self._fijar_mensaje("")

    def _puede_enviar(self) -> bool:
        if self._ocupado or not self._puente.connected or not self._puente.listoParaCiclo:
            return False
        # A3 (tanda 27): con el modo prueba activo no se envía (el control ya
        # no se ve; el backend responde 409 modo_prueba_activo)
        if getattr(self._puente, "modoPrueba", False) is True:
            logger.info("Inicio de ciclo no enviado: modo prueba activo")
            return False
        return True

    def _iniciar(self, sin_registro: bool, operador_id: int | None = None) -> None:
        if not self._puede_enviar():
            return
        logger.info("Iniciando ciclo%s%s...", " sin registro en la base" if sin_registro else "",
                    " con operador elegido" if operador_id is not None else "")
        self._fijar_ocupado(True)

        def tarea():
            resultado = {"ok": False, "codigo": None, "operadores": None}
            try:
                if sin_registro:
                    ok = self._ui.start_cycle(confirmar_sin_registro=True)
                elif operador_id is not None:
                    ok = self._ui.start_cycle(operador_id=operador_id)
                else:
                    ok = self._ui.start_cycle()
                resultado["ok"] = bool(ok)
                if not ok:
                    resultado["codigo"] = self._codigo_rechazo()
                    if resultado["codigo"] in ("operador_requerido", "operador_invalido"):
                        resultado["operadores"] = self._ui.operadores_activos()
            except Exception as e:   # start_cycle ya captura todo; defensa extra
                logger.warning("start_cycle error: %s", e)
            self._terminado.emit(resultado)

        self._ejecutar(tarea)

    def _codigo_rechazo(self):
        try:
            rechazo = self._ui.ultimo_rechazo_inicio()
        except Exception:
            return None
        if not (isinstance(rechazo, tuple) and len(rechazo) == 2 and isinstance(rechazo[0], int)):
            return None
        causa = sesion_backend.interpretar(rechazo[0], rechazo[1], _RUTA).causa
        return causa if causa in _CODIGOS_OPERADOR else None

    def _al_terminar(self, resultado) -> None:
        self._fijar_ocupado(False)
        resultado = resultado if isinstance(resultado, dict) else {}
        if resultado.get("ok"):
            logger.info("Inicio de ciclo aceptado por el backend")
            self._fijar_eleccion(False, [])
            self._fijar_mensaje("")
            return
        logger.warning("Backend rechazó el inicio del ciclo")
        codigo = resultado.get("codigo")
        ya_eligiendo = self._eligiendo
        if codigo in ("operador_requerido", "operador_invalido"):
            lista = resultado.get("operadores")
            if isinstance(lista, list) and lista:
                self._fijar_eleccion(True, lista)
                # la primera apertura no lleva aviso; un rechazo con la lista
                # ya abierta (operador desactivado entre tanto) sí
                self._fijar_mensaje("" if codigo == "operador_requerido" and not ya_eligiendo
                                    else sesion_backend.clave_mensaje(codigo, _RUTA))
            else:
                # sin lista legible (o vacía tras el rechazo): no se inicia
                self._fijar_eleccion(True, [])
                self._fijar_mensaje("operador_ciclo.err_lista")
        elif codigo == "operador_no_verificable":
            self._fijar_eleccion(True, [])
            self._fijar_mensaje(sesion_backend.clave_mensaje(codigo, _RUTA))
        elif self._eligiendo:
            # otro rechazo con la elección abierta: se avisa ahí mismo
            self._fijar_mensaje("operador_ciclo.err_otro")

    def _fijar_eleccion(self, eligiendo: bool, operadores: list) -> None:
        limpia = [{"id": o["id"], "nombre": o["nombre"]} for o in operadores
                  if isinstance(o, dict) and isinstance(o.get("id"), int)
                  and isinstance(o.get("nombre"), str)]
        if eligiendo != self._eligiendo or limpia != self._operadores:
            self._eligiendo = eligiendo
            self._operadores = limpia
            self.eleccionChanged.emit()

    def _fijar_mensaje(self, clave: str) -> None:
        if clave != self._mensaje_clave:
            self._mensaje_clave = clave
            self.eleccionChanged.emit()

    def _fijar_ocupado(self, valor: bool) -> None:
        if valor != self._ocupado:
            self._ocupado = valor
            self.ocupadoChanged.emit()

    @Property(bool, notify=ocupadoChanged)
    def ocupado(self) -> bool:
        return self._ocupado

    @Property(bool, notify=eleccionChanged)
    def eligiendoOperador(self) -> bool:
        return self._eligiendo

    @Property("QVariantList", notify=eleccionChanged)
    def operadores(self) -> list:
        return [dict(o) for o in self._operadores]

    @Property(str, notify=eleccionChanged)
    def mensajeClave(self) -> str:
        return self._mensaje_clave
