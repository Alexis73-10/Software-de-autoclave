# Decisiones — Tanda 15 (reorganización y limpieza, sin cambio funcional, 24-oct)

Fuente de verdad de la tanda 15. Origen: `docs/informes/analisis_estructura_proyecto_2026-10-24.md` y la revisión de Cristian del 24-oct (22:00). **Ningún cambio de comportamiento**: misma API, mismos textos, mismos códigos HTTP, misma lógica de roles, misma compilación salvo los nombres de módulos movidos.

## Decisiones de Cristian (24-oct)
- **D1. Orden de la noche:** L0 cerrada y unida a `dev` (la cierra Cristian) → tanda 13 (VAP-01 + compilación I) → tanda 15. La compilación I **no** lleva la reorganización.
- **D2. Alcance:** P0 (limpieza git), P1 reducido (raíz y `docs/`), P2 (autorización fuera de la UI), P4 (partir `server.py`) y P6 ligero (`tests/`). **Fuera:** P3 (datos de ejecución: el `.exe` ya los redirige a `%ProgramData%` vía `utils/resources._ESCRIBIBLES`) y P5 (`core/runtime`, `control_loop`).
- **D3. Ramas viejas** `instalador-setup`, `feature/roles-sensor-temperatura`, `worktree-anuncios-voz` y `main`: intactas. Solo se podan sus worktrees ya inexistentes.
- **D4. Autorización** en paquete propio `src/autoclave/auth/`.
- **D5. Numeración:** esta es la tanda 15; la 14 queda reservada para la salida de RECUPERACION.

## Decisiones de diseño (Claude, chat)
- **D6. `docs/mis_plans/` y `docs/superpowers/` NO se mueven** (los citan CLAUDE.md, la memoria, los prompts y los informes). Se crea `docs/README.md` con el índice de qué va en cada carpeta.
- **D7. Sin reexportes temporales:** los importadores de `roles`/`validacion_usuario` y de `ui/service_ui` se actualizan todos. Un test de arquitectura impide que la dependencia invertida vuelva.
- **D8. Documentos históricos** (`instruccion_*`, `prompt_*`, `decisiones_*` de tandas pasadas, informes) no se editan aunque citen rutas viejas: son registro. Se actualizan solo documentos vigentes (CLAUDE.md, LEEME, `docs/instalacion/`, `docs/riesgos/`, hoja de pruebas de banco, `tools/instalador/`).
- **D9. Archivos sin seguimiento de git** (`installation_profile.json.invalido-*`, `_suites_t11/`, `capturas_calibracion/`, `__pycache__`): **no se borran** (borrado irreversible). Se listan en el informe para que Cristian los borre a mano.
- **D10. No se une a `dev`.** La rama `tanda-15` queda con push como respaldo; Cristian revisa y une. Motivo: refactorización amplia en Clase C sin urgencia; se respeta la confirmación visual antes de integrar.
- **D11. Firmware V2:** solo se corrige el nombre de la carpeta externa (`Comunocacion` → `Comunicacion`); la V2 se conserva. La carpeta interna del sketch ya se llama bien, Arduino no se afecta.

## Ítems
| ID | Qué | Etapa |
|---|---|---|
| ORG-01 | `git worktree prune`; borrar con `git branch -d` las ramas locales `tanda-*` ya unidas a `dev` | G |
| ORG-02 | `Documentacion/*.docx` → `docs/arquitectura/` | R |
| ORG-03 | `parametros_software.accdb`, `data_base/*.xlsx` → `docs/referencia/` (ningún código los usa; verificado 24-oct) | R |
| ORG-04 | Renombrar `Hardware/Comunocacion_esclava_ESP32_V2` | R |
| ORG-05 | Dejar de versionar `docs/informes/**/*.log` (`git rm --cached` + `.gitignore`); quitar `docs/catalogo_alarmas.2026-09-18.bak.md`; reubicar `docs/file_0000…jpg` y `docs/files UI Especifika/` en `docs/diseno/` (con referencias actualizadas) | R |
| ORG-06 | `docs/README.md` (índice) | R |
| ORG-07 | Los 4 `.spec` → `packaging/`, rutas relativas a `SPECPATH`; compilar desde la raíz con `pyinstaller packaging/<x>.spec` | R |
| ORG-08 | `ui_pyside/services/{roles,validacion_usuario}.py` → `auth/` (`git mv`) | U |
| ORG-09 | `ui/service_ui/*` → `src/autoclave/cliente/`; eliminar `ui/` | U |
| ORG-10 | `ui_qml/prueba_*.py` e `historial_ejemplo.py` → `tools/demos_qml/` (los `.qml` de `qml/Pruebas/` se quedan) | U |
| ORG-11 | Test de arquitectura de capas | U |
| ORG-12 | Partir `backend/server.py` en `backend/rutas/*.py` (APIRouter) | B |
| ORG-13 | `tests/helpers/` y `tests/banco/`; quitar `tests/Github.ico` si no se usa; registrar el marcador `req` | T |

Fuera de alcance explícito: mover `IconoEjecucion.qml` (lo carga `PantallaCicloEnCurso.qml`; valor bajo, riesgo de fallo QML en tiempo de ejecución), renombrar paquetes por idioma, `core/runtime`, `control_loop`, datos de ejecución.

## Evaluación normativa (NTC-IEC 62304:2019 / IEC 62304:2006)
1. Toca autenticación (ORG-08, ORG-12: dependencias de token/rol en cada ruta) → Clase C.
2. Solicitud de cambio (8.2.1): este documento + aprobación de Cristian del 24-oct.
3. Riesgo (7.4.1–7.4.2): no introduce causas nuevas **si** se demuestra equivalencia: (a) mismas rutas, métodos, dependencias y orden de coincidencia; (b) mismo OpenAPI; (c) mismos objetos de roles; (d) suite idéntica en número y en verde; (e) compilación equivalente.
4. Arquitectura (5.3): `docs/arquitectura/DOC_Backend_Arquitectura_API_Servicios.docx` queda desactualizado respecto a `server.py`; se registra como pendiente en el informe (no se edita el `.docx` esta noche). CLAUDE.md sí se actualiza.
5. Verificación a repetir (5.6.6, 5.7.3, 8.2.3): suite completa + compilación + humo de los `.exe`.
6. SOUP (8.1.2): sin cambios. Si el `.exe` del backend deja de arrastrar módulos de UI, se anota la diferencia.
7. Trazabilidad (7.3.3): rutas de archivos citadas en `docs/riesgos/` se actualizan en el mismo commit que las mueve.
