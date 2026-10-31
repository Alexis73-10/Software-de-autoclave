# E9 — Entrega y Setup (tanda 9)

Subagente E9, rama `tanda-9-e9` (desde `tanda-9`, 090a8bf, que contiene `dev` 1ff5afa). 23-oct-2026, sin supervisión. Etapa no ★.

Todas las pruebas se corrieron con `PYTHONPATH=<worktree>/src`. `autoclave.__file__` = `C:\Users\tecni\Documents\codigo_autoclave\.claude\worktrees\agent-adbf5b776b3afc31e\src\autoclave\__init__.py`.

No se ejecutó ningún `.ps1` ni el Setup. Solo se analizaron los `.ps1` con el analizador de PowerShell (`Parser::ParseFile`: 0 errores en los 13) y se compiló el `.iss` con `ISCC.exe`.

## Commits

| Commit | Qué |
|---|---|
| 7c04916 | D9-7: correo neutro y solo `cycles/factory` en los `.spec`; verificador |
| 75e7295 | D9-13.1: refresco de la configuración de fábrica al actualizar; siembra de programas de usuario desde fábrica |
| df41c9b | Guion del ensayo B → D |
| d8c18bf | D9-11: Setup con la estación; endurecimiento de los scripts de `tools/estacion` |
| 6eec84e | Hoja de banco: D9-8, D9-13.1, H4, H13 y H16 |
| (este) | Informe |

## D9-7. Entrega sin datos precargados

- **Correo:** plantilla nueva `src/autoclave/config/plantillas/correo_neutro.json`, con remitente vacío y sin destinatarios. Conserva servidor `smtp.gmail.com` y puerto 587, que no son datos del banco. `config/correo.json` del repositorio no cambia: es el del banco. El programa lee la plantilla como "correo sin configurar" (`config_correo.cargar` → `configurado = False`).
- **`.spec`:** en `Autoclave.spec`, `AutoclaveBackend.spec` y `AutoclaveSettings.spec`:
  - `cycles/` → `cycles/factory/`;
  - `correo.json` empaquetado = la plantilla neutra, igual que la calibración de D8-3.18;
  - el propio build se detiene (`SystemExit`) si algo de `autoclave/cycles/` que no sea `factory/` llega a `a.datas`.
  - `AutoclaveSettings.spec` no lo pedía la decisión. Se cambió por coherencia: no se reparte.
- **Verificador:** `tools/verificar_entrega_neutra.py <dist/Autoclave>`. Sale con 1 si:
  - el `correo.json` empaquetado no es la plantilla byte a byte;
  - tiene remitente o destinatarios;
  - falta;
  - `cycles/` tiene algo distinto de `factory/` (`user/`, `defecto/`, archivos sueltos);
  - `factory/` no tiene programas;
  - la calibración no es la neutra (llama a `verificar_calibracion_neutra.py`).

  K9 puede correr solo este verificador.
- **Consecuencia que hubo que resolver:** sin `cycles/user` en el paquete, una instalación nueva tendría solo los programas de fábrica, que no son editables (`source == "factory"`). Parámetros del ciclo quedaría en solo lectura y D9-8 no se podría probar.
  - Solución en `utils/resources.py`: en la primera instalación (no existe la carpeta persistente `cycles/user`), los programas de usuario se siembran como copia de los de fábrica, sin `nombre_clave`. Ese campo es solo de fábrica: si quedara en la copia, un nombre cambiado en el hospital se seguiría mostrando con el del catálogo. El nombre en cada idioma se sigue resolviendo por el de fábrica (`nombre_clave_de`).
  - La copia se arma en una carpeta temporal y se renombra, porque varios procesos pueden arrancar a la vez.
  - Si la carpeta ya existe (cualquier actualización), no se toca.
  - **DECISIÓN SIN CONFIRMAR (E9-1).**
- **Hallazgo:** los `cycles/user` del repositorio difieren mucho de fábrica. `bowe_dick` tiene 29 diferencias, entre ellas modo 4, 134,5 °C y tasas; 121 y 134 tienen secciones de estabilización viejas. Son residuos del banco. Con D9-7 dejan de salir en la entrega, pero **el equipo de pruebas los conserva al actualizar**: D9-13.1 nunca toca `cycles/user`. Ver PREGUNTA E9-P1.

