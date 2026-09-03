# Subsistema de anuncios por voz — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar el subsistema de anuncios por voz descrito en `docs/mis_plans/planeacion_anuncios_voz.md`: reproducción de WAV pregenerados con cola de prioridad, un observador de flancos sobre `EstadoAutoclave`, persistencia de preferencias, endpoints REST y una vista de configuración en PySide6.

**Architecture:** `ControlLoop._tick()` gana un paso 8 no bloqueante (`AnnouncerObserver.update(estado)`) que solo *lee* estado ya publicado y llama a `Announcer.say(event_id)`. `Announcer` encola en un `heapq` protegido por `threading.Condition` y un hilo worker daemon reproduce con `sounddevice`/`soundfile`, aplicando ganancia cuadrática. Los WAV y su manifiesto de metadatos se generan en build-time (`tools/generar_audio.py`) y se cargan una sola vez en memoria al arrancar el backend.

**Tech Stack:** Python 3.11, `sounddevice`, `soundfile`, `numpy` (ya presente de forma transitiva — `numpy==2.3.5` en `requirements.lock.txt`), FastAPI, PySide6/qfluentwidgets.

## Global Constraints

- Ningún archivo Clase C (`ciclo.py`, `state_machine.py`, `alarm_manager.py`, `ser_puertas.py`) recibe llamadas de audio — ver spec §2.2. La única excepción autorizada es **publicar un atributo informativo nuevo** en `EstadoAutoclave` y en `ProtocoloFallo` (Task 5), exactamente en el mismo patrón ya usado por `fase_en_sostenimiento`/`prevacio_progreso`/`f0_acumulado` — no altera ninguna ruta de decisión.
- `Announcer.say()` nunca bloquea (spec §3.3). Ningún test de `Announcer` debe poder colgarse esperando al worker real: los tests parchean `sounddevice`.
- Timers de audio (cooldown, debounce) usan `time.monotonic()`, nunca `time.time()` (convención del repo, ver CLAUDE.md).
- Todos los textos anunciados están fijados por el catálogo (spec §4) — ningún texto se genera dinámicamente en código.
- El buzzer de hardware (`devices/buzer/buzer.py`) no se modifica.
- No existe endpoint `/audio/announce` genérico (spec §8.1) — solo los 4 endpoints listados.
- **Discrepancia de spec detectada:** §4 dice "Total: 33 archivos WAV" pero la suma real de las tablas §4.2–§4.7 da **32** eventos (5+4+4+10+4+3+2). Este plan implementa los 32 eventos con `event_id`/texto definidos explícitamente en la tabla; no se inventa un evento 33 sin especificar. Confirmar con el usuario si falta un evento en el catálogo antes de aprobar los textos definitivos (ítem V-06, no bloqueante).
- **Generación de audio real diferida:** por decisión del usuario, este plan genera WAV *placeholder* (tono sintético, no voz) vía `tools/generar_audio.py`. Sustituir por locución real (Piper TTS u otra) es un paso posterior fuera de este plan — el script y el manifiesto ya quedan listos para regenerarse con archivos reales sin cambiar ningún otro módulo.
- **Hallazgo de investigación (V-03) que ajusta el spec:** `CicloResultado` (COMPLETADO/FALLO) es un valor de retorno local de `CicloState.run()` (`state_machine/states/ciclo.py:40-46`) — **nunca se publica** en `EstadoAutoclave`. `AnnouncerObserver` deriva `cic_completado`/`fal_ciclo_abortado` combinando `estado.get_machine_state()` (transición `GlobalState`) con `estado.fase_ciclo`, sin tocar `ciclo.py`/`state_machine.py`. Igual hallazgo aplica a `fal_camara_segura` (buzzer de `protocolo_fallo.py`), resuelto en Task 5.

---

### Task 1: Persistencia de preferencias de audio

**Files:**
- Create: `src/autoclave/config/preferences.py`
- Test: `tests/test_preferences.py`

**Interfaces:**
- Consumes: nada (módulo base, sin dependencias del proyecto).
- Produces: `load_preferences(path: Path | None = None) -> dict` devuelve siempre `{"audio": {"enabled": bool, "volume": int}}` (con defaults `enabled=True, volume=80` si el archivo falta, está corrupto o tiene valores inválidos). `save_preferences(preferences: dict, path: Path | None = None) -> None` escribe atómicamente (tempfile + `os.replace`). `DEFAULT_PREFERENCES_PATH: Path` apunta a `<repo_root>/data/preferences.json` (mismo nivel que `_TICKETS_DIR` en `backend/server.py:19`, verificado: `Path(__file__).resolve().parents[3] / "data"`).

- [ ] **Step 1: Escribir los tests que fallan**

```python
# tests/test_preferences.py
import json

from autoclave.config.preferences import load_preferences, save_preferences


def test_carga_defaults_si_no_existe_archivo(tmp_path):
    prefs = load_preferences(tmp_path / "no_existe.json")
    assert prefs == {"audio": {"enabled": True, "volume": 80}}


def test_carga_defaults_si_json_corrupto(tmp_path):
    path = tmp_path / "preferences.json"
    path.write_text("{esto no es json", encoding="utf-8")
    prefs = load_preferences(path)
    assert prefs == {"audio": {"enabled": True, "volume": 80}}


def test_volumen_fuera_de_rango_usa_default(tmp_path):
    path = tmp_path / "preferences.json"
    path.write_text(json.dumps({"audio": {"enabled": False, "volume": 500}}), encoding="utf-8")
    prefs = load_preferences(path)
    assert prefs == {"audio": {"enabled": False, "volume": 80}}


def test_guardar_y_recargar_conserva_valores(tmp_path):
    path = tmp_path / "preferences.json"
    save_preferences({"audio": {"enabled": False, "volume": 42}}, path)
    assert load_preferences(path) == {"audio": {"enabled": False, "volume": 42}}


def test_guardar_es_atomico_no_deja_archivos_temporales(tmp_path):
    path = tmp_path / "preferences.json"
    save_preferences({"audio": {"enabled": True, "volume": 10}}, path)
    restantes = list(tmp_path.iterdir())
    assert restantes == [path]
```

- [ ] **Step 2: Ejecutar y confirmar que fallan**

Run: `pytest tests/test_preferences.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'autoclave.config.preferences'`

- [ ] **Step 3: Implementar `preferences.py`**

```python
# src/autoclave/config/preferences.py
import json
import os
import tempfile
from pathlib import Path

DEFAULT_PREFERENCES_PATH = Path(__file__).resolve().parents[3] / "data" / "preferences.json"

_DEFAULTS = {"enabled": True, "volume": 80}


def load_preferences(path: Path | None = None) -> dict:
    path = path or DEFAULT_PREFERENCES_PATH
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        data = {}

    audio = data.get("audio", {}) if isinstance(data, dict) else {}
    enabled = audio.get("enabled", _DEFAULTS["enabled"])
    volume = audio.get("volume", _DEFAULTS["volume"])

    if not isinstance(enabled, bool):
        enabled = _DEFAULTS["enabled"]
    if not isinstance(volume, int) or isinstance(volume, bool) or not (0 <= volume <= 100):
        volume = _DEFAULTS["volume"]

    return {"audio": {"enabled": enabled, "volume": volume}}


def save_preferences(preferences: dict, path: Path | None = None) -> None:
    path = path or DEFAULT_PREFERENCES_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=".preferences_", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(preferences, f, indent=2, ensure_ascii=False)
        os.replace(tmp_name, path)
    except BaseException:
        if os.path.exists(tmp_name):
            os.remove(tmp_name)
        raise
```

- [ ] **Step 4: Ejecutar y confirmar que pasan**

Run: `pytest tests/test_preferences.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add src/autoclave/config/preferences.py tests/test_preferences.py
git commit -m "feat(audio): persistencia atomica de preferencias de audio"
```

---

### Task 2: Carga y validación del manifiesto de audio

**Files:**
- Create: `src/autoclave/devices/audio/__init__.py` (vacío)
- Create: `src/autoclave/devices/audio/manifest.py`
- Test: `tests/test_audio_manifest.py`

**Interfaces:**
- Consumes: nada del proyecto (usa `soundfile`, stdlib).
- Produces: `EventoAudio` (dataclass: `event_id: str`, `prioridad: int`, `cooldown_s: float`, `texto: str`, `samples` (`numpy.ndarray` float32 mono), `sample_rate: int`). `load_manifest(manifest_path: Path, idioma: str = "es") -> dict[str, EventoAudio]`. `class ManifestError(Exception)`.

- [ ] **Step 1: Escribir los tests que fallan**

