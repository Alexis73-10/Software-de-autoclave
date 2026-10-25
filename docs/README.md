# docs/ — qué va en cada carpeta

Índice de la documentación del repositorio (tanda 15, ORG-06). Una línea por carpeta: qué contiene y cómo se nombran sus archivos.

| Carpeta | Qué va ahí | Convención de nombre |
|---|---|---|
| `arquitectura/` | Documentos de arquitectura y diseño del software en Word (backend, ciclo, hardware, ADC, puertas, máquina de estados global). | `DOC_<Tema>.docx` |
| `diseno/` | Sistema de diseño de la interfaz: especificación UI, mockups de entrega, iconos, tokens de color y tipografía (`files UI Especifika/`) e imágenes de referencia. | Libre; los entregables de diseño conservan el nombre con el que llegaron. |
| `handoff/` | Notas de traspaso entre sesiones sobre un tema concreto. | `handoff-AAAA-MM-DD-<tema>.md` |
| `informes/` | Informes de trabajo ya hecho: resultados de tandas, auditorías, revisiones. Son registro: no se editan después. | `informe_tanda_<fecha>_t<NN>.md` (índice de tanda); `informes/tandaNN/` con `estado.md`, informes por etapa (`<Etapa><NN>_<tema>.md`) y `suites/`. |
| `instalacion/` | LEEME de instalación vigente (el que se copia a la entrega y a la USB). | `LEEME_INSTALACION.md` |
| `mis_plans/` | Planeaciones, decisiones, instrucciones y prompts de tanda, más planes de pruebas (hoja de banco). Las de tandas pasadas son registro. | `planeacion_<tema>.md`, `decisiones_tanda_<NN>.md`, `instruccion_claude_code_tanda_<NN>.md`, `prompt_claude_code_tanda_<NN>.md` |
| `mockups/` | Capturas y maquetas de pantallas por tanda o por pantalla. | `<pantalla>/` o `tanda<NN>/` |
| `referencia/` | Material de referencia que ningún código usa: hojas de cálculo de parámetros y base Access original. | Nombre original del archivo. |
| `riesgos/` | Gestión de riesgos y SOUP (IEC 62304 / ISO 14971): registro de riesgos, matriz de trazabilidad, lista SOUP. Se actualizan en el mismo commit que mueve un archivo citado. | `<tema>.md` |
| `superpowers/` | Specs (`specs/`) y planes de implementación (`plans/`) de diseño. | `AAAA-MM-DD-<tema>-design.md` (specs), `AAAA-MM-DD-<tema>.md` (plans) |

Archivos sueltos en `docs/`: `catalogo_alarmas.md` (catálogo de alarmas vigente), `plan_modificaciones_adc_ino.md` y este `README.md`.
