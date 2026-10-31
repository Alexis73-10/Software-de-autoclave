# U2 — Navegación inferior uniforme

Instrucción: `instruccion_claude_code_tanda_2.md` §2 U2 y decisión 7 (cierre de sesión solo por inactividad, SAF-01).

## 1. Inventario (antes de U2)

Pila de navegación de `Main.qml` (StackView): `Reposo` en el fondo; encima, la pantalla principal (`PantallaPreciclo` o `PantallaCicloEnCurso` según el estado de la máquina); encima, Menú Principal, Login, OPCIONES, Cambio de clave o Nuevo usuario. Login se **reemplaza** por OPCIONES o por Cambio de clave al validar (no queda en la pila).

| Pantalla | Iconos de la barra inferior hoy | Qué hacen |
|---|---|---|
| Preciclo (`PantallaPreciclo.qml`) | Equipo (izq.), avatar (centro, x 550), casa (der., x 957) | Equipo: panel de información. Avatar: login u OPCIONES (`abrirConfiguracion`). Casa: emite `inicioPulsado`, que `Main.qml` **no conecta** (no hace nada). |
| Ciclo en curso (`PantallaCicloEnCurso.qml`) | Equipo, avatar (centro), CANCELAR/CONFIRMAR (der.) | Avatar: login u OPCIONES. Sin casa ni atrás (es pantalla principal). |
| Menú Principal (`MenuPrincipal.qml` + `BarraInferiorMenu.qml`) | Salir (izq., deshabilitado, `TODO(MP-03)`), casa (der.) | Salir: deshabilitado (D-12), `salirPulsado` sin conectar. Casa: `pila.pop()` (vuelve a la principal). |
| Login (`Login.qml` + `BarraInferiorMenu`) | Salir (deshabilitado), casa | Casa: `pila.pop()` — vuelve a la pantalla **anterior** (si se llegó desde el Menú, vuelve al Menú, no a la principal). |
| OPCIONES (`Opciones.qml` + `BarraInferiorMenu`) | Salir (habilitado), casa | Salir: **cierra la sesión** (con diálogo si hay cambios sin guardar) y va a la principal. Casa: principal conservando la sesión. |
| Cambio de clave (`CambioClave.qml` + `BarraInferior`) | Salir, casa | Ambos `abandonar()`: **cierran la sesión** y van a la principal. |
| Nuevo usuario (`NuevoUsuario.qml`, barra propia) | "<" arriba; Salir y casa abajo | "<": vuelve a Usuarios. Salir: **cierra la sesión** (`puente.salir()`) y va al login→principal. Casa: principal. |
| Instalación (`InstalacionVentana.qml`/`Instalacion.qml`) | Botones Atrás/Siguiente del asistente | Atrás: paso anterior del asistente. Ventana aparte, sin barra de navegación ni sesión. |

El icono "Salir" (`salir_sesion.svg`, puerta con flecha a la izquierda) es el que Cristian llama "Atrás": hoy cierra la sesión en OPCIONES, Cambio de clave y Nuevo usuario.

## 2. Tabla objetivo (después de U2)

| Pantalla | Izquierda | Centro | Derecha | Notas |
|---|---|---|---|---|
| Preciclo | Equipo | — | **Avatar** (en el lugar de la casa) | Sin Home: es la principal. Se quitó `inicioPulsado`. |
| Ciclo en curso | Equipo | Avatar | CANCELAR/CONFIRMAR | Sin cambios (es la principal; la derecha la ocupa el botón del ciclo). |
| Menú Principal | **Atrás** | — | Home | Atrás = pantalla anterior (la principal). Home = principal según el estado. |
| Login | **Atrás** | — | Home | Atrás = anterior (principal o Menú). Home = principal (antes volvía a la anterior). |
| OPCIONES | **Atrás** | — | Home | Ambos conservan la sesión. Con cambios sin guardar, piden confirmar el descarte. |
| Cambio de clave | **Atrás** | (inactivos) | Home | Abandonan el cambio obligatorio: la sesión incompleta se descarta con logout (ver D-U2-3). Deshabilitados con el cambio en vuelo. |
| Nuevo usuario | **Atrás** (= "<") | — | Home | Atrás vuelve a OPCIONES › Usuarios. |
| Instalación | Atrás/Siguiente del asistente | — | — | Sin cambios: ventana aparte y sin sesión. Atrás solo recorre los pasos. |

