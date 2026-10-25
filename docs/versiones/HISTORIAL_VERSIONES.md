# Historial de versiones del software del autoclave

Una entrada por **entrega** (compilación con Setup que se instala en el equipo), la más nueva primero. La agrega `tools/entrega/compilar_entrega.py` en el commit `chore(ver): 1.0.0-alpha.N`; no se edita a mano.

- Esquema (D-VER-1): SemVer con prerelease, `1.0.0-alpha.N`, luego `-beta.N`, `-rc.N` y `1.0.0`. N sale de las etiquetas git (D-VER-3) y solo sube en las entregas (D-VER-2).
- `AppVerNum` (lo compara el Setup): `1.0.0.<etapa × 1000 + N>`, con alpha = 1, beta = 2, rc = 3; la versión final es `1.0.0.9000`.
- Cada entrada da la versión, la fecha, el commit base, el `AppVerNum` y los commits desde la entrega anterior (sin merges). Los SHA-256 del Setup y del zip solo existen después de compilar: están en el mensaje de la etiqueta anotada `v1.0.0-alpha.N` (`git show v1.0.0-alpha.N`) y en `entrega/v1.0.0-alpha.N_<fecha>/SHA256SUMS.txt`.
- **`1.0.0-alpha.1` sucede a la compilación I** (`inst-2026-10-24-i`, Setup `1.0.0-i`, `AppVerNum` 1.0.0.9). Las compilaciones anteriores (B a I) se identificaban por letra; sus etiquetas `inst-*` se conservan como historia y no cuentan para N.

<!-- entradas: las agrega compilar_entrega.py debajo de esta línea, la más nueva primero -->

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

