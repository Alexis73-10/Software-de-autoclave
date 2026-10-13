# Propuesta — Fase B, primer paso: arranque del backend por etapas y `GET /arranque`

Fecha: 12-oct-2026 · Estado: **para aprobación, sin código**.
Fuentes: `planeacion_barra_arranque_real.md` (§2, §5, §7, §8) y `planeacion_arranque_y_modo_sin_bd.md` (§3, §4, §5).

## 1. Referencias a `context` en `server.py` que dependen de que exista al importar

`server.py` tiene 96 referencias a `context`. Solo **tres** se ejecutan al importar o fuera de una petición. Las demás están dentro de funciones de endpoint o de helpers que llaman los endpoints, y solo fallan si llega una petición antes de tiempo (ver §1.2).

| Línea | Código | Cuándo corre | Cómo se protege |
|---|---|---|---|
| 53 | `context = BackendContext()` | Al importar. Construye todo: ciclos, perfil, hardware, serial, BD, `ControlLoop` y su arranque. | El constructor queda **sin E/S**: solo `estado` y `alarm_manager`. El resto pasa a métodos por etapa que corre el arranque (§3). Ver la decisión D-1 abajo. |
| 268 | `context.control_loop.al_cancelar_modo_prueba(_prueba_cancelada_por_paro)` | Al importar. | Se mueve al arranque: se registra en cuanto existe `control_loop` y **antes** de `control_loop.start()`, así no se pierde un paro que llegue en el primer tick. |
| 45 | `context.control_loop.stop()` (lifespan, apagado) | Al apagar. | `getattr(context, "control_loop", None)`. Si el arranque falló antes de construirlo, no hay nada que detener y no se toca la tarjeta. |

### 1.1 Dependencia oculta: las pruebas

Hay 12 archivos de prueba del backend que hacen `patch("autoclave.backend.context.BackendContext", return_value=ctx)`, importan `server` y usan `server.context` de inmediato. Entre ellos están `backend_doble.py`, `test_status_endpoint_alarms.py` y `test_backend_cycle_summary.py`.

Con la opción D-1 (a), esas pruebas siguen funcionando sin cambios:
- `context` sigue existiendo al importar, solo que ahora es barato.
- El arranque por etapas no corre al importar ni con `TestClient(app)`. Lo dispara solo `main.py` (§1.3).

### 1.2 Peticiones antes de que el contexto esté listo

Se agrega un **middleware** que responde 503 a toda ruta mientras el contexto no sea operable, con el cuerpo `{"detail": "Arranque en curso", "codigo": "arranque_en_curso"}`. Mismo formato que `RechazoApi`. No se tocan los 90 puntos de uso uno por uno.

- Rutas exentas: `GET /arranque` y `POST /ui/activity` (esta solo toca `actividad_ui`, que no depende de `context`).
- "Operable" significa que el `ControlLoop` ya está construido y arrancado. Ocurre dentro de la etapa 7, **antes** de esperar la conexión de E/S. Así, sin tarjeta, `/status` responde a los pocos segundos y la UI puede ir a la pantalla de espera con alarma a los 15 s (D-E).
- Con un fallo bloqueante antes de ese punto, todo lo demás sigue en 503 con `codigo: "arranque_fallido"`.

### 1.3 Puerto abierto antes de abrir el serial (hallazgo 1 de Code)

uvicorn corre el `lifespan` de inicio **antes** de enlazar el puerto. Si el arranque se disparara ahí y el puerto estuviera ocupado, se abriría el serial y luego el proceso moriría.

Propuesta: `main.py` usa `uvicorn.Server(config)` en vez de `uvicorn.run(...)` y un hilo espera a `server.started`, que solo pasa a verdadero con el socket ya enlazado. Recién entonces llama a `server_mod.iniciar_arranque()`. Si el enlace falla, uvicorn sale y el arranque nunca empieza: ni serial ni salidas. La UI lo detecta a los 20 s (`ARR_SIN_BACKEND`, fase siguiente).

## 2. Registro de etapas

Módulo nuevo `autoclave/backend/arranque/registro.py`, sin dependencias de FastAPI ni de hardware.

