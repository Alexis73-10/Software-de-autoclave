
import logging

from autoclave.installation.profile import entrada_requerida

logger = logging.getLogger(__name__)

class VacuumPump:
    def __init__(self, estado, profile=None):
        self.estado = estado
        # Perfil de instalación: con agua_bomba declarada "no aplica" no se
        # exige su DI (adenda E0/E1, A-1). None = se exige, como antes.
        self.profile = profile
        
    def agua_bomba (self):
        return self.estado.sensores_di.get("agua_bomba")
    
    def bomba_vacio(self):
        return self.estado.salidas_do.get("bomba_vacio")
    
    def puede_activar(self):
        if self.estado.get_flag("FALLO_SUMINISTRO_ELECTRICO"):
            logger.warning("Bomba bloqueada: fallo de suministro eléctrico.")
            return False

        # Sin DI de agua de sello cableado, la protección es solo por hardware
        # (flotador en la bobina del contactor): el software no la exige.
        if entrada_requerida(self.profile, "agua_bomba") and not self.agua_bomba():
            logger.warning("Advertencia: No hay agua en la bomba de vacío.")
            return False

        if not self.bomba_vacio():
            logger.info("Activando bomba de vacío.")
            return True
        else:
            return False
