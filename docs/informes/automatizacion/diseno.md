# Diseño (arquitecto): instalación por automatización

Fuente: informe del arquitecto sobre `plan.md` y las decisiones de Cristian. Rama `automatizacion-instalacion`. Los implementadores deben seguir este documento; si el código real lo contradice, parar y reportar.

## Decisiones de Cristian (fijas)

- v1 (12 car.) y v2 (48 car.) conviven; se distinguen por longitud exacta tras `normalizar_codigo`. Fabricación acepta v1 o v2. Automatización solo `INSA`/`REIA` v2.
- `serial_number` del perfil = `SNAANNNN` (identidad; el respaldo `otra_serie` depende de él). `model_id` sigue siendo el calculado y `validate_profile_data` no se relaja.
- Campos nuevos del perfil: `tipo_instalacion`, `serial_original`, `modelo_original` (+ `sello_identidad`).
- De v2 solo se verifica el código: NO se guardan K_e ni lic/P/G/ventana/orig. El formato `^SN[0-9]{6}$` se exige solo con v2.
- Ciclos: `serie`/`modelo` conservan significado; columnas nuevas NULL `serie_original`, `modelo_original`.
- Originales se muestran en su forma normalizada (mayúsculas), que es la firmada.

## (1) Secretos v1 + v2

- Recurso: `config/activacion_transporte.json` (fuera de `autoclave/config`, como el v1, `secretos.py:23-25`), formato del generador: `{"version":2,"transporte":"<64 hex>","huella_maestro":"<8 hex>"}` (`generador_especifika/src/generador/secretos/nucleo.py:270-274`). Desarrollo: `%USERPROFILE%\Documents\especifika_secretos\activacion_v2.json` o variable `ESPECIFIKA_TRANSPORTE`. El `activacion.json` v1 no se toca.
- `secretos.py` (solo aditivo): `RECURSO_TRANSPORTE`, `ruta_archivo_transporte()`, `leer_transporte(ruta) -> bytes` (versión 2, 64 hex → 32 bytes), `entrada_compilacion_transporte()`. `decodificar`, `leer_archivo`, `entrada_compilacion` no cambian.
- Carga en ejecución en `installation/activacion_v2.py` con caché perezosa propia (`_k_t`, lock, aviso una vez) y `configurar_transporte(k_t|None)` solo para pruebas. No comparte estado con `activation._cargar`. Sin K_t: todo código de 48 car. da `sin_transporte` (falla cerrado); v1 y fabricación siguen igual; un perfil de automatización no carga.
- Empaquetado: `a.datas.append(entrada_compilacion_transporte())` tras `Autoclave.spec:156` y `AutoclaveBackend.spec:90`, y en `AutoclaveSettings.spec` (carga el perfil). Sin archivo válido la compilación se detiene (criterio LIC-01, `secretos.py:79-90`); solo se imprime la huella.
- K_t de prueba (§7.1 `6578a999…9857`) fuera de producción en 3 capas: `entrada_compilacion_transporte()` se niega (SystemExit) si coincide; `tools/verificar_entrega_neutra.py` lee `_internal/config/activacion_transporte.json` y falla si es el de prueba o falta; prueba unitaria de ambas guardas.

## (2) BD de ciclos

- `_migracion_v12` en el mecanismo `PRAGMA user_version` (`db_manager.py:171-230`, tupla `:424-438`), patrón de v2 (`:201-210`): `PRAGMA table_info` y `ALTER TABLE ciclos ADD COLUMN serie_original TEXT` / `modelo_original TEXT`, sin DEFAULT. Aditiva e idempotente.
- Escritura: `crear_ciclo(..., serie_original=None, modelo_original=None)` (`:944-989`); `importar_ciclo_respaldo` lee `encabezado.get("serie_original")`/`modelo_original` (`:1034-1060`); `cycle_logger.py:442-443,472-473,517-518` los toman del perfil con `getattr(..., None)` y los escriben en el encabezado JSONL del respaldo.
- Lectura: consultas `SELECT *`, sin tocar SQL. Ayudante puro `installation/identidad.py`: `identidad_visible(serie, modelo, serie_original, modelo_original) -> {modelo, serie, serial_especifika|None}` (con original: principal = original + serial Especifika; sin él, como hoy).
- Qué lee cada salida: del ciclo guardado: ticket de ciclo (`ticket_formatter.py:488-489`), PDF/correo de ciclo (`acciones_ciclos.py:555`), historial, `ui_pyside/views/ciclos.py:65`. Del perfil vigente: ticket de arranque (`startup_ticket.py:103-104`), `/system/info.equipo` (`sistema.py:129`), resumen/impresión de periodo (`reportes.py:254-255,313`; `acciones_ciclos.py:337,395`), correo de prueba (`reportes.py:225-227`), ticket de mantenimiento, Información del equipo (`info_equipo.py:139-140,234-238`; `info_sistema_controller.py:72-76`), `parametros_equipo_controller.py:151-152`, ciclo en curso. Sin cambios: `_comun._meta_equipo` (`_comun.py:148-153`) y el manifiesto de respaldo (`respaldo.py:79,134-135`) siguen con `SNAANNNN`.

