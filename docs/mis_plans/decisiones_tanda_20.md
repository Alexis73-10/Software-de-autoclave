# Decisiones — Tanda 20: cierre de la migración a Modbus TCP (M31-U) y Setup con Modbus (27-oct)

Fuente de verdad de la tanda: este archivo, `adenda_tanda_19_banco.md` (ADB-01 a ADB-05), `planeacion_enlace_modbus.md` (MOD-01 a MOD-17) y el informe de banco `docs/informes/banco_m31_2026-10-27.md`. Si chocan, prevalece este archivo, después la adenda.

Objetivo: al cerrar la tanda, Cristian instala la entrega (1.0.0-alpha.4) con el Setup en el PC del equipo y el software conecta con los módulos M31-U reales sin pasos manuales en Windows.

## Decisiones de Cristian (27-oct, no reabrir)

1. **Se elimina el enlace serial (ESP32)**: `SerialLink`, su configuración, el protocolo de tramas, la calibración serial, la opción `"serial"` y el firmware de la ESP32 del repositorio. **Antes de borrar nada**, copia de seguridad en el disco `G:` (ver T20-01). Sin la copia verificada no se borra.
2. **El Setup configura la red de los módulos** (paso 08 de la estación): el técnico elige el adaptador Ethernet dedicado y el Setup le pone IP fija 192.168.3.10/24 sin puerta de enlace, con respaldo y reversión al desinstalar; Reparar lo reaplica.
3. **IP del módulo fija: 192.168.3.7**, puerto 502, unidad 1. El Setup no la pregunta.
4. **Enlace Modbus fijo.** Sin página de selección en el Setup ni archivo `enlace_io.json`.
5. **El Setup prueba la conexión** con el módulo al terminar y muestra el resultado. Si falla, informa y no aborta la instalación.
6. **El Setup cambia la contraseña web del módulo.** Hoy el módulo del banco tiene usuario `admin` y una contraseña ya cambiada por Cristian. La contraseña nunca se escribe en el repositorio, en los logs ni en la línea de comandos (T20-04).
7. **AN-30 aceptado:** con Modbus, `TARJETA_MODULOS_ORDEN` o `TARJETA_WATCHDOG` en ciclo invalidan la conexión y la reconexión apaga todo; el protocolo de fallo no ventea sin conexión verificada; «NO ABRIR» se mantiene. Deja de ser DECISIÓN SIN CONFIRMAR.
8. **ADB-04 se implementa (recomendación aceptada):** si al conectar hubo que escribir algún registro de seguridad, se reinicia el módulo (0x0C1D = 0x5BB5), se espera, se reconecta y se relee toda la configuración antes de dar la conexión por verificada. Si no coincide tras el reinicio: `TARJETA_CONFIG_SEGURIDAD`. Una conexión cuyos registros ya coincidían no reinicia. Sigue pendiente la prueba aislada de banco (M-5).

## Requisitos de la tanda

