# Tanda registro_carga: registro de la carga con lector de código de barras (RCB-01..09) (19-nov-2026)

Responde e informa SOLO en español. Especificación: `docs/mis_plans/planeacion_registro_carga.md` (decisiones de Cristian del 19-nov). Léela completa antes de empezar y síguela. Las pantallas de `docs/diseno/mockups/registro_carga/` (`rcb_1_preciclo.png`, `rcb_2_ventana_carga.png`, `rcb_3_catalogo.png`) están aprobadas por Cristian (19-nov): reprodúcelas con los componentes y colores existentes; `pdf_ciclo_con_carga.pdf` es la referencia de la sección «Carga del ciclo» del PDF y del bloque de la tirilla. Ante una ambigüedad, elige lo más simple y anótalo como `DECISIÓN SIN CONFIRMAR` en el informe. Máximo 4 subagentes a la vez; los subagentes no corren la suite completa. No toques el control del ciclo, las fases, las salidas ni la seguridad de la cámara: si algo de la especificación lo exige, detente y anótalo.

## Requisito previo
- Parte de `dev` (1.0.0-beta.4). Verifica que no haya cambios pendientes en `src/`, `tests/`, `tools/` ni `packaging/`. Los de `docs/`, `AJUSTES.md`, `Hadware/`, los `.log` y `habblaud/` de Cristian no cuentan: no los toques. Si hay cambios pendientes, escribe `docs/informes/registro_carga/CERRADO.txt` con `BLOQUEADO: árbol con cambios pendientes` y termina.
- Crea la rama `registro-carga` desde `dev`. Lleva `docs/informes/registro_carga/estado.md` al día tras cada commit; al reanudar, sigue desde el primer paso pendiente.

## Pasos (un commit por paso)
1. Base de datos: migración v15 (§6 y RCB-06.4) con su prueba sobre una base v14 con datos.
2. Parámetros del programa (§4): los dos parámetros en los 6 programas de fábrica y de usuario, catálogo de parámetros, rótulos y ayuda es/en, y la migración al cargar (auditoría, `.bak`, idempotente, sin SIS-06).
3. Catálogo en el backend (§9): servicio de dominio puro, rutas, roles, bitácora e importación CSV desde USB con vista previa y aplicación todo o nada.
4. Inicio con carga (§5): validación en `rutas/ciclo.py` dentro de `bloqueo_maquina()`, `estado.carga_inicio` siguiendo el camino de `operador_inicio`, escritura en `crear_ciclo` (misma transacción), respaldo y reimportación, y detalle de la bitácora. Códigos 409 `carga_requerida` y 422 `carga_invalida`, con textos es/en en `sesion_backend.py`.
5. Tirilla (§7), PDF, correo y detalle del ciclo (§8), con «CARGA NO ESTÉRIL» y reimpresión con el modo guardado.
6. Historial: búsqueda inversa `GET /cycle/history?carga=` y su campo en la pantalla (RCB-07.3).
7. UI (§10 y RCB-08.1/08.2): `ui_qml/domain/registro_carga.py` con su puente, `Componentes/VentanaCarga.qml`, el botón «Carga» en `PantallaPreciclo.qml` solo en la pantalla de carga (puerta 1), envío en `comandos_ciclo`, limpieza del borrador, y la pantalla Opciones › Catálogo de carga. Captura del lector como teclado HID con foco en un campo invisible y Enter como fin de lectura, solo con la ventana abierta. Usa `abrirAlfanumericoAccion` para la entrada manual (regla de la tanda 22). Colores solo de `Tema/Colores.qml`, sin `elide`, textos es/en.
8. Pruebas de §12. Regenera la base de `tests/test_t15_rutas_equivalentes.py` (`docs/informes/tanda15/base/`) por las rutas nuevas y explica el cambio en el informe.
9. Revisión (un subagente revisor) sobre HAZ-RCB-01/02/03: que la carga no pueda caer en otro ciclo, que todo ciclo no COMPLETADO con carga diga «no estéril» en las cuatro salidas (tirilla, PDF, correo, historial), y que la captura no escriba fuera de la ventana. Corrige lo que salga ALTA y MEDIA; lo BAJA va al informe.

## Cierre
- Suite completa en verde.
- `CLAUDE.md`: sección corta «Registro de la carga con lector (RCB, 19-nov)», con rutas, tablas, parámetros, archivos y riesgos.
- Riesgos HAZ-RCB-01..05 en `docs/riesgos/registro_riesgos.md`; trazabilidad REQ-107..REQ-115 (uno por RCB-01..09; si ya están ocupados, usa los siguientes libres y dilo en el informe); bloque RCB (RCB-B1..B6) en `docs/mis_plans/hoja_pruebas_banco_equipo_pruebas.md`.
- Informe `docs/informes/registro_carga/R_informe.md`: cambios por RCB, migraciones, rutas nuevas, pruebas agregadas o modificadas, hallazgos del revisor y lista de `DECISIÓN SIN CONFIRMAR`.
- Merge a `dev`. NO compiles: al cerrar, di que no se compiló y da el comando `python tools/entrega/compilar_entrega.py`.
- Último acto: `docs/informes/registro_carga/CERRADO.txt` (fecha, commit del merge, resultado de la suite). Si un bloqueo necesita a Cristian, escríbelo igual, con `BLOQUEADO:` en la primera línea.
