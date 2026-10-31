# Prompt para Claude Code — tanda 22: teclado en pantalla que dispara acciones por cada tecla (sin supervisión)

Lo envía `powershell -ExecutionPolicy Bypass -File tools\tandas\lanzar_prompt.ps1 -Nombre tanda22` y lo reenvía si la sesión se corta.

---

Eres Claude Code en el repositorio del Software de Autoclave (Especifika). Cristian NO está presente: trabaja de forma autónoma, sin detenerte a preguntar. Todo en español (código, comentarios, commits, informe). Código Clase C (NTC-IEC 62304): velocidad sin sacrificar seguridad.

## Reglas

1. Si existe `docs/informes/tanda22/estado.md` con pasos hechos, REANUDA desde el primero pendiente. Si no existe, créalo y empieza por A0.
2. Este prompt es la spec (TEC-ACC-01 a TEC-ACC-07). Ante ambigüedad, lo más seguro y reversible, marcado «DECISIÓN SIN CONFIRMAR» en el informe.
3. Rama `tanda-22` creada desde `dev`. Nunca `main`, `--force`, `git add -A`, `git push` ni `git branch -D`. No toques el backend salvo lo que diga este prompt (no hace falta: el backend contó y bloqueó bien), ni módulos reales, red, registro de Windows, `.ps1` ni el Setup. No leas el archivo de secretos.
4. **Subagentes: 2 a la vez como máximo** (tanda pequeña). Ningún subagente corre la suite completa; la sesión principal corre `pytest tests -n auto`.
5. Después de cada commit, actualiza `estado.md` (paso → Hecho/Pendiente, último commit).

## Informe de problema (PRB-T22-01, 29-oct, equipo de pruebas, 1.0.0-alpha.10)

Síntoma: en Opciones › Reasignación, al pedir la contraseña de confirmación el ingeniero no alcanza a escribirla, la pantalla lo saca con «Sesión no válida o vencida» y al volver a entrar el login dice «usuario bloqueado».

Evidencia (`tools/diagnostico/logs_autoclave_20261029_1047.zip`, `backend.log` y `ui_puerta1.log`): el backend NO se reinició; a las 10:36:50 recibió 4 POST `/io/assignment` con `reautenticacion_fallida` cada ~0,44 s (lo que tarda PBKDF2) y el 5.º (10:36:53) activó `ControlIntentos` (5 intentos, 300 s), que invalida el token (`_bloquear_por_cambio_clave`); el siguiente envío dio 401 `sesion_invalida`. Se repitió igual a las 10:42:19.

Causa: `Componentes/PanelTeclado.qml` entrega lo escrito «en vivo» (`Connections` → `onTextoChanged` → `_comprometerAlfanumerico` → `_alConfirmar(texto)`), y también lo entrega en `_guardarPendiente` (al abrir otro campo) y en `_cancelar` (con `""`). Eso es correcto para campos que solo guardan el texto en una propiedad, pero `OpcionesReasignacion._pedirClave(clave => control.aplicar(clave))` ejecuta un POST: cada tecla envía una contraseña parcial y suma un intento fallido.

Puntos afectados (callback que ejecuta una acción, no una asignación):
- `Pantallas/OpcionesReasignacion.qml`: `_pedirClave` (usado por Aplicar → `control.aplicar`, Restaurar fábrica → `control.restaurarFabrica` y Verificar → `control.verificar`); paso de nombre reforzado (línea ~548: `fijarNombre` + `Qt.callLater(_pasoReforzada(i + 1))`, avanza de paso con la primera letra); nombre reforzado de Verificar (línea ~605: `conClave(texto)` con la primera letra).
- `Pantallas/OpcionesConectividad.qml` `agregarDestinatario`: con la 1.ª letra del nombre abre el teclado del correo; cada letra del correo llama a `control.agregar`.
- `Pantallas/OpcionesManejoCiclos.qml` `elegirBase` y `pedirDuplicar`: cada letra llama a `control.crear` / `control.duplicar`.

No afectados (solo asignan, se dejan como están): Login, CambioClave, NuevoUsuario, Instalacion, OpcionesUsuarios, SelectorDestino y todos los `abrirNumerico` (Calibración de sensor, Mantenimiento, Parámetros de ciclo y de equipo). En A0 verifica con grep que la lista de afectados está completa; si encuentras otro callback que ejecute una acción (llamada a un controlador que envía al backend, apertura de diálogo o de otro teclado, cambio de pantalla), agrégalo y anótalo.