Pruebas: `tests/test_t9_e9_entrega_neutra.py`, 14 pruebas: plantilla, lectura, `.spec` y verificador con 8 casos de rechazo.

## D9-11. Setup "Configurar este PC como estación del autoclave"

El Setup de Inno estaba solo en la rama `instalador-setup` (2609644, sin unir a `dev`). Se tomaron sus 3 archivos y se extendieron (`git checkout 2609644 -- tools/instalador`). **Punto de choque:** al unir `tanda-9-e9`, la rama `instalador-setup` queda superada. No hay que unirla después, o chocará en `tools/instalador/*` (PREGUNTA E9-P2).

**`tools/instalador/autoclave.iss`** (AppId sin cambios; versión por defecto `1.0.0-d` / `1.0.0.4`, que se puede pasar con `/DAppVer` y `/DAppVerNum`; entrega por defecto `entrega\2026-10-23_d`):
- **Casillas:**
  - "Iniciar Autoclave automáticamente…" (marcada, ya existía);
  - "Configurar este PC como estación del autoclave…" (**marcada**): pasos 01, 04 y 05;
  - "Arranque sin logo de Windows y sin pantalla de bloqueo" (**desmarcada**): paso 02.
- **Página "Inicio de sesión automático"** (después de Tareas, solo con la estación):
  - usuario, prellenado con la cuenta de la sesión de consola (WMI `Win32_ComputerSystem.UserName`), porque el Setup corre elevado y `{username}` podría ser el administrador del UAC;
  - contraseña y repetición; no deja seguir con la contraseña vacía o distinta.
  - No valida la contraseña contra Windows (DECISIÓN SIN CONFIRMAR E9-3): si es incorrecta, Windows muestra el inicio de sesión al reiniciar, sin otro efecto.
