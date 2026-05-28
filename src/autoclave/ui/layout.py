from __future__ import annotations
import PIL.Image as Image
import customtkinter as ctk
from autoclave.utils.resources import resource_path


def is_portrait(w: int, h: int) -> bool:
    return h > w


def font_scale(w: int, h: int) -> float:
    return min(w, h) / 1080


def scaled_font(base: int, scale: float) -> int:
    return max(8, int(base * scale))


def check_orientation_changed(
    w: int, h: int, current_portrait: bool | None
) -> tuple[bool | None, bool]:
    """
    Retorna (new_portrait, should_rebuild).
    should_rebuild es True solo cuando la orientación cambió respecto a current_portrait.
    """
    if w < 100 or h < 100:
        return current_portrait, False
    portrait = h > w
    if current_portrait is None:
        return portrait, False
    return portrait, portrait != current_portrait


def load_footer_icons(scale: float) -> dict:
    """Carga CTkImage para los iconos del footer (info y settings)."""
    w = scaled_font(46, scale)
    h = scaled_font(40, scale)
    size = (w, h)

    def _ico(name):
        img = Image.open(resource_path(f"autoclave/images/{name}"))
        return ctk.CTkImage(light_image=img, dark_image=img, size=size)

    return {
        "info": _ico("info_icon.png"),
        "settings": _ico("settings_icon.png"),
    }