## Decisiones (TEC-ACC)

- **TEC-ACC-01** `PanelTeclado` gana un modo «acción» (solo al confirmar): `abrirAlfanumericoAccion(titulo, valorInicial, longitudMaxima, ocultar, alConfirmar)` (sin `siguiente`). Una propiedad interna `_enVivo` (true en `abrirAlfanumerico`/`abrirNumerico`, false en el modo acción) decide. En modo acción `alConfirmar` se llama **exactamente una vez y solo** al pulsar Confirmar: no en `onTextoChanged`, no en `_guardarPendiente` (lo escrito se descarta al abrir otro campo), no en `_cancelar` (no se llama con `""`), no en Ocultar/`cerrar()`. El modo en vivo actual no cambia en nada.
- **TEC-ACC-02** En modo acción, Confirmar con texto vacío no llama a `alConfirmar` y deja el teclado abierto (DECISIÓN SIN CONFIRMAR).
- **TEC-ACC-03** Reentrancia: `_entregar` ya anula `_alConfirmar` antes de llamarlo; conservarlo y agregar una guarda para que un doble toque en Confirmar mientras el POST síncrono está en curso no produzca un segundo envío (p. ej. el panel queda cerrado o con `_alConfirmar` nulo antes de la llamada; probarlo).
- **TEC-ACC-04** Los 7 puntos afectados pasan a `abrirAlfanumericoAccion`. Las cadenas de dos pasos (nombre reforzado → siguiente diálogo; nombre del destinatario → correo) avanzan solo al Confirmar el primer paso. Cancelar en cualquier paso aborta la cadena sin enviar nada.
- **TEC-ACC-05** `ui_qml/sesion_backend.py`: reconocer `reautenticacion_fallida` y `reautenticacion_requerida` (hoy se registran como «Respuesta no reconocida del backend»). En `enviar`, ante 429 `usuario_bloqueado` cerrar la sesión local de inmediato con el aviso de bloqueo (`sesion.usuario_bloqueado`, con los segundos si el login ya los usa) en lugar de esperar al 401 genérico de «sesión no válida». Revisa que el login muestre ese aviso al abrirse.
- **TEC-ACC-06** Documentación: comentario de cabecera de `PanelTeclado.qml` con la regla («un callback que ejecuta una acción usa el modo acción; el modo en vivo es solo para asignar texto a una propiedad») y una línea en `CLAUDE.md`, sección Interfaz.
- **TEC-ACC-07** Prueba de regla (estilo `test_i2_sin_literales_qml.py`): un test que recorra los `.qml` y falle si un `abrirAlfanumerico(`/`abrirNumerico(` recibe un callback cuyo cuerpo llama a `control.`, `.abrir(`, `abrirAlfanumerico`, `Qt.callLater` o `_pedirClave`. Lista blanca explícita y comentada si aparece un falso positivo.

## Etapas

**A0 (principal).** Crea la rama. Mueve `tools/diagnostico/logs_autoclave_20261029_1047.zip` y `tools/diagnostico/recoger_logs_salida.txt` a `docs/informes/tanda22/evidencia/` y haz commit de ellos junto con este prompt (`git add` con rutas explícitas). Verifica con grep la lista de puntos afectados y anótala en `estado.md`.

**P1 teclado (subagente, worktree `tanda-22-teclado`)**: TEC-ACC-01, 02, 03, 06 en `Componentes/PanelTeclado.qml`, con pruebas QML offscreen nuevas (`tests/test_t22_teclado_accion_qml.py`):
- escribir N caracteres en modo acción → 0 llamadas; Confirmar → 1 llamada con el texto completo;
- Cancelar, Ocultar y abrir otro campo → 0 llamadas;
- Confirmar vacío → 0 llamadas y panel abierto;
- doble Confirmar → 1 llamada;
- modo en vivo: el comportamiento actual intacto (cada tecla llega, Cancelar entrega `""`).

**P2 cliente (subagente, worktree `tanda-22-sesion`)**: TEC-ACC-05 con sus pruebas pytest.

Une P1 y P2 a `tanda-22`. Luego, **principal, secuencial**: TEC-ACC-04 en las 3 pantallas y TEC-ACC-07. Pruebas por pantalla con un controlador doble que cuente llamadas:
- Reasignación: escribir la contraseña letra a letra → 0 llamadas a `aplicar`/`restaurarFabrica`/`verificar`; Confirmar → 1. El nombre reforzado no abre el siguiente diálogo hasta Confirmar.
- Conectividad: el teclado del correo no se abre hasta Confirmar el nombre; `agregar` se llama 1 vez al Confirmar el correo.
- Manejo de ciclos: `crear`/`duplicar` 1 vez al Confirmar.