- **Contraseña:** pasa a PowerShell por la variable de entorno `AUTOCLAVE_CLAVE_AUTOLOGON` del proceso del Setup (`SetEnvironmentVariableW`), que el Setup vacía después. El script la borra al leerla. Nunca va en la línea de comandos.
- **Ejecución:**
  - los scripts se instalan en `{app}\estacion\` (Archivos de programa: solo administradores los cambian); el desinstalador los necesita;
  - `estacion_setup.ps1` (puente nuevo) corre cada paso con `$ErrorActionPreference='Stop'` y devuelve 0 o 1;
  - antes de aplicar un paso, el Setup lo anota en `HKLM\SOFTWARE\Especifika\Autoclave\Estacion` (`Paso01`…);
  - si algo falla, un solo aviso al final con la lista de pasos y la ruta del log. Autoclave queda instalado igual;
  - con la estación, la tarea de arranque se crea para la misma cuenta del inicio automático (`tarea_arranque.ps1 -Usuario`);
  - `NeedRestart` pide reiniciar.
- **Desinstalador:**
  - en `usUninstall` (los scripts siguen presentes) revierte solo los pasos anotados, en orden 05, 04, 02, 01;
  - borra la clave;
  - avisa si una reversión falla, con la instrucción de correr a mano el inverso de `tools/estacion`;
  - nunca usa `-EliminarCuenta`.
- **Permisos:** `[Dirs] {commonappdata}\Especifika\Autoclave; Permissions: users-modify` ya estaba. Inno lo aplica también si la carpeta existe; la lista de verificación incluye comprobarlo con `icacls`.
- **Compilación:** `ISCC.exe /Q /O<fuera del repo> /DEntrega=entrega\2026-10-23_c tools\instalador\autoclave.iss` → salida 0, sin advertencias.
  - Se usó la carpeta `Autoclave\` de la C solo para comprobar que compila. El `.exe` resultante (85 MB) se **borró** y no es entregable.
  - No se ejecutó.

**Revisión de los scripts (leyendo, sin ejecutar):**
- 02, 04 y 05 y los cuatro inversos no piden nada: no tienen `Read-Host` ni `ConfirmImpact`, y `-WhatIf` es opcional. Exigen administrador; el Setup y el desinstalador lo son.
- **01 sí pedía:** `Read-Host` sin `-Contrasena`, y `DefaultDomainName` fijo al nombre del equipo. Se agregaron:
  - `-Dominio`;
  - `-NoCrearCuenta`: falla sin cambiar nada si la cuenta local no existe, así nunca se crea `operador` desde el Setup;
  - `-ContrasenaDesdeEntorno`.

  Además, `AutoAdminLogon` ahora se escribe al final. Sin parámetros, el script se comporta como antes.
- **Problemas de seguridad encontrados y corregidos** (aparecen porque el Setup da Modificar a Usuarios en la carpeta de datos, que contiene `estacion\`, y los inversos corren como administrador con lo que diga `respaldo_<paso>.json`):
  1. **El log escribía `DefaultPassword` en claro.** También escribía el valor anterior. Ahora sale `********`.
  2. **Un usuario sin privilegios podía leer o alterar `estacion\`.** Esa carpeta tiene la contraseña anterior en el respaldo y los respaldos que el inverso aplica en `HKLM`. Ahora queda solo para Administradores y SYSTEM: dueño Administradores, sin herencia, y los archivos de adentro vuelven a heredar (`Protect-DirEstacion` en `_comun.ps1`). Se aplica también con `-WhatIf`.
  3. **`Restore-RegValores` restauraba cualquier clave** que dijera el respaldo, lo que permitía escalar privilegios con un respaldo plantado. Ahora:
     - solo restaura los 25 valores de `$ValoresGestionados`;
     - `Set-RegValor` rechaza escribir uno que no esté en la lista;
     - una prueba comprueba que la lista coincide exactamente con lo que escriben los pasos.
  4. **`05_revertir` importaba el `.pow` de cualquier ruta del respaldo.** Ahora solo el de `estacion\`.
- **Riesgo que se mantiene:** la contraseña del inicio automático queda en `Winlogon\DefaultPassword`, legible por administradores. Lo exige `AutoAdminLogon` y ya era un riesgo aceptado en el plan de la estación, §3.1.

**Lista de verificación** para el PC de prueba, en `tools/instalador/LEEME.md`: estado previo, instalar, reiniciar, inicio automático, Autoclave abierto, desinstalar, reversión y resultado con firma. El LEEME se reescribió para la D. `tools/estacion/LEEME.md` tiene una sección nueva, "Desde el Setup".

Pruebas: `tests/test_t9_e9_setup_estacion.py`, 11 pruebas **estáticas** (prohibido ejecutar `.ps1`):
- lista blanca = valores escritos (25);
- restauración solo de gestionados y log sin contraseña;
- carpeta protegida;
- 01 sin interacción;
- los demás no piden nada;
- puente del Setup;
- casillas marcada y desmarcada;
- pasos y reversión en orden inverso;
- página y contraseña por entorno;
- scripts instalados y permisos;
- mensajes es/en completos.

Las pruebas se escribieron después del código: es la parte de la etapa sin TDD estricto.

## D9-8. Modo 5 en la primera instalación

Sin cambio de código, por decisión. Caso **A-E9-01** en la hoja de banco: instalación limpia de la D, luego Parámetros del ciclo, luego modo 5 en los 4 programas. Si solo ofrece hasta el 4: captura y aviso.

Lo comprobado en código:
- los 8 JSON de la B (fábrica y usuario) tienen `descompresion.modo` con mínimo 0 y máximo 5;
- la D, con la siembra desde fábrica de D9-7, deja los 4 programas editables en la primera instalación (prueba `test_primera_instalacion_siembra_programas_de_usuario_desde_fabrica`).

Antes de D9-7, una instalación limpia de una entrega sin `cycles/user` no habría dejado editar ningún programa.

## D9-13.1. Actualizar sin copiar archivos a mano

**Decisión: lo hace el programa al arrancar, no el Setup** (DECISIÓN SIN CONFIRMAR E9-2). Motivos:
1. sirve igual con el Setup, con el autoinstalador del exe (`instalador_exe`) y con la copia portátil;
2. se prueba con pytest; el código Pascal del Setup no;
3. mantiene la regla del Setup de no tocar nunca archivos de `ProgramData`;
4. es el mismo mecanismo que ya refresca `cycles/factory`.

**Cómo funciona** (`utils/resources._sembrar`):
- Para `autoclave/config/instances/*` y `autoclave/config/global_params.json`, si el archivo persistente difiere byte a byte del empaquetado:
  1. lo copia a `programa\respaldos_configuracion\<AAAA-MM-DD_HHMMSS>\autoclave\config\…`, fuera de `config\` para que nunca se cargue un respaldo como instancia;
  2. lo reemplaza;
  3. deja un aviso en el log.
- Si el respaldo falla, **no reemplaza** y queda el anterior.
- Si es igual, no hace nada: no hay respaldos en cada arranque.
- Nunca entran: `calibration.yaml`, `correo.json`, `active_instances.yaml`, `cycles/user`, `cycles/defecto`, ni nada fuera de `programa\` (perfil, BD, `data\asignacion_io.json`).
- `config/models/*.yaml` no está en la lista de D9-13.1: se sigue sembrando solo si falta.
- Un `global_params.json` editado a mano en el sitio se respalda y se reemplaza también en un reinicio sin actualización, igual que `cycles/factory`. Los valores vigentes viven en la BD. Se ajustó `tests/test_p1_rutas_build_congelado.py`, que antes exigía lo contrario (P1, tanda 7).

**Ensayo B → D sobre una copia** (`tools/ensayo_actualizacion_b_d.py`, en el repositorio para que K9 lo repita con el `_internal` real de la D):
- código de la B: `git archive inst-2026-10-22-b src`, extraído en `C:\Users\tecni\Documents\_t9_e9_tmp\repo_b`;
- `_internal` de la B: copia de `entrega\2026-10-22_b\Autoclave\_internal\autoclave\{config,cycles}`;
- D: este worktree con `--desde-src` (lo que empaqueta `Autoclave.spec`);
- ProgramFiles y ProgramData de prueba. No se tocó nada fuera de las copias.

Salida (`_t9_e9_tmp\ensayo_b_d.txt`):

```
B: version_bd 9; perfil y calibración en <tmp>\PD\Especifika\Autoclave
D: serial PRUEBA-001, version_bd 10, usuarios [admin, cristian, ingeniero], temp_max_apertura 75,
   pausa_max_esterilizacion_s 30, espera_sellado_sin_sonda_min 30, marca_calibracion true, marca_correo true,
   AI [temp_camara, temp_2_camara, temp_referencia, temp_drenaje, pres_camara, pres_chaqueta],
   DO [..., descompresion_rapida, descompresion_lenta, ..., aire_comprimido_chaqueta, aire_comprimido_camara, ...,
       agua_chaqueta, ..., buzer_alarma], fuentes [user],
   respaldos [2026-10-23_002028/autoclave/config/global_params.json,
              2026-10-23_002028/autoclave/config/instances/ACV-2026-001.yaml]
OK: sin errores []
```

**Cámara 2 y `descompresion_lenta` aparecen sin pasos manuales.** Se conservan:
- la calibración del equipo;
- el correo del sitio;
- los programas de usuario de la B, idénticos byte a byte;
- el perfil, los usuarios y `temp_max_apertura` = 75.

Solo hay respaldos de los dos archivos esperados. La sección "Actualizar B → D" del LEEME de la entrega (K9) ya no necesita pasos de copia.

Pruebas: `tests/test_t9_e9_refresco_config_fabrica.py`, 10 pruebas:
- primera instalación: siembra, nombres y no volver a sembrar;
- refresco con respaldo;
- datos del sitio intactos;
- sin cambios, sin respaldo;
- dos actualizaciones;
- respaldo fallido sin reemplazo;
- siembra de calibración y correo solo si faltan;
- ruta del respaldo.

## Hoja de banco

En `docs/mis_plans/hoja_pruebas_banco_equipo_pruebas.md`, bloque nuevo "E9" y filas en el resumen:
- A-E9-01: D9-8 y D9-7 en instalación limpia;
- A-E9-02: actualización B → D con el Setup, sin copias;
- D-E9-01: H4, presión «—» sin transductores;
- D-E9-02: H13, motivo del modo no válido con Líquido;
- D-E9-03: H16, E/S según el perfil, con la lista esperada del ensayo.

Además, la nota de D-39 que remitía a "copiar el YAML a mano" ahora remite a A-E9-02.

## Pruebas corridas (solo las de los módulos tocados y sus importadores)

```
tests/test_t9_e9_entrega_neutra.py tests/test_t9_e9_refresco_config_fabrica.py tests/test_t9_e9_setup_estacion.py
tests/test_p1_rutas_build_congelado.py tests/test_c2_programas_persistentes.py tests/test_r8_asignacion_io.py
tests/test_o2e_bitacora.py tests/test_calentamiento_fase.py tests/test_t8_k8_calibracion_neutra.py
tests/test_b2_spec_excludes.py tests/test_config_correo.py tests/test_instalador_exe_carpeta.py
tests/test_o2g_conectividad.py tests/test_c2_correo_destinatarios.py
→ 206 passed in 33.30s
```

## DECISIONES SIN CONFIRMAR

- **E9-1:** en la primera instalación (sin `cycles/user` persistente), los programas de usuario se siembran como copia de los de fábrica, sin `nombre_clave`. Sin esto, D9-7 dejaba todos los programas en solo lectura.
- **E9-2:** el refresco de D9-13.1 lo hace el programa al arrancar, no el Setup. Ocurre siempre que el archivo difiere del empaquetado, también tras una edición manual sin actualización, y con respaldo con fecha.
- **E9-3:** la página del Setup no valida la contraseña contra Windows; solo exige que no esté vacía y que coincida al repetirla. Una contraseña errónea solo deja la pantalla de inicio de sesión.
- **E9-4:** si en una actualización se desmarca la casilla de la estación, no se revierte nada. Revierte el desinstalador o los scripts. Si se deja marcada, vuelve a pedir la contraseña.
- **E9-5:** el correo neutro conserva `servidor_smtp` = `smtp.gmail.com` y `puerto` = 587 (no son datos del banco).
- **E9-6:** `AutoclaveSettings.spec` también se dejó con correo neutro y solo `factory`.
- **E9-7:** la protección de `estacion\` y la lista blanca se aplican también al usar los scripts a mano. La protección se aplica incluso con `-WhatIf`.

## PREGUNTAS PARA CRISTIAN

- **E9-P1:** el equipo de pruebas conserva al actualizar los `cycles/user` de la B, con residuos del banco: Bowie-Dick en modo 4, 134,5 °C, etc. D9-13.1 prohíbe tocarlos. ¿Se restablecen a mano desde Parámetros del ciclo (valor por defecto) después de instalar la D, o se quiere una opción "restablecer programas a fábrica"?
- **E9-P2:** la rama `instalador-setup` (2609644) queda absorbida por `tanda-9-e9`. ¿Se borra esa rama, o se une antes, para no chocar en `tools/instalador/*`?
- **E9-P3:** con una cuenta Microsoft (no local), Windows a veces ignora el inicio automático con el nombre corto de la cuenta. Está en la lista de verificación (anotar el tipo de cuenta). ¿El equipo usará cuenta local?

## Pendientes

- Validar el Setup en el PC de prueba con la lista de `tools/instalador/LEEME.md` (Cristian). Hasta entonces, no instalar la D con la casilla de la estación en el equipo del autoclave.
- K9:
  - compilar el Setup con `/DEntrega=entrega\<fecha>_d`;
  - correr `tools/verificar_entrega_neutra.py` sobre la carpeta compilada;
  - opcionalmente repetir el ensayo con el `_internal` real: `python tools/ensayo_actualizacion_b_d.py <repo_B> <internal_B> <repo_D> <dist\Autoclave\_internal> <tmp>`.
- No se lanzaron revisores (etapa no ★). La parte de la estación toca seguridad de Windows (registro, contraseña). Si la sesión principal lo considera, conviene un `safety-reviewer` del diff de `tools/estacion` y `tools/instalador`.
- Puntos de choque:
  - `src/autoclave/utils/resources.py`;
  - `tests/test_p1_rutas_build_congelado.py`;
  - los tres `.spec`;
  - `docs/mis_plans/hoja_pruebas_banco_equipo_pruebas.md` (filas del resumen después de G-04 y bloque antes de "Registros…");
  - `tools/instalador/*`.

  No se tocó i18n, `db_manager.py`, `control_loop.py`, `set_io.py`, el catálogo de alarmas ni QML. No hay códigos de alarma nuevos.
