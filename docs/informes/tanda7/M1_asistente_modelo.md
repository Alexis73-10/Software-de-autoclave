# M1 — Asistente de instalación con cálculo del modelo comercial

Tanda 7 (noche 21/22-oct-2026). Rama `tanda-7-m1` (desde `e8e42d7`). Spec: `docs/mis_plans/planeacion_asistente_modelo.md` (§2 a §7, aprobada por Cristian).

## Resumen

- El asistente calcula el nombre comercial `SPK-SAT <L><V|H>[2][-LAB]`. El técnico ya no lo escribe.
- Solo se instalan equipos de piso (`piso`, `piso_lab`).
- El perfil guarda `capacidad_litros` y `tipo_carga`. La validación exige que `model_id` sea el nombre calculado.
- El nombre aparece sin cortes en el ticket de 24 columnas.
- Información del sistema muestra la capacidad y el tipo de carga.

## Commits

| Commit | Parte |
|---|---|
| `4ddc0e0` | Módulo puro `installation/modelo.py`, campos del perfil, `storage` y bloqueo en `tools/declarar_*` |
| `bfab0be` | Puente: calcula `model_id`, ignora el de la QML, no instala equipos de mesa y ofrece el slot `calcularModelo`; textos `instalacion.*` |
| `e559950` | `Instalacion.qml`: paso Cámara, retiro del campo Modelo, resumen e indicador; banco offscreen, pruebas y capturas |
| `fe39fe0` | Lugares donde se muestra: ticket y resumen por periodo sin cortes, `/system/info` y pantalla O2d |
| (este) | Riesgo HAZ-INS-02, fila REQ-19 de trazabilidad e informe |

## Archivos modificados

- Nuevo: `src/autoclave/installation/modelo.py`. Es puro (sin Qt) y expone `calcular_modelo`, `clase_instalable`, `CLASES_INSTALABLES`, `TIPOS_CARGA`, `CAPACIDAD_MIN` y `CAPACIDAD_MAX`.
- `src/autoclave/installation/profile.py`:
  - campos opcionales `capacidad_litros` y `tipo_carga`;
  - `_errores_modelo`: los dos campos van juntos y, si están, `model_id` debe ser igual a `calcular_modelo(...)`.
- `src/autoclave/installation/storage.py`: carga y guarda los dos campos solo si existen. Los perfiles viejos no se migran.
- `src/autoclave/installation/cambio_perfil.py`: `escribir_campo` rechaza `model_id`, `equipment_class`, `door_count`, `capacidad_litros` y `tipo_carga`.
- `src/autoclave/ui_qml/bridge/puente_instalacion.py`:
  - `clases` entrega solo las clases de piso;
  - `construir_perfil` rechaza mesa con error i18n, valida capacidad y carga y calcula `model_id`;
  - slot nuevo `calcularModelo`.
- `src/autoclave/ui_qml/qml/Pantallas/Instalacion.qml`:
  - paso "Cámara" y retiro del campo "Modelo";
  - resumen con el nombre en grande;
  - 8 pasos;
  - fila del resumen de 64 px en vez de 72 px (cabe el bloque del nombre).
- `src/autoclave/i18n/es.json`, `en.json`:
  - claves nuevas `instalacion.*` e `info_sistema.*`;
  - se quitan `instalacion.modelo`, `instalacion.modelo_marcador` e `instalacion.error_modelo`, que ya no se usan.
- `src/autoclave/services/domain/logging/ticket_formatter.py`:
  - `ANCHO_TICKET = 24` y `lineas_rotulo()`;
  - el encabezado del ticket de ciclo usa `lineas_rotulo()`.
- `src/autoclave/services/domain/reportes/resumen_periodo.py`: el modelo ya no se corta a 24 caracteres; pasa a la línea siguiente.
- `src/autoclave/backend/server.py`: `/system/info` → `equipo.capacidad_litros` y `equipo.tipo_carga`, con `None` si faltan o no son válidos.
- `src/autoclave/ui_qml/controllers/info_sistema_controller.py`: filas `capacidad` ("45 L") y `tipo_carga` (clave i18n), con "—" si faltan.
- Pruebas:
  - nuevas: `tests/test_m1_modelo.py`, `tests/test_m1_puente_instalacion.py`, `tests/test_m1_asistente_qml.py` y `tests/test_m1_modelo_documentos.py`;
  - banco nuevo: `tests/m1_asistente_banco.py`;
  - ajustadas: `tests/test_t9_instalacion.py` (clases sin mesa, sin `model_id` en los datos), `tests/test_o2d_info_sistema.py` (dos claves nuevas en `equipo`) y `tests/test_i18n.py` (familias `instalacion.carga_` e `info_sistema.carga_`).