**R revisión (1 subagente, solo lectura)** sobre el diff de `tanda-22` contra `dev`: que ningún campo de formulario (Login, CambioClave, NuevoUsuario, Instalación, Usuarios) haya cambiado de comportamiento; que ningún punto de acción pueda enviar con texto parcial ni con `""`; que la reautenticación y el bloqueo del backend no se hayan tocado. Corrige lo que encuentre y anótalo.

**Suite.** `pytest tests -n auto` verde.

**K entrega (se compila, decisión de Cristian 29-oct).**
1. Une `tanda-22` a `dev` (merge sin fast-forward) y ejecuta `python tools/entrega/compilar_entrega.py --con-generador` desde `dev`.
2. Si la entrega se niega solo por archivos sin seguimiento que esta tanda no creó (p. ej. `.claude/`, `Claude outputs/`, `_suites_t11/`, `docs/informes/*/CERRADO.txt` viejos): agrégalos uno por uno a `.git/info/exclude` (local y reversible) y reintenta; nunca los borres ni hagas commit de ellos; lístalos en el informe con la instrucción para revertir.
3. Si se niega por cualquier otra causa, no la fuerces: `CERRADO.txt` con `BLOQUEADO:` y el motivo.

**U USB (decisión de Cristian 29-oct: formatear la unidad E: y copiar el instalador).** Solo con K exitosa. PowerShell. Comprobaciones previas, TODAS obligatorias; si alguna falla, NO formatees y cierra con `BLOQUEADO: USB no preparada — <motivo>`:
1. Idempotencia: si `E:\Autoclave_Setup_<semver>.exe` ya existe y su SHA-256 coincide con `SHA256SUMS.txt` de la entrega, no formatees ni copies: anótalo y pasa a Z.
2. `Get-Partition -DriveLetter E | Get-Disk`: `BusType` = `USB`, `IsBoot` = False, `IsSystem` = False, y el número de disco distinto del de `C:`, del de la unidad de datos del autoclave (si existe `HKLM\SOFTWARE\Especifika\Autoclave` → `RutaDatos`) y del disco donde está este repositorio.
3. Tamaño del disco ≤ 256 GB.
4. Anota en `estado.md`, ANTES de formatear: modelo, número de serie, tamaño del disco, etiqueta y sistema de archivos actuales de E:, y la lista de primer nivel de `E:\` (para el informe).

Formateo: solo el volumen E:, nunca `Clear-Disk`, `diskpart clean` ni otra unidad: `Format-Volume -DriveLetter E -FileSystem exFAT -NewFileSystemLabel AUTOCLAVE -Confirm:$false` (formateo rápido; exFAT por si el Setup supera 4 GB, DECISIÓN SIN CONFIRMAR). Si Windows lo niega por permisos (la sesión no es de administrador), no intentes elevar: cierra con `BLOQUEADO: USB no preparada — requiere administrador` y deja en el informe los comandos exactos para que Cristian lo haga.

Copia: todo el contenido de `entrega/v<semver>_<fecha>/usb/` (Setup, `SHA256SUMS.txt`, `LEEME_INSTALACION.md`, `drivers/`) a la raíz de `E:\`. Verifica el SHA-256 del Setup copiado contra `SHA256SUMS.txt` y lista lo que quedó en `E:\`. No expulses la unidad.

**Z cierre.**
1. Escribe `docs/informes/tanda22/R22_informe.md`:
   - informe de problema PRB-T22-01 (síntoma, evidencia, causa, corrección, verificación; §9 de la 62304);
   - qué cambió por TEC-ACC, archivos y pruebas;
   - decisiones sin confirmar;
   - qué verificar en la pantalla del equipo: reasignar con contraseña, reforzada, verificar, agregar destinatario, crear y duplicar programa;
   - la versión entregada y el resultado de la USB (datos del disco formateado y SHA-256 verificado);
   - recordatorio: si Cristian quedó bloqueado, se desbloquea solo a los 5 min o reiniciando el control.
2. Agrega la fila `| Z | Hecha | ... |` en `estado.md`.
3. Como último acto, escribe `docs/informes/tanda22/CERRADO.txt` con la fecha, el commit del merge, el resultado de la suite, la versión entregada y el estado de la USB (o el motivo del bloqueo en la primera línea).

Empieza por A0 (o reanuda).
