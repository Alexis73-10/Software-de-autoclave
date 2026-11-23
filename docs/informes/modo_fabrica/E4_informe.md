# Modo fábrica, Etapa 4: paquete de liberación

Fecha: 22-nov-2026. Rama `modo-fabrica`. Base:
- spec `docs/mis_plans/planeacion_modo_fabrica.md`: D-04, FAB-02, §7, §6.1 (USB), pruebas P-07 y P-09;
- revisión `R_revision_plan.md`: R-06, «`historial.db` del paquete», USB sin prueba de escritura ni validación de espacio;
- decisiones `decisiones.md`: DF-08, PA-03.

La Etapa 4 deja la generación y verificación del paquete lista para el cierre (Etapa 5). No implementa el cierre ni agrega rutas: ninguna ruta llama todavía a `generar_paquete_liberacion`.

## Qué se hizo

### 1. Módulo `core/runtime/paquete_liberacion.py` (nuevo)

Ruta del ZIP: `<USB>/Especifika_liberaciones/liberacion_<serie>_<AAAAMMDD-HHMM>.zip`. Si ya existe un archivo con ese nombre (dos paquetes en el mismo minuto), se agrega `_2`, `_3`…

Secuencia de `generar_paquete_liberacion`:
1. Arma el contenido en una carpeta temporal local.
2. Calcula los hashes y el manifiesto.
3. Comprueba la USB con el tamaño estimado.
4. Escribe `<nombre>.zip.tmp` con fsync.
5. Lo relee con `verificar_paquete`.
6. Lo renombra con `os.replace`.

Ante cualquier fallo borra el temporal (y el final si existiera), además de la carpeta `Especifika_liberaciones` si la creó y quedó vacía. La USB queda como estaba (FAB-02).

Contenido (D-04, «todo»):

| Ruta en el ZIP | Origen |
|---|---|
| `informe_liberacion.pdf` | Ver abajo. |
| `ciclos/ciclo_<NNNNNN>_<id>.pdf` | Un PDF por ciclo de la base, con gráfica, alarmas y ticket (`format_ticket`, el mismo texto de la reimpresión). El `id` va en el nombre por si hubiera números repetidos. |
| `historial.db` | Copia completa de la base (API de respaldo de SQLite bajo el lock del `DbManager`). En la copia, `usuarios.hash_pw` y `usuarios.codigo_creacion` quedan en NULL (P-09). `hash_pw` es NOT NULL en el esquema, así que la tabla se reconstruye con las mismas columnas y se recrean sus índices y triggers. Después se hace VACUUM (no quedan hashes en páginas libres) y se pasa a diario DELETE (un solo archivo). La base viva no se toca. |
| `bitacora.csv` | `audit_log` completo, en orden de id: id, fecha, usuario, rol, evento, entidad, valor_anterior, valor_nuevo, detalle. UTF-8 con BOM, separador «;». Incluye también los eventos retirados que la vista oculta. |
| `calibracion.yaml` | Copia del archivo de calibración vigente. |
| `parametros.json` | `{clave: valor}` vigente del equipo. |
| `programas/*` | Los `*.json` y `*.lst` de `cycles/user` (incluye `fabrica_vistos.lst`, `fabrica_borrados.lst` y `numeros_usados.json` si está ahí). |
| `asignacion_io.json` | Asignación de E/S vigente. Sin archivo = asignación de fábrica: queda como ausente. |
| `respaldo_ciclos/**` | Pendientes e `importados/`, recursivo. |
| `logs/<carpeta>/*.log` | `logs/data/` (`datos\data\*.log`) y `logs/logs/` (`datos\logs\*.log`). |
| `manifiesto.json` | Ver abajo. |

Manifiesto:
- `tipo: "liberacion"`, `formato: 1`, `version_sw` (`version_completa()`), `serie`, `modelo`, `tipo_instalacion`; en automatización, además `serial_original` y `modelo_original`;
- `creado_en`, `creado_por`;
- `archivos` (`{ruta: sha256}`) y `ausentes` (`[{ruta, motivo}]`);
- `hash`: mismo cálculo que los respaldos (`respaldo.hash_manifiesto`).

