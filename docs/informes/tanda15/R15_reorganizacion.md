# R15 — Reorganización del repositorio sin cambio funcional (tanda 15)

Fecha: 24-25 oct 2026, de noche, sin supervisión. Rama `tanda-15`, creada desde `dev` (d09d2a9). **No se unió a `dev`** (D10): queda con push como respaldo para que Cristian la revise y la una.

Fuente de verdad: `docs/mis_plans/decisiones_tanda_15.md`. Estado por etapa: `estado.md`.

## Resultado en una línea
Suite **7834 passed** (base 7816 + los tests nuevos), 2 rojas ajenas de `test_config_correo` como en L0 y T13; rutas y OpenAPI **idénticos** a la base; compilación **equivalente** (lista de `dist/` idéntica; PYZ solo con los renombres esperados). **Lista para unir a `dev`.**

## Ítems

| Ítem | Estado | Commit | Nota |
|---|---|---|---|
| ORG-01 | Hecho | (sin commit) | `git worktree prune`: nada que podar (los 53 worktrees existen). 14 ramas `tanda-*` unidas borradas con `-d`; 37 no se pueden borrar porque tienen worktree en `.claude/worktrees/` (`G_ramas.txt`). |
| ORG-02 | Hecho | 324e6a5 | `Documentacion/*.docx` → `docs/arquitectura/`. |
| ORG-03 | Hecho | c97ac8c | `parametros_software.accdb` y `data_base/*.xlsx` → `docs/referencia/`. |
| ORG-04 | Hecho | 5b21c9e | `Hardware/Comunocacion_esclava_ESP32_V2` → `Comunicacion_esclava_ESP32_V2` (solo la carpeta externa, D11). LEEME de la V3 actualizado. |
| ORG-05 | Hecho (parcial) | 3fed414 | `.gitignore` con `docs/informes/**/*.log`; 31 `.log` fuera del índice (siguen en disco). Diseño a `docs/diseno/`. `docs/catalogo_alarmas.2026-09-18.bak.md` **no estaba versionado**: no se borra (D9), va a la lista de abajo. |
| ORG-06 | Hecho | f580047 | `docs/README.md`. |
| ORG-07 | Hecho | 712448f | 4 `.spec` → `packaging/`, rutas relativas a `RAIZ` (`_r`/`_rel`; las tuplas literales de `datas` se conservan porque las vigilan tests). Compilación de comprobación: listas **idénticas** a la base en los 4 (`org07/`). |
| ORG-08 | Hecho | 7698d6e | `roles.py` y `validacion_usuario.py` → `src/autoclave/auth/` (ninguno importaba PySide6 ni UI). 13 importadores. `roles.json` idéntico a la base (`u/roles.json`). |
| ORG-09 | Hecho | 0586850 | `ui/service_ui/*` → `src/autoclave/cliente/` (con `__init__.py`); `src/autoclave/ui/` eliminado (solo quedaban `__pycache__`). 74 archivos actualizados. `GeneradorCodigos.spec` excluye `autoclave.cliente`. |
| ORG-10 | Hecho (parcial) | b165fbc | 4 `prueba_*.py` → `tools/demos_qml/` (se lanzan desde la raíz; insertan `src/` y siguen usando `QML_DIR`; `py_compile` OK). `historial_ejemplo.py` **se queda**: lo importa `tests/helpers/textos_caben_qml.py`. |
| ORG-11 | Hecho | 5947102, 2d1dbe2 | `tests/test_arquitectura_capas.py`: 3 failed sobre `dev` (`base/arquitectura_en_dev.txt`), 12 passed en la rama. Resuelve también imports relativos (V15-U-01). |
| ORG-12 | Hecho | 6d64cce, 8e7cbed, f11a1b9, 08d53da | `server.py` 4980 → 155 líneas; `dependencias.py` + 13 routers + `rutas/_comun.py` (máx. `io.py`, 863). Detalle abajo. |
| ORG-13 | Hecho | 6a143bc | 7 ayudantes a `tests/helpers/`, 8 bancos/capturas a `tests/banco/`, `tests/Github.ico` fuera (nadie lo usaba), marcador `req` en `pyproject.toml`, `tests/README.md`. |
| K | Hecho | — | Compilación de verificación de los 4 `.spec` desde `packaging/` + `ISCC.exe` (Setup compilado, **no ejecutado**). Detalle abajo. |
| V | Hecho | 2d1dbe2, f11a1b9 | 4 revisores: ningún hallazgo funcional; los válidos (comentarios, imports relativos, caracteres de control) corregidos. |

