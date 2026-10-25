# Etapa VER — estado

Instrucción: `docs/mis_plans/instruccion_claude_code_versionado.md`. Rama `versionado` desde `dev`.

| Paso | Contenido | Estado | Commit |
|---|---|---|---|
| 0 | Unir `tanda-15` a `dev` y correr la suite | Hecho | b7560e6 (merge) |
| 1 | Fuente única `_version.py`, `pyproject.toml` dinámico, 5 sitios (VER-01..03, VER-05) | Hecho | 93d3ae8 |
| 2 | Verificación §1: versión en el `.exe` de la I | Hecho (sin commit propio; va en el informe) | — |
| 3 | `_build_info.py` desde los `.spec` y `--escribir-version` (VER-04) | Hecho | dae4d0f (`--escribir-version` en 93d3ae8) |
| 4 | Script `tools/entrega/compilar_entrega.py` (§2) | Hecho | d55950a |
| 5 | Pruebas `tests/test_ver_*.py` (§3) | Hecho | c67cfb5, 37379b9 (aislar test_config_correo) |
| 6 | Documentación: HISTORIAL, LEEME, CLAUDE.md | Hecho | d55950a (HISTORIAL), 4dc24f7 |
| 7 | Informe `VER_informe.md` | Pendiente | |
| 8 | Unir `versionado` a `dev` con la suite en verde | Pendiente | |
| 9 | `CERRADO.txt` | Pendiente | |

## Notas para reanudar
- Suite de la base (dev b7560e6, `python -m pytest tests -n auto`): 7830 passed, 6 failed, 10 skipped, 3 xfailed; en serie pasan 4 de las 6; quedan las 2 de `test_config_correo` (dependen de `data/correo_equipo.json` del PC). Total 7834 passed.
- Verificación §1: el `.exe` de la I no trae `autoclave-*.dist-info` (tampoco está instalado en `_venv_t8_producto`): `importlib.metadata.version("autoclave")` lanza PackageNotFoundError.
- Compilación de verificación real (dae4d0f, `_venv_t8_producto`): `dist/Autoclave/Autoclave.exe --escribir-version` -> `1.0.0-alpha.1.dev+gdae4d0f.sucio` (evidencia en `suites/version_exe_verificacion.json`).