- Documentos: `docs/riesgos/registro_riesgos.md` (HAZ-INS-02), `docs/riesgos/matriz_trazabilidad.md` (REQ-19) y `docs/mis_plans/revision_traducciones.md` (inglés nuevo "sin revisar").
- Capturas: `docs/informes/tanda7/capturas/M1_es_01_activacion.png` … `M1_es_12_listo.png`, 1200×1920, en español. Se regeneran con `python tests/m1_asistente_banco.py es` (con `PYTHONPATH=src`).

## Herramientas `tools/declarar_*.py` (§3)

- `declarar_entradas_suministro.py`, `declarar_sondas_temperatura.py` y `emparejar_tarjeta.py` escriben solo `supply_inputs`, `temperature_probes` o `board_id`, a través de `cambio_perfil.escribir_campo`.
- Las tres conservan el resto del perfil tal cual, incluidos `capacidad_litros` y `tipo_carga`, y lo validan antes de escribir. Una edición que dejara `model_id` inconsistente se rechaza.
- Ninguna cambia `model_id`, `door_count` ni `equipment_class`.
- Aun así, `escribir_campo` ahora **rechaza** de forma explícita los cinco campos del modelo con el mensaje "solo cambia reinstalando el perfil" (AM-6). No los recalcula. Pruebas: `test_escribir_campo_rechaza_campos_del_modelo` y `test_escribir_campo_conserva_los_campos_del_modelo`.

## Dónde se muestra (§5)

| Lugar | Estado |
|---|---|
| Ticket de ciclo (cp437, 24 columnas) | Corregido. "Modelo: SPK-SAT 2000H2-LAB" ocupa 26 caracteres y la impresora lo partía. Ahora "Modelo:" va en una línea y el nombre entero en la siguiente. Un nombre corto sigue en una sola línea. |
| Resumen por periodo (24 columnas) | Corregido. Antes `_cortar` dejaba "Modelo: SPK-SAT 2000H2-L". Ahora usa la misma regla que el ticket de ciclo. |
| Ticket de arranque (48) y de mantenimiento (32) | Sin cambios: el nombre cabe. Verificado con pruebas. |
| PDF y correo | Sin cambios: la cabecera `exportacion.empresa` lleva `{modelo}` y el correo adjunta ese PDF. Verificado. |
| Información del sistema (O2d) | Filas nuevas "Capacidad nominal" ("45 L") y "Tipo de carga" (Vertical/Horizontal), debajo del modelo. Muestran "—" en perfiles anteriores. |
| Configuración de la máquina (O2a) | Sin cambios: ya muestra `model_id` en solo lectura (propiedad sin setter, verificado). |

## Pruebas

- Antes: línea base de la tanda, 5020 passed / 2 skipped / 3 xfailed.
- Después: ver "Resultado de la suite completa" al final.
- Cobertura de §6:
  - tabla completa de §2;
  - rechazos de clase: mesa (las tres clases);
  - rechazos de capacidad: 19, 2001, 45.5, "45" y `True`;
  - rechazos de carga: "v" y "X";
  - rechazos de puertas: 0 y 3;
  - el puente ignora el `model_id` de la QML;
  - un perfil con `model_id` inconsistente es inválido y un perfil viejo es válido;
  - `clases` no contiene mesa e instalar mesa da error;
  - QML offscreen: Cámara bloquea "Siguiente" sin datos válidos (también con 19 L), la vista previa cambia en vivo mientras se escribe con el teclado numérico real (4 → "—", 45 → "SPK-SAT 45V2-LAB") y el resumen muestra el nombre;
  - ticket con `SPK-SAT 2000H2-LAB` sin cortes, en es y en.
- **Aviso para quien corra pruebas en este worktree:** el paquete `autoclave` está instalado en modo editable apuntando a la carpeta principal del repositorio. Sin `PYTHONPATH=src`, pytest prueba el código de la carpeta principal, no el del worktree. Las corridas de M1 se hicieron con `PYTHONPATH=src`.

## DECISIONES SIN CONFIRMAR

1. **Un perfil de mesa ya existente se carga sin rechazo** (prevista en la spec §3).
   - Motivo: en campo no existe ninguno y así una carga no tumba el arranque.
   - Alternativa: rechazarlo en `validate_profile_data`.
   - Commit: `4ddc0e0`.
   - Revertir: agregar `clase_instalable` a la validación de carga.