## ORG-12: cómo se partió `server.py`
- `server.py` conserva `app`, `lifespan`, la compuerta de arranque (middleware), los dos manejadores de excepción, `preparar_arranque`/`iniciar_arranque` y los `include_router`. Sigue siendo el punto de entrada `autoclave.backend.server:app` (`main.py` sin cambios).
- `dependencias.py`: `context`, `tokens`, `intentos_login`, `actividad_ui`, `registro_arranque`, `CALIBRATION_PATH`, locks, `_auditar`, `_log_desarrollo`, `RechazoApi`, `_rechazar*`, `requiere_rol`, `guard_estado`.
- Agrupación (ajustada a la orientativa para quedar bajo 900 líneas): `sistema`, `usuarios`, `io` (modo prueba, calibración de sensores, unidades), `ciclo`, `historial` (`/cycle/summary|list|history`), `parametros_ciclo` (`PATCH /cycle/parameter`), `programas` (`/programas`, `/cycle/display-inputs|sensors|sensor-roles`), `mantenimiento` (incluye calibración atmosférica), `reportes` (impresora, correo, reportes), `respaldo` (`/backup`), `apagado` (`/system/shutdown*` y reinicio del software), `puertas`, `alarmas`.
- Los 323 bloques de nivel superior se movieron **literales** (salvo `@app.<verbo>` → `@router.<verbo>`), comprobado por script; solo se reescribieron 2 líneas de comentario.
- Los loggers de los módulos nuevos conservan el nombre `"autoclave.backend.server"` (los registros no cambian de origen y hay pruebas que filtran por él).
- **Sin imports circulares**: `rutas/*` nunca importa `server`. **DECISIONES SIN CONFIRMAR**:
  - el estado del modo prueba (`_token_modo_prueba`, vigilancias, `_invalidar_sesion`) vive en `rutas/io.py`, porque las rutas `/io/test/*` lo reasignan con `global`; `usuarios` y `server` importan de `io` sus funciones;
  - el apagado y el reinicio del software viven en `rutas/apagado.py` (lo reasigna `/system/shutdown`); `reportes` (impresora con reinicio) importa de ahí;
  - `server_reasignacion.py` no cambia de contrato: sigue leyendo `srv.<nombre>` y `server.py` importa esos 14 nombres; el módulo lo carga `rutas/_comun.py` (lo usan `io` y `respaldo`). Consecuencia: un router no se puede importar suelto sin `server.py` (documentado en `rutas/__init__.py`).
- **Equivalencia** (`tests/test_t15_rutas_equivalentes.py`, contra `base/rutas.json` y `base/openapi.json`): mismas 107 rutas con mismos métodos, `name`, dependencias (con los roles capturados de `requiere_rol`), `status_code` y `response_model`; OpenAPI idéntico con claves ordenadas; ninguna ruta pierde dependencias. El orden **global** de las rutas cambia (también el de `paths` en `/openapi.json`), pero ninguna URL concreta coincide con dos rutas del mismo método, así que cada petición la atiende la misma ruta (el chequeo de orden hoy no tiene pares; `test_detector_de_solapes` prueba el detector).