```python
# tests/test_audio_manifest.py
import hashlib
import json

import numpy as np
import pytest
import soundfile as sf

from autoclave.devices.audio.manifest import ManifestError, load_manifest


def _escribir_wav(path, duracion_s=0.1, sample_rate=22050):
    t = np.linspace(0, duracion_s, int(sample_rate * duracion_s), endpoint=False)
    onda = (0.1 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    sf.write(path, onda, sample_rate, subtype="PCM_16")
    return path


def _manifest_valido(tmp_path):
    audio_dir = tmp_path / "es"
    audio_dir.mkdir()
    wav_path = _escribir_wav(audio_dir / "evt_test.wav")
    sha256 = hashlib.sha256(wav_path.read_bytes()).hexdigest()
    manifest = {
        "version": "1.0",
        "idioma_default": "es",
        "eventos": {
            "evt_test": {
                "prioridad": 3,
                "cooldown_s": 5,
                "texto": "Evento de prueba.",
                "archivos": {"es": "es/evt_test.wav"},
                "sha256": {"es": sha256},
            }
        },
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return manifest_path


def test_carga_evento_valido(tmp_path):
    eventos = load_manifest(_manifest_valido(tmp_path))
    assert set(eventos) == {"evt_test"}
    evt = eventos["evt_test"]
    assert evt.event_id == "evt_test"
    assert evt.prioridad == 3
    assert evt.cooldown_s == 5
    assert evt.texto == "Evento de prueba."
    assert evt.sample_rate == 22050
    assert len(evt.samples) > 0


def test_manifest_inexistente_lanza_manifest_error(tmp_path):
    with pytest.raises(ManifestError):
        load_manifest(tmp_path / "no_existe.json")


def test_wav_faltante_lanza_manifest_error(tmp_path):
    manifest_path = _manifest_valido(tmp_path)
    (tmp_path / "es" / "evt_test.wav").unlink()
    with pytest.raises(ManifestError):
        load_manifest(manifest_path)


def test_sha256_incorrecto_lanza_manifest_error(tmp_path):
    manifest_path = _manifest_valido(tmp_path)
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data["eventos"]["evt_test"]["sha256"]["es"] = "0" * 64
    manifest_path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ManifestError):
        load_manifest(manifest_path)
```

- [ ] **Step 2: Ejecutar y confirmar que fallan**

Run: `pytest tests/test_audio_manifest.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'autoclave.devices.audio'`

- [ ] **Step 3: Implementar `manifest.py`**

```python
# src/autoclave/devices/audio/manifest.py
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import soundfile as sf


class ManifestError(Exception):
    pass


@dataclass
class EventoAudio:
    event_id: str
    prioridad: int
    cooldown_s: float
    texto: str
    samples: object
    sample_rate: int


def load_manifest(manifest_path: Path, idioma: str = "es") -> dict:
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError) as exc:
        raise ManifestError(f"No se pudo leer el manifiesto: {exc}") from exc

    eventos = {}
    base_dir = Path(manifest_path).parent

    for event_id, meta in data.get("eventos", {}).items():
        archivo = meta.get("archivos", {}).get(idioma)
        if not archivo:
            raise ManifestError(f"Evento sin archivo para idioma '{idioma}': {event_id}")

        wav_path = base_dir / archivo
        try:
            raw = wav_path.read_bytes()
        except OSError as exc:
            raise ManifestError(f"Archivo faltante para '{event_id}': {wav_path}") from exc

        sha_esperado = meta.get("sha256", {}).get(idioma)
        sha_real = hashlib.sha256(raw).hexdigest()
        if sha_esperado and sha_real != sha_esperado:
            raise ManifestError(f"SHA-256 no coincide para '{event_id}'")

        try:
            samples, sample_rate = sf.read(wav_path, dtype="float32")
        except Exception as exc:
            raise ManifestError(f"No se pudo decodificar '{event_id}': {exc}") from exc

        eventos[event_id] = EventoAudio(
            event_id=event_id,
            prioridad=int(meta["prioridad"]),
            cooldown_s=float(meta["cooldown_s"]),
            texto=meta.get("texto", ""),
            samples=samples,
            sample_rate=sample_rate,
        )

    return eventos
```

- [ ] **Step 4: Ejecutar y confirmar que pasan**

Run: `pytest tests/test_audio_manifest.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/autoclave/devices/audio/__init__.py src/autoclave/devices/audio/manifest.py tests/test_audio_manifest.py
git commit -m "feat(audio): carga y validacion de manifiesto de audio"
```

---

### Task 3: `Announcer` — cola de prioridad, worker, ganancia

**Files:**
- Create: `src/autoclave/devices/audio/announcer.py`
- Test: `tests/test_announcer.py`

**Interfaces:**
- Consumes: `EventoAudio`/`load_manifest` de Task 2 (por su forma: `dict[str, EventoAudio]` con `.prioridad`, `.cooldown_s`, `.samples`, `.sample_rate`).
- Produces: `class Announcer(eventos: dict, get_volume: Callable[[], int], get_enabled: Callable[[], bool], on_fallo_persistente: Callable[[], None] | None = None)` con métodos `.start()`, `.stop()`, `.say(event_id: str) -> None` (no bloqueante), `.disable_now() -> None` (vacía cola y aborta reproducción en curso). Usado por `AnnouncerObserver` (Task 6) y por los endpoints (Task 8).

- [ ] **Step 1: Escribir los tests que fallan**

```python
# tests/test_announcer.py
import time
from unittest.mock import MagicMock, patch

from autoclave.devices.audio.announcer import Announcer


def _evento(event_id, prioridad, cooldown_s=5.0):
    ev = MagicMock()
    ev.event_id = event_id
    ev.prioridad = prioridad
    ev.cooldown_s = cooldown_s
    ev.samples = [0.0, 0.0]
    ev.sample_rate = 22050
    return ev


def _make_announcer(eventos, enabled=True, volume=80):
    return Announcer(
        eventos={e.event_id: e for e in eventos},
        get_volume=lambda: volume,
        get_enabled=lambda: enabled,
    )


@patch("autoclave.devices.audio.announcer.sd")
def test_say_retorna_de_inmediato_sin_bloquear(mock_sd):
    ev = _evento("a", prioridad=4)
    announcer = _make_announcer([ev])
    inicio = time.monotonic()
    announcer.say("a")
    assert time.monotonic() - inicio < 0.05


@patch("autoclave.devices.audio.announcer.sd")
def test_reproduce_evento_encolado(mock_sd):
    ev = _evento("a", prioridad=4)
    announcer = _make_announcer([ev])
    announcer.start()
    try:
        announcer.say("a")
        time.sleep(0.2)
        assert mock_sd.play.called
    finally:
        announcer.stop()


@patch("autoclave.devices.audio.announcer.sd")
def test_evento_desconocido_se_ignora(mock_sd):
    announcer = _make_announcer([])
    announcer.say("no_existe")  # no debe lanzar


@patch("autoclave.devices.audio.announcer.sd")
def test_deshabilitado_no_encola(mock_sd):
    ev = _evento("a", prioridad=4)
    announcer = _make_announcer([ev], enabled=False)
    announcer.start()
    try:
        announcer.say("a")
        time.sleep(0.2)
        assert not mock_sd.play.called
    finally:
        announcer.stop()


@patch("autoclave.devices.audio.announcer.sd")
def test_cooldown_descarta_repeticion_inmediata(mock_sd):
    ev = _evento("a", prioridad=4, cooldown_s=60.0)
    announcer = _make_announcer([ev])
    announcer.start()
    try:
        announcer.say("a")
        time.sleep(0.15)
        mock_sd.play.reset_mock()
        announcer.say("a")
        time.sleep(0.15)
        assert not mock_sd.play.called
    finally:
        announcer.stop()


@patch("autoclave.devices.audio.announcer.sd")
def test_evento_mas_urgente_interrumpe_al_que_suena(mock_sd):
    lento = _evento("lento", prioridad=3)
    urgente = _evento("urgente", prioridad=0)
    announcer = _make_announcer([lento, urgente])

    # Simula reproducción en curso: sd.wait() no retorna hasta que el test lo libere
    liberar = __import__("threading").Event()
    mock_sd.wait.side_effect = lambda: liberar.wait(2)

    announcer.start()
    try:
        announcer.say("lento")
        time.sleep(0.15)  # da tiempo a que el worker entre a sd.play/sd.wait
        announcer.say("urgente")
        time.sleep(0.05)
        assert mock_sd.stop.called
    finally:
        liberar.set()
        announcer.stop()


@patch("autoclave.devices.audio.announcer.sd")
def test_ganancia_cuadratica_se_aplica_al_volumen(mock_sd):
    import numpy as np
    ev = _evento("a", prioridad=4)
    ev.samples = np.array([1.0, 1.0], dtype=np.float32)
    announcer = _make_announcer([ev], volume=50)
    announcer.start()
    try:
        announcer.say("a")
        time.sleep(0.2)
        muestras_enviadas = mock_sd.play.call_args[0][0]
        assert abs(muestras_enviadas[0] - (0.5 ** 2.0)) < 1e-6
    finally:
        announcer.stop()
```

- [ ] **Step 2: Ejecutar y confirmar que fallan**

Run: `pytest tests/test_announcer.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'autoclave.devices.audio.announcer'`

- [ ] **Step 3: Implementar `announcer.py`**

