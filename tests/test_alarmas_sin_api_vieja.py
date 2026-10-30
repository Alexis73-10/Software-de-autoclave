import pathlib
import re

_SRC = pathlib.Path(__file__).resolve().parents[1] / "src" / "autoclave"
_PROHIBIDO = re.compile(
    r"alarms\.alarm import|alarms\.alarm_types|AlarmType|Alarmas_activas|"
    r"alarm_manager\.(report|clear)\(|_alarm_(report|clear)\("
)


def test_ningun_modulo_usa_la_api_vieja():
    hallazgos = [
        f"{p.relative_to(_SRC)}:{n}: {linea.strip()}"
        for p in _SRC.rglob("*.py")
        for n, linea in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
        if _PROHIBIDO.search(linea)
    ]
    assert hallazgos == []
