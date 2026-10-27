# Historial de versiones del software del autoclave

Una entrada por **entrega** (compilación con Setup que se instala en el equipo), la más nueva primero. La agrega `tools/entrega/compilar_entrega.py` en el commit `chore(ver): 1.0.0-alpha.N`; no se edita a mano.

- Esquema (D-VER-1): SemVer con prerelease, `1.0.0-alpha.N`, luego `-beta.N`, `-rc.N` y `1.0.0`. N sale de las etiquetas git (D-VER-3) y solo sube en las entregas (D-VER-2).
- `AppVerNum` (lo compara el Setup): `1.0.0.<etapa × 1000 + N>`, con alpha = 1, beta = 2, rc = 3; la versión final es `1.0.0.9000`.
- Cada entrada da la versión, la fecha, el commit base, el `AppVerNum` y los commits desde la entrega anterior (sin merges). Los SHA-256 del Setup y del zip solo existen después de compilar: están en el mensaje de la etiqueta anotada `v1.0.0-alpha.N` (`git show v1.0.0-alpha.N`) y en `entrega/v1.0.0-alpha.N_<fecha>/SHA256SUMS.txt`.
- **`1.0.0-alpha.1` sucede a la compilación I** (`inst-2026-10-24-i`, Setup `1.0.0-i`, `AppVerNum` 1.0.0.9). Las compilaciones anteriores (B a I) se identificaban por letra; sus etiquetas `inst-*` se conservan como historia y no cuentan para N.

<!-- entradas: las agrega compilar_entrega.py debajo de esta línea, la más nueva primero -->

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