## Tests tocados (solo rutas de import y destinos de parche)
- ORG-07: `test_b2_spec_excludes.py`, `test_l0_secretos_activacion.py`, `test_t8_k8_calibracion_neutra.py`, `test_t9_e9_entrega_neutra.py`: ruta del `.spec` leído (`packaging/`).
- ORG-08: `test_i18n.py` (también las rutas de archivo `SRC/"auth"/...`), `test_i4_ingles_backend.py`, `test_nuevo_usuario_puente.py`, `test_permisos_opciones.py`, `test_u11_revision_seguridad.py`; y `tools/claves_sin_uso_i18n.py`.
- ORG-09: 57 tests con `autoclave.ui.service_ui` → `autoclave.cliente`; `test_b1_secado_pyside.py` recorre `cliente/` en lugar de `ui/service_ui/`; `test_c1_ajustes_pyside_sesion.py` vigila el texto de import con la ruta nueva.
- ORG-12 (63 archivos de test):
  - `tests/helpers/backend_doble.py`: la recarga también purga `autoclave.backend.dependencias` y `autoclave.backend.rutas*`; `cabecera()` emite en `dependencias.tokens`; nuevos `modulo_backend`, `fijar_en_backend`, `parchear_en_backend`, `parche_en_backend` (los tres últimos ponen el valor en **todos** los módulos donde el nombre está enlazado al mismo objeto: equivalen al antiguo `srv.<nombre> = v` sobre un solo global) y `archivos_backend`/`fuente_backend`.
  - Los mismos bucles de recarga en 11 tests que los copiaban.
  - `srv.<nombre>` → `modulo_backend("<módulo>").<nombre>` para lecturas y para nombres de un solo módulo (p. ej. `_token_modo_prueba` → `rutas.io`); `fijar_en_backend`/`parchear_en_backend`/`parche_en_backend` para `tokens`, `CALIBRATION_PATH`, `_lock_archivos`, `_escribir_json_programa`, `_ai_habilitadas`, `verificar_password`, `_log_desarrollo` y `_inicio_del_dia`.
  - Las pruebas que leen el código (`test_a9_bitacora_d9_6`, `test_i4_ingles_backend`, `test_o2e_bitacora`, `test_r1_hallazgos_bajos`, `test_r8_reasignacion_api`, `test_t2_p8_estados_retirados`) leen ahora todos los archivos en que se partió `server.py` (`fuente_backend()`), para que sus aserciones negativas no pasen en vacío.
  - `test_p1_instalacion_manana::test_server_conserva_el_modulo_time` comprueba `rutas/io.py`, que es donde vive el `time.sleep` del vigilante.
  - `test_i18n.py` carga `server` antes de leer `rutas.programas._SECCIONES_PROGRAMA`.
  - `test_backend_cycle_summary.py`: `_rango_del_periodo` se lee de `rutas._comun`.
- ORG-13: 154 archivos con `tests.<x>` → `tests.helpers.<x>` / `tests.banco.<x>`, y `RAIZ = parents[2]` en los movidos.
- Ningún test se borró, saltó ni relajó (lo confirmó el revisor V de T: 32 `assert` salen y 32 entran, cambiando solo el objeto consultado).

## Suites
| Momento | Resultado (paralelo + repetición en serie) |
|---|---|
| Base (dev) | 7832 recolectados; 7809 + 7 = **7816 passed**, 2 ajenas, 11 skipped, 3 xfailed |
| Fin de R | 7824 passed + 5 en serie (las 3 de arquitectura eran el test nuevo aún sin U) |
| Fin de U | 7826 + 6 = 7832 passed |
| Fin de B | 7828 + 5 = 7833 passed |
| Fin de T | 7826 + 7 = 7833 passed (4 errores en paralelo por un archivo QML temporal compartido; pasan en serie) |
| Tras V (final) | 7849 recolectados = 7832 + 17 (12 de arquitectura, 5 de rutas); 7828 + 6 = **7834 passed**, 2 ajenas |

Las que fallan solo en paralelo son las vistas PySide/QML de siempre; en serie pasan todas menos las 2 de `test_config_correo` (dependen de `data/correo_equipo.json` del PC).

## Compilación (K)
Clones limpios de 371cc88, desde `packaging/`, con `_venv_t8_producto` (PyInstaller 6.20.0):

| .spec | `dist/` | PYZ | Diferencias |
|---|---|---|---|
| Autoclave | 2301 archivos, **idéntica** | 2086 → 2102 | +`autoclave.auth` (3), +`autoclave.backend.dependencias`, +`autoclave.backend.rutas` (15), +`autoclave.cliente` (4); −`autoclave.ui` y `ui.service_ui` (5), −`ui_pyside.services.roles`/`validacion_usuario` (2) |
| AutoclaveBackend | 1 archivo, idéntica | 1387 → 1402 | los mismos +19 y −4: **`autoclave.ui_pyside`, `ui_pyside.services`, `roles` y `validacion_usuario` dejan de entrar** (solo entraban por los roles; el backend ya no arrastra módulos de UI) |
| AutoclaveSettings | 1 archivo, idéntica | 2093 → 2093 | +auth (3), +cliente (4); −ui/service_ui (5), −roles/validación de ui_pyside (2) |
| GeneradorCodigos | 1 archivo, idéntica | 795, **idéntica** | ninguna (excluir `autoclave.cliente` no cambia nada) |

