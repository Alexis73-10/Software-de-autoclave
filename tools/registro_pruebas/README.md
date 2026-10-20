# Registro de pruebas de banco (F1, tanda 3)

App web para registrar la campaña de pruebas de banco desde el teléfono (Android, Chrome) por el Wi-Fi local. FastAPI + SQLite + HTML/JS sin frameworks. Corre en el PC de Cristian; **no se compila a ejecutable**; **nunca se expone a internet**.

## Uso
1. En el PC: doble clic en `iniciar_registro.bat` (o `python tools/registro_pruebas/lanzador_registro.py`). Muestra la URL para el teléfono (`http://<ip>:8090`).
2. Primer arranque: usuario `admin` con contraseña temporal aleatoria (impresa en la consola y en `CLAVE_INICIAL_ADMIN.txt`; se pide cambiarla).
3. Una vez por PC, como administrador: `abrir_firewall.ps1` (solo TCP 8090, perfiles Privado/Dominio, solo subred local). Opcional: `instalar_inicio_automatico.ps1 -Python <pythonw.exe>`.
4. El admin crea un usuario por persona (Administración › Crear ejecutor). Cada ejecutor cambia su clave y crea SU registro de campaña.
5. Datos en `C:\ProgramData\Especifika\RegistroPruebas\` (`registro.db`, `fotos\`, `firmas\`, `exportaciones\`, `respaldos\`, `config.json`). Respaldo al arrancar y cada 6 h (API de SQLite, con verificación).
6. Salida: Exportar HTML/JSON/CSV desde el registro, o `python tools/registro_pruebas/exportar.py --registro N` (copia JSON, CSV y HTML —sin fotos grandes ni base— a `docs/informes/pruebas_banco/<fecha>/<usuario>/`; no agrega nada a git).

## Cómo funciona
- El formulario sale de `docs/mis_plans/hoja_pruebas_banco/pruebas.py` (fuente única). Al crear el registro se guarda una copia con su hash: un cambio posterior de `pruebas.py` no altera registros ya iniciados.
- Nada se sobrescribe: cada guardado es una versión inmutable (usuario, hora del SERVIDOR, hora del teléfono, motivo) con SHA-256 encadenado; fotos y firmas también entran a la cadena. Cambiar un resultado firmado exige motivo. "Verificar cadena" recalcula todo.
- Firma por prueba al marcar su resultado y firma final al cerrar (DECISIÓN SIN CONFIRMAR: alternativa, firma por bloque; no se cambia sin que Cristian lo pida).
- Sin service worker ni PWA (HTTP en la LAN no es contexto seguro): cada guardado va a una cola en IndexedDB y se envía en segundo plano con reintento; indicador "N pendientes de enviar"; "Descargar copia (JSON)" siempre disponible; aviso si se cierra con pendientes. Una vez cargada la página sigue funcionando sin red; **recargar sin red no funciona**.
- Seguridad: solo red local, sesión de 10 h (configurable), bloqueo por intentos, hash PBKDF2, límites de subida (foto 8 MB, firma 200 KB), escape de HTML (textContent), cookie HttpOnly + SameSite=Strict + cabecera `X-Registro` obligatoria en escrituras, CSP y cabeceras seguras.

## Comprobaciones manuales para Cristian (con el teléfono real)
1. **Alcance de red:** abrir `http://<ip-del-PC>:8090` desde el Android conectado al Wi-Fi del banco. Si no abre: comprobar `abrir_firewall.ps1`, que la red del PC sea "Privada" y que el punto de acceso NO aísle clientes (AP/client isolation).
2. Crear dos usuarios (uno por persona) y entrar con cada uno desde su teléfono; comprobar que cada quien solo ve su registro y el admin ve todos.
3. Llenar una prueba: casillas, valores, resultado, **tomar una foto** (cámara trasera), **firmar con el dedo**, guardar. Ver la foto en la miniatura.
4. Con guantes/manos mojadas: ¿los botones se pulsan bien? (todos ≥ 48 px).
5. Modificar un resultado ya firmado: debe pedir el motivo.
6. **Cortar el Wi-Fi a mitad** (modo avión o apagar el AP): guardar 2 pruebas → el indicador marca "2 pendientes de enviar"; intentar cerrar la pestaña → avisa; "Descargar copia (JSON)" descarga; restaurar el Wi-Fi → se envían solas (o recargar la página con red).
7. Exportar el HTML del registro y revisarlo (cabecera, resultados, valores, fotos, firmas, anomalías, hash final); verificar la cadena desde la pantalla (debe decir ÍNTEGRA).
8. Probar `exportar.py` y revisar `docs/informes/pruebas_banco/`.
