from urllib.parse import quote

from autoclave.state_machine.alarms.alarm_manager import AlarmManager
from autoclave.state_machine.alarms.catalogo import COM_01, PRE_06, PUE_02
from tests.test_status_endpoint_alarms import status_client  # noqa: F401  (fixture)


def _con_gestor(mock_ctx):
    am = AlarmManager()
    mock_ctx.alarm_manager = am
    return am


def test_reconocer_clave_con_barra_y_espacios(status_client):
    client, mock_ctx = status_client
    am = _con_gestor(mock_ctx)
    am.activar(PUE_02, origen="Puerta 1", puerta="Puerta 1", fase="Secado")
    resp = client.post(f"/alarms/{quote('PUE-02|Puerta 1', safe='')}/acknowledge",
                       json={"usuario": "cristian"})
    assert resp.status_code == 200 and resp.json() == {"ok": True}
    assert am.obtener("PUE-02|Puerta 1").reconocida_por == "cristian"


def test_reconocer_inexistente_404(status_client):
    client, mock_ctx = status_client
    _con_gestor(mock_ctx)
    assert client.post("/alarms/COM-01/acknowledge", json={"usuario": "x"}).status_code == 404


def test_reconocer_aviso_422(status_client):
    client, mock_ctx = status_client
    _con_gestor(mock_ctx).activar(PRE_06, temp=70.0, maximo=65.0)
    assert client.post("/alarms/PRE-06/acknowledge", json={"usuario": "x"}).status_code == 422


def test_reconocer_sin_usuario_422(status_client):
    client, mock_ctx = status_client
    _con_gestor(mock_ctx).activar(COM_01)
    assert client.post("/alarms/COM-01/acknowledge", json={}).status_code == 422


def test_historial_pasa_filtros_y_recorta_limite(status_client):
    client, mock_ctx = status_client
    mock_ctx.db.get_alarmas_historial.return_value = [{"codigo": "COM-01"}]
    resp = client.get("/alarms/history", params={
        "desde": "2026-10-01T00:00:00", "nivel": "ALARMA", "limite": 5000})
    assert resp.status_code == 200 and resp.json() == {"alarmas": [{"codigo": "COM-01"}]}
    mock_ctx.db.get_alarmas_historial.assert_called_once_with(
        "2026-10-01T00:00:00", None, "ALARMA", 1000)


def test_historial_rechaza_nivel_o_fecha_invalidos(status_client):
    client, _ = status_client
    assert client.get("/alarms/history", params={"nivel": "GRAVE"}).status_code == 422
    assert client.get("/alarms/history", params={"desde": "ayer"}).status_code == 422


def test_reconocer_que_pierde_la_carrera_404(status_client):
    """obtener() la encuentra pero se resuelve/borra antes de reconocer()."""
    from unittest.mock import MagicMock
    client, mock_ctx = status_client
    am = MagicMock()
    am.obtener.return_value.nivel.requiere_reconocimiento = True
    am.reconocer.return_value = False
    mock_ctx.alarm_manager = am
    resp = client.post("/alarms/COM-01/acknowledge", json={"usuario": "x"})
    assert resp.status_code == 404
    am.reconocer.assert_called_once_with("COM-01", "x")