**Regla de Atrás** (`Main.qml`, `atras()`): `pila.pop()` si hay algo por encima de la principal; si no, `volverAPrincipal()`. La pila nunca queda sin pantalla principal.

**Regla de Home** (`volverAPrincipal()`): vacía la pila y empuja la principal que corresponde al estado (preciclo o ciclo en curso), igual que antes en OPCIONES.

## 3. Sesión (decisión 7)

- Se retiró el "Salir" de las barras: el icono `salir_sesion.svg` se reemplazó por `flecha_atras.svg`. Se quitaron `salirPulsado`, `salirHabilitado` y `TODO(MP-03)` de `BarraInferiorMenu.qml` y `MenuPrincipal.qml`.
- Código muerto eliminado:
  - `Opciones.salir()` / `_cerrarSesion()` / `sesionCerrada`;
  - `CambioClave.abandonar()` / `abandonado` (reemplazados por Atrás/Inicio);
  - `NuevoUsuario.pulsarSalir()`;
  - `NuevoUsuarioBridge.salir()` (hacía logout e iba al login).
- No queda ningún cierre manual de una sesión abierta en la UI QML. La única salida con logout es abandonar el **cambio de contraseña obligatorio**: esa sesión todavía no se completó (D-U2-3). Siguen los cierres automáticos:
  - inactividad SAF-01 (5 min);
  - standby;
  - HIBERNACION;
  - desconexión (§3.7 de T-8);
  - 401.
- **Sesión sin pantalla:** el temporizador de inactividad de `SesionVentana` corre siempre que hay sesión, sin importar la pantalla. Además, desde la revisión, **solo cuentan los toques en pantallas con token** (OPCIONES, Nuevo usuario, Cambio de clave), y llegar a una de ellas cuenta como actividad. Así, una sesión que se dejó con Home o Atrás vence a los 5 min aunque otra persona siga usando la preciclo o el ciclo en curso (`sesion_backend.py`, `_en_uso`). Pruebas:
  - `test_sesion_backend.py`: 2 nuevas;
  - `test_navegacion_sesion_qml.py`: Home en OPCIONES conserva la sesión y, con toques en la preciclo, la inactividad la cierra con logout.

## 4. Flujos de seguridad

- **Asistente de instalación:** ventana aparte (`InstalacionVentana.qml`) sin barra de navegación. Su Atrás solo cambia de paso dentro del asistente y no sale a otra pantalla. Sin cambios.
- **Confirmación de estado seguro:** vive en el panel de la campana (U1). Con paro o confirmación pendiente, el panel queda abierto y no se cierra. No se abren login ni Nuevo usuario. Atrás y Home no la alcanzan: el panel está por encima (z 200) y bloquea el toque.
- **Ciclo en curso:** al entrar o salir de CICLO, `aplicarEstadoMaquina()` vacía la pila y pone la principal correcta, como antes. Atrás desde OPCIONES durante un ciclo vuelve a la pantalla de ciclo en curso que está debajo.

## 5. Pruebas

- Nueva `tests/test_u2_navegacion_qml.py`: Menú (Atrás/Home), Login desde el Menú (Atrás → Menú, Home → preciclo sin el Menú debajo), Login desde la preciclo (Atrás deja reposo + principal), preciclo sin casa y con el avatar en su lugar, ninguna barra con Salir ni logout.
- Ajustadas a la regla nueva:
  - `test_opciones_qml.py`: Atrás conserva la sesión;
  - `test_navegacion_sesion_qml.py`: Atrás en el cambio de clave sin logout y luego la inactividad;
  - `test_main_menu_principal_qml.py`: Atrás del login → Menú;
  - `test_ui_qml_app.py`: Home recrea la principal;
  - `test_menu_principal_componentes_qml.py`: `botonAtras` sin `botonSalir`;
  - `test_cambio_clave_controller.py` y `test_nuevo_usuario_puente.py`: ya no hay logout manual.

