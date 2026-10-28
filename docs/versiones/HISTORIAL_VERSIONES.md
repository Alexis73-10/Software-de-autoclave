# Historial de versiones del software del autoclave

Una entrada por **entrega** (compilación con Setup que se instala en el equipo), la más nueva primero. La agrega `tools/entrega/compilar_entrega.py` en el commit `chore(ver): 1.0.0-alpha.N`; no se edita a mano.

- Esquema (D-VER-1): SemVer con prerelease, `1.0.0-alpha.N`, luego `-beta.N`, `-rc.N` y `1.0.0`. N sale de las etiquetas git (D-VER-3) y solo sube en las entregas (D-VER-2).
- `AppVerNum` (lo compara el Setup): `1.0.0.<etapa × 1000 + N>`, con alpha = 1, beta = 2, rc = 3; la versión final es `1.0.0.9000`.
- Cada entrada da la versión, la fecha, el commit base, el `AppVerNum` y los commits desde la entrega anterior (sin merges). Los SHA-256 del Setup y del zip solo existen después de compilar: están en el mensaje de la etiqueta anotada `v1.0.0-alpha.N` (`git show v1.0.0-alpha.N`) y en `entrega/v1.0.0-alpha.N_<fecha>/SHA256SUMS.txt`.
- **`1.0.0-alpha.1` sucede a la compilación I** (`inst-2026-10-24-i`, Setup `1.0.0-i`, `AppVerNum` 1.0.0.9). Las compilaciones anteriores (B a I) se identificaban por letra; sus etiquetas `inst-*` se conservan como historia y no cuentan para N.

<!-- entradas: las agrega compilar_entrega.py debajo de esta línea, la más nueva primero -->

## 1.0.0-alpha.6 — 2026-10-28

- Etiqueta: `v1.0.0-alpha.6` (commit `chore(ver): 1.0.0-alpha.6`, sobre `72c9e8c`)
- AppVerNum: `1.0.0.1006`
- SHA-256 del Setup y del zip: en el mensaje de la etiqueta y en `entrega/v1.0.0-alpha.6_2026-10-28/SHA256SUMS.txt` (solo existen después de compilar)
- Commits desde `v1.0.0-alpha.5`:
  - 56f51c8 docs(ajustes-28oct): estado final
  - 85d3ed9 docs(ajustes-28oct): informe y resultado de la suite
  - bf42bc6 docs(ajustes-28oct): estado tras C
  - 24429f2 fix(aj-02): el ALL_OFF directo del apagado también borra las peticiones de agua
  - 87569e1 fix(aj-03): globo de la gráfica sin nombres montados sobre el valor
  - e58308d docs(ajustes-28oct): estado tras B
  - 2465920 fix(aj-02): agua_intercambiador como OR de las peticiones de vacío y drenaje
  - beb1eb1 docs(ajustes-28oct): estado tras A
  - 6293e8c fix(aj-01): ocultar «Apagar equipo» durante el ciclo


## 1.0.0-alpha.5 — 2026-10-28

- Etiqueta: `v1.0.0-alpha.5` (commit `chore(ver): 1.0.0-alpha.5`, sobre `cc732a1`)
- AppVerNum: `1.0.0.1005`
- SHA-256 del Setup y del zip: en el mensaje de la etiqueta y en `entrega/v1.0.0-alpha.5_2026-10-28/SHA256SUMS.txt` (solo existen después de compilar)
- Commits desde `v1.0.0-alpha.4`:
  - cc732a1 fix(fw-inf): firmware M31 como vX.Y y comprobación solo informativa (corrige ADB-02)
  - 16bc17c docs(t20): cierre Z (CLAUDE.md enlace de E/S Modbus tandas 19-20, informe R20 completo, índice, estado)


## 1.0.0-alpha.4 — 2026-10-27

