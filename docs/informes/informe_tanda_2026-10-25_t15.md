Tanda 15: reorganización sin cambio funcional — suite 7834 passed (base 7816), rutas/OpenAPI idénticos: sí, compilación equivalente: sí. Lista para unir a dev: sí.

# Índice de la tanda 15 (24-25 oct 2026)

- Rama `tanda-15` con push; **no se unió a `dev`** (D10): la revisa y la une Cristian.
- Informe completo: `docs/informes/tanda15/R15_reorganizacion.md`.
- Estado por etapa: `docs/informes/tanda15/estado.md`.
- Línea base y evidencias: `docs/informes/tanda15/base/` (suite, rutas, OpenAPI, roles, compilación), `org07/`, `u/`, `k/` (listados, humo y log de ISCC), `suites/`.

Lo que cambió (sin cambiar comportamiento):
- `src/autoclave/auth/` (roles y validación de usuario), `src/autoclave/cliente/` (antes `ui/service_ui/`); se eliminó `src/autoclave/ui/`.
- `backend/server.py` partido en `dependencias.py` + `rutas/<área>.py` (13 routers) + `rutas/_comun.py`.
- `.spec` en `packaging/` (se compila desde la raíz con `pyinstaller --noconfirm packaging\<x>.spec`).
- `tests/helpers/`, `tests/banco/`, `tests/README.md`, marcador `req`; tests nuevos `test_arquitectura_capas.py` y `test_t15_rutas_equivalentes.py`.
- `docs/README.md`, `docs/arquitectura/`, `docs/referencia/`, `docs/diseno/`; los `.log` de informes ya no se versionan.

Para Cristian:
- **Antes de compilar una entrega, partir de 08d53da o posterior** (ver el incidente de `calibration.yaml` en R15).
- Decidir si se borran las ramas remotas `tanda-2` a `tanda-13` y los worktrees de `.claude/worktrees/`.
- Borrar a mano los archivos sin seguimiento listados en R15 (entre ellos `src/autoclave/config/calibration.yaml.bak`, que creó esta tanda).
- Pendiente 62304 (5.3): actualizar `docs/arquitectura/DOC_Backend_Arquitectura_API_Servicios.docx`.
- 9 DECISIONES SIN CONFIRMAR al final de R15.
