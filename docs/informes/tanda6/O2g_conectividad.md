# O2g — Conectividad

## Qué se hizo

### Backend
- **`core/runtime/estado_red.py`** (nuevo): estado de red de solo lectura.
  - Adaptadores con psutil (nombre, conectado, IPv4, velocidad).
  - Wi-Fi con `netsh wlan show interfaces` (SSID e intensidad; acepta la salida en español o en inglés).
  - Plazo de 3 s, cache de 10 s con `time.monotonic()`. Nunca lanza.
- **`core/runtime/config_correo_equipo.py`** (nuevo): interruptor de envío y destinatarios guardados en `data/correo_equipo.json`.
  - Validación: correo válido, sin duplicados, máximo 10, nombre de 40 caracteres como máximo.
  - Sin archivo rigen los destinos de `config/correo.json` (comportamiento anterior).
- **`ui_qml/exportacion/config_correo.py`**:
  - El envío del Historial toma ahora los destinatarios guardados del equipo.
  - Con el interruptor apagado, `configurado` es falso y el Historial informa "correo no configurado".
  - La contraseña queda fuera del `repr` para que no aparezca en los logs.
- **Endpoints** (`server.py`, sección "O2g"):
  - `GET /network/status` y `GET /email/config`: admin, técnico e ingeniero (operador 403, sin token 401).
    - `/email/config` devuelve remitente, servidor y puerto, y solo `contrasena_configurada` (verdadero o falso). **La contraseña nunca se devuelve.**
  - `PUT /email/config`: admin e ingeniero (técnico 403, decisión 1.9), 409 con ciclo en curso (R-01), 422 si los datos no son válidos. Bitácora `correo_configurado` con las direcciones anterior y nueva.
  - `POST /email/test`: admin e ingeniero.
    - Envía un correo de prueba a cada destinatario **guardado**, nunca a uno escrito a mano.
    - Responde 409 si el envío está desactivado, si no hay destinatarios o si falta configurar el correo, y 502 si fallaron todos los envíos.
    - El texto de la excepción SMTP no se devuelve ni se registra, porque podría contener credenciales.
    - Bitácora `correo_prueba`.
- Permisos de la UI: `permisos_opciones.motivo_destinatarios`.

### UI (mockup 11)
- **`OpcionesConectividad.qml`**:
  - Red: Wi-Fi con su señal y la IP de cada adaptador, con la nota "para cambiar la red se requiere soporte".
  - Correo: interruptor de envío, remitente, servidor y estado de la contraseña ("Configurada" / "No configurada").
  - Destinatarios con "Quitar", "+ Agregar destinatario" (teclado alfanumérico: primero el nombre, después el correo) y "Enviar correo de prueba".
- El técnico ve todo deshabilitado, con el motivo.
- Textos en es/en: sección `conectividad`.

## DECISIÓN SIN CONFIRMAR
1. **Cambiar Wi-Fi o IP desde el software queda en solo lectura.**
   - Para habilitarlo haría falta:
     - un servicio de Windows con privilegios de administrador, o una tarea programada elevada, que ejecute `netsh wlan connect` / `netsh interface ip set address`;
     - comunicación local autenticada con el backend;
     - una lista blanca de operaciones;
     - una reversión automática si se pierde la conectividad (por ejemplo, volver a la configuración anterior a los 60 s sin confirmar);
     - bitácora.
   - Riesgo: dejar el equipo sin soporte remoto (AnyDesk).
2. Los cambios de correo se rechazan con un ciclo en curso (R-01), también para el ingeniero.
3. Con el interruptor de envío apagado, el Historial no envía.

## PREGUNTA PARA CRISTIAN
- ¿El remitente y el servidor SMTP deben poder editarse desde aquí (ingeniero)? Hoy siguen en `config/correo.json`, y la contraseña en el almacén de credenciales de Windows (`python -m autoclave.ui_qml.exportacion.config_correo`).

## Pruebas
`tests/test_o2g_conectividad.py` (28):
- `netsh` en español e inglés y cache de la red;
- validación de destinatarios;
- el Historial toma los destinatarios guardados y respeta el interruptor;
- matriz por rol de lectura, escritura y prueba;
- 401, 422 y 409 en ciclo;
- la contraseña no aparece en ninguna respuesta, mensaje ni error;
- red de solo lectura (405);
- pantalla QML por rol (admin, ingeniero y técnico).

## Capturas (1200×1920, offscreen)
- `O2g_admin.png`
- `O2g_admin_prueba.png`
- `O2g_tecnico.png` (solo lectura con el motivo)

## Recordatorio (11a, sin tocar)
El correo solo llega a los destinatarios guardados. Si se escribe una dirección a mano en el Historial, no llega nada aunque el software diga que se envió.