Un archivo que falta queda en `ausentes`. La base es la excepción: si no se puede copiar, se aborta con `sin_base`. Si falla el PDF de un ciclo, queda como ausente con `error_generacion: <excepción>` y el paquete sigue (E4-D6).

Informe de liberación (`informe_liberacion.pdf`):
- Equipo: serie y modelo; en automatización, serie y modelo originales más el serial Especifika.
- Tipo de instalación, versión del software, fecha, ingeniero (nombre y usuario).
- Calibración final por sensor: función, puerto, ganancia, offset y polinomio de la sección `user`, según la asignación vigente.
- Parámetros finales del equipo con su unidad.
- Programas de fábrica (números 1 a 10) con todos sus parámetros. Los programas fuera de ese rango van aparte, solo con su nombre.
- Ciclos de prueba: número, programa, inicio, resultado, fallo (código y motivo) y alarmas del ciclo.
- Contadores al cierre:
  - calculados de la base: ciclos, último número, ciclos por resultado, alarmas, filas de bitácora, mantenimientos;
  - más los que pase el llamador.
- Archivos ausentes.
- PA-03: espacio de firma «Ingeniero que libera» y «Aprobó», cada uno con Nombre, Fecha y Firma. Las dos firmas van en la misma página.

### 2. PDF sin Qt (`services/domain/exportacion/`, nuevo)

`ui_qml/exportacion/pdf_ciclo.py` dibuja con QPainter sobre QPdfWriter y necesita un `QGuiApplication`. El proceso del backend no lo tiene, y la capa backend/core no puede importar la UI. No se movió ese generador. En su lugar hay dos módulos nuevos:
- `pdf_basico.py`: escritor de PDF mínimo en Python puro (A4, Helvetica y Courier en WinAnsi, texto, líneas, polilíneas, rectángulos, pie con «Página n de N»). Su salida es determinista.
- `pdf_liberacion.py`: `informe_pdf(datos)` y `ciclo_pdf(datos)`.

El PDF del correo no cambió. Se verificó a ojo renderizando los dos PDF con QtPdf.

### 3. DF-08 / R-06 en los respaldos

- `core/runtime/respaldo.py`:
  - `TIPO_RESPALDO`, `TIPO_LIBERACION`, `hash_manifiesto` (pública; `_hash_manifiesto` queda como alias) y `tipo_manifiesto(m)`: sin campo da «respaldo».
  - `crear` agrega `"tipo": "respaldo"`. El resto del formato no cambia y los respaldos anteriores siguen verificando.
  - `validar_para_equipo` devuelve `paquete_no_restaurable` para cualquier tipo distinto de «respaldo», antes que los demás motivos. Así la lista de la USB lo muestra como rechazado.
- `backend/rutas/respaldo.py`: `/backup/restore` responde **422 `paquete_no_restaurable`**, con `confirmar` o sin él, y registra `respaldo_rechazado` con el tipo.
- `/backup/usb` ya buscaba solo `Especifika_respaldos/respaldo_*.zip`, y `ruta_respaldo_segura` rechaza salir de esa carpeta. Nada de `Especifika_liberaciones` se lista ni se restaura (lo fija una prueba).
- `ui_qml/sesion_backend.py`: `paquete_no_restaurable` → `respaldo.err_paquete_no_restaurable`, con textos es/en.

### 4. USB (6.1 / P-07)

`comprobar_usb_para_liberacion(carpeta_usb, bytes_necesarios)`:
- hace una prueba real de escritura: crea un archivo oculto en la raíz, hace fsync y lo borra;
- exige libre ≥ `espacio_requerido(bytes)` = bytes × 1,5 + 20 MB.

Códigos: `usb_ausente`, `usb_no_escribible`, `usb_sin_espacio`. `generar_paquete_liberacion` la llama con el tamaño real sin comprimir del contenido armado.

## API para el cierre (Etapa 5)