- Etiqueta: `v1.0.0-alpha.4` (commit `chore(ver): 1.0.0-alpha.4`, sobre `8a214e9`)
- AppVerNum: `1.0.0.1004`
- SHA-256 del Setup y del zip: en el mensaje de la etiqueta y en `entrega/v1.0.0-alpha.4_2026-10-27/SHA256SUMS.txt` (solo existen después de compilar)
- Commits desde `v1.0.0-alpha.3`:
  - 8a214e9 docs(t20): anomalías conocidas de la 1.0.0-alpha.4 (AN-30/31/32 cerradas, MED-03 actualizada, MED-04, AN-33..35, bloque M con M-5 ampliado, M-5b y M-7; solo Modbus TCP, la ESP32 ya no es compatible; sin uso clínico)
  - cbfc19f docs(t20): estado (I y R hechas)
  - 104e4d8 docs(t20): informe R20, sección R
  - 72c8d4c fix(t20): V20-rr-01 (orden de reinicio no enviada o cierre local no son evidencia) y V20-rr-05 (sin permiso de reinicio no se escribe la configuración); residuales V20-rr-02..04 en MED-03
  - 11584ec docs(t20): informe R20 (decisiones, I, riesgos)
  - fc0f6a0 fix(t20): V20-s3-01..11 correcciones del Setup y del paso 08 (red de los modulos)
  - e689224 fix(t20): V20-s1-06 y V20-s1-08 rol configurar-modulo: pymodbus silenciado, backend comprobado antes de escribir y presupuesto acotado
  - cc4f127 fix(t20): V20-s1-01..05 y V20-s1-07 reinicio del módulo con evidencia, pendiente, acotado y con permiso; falla_salidas en None
  - f02b37e docs(t20): informe R20 con s2 (lista completa de pruebas borradas, V20-s2-05) y s3
  - fff1c85 fix(t20): revisión R de s2 (V20-s2-01..04 pruebas migradas en vez de borradas; V20-s2-06 acciones de alarma sin ESP32; V20-s2-07 'serial' excluido del empaquetado) y bloques E9/N11/T12 en test_f1_registro_pruebas
  - fae9994 docs(t20): estado (P hecha; I y R en curso)
  - fee8f32 docs(t20): T20-06 registro de riesgos (MED-04, MED-03 con ADB-04/ADB-05, nota ADB-02, AN-30 cerrada como decisión, AN-31 y AN-32 cerradas)
  - 01bae78 test(t20): I integración (backend con 5 esclavos y reinicio ADB-04; rol contra el simulador); test_t19_s1_config con ADB-01; comentarios sin SerialLink; claves i18n del rol en el alcance de claves_sin_uso
  - 2828d25 chore(t20): retiro del enlace serial en la documentación (T20-03)
  - f75e9d4 test(t20): migración de las pruebas al retiro del enlace serial (T20-03)
  - 98c34da chore(t20): retiro del firmware de la ESP32 (Hardware/Comunicacion_esclava_ESP32_V2 y _V3, T20-03)
  - 658692a chore(t20): retiro del enlace serial en empaquetado y dependencias (T20-03)
  - e6b2ac7 chore(t20): retiro del enlace serial en el código (T20-03)
  - f2cc939 test(t20): pruebas T20-05 del Setup con Modbus y del paso 08
  - 30499a8 feat(t20): T20-05 Setup con Modbus: paso 08 (red de los modulos), contrasena web y prueba de conexion
  - f80caf8 docs(t20): informe R20 (borrador: A0, B, V, F, s1, T20-06)
  - f95e624 docs(t20): T20-06 hoja de banco regenerada desde pruebas.py (bloques E9/N11/T12 y filas extra que solo estaban en el .md portados; sin la ESP32; M-0/M-1/M-5 actualizados, M-5b prueba aislada de ADB-04, M-7 Setup con Modbus; M-6 retirado)
  - d0510ac feat(t20): rol --rol configurar-modulo (T20-04)
  - 75857ed feat(t20): adenda del banco ADB-01 a ADB-05 en ModbusLink y simulador M31
  - be98c16 docs(t20): estado (P en curso)
  - e8879b8 docs(t20): estado (A0, V, F hechas; tabla de propiedad de P)
  - 0da003a test(t20): F1 doble en memoria de EnlaceES y fixture enlace_doble (sin retirar aún el serial)
  - bfc6f93 feat(t20): claves i18n configurar_modulo (resultado del rol configurar-modulo, es/en) y línea base de la suite
  - f8a7989 docs(t20): estado (A0 en curso, B hecha: copia en G: y etiqueta respaldo-serial-pre-t20)
  - 2c05e2f docs(t20): decisiones, instrucción, prompt, adenda del banco e informe de banco M31
  - 391aedf docs(t19): cierre Z (CLAUDE.md enlace de E/S, informe R19, índice, AN-32 adenda del banco sin aplicar, estado)


