import logging
from autoclave.state_machine.alarms.catalogo import SIS_01

logger = logging.getLogger(__name__)


class FallaState:

    def __init__(self, estado, set_do, alarm_manager):
        self.estado = estado
        self.set_do = set_do
        self.alarm_manager = alarm_manager
        # Hotfix ES (6-nov): callable () -> bool que nivela la presión de
        # cámara igual que PREPARACION (lo fija la StateMachine). None = sin
        # lazo (usos aislados).
        self.nivelar_presion_camara = None

    def run(self) -> bool:
        """
        Llamar en cada tick mientras el estado sea FALLA.
        Retorna True cuando el operador reconoció la falla y la máquina
        debe transicionar a PREPARACION.
        """
        if self.estado.get_flag("PARO_EMERGENCIA"):
            # §5.9 (OPC-23): un reconocimiento con el paro activo se descarta;
            # tras soltar el paro hay que reconocer de nuevo
            if self.estado.get_flag("RESET_FALLA"):
                self.estado.set_flag("RESET_FALLA", False)
                logger.warning("FallaState: RESET_FALLA descartado con el paro de emergencia activo")
            # ALL_OFF limitado: no esperar el ACK en cada tick (A-7)
            self.set_do.apagar_por_paro()
            if self.estado.get_flag("PARO_REAL"):      # U4: sin datos no es SIS-01
                self.alarm_manager.activar(SIS_01, estado="Falla")
            self.set_do.buzer_emergencia()
            return False

        # Hotfix ES (6-nov): sin protocolo de estado seguro, FALLA maneja la
        # presión de cámara como PREPARACION (sobrepresión: venteo, en
        # líquidos por la lenta; vacío: aire atmosférico). Un error no impide
        # el reconocimiento.
        if self.nivelar_presion_camara is not None:
            try:
                self.nivelar_presion_camara()
            except Exception:
                logger.exception("FallaState: no se pudo nivelar la presión de cámara")

        if self.estado.get_flag("RESET_FALLA"):
            self.estado.set_flag("RESET_FALLA", False)
            logger.info("FallaState: reset solicitado → transicionando a PREPARACION")
            return True

        return False
