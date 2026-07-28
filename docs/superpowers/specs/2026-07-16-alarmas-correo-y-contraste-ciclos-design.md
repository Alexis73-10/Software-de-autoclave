# Envío de alarmas por correo + corrección de contraste en "Imprimir Ciclos"

## Problema

Dos pedidos relacionados con la sección de impresión (`impresion_menu.py`,
`ciclos.py`):

1. Las alarmas activas sólo se pueden imprimir (`ImpresionMenuView._print_alarms`).
   No existe forma de enviarlas por correo, a diferencia de los ciclos
   guardados, que sí tienen esa opción (`CiclosView._email_selected`).
2. La vista "Imprimir Ciclos" (`CiclosView`) no tiene ningún `styleSheet`
   propio: hereda la paleta del sistema operativo. Con Windows en modo
   oscuro, el fondo de la vista y de la tabla quedan casi negros mientras
   el texto de las celdas (resultado, fecha, programa) se sigue pintando
   oscuro — texto casi invisible sobre el fondo. Confirmado con captura de
   pantalla: los botones y encabezados (estilizados vía qfluentwidgets
   `PushButton`/`SubtitleLabel`) se ven bien, pero el `TableWidget` no.
   Otras vistas de la app (`impresion_menu.py`, `admin_menu.py`,
   `login.py`, vistas de E/S) no tienen este problema porque fuerzan su
   propio fondo con gradiente azul + tarjeta blanca, ignorando el tema del
   sistema.

## Alcance

- Agregar "Enviar Alarmas por Correo" como acción disponible desde
  `ImpresionMenuView`, enviando un PDF de una página con las alarmas
  activas en ese momento (mismo contenido que ya arma
  `_build_alarms_ticket_lines`). No se agrega historial de alarmas en DB
  — sigue siendo un snapshot del estado actual, igual que "Imprimir
  Alarmas".
- Extraer el diálogo de correo (`_EmailDialog` en `ciclos.py`, con
  guardado de contraseña de aplicación vía `keyring` y envío SMTP) a un
  módulo compartido, para reutilizarlo desde `impresion_menu.py` sin
  duplicar el diálogo completo.
- Corregir el contraste de `CiclosView` aplicando el mismo lenguaje
  visual (fondo con gradiente, tarjeta blanca, texto oscuro fijo) que ya
  usa el resto de la app, incluyendo estilos explícitos para el
  `TableWidget` (encabezados, filas, selección).
- Fuera de alcance: persistir historial de alarmas en la base de datos;
  rediseñar el flujo de impresión de ciclos; cambiar el layout general de
  navegación de la app.

## Arquitectura

### 1. Diálogo de correo compartido

Nuevo módulo `src/autoclave/ui_pyside/views/_email_dialog.py`:

- Clase `EmailDialog(QDialog)` — copia exacta de la actual `_EmailDialog`
  de `ciclos.py` (campos Para/De/Contraseña de app/SMTP/Puerto, guardado
  de credenciales en `keyring`, servicio `"Especifika-Autoclave-Email"`).
- Función `send_email(dlg: EmailDialog, attachment_path: str, subject: str, body: str, attachment_name: str)`
  — generaliza el actual `CiclosView._send_email` (hoy fijo a
  `ciclos_autoclave.zip`) para aceptar asunto, cuerpo y nombre de adjunto
  parametrizados, ya que el caso de alarmas envía un único PDF (no un
  zip) con textos distintos.

`ciclos.py` pasa a importar `EmailDialog` y `send_email` desde este
módulo; se elimina la clase y la función duplicadas de `ciclos.py`. El
resto de `_email_selected` en `ciclos.py` seguirá construyendo su zip de
PDFs como hoy — sólo cambia el origen del diálogo y el envío pasa a
llamar a la función compartida con `attachment_name="ciclos_autoclave.zip"`.

### 2. Envío de alarmas por correo

En `impresion_menu.py`:

```python
_PRINT_OPTIONS: list[tuple[str, str, str | None]] = [
    ("📋", "Imprimir Ciclos",  "ciclos"),
    ("🚨", "Imprimir Alarmas", None),
    ("📧", "Enviar Alarmas por Correo", None),
]
```