## 1.0.0-alpha.3 — 2026-10-27

- Etiqueta: `v1.0.0-alpha.3` (commit `chore(ver): 1.0.0-alpha.3`, sobre `8418b22`)
- AppVerNum: `1.0.0.1003`
- SHA-256 del Setup y del zip: en el mensaje de la etiqueta y en `entrega/v1.0.0-alpha.3_2026-10-27/SHA256SUMS.txt` (solo existen después de compilar)
- Commits desde `v1.0.0-alpha.2`:
  - 8418b22 docs(t19): anomalías conocidas de la 1.0.0-alpha.3 con la tanda 19 (MED-01..MED-03, DECISIONES SIN CONFIRMAR, bloque M, enlace por defecto Modbus; sin uso clínico)
  - c99cd2a docs(t19): informe R19 (borrador hasta K) y estado (I y R hechas)
  - 1277048 test(t19): la integración Modbus descarga el backend importado con Modbus (CALIBRATION_PATH) para las pruebas siguientes del mismo proceso
  - f8b06f0 test(t19): pruebas R1 del enlace Modbus contra el simulador M31
  - 3ae9481 fix(t19): correcciones R del enlace Modbus (V19-s1-01, 03, 04, 05, 06, 07; V19-s3-04)
  - bf932bc fix(t19): el verificador de la entrega falla sin calibration_modbus.yaml y exige la fábrica nominal de MOD-04 (V19-s2-01)
  - 8e17fcb fix(t19): el respaldo compara toda la calibración de fábrica (temperatura y presión) con la activa (V19-s2-02)
  - ab32b2a fix(t19): con Modbus, una cuenta de temperatura fuera de -500..2500 décimas es sin valor (V19-s2-03)
  - 5a44690 test(t19): el apagado individual une la base con map_do aunque la base no cubra el canal reasignado (V19-s2-04)
  - 15b875b docs(t19): estado (I con la suite en verde; R)
  - 496fb18 docs(t19): TARJETA_REINICIO no aplica a Modbus (catálogo) y estado
  - 4b58f14 test(t19): integración del backend completo con el enlace Modbus contra el simulador M31 (arranque, conexión, lecturas, salida, pérdida y reconexión)
  - d41b30e test(t19): espera del evento TARJETA_REINICIO en test_uptime_que_retrocede_es_reinicio (carrera anterior a la tanda)
  - b8a42be test(t19): pruebas de P-s2 (MOD-03 None por canal y conversión Modbus; MOD-04 calibración Modbus, piso de señal, ruta según el enlace, respaldo y verificador; MOD-05 puertos según el enlace, asignación fuera de rango, buzzer en DO 25 y apagado de DO 1-32)
  - 103fbf9 test(t19): pruebas existentes ajustadas al buzzer en DO 25, al apagado de DO 1-32 y a la calibración según el enlace (MOD-04, MOD-05)
  - dcdb3de feat(t19): conversión por enlace con None por canal, calibración Modbus y puertos según el enlace; buzzer en DO 25 (MOD-03, MOD-04, MOD-05)
  - 0b99bad test(t19): P-s1 pruebas del enlace Modbus contra el simulador M31 (configuración, interfaz, mapa, conexión verificada, vigilancia del lazo, pérdida, diagnóstico, salidas)
  - d8a9f33 feat(t19): P-s1 ModbusLink (MOD-02, MOD-03, MOD-06 a MOD-11), su configuración validada y el simulador M31 para las pruebas (MOD-14)
  - a723e62 test(t19): P-s3 alarmas Modbus como TARJETA_ALL_OFF_SIN_CONFIRMAR (MOD-12) y exposición de modulos, tarjeta y enlace_io (MOD-10, MOD-01)
  - e4d061b feat(t19): P-s3 MOD-12 alarmas Modbus en ControlLoop y enlace de E/S en Información del equipo y del sistema (MOD-01)
  - 99759ce docs(t19): estado
  - f5c057c feat(t19): .spec con el enlace Modbus y pymodbus.client en hiddenimports (MOD-13); pymodbus imprescindible en test_b2
  - f70c096 docs(t19): hoja de banco bloque M (M-0 red, M-1..M-6; MOD-15, MOD-17) y riesgos MED-01..MED-03 (MOD-16)
  - a953a4e docs(t19): estado (A0, V, F) y notas de las verificaciones V con la tabla de propiedad de P
  - 4964934 feat(t19): F3 alarmas TARJETA_CONFIG_SEGURIDAD y TARJETA_MODULOS_ORDEN (catálogo, i18n es/en, catalogo_alarmas.md) y textos del enlace en Información del equipo (MOD-12); línea base
  - 754e9a4 feat(t19): F2 interfaz EnlaceES, selección del enlace (enlace_io.json), build_enlace y enlace_io en /status (MOD-01, MOD-02)
  - 7563a3e feat(t19): F1 pymodbus 3.16.1 como dependencia (MOD-13: pyproject, lock y lista SOUP)
  - 875d6e2 docs(t19): decisiones, planeación del enlace Modbus, instrucción, prompt y manuales M31-U
  - 1dd3e94 docs(t18): CLAUDE.md (arranque), informe R18, anomalías conocidas de la 1.0.0-alpha.3 y estado
  - 453b65e fix(t18): hallazgos de R (V18-01 espera con tope tras pedir el reinicio, V18-02 sin reinicio con backend vivo, V18-03 tope de la intro, V18-04 pruebas)
  - 2ec2509 docs(t18): hoja de banco (I-07b, I-13, I-14, I-15) y estado
  - bb951e7 feat(t18): ARR-06, REI-01 y EST-08 (intro sin perfil, reinicio del PC, sin cubierta)
  - b34087c feat(t18): EST-09 paso 07 de la estación (escritorio de la estación)
  - ee8d32f docs(t18): decisiones de la tanda 18 (ARR-06, REI-01, EST-08, EST-09)
  - ddb4978 docs(t17): entrega 1.0.0-alpha.2 (versión, SHA-256 y comando de push) en el informe, el índice y el estado


