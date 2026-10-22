# C2 — Correo a direcciones escritas a mano (tanda 7)

Rama: `tanda-7-c2` (desde `e8e42d7`). Fallo reportado por Cristian (pendiente (a) de la tanda 6): a una dirección escrita a mano no llega nada, aunque el software diga que se envió.

## 1. Causa raíz (con evidencia)

**La causa no estaba en el SMTP: estaba en la pantalla.** `SelectorDestino.qml` abría el teclado en pantalla así:

```qml
raiz.teclado?.abrirAlfanumerico(titulo, "", 80, false,
    function (valor) { if (valor !== "") raiz.elegido(valor) })
```

Pero `PanelTeclado.qml` usa ese callback para la **escritura en vivo**: lo llama en **cada tecla** (`Connections { target: alfanumerico.controlador; function onTextoChanged() { raiz._comprometerAlfanumerico() } }`), no solo al Confirmar. Entonces cada tecla emitía `elegido(texto_parcial)` y eso disparaba `AccionesCiclos.enviarCorreo(ids, texto_parcial)`:

1. Mientras la dirección no tenía forma válida ("J", "Ju", … "Juan@gmail."), el puente respondía "El correo de destino no es válido" y quedaba libre.
2. En la primera dirección parcial con forma válida, **`Juan@gmail.c`**, el puente arrancaba el envío de verdad (PDF + SMTP, varios segundos).
3. Las teclas que seguían ("o", "m") y el propio Confirmar llegaban con la acción **ocupada**, y `_empezar()` las descartaba sin decir nada.
4. El relay (Gmail) acepta `RCPT TO:<Juan@gmail.c>` y después devuelve el rebote al remitente, así que la pantalla mostraba en verde **"Se enviaron 1 ciclo(s) a Juan@gmail.c"**. La dirección completa nunca se enviaba.

Evidencia 1 — prueba QML (`tests/test_c2_selector_correo_manual_qml.py`) con el código anterior: al escribir `juan@gmail.com` y luego Cancelar, el selector emitió `elegido` 14 veces:

```
['J', 'Ju', 'Jua', 'Juan', 'Juan@', 'Juan@g', 'Juan@gm', 'Juan@gma', 'Juan@gmai',
 'Juan@gmail', 'Juan@gmail.', 'Juan@gmail.c', 'Juan@gmail.co', 'Juan@gmail.com']
```

(Cancelar no deshacía nada: el envío ya había salido.)

Evidencia 2 — script de reproducción de punta a punta con el **código anterior** (el puente `AccionesCiclos` real con su hilo de trabajo, el `smtplib` real y el SMTP falso local de `tests/smtp_falso.py`, sin red). Se simulan las teclas a 150 ms y un PDF de 2 s, como en el equipo:

```
RCPT TO recibidos por el relay: ['Juan@gmail.c']
Entregados: [['Juan@gmail.c']]
Avisos en pantalla:
   ERR El correo de destino no es válido      (x11, una por tecla)
   OK  Se enviaron 1 ciclo(s) a Juan@gmail.c
```

Con un PDF más rápido (0,4 s), el relay recibió las dos direcciones, `Juan@gmail.c` y `Juan@gmail.com`: a veces el Confirmar entraba cuando la acción ya estaba libre. Eso explica por qué el fallo era intermitente.

**Causas secundarias encontradas (no provocaban este fallo, pero se corrigieron porque la etapa lo pide):**
- `correo.enviar` ignoraba lo que devuelve `send_message`: con varios destinatarios, `smtplib` **no lanza excepción** si el relay acepta al menos uno y devuelve en silencio el dict de rechazados. Hoy no pasaba porque siempre se enviaba a una sola dirección, pero rompía en cuanto se enviara a varias.
- El mensaje de "enviado" se armaba con la dirección pedida, no con lo que el relay aceptó.
- El envío no quedaba en la bitácora.
- Cabecera `To` frente a envelope: con una sola dirección eran iguales. Ahora el envelope se pasa explícito (`to_addrs`).

Las vistas PySide (`views/ciclos.py`, `_email_dialog.py`) usan un `QLineEdit` (sin escritura en vivo) y `sendmail` con una sola dirección, que lanza `SMTPRecipientsRefused` si la rechazan. No tienen este fallo y no se tocaron. Son código heredado: `_email_dialog.py` no tiene llamador y `views/ciclos.py` solo lo usa la ventana PySide.

## 2. Corrección

