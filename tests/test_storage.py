import json
import pytest
from autoclave.installation import storage
from autoclave.installation.storage import delete


def _write_fake_profile(path):
    path.write_text(json.dumps({"locked": True}), encoding="utf-8")


def test_delete_elimina_archivo_existente(tmp_path, monkeypatch):
    fake = tmp_path / "installation_profile.json"
    _write_fake_profile(fake)
    monkeypatch.setattr(storage, "INSTALLATION_FILE", fake)

    assert fake.exists()
    delete()
    assert not fake.exists()


def test_delete_sin_archivo_no_lanza_excepcion(tmp_path, monkeypatch):
    fake = tmp_path / "installation_profile.json"
    monkeypatch.setattr(storage, "INSTALLATION_FILE", fake)

    assert not fake.exists()
    delete()  # no debe lanzar


def test_save_falla_si_bloqueado_y_existe(tmp_path, monkeypatch):
    """Documenta el comportamiento existente: save lanza si locked=True y el archivo existe."""
    from autoclave.installation.storage import save
    from autoclave.installation.profile import InstallationProfile, Role
    from autoclave.installation.equipment import EquipmentClass
    from autoclave.devices.puertas.door_type import DoorType
    from datetime import datetime

    fake = tmp_path / "installation_profile.json"
    _write_fake_profile(fake)
    monkeypatch.setattr(storage, "INSTALLATION_FILE", fake)

    profile = InstallationProfile(
        machine_id="X", model_id="M", serial_number="S",
        equipment_class=EquipmentClass.MESA_B,
        door_count=1, door_type=DoorType.SIMPLE,
        cooling_level=0, door_id=1,
        role=Role.OPERATOR_FRONT,
        created_at=datetime.utcnow(),
        locked=True,
    )
    with pytest.raises(RuntimeError, match="bloqueado"):
        save(profile)


def test_delete_luego_save_funciona(tmp_path, monkeypatch):
    """Después de delete(), save() puede guardar aunque locked=True."""
    from autoclave.installation.storage import save
    from autoclave.installation.profile import InstallationProfile, Role
    from autoclave.installation.equipment import EquipmentClass
    from autoclave.devices.puertas.door_type import DoorType
    from datetime import datetime

    fake = tmp_path / "installation_profile.json"
    _write_fake_profile(fake)
    monkeypatch.setattr(storage, "INSTALLATION_FILE", fake)

    profile = InstallationProfile(
        machine_id="X", model_id="M", serial_number="SN001",
        equipment_class=EquipmentClass.MESA_B,
        door_count=1, door_type=DoorType.SIMPLE,
        cooling_level=0, door_id=1,
        role=Role.OPERATOR_FRONT,
        created_at=datetime.utcnow(),
        locked=True,
    )
    delete()
    save(profile)  # no debe lanzar
    assert fake.exists()