```python
# src/autoclave/devices/audio/announcer.py
import heapq
import itertools
import logging
import threading
import time

import sounddevice as sd

logger = logging.getLogger(__name__)

_MAX_COLA = 10


class Announcer:
    def __init__(self, eventos, get_volume, get_enabled, on_fallo_persistente=None):
        self._eventos = eventos
        self._get_volume = get_volume
        self._get_enabled = get_enabled
        self._on_fallo_persistente = on_fallo_persistente

        self._lock = threading.Lock()
        self._cond = threading.Condition(self._lock)
        self._cola = []
        self._encolados = set()
        self._contador = itertools.count()
        self._ultimo_reproducido = {}
        self._prioridad_sonando = None
        self._fallos_consecutivos = 0

        self._detener = threading.Event()
        self._worker = threading.Thread(target=self._run, name="Announcer", daemon=True)

    def start(self):
        self._worker.start()

    def stop(self):
        self._detener.set()
        with self._cond:
            self._cond.notify_all()
        sd.stop()
        if self._worker.is_alive():
            self._worker.join(timeout=2)

    def say(self, event_id: str) -> None:
        evento = self._eventos.get(event_id)
        if evento is None or not self._get_enabled():
            return

        now = time.monotonic()
        with self._cond:
            ultimo = self._ultimo_reproducido.get(event_id)
            if ultimo is not None and now - ultimo < evento.cooldown_s:
                return
            if event_id in self._encolados:
                return

            if self._prioridad_sonando is not None and evento.prioridad < self._prioridad_sonando:
                sd.stop()

            if len(self._cola) >= _MAX_COLA:
                peor = max(self._cola)
                if evento.prioridad < peor[0]:
                    self._cola.remove(peor)
                    self._encolados.discard(peor[2])
                    heapq.heapify(self._cola)
                    logger.warning("Announcer: cola llena, se descarta %s", peor[2])
                else:
                    logger.warning("Announcer: cola llena, se descarta %s", event_id)
                    return

            heapq.heappush(self._cola, (evento.prioridad, next(self._contador), event_id))
            self._encolados.add(event_id)
            self._cond.notify_all()

    def disable_now(self) -> None:
        with self._cond:
            for _, _, event_id in self._cola:
                self._encolados.discard(event_id)
            self._cola.clear()
        sd.stop()

    def _run(self):
        while not self._detener.is_set():
            with self._cond:
                while not self._cola and not self._detener.is_set():
                    self._cond.wait()
                if self._detener.is_set():
                    return
                prioridad, _, event_id = heapq.heappop(self._cola)
                self._encolados.discard(event_id)
                self._prioridad_sonando = prioridad
                self._ultimo_reproducido[event_id] = time.monotonic()

            evento = self._eventos[event_id]
            try:
                volumen = max(0, min(100, self._get_volume()))
                ganancia = (volumen / 100) ** 2.0
                sd.play(evento.samples * ganancia, evento.sample_rate)
                sd.wait()
                self._fallos_consecutivos = 0
            except Exception as exc:
                self._fallos_consecutivos += 1
                logger.warning("Announcer: fallo de reproduccion (%s): %s", event_id, exc)
                if self._fallos_consecutivos >= 3 and self._on_fallo_persistente:
                    self._on_fallo_persistente()
            finally:
                with self._cond:
                    self._prioridad_sonando = None
```

- [ ] **Step 4: Ejecutar y confirmar que pasan**

Run: `pytest tests/test_announcer.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add src/autoclave/devices/audio/announcer.py tests/test_announcer.py
git commit -m "feat(audio): cola de prioridad Announcer con worker no bloqueante"
```

---

### Task 4: Generación de audios placeholder y manifiesto real

**Files:**
- Create: `conftest.py` (en la raíz del repo — no existe todavía; `tools/` tampoco tiene `__init__.py` hoy y nunca se importó como paquete en un test, así que sin esto `from tools.generar_audio import ...` no es fiable: no hay instalación editable que cubra `tools/`, solo `src/` vía `[tool.setuptools.packages.find] where = ["src"]` en `pyproject.toml`, y ni `tests/` ni la raíz tienen otro mecanismo que agregue la raíz del repo a `sys.path`)
- Create: `tools/__init__.py` (vacío — convierte `tools/` en paquete explícito; hoy es un directorio plano con scripts sueltos)
- Create: `tools/generar_audio.py`
- Test: `tests/test_generar_audio.py`

**Interfaces:**
- Consumes: `numpy`, `soundfile` (stdlib + libs ya usadas por Task 2/3).
- Produces: `CATALOGO: list[tuple[str, int, str]]` (event_id, prioridad, texto — los 32 eventos de spec §4.2-§4.7, ver nota de discrepancia en Global Constraints). `generar(output_dir: Path) -> None` escribe `output_dir/es/<event_id>.wav` y `output_dir/manifest.json`, consumibles directamente por `load_manifest` de Task 2.

- [ ] **Step 0: Hacer que la raíz del repo sea importable como paquete para los tests**

```python
# conftest.py (raíz del repo)
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
```

```python
# tools/__init__.py
```

Run: `pytest tests/test_control_loop_f0.py -v` (cualquier suite existente, solo para confirmar que agregar `conftest.py` en la raíz no rompe nada ya en verde)
Expected: passed, sin cambios respecto al comportamiento previo.

- [ ] **Step 1: Escribir el test que falla**

```python
# tests/test_generar_audio.py
import json

from tools.generar_audio import CATALOGO, generar
from autoclave.devices.audio.manifest import load_manifest

_PRIORIDADES_VALIDAS = {0, 1, 2, 3, 4, 5}


def test_catalogo_tiene_32_eventos_unicos():
    ids = [event_id for event_id, _, _ in CATALOGO]
    assert len(ids) == 32
    assert len(set(ids)) == 32


def test_catalogo_prioridades_validas():
    for _, prioridad, _ in CATALOGO:
        assert prioridad in _PRIORIDADES_VALIDAS


def test_generar_produce_manifiesto_cargable(tmp_path):
    generar(tmp_path)
    eventos = load_manifest(tmp_path / "manifest.json")
    assert set(eventos) == {event_id for event_id, _, _ in CATALOGO}


def test_generar_produce_archivos_wav_para_cada_evento(tmp_path):
    generar(tmp_path)
    for event_id, _, _ in CATALOGO:
        assert (tmp_path / "es" / f"{event_id}.wav").exists()


def test_manifest_tiene_texto_por_evento(tmp_path):
    generar(tmp_path)
    data = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    for event_id, _, texto in CATALOGO:
        assert data["eventos"][event_id]["texto"] == texto
```

- [ ] **Step 2: Ejecutar y confirmar que falla**

Run: `pytest tests/test_generar_audio.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'tools.generar_audio'`

- [ ] **Step 3: Implementar `tools/generar_audio.py`**

```python
# tools/generar_audio.py
#
# Genera WAV placeholder (tono sintetico, NO locucion real) y el
# manifest.json correspondiente. Sustituir por locucion real (Piper TTS
# u otra) es un paso posterior: basta con reemplazar los .wav y volver a
# correr este script para regenerar el manifiesto con los sha256 nuevos.
import hashlib
import json
from pathlib import Path

import numpy as np
import soundfile as sf

SAMPLE_RATE = 22050

_COOLDOWN_POR_PRIORIDAD = {0: 60, 1: 60, 2: 60, 3: 5, 4: 5, 5: 5}

# (event_id, prioridad, texto) — catalogo de spec docs/mis_plans/planeacion_anuncios_voz.md §4
CATALOGO = [
    ("emg_paro_emergencia", 0, "Paro de emergencia activado."),
    ("emg_fallo_electrico", 0, "Fallo de suministro electrico."),
    ("emg_sensor_ausente", 0, "Sensor critico ausente. Ciclo abortado."),
    ("emg_puerta_1_atrapada", 0, "Atrapamiento en puerta uno."),
    ("emg_puerta_2_atrapada", 0, "Atrapamiento en puerta dos."),
    ("fal_ciclo_abortado", 1, "Ciclo abortado por fallo."),
    ("fal_camara_segura", 1, "Camara en condiciones seguras."),
    ("fal_puerta_1_error", 1, "Fallo en puerta uno."),
    ("fal_puerta_2_error", 1, "Fallo en puerta dos."),
    ("alr_sum_agua_bomba", 2, "Falta suministro de agua de bomba."),
    ("alr_sum_agua_generador", 2, "Falta suministro de agua de generador."),
    ("alr_sum_aire_comprimido", 2, "Falta suministro de aire comprimido."),
    ("alr_sum_electrico", 2, "Alerta de suministro electrico."),
    ("alr_ai_pres_camara", 2, "Error en sensor de presion de camara."),
    ("alr_ai_pres_chaqueta", 2, "Error en sensor de presion de chaqueta."),
    ("alr_ai_pres_empaque_1", 2, "Error en sensor de presion de empaque uno."),
    ("alr_ai_pres_empaque_2", 2, "Error en sensor de presion de empaque dos."),
    ("alr_ai_temp_camara", 2, "Error en sensor de temperatura de camara."),
    ("alr_ai_temp_2_camara", 2, "Error en sensor de temperatura de camara dos."),
    ("alr_ai_temp_ref", 2, "Error en sensor de temperatura de referencia."),
    ("alr_ai_temp_chaqueta", 2, "Error en sensor de temperatura de chaqueta."),
    ("alr_ai_temp_drenaje_cam", 2, "Error en sensor de temperatura de drenaje de camara."),
    ("alr_ai_temp_drenaje", 2, "Error en sensor de temperatura de drenaje."),
    ("pta_1_abierta", 3, "Puerta uno abierta."),
    ("pta_1_cerrada", 3, "Puerta uno cerrada."),
    ("pta_2_abierta", 3, "Puerta dos abierta."),
    ("pta_2_cerrada", 3, "Puerta dos cerrada."),
    ("cic_iniciado", 4, "Ciclo iniciado."),
    ("cic_completado", 4, "Ciclo completado."),
    ("equipo_preparado", 4, "Equipo preparado."),
    ("sys_bienvenida", 5, "Bienvenido. Autoclave Especifika."),
    ("sys_prueba_audio", 5, "Prueba de audio correcta."),
]


def _tono_placeholder(duracion_s: float = 0.4):
    t = np.linspace(0, duracion_s, int(SAMPLE_RATE * duracion_s), endpoint=False)
    return (0.2 * np.sin(2 * np.pi * 440.0 * t)).astype(np.float32)


def generar(output_dir: Path) -> None:
    audio_dir = output_dir / "es"
    audio_dir.mkdir(parents=True, exist_ok=True)

    eventos = {}
    onda = _tono_placeholder()
    for event_id, prioridad, texto in CATALOGO:
        wav_path = audio_dir / f"{event_id}.wav"
        sf.write(wav_path, onda, SAMPLE_RATE, subtype="PCM_16")
        sha256 = hashlib.sha256(wav_path.read_bytes()).hexdigest()
        eventos[event_id] = {
            "prioridad": prioridad,
            "cooldown_s": _COOLDOWN_POR_PRIORIDAD[prioridad],
            "texto": texto,
            "archivos": {"es": f"es/{event_id}.wav"},
            "sha256": {"es": sha256},
        }

    manifest = {"version": "1.0", "idioma_default": "es", "eventos": eventos}
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )


if __name__ == "__main__":
    destino = Path(__file__).resolve().parents[1] / "src" / "autoclave" / "assets" / "audio"
    generar(destino)
    print(f"Generados {len(CATALOGO)} audios placeholder en {destino}")
```

