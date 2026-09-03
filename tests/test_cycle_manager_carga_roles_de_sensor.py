from autoclave.core.managers.cycle_manager import CycleManager


def _cargar_ciclos():
    cm = CycleManager()
    cm.load_all_cycles()
    return cm


def test_todos_los_perfiles_cargan_sin_excepcion():
    cm = _cargar_ciclos()
    # 5 archivos JSON pero solo 3 ciclos únicos (user overrides factory)
    assert len(cm.cycles) == 3


def test_perfiles_existentes_no_configuran_liquido_por_defecto():
    """Los 5 perfiles actuales son de sólidos: el principal por defecto debe
    seguir siendo temp_camara y no debe haber referencia configurada."""
    cm = _cargar_ciclos()
    for cycle in cm.cycles.values():
        assert cycle.get_principal_sensor() == "temp_camara", cycle.id
        assert cycle.get_referencia_sensor() is None, cycle.id


def test_perfiles_traen_display_slots_de_longitud_3():
    cm = _cargar_ciclos()
    for cycle in cm.cycles.values():
        assert len(cycle.display_slots) == 3, cycle.id