```python
from autoclave.core.runtime import paquete_liberacion as pl

pl.CARPETA == "Especifika_liberaciones"; pl.TIPO == "liberacion"; pl.FORMATO == 1

class pl.ErrorPaquete(Exception): codigo: str; detalle: str
@dataclass(frozen=True)
class pl.ResultadoPaquete: ruta: Path; hash_global: str; tamano: int; hash_manifiesto: str; ausentes: tuple

@dataclass
class pl.FuentesPaquete:
    copiar_base: Callable[[Path], None]      # pl.copiar_base_desde(db)
    equipo: dict                             # serie, modelo, tipo_instalacion, serial_original, modelo_original
    version_sw: str
    parametros: list | dict = []             # config_manager.describir() o {clave: valor}
    ruta_calibracion: Path | None = None
    carpeta_programas: Path | None = None    # cycles/user
    ruta_asignacion_io: Path | None = None
    carpeta_respaldo_ciclos: Path | None = None
    carpetas_logs: dict = {}                 # {"data": Path, "logs": Path}
    mapas_sensores: dict | None = None       # None = EstadoAutoclave.map_temp/map_pres
    contadores: dict = {}                    # filas extra del informe

pl.copiar_base_desde(db) -> Callable[[Path], None]
pl.fuentes_del_equipo(context, contadores=None) -> FuentesPaquete     # rutas reales desde BackendContext
pl.espacio_requerido(bytes_necesarios: int) -> int
pl.comprobar_usb_para_liberacion(carpeta_usb, bytes_necesarios: int) -> int   # bytes libres
pl.generar_paquete_liberacion(fuentes, carpeta_usb, usuario: str, ahora: datetime | None = None) -> ResultadoPaquete
pl.verificar_paquete(ruta) -> str                                     # hash global
pl.nombre_paquete(serie, ahora) -> str
pl.anonimizar_base(ruta) / pl.bitacora_csv(conn)                      # auxiliares públicas
```

Códigos de `ErrorPaquete`:
- al armar: `usb_ausente`, `usb_no_escribible`, `usb_sin_espacio`, `sin_base`, `error_generacion`;
- al verificar: `ilegible`, `sin_manifiesto`, `manifiesto_invalido`, `manifiesto_alterado`, `tipo_invalido`, `archivo_faltante`, `archivo_no_declarado`, `hash_invalido`.

`hash_global` (para `estado_fabrica.hash_paquete`) es el SHA-256 del ZIP completo.

Para el cierre:
- Antes de armar, la USB se puede comprobar con `comprobar_usb_para_liberacion(unidad, 0)`; la generación vuelve a comprobarla con el tamaño real.
- La unidad debe venir de `respaldo.unidades_usb()` (USB extraíble), igual que en `/backup`.
- `fuentes_del_equipo` toma `context.profile`, `config_manager`, `cycle_manager.carpeta("cycles/user")`, `asignacion_io.ruta_por_defecto()`, `data/respaldo_ciclos` y `data/` y `logs/` bajo `app_root()`.
- La generación tarda en proporción a los ciclos (un PDF por ciclo y VACUUM de la copia): conviene correrla fuera del lazo y con un aviso de progreso.

## Archivos

- Nuevos:
  - `src/autoclave/core/runtime/paquete_liberacion.py`
  - `src/autoclave/services/domain/exportacion/__init__.py`, `pdf_basico.py` y `pdf_liberacion.py`
- Cambiados:
  - `src/autoclave/core/runtime/respaldo.py`
  - `src/autoclave/backend/rutas/respaldo.py`
  - `src/autoclave/ui_qml/sesion_backend.py`
  - `src/autoclave/i18n/es.json` y `en.json`
- Pruebas nuevas (33):
  - `tests/test_fab_e4_paquete.py` (25)
  - `tests/test_fab_e4_respaldo.py` (8; reutiliza la fixture `api` de `test_o2h_respaldo.py`)

## Pruebas

- Contenido completo del ZIP:
  - sin `.txt` ni otros archivos ajenos;
  - nada temporal en la USB;
  - PDF válidos;
  - `parametros.json` correcto.