## 1.0.0-alpha.2 — 2026-10-26

- Etiqueta: `v1.0.0-alpha.2` (commit `chore(ver): 1.0.0-alpha.2`, sobre `a9682f5`)
- AppVerNum: `1.0.0.1002`
- SHA-256 del Setup y del zip: en el mensaje de la etiqueta y en `entrega/v1.0.0-alpha.2_2026-10-26/SHA256SUMS.txt` (solo existen después de compilar)
- Commits desde `v1.0.0-alpha.1`:
  - 15b52b9 docs(t17): cierre Z — informe R17, índice y estado
  - a51a120 docs(t17): anomalías conocidas de la 1.0.0-alpha.2 con la tanda 17, protecciones ESG-02 y pruebas manuales
  - 5f22a16 docs(t17): estado tras R
  - 02baeb2 docs(t17): resolución de R3
  - 1927438 test(t17): R3 V17-s3-05 modo_prueba_en_protocolo verifica ESG-02 con presion vigente
  - 364e2eb fix(t17): R3 V17-s3-02 CIC-10 por los demas motivos con la presion perdida; V17-s3-06 comentario
  - 32f6227 docs(t17): resolución de R1
  - 9d0e897 test(t17): R1 s1 — DACL verificada (con ejecución del comando de AplicarAcl sobre una carpeta temporal), buses USB, reversión fallida, estacion\ apartada e instalador_exe con el Setup; pruebas de texto renombradas test_texto_/test_replica_
  - f027afb fix(t17): R1 s1 — DACL reemplazada y verificada, programa\ comprobada tras protegerla, estacion\ preexistente apartada, discos USB excluidos, reversión fallida conserva rutas, instalador_exe no instala junto al Setup
  - 952e331 fix(t17): integración de R4 — clave arranque.version_software; resolución de R4
  - 94781b1 test(t17): R4 s4 — capas, mensaje de DESPEJAR, clic real en botones visibles, presión en psi y con /status 500
  - 661c85e fix(t17): R4 s4 — mensaje de DESPEJAR en el detalle, capas cerradas con la seguridad urgente, Hasta sin «Sin fecha»
  - dc6f21d fix(t17): instancia_unica en los hiddenimports del .spec; resolución de R2
  - 6ad8360 test(t17): R2 V17-s2-01..06 con dobles (mutex, eventos senalados, prefijo, reinicio, parser de 03/06)
  - f72409f fix(t17): R2 V17-s2-01..06 mutex del lanzador, espera solo de eventos pendientes, 03 con retraso, log del rol, prefijo Digimon y reinicio solo si se escribio
  - 25f619e docs(t17): CLAUDE.md con instalación, zona horaria, SON-01, ESG-01/02, bitácora central y arranque
  - 222bd64 docs(t17): hoja de banco, bloque I (instalación y estación, SON-01, ESG-01/02, MPR-01, ALM-01, PRC-01, BIT)
  - 632e4b9 fix(t17): V17-s3-01 la supresión de la bitácora se enclava al ver un perfil válido y avisa con WARNING
  - 153dcd6 docs(t17): estado tras P e integración
  - 32efe11 fix(t17): integración I — i18n de s3/s4, contrato avisos_corte_prueba, códigos ESG-02 en la UI, serie temp_2_camara del PDF, OpenAPI con categoria
  - 475198a docs(t17): respuestas de P (s1..s4)
  - 69c87bc fix(t17): retirar un QML temporal de pruebas que entró por error en F3
  - 43ed55e fix(t17): F2 la supresión de la bitácora no impide abrir una base sin el atributo (test_secuencia_arranque)
  - 8daaa0b feat(t17): BIT-05 filtro por categoria en GET /audit_log; /status con ESG-01/02
  - ff3bf9d feat(t17): ESG-01 sin CIC-10 por presion sin lectura; ESG-02 modo prueba con estado seguro
  - 5d0f707 feat(t17): SON-01 sondas No en uso visibles como monitoreo (revierte O11)
  - cc11380 test(t17): F3 línea base i18n admite el tercer nivel bitacora.categoria (BIT-05)
  - 783c968 feat(t17): MPR-01 presión en el modo prueba, BIT-05 filtros con calendario y desplegables, VER-08 prueba
  - 9e35f46 feat(t17): PRC-01 selector de programas, ALM-01 detalle de alarmas y rótulo (monitoreo) de SON-01
  - 10b9427 test(t17): EST-06 armado Digimon y herramienta con dobles; EST-07 cubierta y orden del lanzador
  - b0c02e5 feat(t17): EST-06 asociacion de tactiles sin MultiDigitizer y EST-07 cubierta de arranque
  - 892a29b docs(t17): s1 LEEME del instalador, de la estación y de instalación con la disposición X:\Especifika\Autoclave\{programa,datos}, páginas de unidad y zona, bloqueo de la disposición anterior y /ZONA=
  - 1c38b99 test(t17): s1 pruebas estáticas del Setup (INS-01, INS-02, EST-06.3), _comun.ps1 y esta_instalado_aqui con registro simulado
  - d71ae69 feat(t17): s1 Setup con unidad y disposición X:\Especifika\Autoclave\{programa,datos} (INS-02), zona horaria (INS-01) y TactilesRepetir (EST-06.3)
  - a105691 docs(t17): estado, respuestas de V y tabla de propiedad de P
  - f101b2e feat(t17): F3 textos i18n de la tanda y UI-VER (se retira app.version y V:1.0 de las barras)
  - 526a570 feat(t17): F2 bitácora central (BIT-01..05): eventos retirados al log, nada durante la instalación, equipo_instalado, categorías
  - af32dbd fix(t17): A1 test_f1_registro_pruebas admite el bloque H de la hoja de banco (cierre de la tanda 16)
  - 7324847 feat(t17): F1 contrato de la ruta de datos (INS-02): registro, regla anterior, carpeta del exe
  - fca0102 fix(t17): A1 test_historial_entrada_debajo_de_la_marca no depende de que el historial real esté vacío
  - 424e5d6 docs(t17): decisiones, instrucción y prompt de la tanda 17
  - d643a9a docs(t16): cierre Z — CLAUDE.md, hoja de banco (bloque H), informe R16, índice y estado
  - d5cdbc8 chore(t16): /data/ completo en .gitignore (P10, D-14.10)
  - e53a63b docs(t16): anomalías conocidas de la 1.0.0-alpha.2
  - 71cf5c5 docs(t16): estado tras R
  - 4fda28b fix(t16): hallazgos de la revisión R (V16-s1..s5)
  - 71d277d docs(t16): estado tras P e I
  - 6554f16 test(t16): integración VCH §8 puntos 1 a 9 de punta a punta
  - 7484757 fix(t16): integración I — i18n de s4/s5, bitácora, códigos de rechazo, fase legible y bases
  - e774062 test(t16): s4 pruebas de P1, P2, parámetros nuevos, DEU-01 y PRG-01
  - d778624 feat(t16): s4 programas y límites (P1, P2, parámetros nuevos, DEU-01, PRG-01)
  - 53952d9 test(t16): P4 NO CONFORME visible: backend, ticket/PDF/correo y QML
  - d306606 feat(t16): P4 NO CONFORME visible (D-14.4)
  - 4125106 feat(t16): s2 CALENTAMIENTO en modo chaqueta (VCH C), P3 y filtro de plausibilidad P7
  - 00b0bb5 feat(t16): s3 CICLO, corte único de chaqueta, VCH Q y correcciones V-02
  - 7f364f1 feat(t16): s1 ESTERILIZACION con VCH (modo chaqueta y aislamiento), P5, P6 y SAF-05
  - 6cf4573 docs(t16): estado con V y tabla de propiedad de la etapa P
  - 687207c feat(t16): F4 estado.no_conforme_reconocido (P4), se limpia en cada ciclo
  - 41ed517 feat(t16): F4 contratos del estado del ciclo (aislamiento, corte de chaqueta, NO CONFORME, modo de vapor)
  - 7a74963 feat(t16): F3 DebounceAcumulado, AislamientoCamara y profile.modo_vapor
  - 3df6b1a feat(t16): F2 alarmas CIC-15 a CIC-18, motivos de fase y claves i18n de parámetros nuevos
  - 4c4f4b9 docs(t16): línea base de la suite (7922 recolectadas, 1 falla preexistente en dev)
  - f1dc41e feat(t16): F1 parámetros de equipo VCH, D-CHQ y DEU-01 con lectores y coherencia
  - d26d7cf feat(t16): F5 testpaths = ["tests"] en pyproject.toml
  - cbb96ba docs(t16): documentos fuente, instrucción y prompt de la tanda 16


