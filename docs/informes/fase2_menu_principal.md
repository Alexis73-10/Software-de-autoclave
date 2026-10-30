# Informe de Fase 2 — Menú Principal (UI QML): backend y datos

Plan: `docs/mis_plans/planeacion_menu_principal_ui_qml.md` (v1.3)
Fecha: 2026-10-02
Rama: `dev`, último commit al empezar: `960647f`. Sin commit (D-10).

---

## 0. Archivos con cambios previos sin commit (antes de empezar)

`git status` al iniciar la Fase 2. Ninguno de estos cambios es de este trabajo, salvo los marcados.

Modificados:

- `.claude/settings.local.json`
- `src/autoclave/services/domain/logging/db_manager.py` — cambios de otro trabajo (auditoría de creación de usuarios: columnas `creado_por`, `creado_en`, `codigo_creacion` y `existe_usuario`)
- `src/autoclave/ui_pyside/main_window.py`
- `src/autoclave/ui_pyside/views/admin_menu.py`
- `src/autoclave/ui_qml/assets/textos/es.json`
- `src/autoclave/ui_qml/bridge/ui_bridge.py`
- `src/autoclave/ui_qml/controllers/__init__.py`
- `src/autoclave/ui_qml/qml/Componentes/BarraSuperior.qml`
- `src/autoclave/ui_qml/qml/Pantallas/Login.qml`
- `src/autoclave/ui_qml/qml/Pantallas/PantallaCicloEnCurso.qml`
- `src/autoclave/ui_qml/qml/Pantallas/PantallaPreciclo.qml`
- `src/autoclave/ui_qml/qml/Pruebas/PruebaCicloEnCurso.qml`
- `src/autoclave/ui_qml/qml/Tema/Colores.qml` — **de este trabajo** (tokens de la Fase 1)
- `tests/test_ui_bridge.py`
- `tests/test_usuarios_db.py`

Sin versionar de otros trabajos: `INFORME_OPCIONES_POST_LOGIN.md`, `docs/mis_plans/nuevo_usuario.png`, `docs/mis_plans/planeacion_*.md` (salvo el de este trabajo), `docs/mockups/`, `src/autoclave/images/nuevo_usuario*.png`, `src/autoclave/images/pantalla_ciclo_con_grafica_editada.png`, `src/autoclave/ui_pyside/services/roles.py`, `src/autoclave/ui_pyside/services/validacion_usuario.py`, `src/autoclave/ui_pyside/views/nuevo_usuario/`, `src/autoclave/ui_qml/controllers/login_controller.py`, `src/autoclave/ui_qml/qml/NuevoUsuarioHost.qml`, `src/autoclave/ui_qml/qml/Pantallas/NuevoUsuario.qml` y sus pruebas (`tests/test_admin_menu_nuevo_usuario.py`, `tests/test_flujo_nuevo_usuario.py`, `tests/test_login_controller.py`, `tests/test_login_qml_autenticacion.py`, `tests/test_nuevo_usuario_puente.py`, `tests/test_nuevo_usuario_qml.py`).

Sin versionar de este trabajo (Fase 1): `docs/informes/`, `ciclos_totales.svg` (mono y color), `prueba_menu_principal.py`, `BarraInferiorMenu.qml`, `DetalleUltimoCiclo.qml`, `EncabezadoMenu.qml`, `IconoColor.qml`, `TarjetaMenu.qml`, `TarjetaResumen.qml`, `GaleriaMenuPrincipal.qml`, `tests/test_menu_principal_componentes_qml.py`.

Archivos compartidos que toca esta fase (D-22): `db_manager.py` (con cambios ajenos) y `server.py` (sin cambios ajenos al empezar). `es.json` no se toca en esta fase.

---

## 1. Paso 1 — Verificación de MP-14 (solo lectura)

### 1.1 (a) Curva del ciclo en el historial — EXISTE, sin endpoint histórico

Hay dos series guardadas por ciclo, ambas en `data/autoclave.db` y ninguna se borra al terminar el ciclo (no hay `DELETE` sobre esas tablas en el código):