| Parte | Archivo | Qué cambia |
|---|---|---|
| Pantalla | `ui_qml/qml/Componentes/SelectorDestino.qml` | El callback de escritura en vivo solo **guarda** el texto. Al Confirmar (o al Ocultar con texto) se pasa a un paso de confirmación: muestra la dirección, avisa si el formato no es válido (los botones de enviar quedan deshabilitados), aclara que la dirección no se guarda y ofrece **"Enviar solo a esta dirección"**, **"Enviar a esta y a los guardados"** (si hay guardados) y **"Corregir"**. Cancelar en el teclado no elige nada. Opción nueva **"Todos los guardados"** (si hay más de uno). `elegido` lleva una o varias direcciones separadas por coma. `MenuPrincipal.qml` no cambia. |
| Envío | `ui_qml/exportacion/correo.py` | `separar_destinos()` (quita espacios, vacías y repetidas). `armar_mensaje()` acepta una lista. `enviar()` pasa el envelope explícito y devuelve `ResultadoEnvio(aceptados, rechazados={dirección: código SMTP})`. Si el relay rechaza a todos, devuelve un resultado sin aceptados en vez de lanzar. No guarda los textos del servidor. |
| Puente | `ui_qml/bridge/acciones_ciclos.py` | Valida **todas** las direcciones antes de generar nada. Si hay una mal escrita, no envía a ninguna y el aviso la nombra. El tope es 11 direcciones (10 guardadas + 1 a mano). El mensaje se arma con las direcciones **aceptadas**. Con rechazo parcial, el aviso nombra las rechazadas y queda como no exitoso (rojo). Con rechazo total, o si no hubo respuesta por destinatario, nunca dice "enviado". Aplica a ciclos, resumen y consolidado. La dirección escrita a mano **no** se escribe en ningún archivo de configuración. |
| Bitácora | `backend/server.py` (`POST /email/sent`), `core/runtime/bitacora.py` | Evento nuevo `correo_enviado` en `audit_log`. `valor_nuevo` lleva el resultado y las direcciones, que es lo que muestra la pantalla de Bitácora ("envió un correo desde Historial o Reportes: resultado=…, destinatarios=[…]"). El `detalle` lleva tipo, destinatarios, manuales, ciclos, aceptados, rechazados (código) y resultado (`enviado` / `parcial` / `rechazado` / `error_conexion` / `error_autenticacion` / `sin_confirmacion`). Nunca lleva la contraseña ni textos de excepción. El cuerpo se valida a mano (campos extra prohibidos, largos acotados) para que un 422 no repita lo recibido. Si el backend no responde, el resultado del envío no cambia y queda en el log de texto. Una dirección inválida no llega a ser un intento, así que no se registra. |
| Correo de prueba | `backend/server.py` (`_enviar_correo`) | Como `correo.enviar` ya no lanza con rechazo total, aquí se convierte en `SMTPRecipientsRefused`. Así `/email/test` sigue contando ese caso como fallido. |
| Arnés | `ui_qml/historial_ejemplo.py` | `enviar_ejemplo` devuelve un resultado simulado (todos aceptados). |
| Textos | `i18n/es.json`, `i18n/en.json` | `correo_c2.*` (10 claves), `bitacora.ev.correo_enviado` y `bitacora.tipo.correo_enviado`. El inglés quedó anotado como "sin revisar" en `docs/mis_plans/revision_traducciones.md`. |

## 3. Pruebas

Pruebas nuevas, todas sin red. `tests/smtp_falso.py` es un servidor SMTP falso en 127.0.0.1 que habla EHLO/MAIL/RCPT/DATA con el `smtplib` real y responde 550 a las direcciones que se le indiquen. No se instaló `aiosmtpd`.

- `tests/test_c2_correo_destinatarios.py` (10): separar direcciones, varias en `To`, una aceptada, mixtas en el envelope, rechazo parcial, rechazo total, relay caído (`OSError`), envelope explícito y que el resultado no lleve la contraseña.
- `tests/test_c2_acciones_correo_manual.py` (10), puente con el SMTP falso:
  - una guardada, todas las guardadas, la manual sola (llega y no se guarda) y mixta;
  - dirección inválida (no envía, nombra la dirección y no deja bitácora);
  - rechazo parcial (nombra la rechazada, aviso no exitoso) y rechazo total (nunca "Se envió");
  - relay caído;
  - resumen con rechazo parcial;
  - bitácora caída sin efecto en el resultado.
  - En todas se comprueba la bitácora y que no lleve la contraseña.
- `tests/test_c2_correo_bitacora_api.py` (9): `POST /email/sent` sin sesión y con sesión (anota el usuario), 5 cuerpos inválidos (incluido un campo `contrasena`) que dan 422 sin registrar ni repetir el valor, el texto del evento en es/en, y `_enviar_correo` con rechazo total.
- `tests/test_c2_selector_correo_manual_qml.py` (5), pantalla real con el teclado real:
  - escribir no elige nada; Confirmar lleva a la confirmación; "solo a esta" envía solo la manual;
  - mixta envía la manual más las guardadas;
  - una dirección inválida se avisa sin poder enviarse y "Corregir" reabre el teclado con lo escrito;
  - Cancelar no elige nada;
  - "Todos los guardados".
