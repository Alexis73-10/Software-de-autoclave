# F1 — App de registro de pruebas de banco (teléfono Android, red local)

Código: `tools/registro_pruebas/` (README con el uso y las comprobaciones manuales). Pruebas: `tests/test_f1_registro_pruebas.py` (42) y `tests/js/cola.test.js` (9, con node). No se compiló nada ni se ejecutó ningún `.ps1`.

## Qué hay
- **Formulario generado desde `pruebas.py`** (35 pruebas, bloques A-G, incluidas las de H1). Al crear un registro se guarda un snapshot con hash; un cambio posterior de la fuente no lo altera (prueba).
- **Interfaz** (HTML/JS sin frameworks, `static/`): botones ≥ 48 px, alto contraste, una prueba por pantalla, navegación anterior/siguiente, avance por bloque, aviso (sin bloquear) del orden seguro (A-04, B-01, B-03, B-04 antes de E/F/G). Por prueba: pasos con casilla, valores observados, resultado (Aprobada/Fallada/No aplica), observaciones, fotos y firma en pantalla.
- **Usuarios y registros:** cada ejecutor con su usuario crea y edita SU registro (cabecera con equipo, serial, versión/commit, firmware/ID tarjeta, perfil, programas, instrumentos, fecha, lugar); el admin ve todos, crea ejecutores, restablece claves, respalda y ve la **consolidación por prueba** con las discrepancias marcadas.
- **Integridad:** hora del SERVIDOR y del teléfono (guardadas aparte); versiones inmutables (triggers contra UPDATE/DELETE) con SHA-256 encadenado; fotos y firmas con sha256 en la cadena; un resultado firmado solo cambia con versión nueva y motivo; "Verificar cadena" (detecta versión alterada, hueco, snapshot alterado o archivo modificado). Reintentos idempotentes por `cliente_uuid`. Anomalías `AN-nnn` versionadas (prueba, descripción, gravedad, acción, responsable, estado, reensayo), abribles desde la prueba.
- **Firma:** canvas → PNG pequeño por prueba al marcar su resultado, y firma final al cerrar (registro cerrado = inmutable).
- **Fotos:** `<input capture="environment">`, reducción en el cliente (1600 px, JPEG 80 %), varias por prueba, sello del servidor y hash, archivo `R<id>_<prueba>_foto_<hash>.jpg`.
- **Red inestable (sin service worker):** cola en IndexedDB con envío en orden, reintento con espera creciente (1→30 s), indicador "N pendientes de enviar", "Descargar copia (JSON)", aviso al cerrar con pendientes, sesión vencida pausa la cola sin perder nada. Probado con node (red cortada y recuperada, orden FIFO, rechazos, pausa) y en un navegador real con la red cortada (fetch forzado a fallar) contra el servidor local.
- **Salida:** `registro.json` (versiones y hashes), `registro.html` imprimible (cabecera, cada prueba, valores, miniaturas y firmas incrustadas, resumen por bloque, anomalías, hash final), `resultados.csv` y `exportar.py` (copia a `docs/informes/pruebas_banco/<fecha>/<usuario>/` sin fotos grandes ni base; sin tocar git).
- **Seguridad:** solo red local (firewall por subred, perfiles Privado/Dominio), sin credenciales por defecto (admin con clave aleatoria temporal), PBKDF2, bloqueo por intentos (también usuarios inexistentes), sesión de 10 h configurable, límites de subida, escape de HTML, CSRF (cabecera propia + SameSite=Strict), CSP y cabeceras seguras, validación de tipo por contenido.
- **Operación:** `lanzador_registro.py` (puerto ocupado: reutiliza o avisa), `iniciar_registro.bat`, `abrir_firewall.ps1`, `instalar_inicio_automatico.ps1`/`quitar_…`, respaldo con la API de SQLite (al arrancar y cada 6 h, con integridad y poda).

## Verificación en navegador (Chrome, escritorio) contra el servidor local
Login con cambio de clave obligatorio, alta de ejecutor, creación de registro, una prueba con casilla/valor/resultado/firma dibujada, guardado, red cortada con 2 pendientes y recuperación sin duplicados, cambio de un resultado firmado con motivo, aviso de orden seguro en E-01, pantalla de administración y consolidación. Un defecto real (arreglos anidados mostrados como `[object HTMLLabelElement]`) se encontró y corrigió así. NO se probó en un Android real ni la cámara: está en la lista manual del README.

## DECISIONES SIN CONFIRMAR
1. **Firma por prueba** (la pidió el documento); alternativa: por bloque. No se cambia sin orden de Cristian.
2. Puerto 8090 (G1 usa 8080); sesión 10 h; foto 8 MB; firma 200 KB; respaldo cada 6 h; retención 30 días.
3. Cerrar un registro con pruebas sin resultado es posible con confirmación y queda anotado (`sin_resultado`).
4. El admin NO edita registros de otros (solo ve, consolida, exporta, verifica); el dueño no puede reabrir un registro cerrado.
5. Una prueba sin resultado no exige firma; con resultado, sí (firma nueva si cambia).
6. Los ejecutores no se pueden borrar (solo desactivar): el historial conserva su nombre.

## Limitaciones
- Recargar la página sin red no funciona (no hay service worker; por diseño). La cola sobrevive a recargar con red.
- Un teléfono con reloj mal puesto guarda esa hora en `ts_cliente` (el servidor sella la suya).
- Las anomalías creadas sin red se numeran al llegar al servidor (el teléfono las muestra como pendientes).
- Sin IndexedDB (modo privado) la cola funciona solo en memoria.

## Revisión (safety-reviewer sobre seguridad de la información): sin Críticos ni Altos
Corregidos: **REG-01** (cambiar el resultado exige una firma nueva, validado en servidor), **REG-02** (cambiar la clave cierra las demás sesiones del usuario), **REG-08** (`ts_cliente` validado), **REG-10** (el CSV neutraliza celdas que empiezan con `=+-@`).
Aceptados/documentados:
- REG-03 (Media): el bloqueo por intentos es por usuario; alguien en la LAN puede bloquear 15 min a `admin` repitiendo intentos fallidos. Aceptado con una red de banco de confianza; alternativa: límite por IP.
- REG-04 (Media): HTTP plano en el Wi-Fi (clave, cookie, fotos sin cifrar); la cookie no lleva `Secure` (no hay HTTPS). Mitigación: Wi-Fi dedicado del banco, firewall solo subred local (`abrir_firewall.ps1` ya limita `RemoteAddress LocalSubnet`, perfiles Privado/Dominio), nunca a internet.
- REG-05/06/07 (Bajas): un reintento posterior al cierre se muestra como rechazado; la interfaz muestra de forma optimista lo encolado (el contador de pendientes/rechazados avisa) y no hay pantalla de rechazados (solo la copia JSON); un `cliente_uuid` repetido con otro contenido se ignora (96 bits aleatorios).
- REG-09 (Baja): la cadena protege contra errores y manipulación casual, no contra quien edite el `.db` y recalcule hashes (no hay ancla externa): conviene anotar el hash final del HTML en el expediente en papel al cerrar.
- Observación: el admin conoce la clave temporal que crea; podría suplantar a un ejecutor hasta que este la cambie.
