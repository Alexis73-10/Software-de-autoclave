# Instrucción maestra para Claude Code — Tanda 11 (sin supervisión)

> La lanza `tools/tandas/lanzar_tanda.ps1 -Tanda 11` (`claude -p`, se relanza si se corta): REANUDA siempre desde `docs/informes/tanda11/estado.md`.

**Contexto:** ajustes pedidos por Cristian el 23-oct tras usar la compilación F en el equipo de pruebas. Fuente de verdad: `docs/mis_plans/decisiones_tanda_11.md`, COMPLETO. Los ciclos en el equipo empiezan el lunes 26-oct.

**Modo:** **4 subagentes en paralelo** (aprobado por Cristian para esta tanda), cada uno en su worktree y rama `tanda-11-<id>`, solo con sus pruebas (`PYTHONPATH=<worktree>/src`, comprobando `autoclave.__file__`). La suite completa solo la corre la sesión principal: una vez por cada unión, en paralelo con `pytest -n auto` como en la sección 2 de la tanda 10 (si algo falla, repite en serie solo lo que falló). **NO termines el turno con subagentes activos.**

## 0. Reglas
1. **Rama y archivos:** rama `tanda-11` desde `dev`; subramas `tanda-11-<id>`. Estado en `docs/informes/tanda11/estado.md`. Informes en `docs/informes/tanda11/<id>_<nombre>.md`. Decisiones sin confirmar en `docs/informes/tanda11/DECISIONES_PARA_REVISAR.md`. Índice en `docs/informes/informe_tanda_<fecha>_t11.md`.
2. **Precondición (A0):** `docs/informes/tanda10/estado.md` tiene `| Z | Hecha |` y `dev` contiene `tanda-10`. Si no, escribe "Esperando el cierre de la tanda 10" en `tanda11/estado.md` y termina.
3. **Git:**
   - Nunca uses `main`, `--force`, `git add -A` ni `git push --delete`.
   - No commitees `data/`, `.claude/`, `*.db`, `installation_profile.json*`, `dist/`, `build/` ni `entrega/`.
   - No toques `stash@{0}`.
   - Une a `dev` con `--no-ff` y la suite en verde.
   - Varias etapas tocan `i18n/es.json` y `en.json`: une **de una en una** y resuelve los conflictos conservando las claves de ambas.
4. **Prohibido:** hardware o puertos COM reales, cargar firmware, EJECUTAR `.ps1` o el Setup, instalar software del sistema. **Autorizado:** PyInstaller en un clon limpio de la etiqueta e `ISCC.exe` (solo compilar).
5. **Ante ambigüedad:** lo más seguro y reversible, como "DECISIÓN SIN CONFIRMAR". Si algo termina tocando la lógica de ciclo, estado seguro o puertas fuera de lo que dicen las decisiones, no lo cambies y déjalo como "PREGUNTA PARA CRISTIAN".
6. **Prioridad:** A0 → (R11, E11, S11, U11 en paralelo) → N11 y O11 (entran en cuanto se libera un cupo, en ese orden) → K11 → Z. Si el límite de uso amenaza, K11 y Z van antes que lo no empezado; Z se hace SIEMPRE.

## 1. Etapas
**A0.** Comprueba la precondición, crea `tanda-11` desde `dev`, toma la línea base de la suite y haz un commit `docs(tanda11)` con esta instrucción, `decisiones_tanda_11.md` y el prompt.

**R11. Reinicio del software al cambiar la impresora** (subagente). D11-1:
- `reiniciar_software` reutilizable, con el cierre ordenado del apagado pero sin `shutdown`, y relanzamiento de `Autoclave.exe` con una sola instancia.
- Diálogo en `OpcionesParametrosEquipo.qml` y rechazo en CICLO en el backend.
- En desarrollo (sin exe congelado), el relanzamiento usa el mismo comando con el que arrancó el proceso.
- Pruebas: confirmar/cancelar; rechazo en CICLO; la auditoría; el orden "guardar → cerrar → relanzar" (con un lanzador simulado, nunca reiniciando de verdad); y que no quede un segundo backend escuchando.

**E11. Retiro de `aire_comprimido_chaqueta`** (subagente, corto). D11-2:
- Busca TODAS las apariciones (`grep -rn aire_comprimido_chaqueta`, incluidas las variantes con prefijo `funcion_`) en `src/`, `tests/`, `tools/`, la configuración y la documentación de E/S.
- Pruebas:
  - la función ya no aparece en `/io/channels` ni en la asignación de E/S;
  - las demás salidas conservan su número;
  - un YAML antiguo que la trae arranca con una advertencia;
  - `aire_comprimido_camara` sigue funcionando en descompresión modo 4 y en el protocolo de fallo (pruebas existentes en verde).