El bucle que construye los botones ya distingue `target is None` para
conectar una acción en vez de navegar; se extiende con un diccionario de
handlers por texto de botón (`"Imprimir Alarmas": self._print_alarms,
"Enviar Alarmas por Correo": self._email_alarms`) en vez del `if/else`
actual, para no encadenar más ramas.

`_email_alarms(self)`:
1. Igual que `_print_alarms`, obtiene `alarms = self._client.get_status().get("alarms", [])`.
2. Si está vacío → `QMessageBox.information` "No hay alarmas activas." (mismo mensaje que hoy), no abre diálogo.
3. Si hay alarmas → abre `EmailDialog(self)`. Si se cancela, no hace nada.
4. Si se acepta, genera un PDF temporal con `_generate_alarms_pdf(alarms, path)` (nueva función, modelada en
   `CiclosView._generate_cycle_pdf`: mismo tamaño de papel de 55 mm, fuente Courier New 7pt, alto calculado a
   partir del número de líneas de `_build_alarms_ticket_lines`).
5. Llama a `send_email(dlg, path, subject="Alarmas Activas — Especifika Autoclave", body="Adjunto encontrará el reporte de alarmas activas del autoclave.", attachment_name=f"alarmas_{timestamp}.pdf")`.
6. Éxito → `QMessageBox.information` confirmando destinatario. Error → `QMessageBox.critical` con el mensaje de la excepción (mismo patrón que `ciclos.py`).

### 3. Contraste de `CiclosView`

- `CiclosView.__init__` agrega el mismo `setStyleSheet` de fondo con
  gradiente (`#1a3a5c` → `#3a6fa8`) que usan `ImpresionMenuView` y
  `AdminMenuView`.
- El contenido (filtros + tabla + botones) se envuelve en un `QFrame`
  blanco redondeado (`border-radius: 20px`), pero **sin** el
  `setMaximumWidth(460)` que usan los menús — la tarjeta debe ocupar el
  ancho disponible para que la tabla de 6 columnas sea legible.
- Estilos explícitos nuevos:
  - Botón "← Volver": mismo `_BTN_BACK` que ya usan las demás vistas.
  - Labels/BodyLabel de filtros: `color: #1a2a3a`.
  - `TableWidget`: QSS con fondo blanco, texto `#1a2a3a`, encabezado con
    fondo `#f0f2f5` y texto oscuro en negrita, filas alternadas
    (`alternate-background-color: #f8f9fa`), selección
    `background-color: #dbeafe`.
- No cambia ninguna lógica de `_load_data`, `_print_selected`, ni la
  construcción de filas — sólo estilos.

## Manejo de errores

- `_email_alarms` reutiliza exactamente el mismo patrón try/except que
  `CiclosView._email_selected` ya usa alrededor de `send_email` — un
  fallo de SMTP no debe dejar la UI en un estado inconsistente, sólo
  mostrar el error.
- Si `self._client.get_status()` lanza una excepción (backend caído),
  `_email_alarms` la trata igual que `_print_alarms` ya lo hace: alarmas
  vacías → aviso "No hay alarmas activas", sin abrir el diálogo de
  correo (evita pedir credenciales para una acción que no tiene nada que
  enviar).
- El PDF temporal de alarmas se genera con `tempfile.TemporaryDirectory()`
  igual que en `ciclos.py`, así que se limpia solo aunque el envío falle.

## Testing

- `tests/test_email_dialog.py` (nuevo): valida que `EmailDialog` guarda/
  carga la contraseña vía keyring y que `send_email` arma el mensaje
  MIME con asunto/cuerpo/nombre de adjunto parametrizados (mock de
  `smtplib.SMTP`).
- `tests/test_ciclos_print.py`: se ajustan los imports de `_EmailDialog`
  a `EmailDialog` desde el nuevo módulo; el resto de los tests no cambia
  porque el comportamiento de `_email_selected` es el mismo.
- `tests/test_impresion_menu.py`: se agregan tests para
  `_email_alarms` — sin alarmas activas no abre diálogo; con alarmas,
  genera el PDF y llama a `send_email` con los parámetros esperados
  (mock de `EmailDialog.exec` y de `send_email`); fallo de envío muestra
  `QMessageBox.critical`.
- No hay test automatizado de contraste de color (no es una propiedad
  que pytest verifique razonablemente); se confirma visualmente con una
  captura de pantalla de `CiclosView` antes/después, como se hizo durante
  el diagnóstico de este spec.
