# N11 — Instalador: Actualizar o Instalación limpia, y asociación de los táctiles (tanda 11)

Subagente N11, rama `tanda-11-n11` (desde `tanda-11`, e6886df). 23-oct-2026, sin supervisión. Fuente: D11-4 y D11-5 de `docs/mis_plans/decisiones_tanda_11.md`.

**No se ejecutó ningún `.ps1` ni el Setup.** Solo se hizo esto:
- se compiló el `.iss` con `ISCC.exe`; el `.exe` resultante se borró;
- se analizaron los `.ps1` con el parser de PowerShell (`Parser::ParseFile`, sin ejecutarlos);
- se corrieron pruebas estáticas de pytest.

`autoclave.__file__` = `C:\Users\tecni\Documents\codigo_autoclave\.claude\worktrees\agent-a51f785e3e9553e65\src\autoclave\__init__.py` (las pruebas no importan `autoclave`; leen el `.iss` y los scripts).

## Commits

| Commit | Qué |
|---|---|
| a12f268 | `autoclave.iss` (D11-4 y D11-5), `06_asociar_tactiles.ps1`, `06_revertir_asociar_tactiles.ps1`, `estacion_setup.ps1`, `tools/estacion/LEEME.md`, pruebas nuevas |
| a2dbd72 | `tools/instalador/LEEME.md` y hoja de banco (A-N11-01 a A-N11-05) |
| (este) | Informe |

## D11-4. Actualizar o Instalación limpia

**Página de opciones** (`PaginaOpciones`, después de Bienvenida):

| Instalada | Página | Opciones (la primera, marcada) |
|---|---|---|
| Más vieja | "Actualizar Autoclave" (versión instalada y la del Setup) | **Actualizar (conserva los datos)** · Instalación limpia |
| La misma | "Autoclave ya está instalado" | **Reparar (conserva los datos)** · Instalación limpia · Desinstalar |

- "Reinstalar" y su función `DesinstalarParaReinstalar` se retiraron.
- La página ya no se salta nunca: hasta pulsar "Instalar" no se hace nada. Volver con Atrás y elegir otra opción deshace la elección, porque `Modo` se recalcula en cada Siguiente desde `ModoBase`.

**Doble confirmación** (`ConfirmarLimpia`, al pulsar Siguiente con "Instalación limpia"):
- son dos `MsgBox` Sí/No, las dos con **No por defecto** (`MB_DEFBUTTON2`);
- la segunda empieza con "SEGUNDA CONFIRMACIÓN" y dice que se borran los ciclos registrados, los usuarios, el perfil de instalación y la calibración, y dónde queda el respaldo;
- un No deja al técnico en la página.