## (3) Protección del perfil

- Campos: `tipo_instalacion` (`"fabricacion"`|`"automatizacion"`; ausente = fabricación), `serial_original`, `modelo_original` (forma normalizada), `sello_identidad`.
- `sello_identidad = HMAC(K_p, "1|{tipo}|{serial_number}|{serie_n}|{modelo_n}")`, `K_p = HMAC(K_t, "ESPK2|AUTOCLAVE|PERFIL")`, hex de 64. No se guarda el código ni K_e ni datos de licencia (guardar el código equivaldría a guardar K_e).
- `validate_profile_data` sigue puro (sin secretos): valor de `tipo_instalacion` válido; automatización exige ambos originales canónicos (`normalizar(x) == x`), sello 64 hex y `serial_number` `^SN\d{6}$`; fabricación prohíbe los tres campos y el sello. `_errores_modelo` no se toca.
- `storage.save` escribe los 4 campos solo en automatización (JSON de fabricación idéntico byte a byte). `storage.load`, solo en automatización: si `activacion_v2.verificar_sello_identidad(data)` es False o falta K_t → `ProfileValidationError`; `bootstrap.get_installation_profile` lo vuelve None → `requiere_instalacion` True, motivo `invalido` (ARR-06): el asistente abre, aparta el perfil como `.invalido-<fecha>` y se reinstala con REIA.
- `cambio_perfil.py:27`: `CAMPOS_DE_IDENTIDAD = (serial_number, machine_id, tipo_instalacion, serial_original, modelo_original, sello_identidad)` rechazados como `CAMPOS_DEL_MODELO`.
- Perfiles existentes cargan como fabricación sin sello.
- **Límite real (decirlo en el informe y el registro de riesgos):** K_t es común a todos los equipos y queda en claro en `{programa}\_internal\config\` con lectura para Usuarios. Quien tenga acceso al PC puede resellar un perfil editado y fabricar códigos INS/INSA; quitar campos y sello convierte automatización en fabricación sin detección. El sello solo frena la edición casual o accidental. Residual aceptado, igual que v1; lo resuelve L1.

## (4) Contratos

En `installation/activacion_v2.py`:

```python
class Modo(str, Enum): FABRICACION; AUTOMATIZACION
@dataclass(frozen=True)
class ResultadoCodigo: ok: bool; motivo: str|None; formato: "v1"|"v2"|None; tipo: "INS"|"REI"|None; originales: tuple[str,str]|None
def verificar_codigo_instalacion(serial, codigo, modo, serie_original=None, modelo_original=None, *,
        hoy: date|None=None, k_t: bytes|None=None,
        validar_v1=activation.validate_installation_code) -> ResultadoCodigo
