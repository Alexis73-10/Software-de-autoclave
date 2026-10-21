# Tanda 5: índice (20-oct-2026)

Rama `tanda-5`, creada desde `dev` (a563a06) y unida a `dev` con `--no-ff` en la etapa Z. Decisiones y preguntas: `tanda5/DECISIONES_PARA_REVISAR.md`. Estado: `tanda5/estado.md`.

| Etapa | Informe | Estado |
|---|---|---|
| E0 | `tanda5/E0_integracion_otra_sesion.md` | Hecha |
| R0 | `tanda5/R0_revision_agentes_tanda4.md` | Hecha |
| P1 ★ | `tanda5/P1_salida_modo_prueba.md` | Hecha |
| P2 | `tanda5/P2_impresora_habilitada.md` | Hecha |
| P3 ★ | `tanda5/P3_renovacion_token_pyside.md` | Hecha |
| O1 ★ | `tanda5/O1_inventario_opciones.md`, `tanda5/O1_parametros_ciclo.md` | Hecha (las entradas mostradas aún no se usan en Preciclo) |
| T1 ★ | `tanda5/T1_matriz_transiciones.md` | Hecha (1 corrección, 12 preguntas) |
| U1 ★ | `tanda5/U1_unidades.md` | Hecha |
| I1 ★ | `tanda5/I1_i18n_backend.md` | Parcial (alarmas e idioma; faltan motivos de puerta, parámetros de fallo y `nombre_clave`) |
| I2 | `tanda5/I2_i18n_qml.md` | Parcial (literales y lecturas; faltan gráficas, textos de Python y capturas) |
| I3 | `tanda5/I3_salidas_backend.md` | Parcial (ticket de ciclo; faltan PDF, correo y tickets de resumen y arranque) |
| O2 | — | **No hecha** (el resto de Opciones sigue en "Próximamente"; ver el inventario de O1) |
| H1 | `docs/mis_plans/hoja_pruebas_banco_equipo_pruebas.md` | Hecha (B-08, C-05, D-15 a D-19, G-02) |
| Z | este índice | Hecha |

## Pasos manuales antes del lunes 26-oct
1. **Push:** si `git push origin dev tanda-5` falló (ver estado.md), hacerlo a mano.
2. Revisar `DECISIONES_PARA_REVISAR.md` y responder las PREGUNTAS de T1, sobre todo P-1, P-2 y P-3.
3. Decidir sobre los cambios sin commit de la otra sesión: teclados, sus pruebas y `bowe_dick.json` (fábrica y usuario).
4. Compilar el ejecutable (`pyinstaller --noconfirm Autoclave.spec`). En esta tanda no se compiló.
5. En el equipo, correr la hoja de banco, empezando por B-01, B-03, B-04, B-08, C-05 y D-18. Con líquidos, G-02.
6. Confirmar si el sensor de chaqueta es absoluto o manométrico antes de usar psig (U1).
7. Dejar `data/unidades.json` en °C/kPa y `data/idioma.json` en "es" (son los valores por defecto si no existen).
8. Verificar el truncado de textos en 1024 px en inglés (D-19). El inglés NO se habilita en campo (R-06).