## DECISIONES SIN CONFIRMAR

- **D-U2-1:** el icono de Atrás es `flecha_atras.svg` (ya existía en los assets), no `salir_sesion.svg`, para que no parezca "salir de la sesión". Alternativa: conservar el icono anterior con la acción nueva.
- **D-U2-2:** en el Menú Principal, Atrás y Home llevan al mismo lugar (la principal): la barra queda uniforme. Alternativa: dejar libre la celda izquierda del Menú.
- **D-U2-3:** abandonar el **cambio de contraseña obligatorio** con Atrás o Inicio descarta la sesión con logout, como antes. Esa sesión no se completó, así que no se considera un "cierre manual" (decisión 7). Si se conservara (primera versión de U2), los revisores señalaron tres problemas:
  - el avatar quedaría atado al cambio de otro usuario;
  - se perdería el descarte por desconexión;
  - un cambio en vuelo podría quedar aplicado sin saberlo.

  Alternativa: conservarla y deshabilitar solo durante el envío.
- **D-U2-5:** fuera de las pantallas con token, los toques no prolongan la sesión (SAF-01). Alternativa: pedir la contraseña al volver a entrar aunque el token siga vivo.
- **D-U2-4:** en la pantalla de ciclo en curso no se agregó Home ni Atrás: es la principal y la derecha la ocupa CANCELAR/CONFIRMAR.

## Comprobaciones manuales

1. En las dos pantallas, recorrer preciclo → Menú → Iniciar sesión → OPCIONES y volver con Atrás paso a paso, y con Home de un toque.
2. Con una sesión abierta, salir con Home y esperar 5 min sin tocar: el avatar debe pedir el login otra vez.
3. Durante un ciclo, entrar a OPCIONES (engranaje) y volver con Atrás: la pantalla de ciclo en curso.

## Revisores

**safety-reviewer:** sin Críticos.
- SAF-01 (**Alto**, la sesión dejada con Atrás/Home no vencía mientras otra persona tocara la preciclo: OPCIONES con el rol ajeno): **corregido** con la inactividad contada solo en pantallas con token (D-U2-5). Tiene pruebas.
- SAF-02 (Medio, cambio obligatorio abandonado sin logout): **corregido**, se descarta (D-U2-3).
- SAF-03 (Medio, Home con estado DESCONOCIDO iba a la preciclo durante un ciclo): **corregido**, se conserva la última principal.
- SAF-04 (Bajo, comentarios viejos): **corregido**.

**timing-auditor:** sin Críticos.
- TMG-01 (**Alto**, respuesta tardía de login o cambio de clave que reemplazaba la pantalla principal tras Atrás/Home o un cambio de estado): **corregido**, `esActual()` ignora las señales de una pantalla que ya no está arriba.
- TMG-02 (**Alto**, `irALogin` y `replace(loginComp)` con el paro activo tapaban el panel): **corregido**, con paro se va a la principal.
- TMG-03 (Medio, Atrás con el cambio de clave en vuelo): **corregido**, Atrás/Inicio deshabilitados con `control.ocupado`.
- TMG-04 (Medio): igual que SAF-03, corregido.
- TMG-05 (Bajo, `admin_menu` con `pop()` sin guardia): **corregido**, usa `atras()`.
- TMG-06 (Bajo, crear usuario bloquea la GUI hasta 5 s): anterior a U2; PENDIENTE.
- TMG-07 (Bajo, salidas forzadas descartan cambios de OPCIONES sin aviso): aceptado como salida forzada; comentarios actualizados.
