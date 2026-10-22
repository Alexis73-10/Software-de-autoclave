# E2 (tanda 8): nombres de familia y modelo

Rama: `tanda-8-e2`. Puntos: D8-0 y D8-3.23.

## Qué se hizo

### D8-0. Hospitalario y Laboratorio

Solo cambió el texto visible, por catálogo i18n. Los valores internos `piso` y `piso_lab`, la validación, la lógica y el nombre del modelo `SPK-SAT …[-LAB]` no cambian. Hay una prueba que lo comprueba.

| Lugar | Antes | Ahora |
|---|---|---|
| Asistente: tarjetas del paso Tipo de equipo y resumen (`instalacion.clase_*`) | Piso / Piso Laboratorio (Floor-standing …) | Hospitalario / Laboratorio (Hospital / Laboratory) |
| Panel de información del equipo del menú (`equipo.clase_*`) | Piso / Piso laboratorio | Hospitalario / Laboratorio |
| Error del asistente al rechazar mesa (`instalacion.error_clase_fuera_alcance`) | "…equipos de piso y de laboratorio de piso" | "…equipos hospitalarios y de laboratorio" ("hospital and laboratory units") |
| Ticket de arranque | `Clase: piso_lab` (valor crudo) | `Clase: Laboratorio` / `Class: Laboratory`, tomado de `equipo.clase_*` en el idioma del ticket. Si una clase no tiene texto, se imprime el valor interno (nunca vacío). |
| Información del sistema | no mostraba la clase | fila nueva "Tipo de equipo" / "Equipment type", debajo de Tipo de carga. `/system/info` entrega `equipo.clase` (valor interno) y la pantalla lo traduce. Un valor desconocido o ausente se muestra "—". |
| PDF (ciclo, resumen y consolidado) | no mostraba la clase | la línea de empresa agrega la familia (ver D8-3.23) |

Los textos son ASCII, así que se imprimen bien en cp437.

### D8-3.23. Capacidad y carga

- **Tickets.** El de ciclo, el de arranque, el de mantenimiento y el resumen por periodo ya llevaban solo el nombre del modelo. No se tocaron. Hay pruebas de que el ticket de arranque y la cabecera del ticket de ciclo no traen capacidad, carga ni familia.
- **Información del sistema.** Capacidad y tipo de carga ya estaban (M1). Se verificó en las capturas.
- **Cabecera del PDF. NO estaban:** la línea de empresa solo llevaba el modelo y la serie. Ahora agrega, con la nueva clave `exportacion.equipo_pdf`, la familia, la capacidad y la carga:
  `Especifika S.A.S. · Autoclave SPK-SAT 45V2-LAB · Serie SN-0001 · Laboratorio · 45 L · Carga vertical`
  - Aplica a los tres PDF: ciclo, resumen por periodo y consolidado.
  - Los datos salen del nombre de modelo guardado con el ciclo o con el resumen, con la función nueva `desglosar_modelo()` en `installation/modelo.py`. Es el inverso exacto de `calcular_modelo` y se verifica en ida y vuelta.
  - Con un modelo anterior a M1 (por ejemplo "ACV-150"), la línea queda como antes.
  - Una prueba comprueba que el caso más largo (2000 L, dos puertas, laboratorio, serie de 15 caracteres) cabe en el ancho de la hoja en es y en en.

## Commits

- `5c335fa` feat(tanda8-e2): familias Hospitalario/Laboratorio por catálogo y capacidad/carga en el PDF
- `66ab60b` docs(tanda8-e2): capturas del asistente e Información del sistema en es y en
- (este informe y el log de la suite, en el commit siguiente)

## Archivos tocados

- **Puntos de choque:**
  - `src/autoclave/i18n/es.json` y `en.json`:
    - claves cambiadas: `instalacion.clase_piso` y `instalacion.clase_piso_lab`, `equipo.clase_piso` y `equipo.clase_piso_lab`, `instalacion.error_clase_fuera_alcance`;
    - claves nuevas: `info_sistema.rotulo_clase`, `exportacion.equipo_pdf`, `exportacion.carga_V` y `exportacion.carga_H`.
  - `src/autoclave/backend/server.py`: un campo más en `/system/info`.
  - No se tocó ningún QML: E1 cambia `Instalacion.qml` y no hay choque.
- **Código:**
  - `devices/printer/startup_ticket.py`;
  - `installation/modelo.py`;
  - `ui_qml/controllers/info_sistema_controller.py`;
  - `ui_qml/bridge/acciones_ciclos.py`.
