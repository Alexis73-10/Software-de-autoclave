# G1 — Generador de códigos usable sin terminal

Instrucción: `instruccion_claude_code_tanda_2.md` §2 G1 y decisión 6b (agregadas el 19-oct por la sesión de Cristian). El generador corre solo en el PC de Cristian, con su propia base, y los demás usuarios entran por navegador desde la red local.

## Qué se hizo (`tools/generador/`)

| Archivo | Rol |
|---|---|
| `db.py` | Base propia con **WAL** y `busy_timeout` de 5 s; tabla nueva `usuarios` (usuario, hash, rol admin/usuario, activo, creado, debe_cambiar). La migración es idempotente: `codigos_generados` no cambia y los registros históricos (p. ej. "especifika") se conservan. |
| `datos_generador.py` | Carpeta de datos persistente: `C:\ProgramData\Especifika\Generador\` por defecto o la variable `GENERADOR_DATOS`. `config.json` con host (`0.0.0.0`, red local), puerto (8080), inactividad (15 min), intentos (5), bloqueo (15 min) y retención (30 días). La primera vez **copia** (no mueve) la `generador.db` heredada; nunca pisa una base existente. |
| `seguridad_generador.py` | **Hash con la misma función del software** (`autoclave.backend.contrasenas`, PBKDF2-HMAC-SHA256 con sal). Bloqueo temporal tras N fallos. Sesiones en memoria con expiración por inactividad (`time.monotonic`). Admin inicial con contraseña temporal aleatoria. |
| `respaldo_generador.py` | Respaldo con la **API de respaldo de SQLite** al arrancar y cada 24 h, en `Respaldos\`. `PRAGMA integrity_check` de cada copia: una corrupta se descarta. Retención de 30 días. |
| `app.py` | `create_app()`, con estas rutas: login, cierre de sesión, cambio de contraseña (obligatorio en el primer ingreso), generar y reinstalar (`codigos_generados.usuario` = usuario real), administración solo para admin (crear con contraseña temporal mostrada una vez, desactivar/activar, restablecer contraseña) y `/salud`. **Se eliminaron el usuario y la contraseña por defecto del código** (`GENERADOR_USER/PASS`). La pantalla de login muestra la URL con la IP local para compartirla. |
| `lanzador.py` | Entrada del ejecutable y de desarrollo. Si el puerto lo ocupa otra instancia del generador, solo abre el navegador; si lo ocupa otro programa, sale con código 2 y lo deja en el log. Si no, arranca el servidor y abre el navegador. Con `--sin-navegador` es la variante para la tarea programada. |
| `instalar_inicio_automatico.ps1` / `quitar_inicio_automatico.ps1` | Tarea programada **al iniciar el equipo**, como SYSTEM, sin ventana, que reintenta si se cae. |
| `abrir_firewall.ps1` | Regla de entrada TCP solo al puerto, **solo perfiles Privado/Dominio** y **solo desde la subred local**. |
| `../../GeneradorCodigos.spec` | PyInstaller onefile, **sin consola**, sin datos dentro del ejecutable. |

**Primer arranque sin usuarios:** se crea `admin` con una contraseña temporal aleatoria. Se imprime una vez en la consola (en desarrollo; el ejecutable no tiene consola) y se escribe en `CLAVE_INICIAL_ADMIN.txt`, en la carpeta de datos. La pantalla de login indica dónde está, sin mostrarla en la red. El archivo se borra cuando admin cambia la contraseña.

No se cambió `activation.py` ni sus secretos. El diseño a futuro está en `docs/mis_plans/planeacion_generador_codigos.md`:
- firmas Ed25519;
- servidor central con HTTPS y respaldos;
- secretos fuera del código;
- licencias por pago.

**Aviso:** el ejecutable del generador **no debe copiarse a ningún PC de cliente**.

## Pruebas

- Nueva `tests/test_g1_generador.py`, 22 pruebas:
  - WAL y busy_timeout;
  - migración de una base heredada conservando sus registros;
  - no pisar una base existente;
  - config por defecto y configurable;
  - sin contraseña por defecto en el código;
  - admin inicial;
  - hash y verificación;
  - bloqueo por intentos y desbloqueo por tiempo;
  - expiración de la sesión y renovación con el uso;
  - usuario desactivado;
  - cambio obligatorio que borra el archivo de la clave inicial;
  - usuario real en los códigos;
  - permisos de admin;
  - no quedarse sin admin;
  - restablecer contraseña;
  - `/salud` y la URL en el login;
  - respaldo con integridad;
  - retención de 30 días;
  - puerto ocupado por otro programa;
  - puerto ocupado por el generador.
- `tests/test_generador_db.py` (8, anteriores): sin cambios, en verde.
- **Prueba de humo** con el lanzador real en una carpeta temporal: `/salud` responde, copia de la base heredada, respaldo creado, aviso del admin inicial y URL de red en el login; una segunda instancia solo abre el navegador.
- No se corrió la suite completa en este punto: la otra sesión tenía U4 a medio editar en el mismo árbol. G1 no toca código del autoclave.

## Cómo compilar y probar (Cristian)

1. Desde la raíz del repo: `pyinstaller GeneradorCodigos.spec` → `dist\GeneradorCodigos.exe`.
2. Copiar el `.exe` a una carpeta fija del PC de Cristian, p. ej. `C:\Especifika\`. La primera vez copia `tools\generador\generador.db` si está junto al `.exe` o en `tools\generador\`.
3. Doble clic: abre el navegador. Ingresar como `admin` con la clave de `C:\ProgramData\Especifika\Generador\CLAVE_INICIAL_ADMIN.txt` y cambiarla.
4. Como administrador:
   - `.\abrir_firewall.ps1 -Puerto 8080`;
   - `.\instalar_inicio_automatico.ps1 -Exe C:\Especifika\GeneradorCodigos.exe`.

**Comprobaciones manuales:**
- login desde otro PC de la red con la URL de la pantalla de login;
- reiniciar Windows y entrar sin abrir nada (inicio automático);
- `Respaldos\` con un archivo del día;
- dos usuarios generando códigos al mismo tiempo, con sus nombres en el historial;
- 5 contraseñas malas bloquean ese usuario 15 min;
- con la red marcada como **Pública**, otro PC no debe poder entrar.

## DECISIONES SIN CONFIRMAR

- **D-G1-1:** inicio automático con una tarea programada **al iniciar el equipo como SYSTEM**, sin ventana ni sesión iniciada. Es más robusto que un acceso directo en Inicio, que depende de que alguien inicie sesión. El navegador lo abre cada usuario.
- **D-G1-2:** `CLAVE_INICIAL_ADMIN.txt` queda en `C:\ProgramData\...`, que por defecto pueden leer los usuarios locales del PC. Aceptable porque solo vive hasta el primer cambio. Alternativa: restringir los permisos de la carpeta de datos a Administradores y SYSTEM.
- **D-G1-3:** inactividad de 15 min, 5 intentos, bloqueo de 15 min y contraseña mínima de 10 caracteres. Todo se configura en `config.json`, salvo la longitud mínima.
- **D-G1-4:** las sesiones viven en memoria: reiniciar el generador cierra todas.
