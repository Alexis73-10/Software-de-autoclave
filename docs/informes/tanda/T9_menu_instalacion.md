# T9 — Menú de instalación conectado

Instrucción: tanda 2026-10-14 §2 T9 con la decisión 1.7; `planeacion_menu_instalacion_ui.md` §5 y §6 (ARR-02 / MIG-07).

## 1. Qué se hizo

**Puente real** (`ui_qml/bridge/puente_instalacion.py`, nuevo). Cumple el contrato de §5:
- `clases`: capacidades por clase, tomadas de `get_capabilities`.
- `validarCodigo(serie, codigo)`: código de activación del día (`activation.py`). Un intento inválido queda en el log, igual que antes.
- `instalar(perfil) -> {ok, error}`. Vuelve a validar todo lo que validó la pantalla (la UI no es la barrera):
  - el código del día;
  - la clase;
  - puertas, puerta del PC y enfriamiento dentro de la capacidad de la clase (con 1 puerta, la puerta del PC queda en 1);
  - el tipo de puerta y `vapor_source` (`generator | boiler | mixed`);
  - `temp_camara` siempre instalada, y los suministros por defecto en «cableado» (falla cerrada).

  El perfil se escribe bloqueado (`locked=True`, `role=operator_front`, `created_at` en UTC sin zona, igual que el asistente anterior).

**Nunca se sobrescribe un perfil válido.** Un perfil existente pero inválido no se borra (el asistente anterior lo borraba): se aparta como `installation_profile.json.invalido-<fecha>`.

**Arranque** (`ui_qml/app.py`). En la ventana principal (puerta 1), si falta el perfil o es inválido (`requiere_instalacion()`), se abre `InstalacionVentana.qml` (nuevo) en lugar de `Main.qml`:
- La ventana contiene el asistente `Pantallas/Instalacion.qml` y su teclado en pantalla.
- La puerta 2 abre el menú normal, donde el arranque del backend informa `ARR_PERFIL`.
- Un reloj alterado (`ClockTamperedError`) no abre el asistente: el arranque lo informa como `ARR_RELOJ`, que es bloqueante.
- Al terminar, el botón del resultado cierra la aplicación (código 3, que el lanzador no relanza). El texto existente pide reiniciar el software, porque el backend arrancó sin perfil.

**Lo que no se hizo:**
- **`wizard.py` no se retiró**: lo siguen usando `autoclave/main.py` y `autoclave/ui/main.py`, el arranque tkinter que aún existe (§8 de `planeacion_arranque_y_modo_sin_bd.md`).
- Sin diálogo de clave de fabricante. `factory_dialog.py` sigue sin usarse.
- Etiquetas de los tipos de puerta: provisionales, sin cambios.
- Sin USB de recuperación.
- La etapa "Verificando sensores" sigue oculta en la barra de arranque; no se tocó.

## 2. Pruebas

`tests/test_t9_instalacion.py` (20). Cubre:
- clases y validaciones de `construir_perfil`, incluidos los rechazos;
- código revalidado;
- que no se sobrescribe un perfil válido;
- que un perfil inválido se aparta;
- reloj alterado;
- el puente completo;
- la carga de `InstalacionVentana.qml` offscreen sin avisos de QML;
- `app.main`: el asistente se abre solo en la puerta 1 y solo sin perfil.

## 3. DECISIONES SIN CONFIRMAR

- D-T9-1: el asistente solo se abre en la puerta 1. La puerta 2 muestra el menú con el fallo de arranque.
- D-T9-2: al terminar se cierra la UI con el código 3 y el lanzador no la relanza. **Hay que reiniciar el equipo** (backend y pantallas): el backend sigue en `ARR_PERFIL` hasta reiniciarse.
- D-T9-3: un perfil inválido se aparta con fecha en vez de borrarse.
- D-T9-4: `instalar()` corre en el hilo de la GUI; es una escritura pequeña y única.

## 4. PENDIENTES

- Retirar `wizard.py` cuando se retire el arranque tkinter (`main.py`, `ui/main.py`).
- Reinicio automático del backend tras instalar (lanzador único, fase B del arranque).
- Prueba con el teclado real en el equipo.

## 5. Revisores (resultado)

**timing-auditor**: 0 críticos, 1 alto, 2 medios y 3 bajos. **safety-reviewer**: 0 críticos, 1 alto, 2 medios y 4 bajos.

Corregidos:
- **TMG-01 (alto)**: `created_at` se guardaba en UTC y `clock_guard` compara con la fecha local. Al instalar después de las 19:00 en Colombia, el siguiente arranque daba `ARR_RELOJ` (bloqueante) hasta la medianoche. Ahora el perfil se sella en hora local, tanto en el puente como en `wizard.py`.
- **SAF-01 (alto)**: el tipo de puerta decide si el software maneja el cerrojo (`has_lock`) y vigila el empaque. No hay una matriz aprobada de tipos de puerta por clase, así que no se restringe (sería inventar reglas). Mitigación:
  - el resumen muestra "Cerrojo: controlado / NO controlado" y "Sensor de empaque";
  - con un tipo sin cerrojo, la confirmación final lo dice expresamente.

  D-T9-5 CERRADA (Cristian, 2026-10-16): cualquier tipo de puerta puede ir con cualquier equipo; por eso el asistente los pide por separado. No hay matriz por clase; el aviso del resumen queda como información.
- **TMG-03 / SAF-04 (medio / bajo)**: `storage.save` escribe el perfil de forma atómica (temporal, fsync y `os.replace`).
- **TMG-02 (medio)**: al terminar, el asistente sale con el código 3 (`CODIGO_INSTALACION_TERMINADA`). El vigilante D-04 no lo relanza, no lo cuenta y registra en el log que hay que reiniciar el equipo.
- **SAF-06 (bajo)**: un perfil ilegible por otras causas (raíz que no es objeto, permisos) se trata como inválido y abre el asistente; antes la UI caía sin mensaje.

Pendientes (no son altos ni críticos):
- SAF-02: `wizard.py` (ruta tkinter, sigue en uso desde `main.py` y `ui/main.py`) no escribe `vapor_source` y borra el perfil inválido. Hay que definir el punto de entrada de producción y retirar la ruta antigua o hacer que reutilice `construir_perfil`.
- SAF-03: falta definir qué significa `door_id` en la arquitectura de un solo PC con dos pantallas (va junto con el pendiente de `source_door`).
- SAF-05: el perfil no va firmado y el secreto del código está en el código distribuido (es anterior a T9).
- SAF-07: el resumen no pide confirmar la fecha y hora del sistema.
- TMG-04: un código validado antes de la medianoche se rechaza después, con un mensaje genérico.
- TMG-05: los slots corren en el hilo de la GUI (aceptable).
- TMG-06: la puerta 2 no recarga el perfil (hay que reiniciar).
- Pregunta 8 del revisor: `revisa_empaque` vigila `pres_empaque_N` para motorized/locking, pero `factory.py` solo lo mapea para advanced.

## 6. Comprobaciones manuales de Cristian

- Renombrar `installation_profile.json` y arrancar las dos pantallas:
  - en la puerta 1 se abre el asistente;
  - en la puerta 2 aparece el menú con el fallo de perfil.
- Completar el asistente con un código del día (`tools/` del fabricante) y comprobar que se escribe `installation_profile.json` con `vapor_source` y `locked: true`.
- Con el perfil ya válido, la puerta 1 abre el menú normal y no el asistente.