```python
class EstadoEtapa(str, Enum):
    OK = "ok"; EN_CURSO = "en_curso"; PENDIENTE = "pendiente"
    DEGRADADO = "degradado"; FALLO = "fallo"

@dataclass
class Etapa:
    clave: str
    peso: float
    origen: str                    # "lanzador" | "backend" | "ui"
    estado: EstadoEtapa = EstadoEtapa.PENDIENTE
    codigo: str | None = None
    t_inicio: float | None = None  # time.monotonic(); solo para log y medir pesos (D-D)
    t_fin: float | None = None

# §7 de planeacion_barra_arranque_real.md — pesos provisionales (D-D)
ETAPAS_ARRANQUE = (
    ("verificando_instalacion", 1, "lanzador"),
    ("liberando_procesos",      1, "lanzador"),
    ("iniciando_servicios",     2, "backend"),
    ("cargando_configuracion",  1, "backend"),
    ("verificando_calibracion", 1, "backend"),
    ("abriendo_base_datos",     1, "backend"),
    ("conectando_modulos_es",   2, "backend"),
    ("verificando_sensores",    2, "backend"),
    ("preparando_interfaz",     1, "ui"),
)

class RegistroArranque:
    def __init__(self, etapas=ETAPAS_ARRANQUE, reloj=time.monotonic): ...
    def iniciar(self, clave) -> None                 # pendiente -> en_curso
    def completar(self, clave) -> None               # en_curso -> ok
    def degradar(self, clave, codigo) -> None        # en_curso -> degradado
    def fallar(self, clave, codigo) -> None          # en_curso|pendiente -> fallo
    def anotar(self, clave, codigo) -> None          # código sobre una etapa en_curso (p. ej. ARR_SIN_ES reintentando)
    @property fallo_bloqueante -> bool
    @property terminado -> bool
    @property etapa_actual -> str | None
    def instantanea(self) -> dict                    # contrato §5, copia independiente
```

Reglas:
- **Hilos.** Un `threading.Lock` interno: escribe el hilo de arranque y leen los hilos de petición. `instantanea()` devuelve una copia profunda.
- **Monotonía (B-03).** `ok`, `degradado` y `fallo` son finales. Una transición inválida (p. ej. `ok → en_curso`) lanza `ValueError`, porque es un error de programación, no de campo. Los reintentos de las etapas 6 y 7 ocurren dentro de `en_curso`.
- **`falloBloqueante`.** Verdadero si alguna etapa está en `fallo`.
- **`terminado`.** Verdadero si todas las etapas con `origen != "ui"` están en `ok` o `degradado` (ver D-2).
- **`etapaActual`.** La etapa en `fallo`, si la hay. Si no, la primera en `en_curso`. Si no, la primera en `pendiente` que no sea de la UI. Es `null` si `terminado`.
- **Log.** Cada transición deja una línea con la duración (`t_fin - t_inicio`), para calibrar los pesos en el PC industrial (D-D).

El endpoint, en `server.py`, sin token y fuera del middleware: `GET /arranque` devuelve `registro.instantanea()`. El registro se crea al importar `server.py` (es barato), así que responde desde que el puerto abre.

## 3. Secuencia y clasificación (`autoclave/backend/arranque/secuencia.py`)

`ejecutar_arranque(context, registro, *, plazo_es_s=15, intentos_bd=3)` corre en un hilo daemon. Cada etapa es un método de `BackendContext` o una función pequeña. Una excepción no prevista en cualquier etapa la deja en `fallo` con el código `ARR_ERROR_INTERNO` y queda en el log con traza.

