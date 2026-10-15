# state_machine/cycle_phases/valvula_reposo.py
#
# Válvula de reposo al finalizar el ciclo: qué dejar abierto según el modo
# de descompresión configurado del ciclo (0 se trata como 2, igual que
# ProtocoloFallo._aplicar_paso_modo). No decide vacío vs. rango normal —
# eso lo resuelve cada llamador con su propia lectura de presión.
#
# Carga líquida (tanda 2026-10-14 §1.2): la descompresión rápida solo se usa
# en los modos 4/5 y únicamente cuando el Principal ya está en o por debajo de
# temperatura_enfriamiento (`enfriada`); en cualquier otro caso, la lenta.


def abrir_valvula_modo(set_do, modo: int, liquido: bool = False, enfriada: bool = True) -> None:
    modo_efectivo = 2 if not modo else modo
    if liquido:
        if modo_efectivo in (4, 5) and enfriada:
            set_do.descompresion_chaqueta_on()
            set_do.descompresion_rapida_on()
        else:
            set_do.descompresion_rapida_off()
            set_do.descompresion_lenta_on()
        return
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
