# ALD — detalle de todas las alarmas, alertas y fallos (tanda 26)

Síntoma: «Temperatura demasiado alta» no abría ninguna tarjeta. Causa: es el motivo `temp_alta` de `core/runtime/camara_segura.py`, que se muestra en la fila `filaNoAbrir` de `Componentes/SeccionEstadoSeguro.qml`. Esa fila era un `FilaAlarma` sintético sin `tocable`, igual que las otras 7 filas de la sección y `alarmaArranque` de `Main.qml`.

## 1. Inventario (antes del cambio)

| Superficie | Qué muestra | ¿Abría el detalle? |
|---|---|---|
| `Main.qml` `alarmaArranque` (FilaAlarma ARRANQUE) | Fallo bloqueante de arranque sobre la intro | No → **sí** |
| `Main.qml` `avisoSinConexionSesion` | Cuenta regresiva de cierre de sesión sin conexión | No (aviso de sesión, no es alarma; sin cambio) |
| `SeccionEstadoSeguro` (8 FilaAlarma: sin conexión, módulo E/S desconectado, módulo E/S sin datos, paro, estado seguro pendiente, en curso, NO ABRIR, modo prueba). Se ve en Preciclo, Ciclo en curso y el panel de la campana de todas las pantallas | Filas de seguridad | No → **sí** (las 8) |
| `SeccionEstadoSeguro` notas, botón «Confirmar y llevar a estado seguro», botón asignar sonda | Texto de apoyo y acciones | Sin cambio (ALM-01, ESS-04) |
| `PanelNotificaciones` delegado de alarmas (FilaAlarma `tocable: true`) | Alarmas activas por grupo | Sí |
| `PantallaPreciclo` `listaAlarmasPreciclo` | Alarmas activas | Sí |
| `Reportes` › `ListaAlarmasPeriodo` | Alarmas del periodo | Sí (`abrir(fila.detalle)`) |
| `PanelFinCiclo` (FilaAcordeon de `alarmas_ciclo`) | Alarmas del ciclo terminado | No: se despliega en línea con la causa (excepción justificada, FC-13) |
| `PantallaCicloEnCurso` píldora «Alarmas/Observaciones (N)» | Contador | Lleva al panel de fin de ciclo (sin cambio) |
| `OpcionesEntradasSalidas` `avisoCorte_i` (`/status.avisos_corte_prueba`) | Cortes del modo prueba | No (excepción: archivo de otro frente, T26-ESP; ver ALD-04) |
| Insignias de campana, Reposo `avisoInstalacion` | Contador / aviso de instalación | No son alarmas |
| Historial (ListaCiclos/DetalleCiclo) | Sin filas de alarma en QML | — |
| Bandeja SIS-06 | No existe en el QML: SIS-06 llega como alarma del catálogo y se ve en las listas de arriba | — |

Catálogo: todas las alarmas de `CATALOGO` tienen `titulo` y `accion` en `alarmas.<código>` de es y en (comprobado; ahora lo fija la prueba (b)).

## 2. Hallazgos

- **ALD-01 (ALTA):** las 8 filas de `SeccionEstadoSeguro` (incluida NO ABRIR) no abrían detalle; el operador no podía ver el valor medido ni el límite ni qué hacer. Corregido.
- **ALD-02 (MEDIA):** `/status` no publicaba el límite con que se juzga la cámara (`temp_max_apertura` vigente, atm ± rango). Corregido como dato de solo lectura (`camara_segura_limites`), sin tocar la lógica.
- **ALD-03 (MEDIA):** `alarmaArranque` de `Main.qml` no abría detalle. Corregido.
- **ALD-04 (BAJA):** los avisos de corte del modo prueba en Entradas/Salidas no abren detalle; el archivo está fuera de este alcance (lo usa T26-ESP). Queda como excepción en la prueba (a).
- **ALD-05 (BAJA):** la hora de aparición de las filas sintéticas no existe en el backend; se toma en la UI (primer `/status` en que el puente ve la condición). Es informativa y se pierde al reiniciar la UI.

## 3. Qué cambió