## 1.0.0-alpha.1 — 2026-10-25

- Etiqueta: `v1.0.0-alpha.1` (commit `chore(ver): 1.0.0-alpha.1`, sobre `70a242e`)
- AppVerNum: `1.0.0.1001`
- SHA-256 del Setup y del zip: en el mensaje de la etiqueta y en `entrega/v1.0.0-alpha.1_2026-10-25/SHA256SUMS.txt` (solo existen después de compilar)
- Commits desde `inst-2026-10-24-i`:
  - 70a242e docs(ver): anomalias conocidas de la 1.0.0-alpha.1 y lanzadores
  - 9bfd130 docs(ver): informe VER_informe.md y estado final de la etapa
  - b3be082 fix(ver): sumas con LF y listas de commits vacías (ensayo de punta a punta)
  - 146e1ff docs(ver): estado de la etapa VER (pasos 1 a 6 hechos)
  - 4dc24f7 docs(ver): uso del script de entrega en el LEEME y en CLAUDE.md
  - 37379b9 test(ver): test_config_correo no depende de data/correo_equipo.json del PC
  - c67cfb5 test(ver): pruebas de la etapa VER (§3)
  - d55950a feat(ver): script de entrega tools/entrega/compilar_entrega.py (§2)
  - dae4d0f feat(ver): _build_info.py generado por los .spec del autoclave (VER-04)
  - 93d3ae8 feat(ver): fuente única de versión en autoclave/_version.py (VER-01..03, VER-05)
  - ee2f132 docs(ver): estado de la etapa VER (paso 0 hecho)
  - 16968bd docs(tanda15): cierre Z — informe R15, índice, estado y evidencias de K
  - 08d53da fix(t15): restaurar src/autoclave/config/calibration.yaml de dev
  - f11a1b9 fix(t15): comentarios de la revisión V15-B (sin cambio funcional)
  - 2d1dbe2 fix(t15): hallazgos de la revisión V (sin cambio funcional)
  - 371cc88 docs(tanda15): estado de la etapa T
  - 6a143bc refactor(t15): ORG-13 tests/helpers y tests/banco; marcador req
  - e681697 docs(tanda15): estado de la etapa B
  - 8e7cbed refactor(t15): ORG-12 (cont.) finales de línea de 9 tests reescritos
  - 6d64cce refactor(t15): ORG-12 partir backend/server.py en backend/rutas/*.py (APIRouter)
  - 8fbc5f9 docs(tanda15): estado de la etapa U
  - 5947102 test(t15): ORG-11 test de arquitectura de capas
  - b165fbc refactor(t15): ORG-10 demos QML prueba_*.py a tools/demos_qml/
  - 0586850 refactor(t15): ORG-09 ui/service_ui a autoclave.cliente; se elimina ui/
  - 7698d6e refactor(t15): ORG-08 roles y validacion_usuario a autoclave.auth
  - 0fd8515 docs(tanda15): estado de A0, G y R; compilación ORG-07 idéntica a la base
  - 712448f refactor(t15): ORG-07 los 4 .spec a packaging/ con rutas relativas a RAIZ
  - f580047 refactor(t15): ORG-06 docs/README.md con el índice de carpetas
  - 3fed414 refactor(t15): ORG-05 .log de informes fuera de git; diseño a docs/diseno/
  - 5b21c9e refactor(t15): ORG-04 Hardware/Comunocacion_esclava_ESP32_V2 -> Comunicacion_esclava_ESP32_V2
  - c97ac8c refactor(t15): ORG-03 parametros_software.accdb y data_base/*.xlsx a docs/referencia/
  - 324e6a5 refactor(t15): ORG-02 Documentacion/*.docx a docs/arquitectura/
  - d35e544 docs(tanda15): A0 línea base (suite, rutas, OpenAPI, roles, compilación)
  - aee5334 docs(tanda15): decisiones, instrucción, prompt y estado inicial
  - a246883 docs(tanda13): K13 compilación I, LEEME (cambios respecto a la H, 8h) e índice; cierre Z

