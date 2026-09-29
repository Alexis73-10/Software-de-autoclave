# tests/test_alarmas_domain.py
#
# Lógica pura de clasificación de alarmas por severidad (§ alarmSeverity de
# tokens.json / hallazgo UI-05 del plan de interfaz dual-pantalla). Cuatro
# niveles: 1 Informativo (toast), 2 Aviso (banner), 3 Alarma (banner
# parpadeante), 4 Fallo crítico (pantalla completa, bloqueante).

import pytest

from autoclave.ui_qml.domain.alarmas import (
    Alarma,
    presentacion_de,
    es_persistente,
    requiere_ack,
    es_bloqueante,
    alarma_bloqueante,
)


# ── clasificación por severidad (fuente: tokens.json alarmSeverity) ──────

@pytest.mark.parametrize("severidad,esperado", [
    (1, "toast"),
    (2, "banner"),
    (3, "banner-blink"),
    (4, "fullscreen"),
])
def test_presentacion_de(severidad, esperado):
    assert presentacion_de(severidad) == esperado


@pytest.mark.parametrize("severidad,esperado", [
    (1, False),
    (2, True),
    (3, True),
    (4, True),
])
def test_es_persistente(severidad, esperado):
    assert es_persistente(severidad) == esperado


@pytest.mark.parametrize("severidad,esperado", [
    (1, False),
    (2, False),
    (3, True),
    (4, True),
])
def test_requiere_ack(severidad, esperado):
    assert requiere_ack(severidad) == esperado


@pytest.mark.parametrize("severidad,esperado", [
    (1, False),
    (2, False),
    (3, False),
    (4, True),
])
def test_es_bloqueante(severidad, esperado):
    assert es_bloqueante(severidad) == esperado


def test_severidad_desconocida_lanza_value_error():
    with pytest.raises(ValueError):
        presentacion_de(5)


# ── alarma_bloqueante: cuál se muestra en pantalla completa ──────────────

def test_alarma_bloqueante_none_si_no_hay_severidad_4():
    alarmas = [
        Alarma(id="A", severidad=2, ts="2026-08-12T10:00:00Z", acked=False),
        Alarma(id="B", severidad=3, ts="2026-08-12T10:00:01Z", acked=False),
    ]
    assert alarma_bloqueante(alarmas) is None


def test_alarma_bloqueante_devuelve_la_severidad_4():
    alarmas = [
        Alarma(id="A", severidad=2, ts="2026-08-12T10:00:00Z", acked=False),
        Alarma(id="B", severidad=4, ts="2026-08-12T10:00:01Z", acked=False),
    ]
    assert alarma_bloqueante(alarmas).id == "B"


def test_alarma_bloqueante_ya_reconocida_no_bloquea():
    # Reconocida (acked=True) -> ya no debe seguir bloqueando la pantalla.
    alarmas = [
        Alarma(id="B", severidad=4, ts="2026-08-12T10:00:01Z", acked=True),
    ]
    assert alarma_bloqueante(alarmas) is None


def test_alarma_bloqueante_con_varias_devuelve_la_mas_antigua():
    # La primera en dispararse es la causa raíz -> se muestra esa primero.
    alarmas = [
        Alarma(id="mas_reciente", severidad=4, ts="2026-08-12T10:05:00Z", acked=False),
        Alarma(id="mas_antigua", severidad=4, ts="2026-08-12T10:00:00Z", acked=False),
    ]
    assert alarma_bloqueante(alarmas).id == "mas_antigua"


def test_alarma_bloqueante_lista_vacia():
    assert alarma_bloqueante([]) is None
