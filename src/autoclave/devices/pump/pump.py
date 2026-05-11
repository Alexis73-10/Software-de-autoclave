
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VacuumPump:
    def __init__(self, estado):
        self.estado = estado
        
    def agua_bomba (self):
        return self.estado.sensores_di.get("agua_bomba")
    
    def bomba_vacio(self):
        return self.estado.salidas_do.get("bomba_vacio")
    
    def puede_activar(self):
        if not self.agua_bomba():
            logger.warning("Advertencia: No hay agua en la bomba de vacío.")
            return False
        
        if not self.bomba_vacio() and self.agua_bomba():
            logger.info("Activando bomba de vacío.")
            return True
        else:
            return False