- Manifiesto: `tipo` «liberacion», `hash` verificado, SHA-256 de cada archivo, `verificar_paquete` igual al SHA-256 del ZIP.
- Informe con todas las secciones y las firmas; en automatización, con los originales.
- PDF de ciclo con la gráfica, las alarmas y el ticket.
- P-09: la copia no contiene el hash ni el código de creación, ni siquiera como bytes sueltos, y sus filas quedan en NULL. Se conservan los ciclos, las lecturas y los triggers de usuarios; `integrity_check` da ok y el diario queda en `delete`. La base viva conserva el hash.
- Bitácora CSV con BOM y todas las filas, con «;» y comillas bien escapados.
- Verificación: falla con un archivo cambiado, un archivo faltante, un archivo sin declarar, el manifiesto alterado, sin manifiesto, un byte del ZIP alterado, y con un respaldo (`tipo_invalido`).
- P-07:
  - sin USB, `usb_ausente`;
  - sin espacio (incluido el borde exacto del margen), `usb_sin_espacio`;
  - USB no escribible, `usb_no_escribible`;
  - escritura cortada a mitad, verificación fallida o sin base: en todos los casos la USB queda vacía.
- Ausentes registrados en el manifiesto; dos paquetes en el mismo minuto no se pisan.
- DF-08:
  - un respaldo nuevo lleva el tipo;
  - un manifiesto sin tipo se acepta y se restaura;
  - con tipo «liberacion», 422 `paquete_no_restaurable` (con y sin confirmar) y no aplica nada;
  - un ZIP de liberación renombrado como respaldo también se rechaza;
  - la lista de la USB no muestra `Especifika_liberaciones`;
  - hay texto es/en.
- Subconjunto (`-k "respaldo or backup or pdf or exportacion or arquitectura or fab_ or t15_rutas or sesion_backend or i18n"`): **857 en verde**. La suite completa no se corrió (la corre el coordinador).
- P-12 (`test_src_no_tiene_drop_trigger`): la anonimización no usa `DROP TRIGGER`. Los triggers viajan con la tabla renombrada, desaparecen con su `DROP TABLE` y se recrean con su SQL original.

## Decisiones tomadas en esta etapa (todas `DECISIÓN SIN CONFIRMAR`)

- **E4-D1.** PDF del paquete con un escritor propio en Python puro y no con el generador Qt del correo. Este necesita un `QGuiApplication`, que el backend no tiene, y la regla de capas lo impide. Alternativa descartada: un rol `Autoclave.exe --rol pdf-lote` que el backend lanzaría como subproceso con Qt offscreen. Daría PDF idénticos a los del correo, a cambio de otro rol, más integración con el compilado y otro punto de fallo en el cierre. matplotlib está excluido del compilado. Los PDF del paquete tienen el mismo contenido (datos, gráfica, alarmas, ticket) con un diseño más simple.
- **E4-D2.** Los textos del informe y de los PDF de ciclo van en español fijo, no por i18n: es un registro interno de Especifika.
- **E4-D3.** El hash global es el SHA-256 del archivo ZIP completo, no el `hash` del manifiesto. Se comprueba con cualquier herramienta y cubre también el manifiesto. Los dos van en `ResultadoPaquete`.
- **E4-D4.** Espacio exigido en la USB: tamaño sin comprimir × 1,5 + 20 MB.
- **E4-D5.** CSV con separador «;» (Excel con configuración regional de Colombia) y UTF-8 con BOM. La bitácora incluye todas las filas, también las de eventos retirados.
- **E4-D6.** Si falla el PDF de un ciclo, el paquete no se aborta: queda en `ausentes` con el motivo y figura en el informe. La base sí es obligatoria. Un fallo al anonimizar la copia aborta (`error_generacion`): nunca sale una base con hashes.
- **E4-D7.** Programas: al ZIP van todos los `*.json` y `*.lst` de `cycles/user`, pero no los `.bak`. En el informe, «programas de fábrica» son los de número 1 a 10 con todos sus parámetros; los demás se listan solo por nombre.
- **E4-D8.** El nombre del PDF de ciclo lleva el número y el id de la base (`ciclo_000002_2.pdf`), para que no choquen dos números repetidos.
- **E4-D9.** El informe no incluye la calibración de fábrica del equipo (`calibracion_fabrica_equipo.yaml`) ni `parametros_fabrica_equipo.json`. En el cierre se escriben después del paquete y valen lo mismo que lo vigente que sí va.