- Una primera compilación de Autoclave en el clon reutilizado de ORG-07 dio 2303 archivos: 2 `.pyc` de `config/__pycache__` que dejó la compilación anterior en ese clon (el `.spec` empaqueta la carpeta `config` entera). En un clon nuevo (`k/Autoclave_clon_nuevo.txt`) la lista es idéntica a la base. **Riesgo previo, no de esta tanda**: compilar dos veces en el mismo árbol mete esa caché en la entrega.
- `verificar_entrega_neutra.py`: OK (calibración y correo neutros, solo `cycles/factory`).
- Humo de `Autoclave.exe --portable` en una copia (igual que K13): lanzador + 2 pantallas; la 1 muestra **INSTALACIÓN DEL EQUIPO, Paso 1 de 9 · Activación** y la 2 «Instalación en curso en la pantalla 1» (`k/humo/`); logs sin `Traceback`/`ERROR`/`COM<n>`; ningún proceso vivo al final.
- Backend y Settings: no se ejecutaron (DECISIÓN SIN CONFIRMAR: el backend suelto podría abrir el serial); se comprobó que el PYZ trae los módulos nuevos. Generador: arranca, responde HTTP en el puerto 8080 con datos en una carpeta temporal y se cerró.
- `ISCC.exe /DEntrega=<clon>\dist /DAppVer=1.0.0-t15verif`: salida 0, `Autoclave_Setup_1.0.0-t15verif.exe` (87 MB) fuera del repositorio. **No se ejecutó.** Sin etiqueta, sin `usb/`, sin SHA de entrega.

## Revisión V
- **U**: sin hallazgos funcionales. V15-U-01 (imports relativos en el test de arquitectura): corregido. V15-U-02 (capas `installation`, `utils`, `config`, `cycles` fuera de la lista): no se amplió, porque la lista es la de la instrucción (anotado). U-03/U-04/U-05: comentarios y exclusiones sin efecto.
- **B**: sin cambios funcionales (lo comparó contra una copia de `dev`: mismas rutas, parámetros, dependencias, middleware y manejadores; globales reasignadas solo leídas en su propio módulo). B-01/B-02/B-03: comentarios corregidos (f11a1b9). B-04: paréntesis suelto, corregido.
- **R/K**: sin cambios funcionales ni rutas rotas. RK-04/RK-05 corregidos. RK-01: los `.log` fuera del índice siguen en disco y en el historial de `dev` (último commit que los tiene: **d09d2a9**); los informes viejos que los citan son registro (D8). RK-02: el comentario del `.ino` de la V3 con la ruta vieja **no se tocó** a propósito (no se edita fuente de firmware). RK-06: preexistentes.
- **T**: sin hallazgos que incumplan la regla. T-01 (chequeo de orden sin pares) y T-02 (marcador `req` aún sin uso, sin `--strict-markers`): informativos.

## Incidente corregido: `calibration.yaml`
Al instalar los módulos de ORG-12 corrí `test_backend_autenticacion.py` **antes** de reescribir los tests: su fixture fijaba `srv.CALIBRATION_PATH` y la ruta ya lo buscaba en `rutas/io`, así que un PATCH de calibración escribió en el `src/autoclave/config/calibration.yaml` real (y dejó `calibration.yaml.bak`). Ese cambio entró por error en el commit 6d64cce (`git add -u`). Se restauró el contenido de `dev` en **08d53da**; `git diff dev tanda-15 -- src/autoclave/config` queda vacío. Con los tests finales, los 10 archivos que calibran dejan el archivo real intacto (comprobado por hash y fecha). Las compilaciones K se hicieron con 371cc88, que aún llevaba ese YAML: en Autoclave no importa (se reemplaza por la plantilla neutra); en Backend y Settings cambia el contenido de un archivo, no la lista. **Antes de una compilación de entrega, partir de 08d53da o posterior.**

## Ramas
- Borradas (unidas a `dev`, con `-d`): tanda-6, tanda-7, tanda-7-c2, tanda-7-d2, tanda-7-l1, tanda-7-m1, tanda-7-m2, tanda-7-p1, tanda-7-q1, tanda-8, tanda-9, tanda-10, tanda-11, tanda-12.
- No borradas (tienen worktree en `.claude/worktrees/`): las 37 `tanda-8-*`, `tanda-9-*`, `tanda-10-*`, `tanda-11-*`, `tanda-12-*` de subagentes (lista en `G_ramas.txt`). Para borrarlas hay que quitar antes esos worktrees.
- Intactas: `tanda-13`, `licencia-l0`, `main` y las de D3.
- **Remotas `tanda-*` por decidir (Cristian)**: origin/tanda-2, tanda-3, tanda-4, tanda-5, tanda-6, tanda-7, tanda-8, tanda-9, tanda-10, tanda-11, tanda-12, tanda-13.

