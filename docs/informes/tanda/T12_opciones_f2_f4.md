# T12 — OPCIONES, Fases 2 a 4 (Parámetros del ciclo y roles de sensor)

Instrucción: tanda 2026-10-14 §2 T12 con §1.6; `planeacion_opciones_parametros_ciclo.md` rev. 3.1 (con adenda). La Fase 5 (retiro de las vistas PySide) NO entra.

## 1. Qué se hizo

**Backend (`server.py`)**
- `GET /programas`: devuelve número, nombre, origen, si está dañado, si es editable (de usuario y no dañado) y las secciones en el orden de §5.1, con la marca "No se ejecuta" (Q-2). Esa marca aparece en precalentamiento y secado en 0, y en prevacío sin pulsos.
- `GET /programas/{n}/seccion/{s}`: devuelve por cada parámetro:
  - ruta, tipo, unidad y valor;
  - valor **por defecto**, tomado del perfil de fábrica del mismo número (`CycleManager.fabrica`, §6.1). Sin perfil de fábrica se devuelve `null`, que la UI muestra como "—" (Q-4);
  - **rango efectivo** (catálogo ∩ JSON) y las opciones de los enumerados;
  - `modificado` y la **última modificación**, tomada de `audit_log`.
  - En Descompresión solo se devuelven el modo, la espera previa y los parámetros del modo activo (Q-3).
- `CycleManager.fabrica`: perfil de fábrica inmutable por número de programa. Los programas de usuario con el mismo `cycle_id` no lo pisan.

**Interfaz (PROVISIONAL, sin diseño final)**
- `controllers/parametros_ciclo_controller.py`: programas, secciones, parámetros, edición y sensores. Las peticiones salen con el token de la ventana (`SesionVentana.enviar`).
  - La edición envía `valor_anterior_esperado` (RB-06).
  - Un error se muestra con el texto de §5.4.
  - Sin respuesta, el resultado se trata como **incierto**: se recarga el valor y solo después se informa (D-15).
- `Pantallas/OpcionesParametrosCiclo.qml`, dentro de la zona de contenido de OPCIONES:
  - **Programa** (§5.1): selector "NN · Nombre", secciones con "No se ejecuta" y fila "Sensores de temperatura".
  - **Sección** (§5.2): parámetros con su valor y unidad, asterisco si difieren del valor por defecto y leyenda al pie.
  - **Ventana de ajuste** (§5.3):
    - tarjetas Actual, Por defecto (tocable si difiere), Mínimo y Máximo;
    - última modificación;
    - nuevo valor con el teclado numérico de la ventana, acotado al rango efectivo; interruptor u opciones para booleanos y enumerados (U-17);
    - Guardar deshabilitado si no hay cambio o si la edición no está permitida.
  - **Sensores** (§5.5): una tarjeta por sensor con lectura y selector Principal / Referencia / No en uso.
    - Reglas: el Principal no se quita directamente; un nuevo Principal pasa el anterior a No en uso; como máximo 2 Referencias; un sensor sin señal solo admite No en uso.
    - Contadores; las tarjetas modificadas se marcan.
    - Guardar envía el conjunto completo con `asignacion_anterior_esperada`.
    - Sin advertencia de sonda fría (decisión 1.1).
- `Opciones.qml`: la sección "parametros_ciclo" ya no muestra "Próximamente". Los roles sin guardar alimentan `cambiosPendientes`, así que cambiar de sección o salir pide confirmación. `Main.qml` le pasa el teclado de la ventana.
- `sesion_backend`: se agregaron los códigos nuevos (`VALOR_CAMBIO`, `VALOR_INVALIDO`, `PROGRAMA_NO_EDITABLE`, `BASE_OCUPADA`, `estado_no_permitido`, de sensores, etc.) para que el cuerpo de la respuesta llegue al controlador.
- Textos nuevos en es/en (`opciones.*`), registrados en `revision_traducciones.md`.

**Q-2 a Q-8:**
- Hechos en T12: Q-2, Q-3 y Q-4.
- Ya estaban:
  - Q-6: el engranaje de la pantalla de ciclo en curso abre login → OPCIONES.
  - Q-7: el cajón no se abre deslizando.
  - Q-8: el título es la sección activa.
- **Permisos (§1.6)**: los aplica el backend (técnico fuera de CICLO, ingeniero siempre). La UI refleja `edicionPermitida` (T10).

## 2. Pruebas

- `tests/test_t12_opciones_parametros.py` (13). Cubre:
  - las rutas: programas, "No se ejecuta", valor por defecto, rango efectivo, última modificación, Q-3, asterisco, Q-4 y 404;
  - el controlador: carga, `valor_anterior_esperado`, códigos de error, resultado incierto y sensores todo o nada;
  - una vista QML offscreen: programa → sección → ajuste → sensores, sin avisos de QML.
- Ajustada: `test_opciones_qml` (Parámetros del ciclo ya no muestra "Próximamente").

## 3. DECISIONES SIN CONFIRMAR

- D-T12-1: las vistas viven dentro de la zona de contenido de OPCIONES, no como pantallas apiladas a pantalla completa. Es más simple y reversible.
- D-T12-2: las **etiquetas** de los parámetros son provisionales (la clave legible, por ejemplo "Tiempo esterilizacion"). Faltan las etiquetas, el paso y los decimales del catálogo (especificación 3). Los flotantes se muestran con 1 decimal.
- D-T12-3: la "Última modificación" muestra el **login**, no el nombre, porque `audit_log` no guarda el nombre.
- D-T12-4: los programas de fábrica se listan en solo lectura; en la práctica, los de usuario homónimos los reemplazan.

## 4. PENDIENTES

- Diseño final de las cuatro vistas (diseñador).
- Catálogo de etiquetas, pasos y decimales (especificación 3).
- Advertencia de F0 al dejar sin uso una sonda de cámara (RS-04.3): no se implementó, porque F0 solo existe en laboratorio y viene desactivado por defecto.
- Fase 5 (retiro de `params_ciclo.py` y `secado.py` PySide): fuera de alcance.
- Revisores: T12 no figura en la lista de etapas de seguridad de la regla 7; no se ejecutaron.

## 4b. Verificación sobre el teclado

`PanelTeclado.abrirNumerico` recibe el mínimo y el máximo efectivos, así que el teclado no acepta valores fuera de rango. El backend vuelve a validar igual.

## 5. Comprobaciones manuales de Cristian

- Con un técnico en PREPARADO, en OPCIONES › Parámetros del ciclo:
  1. Elegir 04 · Líquidos y verificar que "Vacío" y "Secado" dicen "No se ejecuta".
  2. Abrir Esterilización y cambiar el tiempo con el teclado: debe guardarse y quedar marcado con asterisco.
  3. Abrir Descompresión y verificar que solo se ve el modo 4.
- En Sensores de temperatura, asignar Principal = Cámara 2 y guardar. Con un ciclo en curso, la edición debe quedar bloqueada (aviso fijo).
- Revisar el tamaño de las fuentes y las áreas táctiles en la pantalla real.