2. **Ticket de 24 columnas: si "Modelo: <nombre>" no cabe, el nombre va entero en la línea siguiente.**
   - Motivo: el nombre no se puede cortar.
   - Alternativa: acortar el rótulo ("Mod.:") o reducir la fuente.
   - Commit: `fe39fe0`.
   - Revertir: volver a la línea única en `format_header` y `format_ticket_resumen`.
3. **`escribir_campo` rechaza los campos del modelo** en vez de recalcular el nombre.
   - Motivo: AM-6, el modelo solo cambia reinstalando.
   - Commit: `4ddc0e0`.
   - Revertir: quitar `CAMPOS_DEL_MODELO`.
4. **El puente acepta una capacidad `45.0` como 45.** QML puede entregar los números como `float`. `calcular_modelo` es estricto y rechaza cualquier `float`; 45.5 se rechaza en ambos casos.
5. **La vista previa la calcula el puente** (slot `calcularModelo`), no JavaScript. Así la regla vive en un solo lugar, `installation/modelo.py`. Sin puente, la pantalla muestra "—".
6. **Información del sistema muestra la capacidad como "45 L"**, con la unidad del SI sin traducir. Alternativa: una clave i18n con `{n} L`.
7. **El error de capacidad aparece al tocar "Siguiente"** (como en los demás pasos). El teclado numérico ya impide confirmar fuera de 20–2000, con el rango resaltado.
8. **Se quitaron las claves i18n `instalacion.modelo`, `instalacion.modelo_marcador` e `instalacion.error_modelo`.** Ya no se usan. Si otra rama las usa, al unir aparecerán como claves faltantes en `tests/test_i18n.py`.
9. **Fila del resumen de 64 px (antes 72 px).** Así caben el bloque del nombre y las dos filas nuevas sin que el aviso de error de guardado tape la última fila.

## PREGUNTAS PARA CRISTIAN

- El ticket de arranque imprime "Clase: piso_lab", el valor crudo, sin traducir. No se tocó (fuera de alcance). ¿Se quiere el nombre legible?
- ¿Se quiere la capacidad y el tipo de carga también en el ticket o el PDF? La spec solo los pide en Información del sistema.

## PROBLEMAS CONOCIDOS PARA MAÑANA

- Ninguno bloqueante para la instalación.
- Las líneas "Num serie: …" del ticket de 24 columnas tienen el mismo riesgo de partirse con series largas (más de 13 caracteres). No es de M1 y no se tocó.
- Al cargar el asistente, el registro muestra avisos i18n de claves vacías (`instalacion.clase_`, `instalacion.puerta_`, `instalacion.vapor_`). Vienen de que el resumen se evalúa sin datos y ya existían antes de M1. No afectan la pantalla.

## Coordinación

- `Instalacion.qml` es punto de choque con P1, que puede hacer cambios mínimos.
- M1 cambió el arreglo `pasos` (agrega `"camara"`), la validación `_validar`, `perfil()`, `filasResumen`, el paso Datos (posiciones `y`) y el Resumen.
- Al unir, conserva los pasos y el diseño de M1 y aplica encima los arreglos de P1.
- En los JSON de i18n, une las claves y quita solo las tres claves de la decisión 8.

## Comprobaciones manuales para Cristian

1. En el equipo sin perfil:
   - el asistente muestra 8 pasos;
   - Tipo de equipo muestra solo Piso y Piso Laboratorio, sin selección.
2. En el paso Cámara:
   - con el campo vacío o sin carga elegida, "Siguiente" no avanza y muestra el error bajo el campo;
   - el teclado numérico no confirma 19 ni 2001;
   - la vista previa cambia mientras se escribe.
3. En el Resumen:
   - el nombre arriba en grande (p. ej. `SPK-SAT 45V2-LAB` con Piso laboratorio y 2 puertas);
   - luego la capacidad ("45 L") y el tipo de carga.
4. Tras instalar:
   - `installation_profile.json` tiene `model_id`, `capacidad_litros` y `tipo_carga` consistentes;
   - Información del sistema muestra el modelo, la capacidad y la carga;
   - el ticket de un ciclo imprime el modelo completo.

## Resultado de la suite completa

- En la rama `tanda-7-m1`: 5139 passed, 2 skipped, 3 xfailed (18 min 10 s; corrida por la sesión principal el 22-oct, 06:05).
- Tras unirla a `tanda-7` (L1 + P1 + M1): 5200 passed, 2 skipped, 3 xfailed.
- Nota de integración: la fila de trazabilidad de M1 se renumeró de REQ-19 a REQ-27, porque Q1 usó REQ-19 a REQ-26.