def sellar_identidad(tipo, serial, serie_n, modelo_n, k_t=None) -> str
def verificar_sello_identidad(data, k_t=None) -> bool
def configurar_transporte(k_t: bytes|None) -> None   # solo pruebas
```

Despachador: (1) `normalizar_codigo` (`activation.py:92-97`); (2) longitud 12: en automatización → `v1_en_automatizacion` sin llamar a v1; en fabricación → `validar_v1(serial, codigo, hoy)`; (3) longitud 48: serial sin `^SN\d{6}$` → `serial_formato`; sin K_t → `sin_transporte`; en automatización normalizar originales (fallo → `serie_original`/`modelo_original`, no consume intento); (4) `leer_instalacion` copiado de `generador/formato/codigos.py:543-594` con motivos `formato`, `digitacion`, `tipo`, `etiqueta`, `ventana`, `rango`; (5) otra longitud → `formato`.

`construir_perfil(datos, codigo, ahora=None, verificar_codigo=verificar_codigo_instalacion, sellar=sellar_identidad)`: lee `datos["tipo_instalacion"]`, `["serial_original"]`, `["modelo_original"]`; en fabricación ignora los originales; llama al verificador con `hoy=ahora.date()`; lanza `ValueError(i18n.t(clave))`.

Slot `validarCodigo(serie, codigo, modo, serieOriginal, modeloOriginal) -> str`: devuelve "" o una clave i18n (hoy devuelve bool, `puente_instalacion.py:316-323`; `Instalacion.qml:200-201`). `instalar()` revalida todo.

i18n es/en nuevas: `instalacion.error_codigo_automatizacion` («Código inválido: revise el serial Especifika y la serie y el modelo originales»), `error_codigo_v1_automatizacion`, `error_serie_original`, `error_modelo_original`, `error_serial_v2`; `sin_transporte` usa `error_codigo` y deja ERROR en el log.

Pruebas: `configurar_transporte(K_t de prueba)`, `hoy=`, `validar_v1=`; doble `tests/helpers/codigo_doble.py` (`acepta(modo, originales)`, `rechaza(motivo)`); migrar los 8 archivos que inyectan `lambda s, c: True` (39 usos): `test_m1_puente_instalacion`, `test_t9_instalacion`, `test_g10_codigo_activacion` y otros. `equipo_instalado` agrega `tipo_instalacion`, `serie_original`, `modelo_original`.

## Orden y conjuntos (sin solape)

Fijadas las firmas de (4):
- **A:** `activacion_v2.py`, `secretos.py`, los 3 `.spec`, `tools/verificar_entrega_neutra.py`, copia de `vectores_formato_v2.json` en `tests/vectores/`, pruebas v2/transporte. INS/REI ya; INSA/REIA esperan los vectores finales del generador.
- **B:** `profile.py`, `storage.py`, `cambio_perfil.py`, pruebas de perfil (sello inyectado).
- **C:** `db_manager.py` (v12), `cycle_logger.py`, pruebas de migración y respaldo JSONL.
- Después de A y B → **D:** `puente_instalacion.py`, `Instalacion.qml`, i18n `es.json`/`en.json` (único dueño, incluye claves de E), `codigo_doble`, las 8 pruebas; vigilar `textos_caben_qml`.
- Después de B y C → **E:** `identidad.py` y salidas de (2); pasa sus claves i18n a D.
- Al final → **F:** CLAUDE.md, registro de riesgos, trazabilidad, `R_informe`.
- Revisor (opus) obligatorio en A, B y C.

## Riesgos para el registro

| Riesgo | Efecto | Mitigación |
|---|---|---|
| K_t en claro y común | Se fabrican códigos y se resellan perfiles | Residual aceptado como v1; lo resuelve L1 (DPAPI/K_e); documentar |
| Compilación sin K_t o con la de prueba | Equipo atascado en el asistente, o falsificable con vectores públicos | Compilación detenida, K9, prueba unitaria |
| Originales mal tecleados | Código rechazado | Normalización idéntica a la del generador, vectores, reemisión |
| Dos identidades en la trazabilidad | Confusión al revisar ciclos | Columnas aparte; respaldo con `SNAANNNN`; prueba de `otra_serie` |
| Automatización → fabricación borrando campos | No se detecta | Residual aceptado; `cambio_perfil` lo rechaza |
| Modelo de 80 car. en ticket de 48 columnas (`_W=48`) | Línea truncada | Partir la línea y probarlo |
| BD v12 abierta por software anterior | Ninguno esperado | `SELECT *` por nombre lo tolera |
| Texto de 13+ car. con prefijo v1 válido | Hoy pasa (`activation.py:114`) | Ahora se rechaza; cambio aceptado, anotarlo |

## Contradicciones señaladas

1. `/status.equipo` no existe; es `/system/info.equipo` (`sistema.py:129`); comprobar con `test_t15`.
2. El perfil no tiene firma/hash hoy; se crea una nueva solo para automatización.
3. «Reinstalación sigue la modalidad del perfil» no se puede imponer (el asistente aparta el perfil previo); la modalidad la decide la casilla y la garantiza REIA.
4. Spec §3.1 (`formato_codigos_v2.md:111`) retira v1 y mueve transporte a `activacion.json`; Cristian decidió convivencia con archivo aparte → pedir nota en la spec.
5. Spec §4.2 guarda K_e con DPAPI; aquí no se guarda → todo equipo instalado con v2 ahora necesitará REI/REIA cuando llegue L1.
6. Spec §5 prevé bloqueo de 5 intentos/15 min; el asistente no tiene contador (fuera de alcance; anotar).
7. «v1 como hoy» choca con detección por longitud exacta (ver riesgo del prefijo).
8. `AutoclaveSettings.spec` necesita la K_t (carga el perfil y verifica el sello).
9. REI trae `orig`, pero `created_at` sigue siendo hoy (`clock_guard`); coherente con no guardar datos de licencia.
10. La spec 2.1.0 sigue «pendiente de revisión de Cristian»; si cambia, mandan el generador y sus vectores.
