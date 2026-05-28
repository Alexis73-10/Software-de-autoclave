import pytest
import tkinter as tk
from autoclave.ui.layout import (
    is_portrait, font_scale, scaled_font, check_orientation_changed
)
from autoclave.ui.cycle.widgets.phase_indicator import PhaseIndicator


@pytest.fixture(scope="module")
def tk_root():
    root = tk.Tk()
    root.withdraw()
    yield root
    root.destroy()


def test_is_portrait_landscape():
    assert is_portrait(1920, 1080) is False


def test_is_portrait_portrait():
    assert is_portrait(1080, 1920) is True


def test_is_portrait_square():
    assert is_portrait(1000, 1000) is False


def test_font_scale_reference_landscape():
    assert font_scale(1920, 1080) == pytest.approx(1.0)


def test_font_scale_reference_portrait_13():
    # 13" girado: min sigue siendo 1080
    assert font_scale(1080, 1920) == pytest.approx(1.0)


def test_font_scale_8inch_landscape():
    assert font_scale(1280, 800) == pytest.approx(800 / 1080)


def test_font_scale_8inch_portrait():
    # misma escala en ambas orientaciones del 8"
    assert font_scale(800, 1280) == pytest.approx(800 / 1080)


def test_scaled_font_scale_1():
    assert scaled_font(90, 1.0) == 90


def test_scaled_font_scaled_down():
    assert scaled_font(90, 0.74) == int(90 * 0.74)


def test_scaled_font_minimum():
    assert scaled_font(14, 0.1) == 8


# check_orientation_changed(w, h, current) → (new_portrait, should_rebuild)

def test_check_first_call_landscape():
    portrait, rebuild = check_orientation_changed(1920, 1080, None)
    assert portrait is False
    assert rebuild is False  # primer llamado: solo registrar, no rebuild


def test_check_first_call_portrait():
    portrait, rebuild = check_orientation_changed(1080, 1920, None)
    assert portrait is True
    assert rebuild is False


def test_check_same_orientation():
    portrait, rebuild = check_orientation_changed(1920, 1080, False)
    assert portrait is False
    assert rebuild is False  # sin cambio


def test_check_flip_to_portrait():
    portrait, rebuild = check_orientation_changed(1080, 1920, False)
    assert portrait is True
    assert rebuild is True  # flip → rebuild


def test_check_flip_to_landscape():
    portrait, rebuild = check_orientation_changed(1920, 1080, True)
    assert portrait is False
    assert rebuild is True


def test_check_too_small_dimensions():
    portrait, rebuild = check_orientation_changed(50, 50, False)
    assert portrait is False  # current_portrait unchanged
    assert rebuild is False  # ignorar dimensiones transitorias


def test_check_small_width_only():
    # w < 100 but h is large — still a transient, portrait state must not change
    portrait, rebuild = check_orientation_changed(50, 800, True)
    assert portrait is True
    assert rebuild is False


def test_phase_indicator_default_fonts(tk_root):
    ind = PhaseIndicator(tk_root)
    tk_root.update()
    assert ind._font_size_label == 22
    assert ind._font_size_timer == 20
    ind.destroy()


def test_phase_indicator_custom_fonts(tk_root):
    ind = PhaseIndicator(tk_root, font_size_label=16, font_size_timer=14)
    tk_root.update()
    assert ind._font_size_label == 16
    assert ind._font_size_timer == 14
    ind.destroy()


def test_phase_indicator_update_no_crash(tk_root):
    ind = PhaseIndicator(tk_root, font_size_label=16, font_size_timer=14)
    ind.update("ESTERILIZACION", 2.0, 4.0)
    ind.update_approach("CALENTAMIENTO", 87.0, 134.0, "°C")
    ind.update_info("PRE_VACIO", "A 1/4")
    tk_root.update()
    ind.destroy()