**Respaldo y borrado** (`EjecutarLimpia`, llamado desde `PrepareToInstall`, es decir, al pulsar Instalar). Si la función devuelve un texto, Inno muestra el mensaje en la página "Preparando la instalación" y no instala. Pasos:
1. **Autoclave abierto** (WMI, `Win32_Process` `Autoclave.exe`): se detiene sin tocar nada.
2. No existe la carpeta de datos: no hay nada que hacer y sigue.
3. **Respaldo:**
   - crea `%ProgramData%\Especifika\Autoclave_respaldos\` y lo protege con `icacls /inheritance:r`: solo Administradores y SYSTEM (`ProtegerRespaldos`; ver N11-3);
   - copia recursiva (`CopiarArbol`) a `AAAAMMDD-HHMMSS\`, con sufijo `_2`, `_3`… si ya existe;
   - falla ante cualquier error de copia o ante un enlace o unión dentro de los datos.
4. **Verificación:** mismo número de archivos y de bytes en el original y en la copia (`ContarArbol`).
5. **Si 3 o 4 fallan: no se borra nada** y se detiene con `LimpiaRespaldoFallo`, que avisa que la copia puede estar incompleta.
6. **Borrado** del contenido de la carpeta de datos, **salvo `estacion\`** (N11-1). Comprueba que cada entrada desapareció. Si no, se detiene con `LimpiaBorradoFallo`, que da la ruta del respaldo.
7. Sigue la instalación normal: tareas y cuenta, como una nueva. El `[Dirs]` vuelve a dar Modificar a Usuarios. Sin perfil, el primer arranque abre el menú de instalación (D11-4.3, comportamiento que ya existía).

**Más nueva instalada:** sin cambios. Se niega.

**Silencioso:** `/SILENT` y `/VERYSILENT` nunca hacen limpia, porque no hay página ni `NextButtonClick`. Con la misma versión hacen Reparar; con una más vieja, Actualizar.

### Revisión de la lógica Pascal (tabla de casos)

`Modo` lo fija `InitializeSetup`; `ModoBase` es su copia fija.

| Caso | InitializeSetup | Página | Modo al instalar | PrepareToInstall | ssPostInstall | Datos |
|---|---|---|---|---|---|---|
| Sin instalación | `ModoNuevo` (no hay clave de desinstalación) | ninguna | Nuevo | `''` | AplicarEstacion y tarea | sin cambio |
| Versión vieja, Actualizar (defecto) | `ModoActualizar` | Actualizar/Limpia | Actualizar | `''` | AplicarEstacion y tarea | conservados |
| Versión vieja, Limpia, dos Sí | `ModoActualizar` | Actualizar/Limpia | `ModoLimpia` | `EjecutarLimpia` | AplicarEstacion y tarea, más log de la ruta del respaldo | respaldados y borrados (salvo `estacion\`) |
| Versión vieja, Limpia, un No | `ModoActualizar` | se queda en la página | — | — | — | conservados |
| Misma versión, Reparar (defecto) | `ModoMantenimiento` | Reparar/Limpia/Desinstalar | `ModoReparar` | `''` | RepararEstacion (sin 01 ni 06) | conservados |
| Misma versión, Limpia | `ModoMantenimiento` | ídem | `ModoLimpia` | `EjecutarLimpia` | AplicarEstacion completa | respaldados y borrados |
| Misma versión, Desinstalar | `ModoMantenimiento` | ídem | — | — | el Setup se cierra y abre el desinstalador | conservados |
| Misma versión, silencioso | `ModoMantenimiento` | sin página | Mantenimiento | `''` | RepararEstacion | conservados |
| Versión más nueva | `Result := False` y aviso `VersionMasNueva` | — | — | — | — | sin cambio |
| Limpia con Autoclave abierto | — | — | `ModoLimpia` | `LimpiaProgramaAbierto`: no instala | — | **sin cambio** |
| **Respaldo fallido** (sin espacio, archivo ilegible, enlace, ACL) | — | — | `ModoLimpia` | `LimpiaRespaldoFallo`: no instala | — | **sin cambio**; copia parcial en `Autoclave_respaldos\…` |
| Respaldo que no coincide (archivos o bytes) | — | — | `ModoLimpia` | `LimpiaRespaldoFallo` | — | **sin cambio** |
| Borrado incompleto (archivo bloqueado) | — | — | `ModoLimpia` | `LimpiaBorradoFallo`: no instala | — | parcialmente borrados; respaldo completo verificado |
| Limpia, Atrás y Actualizar o Reparar | — | se vuelve a elegir | Actualizar o Reparar | `''` | normal | conservados |

Notas de la revisión:
- El borrado está en una sola llamada (`BorrarContenidoDatos`), que solo se alcanza con el respaldo hecho y verificado (la prueba lo comprueba por orden de texto).
- En `EjecutarLimpia` los pasos del respaldo van en `if` separados para no depender de la evaluación en cortocircuito de Pascal Script. `ShouldSkipPage` y `NextButtonClick` usan el mismo patrón `(Pagina <> nil) and (PageID = Pagina.ID)` que ya tenía el `.iss` instalado en la F.
- Un error en `PrepareToInstall` deja al técnico en "Preparando la instalación". Si vuelve a intentar (Atrás, Instalar), se hace un respaldo nuevo con otra fecha; el anterior no se toca.

## D11-5. Asociación de los táctiles

- **`tools/estacion/06_asociar_tactiles.ps1`** (nombres según la convención `NN_…` y `NN_revertir_…`):
  - pide administrador y escribe el log en `estacion.log`;
  - cuenta los monitores (`Screen.AllScreens`). Con menos de 2, lo anota y sale sin abrir nada;
  - la primera vez guarda los valores de `HKLM\SOFTWARE\Microsoft\Wisp\Pen\Digimon` (vista de 64 bits) en `respaldo_06_asociar_tactiles.json`: `DigimonAntes` y `DigimonExistia`. No se sobrescribe al volver a correrlo;
  - abre `%windir%\System32\MultiDigitizer.exe` y espera hasta `-MinutosEspera` (10 por defecto). Si la herramienta no se cierra, la cierra el script;
  - al final escribe en el log `Asociaciones tactiles en HKLM\…\Digimon: N`, con WARN si N < 2. Menos de 2 **no es falla**: sale con 0.
- **`06_revertir_asociar_tactiles.ps1`** (según el respaldo):
  - borra los valores que no estaban antes;
  - devuelve su dato a los que cambiaron;
  - deja los que ya estaban;
  - borra la clave si no existía antes y quedó vacía;
  - solo escribe en esa clave. Sin respaldo, no borra nada.
- **`estacion_setup.ps1`:** `ValidateSet` y la tabla de scripts incluyen `'06'`.
- **`autoclave.iss`:**
  - nueva subtarea `estacion\tactiles`, "Asociar cada pantalla táctil con su monitor", **marcada**. Tiene `Check: HayDosMonitores` (`GetSystemMetrics(SM_CMONITORS) >= 2`), así que solo aparece con 2 o más monitores;
  - en `AplicarEstacion`, después del 05: `MarcarPaso('06')` antes de aplicar (así el desinstalador lo revierte aunque falle), luego `EjecutarPaso('06')` y luego `ContarAsociacionesTactiles` (`RegGetValueNames` sobre Digimon, `HKLM64`). Si la subtarea está marcada, el paso se omite en un Setup silencioso;
  - al final de `ssPostInstall`, si quedan menos de 2: aviso "Repita la asociación de pantallas táctiles: quedaron N asociaciones…", con cómo repetirla. No falla;
  - **Reparar no reaplica el 06** (N11-4);
  - el desinstalador revierte `06` primero (06, 05, 04, 02, 01);
  - los dos scripts se instalan en `{app}\estacion`.
- **`tools/estacion/LEEME.md`:**
  - fila del paso 6;
  - el Setup, la reversión y la lista de comprobación (asociación y reinicio);
  - sección nueva "Pantallas táctiles: marcar los puertos USB": cambiar un cable de puerto deshace la asociación; marcar también los cables de video.

## Verificación

- **ISCC** (`C:\Users\tecni\AppData\Local\Programs\Inno Setup 6\ISCC.exe /O"C:\Users\tecni\Documents\_t11_n11_iss" /DEntrega=C:\Users\tecni\Documents\codigo_autoclave\entrega\2026-10-23_f /DAppVer=1.0.0-n11 /DAppVerNum=1.0.0.7 tools\instalador\autoclave.iss`):
  - **salida 0, `Successful compile`, sin advertencias ni sugerencias**;
  - la primera compilación avisó de que `FileCopy` está renombrada: se cambió a `CopyFile`;
  - el `.exe` (85 MB) se **borró** y no es entregable. La versión `1.0.0-n11` / `1.0.0.7` era solo para compilar; K11 pasa la suya.
- **Parser de PowerShell:** 0 errores en los 15 `.ps1` de `tools/estacion` y `tools/instalador`, incluidos los dos nuevos. PSScriptAnalyzer no está instalado y no se instaló (regla 3).
- **Pruebas:** `tests/test_t11_n11_instalador_limpia_tactiles.py`, 16 pruebas nuevas, todas estáticas (prohibido ejecutar `.ps1`). Cubren:
  - las dos páginas y sus opciones; Reinstalar ya no existe;
  - la doble confirmación con No por defecto y el texto de la segunda en es y en;
  - el orden "programa abierto → proteger → respaldar → verificar → borrar" y que hay una sola llamada que borra;
  - la carpeta de respaldo con fecha y protegida; se conserva `estacion\`; se rechazan los enlaces;
  - la versión más nueva se sigue negando; el modo silencioso nunca hace limpia;
  - la subtarea marcada y solo con 2 monitores;
  - el 06 se marca antes de aplicarse, se omite en silencioso, cuenta en Digimon y avisa;
  - Reparar sin 06; reversión con el 06 primero;
  - los scripts instalados y en el puente;
  - el contenido del script 06 y de su inverso: solo la clave Digimon, respaldo antes de abrir la herramienta, espera acotada;
  - el LEEME con los puertos USB;
  - los mensajes en los dos idiomas;
  - el parser de PowerShell sobre los 3 scripts tocados: solo analiza, se salta si no hay `powershell.exe`.
- **Prueba existente** `tests/test_t9_e9_setup_estacion.py`, sin cambios.

Resultado exacto:

```
tests/test_t11_n11_instalador_limpia_tactiles.py tests/test_t9_e9_setup_estacion.py
27 passed in 1.00s
```

(Ninguna otra prueba lee `tools/instalador` ni `tools/estacion`: `grep -rl` en `tests/`.)

## Hoja de banco

Bloque nuevo "Bloque N11" antes de "Registros…" y 5 filas en el resumen, después de D-X9-02:
- A-N11-01: Actualizar conserva los datos;
- A-N11-02: limpia con doble confirmación, respaldo completo y protegido, y menú de instalación al abrir;
- A-N11-03: limpia rechazada (No, Atrás, Autoclave abierto). El respaldo fallido no se provoca en banco: se remite a este informe;
- A-N11-04: asociación de los 2 táctiles, log y puertos USB anotados;
- A-N11-05: reinicio del PC con la asociación conservada, Reparar sin la herramienta, cable cambiado de puerto y reversión al desinstalar.

También se actualizó `tools/instalador/LEEME.md`: tabla de opciones, la limpia paso a paso, cómo restaurar un respaldo, la sección de los táctiles y la lista de verificación (Reinstalar → casos A-N11).

## DECISIONES SIN CONFIRMAR

- **N11-1:** la instalación limpia **no borra `estacion\`**. Esa carpeta guarda los valores de Windows anteriores a la estación (`respaldo_01..06`, BCD, plan de energía), que el desinstalador necesita para revertirla. Si se borrara, el siguiente "Aplicar" tomaría como original lo ya cambiado y la desinstalación nunca devolvería Windows a su estado previo. Va completa en el respaldo. Todo lo demás de `%ProgramData%\Especifika\Autoclave` se borra.
- **N11-2:** la limpia **no ejecuta el desinstalador**, a diferencia del antiguo Reinstalar. Borra los datos y sigue con el asistente completo. Los pasos de la estación se vuelven a aplicar sobre los respaldos conservados (son idempotentes). Así sirve igual con una versión vieja que con la misma, y no depende de que el desinstalador anterior termine.
- **N11-3:** `Autoclave_respaldos\` queda **solo para Administradores y SYSTEM**. ProgramData da lectura a Usuarios por herencia, y el respaldo contiene `estacion\` (con la contraseña anterior del inicio automático, si la había) y la base con los usuarios. Si `icacls` falla, el respaldo cuenta como fallido y no se borra nada. Restaurar requiere administrador.
- **N11-4:** **Reparar no reaplica el paso 06**, como pasa con el 01: abre una herramienta interactiva y un Setup silencioso quedaría esperando. La asociación hecha se conserva. Para repetirla, Panel de control o el script.
- **N11-5:** el paso 06 se **omite en un Setup silencioso**, aunque la subtarea esté marcada (se anota en el log de Inno).
- **N11-6:** "2 o más monitores" se evalúa **al ejecutar el Setup** (`SM_CMONITORS`). Si en ese momento hay un solo monitor conectado, la subtarea no aparece y el paso no se anota.
- **N11-7:** el conteo de asociaciones es el **número de valores de la clave Digimon**. Entradas viejas de un táctil desconectado también cuentan, así que un 2 no garantiza que los dos táctiles actuales estén bien. Por eso la hoja de banco pide tocar cada pantalla.
- **N11-8:** el aviso de menos de 2 asociaciones es un `MsgBox` informativo al final de la instalación, antes de la página Finalizar, y no un texto añadido a esa página (podría quedar cortado).
- **N11-9:** la espera máxima de la herramienta es de **10 min**. Pasado ese tiempo, el script la cierra y sigue.
- **N11-10:** el respaldo se verifica por **número de archivos y bytes**, no por hash. Los respaldos no se borran solos.

## PREGUNTAS PARA CRISTIAN

- **N11-P1:** ¿conservar `estacion\` en la limpia (N11-1) está bien, o la limpia debe además revertir la estación (desinstalar primero, como el antiguo Reinstalar)?
- **N11-P2:** ¿cuántos respaldos de limpia se guardan? Hoy se acumulan sin límite en `Autoclave_respaldos\`, y cada uno ocupa lo que la carpeta de datos (la base crece con los ciclos).
- **N11-P3:** el programa de ajustes PySide guarda "recordar usuario" en `HKCU\Software\Especifika\Autoclave` (`QSettings`), fuera de ProgramData. La limpia no lo borra. ¿Debe borrarlo? Es la cuenta de quien instala, no la del operador.
- **N11-P4:** ¿la herramienta de Windows (`MultiDigitizer.exe`) existe y funciona en la estación con Windows 11 Pro y estos paneles? No se pudo comprobar sin ejecutarla (A-N11-04).

## Pendientes

- Probar A-N11-01 a A-N11-05 en el PC de prueba (Cristian) antes de usar la limpia o el paso 06 en el equipo del autoclave.
- No se lanzó ningún revisor (etapa no ★). La limpia borra datos de pacientes y ciclos. Si la sesión principal lo considera, conviene un `safety-reviewer` del diff de `tools/instalador/autoclave.iss` (funciones `EjecutarLimpia`, `CopiarArbol`, `BorrarContenidoDatos`).
- K11: compilar con `/DAppVer` y `/DAppVerNum` de la G, como en K10. Los valores por defecto del `.iss` siguen en la D.

## Puntos de choque tocados

- `tools/instalador/autoclave.iss`
- `docs/mis_plans/hoja_pruebas_banco_equipo_pruebas.md`: 5 filas después de D-X9-02 y el bloque N11 antes de "Registros que se deben conservar"
- `tools/instalador/LEEME.md`, `tools/instalador/estacion_setup.ps1` y `tools/estacion/LEEME.md`

No se tocaron i18n (los textos del Setup van en `[CustomMessages]` es/en del `.iss`, como hasta ahora), QML, `app.py`, `server.py`, `doble_pantalla.py`, `test_v8b_textos.py` ni `LEEME_INSTALACION.md`.
