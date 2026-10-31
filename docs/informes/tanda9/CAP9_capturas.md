# CAP9 — Banco de capturas QML de la tanda 9 (D9-13.5)

Rama `tanda-9-cap9`, desde `tanda-9` en e8a22d0. Solo documentación: no se cambió código de
producto. Se agregó un script de capturas (`tests/cap9_capturas_banco.py`, no lo recoge pytest)
que reúne los mecanismos que ya existían.

## Qué se hizo

| Punto | Estado |
|---|---|
| D9-13.5: regenerar el banco de capturas con el código final de la tanda 9, en es y en | Hecho: 102 capturas (51 por idioma) en `docs/informes/tanda9/capturas/banco/` |
| Pantalla de reasignación de E/S (Opciones avanzadas) | Hecho: recorrido R8 completo (10 por idioma) y la vista del ingeniero desde C9 |
| Manejo de ciclos (C9) | Hecho: 8 por idioma |
| Parámetros del equipo con «Cámara segura» (P9) | Hecho: puertas simples y automáticas (4 por perfil e idioma) |
| Tarjeta de alarmas de Preciclo: estado seguro de arranque sin confirmación y CIC-10/SEN-06 (S9) | Hecho: 3 por idioma, con `Main.qml` completo |

## Mecanismo (reutilizado, offscreen, sin backend ni hardware)

`tests/cap9_capturas_banco.py` llama, cada uno en subprocesos con `QT_QPA_PLATFORM=offscreen`:

- `pantallas`: el banco de I4/V8b (`tests/i4_truncado_banco.py`), 22 pantallas sueltas a
  1024x1638, con `resumen.json` de textos recortados o desbordados.
- `reasignacion`: los pasos de `tests/test_r8_reasignacion_banco_qml.py` (`PASOS`) sobre
  `tests/opciones_qml_banco.py` (1200x1920, rol ingeniero).
- `manejo`: los pasos de `tests/test_c9_manejo_ciclos_banco_qml.py` (técnico fuera de ciclo,
  técnico e ingeniero en CICLO, ingeniero con el selector).
- `p9`: `tests/p9_capturas_banco.py` con el destino cambiado a la carpeta del banco.
- `preciclo` (nuevo, mismo andamiaje que `tests/test_s9_login_y_causa_qml.py`): `Main.qml` con
  `UiBridge` sobre un `UIServiceBackend` simulado; tras tocar Reposo se capturan tres estados.
  Las alarmas se arman con el catálogo real (`CATALOGO[...]`, `renderizar`, `nivel.nombre_compat`)
  igual que `server._alarma_dto`, y el motivo de CIC-10 es el texto literal de `ProtocoloFallo`.

### Cómo regenerarlas

```
PYTHONPATH=<worktree>/src python -X utf8 tests/cap9_capturas_banco.py            # todas
PYTHONPATH=<worktree>/src python -X utf8 tests/cap9_capturas_banco.py preciclo   # una parte
```

Partes: `pantallas`, `reasignacion`, `manejo`, `p9`, `preciclo`. El script imprime
`autoclave.__file__` al empezar. En esta corrida:
`C:\Users\tecni\Documents\codigo_autoclave\.claude\worktrees\agent-a5c42f144a8ff25e4\src\autoclave\__init__.py`.

Resultado de la corrida: todas las partes terminaron bien; sin avisos del motor QML en
reasignación, manejo y preciclo; `resumen.json` sin textos recortados ni desbordados en las 44
pantallas sueltas; P9 «ok» en los 4 casos; preciclo: causa «Arranque con la cámara no segura…»
(en: «Start-up with the chamber not safe…»), sin botón de confirmar, 2 alarmas en el paso 2 y el
aviso de paro liberado en el paso 3.

Las pruebas de pytest de esos módulos no se corrieron como pruebas (solo se usaron sus pasos para
capturar); no se tocó ningún módulo del producto.

## Lista de capturas (cada una existe en `es` y en `en`)

Carpeta: `docs/informes/tanda9/capturas/banco/`. `<i>` = `es` | `en`.