**S11. SEN-03 según los sensores en uso** (subagente, corto). D11-3 en `vigilar_fuera_de_ciclo` y sus llamadores (`preparacion.py`, `preparado.py`). Pruebas:
- un sensor "No en uso" desconectado no da SEN-03;
- al pasar a un programa que lo usa, aparece en el siguiente tick;
- al volver, se resuelve;
- con 2 pantallas, se vigila la unión de los programas seleccionados en ambas;
- `verificar_inicio` sigue bloqueando el programa que lo usa.

**U11. Cuentas Admin e Ingeniero** (subagente; ★ con un revisor `safety-reviewer` al final, porque toca la autenticación). D11-6 completo: marca de cuenta del sistema, protecciones en el backend y en la UI de usuarios, inicio de sesión sin distinguir mayúsculas, unicidad al crear sin distinguir mayúsculas y migración idempotente. Pruebas:
- la migración sobre una copia de una BD con `admin`/`ingeniero`: contraseña, `debe_cambiar_clave` y auditoría intactos, más la fila `usuario_renombrado`;
- que corra dos veces sin efecto;
- el choque de nombres;
- el rechazo (409) de desactivar, borrar, cambiar el rol o renombrar las 2 cuentas;
- el inicio de sesión con `admin`, `ADMIN` y `Admin`;
- la regla del último ingeniero activo.

Actualiza las credenciales iniciales en `entrega/LEEME_INSTALACION.md` (solo el texto fuente del repo, no `entrega/` compilada) y en la hoja de pruebas de banco.

**N11. Instalador: Actualizar o Instalación limpia y asociación de táctiles** (subagente; un solo subagente porque ambos tocan `autoclave.iss`). D11-4 y D11-5:
- página de opciones, doble confirmación, respaldo previo y cancelación si el respaldo falla;
- `06_asociar_tactiles.ps1`, su revertir, el registro en `ClaveEstacion` para que el desinstalador lo revierta, y el `LEEME.md` de la estación.

Verificación sin ejecutar nada:
- `ISCC.exe` compila;
- revisión de la lógica Pascal en el informe (tabla de casos: sin instalación, versión vieja, misma versión, versión más nueva, respaldo fallido);
- análisis estático de PowerShell si está disponible.

Agrega a `hoja_pruebas_banco_equipo_pruebas.md` los casos que Cristian debe probar en el PC de prueba: actualizar, instalación limpia con respaldo, asociación de los 2 táctiles y reinicio del PC con la asociación conservada.

**O11. Entradas mostradas: solo sensores en uso y selector por fila** (subagente). D11-7 completo:
- backend (`_entradas_mostradas_de`, `entradas_de`, `fijar_entradas`, el cambio de rol y la omisión);
- `parametros_ciclo_controller.py` y `OpcionesParametrosCiclo.qml` con las 3 filas y su desplegable;
- Preciclo, Ciclo y la gráfica sin las filas "No en uso".

Si S11 ya está unida, parte de `tanda-11` actualizada; si no, coordina los cambios en `sensores_ciclo.py`.

Pruebas:
- el selector no ofrece un sensor No en uso y el backend lo rechaza (422);
- el cambio de rol lo quita de la selección (con auditoría) y repone el Principal si la lista queda vacía;
- la omisión con distintas asignaciones;
- un JSON viejo con un sensor No en uso se filtra al presentarse;
- no hay entradas repetidas entre filas y la Entrada 1 es obligatoria;
- capturas antes/después de Opciones, Preciclo y Ciclo con el banco de capturas, en es y en.

**K11. Compilación G** (sesión principal). Mismos pasos y verificaciones que K10:
- verificador neutro y prueba de humo;
- ensayo F → G sobre una copia con el perfil y la BD de la F, para probar la migración de usuarios de U11;
- Setup compilado y no ejecutado;
- SHA-256;
- `usb/` con exactamente lo que va a la USB.

**Z. Cierre (OBLIGATORIO).**
- Suite en verde y unión a `dev` comprobada.
- Push de `dev`, `tanda-11` y la etiqueta.
- Índice con el resumen, las DECISIONES SIN CONFIRMAR, las PREGUNTAS y lo que quedó sin hacer.
- Primera línea del índice: si hay compilación G y si se recomienda instalarla antes del lunes.
- Fila `| Z | Hecha |` en `estado.md`.