- `src/autoclave/ui_qml/domain/detalle_aviso.py` (nuevo, puro): `armar(clave, contexto)` arma la fila con la forma de `AlarmListModel.detalle` (id, level, priority, código y `codigoVisible` con `catalogo.codigo_visible()`, `titulos`/`descripciones`/`acciones` es/en, `aparecida`, `estado`, `sintetica: True`). NO ABRIR: cada motivo de `camara_segura` con su texto (temp_alta: temperatura medida y límite; sobrepresión/vacío: presión medida y rango atm ± rango; sin lectura, sin datos vigentes, falta de configuración; sin código, el texto del backend), en las unidades vigentes. Sin dato de límite muestra «—», nunca un número inventado. Además `claves_activas`/`actualizar_apariciones` para la hora.
- `src/autoclave/ui_qml/bridge/detalle_aviso_qml.py` (nuevo): singleton `Autoclave.DetalleAviso` (`armar`), registrado en `bridge/__init__.py`.
- `ui_bridge.py`: `_seguridad` conserva código, valores y límites del motivo; propiedad `contextoAviso` (motivo, causa del estado seguro, horas de aparición).
- `backend/rutas/sistema.py`: `/status.camara_segura_limites` = `temp_max_apertura` (vigente: el menor entre equipo y último ciclo, igual que `evaluar`), `temp_max_apertura_equipo`, `temp_max_apertura_ciclo`, `presion_atmosferica`, `rango_presion_atm`. Solo lectura.
- `SeccionEstadoSeguro.qml`: las 8 filas `tocable` → `abrirDetalle(clave)` → `VentanaDetalleAlarma.abrirDesde(DetalleAviso.armar(...))`. La ventana se carga con un `Loader` al primer toque (las secciones ocultas no crean ventanas) y se relee con `seguridadChanged`; si la condición desaparece queda «Ya no está activa». Sin botones nuevos.
- `VentanaDetalleAlarma.qml`: una fila `sintetica` se abre tal cual y no se relee del modelo de alarmas.
- `Main.qml`: `alarmaArranque` tocable con su `VentanaDetalleAlarma`.
- i18n es/en: sección `aviso_detalle` (título y acción por fila; `no_abrir_motivos.*`). `tests/test_i18n.py`: familia dinámica `aviso_detalle.` enumerada (`detalle_aviso.sufijos_i18n()`).
- Pruebas: `tests/test_t26_ald_detalle_alarmas.py` (a)(b)(c), con un arnés QML que toca NO ABRIR y lee «Temperatura de la cámara: 87.4 °C», el límite y la hora.

Respeta D8-5.4 (sin `elide` nuevos), colores solo de `Tema/`, la regla del teclado de la tanda 22 (no hay teclados) y ALM-01 (el detalle no cambia estado).

## 4. Decisiones sin confirmar

- `DECISIÓN SIN CONFIRMAR` Nivel y color de las filas sintéticas: NO ABRIR = «Alarma» (media), estado seguro en curso = «Emergencia» con color medio, modo prueba = «Aviso»; el resto «Emergencia».
- `DECISIÓN SIN CONFIRMAR` Textos de «qué hacer» de cada fila sintética y de cada motivo de NO ABRIR (es/en), redactados aquí.
- `DECISIÓN SIN CONFIRMAR` Hora de aparición tomada en la UI (ALD-05).

## 5. Pruebas corridas

`tests/test_t26_ald_detalle_alarmas.py` (12), `test_v8b_textos`, `test_tema_oscuro`, `test_t22_regla_teclado_accion`, `test_t17_s4_alarmas_qml`, `test_i18n`, `test_i4_ingles_qml`, `test_ess_estado_seguro_silencioso`, `test_t7_avisos_qml`, `test_t21_textos_caben_qml`, `test_arquitectura_capas`, `test_status_endpoint_alarms`, `test_alarmas_catalogo`: en verde. `test_t15_rutas_equivalentes` falla por la ruta `/arranque/iniciar` de ARQ (no por ALD; `/status` no está fijado campo a campo).

Pendiente de banco (T26): tocar NO ABRIR en el equipo con la cámara caliente y ver valor y límite.