- [ ] **Step 4: Ejecutar y confirmar que pasan**

Run: `pytest tests/test_generar_audio.py -v`
Expected: 5 passed

- [ ] **Step 5: Generar los assets reales del repositorio**

Run: `python tools/generar_audio.py`
Expected: imprime `Generados 32 audios placeholder en .../src/autoclave/assets/audio`, y crea `src/autoclave/assets/audio/manifest.json` + 32 archivos en `src/autoclave/assets/audio/es/`.

- [ ] **Step 6: Commit**

```bash
git add conftest.py tools/__init__.py tools/generar_audio.py tests/test_generar_audio.py src/autoclave/assets/audio/
git commit -m "feat(audio): generador de audios placeholder y manifiesto real (32 eventos)"
```

---

### Task 5: Publicar `camara_segura_confirmada` en `EstadoAutoclave`

**Files:**
- Modify: `src/autoclave/core/runtime/status.py` (agregar atributo, junto a `fase_en_sostenimiento`/`prevacio_progreso`, línea ~107-110)
- Modify: `src/autoclave/state_machine/cycle_phases/protocolo_fallo.py:36,46,212` (publicar el flag en el mismo punto donde hoy se marca `_buzzer_emitido`)
- Test: `tests/test_protocolo_fallo_camara_segura.py`

**Interfaces:**
- Consumes: `EstadoAutoclave` (Task no crea clase nueva, solo agrega atributo).
- Produces: `estado.camara_segura_confirmada: bool` — `False` por defecto y en cada `ProtocoloFallo.reset()`/`__init__`, pasa a `True` en el mismo tick en que se emite el buzzer de condiciones seguras (`protocolo_fallo.py:211-212`). Consumido por `AnnouncerObserver` (Task 6) para disparar `fal_camara_segura`.

**Por qué esto no es una excepción real a "no tocar Clase C":** es exactamente el mismo patrón que ya usa el propio `protocolo_fallo.py`/`ciclo.py` para `fase_en_sostenimiento`, `prevacio_progreso`, `sub_estado_ciclo`, `f0_acumulado` — un atributo *solo publicado*, nunca leído por ninguna ruta de decisión de la fase. No cambia cuándo se dispara el buzzer ni ninguna otra salida.

- [ ] **Step 1: Escribir el test que falla**

```python
# tests/test_protocolo_fallo_camara_segura.py
from unittest.mock import MagicMock

from autoclave.state_machine.cycle_phases.protocolo_fallo import ProtocoloFallo


def _make_protocolo(pres=101.3, temp=30.0, pres_atm=101.3, rango=3.0, temp_max=40.0):
    estado = MagicMock()
    estado.camara_segura_confirmada = False
    estado.sensores_pres = {"pres_camara": pres}
    estado.sensores_temp = {"temp_camara": temp}

    set_do = MagicMock()
    cycle = MagicMock()
    cycle.get_param.side_effect = lambda seccion, nombre, default=None: {
        ("protocolo_fallo", "temp_max_apertura"): temp_max,
    }.get((seccion, nombre), default)

    return ProtocoloFallo(estado=estado, set_do=set_do, cycle=cycle, config=MagicMock()), estado


def test_estado_inicia_sin_confirmar():
    _, estado = _make_protocolo()
    assert estado.camara_segura_confirmada is False


def test_reset_vuelve_a_dejar_el_flag_en_false():
    protocolo, estado = _make_protocolo()
    estado.camara_segura_confirmada = True
    protocolo.reset()
    assert estado.camara_segura_confirmada is False
```

- [ ] **Step 2: Ejecutar y confirmar que fallan (o pasan trivialmente si el atributo aún no existe en el mock)**

Run: `pytest tests/test_protocolo_fallo_camara_segura.py -v`
Expected: puede pasar trivialmente contra el `MagicMock` (no verifica aún la escritura real) — este test se completa junto con el de integración del Step 4. Continuar.

- [ ] **Step 3: Modificar `status.py`**

En `src/autoclave/core/runtime/status.py`, dentro de `EstadoAutoclave.__init__`, junto a `self.fase_en_sostenimiento`:

```python
        # True cuando ProtocoloFallo confirmo que la camara alcanzo
        # condiciones seguras (mismo tick en que emite el buzzer de fallo).
        # Se reinicia a False en ProtocoloFallo.reset()/__init__.
        self.camara_segura_confirmada: bool = False
```

- [ ] **Step 4: Modificar `protocolo_fallo.py`**

En `__init__` (línea 36) y en `reset()` (línea 46), junto a `self._buzzer_emitido = False`:

```python
        self._buzzer_emitido  = False
        self.estado.camara_segura_confirmada = False
```

(aplicar el mismo agregado en las dos ubicaciones — `__init__` y `reset()`).

En el punto donde se marca el buzzer como emitido (línea 212):

```python
                self.set_do.buzer_fallo()
                self._buzzer_emitido = True
                self.estado.camara_segura_confirmada = True
```

- [ ] **Step 5: Añadir el test de integración (edita el archivo de Step 1, agrega esta función) y ejecutar**

```python
def test_publica_camara_segura_confirmada_al_emitir_buzzer():
    protocolo, estado = _make_protocolo(pres=101.3, temp=30.0)
    protocolo.ejecutar()
    protocolo.update()  # segun la firma real de update() en protocolo_fallo.py — ajustar args si difiere
    assert estado.camara_segura_confirmada is True
```

Run: `pytest tests/test_protocolo_fallo_camara_segura.py tests/test_protocolo_fallo_reintento.py -v`
Expected: todos pasan (el segundo archivo es la suite existente de la fase — confirma que no se rompió nada).

Nota para quien ejecute esta tarea: revisar la firma exacta de `ProtocoloFallo.update()` (no confirmada en la investigación previa — solo se confirmó `ejecutar()` y el bloque interno de la línea ~200) y ajustar los argumentos del test de integración según corresponda antes de darlo por bueno.

- [ ] **Step 6: Commit**

```bash
git add src/autoclave/core/runtime/status.py src/autoclave/state_machine/cycle_phases/protocolo_fallo.py tests/test_protocolo_fallo_camara_segura.py
git commit -m "feat(audio): publicar camara_segura_confirmada para el anunciador de voz"
```

---

### Task 6: `AnnouncerObserver` — detección de flancos

**Files:**
- Create: `src/autoclave/services/domain/audio/__init__.py` (vacío)
- Create: `src/autoclave/services/domain/audio/announcer_observer.py`
- Test: `tests/test_announcer_observer.py`

**Interfaces:**
- Consumes: `Announcer.say(event_id: str)` de Task 3. Lee `estado.Alarmas_activas` (lista de objetos con `.id`), `estado.estado_puertas` (dict `str -> DoorState`), `estado.get_machine_state() -> GlobalState`, `estado.fase_ciclo: str`, `estado.camara_segura_confirmada: bool` de Task 5.
- Produces: `class AnnouncerObserver(announcer)` con `.update(estado) -> None`, llamado desde `ControlLoop._tick()` (Task 7).

- [ ] **Step 1: Escribir los tests que fallan**