- Pruebas existentes ajustadas al nuevo contrato (el relay simulado devuelve qué aceptó): `test_correo_ciclos.py`, `test_acciones_ciclos_puente.py` y `test_menu_principal_pantalla_qml.py`.

Suite completa (con `PYTHONPATH=<worktree>/src`, ver problemas conocidos):
- antes: línea base de la tanda, 5020 passed / 2 skipped / 3 xfailed;
- después: 5053 passed, 2 skipped, 3 xfailed (18 min 12 s; corrida por la sesión principal el 22-oct, 06:05).

## 4. DECISIONES SIN CONFIRMAR

1. **Rechazo parcial = aviso no exitoso (rojo).**
   - Motivo: que nadie dé por enviado un correo que no le llegó a alguien.
   - Alternativa: mostrarlo en verde con la nota de las rechazadas.
   - Commit: `6f79695`.
   - Cómo revertir: en `AccionesCiclos._resultado`, devolver `True` cuando hay aceptados.
2. **Una dirección inválida bloquea todo el envío**, aunque las demás sean válidas.
   - Motivo: no enviar a medias lo que el usuario pidió sin que se entere.
   - Alternativa: enviar a las válidas y avisar de las inválidas.
   - Commit: `6f79695`.
   - Cómo revertir: `_validar_envio`.
3. **Paso de confirmación de la dirección escrita a mano** (un toque más), con "solo a esta" o "a esta y a los guardados", y opción nueva "Todos los guardados".
   - Motivo: la etapa pide "sola o junto con las guardadas, según lo que eligió el usuario", y la pantalla anterior no tenía forma de elegirlo.
   - Alternativa: casillas de selección múltiple.
   - Commit: `6a264a0`.
   - Cómo revertir: volver `SelectorDestino.qml` a `e8e42d7`, pero conservando que el callback solo guarde el texto y que se elija en `onConfirmado`.
4. **`POST /email/sent` sin sesión obligatoria.**
   - Motivo: el Menú Principal envía sin iniciar sesión, y el backend solo escucha en 127.0.0.1, igual que `/cycle/history/print`. Si hay token, se anota el usuario.
   - Alternativa: exigir sesión, pero los envíos del menú quedarían sin registrar.
   - Commit: `6f79695`.
5. **El "Ocultar" del teclado con texto escrito también lleva a la confirmación** (no envía).
   - Motivo: Ocultar "conserva lo escrito" en el resto de la app.
   - Commit: `6a264a0`.
6. **La dirección se envía con las mayúsculas tal como se escribieron.** El teclado arranca en mayúscula ("Juan@…"). La mayoría de los servidores no distinguen mayúsculas en la parte local, pero el estándar lo permite. No se cambió el teclado.

## 5. PREGUNTAS PARA CRISTIAN

- ¿El rechazo parcial debe verse en rojo (como quedó) o en verde con la nota?
- ¿El paso de confirmación de la dirección escrita a mano le sirve así, o prefiere casillas para marcar varios destinos?

## 6. PROBLEMAS CONOCIDOS PARA MAÑANA

- **En los worktrees, `python -m pytest` importa el `src` de la carpeta principal**: el paquete está instalado en modo editable apuntando ahí y el repositorio no tiene `pythonpath` en la configuración de pytest. Las pruebas de esta rama se corrieron con `PYTHONPATH=<worktree>/src`. Sin eso, una corrida desde un worktree prueba el código de la carpeta principal, no el de la rama. Lo debe tener en cuenta quien integre.
- Gmail acepta en el momento direcciones con dominios inexistentes (`@gmail.c`) y rebota después al buzón del remitente. Ningún software puede detectarlo al enviar. La confirmación visible de la dirección es la defensa. Los rebotes llegan al buzón del remitente del equipo.

## 7. Comprobaciones manuales para Cristian (en el equipo, con internet)

1. Historial → marcar un ciclo → ENVIAR POR CORREO → "Otro correo…" → escribir su correo completo. Mientras escribe no debe pasar nada.
2. Confirmar → debe verse la dirección completa, el aviso "no se agrega a los guardados" y los botones. Tocar "ENVIAR SOLO A ESTA DIRECCIÓN" → el aviso debe nombrar la dirección completa y el correo debe llegar.
3. Repetir con "ENVIAR A ESTA Y A LOS GUARDADOS" → debe llegar a todos.
4. Escribir una dirección sin ".com" → debe verse el aviso rojo y los botones de enviar atenuados; "CORREGIR" reabre el teclado.
5. OPCIONES › Conectividad: los destinatarios guardados no deben haber cambiado.
6. OPCIONES › Bitácora: debe aparecer "envió un correo desde Historial o Reportes: resultado=enviado, destinatarios=[…]" por cada envío.
7. Reportes → Resumen y Consolidado → "Otro correo…": el mismo comportamiento.