### T20-01 · Copia de seguridad previa al retiro (obligatoria, primera acción después de A0)
- Destino: `G:\Respaldos_autoclave\pre_tanda20_<AAAAMMDD_HHMM>\`. `G:` es un disco externo: se comprueba al empezar B y, al terminar, se relee el bundle desde `G:` (`git bundle verify`) para confirmar que quedó escrito.
- Contenido:
  - `repo_completo.bundle`: `git bundle create ... --all` (todas las ramas y etiquetas), comprobado con `git bundle verify`;
  - `dev_<commit>.zip`: `git archive` de `dev` (incluye `Hardware/` con el firmware de la ESP32, `serial_link.py`, la calibración serial y sus pruebas);
  - `LEEME.txt`: fecha, commit de `dev`, etiqueta y cómo restaurar (`git clone repo_completo.bundle`).
- Etiqueta local anotada `respaldo-serial-pre-t20` sobre el commit de `dev` respaldado.
- Si `G:` no existe, no se puede escribir o no tiene espacio: `CERRADO.txt` con `BLOQUEADO:` y no se borra nada.

### T20-02 · Adenda del banco (ADB-01 a ADB-05)
- ADB-01: composición esperada de 5 esclavos con IDs 0 a 4: `GXAXX0A00`, `GAXXXA000`, `GXXAX00A0`, `GXXAX00A0`, `GXDXX0600` (el principal figura como esclavo 0 con sus 16 AI). Se lee un esclavo más y debe ser «NONE».
- ADB-02: el firmware se compara solo por la parte de versión, nunca por el prefijo de producto. Caso real: principal `9232-0-13`; esclavos `9286-0-10`, `9233-0-12`, `9233-0-12`, `9233-0-12`, `9304-0-10` → compatible.
- ADB-03: el ID del equipo es la MAC del principal sin separadores (`005404849DB1` en el banco). Verificar que el emparejamiento de `board_id` del perfil (FW-D7) use ese valor con Modbus.
- ADB-04: decisión 8.
- ADB-05: 0x0C37 no es bandera. Se registra su valor crudo en el diagnóstico y en el log; no se escribe, no se exige 0 y no dispara `TARJETA_WATCHDOG`. La detección del corte queda en la discrepancia (MOD-11) y la reconexión (MOD-08).
- Pruebas obligatorias con el simulador: la composición real de 5 esclavos conecta; un esclavo distinto, ausente o en otro orden da `TARJETA_VERSION_INCOMPATIBLE` / `TARJETA_MODULOS_ORDEN`; 0x0C37 con valores 100 y 105 no impide la conexión; configuración distinta → escritura, reinicio, relectura; configuración igual → sin reinicio; tras el reinicio con la configuración distinta → `TARJETA_CONFIG_SEGURIDAD`. El simulador debe modelar el reinicio (cierra conexiones y vuelve) y 0x0C37 como contador.

### T20-03 · Retiro del enlace serial
- Se borran del código: `protocols/serial_link.py`, `serial_link_config`, la selección de enlace (`config/enlace_io.py`, `enlace_io.json`), `build_serial` y la rama serial de `build_enlace`, `ADC_MAXIMO` y la conversión ADC exclusiva del serial, `config/calibration.yaml` serial, los puertos del serial en `asignacion_io.puertos()`, `_ALARMAS_PIDEN_HANDSHAKE` y el handshake de la tarjeta, la dependencia `pyserial` si nada más la usa (lista SOUP y `.spec`), y `Hardware/Comunicacion_esclava_ESP32_V2` y `_V3`.
- `EnlaceES` (`protocols/enlace.py`) se conserva como interfaz con una sola implementación, para las pruebas y dobles.
- `/status.enlace_io` y la fila de Información del equipo se conservan con el valor constante `"modbus"` («Modbus TCP»), para no romper la API ni `tests/test_t15_rutas_equivalentes.py` (DECISIÓN SIN CONFIRMAR).
- Alarmas que solo emitía el serial (p. ej. `TARJETA_REINICIO`): dejan de emitirse, pero su entrada de catálogo y sus textos se conservan para mostrar el historial y la bitácora antiguos (DECISIÓN SIN CONFIRMAR).
- La calibración Modbus conserva el nombre `calibration_modbus.yaml` y su copia en `data/`. El rechazo de un respaldo con otra fábrica (422 `calibracion_otro_enlace`) se conserva: rechaza los respaldos de equipos serial.
- Pruebas: `tests/conftest.py` deja de fijar el enlace serial; las pruebas que usaban el doble serial pasan a un doble Modbus (simulador M31 o doble en memoria de `EnlaceES`). Excepción autorizada a «no borrar pruebas»: se borran solo las pruebas cuyo único objeto es el enlace serial, el firmware o la conversión ADC del serial (lista completa en el informe, con archivo y motivo). Cualquier otra prueba se migra con su aserción intacta.
- Documentación: `CLAUDE.md` (secciones del enlace y de la tarjeta), catálogo de alarmas, hoja de banco (se retiran las pruebas de la ESP32), lista SOUP, registro de riesgos (riesgos propios del serial: «retirado en la tanda 20»), `docs/README.md` si nombra el firmware.

### T20-04 · Configuración del módulo desde el ejecutable (`--rol configurar-modulo`)
- Nuevo rol de `Autoclave.exe` (`exe_unico.py`, en el estilo de `asociar-tactiles`), lo invoca el Setup.
- Usa el mismo código de `ModbusLink` para leer modelo, composición, firmware y MAC (sin duplicar la verificación).
- **No escribe bobinas ni la configuración de seguridad** (eso lo hace el software al conectar) y no reinicia el módulo.
- Si hay un backend escuchando en 127.0.0.1:8000, no actúa y lo informa (no comparte el módulo con un software en marcha).
- Contraseña web (decisión 6): si recibe `--clave-archivo <ruta>`, lee la contraseña de ese archivo, lo borra de inmediato y escribe el usuario `admin` (0x758B, 5 registros) y la contraseña (0x7590, 3 registros, máximo 6 caracteres ASCII imprimibles) con fc10, y los relee para comparar. La contraseña nunca va al log ni al resultado. Antes de escribir valida longitud y caracteres; si no cumple, no escribe.
- Resultado: archivo JSON (`--resultado <ruta>`) con `ok`, código de error y texto (es/en), modelo, composición, firmware, MAC y `clave_cambiada` (true/false). Código de salida 0 solo si todo fue correcto.
- Presupuesto total de 30 s con reintentos (el adaptador puede tardar en subir tras el paso 08).
- `--ip`/`--puerto` solo se aceptan con `127.0.0.1` (para probar el `.exe` contra el simulador); con cualquier otra IP se usan 192.168.3.7:502 fijos.
- Nota de riesgo para el registro: la contraseña web se puede leer por Modbus (R 0x03 en 0x7590) y Modbus TCP no tiene autenticación; la protección real es la red dedicada (MED-04, MEDIA).

### T20-05 · Setup
- **Paso 08 · red de los módulos** (`tools/estacion/08_red_modulos.ps1` y `08_revertir_red_modulos.ps1`, con `_comun.ps1`):
  - página propia «Red de los módulos de E/S» con la lista de adaptadores Ethernet físicos (nombre, descripción, MAC, estado del cable); no se ofrecen Wi-Fi ni virtuales;
  - preselección: el que ya tenga 192.168.3.10; si no, ninguno preseleccionado y el técnico debe elegir (no se puede seguir sin elegir, salvo desmarcar la casilla «Configurar la red de los módulos», marcada por defecto);
  - si el adaptador elegido es el único con puerta de enlace o con conexión a Internet, advertencia explícita de que perderá esa red (el técnico confirma);
  - si otro adaptador ya está en 192.168.3.0/24, error y no se aplica;
  - aplica IPv4 estática 192.168.3.10/24, sin puerta de enlace ni DNS, DHCP desactivado en ese adaptador; respaldo de la configuración anterior en `datos\estacion\respaldo_08.json`; el revertir la restaura; el desinstalador lo revierte; Reparar lo reaplica con el adaptador guardado; se anota como `Paso08`;
  - silencioso: `/ADAPTADOR=<MAC>`; sin él, en silencioso no se toca la red y se anota.
  - Es independiente de la casilla de estación (01–07): la red se necesita aunque el PC no se configure como estación.
- **Contraseña web del módulo:** página con contraseña y confirmación (máx. 6 caracteres ASCII imprimibles). En instalación nueva es obligatoria; en actualización o Reparar es opcional (vacía = no se cambia). Se pasa al rol por un archivo en `{tmp}` que el rol borra. En silencioso no se cambia y se anota. Nunca va al log de Inno ni a la línea de comandos.
- **Prueba de conexión** (decisión 5): después del paso 08, el Setup ejecuta `Autoclave.exe --rol configurar-modulo` y muestra el resultado en una página final: correcto (modelo, 5 módulos, firmware, MAC/ID) o el motivo con la acción sugerida (cable, adaptador, módulo apagado, composición distinta). No aborta.
- En `{app}` ya no se instala `enlace_io.json`.

### T20-06 · Hoja de banco y riesgos
- `docs/mis_plans/hoja_pruebas_banco/pruebas.py` regenerado con el bloque M (hoy solo está en el `.md`), sin las pruebas de la ESP32.
- Nuevo M-7 «Setup con Modbus»: adaptador y IP, reversión al desinstalar, contraseña web cambiada (entrar a 192.168.3.7 con la nueva), prueba de conexión correcta y con cable desconectado.
- M-5 ampliado con la prueba aislada de ADB-04.
- MED-04 en `docs/riesgos/registro_riesgos.md`; AN-30 cerrado como decisión; AN-31 y AN-32 cerrados.
