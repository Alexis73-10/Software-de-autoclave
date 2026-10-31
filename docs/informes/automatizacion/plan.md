# Plan (paso 1): instalación por automatización en el autoclave

Rama `automatizacion-instalacion` (desde `dev`). Resultado de la exploración del planeador; sin cambios de código todavía. Prompt de origen: `docs/mis_plans/prompt_claude_code_instalacion_automatizacion.md`.

## Estado real

- **v1** (`installation/activation.py:100-114`): HMAC-SHA256(secreto `instalacion`, `SERIE:AAAA-MM-DD`) en Base32, cortado a 12 caracteres, válido solo el día de emisión. La validación compara `normalizar_codigo(code)[:12]` (l.114): hoy un texto de más de 12 caracteres con prefijo válido pasa.
- Secretos: `installation/secretos.py:22` (`instalacion`, `fabrica`), recurso `config/activacion_secretos.json`, empaquetado en `packaging/Autoclave.spec:155` y `AutoclaveBackend.spec:90`.
- **El autoclave no tiene nada de v2 ni `K_t`.** El generador exporta `{"version":2,"transporte","huella_maestro"}` (`generador_especifika/src/generador/secretos/nucleo.py:253-274`), incompatible con `secretos.decodificar`.
- Único consumidor: `ui_qml/bridge/puente_instalacion.py:42,127,133,303,318` (`construir_perfil` recibe `validar_codigo` inyectable). Pruebas: `tests/test_activation.py`, `test_g10_codigo_activacion.py`, `test_l0_secretos_activacion.py`.
- El perfil **no tiene firma ni hash**.
- El módulo de licencia L1 (K_e, DPAPI, estados) no existe: FIN/EMG/EXT/SOL quedan fuera de este trabajo.

## Detección v1 / v2

Mismo alfabeto Base32 tras `normalizar_codigo`; el criterio único es la **longitud exacta**: 12 = v1, 48 = v2, cualquier otra o carácter fuera del alfabeto = inválido. El despachador exige la longitud antes de llamar a v1 (por el `[:12]`). En v2: Luhn, versión 00, tipo 1/2 (INS/INSA comparten cabecera B; REI/REIA la C; los separa el HMAC del modo). Casos límite: 11, 13, 47, 49; 12 con un 9; v1 válido con sufijo; v2 con cabecera D/E/F o versión ≠ 0.

## Archivos por paso

- **2 Verificador:** módulo nuevo `installation/activacion_v2.py` (INS/REI/INSA/REIA + normalización copiada del generador), `secretos.py` y los 2 `.spec` (cargar `K_t`), `docs/referencia/formato_codigos_v2.md`, pruebas (incluida la que falla si `K_t` empaquetado = `K_t` de prueba, §7.1). Sin `K_t`: v2 falla cerrado y v1 sigue igual.
- **3 Perfil:** `installation/profile.py:209-233` y `:272-386` (`_errores_modelo` l.254-269 sin tocar), `storage.py:20-84` (`save` omite claves opcionales vacías, l.66-71), `cambio_perfil.py:27` (agregar los 3 campos a la lista protegida).
- **4 Asistente:** `puente_instalacion.py:126-202`, `:316-323` (`validarCodigo` con modo y originales), `:258-274` (`equipo_instalado`); `Pantallas/Instalacion.qml:150-151` (código `maximo: 12` → 48 + guiones; serie `maximo: 20`), `:196-201`, `:251`; i18n `instalacion.*` es/en; cuidar `tests/helpers/textos_caben_qml.py`. El asistente no sabe si es reinstalación (el perfil anterior se aparta): REI/REIA sale de la cabecera y la variante, de la casilla.
- **5 Salidas:** `devices/printer/startup_ticket.py:103-104` (`_W=48`, partir modelos largos), `backend/rutas/reportes.py:254-255`, `backend/rutas/sistema.py:129` (`/system/info.equipo`; verificar `tests/test_t15_rutas_equivalentes.py:148`), `cycle_logger.py:442-443` y `db_manager.py:967,1039`, `info_equipo.py:139-140,233-238`, `parametros_equipo_controller.py:151-152`; también `ticket_formatter.py`, `pdf_ciclo.py`, `acciones_ciclos.py:60-65`, `info_sistema_controller.py`, `resumen_sistema.py`, `arranque_equipo.py`, `ticket_mantenimiento.py`, `ciclo_en_curso.py`.
  - **Riesgo crítico:** `_comun._meta_equipo` (l.148-153) alimenta `core/runtime/respaldo.validar_para_equipo` (rechazo `otra_serie`): su `serie` debe seguir siendo `SNAANNNN`.
- **6 Pruebas:** nuevas, más ajustes a `test_profile_validation.py`, `test_m1_puente_instalacion.py`, `test_t9_instalacion.py`, `test_t18_arranque_instalacion.py`, `test_adenda_herramientas_perfil.py`.
- **7 Docs:** `CLAUDE.md`, `docs/riesgos/registro_riesgos.md`, `R_informe.md`, `estado.md`.

## Qué se puede hacer sin los vectores del generador

Paso 3 completo; asistente con validador inyectado; paso 5; regresión v1 y de perfil; INS/REI de fabricación v2 contra los vectores V1–V3/N1–N4 (no cambian); carga de `K_t`. **Espera al generador:** vectores INSA/REIA, normalización exacta de originales, mensaje exacto, matriz cruzada, copia 2.1.0 del documento.

## Conjuntos de archivos para paralelo

A: verificador, secretos, specs. B: `profile.py`, `storage.py`, `cambio_perfil.py` y pruebas. C: `puente_instalacion.py`, `Instalacion.qml`, i18n `instalacion.*` (depende de B). D: salidas del paso 5 (depende de B; el i18n compartido lo posee C).

## Decisiones estructurales (arquitecto) y preguntas

Estructurales: esquema de secretos v1+v2; columnas de ciclos; protección del perfil; contrato de `validarCodigo`. Preguntas: ver el chat (7). Revisor obligatorio: paso 2, paso 3 y la migración de la BD de ciclos.

## Criterios de terminado

- **2:** V1–V3/N1–N4 verdes; INSA/REIA con vectores del generador; INS ≠ INSA en ambos sentidos; matriz {v1,v2}×{fab,auto}×{INS,INSA,REI,REIA}; sin `K_t` v2 falla cerrado y v1 igual; `test_arquitectura_capas.py` y la prueba de `K_t` de producción.
- **3:** perfil viejo carga como fabricación; automatización sin originales o fabricación con originales = inválido; `model_id` ajeno rechazado; `cambio_perfil` rechaza los 3 campos; JSON de fabricación sin cambios (o cambio decidido).
- **4:** casilla con validación de charset y largo; el modo elige INS o INSA sin probar ambas; mensaje propio es/en; `textos_caben` verde.
- **5:** fabricación idéntica byte a byte (ticket, PDF, `/system/info`); automatización con original + «Serial Especifika»; respaldo sigue con `SNAANNNN`; `test_t15` igual; `equipo_instalado` con campos nuevos.
- **6:** `pytest tests` verde con prueba de extremo a extremo.
- **7:** documentación, riesgo nuevo y `estado.md` al día.