| # | Etapa | Qué hace el backend | Resultado |
|---|---|---|---|
| 1 | verificando_instalacion | `get_installation_profile()` y `get_capabilities()`. El reloj sigue en el lanzador. | Sin perfil o perfil inválido: **fallo** `ARR_PERFIL` |
| 2 | liberando_procesos | Nada: es del lanzador. | `ok` al iniciar el arranque (ver D-3) |
| 3 | iniciando_servicios | El puerto ya está enlazado (§1.3). | `ok` |
| 4 | cargando_configuracion | `ConfigManager.load_config()`, `CycleManager.load_all_cycles()`, `set_default_cycle("bowe_dick")`, `_validar_configuracion()` | `global_params.json` ilegible: **fallo** `ARR_CONFIG_ILEGIBLE`. Ciclo por defecto inexistente: **fallo** `ARR_CICLO_DEFECTO`. Un JSON de ciclo corrupto: **degradado** `ARR_CICLO_CORRUPTO` (*). Valores fuera de rango: ver D-4. |
| 5 | verificando_calibracion | `Units(calibration_path())`, separado de `build_hardware` | Ausente, ilegible, vacía (**) o que no valida: **fallo** `ARR_CALIBRACION` |
| 6 | abriendo_base_datos | `DbManager()` y `SensorCalibrationAuditDB()`, hasta 3 intentos | Agotados: **degradado** `ARR_SIN_BD` (excepción pedida). Ver D-5. |
| 7 | conectando_modulos_es | `SerialLink` más `start()`, puertas, `ServicioPuertas`, `RealtimePrinter`, `CycleLogger`, `ControlLoop`, registro del aviso de paro y `start()` (contexto **operable**). Luego espera `serial.is_connected()`. | A los 15 s sin E/S: sigue `en_curso` con `codigo=ARR_SIN_ES` y reintentando (D-E), sin fallo. Al conectar: `ok`. |
| 8 | verificando_sensores | No corre hasta que la 7 esté `ok` (D-E). | Ver D-6. |
| 9 | preparando_interfaz | Nada en el backend. | Siempre `pendiente` en `/arranque` (D-2) |

(*) Hoy `CycleManager._load_from_folder` traga el error con un `print`. Agregaría una lista `cycle_manager.errores_carga` para poder degradar la etapa. Es un cambio mínimo y no altera qué ciclos se cargan.

(**) Hoy `load_config()` devuelve un `AppConfig()` con valores por defecto si el YAML está vacío. Eso es justo el "valor por defecto silencioso" que §4.5 prohíbe. Lo trataría como fallo **dentro de la etapa**, sin cambiar `load_config` para sus otros usos.

Ante un fallo bloqueante en las etapas 1, 4 o 5, la secuencia se detiene: no se abre el serial, no se construye ni arranca el `ControlLoop` y no se manda ninguna orden a la tarjeta.

## 4. Pruebas propuestas

**`tests/test_registro_arranque.py`** (puro, sin Qt ni FastAPI)
1. Las 9 etapas, en orden, con la clave, el peso y el origen de §7. Todas `pendiente` al inicio.
2. La instantánea cumple el contrato: `terminado`, `falloBloqueante`, `etapaActual` y `etapas[{clave, estado, codigo, peso}]` con sus tipos.
3. Transiciones válidas. `degradado` cuenta para `terminado`.
4. `fallo` deja `falloBloqueante=true` y `etapaActual` = la etapa fallida.
5. No hay retroceso: `ok → en_curso`, `fallo → ok` y `degradado → en_curso` lanzan `ValueError`.
6. `terminado` con las etapas 1 a 8 en `ok`/`degradado` y la 9 `pendiente`.
7. `anotar()` deja el código en una etapa `en_curso` sin marcar fallo.
8. Modificar la instantánea devuelta no altera el registro.
9. Lectura concurrente: varios hilos llaman a `instantanea()` mientras otro avanza etapas, sin excepciones ni estados mezclados.

**`tests/test_secuencia_arranque.py`** (contexto con fakes: sin serial, sin SQLite real, reloj inyectado)
1. Arranque normal: orden de etapas, `terminado` al final, `ControlLoop.start()` una sola vez y el aviso de paro registrado antes de `start()`.
2. Perfil ausente: fallo en la etapa 1 con `ARR_PERFIL`. No se crean `SerialLink` ni `ControlLoop`.
3. `global_params.json` ilegible da fallo `ARR_CONFIG_ILEGIBLE`. Sin `bowe_dick`, fallo `ARR_CICLO_DEFECTO`. Un ciclo corrupto da `degradado` y el arranque continúa.
4. Calibración ausente, YAML corrupto o YAML vacío: fallo `ARR_CALIBRACION`, sin serial.
5. BD que falla 3 veces: `degradado` con `ARR_SIN_BD` y el arranque llega al final. BD que falla 1 vez y luego abre: `ok`.
6. E/S sin conexión: a los 15 s (reloj inyectado), la etapa 7 queda `en_curso` con `ARR_SIN_ES`, sin `falloBloqueante`, la etapa 8 no empezó y el contexto ya es operable. Al conectar, la 7 pasa a `ok` y sigue la 8.
7. Una excepción inesperada en una etapa da fallo `ARR_ERROR_INTERNO`, y las etapas siguientes quedan `pendiente`.

