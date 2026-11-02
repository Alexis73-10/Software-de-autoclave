# Modo oscuro: estado

Rama `modo-oscuro` (desde `dev` c43b9d0b). Prompt: `docs/mis_plans/prompt_claude_code_modo_oscuro.md`. Plan: `plan.md`.

| Paso | Descripción | Estado |
|---|---|---|
| 1 | Inventario y plan (sin tocar código) | Hecho |
| 2 | Mecanismo de tema (Colores + Apariencia + persistencia + slot) | Hecho (conjunto A) |
| 3 | Eliminar literales de color fuera de `Tema/` | Parcial: conjuntos A, B (ciclo) y D (menú, sesión, instalación, Opciones) hechos; C pendiente (`_PENDIENTES` de `tests/test_tema_oscuro.py`) |
| 4 | Componentes con color propio e íconos | Parcial: chrome y fondos (A) y conjunto C (comunes, modales, teclados, alarmas) y B (Preciclo, Ciclo en curso, fases, gráfica, deslizador; OSC-20) y D (OSC-18/19) hechos |
| 5 | Selector en Opciones (i18n Tema/Claro/Oscuro) | Hecho |
| 6 | Pruebas automáticas (`test_tema_oscuro.py`, existentes, suite) | Parcial: `test_tema_oscuro.py` en verde; suite completa pendiente (al final) |
| 7 | Capturas en ambos temas | Hecho (40 capturas en `capturas/`, `LEEME.md`; claro idéntico a dev salvo borde de íconos; hallazgos de oscuro: campos del Login blancos, «PUERTA CERRADA» deshabilitado, chevron de Tiempos) |
| 8 | Riesgos, trazabilidad, CLAUDE.md, `R_informe.md` | Hecho (HAZ-OSC-01, REQ-OSC-01, sección en CLAUDE.md, `R_informe.md` borrador con «Capturas» PENDIENTE) |
| 9 | Revisión, merge a `dev` sin push, `CERRADO.txt` | Pendiente |

Commits del conjunto A: 658538d2 (persistencia y /theme), e2edffd0 (Colores y Apariencia), 017cf808 (selector), 937c15a6 (fondos y chrome) y el de las pruebas (ver `git log -1`).

Para B, C y D: al migrar un archivo, quitarlo de `_PENDIENTES` en `tests/test_tema_oscuro.py` (la prueba falla si queda en la lista un archivo ya limpio).

Corrección OSC-21/OSC-22 (3 defectos de oscuro de las capturas): `fondoCampo`, `iconoCampo`, `puertaCerradaTexto/Borde`; capturas de oscuro login y preciclo_preparado actualizadas; test_tema_oscuro y pruebas QML de Login/Preciclo/NuevoUsuario/IndicadorPuerta en verde. Ver `git log -1`.

Cambios del revisor: `IndicadorPuerta` texto/ícono con `puertaCerradaTexto`; comentarios de color por posición (OSC-23); pruebas de `puertaCerradaTexto` y de uso único de `fondoGradiente`.