```python
# tests/test_announcer_observer.py
from unittest.mock import MagicMock

from autoclave.devices.puertas.advanced_door import DoorState
from autoclave.state_machine.machine.enum_global import GlobalState
from autoclave.services.domain.audio.announcer_observer import AnnouncerObserver


class _Alarma:
    def __init__(self, alarm_id):
        self.id = alarm_id


def _estado(machine_state=GlobalState.PREPARADO, fase_ciclo="", alarmas=None,
            puertas=None, camara_segura=False):
    e = MagicMock()
    e.get_machine_state.return_value = machine_state
    e.fase_ciclo = fase_ciclo
    e.Alarmas_activas = alarmas or []
    e.estado_puertas = puertas or {"Puerta 1": DoorState.CERRADO, "Puerta 2": DoorState.CERRADO}
    e.camara_segura_confirmada = camara_segura
    return e


def test_primer_tick_no_anuncia_nada():
    announcer = MagicMock()
    obs = AnnouncerObserver(announcer)
    obs.update(_estado())
    announcer.say.assert_not_called()


def test_alarma_nueva_dispara_evento_mapeado():
    announcer = MagicMock()
    obs = AnnouncerObserver(announcer)
    obs.update(_estado())  # siembra
    obs.update(_estado(alarmas=[_Alarma("SUMINISTRO_AGUA_BOMBA")]))
    announcer.say.assert_called_once_with("alr_sum_agua_bomba")


def test_alarma_sin_mapeo_no_dispara_nada():
    announcer = MagicMock()
    obs = AnnouncerObserver(announcer)
    obs.update(_estado())
    obs.update(_estado(alarmas=[_Alarma("NO_HAY_CONEXION")]))
    announcer.say.assert_not_called()


def test_alarma_que_sigue_activa_no_repite():
    announcer = MagicMock()
    obs = AnnouncerObserver(announcer)
    obs.update(_estado())
    obs.update(_estado(alarmas=[_Alarma("SENSOR_AUSENTE")]))
    announcer.say.reset_mock()
    obs.update(_estado(alarmas=[_Alarma("SENSOR_AUSENTE")]))
    announcer.say.assert_not_called()


def test_puerta_abriendo_a_abierto_anuncia_una_vez():
    announcer = MagicMock()
    obs = AnnouncerObserver(announcer)
    obs.update(_estado(puertas={"Puerta 1": DoorState.CERRADO, "Puerta 2": DoorState.CERRADO}))
    obs.update(_estado(puertas={"Puerta 1": DoorState.ABRIENDO, "Puerta 2": DoorState.CERRADO}))
    announcer.say.assert_not_called()  # transitorio, D-07
    obs.update(_estado(puertas={"Puerta 1": DoorState.ABIERTO, "Puerta 2": DoorState.CERRADO}))
    announcer.say.assert_called_once_with("pta_1_abierta")


def test_puerta_atrapada_dispara_emergencia():
    announcer = MagicMock()
    obs = AnnouncerObserver(announcer)
    obs.update(_estado())
    obs.update(_estado(puertas={"Puerta 1": DoorState.CERRADO, "Puerta 2": DoorState.ATRAPADA}))
    announcer.say.assert_called_once_with("emg_puerta_2_atrapada")


def test_transicion_a_ciclo_anuncia_ciclo_iniciado():
    announcer = MagicMock()
    obs = AnnouncerObserver(announcer)
    obs.update(_estado(machine_state=GlobalState.PREPARADO))
    obs.update(_estado(machine_state=GlobalState.CICLO))
    announcer.say.assert_called_once_with("cic_iniciado")


def test_ciclo_completado_anuncia_equipo_preparado_y_cic_completado():
    announcer = MagicMock()
    obs = AnnouncerObserver(announcer)
    obs.update(_estado(machine_state=GlobalState.CICLO, fase_ciclo="COMPLETADO"))
    obs.update(_estado(machine_state=GlobalState.PREPARADO, fase_ciclo="COMPLETADO"))
    llamados = {c.args[0] for c in announcer.say.call_args_list}
    assert llamados == {"equipo_preparado", "cic_completado"}


def test_ciclo_cancelado_no_anuncia_cic_completado():
    announcer = MagicMock()
    obs = AnnouncerObserver(announcer)
    obs.update(_estado(machine_state=GlobalState.CICLO, fase_ciclo="CANCELADO"))
    obs.update(_estado(machine_state=GlobalState.PREPARADO, fase_ciclo="CANCELADO"))
    llamados = {c.args[0] for c in announcer.say.call_args_list}
    assert llamados == {"equipo_preparado"}


def test_transicion_ciclo_a_falla_anuncia_fallo_de_ciclo():
    announcer = MagicMock()
    obs = AnnouncerObserver(announcer)
    obs.update(_estado(machine_state=GlobalState.CICLO))
    obs.update(_estado(machine_state=GlobalState.FALLA))
    announcer.say.assert_called_once_with("fal_ciclo_abortado")


def test_camara_segura_confirmada_dispara_una_vez():
    announcer = MagicMock()
    obs = AnnouncerObserver(announcer)
    obs.update(_estado(camara_segura=False))
    obs.update(_estado(camara_segura=True))
    announcer.say.assert_called_once_with("fal_camara_segura")
    announcer.say.reset_mock()
    obs.update(_estado(camara_segura=True))
    announcer.say.assert_not_called()


def test_equipo_de_una_puerta_no_dispara_eventos_de_puerta_2():
    announcer = MagicMock()
    obs = AnnouncerObserver(announcer)
    obs.update(_estado(puertas={"Puerta 1": DoorState.CERRADO}))
    obs.update(_estado(puertas={"Puerta 1": DoorState.ABIERTO}))
    llamados = [c.args[0] for c in announcer.say.call_args_list]
    assert all("puerta_2" not in nombre for nombre in llamados)
```

- [ ] **Step 2: Ejecutar y confirmar que fallan**

Run: `pytest tests/test_announcer_observer.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'autoclave.services.domain.audio'`

- [ ] **Step 3: Implementar `announcer_observer.py`**

```python
# src/autoclave/services/domain/audio/announcer_observer.py
from autoclave.devices.puertas.advanced_door import DoorState
from autoclave.state_machine.machine.enum_global import GlobalState

_ALARMA_A_EVENTO = {
    "PARO_EMERGENCIA": "emg_paro_emergencia",
    "FALLO_SUMINISTRO_ELECTRICO": "emg_fallo_electrico",
    "SENSOR_AUSENTE": "emg_sensor_ausente",
    "SUMINISTRO_AGUA_BOMBA": "alr_sum_agua_bomba",
    "SUMINISTRO_AGUA_GENERADOR": "alr_sum_agua_generador",
    "SUMINISTRO_AIRE_COMPRIMIDO": "alr_sum_aire_comprimido",
    "SUMINISTRO_ELECTRICO": "alr_sum_electrico",
    "ERROR_AI_PRES_CAMARA": "alr_ai_pres_camara",
    "ERROR_AI_PRES_CHAQUETA": "alr_ai_pres_chaqueta",
    "ERROR_AI_PRES_EMPAQUE_1": "alr_ai_pres_empaque_1",
    "ERROR_AI_PRES_EMPAQUE_2": "alr_ai_pres_empaque_2",
    "ERROR_AI_TEMP_CAMARA": "alr_ai_temp_camara",
    "ERROR_AI_TEMP_2_CAMARA": "alr_ai_temp_2_camara",
    "ERROR_AI_TEMP_REF": "alr_ai_temp_ref",
    "ERROR_AI_TEMP_CHAQUETA": "alr_ai_temp_chaqueta",
    "ERROR_AI_TEMP_DRENAJE_CAM": "alr_ai_temp_drenaje_cam",
    "ERROR_AI_TEMP_DRENAJE": "alr_ai_temp_drenaje",
}

_PUERTA_A_SUFIJO = {"Puerta 1": "1", "Puerta 2": "2"}
_ESTADOS_TERMINALES_PUERTA = {DoorState.ABIERTO: "abierta", DoorState.CERRADO: "cerrada"}


class AnnouncerObserver:
    def __init__(self, announcer):
        self._announcer = announcer
        self._alarmas_vistas = None
        self._puertas_previas = None
        self._machine_state_previo = None
        self._camara_segura_previo = None

    def update(self, estado) -> None:
        if self._alarmas_vistas is None:
            self._sembrar(estado)
            return

        self._detectar_alarmas(estado)
        self._detectar_puertas(estado)
        self._detectar_maquina(estado)
        self._detectar_camara_segura(estado)

    def _sembrar(self, estado) -> None:
        self._alarmas_vistas = {a.id for a in estado.Alarmas_activas}
        self._puertas_previas = dict(estado.estado_puertas)
        self._machine_state_previo = estado.get_machine_state()
        self._camara_segura_previo = bool(getattr(estado, "camara_segura_confirmada", False))

    def _detectar_alarmas(self, estado) -> None:
        activas = {a.id for a in estado.Alarmas_activas}
        for alarm_id in activas - self._alarmas_vistas:
            event_id = _ALARMA_A_EVENTO.get(alarm_id)
            if event_id:
                self._announcer.say(event_id)
        self._alarmas_vistas = activas

    def _detectar_puertas(self, estado) -> None:
        for puerta, sufijo in _PUERTA_A_SUFIJO.items():
            if puerta not in estado.estado_puertas:
                continue
            actual = estado.estado_puertas.get(puerta)
            previo = self._puertas_previas.get(puerta)
            if actual != previo:
                if actual == DoorState.ATRAPADA:
                    self._announcer.say(f"emg_puerta_{sufijo}_atrapada")
                elif actual == DoorState.ERROR:
                    self._announcer.say(f"fal_puerta_{sufijo}_error")
                elif actual in _ESTADOS_TERMINALES_PUERTA:
                    self._announcer.say(f"pta_{sufijo}_{_ESTADOS_TERMINALES_PUERTA[actual]}")
            self._puertas_previas[puerta] = actual

    def _detectar_maquina(self, estado) -> None:
        actual = estado.get_machine_state()
        previo = self._machine_state_previo
        if actual != previo:
            if actual == GlobalState.CICLO:
                self._announcer.say("cic_iniciado")
            elif actual == GlobalState.PREPARADO:
                self._announcer.say("equipo_preparado")
                if previo == GlobalState.CICLO and estado.fase_ciclo == "COMPLETADO":
                    self._announcer.say("cic_completado")
            elif actual == GlobalState.FALLA and previo == GlobalState.CICLO:
                self._announcer.say("fal_ciclo_abortado")
        self._machine_state_previo = actual

    def _detectar_camara_segura(self, estado) -> None:
        actual = bool(getattr(estado, "camara_segura_confirmada", False))
        if actual and not self._camara_segura_previo:
            self._announcer.say("fal_camara_segura")
        self._camara_segura_previo = actual
```