**`tests/test_endpoint_arranque.py`** (con `backend_doble`, `TestClient`)
1. `GET /arranque` sin token responde 200 con el contrato, antes de correr el arranque.
2. Antes de que el contexto sea operable, `GET /status` y un `POST` cualquiera responden 503 con `arranque_en_curso`, y `POST /ui/activity` responde 200.
3. Con el contexto operable, `/status` responde normal.
4. Con fallo bloqueante, `/arranque` muestra `falloBloqueante=true` y el código, y el resto responde 503 con `arranque_fallido`.
5. Importar `server` no construye hardware: con `build_hardware`, `SerialLink` y `DbManager` parcheados para lanzar excepción, la importación no falla.
6. `main.py`: el arranque se dispara solo cuando `server.started` es verdadero. Con un `Server` falso que nunca enlaza, no se dispara.

**Regresión:** los 12 archivos de prueba del backend que ya existen, sin modificarlos.

## 5. Decisiones que necesito

| # | Pregunta | Recomendación |
|---|---|---|
| D-1 | (a) Mantener `context = BackendContext()` al importar, pero con un constructor sin E/S y la construcción en métodos por etapa. (b) Dejar `context = None` y asignarlo al final. | **(a).** Cumple el objetivo (nada pesado al importar, puerto desde t = 0), no hay que proteger `context is None` en 90 sitios y las 12 pruebas siguen igual. Si exiges (b), habría que tocar `backend_doble.py` y los 11 archivos que parchean `BackendContext`. |
| D-2 | La etapa 9 la completa cada UI. ¿`terminado` del backend la excluye? | Sí, se excluye (`origen="ui"`). Si no, `terminado` nunca sería verdadero en `/arranque`. El texto de §5 ("todas las etapas") quedaría como "todas las del backend y el lanzador". |
| D-3 | Etapas 1 y 2 en `/arranque` mientras el lanzador no publique `arranque_lanzador.json`. | 1: el backend la evalúa con su propia verificación del perfil, que ya hace hoy. 2: `ok` al iniciar, porque si el backend corre, el lanzador ya la pasó. Al integrar el lanzador se revisa. |
| D-4 | Configuración con valores fuera de rango (`CONFIGURACION_INVALIDA`). Hoy el backend arranca bloqueado con alarma para que la UI muestre la causa. | Etapa 4 en **fallo** `CONFIGURACION_INVALIDA` y la secuencia se detiene. La intro ya muestra el código. Se conserva `_validar_configuracion` (y su prueba) como la función que detecta el error. |
| D-5 | Etapa 6 degradada: `CycleLogger` y unos 25 endpoints usan `context.db`. El modo sin BD (§7 del plan) no entra en este paso. | Provisional hasta §7: `context.db` = objeto `BdNoDisponible`, cuyas llamadas lanzan una excepción que se traduce en 503 `sin_base_de_datos`. Además, alarma `OPERANDO_SIN_BD` con `blocks_operation=True`, porque un ciclo sin registro rompe la trazabilidad. El arranque termina y la barra se completa. ¿O prefieres que el ciclo se permita ya? |
| D-6 | Etapa 8: me pediste no tocar sensores. | Paso transitorio: `ok` inmediato en cuanto la 7 está `ok`, con un aviso en el log ("verificación de sensores §6 pendiente"). La lógica real va en otro paso. |
| D-7 | Códigos de etapa nuevos (`ARR_PERFIL`, `ARR_CONFIG_ILEGIBLE`, `ARR_CICLO_DEFECTO`, `ARR_CICLO_CORRUPTO`, `ARR_CALIBRACION`, `ARR_SIN_BD`, `ARR_SIN_ES`, `ARR_ERROR_INTERNO`). | Los uso tal cual y los anoto en `docs/catalogo_alarmas.md` como códigos de arranque. ¿O ya tienes nombres? |
| D-8 | `main.py` pasa de `uvicorn.run` a `uvicorn.Server` para disparar el arranque con el puerto ya enlazado (§1.3). Es fuera de `server.py`, pero no es UI, lanzador ni sensores. | Hacerlo: es lo que garantiza "puerto ocupado → no se abre el serial". |

## 6. Fuera de este paso
Las etapas 1 y 2 del lanzador (D-A), `ProgresoArranqueReal` en la UI, los textos `arranque.<clave>`, la verificación de sensores (§6), el modo sin BD completo (§7), la pantalla de espera a los 15 s del lado de la UI, y el ticket de arranque y el heartbeat.