| Tabla | Contenido | Frecuencia | Lectura existente |
|---|---|---|---|
| `lecturas_grafica` | `t_s` (segundos monotónicos desde el inicio, C-01), `fase`, `temp_camara`, `temp_ref`, `pres_camara` | ~1 s, solo en fases de ciclo (`cycle_logger.py`, `_PERIODO_GRAFICA_S = 1.0`) | `DbManager.get_lecturas_grafica(ciclo_id, desde_id)`. HTTP: solo `GET /cycle/current/graph`, que devuelve la serie **únicamente mientras la máquina está en CICLO** (`_ciclo_de_pantalla()`); de un ciclo ya terminado no hay endpoint. |
| `lecturas` | `timestamp_rel` (texto `HH:MM:SS`), `timestamp_abs`, `fase_codigo` (W/H/S/E), `temp_camara`, `pres_camara`, `para_imprimir` | intervalo por fase configurable (por defecto 60 s) | `GET /cycle/history/{ciclo_id}/readings` (todas las lecturas del ticket). Es la serie del ticket impreso, no la de la gráfica. |

Cómo se podría leer para la ventana de Último ciclo: un endpoint de solo lectura que devuelva `lecturas_grafica` de un `ciclo_id` histórico (el mismo formato de `GET /cycle/current/graph`, que ya consume `GraficaCiclo.qml`). También existe `ciclo_fases` (inicio, fin y duración de cada fase). Nota: `timestamp_rel` de `lecturas` se calcula con `time.time()` (reloj de pared), no monotónico; `lecturas_grafica` sí es monotónica.

No se implementa hasta tu aprobación (instrucción del Paso 2).

### 1.2 (b) Quién inició el ciclo — NO SE GUARDA

- La tabla `ciclos` tiene la columna `operador`, pero `CycleLogger` llama a `db.crear_ciclo(...)` sin pasarla (`cycle_logger.py:219`), así que queda siempre `''`.
- `POST /cycle/start` no recibe usuario ni operador; solo activa la bandera `START_CICLO`.
- No existe registro de operadores (B-02 de `planeacion_menu_principal.md`), y la sesión de usuario vive en el subproceso PySide (o en el login QML en desarrollo de otro trabajo), sin canal hacia el backend.
- Conclusión: hoy no hay forma de saber quién envió un ciclo. La ventana de Último ciclo mostraría "—" en ese campo.

### 1.3 (c) Mantenimiento — NO EXISTE NINGÚN DATO

- No hay tabla, parámetro global, archivo de perfil ni endpoint con fecha del último mantenimiento, intervalo en días o intervalo en ciclos.
- Las únicas apariciones de "mantenimiento" son un rótulo de menú en `ui_pyside/views/admin_menu.py`, la fila "No disponible" de `ui_qml/bridge/info_equipo.py` y comentarios de `protocolo_fallo.py` sin relación.
- Conclusión: no se pueden calcular ciclos restantes ni mostrar la fecha del último mantenimiento. La tarjeta y su ventana muestran "—" (B-03 de `planeacion_menu_principal.md`).

---

## 2. Paso 2 — Endpoint, puente y formateadores

### 2.1 Archivos

| Archivo | Tipo | Contenido |
|---|---|---|
| `src/autoclave/services/domain/logging/db_manager.py` | modificado (compartido, D-22) | Método `get_resumen_ciclos(desde)`: último `numero_ciclo`, ciclos terminados desde `desde` y fila del último ciclo. Un solo bloque nuevo (hunk `@@ -222 +234`), separado de los cambios del otro trabajo. |
| `src/autoclave/backend/server.py` | modificado (compartido, D-22) | `from datetime import datetime`, `_inicio_del_dia()`, `GET /cycle/summary` y `GET /cycle/history/{ciclo_id}/graph`. Dos bloques, ambos de este trabajo. |
| `src/autoclave/ui_qml/domain/resumen_sistema.py` | nuevo | Formateadores puros: `formatear_entero`, `formatear_fecha`, `formatear_hora`, `formatear_numero_programa`, `clave_resultado`, `resumen_presentable`. `SIN_DATO = "—"`. |
| `src/autoclave/ui_qml/bridge/resumen_sistema.py` | nuevo | Puente `ResumenSistema` (QObject) para QML. |
| `tests/test_backend_cycle_summary.py` | nuevo | 13 pruebas |
| `tests/test_resumen_sistema_dominio.py` | nuevo | 41 pruebas |
| `tests/test_resumen_sistema_puente.py` | nuevo | 14 pruebas |

`es.json` no se tocó en esta fase.

### 2.2 `GET /cycle/summary` (solo lectura)

Respuesta:

```json
{
  "ciclos_totales": 128,
  "ciclos_hoy": 3,
  "ultimo_ciclo": {
    "id": 128,
    "numero_ciclo": 128,
    "fecha_inicio": "2026-10-02T14:25:10.123456",
    "fecha_fin": "2026-10-02T15:02:00",
    "programa_id": "instrumental_134",
    "programa_nombre": "Instrumental 134",
    "programa_numero": 2,
    "resultado": "COMPLETADO",
    "operador": null
  }
}
```

Reglas:

- `ciclos_totales`: último `numero_ciclo` (`MAX`), no un conteo de filas. Sobrevive a filas faltantes, pero no a vaciar la tabla. Marcado `TODO(MP-06a)` en `server.py`. Sin ciclos: `0`.
- `ciclos_hoy`: ciclos con `fecha_fin` no nula y `fecha_fin >= medianoche local` (`_inicio_del_dia()`, mismo formato ISO sin zona que guarda la tabla). Cuenta todos los terminados (COMPLETADO, FALLO, CANCELADO), coherente con el rótulo "Realizados" (D-15). Un ciclo que empezó ayer y terminó hoy cuenta hoy. Un ciclo interrumpido (sin `fecha_fin`) no cuenta.
- `ultimo_ciclo`: la fila de mayor `id`, aunque no esté cerrada (entonces `fecha_fin` y `resultado` son `null`). Sin ciclos: `null`.
- `programa_numero`: **la tabla `ciclos` no guarda el número de programa**, solo `tipo_ciclo` (el id) y `nombre_ciclo`. El endpoint toma el número del programa que hoy tiene ese id en `cycle_manager`; si el programa ya no existe o no tiene `cycle_number`, devuelve `null`. Riesgo: si a un programa se le cambia el número, el historial mostraría el número nuevo. Guardar el número en `ciclos` sería un cambio de esquema y de `CycleLogger`, fuera de lo autorizado.
- `id`: id en BD del último ciclo, para pedir su curva (§2.5).
- `operador`: valor de `ciclos.operador`, o `null` si está vacío. Hoy siempre es `null` porque `CycleLogger` no lo guarda (§1.2); queda listo para cuando exista el registro de operadores (B-02).

### 2.3 Puente `ResumenSistema`

Sigue el patrón de `InfoEquipo`: la consulta HTTP corre en un hilo aparte (`ejecutar`, inyectable en pruebas), el resultado vuelve al hilo de la GUI por señal y no se lanza una segunda consulta mientras hay una en curso.

- `iniciar()`: consulta en el momento y arma el sondeo cada 10 s (`intervaloMs`, provisional, §6.5). `detener()` lo para. Pensado para que la pantalla los llame al activarse y desactivarse (Fase 3).
- Propiedades (texto): `ciclosTotales`, `ciclosHoy`, `ultimoFecha` (`DD/MM/AAAA`), `ultimoHora` (`HH:MM`), `ultimoPrograma` (número con dos dígitos, `02`), `ultimoProgramaNombre`, `ultimoResultado` (clave `COMPLETADO` / `FALLO` / `CANCELADO`, o `""`; la pantalla la traduce con `es.json` y muestra "—" si es `""`).
- `sinConexion` (bool): `true` cuando la última consulta falló o la respuesta vino mal formada.
- `proximoMantenimiento`: siempre "—" (no hay fuente, §1.3).
- `tiempoSecado`: siempre "—" con `TODO(MP-11)`.
- `ultimoOperador`: quién envió el último ciclo; "—" mientras no se guarde.
- Curva del último ciclo (§2.5): `cargarGraficaUltimo()`, `graficaUltimoDisponible`, `datosGraficaUltimo` (arreglos `t_min`, `temp_camara`, `temp_ref`, `pres_camara`, el formato de `GraficaCiclo.qml`) y `fasesGraficaUltimo` (inicio de cada fase, para los divisores).

Interpretación de §6.3 y §6.5 (dicen cosas distintas sobre el backend sin respuesta): §6.5 pide conservar los últimos valores y marcar el error; §6.3 y D-16 piden mostrar el aviso y "—". Se aplican las dos: la última respuesta buena se conserva internamente, pero mientras `sinConexion` es `true` las propiedades muestran "—"; al volver la conexión se publican los datos nuevos. Antes de la primera respuesta no se marca sin conexión, para no mostrar el aviso al abrir la pantalla.

### 2.4 Decisiones de presentación