- [ ] **Step 4: Ejecutar y confirmar que pasan**

Run: `pytest tests/test_announcer_observer.py -v`
Expected: 11 passed

- [ ] **Step 5: Commit**

```bash
git add src/autoclave/services/domain/audio/__init__.py src/autoclave/services/domain/audio/announcer_observer.py tests/test_announcer_observer.py
git commit -m "feat(audio): AnnouncerObserver con deteccion de flancos sobre EstadoAutoclave"
```

---

### Task 7: Integración en `context.py` y `ControlLoop._tick()`

**Files:**
- Modify: `src/autoclave/backend/context.py`
- Modify: `src/autoclave/services/domain/loop/control_loop.py`
- Test: `tests/test_control_loop_audio_step.py`

**Interfaces:**
- Consumes: `Announcer`/`AnnouncerObserver` (Tasks 3/6), `load_manifest` (Task 2), `load_preferences`/`save_preferences` (Task 1), `ProtocoloFallo`/`camara_segura_confirmada` (Task 5).
- Produces: `ControlLoop.__init__(..., announcer_observer=None)` — parámetro nuevo, con default `None` para no romper las instanciaciones existentes en tests (`test_control_loop_f0.py` y similares no pasan este argumento). `BackendContext.announcer: Announcer`, `BackendContext.audio_preferences: dict` — usados por los endpoints (Task 8).

**Decisión de diseño (no especificada explícitamente en el spec, documentada aquí):** el paso 8 se pausa durante `_test_mode` igual que los pasos 3/5/7 — evita que el modo de validación en banco (`/io/test/*`) dispare anuncios de voz por manipulación manual de salidas/sensores.

- [ ] **Step 1: Escribir el test que falla**

```python
# tests/test_control_loop_audio_step.py
from unittest.mock import MagicMock, patch

from autoclave.state_machine.machine.enum_global import GlobalState


class _FakeEstado:
    def __init__(self):
        self._state = GlobalState.PREPARADO
        self.fase_ciclo = ""
        self.Alarmas_activas = []
        self.estado_puertas = {}
        self.camara_segura_confirmada = False
        self.sensores_di = {}
        self.sensores_temp = {}
        self.sensores_pres = {}
        self.salidas_do = {}
        self.flags = {}

    def get_machine_state(self):
        return self._state

    def get_flag(self, flag):
        return False

    def update(self, datos):
        pass


def _make_loop(announcer_observer):
    from autoclave.services.domain.loop.control_loop import ControlLoop

    estado = _FakeEstado()
    cycle = MagicMock()
    cycle.get_param.return_value = False
    cycle_manager = MagicMock()
    cycle_manager.get_selected_cycle.return_value = cycle

    link = MagicMock()
    link.is_connected.return_value = True

    with patch("autoclave.services.domain.loop.control_loop.StateMachine"):
        loop = ControlLoop(
            units=MagicMock(get_all=MagicMock(return_value={})),
            door_service=MagicMock(),
            doors=[],
            estado=estado,
            link=link,
            set_do=MagicMock(),
            alarm_manager=MagicMock(),
            cycle_manager=cycle_manager,
            config_manager=MagicMock(),
            announcer_observer=announcer_observer,
        )
    return loop


def test_tick_llama_al_observador_de_audio_cuando_no_esta_en_modo_prueba():
    observer = MagicMock()
    loop = _make_loop(observer)
    loop._tick()
    observer.update.assert_called_once_with(loop.estado)


def test_tick_no_llama_al_observador_en_modo_prueba():
    observer = MagicMock()
    loop = _make_loop(observer)
    loop._test_mode.set()
    loop._tick()
    observer.update.assert_not_called()


def test_tick_no_falla_si_no_hay_observador_de_audio():
    loop = _make_loop(None)
    loop._tick()  # no debe lanzar
```

- [ ] **Step 2: Ejecutar y confirmar que falla**

Run: `pytest tests/test_control_loop_audio_step.py -v`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'announcer_observer'`

- [ ] **Step 3: Modificar `control_loop.py`**

En `__init__` (línea 39-41), agregar el parámetro:

```python
    def __init__(self, units, door_service, doors, estado, link, set_do,
                 alarm_manager, cycle_manager, config_manager,
                 cycle_logger=None, interval=0.5, cap=None, realtime_printer=None,
                 announcer_observer=None):
```

Y guardarlo junto a los demás colaboradores (línea 56-57):

```python
        self.realtime_printer = realtime_printer
        self.cap             = cap
        self.announcer_observer = announcer_observer
```

En `_tick()`, después del paso 7 (línea 195-196), agregar el paso 8:

```python
        # 8. Anuncios por voz — observador no bloqueante, solo lee estado ya
        # publicado. Pausado en modo prueba por la misma razon que 3/5/7:
        # no debe reaccionar a manipulacion manual de /io/test/*.
        if not self._test_mode.is_set() and self.announcer_observer is not None:
            self.announcer_observer.update(self.estado)
```

- [ ] **Step 4: Ejecutar y confirmar que pasan (incluyendo la suite de F0 existente, para confirmar que no se rompió nada)**

Run: `pytest tests/test_control_loop_audio_step.py tests/test_control_loop_f0.py tests/test_control_loop_test_mode.py -v`
Expected: todos pasan.

- [ ] **Step 5: Modificar `context.py`**

Agregar los imports:

```python
from autoclave.config.preferences import load_preferences, save_preferences
from autoclave.devices.audio.manifest import load_manifest, ManifestError
from autoclave.devices.audio.announcer import Announcer
from autoclave.services.domain.audio.announcer_observer import AnnouncerObserver
from autoclave.state_machine.alarms.alarm import Alarm
from autoclave.state_machine.alarms.alarm_types import AlarmType
from autoclave.utils.resources import resource_path
```

En `BackendContext.__init__`, antes de construir `self.control_loop` (línea 85), agregar:

```python
        # Anuncios por voz — deshabilitado en caliente si el manifiesto no
        # carga (archivo faltante/corrupto); el equipo sigue operando (D-14).
        self.audio_preferences = load_preferences()
        try:
            eventos_audio = load_manifest(resource_path("autoclave/assets/audio/manifest.json"))
            self._audio_disponible = True
        except ManifestError as exc:
            logger.warning("Anuncios por voz deshabilitados: %s", exc)
            eventos_audio = {}
            self._audio_disponible = False

        def _reportar_audio_no_disponible():
            self._audio_disponible = False
            self.alarm_manager.report(Alarm(
                alarm_id="AUDIO_NO_DISPONIBLE",
                alarm_type=AlarmType.ALERTA,
                source_state="ANNOUNCER",
                description="Subsistema de anuncios por voz no disponible.",
                recoverable=True,
                blocks_operation=False,
            ))

        if not self._audio_disponible:
            _reportar_audio_no_disponible()

        self.announcer = Announcer(
            eventos=eventos_audio,
            get_volume=lambda: self.audio_preferences["audio"]["volume"],
            get_enabled=lambda: self.audio_preferences["audio"]["enabled"] and self._audio_disponible,
            on_fallo_persistente=_reportar_audio_no_disponible,
        )
        self.announcer.start()
        announcer_observer = AnnouncerObserver(self.announcer)