**Pantallas sueltas (banco I4/V8b), 22 × 2** — `CAP9_<i>_<pantalla>.png`:
IntroArranque, Login, CambioClave, NuevoUsuario, MenuPrincipal, PantallaPreciclo,
PantallaCicloEnCurso, Instalacion, Reposo, Opciones, OpcionesParametrosCiclo,
OpcionesParametrosEquipo, OpcionesUsuarios, OpcionesFechaHora, OpcionesInfoSistema,
OpcionesBitacora, OpcionesCalibracionAtm, OpcionesCalibracionSensor, OpcionesConectividad,
OpcionesRespaldo, OpcionesEntradasSalidas, OpcionesMantenimiento. Más `resumen.json`.

**Reasignación de E/S (R8), 10 × 2** — `R8_<i>_`: `1_tabla`, `2_cambios`, `3_selector`,
`4_alerta`, `5_reforzada`, `6_reinicio`, `7_conflicto`, `8_en_ciclo`, `9_verificacion`,
`10_verificar`.

**Manejo de ciclos (C9), 8 × 2** — `C9_<i>_`: `1_tecnico_lista`, `2_crear_base`, `3_creado`,
`4_borrar`, `5_tecnico_en_ciclo`, `6_ingeniero_en_ciclo`, `7_ingeniero_manejo`,
`8_ingeniero_reasignacion`.

**Parámetros y E/S (P9), 4 × 2 perfiles × 2** — `P9_<simples|automaticas>_<i>_`:
`1_ciclo_finalizacion`, `2_equipo_entrada`, `3_equipo_camara_segura`, `4_entradas_salidas`.

**Preciclo con la tarjeta de alarmas (S9), 3 × 2** — `CAP9_<i>_preciclo_`:
`1_estado_seguro_arranque` (estado seguro de arranque, sin confirmación),
`2_cic10_sen06_sin_presion` (el mismo detenido por la presión de cámara sin lectura, con CIC-10 y
SEN-06), `3_confirmacion_tras_paro` (confirmación pendiente tras un paro real liberado).

Total: 44 + 20 + 16 + 16 + 6 = **102** PNG.

## Hallazgos vistos en las capturas (sin corregir: no es el alcance de CAP9)

1. **Alarmas de Preciclo en español con la interfaz en inglés.** La lista de la tarjeta usa el
   campo `description` del DTO de `/status` (descripción registrada, en español); `UiBridge`
   (`_normalizar_alarmas`) no usa `textos[<idioma>]`, que el servidor sí manda. En
   `CAP9_en_preciclo_2_*` las filas de CIC-10 y SEN-06 salen en español mientras el resto de la
   tarjeta (incluida la fila de seguridad con el mismo motivo) sale en inglés. PREGUNTA PARA
   CRISTIAN: ¿se corrige en la tanda siguiente (tomar `textos[I18n.lang].descripcion` con
   `description` como respaldo)?
2. **Fila de CIC-10 ilegible.** El motivo largo con `fontSizeMode: Text.HorizontalFit` se achica
   hasta la fuente mínima y aun así se corta («…La cámara sigue sin considerar…»), en es y en.
   Además repite el texto de la fila de seguridad de arriba. Sugerencia: ajuste de línea en vez de
   reducción, o mostrar el título de la alarma.
3. En el doble de Preciclo los valores de sensores salen como «—»; no se investigó (el doble no
   llena todos los datos del ciclo) y no afecta a la tarjeta de alarmas.

## Lo que faltó

- Capturas con backend y datos reales (todas son de bancos sin backend, como en V8b). El banco de
  pantallas sueltas carga cada pantalla sola: algunas subpantallas de Opciones se ven casi vacías;
  sirven para revisar textos, no el aspecto final.
- El panel de la campana con las mismas alarmas de S9 y la pantalla de ciclo en curso con datos no
  se capturaron (no hay banco para ellos con datos).

## Commits

- `docs(tanda9-cap9)`: script `tests/cap9_capturas_banco.py`, 102 capturas + `resumen.json`
  y este informe.

## DECISIONES SIN CONFIRMAR

- Las capturas de R8, C9 y P9 se copiaron en la carpeta única del banco con sus nombres
  originales (no se renombraron) para que se puedan cruzar con sus informes; las carpetas
  `capturas/c9` y `capturas/p9` de sus etapas no se tocaron.

## Puntos de choque

Ninguno (sin i18n, `db_manager.py`, `control_loop.py`, `set_io.py`, catálogo de alarmas ni QML).
Sin códigos de alarma nuevos.