- "Último ciclo" muestra la fecha y hora de **inicio** del ciclo (`fecha_inicio`). Confirmado por Cristian el 2026-10-02.
- "—" (raya) como sin dato en el menú, como pide el plan. La pantalla de preciclo usa "---" (`pantalla_ciclo.SIN_DATO`); no se unificaron.
- Programa en "Último ciclo": solo el número (§6.3, "número de programa"). El nombre queda disponible en `ultimoProgramaNombre` para la ventana flotante.

### 2.5 Ampliación aprobada: curva y operador del último ciclo

Aprobada por Cristian el 2026-10-02, con base en §1. También aprobó tomar el número de programa del programa actual (§2.2) y la interpretación de "sin conexión" (§2.3).

- La curva **no** va dentro de `GET /cycle/summary`: ese endpoint se consulta cada 10 s y la curva de un ciclo tiene miles de puntos (~1 por segundo). Va en un endpoint propio, `GET /cycle/history/{ciclo_id}/graph`, que el puente llama solo al abrir la ventana flotante de Último ciclo. El resumen agrega el `id` del ciclo para poder pedirla.
- `GET /cycle/history/{ciclo_id}/graph`: lee `lecturas_grafica` de un ciclo del historial con el mismo formato que `GET /cycle/current/graph` (`id`, `t_s`, `fase`, `fase_ui`, `temp_camara`, `temp_ref`, `pres_camara`). Ciclo inexistente: 404. Sin lecturas: lista vacía. Solo lectura.
- El puente reutiliza `AcumuladorGrafica` (`ui_qml/domain/ciclo_en_curso.py`, del trabajo de ciclo en curso, sin modificarlo) para dejar la serie en el formato que ya consume `GraficaCiclo.qml`.
- Operador: el campo se publica (§2.2), pero hoy siempre muestra "—".
- Mantenimiento: sin cambios; sigue sin fuente (§1.3).

---

## 3. Pruebas

Cada grupo se escribió primero y se vio fallar (falta de código) antes de implementar.

- `tests/test_backend_cycle_summary.py` (13): sin ciclos; "hoy" con ciclos de ayer, que cruzan medianoche, FALLO, CANCELADO e interrumpido; total como último número con filas faltantes; último por mayor id; endpoint completo (con `id` y `operador`); operador guardado; resultado nulo y programa inexistente; programa sin número; formato de `_inicio_del_dia()`; curva histórica (solo la del ciclo pedido, con `fase_ui`), sin lecturas y ciclo inexistente (404).
- `tests/test_resumen_sistema_dominio.py` (41): enteros (incluido valor largo 1234567 sin separador, negativos, booleanos y texto); fecha y hora; número de programa; solo estados terminales; sin respuesta; sin ciclos; un ciclo CANCELADO; respuesta mal formada sin tumbar el resto; operador (guardado, vacío o inválido); id del último ciclo.
- `tests/test_resumen_sistema_puente.py` (14): estado inicial; consulta y publicación; sin cambios no emite; backend sin respuesta (aviso y "—"); recuperación; respuesta mal formada; sin consultas superpuestas; sondeo de 10 s; mantenimiento y secado sin fuente; curva sin cargar, cargada, sin respuesta y sin último ciclo (no consulta); operador.

Suite completa (`python -m pytest`, 2026-10-02, tras la ampliación): **1539 passed**, 0 fallos (6 avisos de deprecación preexistentes en `test_storage.py`).

Nota: en la primera corrida de la ampliación falló `test_grafica_historica` por un error del dato de prueba (usé la fase `PREVACIO`; en el backend se llama `PRE_VACIO`). Se corrigió la prueba, no el código.

---

## 4. Commit (D-22), cuando lo confirmes

- `server.py`: los dos bloques son de este trabajo.
- `db_manager.py`: incluir solo el bloque de `get_resumen_ciclos` (`@@ -222 +234`); los otros cuatro bloques (tabla `usuarios`, migración, `crear_usuario`, `existe_usuario`) son del otro trabajo y quedan sin commit.
- `Colores.qml` y los archivos nuevos de las Fases 1 y 2 son de este trabajo.

---

## 5. Pendientes

De Cristian:

- MP-11, MP-12, MP-14 (contenido de las ventanas de Ciclos totales y Ciclos hoy).
- Mockup v3: `docs/mockups/` ya existe en el árbol (sin versionar); se revisará al iniciar la Fase 3.

`TODO` de este trabajo en el código: `TODO(MP-06a)` en `server.py` (y en el docstring de `get_resumen_ciclos`), `TODO(MP-11)` en `bridge/resumen_sistema.py`.