## Archivos sin seguimiento para borrar a mano (D9: no se borró ninguno)
- `docs/catalogo_alarmas.2026-09-18.bak.md`
- `installation_profile.json.invalido-20261020-145927`
- `_suites_t11/`, `capturas_calibracion/` (ignorada)
- `src/autoclave/config/calibration.yaml.bak` (**lo creó esta tanda**, ver el incidente; además un build desde este árbol lo empaquetaría)
- `src/autoclave/i18n/es.json.bak`, `src/autoclave/images/icono autoclave.jpg`
- los `__pycache__/`
- Fuera del repositorio, de esta tanda: `..\_build_t15_base_<spec>` (4), `..\_build_t15_<spec>` (4), `..\_build_t15_Autoclave_k2` (con el Setup de verificación), `..\_t15_tools`.

## Evaluación 62304 (decisiones, §Evaluación normativa)
1. **Clase C**: toca autenticación (ORG-08, ORG-12). Tratado como tal: línea base, equivalencia automática, suite completa en cada etapa y 4 revisiones independientes.
2. **Solicitud de cambio (8.2.1)**: `decisiones_tanda_15.md` + aprobación de Cristian del 24-oct.
3. **Riesgo (7.4.1–7.4.2)**: sin causas nuevas, con la evidencia de cada condición: (a) mismas rutas, métodos, dependencias y orden de coincidencia: `test_t15_rutas_equivalentes` + revisor B; (b) mismo OpenAPI: `test_openapi_identico`; (c) mismos roles: `u/roles.json` = `base/roles.json`; (d) suite en verde, mismo número salvo los 17 tests nuevos: 7834 passed; (e) compilación equivalente: tabla de K.
4. **Arquitectura (5.3)**: CLAUDE.md actualizado. **Pendiente**: `docs/arquitectura/DOC_Backend_Arquitectura_API_Servicios.docx` sigue describiendo `server.py` como un único archivo (no se editó esta noche).
5. **Verificación repetida (5.6.6, 5.7.3, 8.2.3)**: suite completa por etapa, compilación de los 4 `.spec` + Setup, humo del `.exe`.
6. **SOUP (8.1.2)**: sin cambios de dependencias. El backend deja de arrastrar módulos de UI (`ui_pyside.services.*`).
7. **Trazabilidad (7.3.3)**: rutas citadas en `docs/riesgos/` actualizadas en el mismo commit (`lista_soup.md` en ORG-07). Marcador `req` registrado para pruebas nuevas.

## DECISIONES SIN CONFIRMAR
1. Test de arquitectura: excepción acotada a `backend` para `autoclave.ui_qml.exportacion.{config_correo,correo}` (import diferido existente; moverlo queda fuera de D2).
2. Estado del modo prueba en `rutas/io.py`; apagado y reinicio en `rutas/apagado.py`; `server_reasignacion` cargado desde `rutas/_comun.py` y con su contrato `srv.<nombre>` intacto (server.py importa esos nombres).
3. Agrupación de rutas con 4 áreas más que la orientativa (`historial`, `parametros_ciclo`, `programas`, `respaldo`, `apagado`) para quedar bajo 900 líneas.
4. `historial_ejemplo.py` se queda en `ui_qml/` (lo importa una prueba); los comentarios de los `.qml` de `qml/Pruebas/` que citan `ui_qml/prueba_*.py` no se editaron (son archivos de producción).
5. Los encabezados de `auth/roles.py`, `auth/validacion_usuario.py` y `cliente/session_manager.py` conservan su comentario de ruta vieja (la instrucción pedía contenido idéntico salvo imports).
6. El comentario del `.ino` de la V3 con la ruta vieja de la V2 no se tocó.
7. `cliente/` lleva `__init__.py` (antes `ui/service_ui` era un paquete de espacio de nombres); añade `autoclave.cliente` al PYZ.
8. Humo: solo de `Autoclave.exe` (como K13) y del generador; Backend y Settings no se ejecutaron.
9. ORG-11 quedó con el prefijo `test(t15)` en lugar de `refactor(t15)`; no se reescribió el historial.
