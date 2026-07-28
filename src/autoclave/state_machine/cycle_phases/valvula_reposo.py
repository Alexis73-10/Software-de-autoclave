# state_machine/cycle_phases/valvula_reposo.py
#
# Válvula de reposo al finalizar el ciclo: qué dejar abierto según el modo
# de descompresión configurado del ciclo (0 se trata como 2, igual que
# ProtocoloFallo._aplicar_paso_modo). No decide vacío vs. rango normal —
# eso lo resuelve cada llamador con su propia lectura de presión.


def abrir_valvula_modo(set_do, modo: int) -> None:
    modo_efectivo = 2 if modo == 0 else modo
    if modo_efectivo == 1:
        set_do.descompresion_rapida_on()
    elif modo_efectivo == 2:
        set_do.descompresion_lenta_on()
    elif modo_efectivo == 3:
        set_do.descompresion_rapida_on()
    elif modo_efectivo in (4, 5):
        set_do.descompresion_chaqueta_on()
        set_do.descompresion_rapida_on()


def cerrar_valvulas_descompresion(set_do) -> None:
    set_do.descompresion_rapida_off()
    set_do.descompresion_lenta_off()
    set_do.descompresion_chaqueta_off()
