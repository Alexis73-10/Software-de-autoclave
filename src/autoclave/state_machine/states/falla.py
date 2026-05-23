import logging

logger = logging.getLogger(__name__)


class FallaState:

    def __init__(self, estado):
        self.estado = estado

    def run(self) -> bool:
        """
        Llamar en cada tick mientras el estado sea FALLA.
        Retorna True cuando el operador reconoció la falla y la máquina
        debe transicionar a PREPARACION.
        """
        if self.estado.get_flag("RESET_FALLA"):
            self.estado.set_flag("RESET_FALLA", False)
            logger.info("FallaState: reset solicitado → transicionando a PREPARACION")
            return True
        return False