- **Pruebas:**
  - nueva: `tests/test_e2_nombres_familia.py`, con 45 casos;
  - ajustadas:
    - `tests/test_i18n.py`: familias dinámicas `equipo.clase_` y `exportacion.carga_`;
    - `tests/test_o2d_info_sistema.py`: campo `clase` en `/system/info`.
  - arneses:
    - `tests/m1_asistente_banco.py`: carpeta de capturas configurable, títulos de las tarjetas de clase y valor del resumen;
    - `tests/opciones_qml_doble.py`: parámetros opcionales `idioma` y `carpeta`. Sin ellos, se comporta igual que antes.

## Pruebas nuevas (`tests/test_e2_nombres_familia.py`)

- Catálogo: es y en en los dos grupos. Ningún texto de clase dice "piso" ni "floor".
- Valores internos y `calcular_modelo` sin cambio.
- Ticket de arranque:
  - la clase sale traducida en es y en, para las dos clases;
  - no aparece "piso";
  - el texto se puede codificar en cp437;
  - no trae capacidad ni carga;
  - una clase sin texto se imprime con su valor interno.
- Cabecera del ticket de ciclo: solo el modelo.
- `/system/info` entrega `clase`. `grupos_de` arma la fila `clase` con `equipo.clase_*` y muestra "—" si el valor es desconocido.
- `desglosar_modelo`: casos válidos, ida y vuelta, y 8 nombres inválidos.
- Línea de empresa del PDF:
  - en es y en;
  - modelo antiguo sin desglose;
  - cabe en el ancho de la hoja.
- QML offscreen:
  - asistente en es y en: títulos de las tarjetas, resumen y perfil instalado con `equipment_class = piso_lab`;
  - Información del sistema en es y en, con la fila nueva visible y sin "piso_lab".

## Capturas (`docs/informes/tanda8/capturas/e2/`)

- `E2_es_asistente_equipo.png` y `E2_en_asistente_equipo.png`: paso Tipo de equipo.
- `E2_es_asistente_resumen.png` y `E2_en_asistente_resumen.png`: resumen.
- `E2_es_info_sistema.png` y `E2_en_info_sistema.png`: Información del sistema.

Para regenerarlas: `E2_CAPTURAS=1 PYTHONPATH=<worktree>/src python -m pytest tests/test_e2_nombres_familia.py -k "pantalla or asistente"`. El arnés del asistente también guarda los pasos de M1. Se conservaron solo el paso de equipo y el resumen, renombrados.

## Suite completa

`autoclave.__file__` = `C:\Users\tecni\Documents\codigo_autoclave\.claude\worktrees\agent-a5c1633b466a51510\src\autoclave\__init__.py`

Resultado: **5427 passed, 3 skipped, 3 xfailed** en 27 min 12 s (log en `docs/informes/tanda8/suites/e2.log`).

## DECISIONES SIN CONFIRMAR

1. **Fila "Tipo de equipo" en Información del sistema.** D8-0 pide la familia en Información del sistema, pero la pantalla no mostraba la clase. Se agregó una fila después de Tipo de carga, con el mismo rótulo que el asistente ("Tipo de equipo"). Así no cambia el orden que fijó M1 (modelo, capacidad, carga).
   - Revertir: quitar la fila en `grupos_de` y `CLAVES_FILA`.
2. **Capacidad y carga en la cabecera del PDF.** La decisión dice "ya están", pero no estaban. Se agregaron a la línea de empresa, junto con la familia, deducidas del nombre del modelo guardado con el ciclo. Se dedujeron del nombre y no del perfil actual por dos razones: el PDF de un ciclo describe el equipo con el que se corrió, y así no hace falta otro camino de datos. Un modelo anterior a M1 no muestra esos datos.
   - Alternativa: columnas propias en la fila de campos de la cabecera.
3. **Rótulo "Clase:" del ticket de arranque.** Se conservó; solo cambió el valor.
4. **Texto del error de clase fuera de alcance.** Se actualizó para no decir "piso". El asistente ya no ofrece mesa, así que es un error de respaldo.

## PREGUNTAS PARA CRISTIAN

- ¿Prefiere "Familia" en lugar de "Tipo de equipo" como rótulo de la fila en Información del sistema?
- En el PDF, ¿la familia, la capacidad y la carga van bien en la línea de empresa, o las quiere como columnas de la cabecera?

## Pendientes

- Ninguno de E2. V8b revisa los catálogos.