```

Y pasar `announcer_observer=announcer_observer` al constructor de `ControlLoop` (junto a los demás kwargs, línea 85-98).

- [ ] **Step 6: Ejecutar toda la suite de tests de backend para confirmar que la app sigue arrancando**

Run: `pytest tests/test_backend_calibration_endpoints.py tests/test_io_endpoints.py tests/test_status_endpoint_alarms.py -v`
Expected: todos pasan (estos tests parchean `BackendContext` completo, así que no deberían verse afectados, pero confirman que el import no rompe la carga del módulo `server.py`).

- [ ] **Step 7: Commit**

```bash
git add src/autoclave/backend/context.py src/autoclave/services/domain/loop/control_loop.py tests/test_control_loop_audio_step.py
git commit -m "feat(audio): integrar Announcer/AnnouncerObserver en ControlLoop y BackendContext"
```

---

### Task 8: Endpoints REST (`/audio/*`)

**Files:**
- Modify: `src/autoclave/backend/server.py`
- Test: `tests/test_audio_endpoints.py`

**Interfaces:**
- Consumes: `context.announcer` (`Announcer.say`/`disable_now`), `context.audio_preferences`, `context._audio_disponible` (Task 7), `save_preferences` (Task 1).
- Produces: 4 endpoints según spec §8.1.

- [ ] **Step 1: Escribir los tests que fallan**

```python
# tests/test_audio_endpoints.py
import sys
import importlib
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def audio_client(tmp_path):
    mock_ctx = MagicMock()
    mock_ctx.audio_preferences = {"audio": {"enabled": True, "volume": 80}}
    mock_ctx._audio_disponible = True
    mock_ctx.announcer = MagicMock()

    for key in list(sys.modules):
        if "autoclave.backend.server" in key:
            del sys.modules[key]

    with patch("autoclave.backend.context.BackendContext", return_value=mock_ctx):
        with patch("autoclave.config.preferences.DEFAULT_PREFERENCES_PATH", tmp_path / "preferences.json"):
            srv = importlib.import_module("autoclave.backend.server")

    from fastapi.testclient import TestClient
    return TestClient(srv.app), mock_ctx


def test_get_audio_config(audio_client):
    client, ctx = audio_client
    resp = client.get("/audio/config")
    assert resp.status_code == 200
    assert resp.json() == {"enabled": True, "volume": 80, "available": True}


def test_patch_audio_config_actualiza_volumen(audio_client):
    client, ctx = audio_client
    resp = client.patch("/audio/config", json={"volume": 42})
    assert resp.status_code == 200
    assert ctx.audio_preferences["audio"]["volume"] == 42


def test_patch_audio_config_volumen_fuera_de_rango_422(audio_client):
    client, ctx = audio_client
    resp = client.patch("/audio/config", json={"volume": 150})
    assert resp.status_code == 422
    assert ctx.audio_preferences["audio"]["volume"] == 80


def test_patch_audio_config_deshabilitar_vacia_cola(audio_client):
    client, ctx = audio_client
    resp = client.patch("/audio/config", json={"enabled": False})
    assert resp.status_code == 200
    ctx.announcer.disable_now.assert_called_once()


def test_post_audio_test_reproduce_evento(audio_client):
    client, ctx = audio_client
    resp = client.post("/audio/test")
    assert resp.status_code == 200
    ctx.announcer.say.assert_called_once_with("sys_prueba_audio")


def test_post_audio_test_reintenta_tras_fallo_previo(audio_client):
    """§7.2: tras autodeshabilitarse por 3 fallos consecutivos, el botón de
    prueba es el mecanismo de reintento — debe volver a intentar reproducir
    aunque _audio_disponible esté en False."""
    client, ctx = audio_client
    ctx._audio_disponible = False
    resp = client.post("/audio/test")
    assert resp.status_code == 200
    assert ctx._audio_disponible is True
    ctx.announcer.say.assert_called_once_with("sys_prueba_audio")


def test_post_audio_ui_ready_es_idempotente(audio_client):
    client, ctx = audio_client
    resp1 = client.post("/audio/ui-ready")
    resp2 = client.post("/audio/ui-ready")
    assert resp1.status_code == 200 and resp2.status_code == 200
    ctx.announcer.say.assert_called_once_with("sys_bienvenida")
```

- [ ] **Step 2: Ejecutar y confirmar que fallan**

Run: `pytest tests/test_audio_endpoints.py -v`
Expected: FAIL — `404 Not Found` en todos (los endpoints no existen aún).

- [ ] **Step 3: Implementar los endpoints en `server.py`**

Agregar al final de `server.py`:

```python
_ui_ready_emitido = False


@app.get("/audio/config")
def get_audio_config():
    audio = context.audio_preferences["audio"]
    return {"enabled": audio["enabled"], "volume": audio["volume"], "available": context._audio_disponible}


@app.patch("/audio/config")
def update_audio_config(body: dict = Body(...)):
    audio = context.audio_preferences["audio"]

    if "volume" in body:
        volume = body["volume"]
        if not isinstance(volume, int) or isinstance(volume, bool) or not (0 <= volume <= 100):
            raise HTTPException(status_code=422, detail="volume debe ser un entero entre 0 y 100")
        audio["volume"] = volume

    if "enabled" in body:
        enabled = body["enabled"]
        if not isinstance(enabled, bool):
            raise HTTPException(status_code=422, detail="enabled debe ser booleano")
        audio["enabled"] = enabled
        if not enabled:
            context.announcer.disable_now()

    from autoclave.config.preferences import save_preferences
    save_preferences(context.audio_preferences)

    return {"ok": True, "enabled": audio["enabled"], "volume": audio["volume"]}


@app.post("/audio/test")
def test_audio():
    # El botón de prueba es el mecanismo de reintento de campo (spec §7.2):
    # si el subsistema se autodeshabilitó por 3 fallos consecutivos, esta
    # llamada vuelve a habilitar el intento de reproducción.
    context._audio_disponible = True
    context.announcer.say("sys_prueba_audio")
    return {"ok": True}


@app.post("/audio/ui-ready")
def audio_ui_ready():
    global _ui_ready_emitido
    if not _ui_ready_emitido:
        context.announcer.say("sys_bienvenida")
        _ui_ready_emitido = True
    return {"ok": True}
```

- [ ] **Step 4: Ejecutar y confirmar que pasan**

Run: `pytest tests/test_audio_endpoints.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add src/autoclave/backend/server.py tests/test_audio_endpoints.py
git commit -m "feat(audio): endpoints REST /audio/config, /audio/test, /audio/ui-ready"
```

---

### Task 9: Vista de configuración en PySide6

**Files:**
- Create: `src/autoclave/ui_pyside/views/audio_config.py`
- Modify: `src/autoclave/ui_pyside/main_window.py`
- Test: `tests/test_audio_config_view.py`

**Interfaces:**
- Consumes: `BackendClient` (`src/autoclave/ui/service_ui/backend_client.py:6-56` — `.get(path)`, `.patch(path, body)`, `.post(path, body=None)`, todos lanzan `requests.HTTPError`/`requests.RequestException`, patrón ya usado en `params_ciclo.py:317-335`). Patrón de vista `View(nav_callback)` de `home.py`/`params_ciclo.py`.
- Produces: `class AudioConfigView(QWidget)` registrada en `MainWindowFluent._stack` como `"audio"` en el diccionario de `navigate_to`.

- [ ] **Step 1: Escribir el test que falla**

```python
# tests/test_audio_config_view.py
import sys
from unittest.mock import patch

import pytest


@pytest.fixture(scope="session", autouse=True)
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


def test_carga_config_inicial_desde_el_backend():
    from autoclave.ui_pyside.views.audio_config import AudioConfigView

    with patch(
        "autoclave.ui_pyside.views.audio_config.BackendClient.get",
        return_value={"enabled": False, "volume": 42, "available": True},
    ):
        view = AudioConfigView(nav_callback=lambda *_: None)

    assert view._chk_enabled.isChecked() is False
    assert view._slider_volume.value() == 42
    assert "disponible" in view._lbl_available.text().lower()


def test_cambiar_slider_hace_patch_de_volumen():
    from autoclave.ui_pyside.views.audio_config import AudioConfigView

    with patch(
        "autoclave.ui_pyside.views.audio_config.BackendClient.get",
        return_value={"enabled": True, "volume": 80, "available": True},
    ):
        view = AudioConfigView(nav_callback=lambda *_: None)

    with patch("autoclave.ui_pyside.views.audio_config.BackendClient.patch") as mock_patch:
        view._slider_volume.setValue(30)
        view._on_volume_released()
        mock_patch.assert_called_once_with("/audio/config", {"volume": 30})


def test_boton_probar_llama_al_endpoint_de_prueba():
    from autoclave.ui_pyside.views.audio_config import AudioConfigView

    with patch(
        "autoclave.ui_pyside.views.audio_config.BackendClient.get",
        return_value={"enabled": True, "volume": 80, "available": True},
    ):
        view = AudioConfigView(nav_callback=lambda *_: None)

    with patch("autoclave.ui_pyside.views.audio_config.BackendClient.post") as mock_post:
        view._on_test_clicked()
        mock_post.assert_called_once_with("/audio/test")


def test_backend_no_disponible_no_lanza_excepcion():
    from autoclave.ui_pyside.views.audio_config import AudioConfigView
    import requests

    with patch(
        "autoclave.ui_pyside.views.audio_config.BackendClient.get",
        side_effect=requests.RequestException("sin conexion"),
    ):
        view = AudioConfigView(nav_callback=lambda *_: None)  # no debe lanzar

    assert "sin conexión" in view._lbl_available.text().lower()
```

- [ ] **Step 2: Ejecutar y confirmar que falla**

Run: `pytest tests/test_audio_config_view.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'autoclave.ui_pyside.views.audio_config'`

- [ ] **Step 3: Implementar `audio_config.py`**

```python
# src/autoclave/ui_pyside/views/audio_config.py
import logging

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)
import requests

from autoclave.ui.service_ui.backend_client import BackendClient

logger = logging.getLogger(__name__)

_BACKEND_URL = "http://localhost:8000"


class AudioConfigView(QWidget):
    def __init__(self, nav_callback):
        super().__init__()
        self._nav = nav_callback
        self._client = BackendClient(_BACKEND_URL)
        self._cargando = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 30, 40, 30)
        layout.setSpacing(20)

        title = QLabel("Anuncios por voz")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(title)

        self._chk_enabled = QCheckBox("Anuncios por voz habilitados")
        self._chk_enabled.stateChanged.connect(self._on_enabled_changed)
        layout.addWidget(self._chk_enabled)

        vol_row = QHBoxLayout()
        vol_row.addWidget(QLabel("Volumen"))
        self._slider_volume = QSlider(Qt.Orientation.Horizontal)
        self._slider_volume.setRange(0, 100)
        self._slider_volume.sliderReleased.connect(self._on_volume_released)
        vol_row.addWidget(self._slider_volume, stretch=1)
        self._lbl_volume = QLabel("--")
        self._slider_volume.valueChanged.connect(lambda v: self._lbl_volume.setText(str(v)))
        vol_row.addWidget(self._lbl_volume)
        layout.addLayout(vol_row)

        self._lbl_available = QLabel("Estado del dispositivo: —")
        layout.addWidget(self._lbl_available)

        btn_row = QHBoxLayout()
        btn_test = QPushButton("Probar")
        btn_test.clicked.connect(self._on_test_clicked)
        btn_row.addWidget(btn_test)

        btn_back = QPushButton("Volver")
        btn_back.clicked.connect(lambda: self._nav("home"))
        btn_row.addWidget(btn_back)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        layout.addStretch()

        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh_status)
        self._refresh_timer.start(5000)
        self._refresh_status()

    def _refresh_status(self) -> None:
        try:
            data = self._client.get("/audio/config")
        except requests.RequestException:
            self._lbl_available.setText("Estado del dispositivo: sin conexión con el backend")
            return

        self._cargando = True
        self._chk_enabled.setChecked(bool(data.get("enabled", True)))
        self._slider_volume.setValue(int(data.get("volume", 80)))
        self._lbl_volume.setText(str(int(data.get("volume", 80))))
        self._cargando = False

        disponible = bool(data.get("available", True))
        self._lbl_available.setText(
            "Estado del dispositivo: disponible" if disponible
            else "Estado del dispositivo: NO disponible"
        )

    def _on_enabled_changed(self, _state) -> None:
        if self._cargando:
            return
        try:
            self._client.patch("/audio/config", {"enabled": self._chk_enabled.isChecked()})
        except requests.RequestException as e:
            logger.warning("No se pudo actualizar 'enabled' de audio: %s", e)

    def _on_volume_released(self) -> None:
        if self._cargando:
            return
        try:
            self._client.patch("/audio/config", {"volume": self._slider_volume.value()})
        except requests.RequestException as e:
            logger.warning("No se pudo actualizar 'volume' de audio: %s", e)

    def _on_test_clicked(self) -> None:
        try:
            self._client.post("/audio/test")
        except requests.RequestException as e:
            logger.warning("No se pudo probar el audio: %s", e)
```

- [ ] **Step 4: Ejecutar y confirmar que pasan**

Run: `pytest tests/test_audio_config_view.py -v`
Expected: 4 passed

- [ ] **Step 5: Registrar la vista en `main_window.py`**

Agregar el import junto a los demás (línea 51):

```python
        from autoclave.ui_pyside.views.audio_config import AudioConfigView
```

Instanciar junto a las demás vistas (línea 65-66):

```python
        self._audio_config = AudioConfigView(nav_callback=self.navigate_to)
```

Agregar a la tupla de `addWidget` (línea 68-71) y al diccionario de `navigate_to` (línea 178-180):

```python
        views = {
            "home":         self._home,
            "audio":        self._audio_config,
            ...
        }
```

- [ ] **Step 6: Ejecutar la suite de navegación existente para confirmar que no se rompió nada**

Run: `pytest tests/test_main_window_navigate_payload.py -v`
Expected: passed

- [ ] **Step 7: Commit**

```bash
git add src/autoclave/ui_pyside/views/audio_config.py src/autoclave/ui_pyside/main_window.py tests/test_audio_config_view.py
git commit -m "feat(audio): vista de configuracion de anuncios por voz en PySide6"
```

---

### Task 10: Bienvenida al arrancar la UI

**Files:**
- Modify: `src/autoclave/main.py`
- Test: `tests/test_main_hardware_wait.py` (extender la suite existente en vez de crear una nueva — ya cubre el flujo de arranque de `main.py`)

**Interfaces:**
- Consumes: `BACKEND_URL` ya definido en `main.py:20`, endpoint `POST /audio/ui-ready` (Task 8).

- [ ] **Step 1: Escribir el test que falla**

`tests/test_main_hardware_wait.py` ya sigue el patrón `patch("autoclave.main.requests.get", ...)` para las funciones de arranque existentes (`_hardware_connected`); el test nuevo usa el mismo patrón con `requests.post`.

```python
# agregar a tests/test_main_hardware_wait.py
from unittest.mock import patch

from autoclave import main as main_module


@patch("autoclave.main.requests.post")
def test_ui_ready_se_llama_tras_construir_la_ventana(mock_post):
    main_module.notify_ui_ready()
    mock_post.assert_called_once_with(f"{main_module.BACKEND_URL}/audio/ui-ready", timeout=2)
```

- [ ] **Step 2: Ejecutar y confirmar que falla**

Run: `pytest tests/test_main_hardware_wait.py::test_ui_ready_se_llama_tras_construir_la_ventana -v`
Expected: FAIL — `AttributeError: module 'autoclave.main' has no attribute 'notify_ui_ready'`

- [ ] **Step 3: Implementar `notify_ui_ready()` en `main.py` y llamarlo tras construir la ventana**

Agregar la función junto a `is_backend_alive`/`wait_for_backend` (línea ~28):

```python
def notify_ui_ready():
    try:
        requests.post(f"{BACKEND_URL}/audio/ui-ready", timeout=2)
    except requests.RequestException:
        logger.warning("No se pudo notificar ui-ready al backend (sin audio de bienvenida)")
```

Llamarla en `main()`, después de que `app` (la ventana principal) está construida (línea 194, antes de `app.protocol(...)`):

```python
    logger.info("UI Autoclave iniciada")
    notify_ui_ready()
    app.protocol("WM_DELETE_WINDOW", on_close)
```

- [ ] **Step 4: Ejecutar y confirmar que pasa**

Run: `pytest tests/test_main_hardware_wait.py -v`
Expected: todos pasan (incluidos los tests preexistentes del archivo).

- [ ] **Step 5: Commit**

```bash
git add src/autoclave/main.py tests/test_main_hardware_wait.py
git commit -m "feat(audio): notificar ui-ready al backend tras construir la ventana principal"
```

---

### Task 11: Dependencias del proyecto

**Files:**
- Modify: `pyproject.toml`
- Modify: `requirements.lock.txt` (regenerar, no editar a mano)

**Interfaces:** ninguna — tarea de empaquetado.

**Hallazgo de investigación (ajusta spec §10.2):** el spec dice "modificar `requirements.txt`", pero ese archivo **no existe** en el repo. Las dependencias reales del paquete se declaran en `pyproject.toml:16-29` (`[project].dependencies`); `requirements.lock.txt` es un lock generado (formato UTF-16, ver su contenido actual) que hay que regenerar con la herramienta que ya usa el proyecto para producirlo, no editar a mano.

- [ ] **Step 1: Agregar las dependencias a `pyproject.toml`**

En el bloque `dependencies` (línea 16-29), agregar junto a `"pyserial"`:

```toml
dependencies = [
  "pyserial",
  "tk",
  "pillow",
  "PyYAML",
  "ruamel.yaml",
  "SQLAlchemy",
  "pydantic",
  "PySide6",
  "PySide6-Fluent-Widgets[full]",
  "pyqtgraph",
  "keyring",
  "pywin32",
  "sounddevice",
  "soundfile",
]
```

- [ ] **Step 2: Instalar y verificar que ambas librerías cargan en este entorno Windows**

Run: `pip install sounddevice soundfile` seguido de `python -c "import sounddevice, soundfile; print('ok')"`
Expected: `ok` (ambas traen binarios precompilados para Windows — PortAudio y libsndfile respectivamente — no deberían requerir toolchain de compilación adicional).

- [ ] **Step 3: Regenerar `requirements.lock.txt` con el mismo procedimiento que generó el archivo actual**

Identificar primero cómo se generó el lock existente (buscar en `docs/`, `Makefile`, scripts de build, o preguntar al usuario si no hay evidencia clara en el repo — no se encontró el comando durante la investigación de este plan). Sea cual sea el comando, correrlo para que `sounddevice`/`soundfile` (y `numpy`, que pasa de transitiva-por-pyqtgraph a también-transitiva-por-soundfile, sin cambio real) queden reflejados con versión fijada.

- [ ] **Step 4: Ejecutar la suite completa de tests para confirmar que no se rompió nada con el cambio de dependencias**

Run: `pytest -q`
Expected: mismo resultado que antes de este plan (0 regresiones) más todos los tests nuevos de las Tasks 1-10 en verde.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml requirements.lock.txt
git commit -m "chore(audio): declarar dependencias sounddevice y soundfile"
```

---

## Verificación en campo (no automatizable, pendiente tras integrar hardware)

Corresponde a T-05 del spec (§11): confirmar audibilidad del parlante amplificado sobre el ruido ambiente de la sala de autoclaves, a la distancia habitual de trabajo del operador. Fuera del alcance de este plan de código.

## Ítems que quedan explícitamente abiertos tras este plan

- **V-06** (spec §12): aprobación del catálogo de textos por Calidad regulatoria — permite avanzar con los WAV placeholder de Task 4, pero los textos deben confirmarse (incluida la discrepancia de conteo 32 vs. 33) antes de generar locución real.
- **V-07**: confirmación formal de la clasificación IEC 62304 Clase A por el responsable de calidad regulatoria — este plan no cambia esa clasificación, pero tampoco la confirma.
- Sustitución de los WAV placeholder por locución real (Piper TTS u otra) — el manifiesto y `tools/generar_audio.py` ya quedan preparados para regenerarse sin tocar el resto del subsistema.
