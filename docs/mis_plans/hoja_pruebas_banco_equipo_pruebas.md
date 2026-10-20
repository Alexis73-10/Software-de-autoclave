# Hoja de pruebas de banco — equipo de pruebas

> Generado desde `docs/mis_plans/hoja_pruebas_banco/pruebas.py` (editar ahí y regenerar con `generar.py`). Versión imprimible: `hoja_pruebas_banco_equipo_pruebas.html`.

- Equipo de pruebas: autoclave de laboratorio, 2 puertas abatibles manuales, generador interno (sin DO1/DO2), sondas Cámara 1, Cámara 2, Referencia y drenaje.
- Origen: tanda 2 (P1, E7). Reúne las 11 comprobaciones manuales de `docs/informes/informe_tanda_2026-10-14.md` §5 y las de la tanda 2 (`docs/informes/tanda2/`).
- Valores de los programas de fábrica (provisionales, por validar aquí): Bowie & Dick 134 °C / 3,5 min; Instrumental 134 °C / 7 min; Instrumental 121 °C / 15 min; Líquidos 121 °C / 15 min, sin prevacío ni secado, descompresión modo 4 con contrapresión hasta 80 °C (Principal).

## Orden seguro de ejecución

1. Bloques A a D en seco, en ese orden: primero se confirma el perfil, la tarjeta y la seguridad sin energía térmica en la cámara.
2. No pasar al bloque E sin haber aprobado B-01 (paro), B-03 (NO ABRIR), B-04 (puertas) y A-04 (DO1/DO2).
3. Bloque E (ciclos normales) antes del F (fallas provocadas): las fallas se provocan solo con un ciclo normal ya aprobado.
4. F-04 (puerta en ciclo) solo durante PREVACIO, nunca con presión positiva.
5. Bloque G (Líquidos) al final y con vidrio real; detener ante cualquier ebullición o rotura.
6. Entre pruebas en operación, esperar a cámara segura (NO ABRIR apagado) antes de manipular la carga.

## Resumen

| ID | Prueba | Modo | Origen |
|---|---|---|---|
| A-01 | Instalación con el asistente QML | En seco (sin vapor) | §5.7; S1 |
| A-02 | Arranque con la tarjeta conectada: ALL_OFF | En seco (sin vapor) | §5.1 (T6) |
| A-03 | Firmware 1.0.0: versión e ID solo en Información del sistema | En seco (sin vapor) | E6; tanda 2 §1 |
| A-04 | DO1/DO2 nunca se encienden (generador interno) | En seco (sin vapor) | S1 |
| B-01 | Paro de emergencia NC: pulsar, soltar, confirmar | En seco (sin vapor) | §5.2; PF-21; U1 |
| B-02 | Paro NC: cable cortado = paro | En seco (sin vapor) | PF-21 |
| B-03 | NO ABRIR con la cámara no segura (simulado en seco) | En seco (sin vapor) | §5.2 (T4) |
| B-04 | Puertas manuales: un sensor de cerrada por puerta | En seco (sin vapor) | tanda 2; T9 |
| B-05 | Tarjeta desconectada fuera de ciclo | En seco (sin vapor) | §5.10; U4 |
| B-06 | Apagar equipo (solo pantalla 1; cualquier estado salvo ciclo) | En seco (sin vapor) | §5.8; T7; A1 (tanda 3) |
| B-07 | Apagar equipo en FALLA, con paro, sin tarjeta y con la cámara no segura | En seco (sin vapor) | A1 (tanda 3); A2 |
| C-01 | Modo sin base de datos | En seco (sin vapor) | §5.6 (T8); S3 |
| C-02 | Alarmas de la tarjeta fuera de ciclo | En seco (sin vapor) | §5.10 (T1) |
| C-03 | Corte de energía fuera de ciclo y arranque | En seco (sin vapor) | §5.1 (T6) |
| C-04 | Corte de energía abrupto: base y archivos de estado íntegros | En seco (sin vapor) | A2 (tanda 3) |
| D-01 | Roles de sensor: Principal / Referencias / No en uso | En seco (sin vapor) | §5.5 (T3, T12) |
| D-02 | Parámetros: técnico edita en PREPARADO, rechazado en ciclo | En seco (sin vapor) | §5.9 (T10, T12) |
| D-03 | Calibración con límites de plausibilidad | En seco (sin vapor) | S3a |
| D-04 | Pantallas: navegación, campana y legibilidad | En seco (sin vapor) | §5.11; U1; U2 |
| D-05 | Cambio de programa: permitido en FALLA, rechazado con algo en curso | En seco (sin vapor) | S2 |
| D-06 | Próximo mantenimiento: cálculo, registro y aviso | En seco (sin vapor) | M1 (tanda 3) |
| D-07 | Calibración y Entradas/Salidas desde el ejecutable (engrane) | En seco (sin vapor) | C1 (tanda 3); S3a |
| D-08 | Programas de usuario persistentes con el ejecutable | En seco (sin vapor) | C2 (tanda 3) |
| D-09 | Menú Principal sin la tarjeta de secado; CIC-10 indica qué hacer | En seco (sin vapor) | S4; U5 (tanda 3) |
| E-01 | Instrumental 134 completo | En operación (vapor) | §5.3 |
| E-02 | Instrumental 121 completo | En operación (vapor) | §5.3; T11 |
| E-03 | SECADO alcanza vacío con la bomba y las válvulas cerradas | En operación (vapor) | T5 §1.6 |
| E-04 | Vigilar el corte por calidad de vapor del calentamiento | En operación (vapor) | CLAUDE.md (calentamiento) |
| E-05 | NO ABRIR en las dos pantallas con la cámara caliente | En operación (vapor) | §5.2 |
| E-06 | Operador del ciclo en ticket, historial y detalle | En operación (vapor) | O1 (tanda 3) |
| F-01 | Paro de emergencia durante el ciclo | En operación (vapor) | B-01 en ciclo |
| F-02 | Pérdida de comunicación durante el ciclo | En operación (vapor) | §5.10 (T1) |
| F-03 | Corte de energía durante el ciclo | En operación (vapor) | §5.1 (T6) |
| F-04 | Puerta abierta durante el ciclo = FALLO | En operación (vapor) | tanda 2 §1 |
| G-01 | Líquidos con la sonda dentro del líquido | En operación (vapor) | §5.4; T11; HAZ-LIQ-01 |

## Bloque A. Arranque, instalación y firmware (en seco)

### A-01 — Instalación con el asistente QML

- **Modo:** En seco (sin vapor)  ·  **Origen:** §5.7; S1
- **Objetivo:** El perfil del equipo de pruebas queda con la fuente de vapor correcta y bloqueado.
- **Precondiciones:** Sin `installation_profile.json` (o apartado). Tarjeta conectada.
- **Pasos:**
  1. Arrancar el software.
  2. Verificar que la pantalla de la puerta 1 abre el asistente de instalación.
  3. Elegir tipo de equipo, tipo de puerta, fuente de vapor = Generador interno.
  4. En el paso de suministros, desmarcar las entradas que el banco NO tiene cableadas (DI9 agua del generador, DI12 presostato de vapor, etc.).
  5. Terminar y reiniciar el equipo.
- **Resultado esperado:** El perfil se escribe con `vapor_source = generator` y `locked = true`. El resumen indica si hay cerrojo. Tras reiniciar, arranca normal.
- **Criterio de aprobado/fallo:** Aprobado si `installation_profile.json` tiene `vapor_source: "generator"`, `locked: true` y las entradas de suministro coinciden con el cableado real.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### A-02 — Arranque con la tarjeta conectada: ALL_OFF

- **Modo:** En seco (sin vapor)  ·  **Origen:** §5.1 (T6)
- **Objetivo:** Al conectar con la tarjeta, todas las salidas quedan apagadas.
- **Precondiciones:** Equipo apagado, tarjeta conectada por USB.
- **Pasos:**
  1. Encender el PC y el software.
  2. Observar los LED/relés de salida de la tarjeta durante el arranque.
- **Resultado esperado:** Ninguna salida se enciende durante el arranque; la barra de arranque termina.
- **Criterio de aprobado/fallo:** Aprobado si ninguna salida se activa hasta que el equipo lo pida.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### A-03 — Firmware 1.0.0: versión e ID solo en Información del sistema

- **Modo:** En seco (sin vapor)  ·  **Origen:** E6; tanda 2 §1
- **Objetivo:** La versión y el ID de la tarjeta se ven solo en Información del sistema.
- **Precondiciones:** Tarjeta con firmware 1.0.0 conectada.
- **Pasos:**
  1. Abrir Menú Principal › Información.
  2. Revisar la preciclo y el ciclo en curso.
- **Resultado esperado:** Información muestra versión 1.0.0 y el ID único de la tarjeta, y si está emparejada. Las demás pantallas no los muestran.
- **Criterio de aprobado/fallo:** Aprobado si versión e ID son correctos y aparecen solo ahí.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### A-04 — DO1/DO2 nunca se encienden (generador interno)

- **Modo:** En seco (sin vapor)  ·  **Origen:** S1
- **Objetivo:** Con generador interno, el software no usa DO1 ni DO2.
- **Precondiciones:** Perfil con `vapor_source = generator`. Sesión de técnico.
- **Pasos:**
  1. Activar el modo prueba.
  2. Intentar encender DO1 (vapor_generador) y DO2 (vapor_caldera).
  3. Revisar el log de arranque.
- **Resultado esperado:** Ambos rechazados: "Esta salida de fuente de vapor no la usa este equipo". El log dice "salidas deshabilitadas: DO1, DO2".
- **Criterio de aprobado/fallo:** Aprobado si DO1/DO2 no se activan físicamente en ningún momento.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

## Bloque B. Seguridad en seco: paro, puertas, NO ABRIR, alarmas

### B-01 — Paro de emergencia NC: pulsar, soltar, confirmar

- **Modo:** En seco (sin vapor)  ·  **Origen:** §5.2; PF-21; U1
- **Objetivo:** El paro detiene todo, se ve en las dos pantallas y exige confirmación para el estado seguro.
- **Precondiciones:** PREPARADO, cámara fría y a presión atmosférica, sin sesión.
- **Pasos:**
  1. Pulsar el paro.
  2. Observar las dos pantallas (preciclo, menú, login).
  3. Soltar el paro.
  4. Pulsar "Confirmar y llevar a estado seguro" sin iniciar sesión.
  5. Esperar a que termine.
- **Resultado esperado:** Con paro: todas las salidas apagadas, alarma de paro en rojo, campana con insignia roja. Al soltar: aviso naranja y botón azul, insignia parpadeando. Al confirmar: "En curso…" y luego vuelve a PREPARACION/PREPARADO.
- **Criterio de aprobado/fallo:** Aprobado si el paro se ve sin buscarlo en las dos pantallas, el botón funciona sin sesión y no queda ninguna salida encendida durante el paro.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### B-02 — Paro NC: cable cortado = paro

- **Modo:** En seco (sin vapor)  ·  **Origen:** PF-21
- **Objetivo:** Con lógica invertida, un cable del paro desconectado se trata como paro.
- **Precondiciones:** PREPARADO.
- **Pasos:**
  1. Desconectar el cable de la entrada del paro (DI10) en la bornera.
  2. Reconectar.
- **Resultado esperado:** Desconectado = paro activo (igual que B-01).
- **Criterio de aprobado/fallo:** Aprobado si el cable abierto produce paro.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### B-03 — NO ABRIR con la cámara no segura (simulado en seco)

- **Modo:** En seco (sin vapor)  ·  **Origen:** §5.2 (T4)
- **Objetivo:** El aviso NO ABRIR y el bloqueo de puerta dependen de la cámara segura.
- **Precondiciones:** Cámara fría. Si es posible, calentar el sensor Principal con una fuente controlada (baño o pistola de calor) por encima de `temp_max_apertura` (100 °C; 80 °C en Líquidos).
- **Pasos:**
  1. Calentar el sensor Principal.
  2. Abrir el panel de la campana en las dos pantallas.
  3. Intentar abrir la puerta desde la UI.
  4. Dejar enfriar.
- **Resultado esperado:** Fila "NO ABRIR" con el motivo en el panel; la puerta no se abre desde la UI. Al enfriar, desaparece.
- **Criterio de aprobado/fallo:** Aprobado si nunca se permite abrir con el Principal caliente.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### B-04 — Puertas manuales: un sensor de cerrada por puerta

- **Modo:** En seco (sin vapor)  ·  **Origen:** tanda 2; T9
- **Objetivo:** Cada puerta abatible manual se lee con su único sensor de cerrada.
- **Precondiciones:** PREPARADO.
- **Pasos:**
  1. Abrir y cerrar a mano la puerta 1; luego la puerta 2.
  2. Observar el estado de cada puerta en su pantalla.
- **Resultado esperado:** Cada pantalla refleja su puerta (abierta/cerrada) sin cruzarlas. Con cualquier puerta abierta no se puede iniciar ciclo.
- **Criterio de aprobado/fallo:** Aprobado si los estados coinciden con la realidad y bloquean el inicio.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### B-05 — Tarjeta desconectada fuera de ciclo

- **Modo:** En seco (sin vapor)  ·  **Origen:** §5.10; U4
- **Objetivo:** Desconectar el USB no se confunde con un paro y deja el equipo en estado seguro.
- **Precondiciones:** PREPARADO.
- **Pasos:**
  1. Desconectar el USB de la tarjeta.
  2. Observar alarmas y campana.
  3. Reconectar.
- **Resultado esperado:** FALLA recuperable con "Tarjeta de E/S desconectada" (no "paro de emergencia"); NO ABRIR activo; sin inicio de ciclo. Al reconectar vuelve sin pedir confirmación de estado seguro (si nunca hubo paro real).
- **Criterio de aprobado/fallo:** Aprobado si no se muestra un paro falso y el equipo se recupera solo al reconectar. (Depende de U4.)
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### B-06 — Apagar equipo (solo pantalla 1; cualquier estado salvo ciclo)

- **Modo:** En seco (sin vapor)  ·  **Origen:** §5.8; T7; A1 (tanda 3)
- **Objetivo:** El apagado está disponible solo desde la puerta 1 y se permite en cualquier estado salvo ciclo en curso, con aviso si la cámara no es segura.
- **Precondiciones:** PREPARADO (luego repetir en FALLA). Instalado con el ejecutable, o `AUTOCLAVE_APAGADO_REAL=1`.
- **Pasos:**
  1. Desde la puerta 2, buscar "Apagar equipo".
  2. Desde la puerta 1, Información del equipo › Apagar equipo, cancelar en la confirmación.
  3. Iniciar un ciclo corto e intentar Apagar equipo.
  4. Cancelar el ciclo y, ya en FALLA o PREPARADO, Apagar equipo y confirmar.
- **Resultado esperado:** Puerta 2: no disponible. Puerta 1: pide confirmación; durante el ciclo, rechazado (hay que cancelar antes). Fuera de ciclo: salidas apagadas, bitácora `apagar_equipo` (estado, cámara segura, tarjeta), base cerrada y Windows se apaga.
- **Criterio de aprobado/fallo:** Aprobado si solo apaga desde la puerta 1, nunca en ciclo, y la bitácora registra el estado y la condición de la cámara.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### B-07 — Apagar equipo en FALLA, con paro, sin tarjeta y con la cámara no segura

- **Modo:** En seco (sin vapor)  ·  **Origen:** A1 (tanda 3); A2
- **Objetivo:** El personal técnico puede dejar el equipo fuera de servicio aunque haya una falla, el paro esté pulsado o no haya tarjeta; el siguiente arranque es normal.
- **Precondiciones:** Sin ciclo en curso. Probar cada condición por separado: (a) FALLA recuperable (p. ej. USB desconectado); (b) paro de emergencia pulsado; (c) tarjeta desconectada; (d) cámara no segura (si se puede, con la cámara caliente, p. ej. tras E-01).
- **Pasos:**
  1. Provocar la condición.
  2. En la puerta 1, Información del equipo › Apagar equipo.
  3. Con la cámara no segura, leer el aviso del diálogo y confirmar.
  4. Tras el apagado, volver a encender el PC y el software.
- **Resultado esperado:** Con la cámara no segura el diálogo avisa "NO ABRIR… no abra las puertas". En todos los casos el equipo se apaga. Al encender, arranca normal (estado seguro o confirmación si la cámara no es segura) sin intervención técnica.
- **Criterio de aprobado/fallo:** Aprobado si ninguna condición impide el apagado, no se abre ninguna puerta ni válvula por el apagado y el arranque siguiente es normal.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

## Bloque C. Comunicación, energía y base de datos (en seco)

### C-01 — Modo sin base de datos

- **Modo:** En seco (sin vapor)  ·  **Origen:** §5.6 (T8); S3
- **Objetivo:** Sin base, el equipo opera con respaldo JSONL, alarma y confirmación por ciclo.
- **Precondiciones:** Copia de seguridad de la base. Reemplazar la base por un archivo que no sea SQLite.
- **Pasos:**
  1. Arrancar.
  2. Verificar la marca BD_BLOQUEADA y la alarma "Operando sin base de datos".
  3. Iniciar un ciclo corto (o B&D en seco si el banco lo permite) y confirmar "Continuar sin registro".
  4. Restaurar la base y reiniciar.
- **Resultado esperado:** El ciclo pide confirmación; el ticket imprime "SIN OPERADOR / SIN BD"; calibración y parámetros bloqueados. Al restaurar, el ciclo del respaldo se reimporta.
- **Criterio de aprobado/fallo:** Aprobado si el ciclo queda en el ticket, en `data/respaldo_ciclos/` y después en la base.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### C-02 — Alarmas de la tarjeta fuera de ciclo

- **Modo:** En seco (sin vapor)  ·  **Origen:** §5.10 (T1)
- **Objetivo:** Pérdida de comunicación fuera de ciclo = FALLA recuperable.
- **Precondiciones:** PREPARADO.
- **Pasos:**
  1. Desconectar el USB en PREPARADO.
  2. Reconectar.
- **Resultado esperado:** FALLA recuperable con la causa; al reconectar vuelve a PREPARADO.
- **Criterio de aprobado/fallo:** Aprobado si se recupera sin reiniciar el software.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### C-03 — Corte de energía fuera de ciclo y arranque

- **Modo:** En seco (sin vapor)  ·  **Origen:** §5.1 (T6)
- **Objetivo:** El arranque tras un corte deja todo apagado y pide confirmación si la cámara no es segura.
- **Precondiciones:** PREPARADO.
- **Pasos:**
  1. Cortar la energía del PC y la tarjeta.
  2. Restaurar y arrancar.
- **Resultado esperado:** ALL_OFF al conectar; si la cámara no es segura, el estado seguro pide confirmación.
- **Criterio de aprobado/fallo:** Aprobado si ninguna salida se enciende sola tras el corte.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### C-04 — Corte de energía abrupto: base y archivos de estado íntegros

- **Modo:** En seco (sin vapor)  ·  **Origen:** A2 (tanda 3)
- **Objetivo:** Sin UPS, un corte (incluso mientras se escribe) no daña la base ni los archivos de estado.
- **Precondiciones:** PREPARADO, con al menos un ciclo en el historial. Copia de seguridad de `data/`.
- **Pasos:**
  1. Cortar la energía del PC con el interruptor (sin apagar), durante una calibración o un cambio de parámetro.
  2. Restaurar y arrancar.
  3. Revisar Historial, la calibración y `data/` (sin archivos `.tmp` pendientes).
- **Resultado esperado:** Arranca sin avisos de base corrupta; el historial está completo hasta el último ciclo cerrado; la calibración y los parámetros están íntegros (la versión anterior o la nueva, nunca truncados).
- **Criterio de aprobado/fallo:** Aprobado si la base abre (sin BD_BLOQUEADA), la calibración se lee y el contador de ciclos sigue consecutivo.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

## Bloque D. Sensores, parámetros y pantallas (en seco)

### D-01 — Roles de sensor: Principal / Referencias / No en uso

- **Modo:** En seco (sin vapor)  ·  **Origen:** §5.5 (T3, T12)
- **Objetivo:** La asignación de roles se guarda y un sensor en uso sin lectura impide iniciar.
- **Precondiciones:** Sesión de técnico, PREPARADO.
- **Pasos:**
  1. OPCIONES › Parámetros del ciclo › Sensores de temperatura: poner Cámara 2 como Referencia en Instrumental 121.
  2. Desconectar la sonda Cámara 2.
  3. Intentar iniciar Instrumental 121.
  4. Dejar Cámara 2 en No en uso y volver a intentar.
- **Resultado esperado:** Con Cámara 2 en uso y sin lectura: inicio rechazado. En No en uso: no genera alarma ni bloquea.
- **Criterio de aprobado/fallo:** Aprobado si el inicio se bloquea solo cuando el sensor está en uso.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### D-02 — Parámetros: técnico edita en PREPARADO, rechazado en ciclo

- **Modo:** En seco (sin vapor)  ·  **Origen:** §5.9 (T10, T12)
- **Objetivo:** La edición queda auditada y se rechaza durante un ciclo.
- **Precondiciones:** Sesión de técnico.
- **Pasos:**
  1. Editar un parámetro en PREPARADO y guardar.
  2. Iniciar un ciclo e intentar editar.
- **Resultado esperado:** En PREPARADO se guarda y queda la última modificación; en ciclo, rechazado.
- **Criterio de aprobado/fallo:** Aprobado si ambos comportamientos se cumplen.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### D-03 — Calibración con límites de plausibilidad

- **Modo:** En seco (sin vapor)  ·  **Origen:** S3a
- **Objetivo:** Una calibración imposible se rechaza; una corrección grande pide confirmación.
- **Precondiciones:** Sesión de técnico. Patrón de temperatura y de presión.
- **Pasos:**
  1. Calibrar temp_camara con dos puntos normales (corrección < 5 °C).
  2. Intentar una corrección de 20 °C.
- **Resultado esperado:** La primera se aplica y se audita; la segunda se rechaza como no plausible.
- **Criterio de aprobado/fallo:** Aprobado si no se puede guardar una calibración absurda. (Depende de S3a.)
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### D-04 — Pantallas: navegación, campana y legibilidad

- **Modo:** En seco (sin vapor)  ·  **Origen:** §5.11; U1; U2
- **Objetivo:** La navegación es uniforme y los textos y áreas táctiles son usables en el equipo real.
- **Precondiciones:** Las dos pantallas encendidas.
- **Pasos:**
  1. Preciclo → Menú → Iniciar sesión → OPCIONES y volver con Atrás paso a paso; luego con Home de un toque.
  2. Abrir la campana con alarmas activas.
  3. Salir con Home con sesión abierta y esperar 5 min sin tocar pantallas con sesión.
  4. Revisar tamaño de textos y botones (avisos, login sin BD, asistente, Opciones).
- **Resultado esperado:** Atrás regresa a la anterior sin cerrar sesión; Home a la principal; la sesión vence a los 5 min aunque se use la preciclo.
- **Criterio de aprobado/fallo:** Aprobado si no hay pantallas sin salida ni textos/botones inutilizables.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### D-05 — Cambio de programa: permitido en FALLA, rechazado con algo en curso

- **Modo:** En seco (sin vapor)  ·  **Origen:** S2
- **Objetivo:** El cambio de programa sin sesión sigue la decisión 2 y queda en la bitácora.
- **Precondiciones:** Equipo en FALLA (p. ej. tras C-02).
- **Pasos:**
  1. Cambiar de programa sin sesión.
  2. Pulsar el paro e intentar cambiar.
- **Resultado esperado:** En FALLA se acepta; con paro (o estado seguro pendiente) se rechaza. Ambos quedan en `audit_log`.
- **Criterio de aprobado/fallo:** Aprobado si la bitácora tiene `PROGRAMA_SELECCIONADO` y `PROGRAMA_SELECCION_RECHAZADA`.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### D-06 — Próximo mantenimiento: cálculo, registro y aviso

- **Modo:** En seco (sin vapor)  ·  **Origen:** M1 (tanda 3)
- **Objetivo:** El próximo mantenimiento se calcula desde la instalación, se registra y nunca bloquea un ciclo.
- **Precondiciones:** Sesión de técnico. Intervalo por defecto PROVISIONAL (180 días): confirmar o cambiarlo con `PUT /maintenance/config`.
- **Pasos:**
  1. Ver Menú Principal: tarjeta Próximo mantenimiento, su ventana e Información del equipo.
  2. OPCIONES › Mantenimiento: Registrar mantenimiento realizado (preventivo).
  3. Con `intervalo_dias` muy bajo (p. ej. 1) y el reloj adelantado, comprobar "VENCIDO" y el aviso en la campana; iniciar un ciclo.
  4. Con el reloj anterior a la instalación, abrir la ventana de mantenimiento.
- **Resultado esperado:** Fecha = instalación + intervalo; tras registrar, la base es hoy. Vencido: aviso SIS-04 en la campana y el ciclo se inicia igual. Reloj anterior a la instalación: "—" (no un valor falso) y el registro se rechaza.
- **Criterio de aprobado/fallo:** Aprobado si nunca se bloquea un ciclo por el mantenimiento y no se muestra una fecha falsa. Anotar los intervalos definitivos que Cristian apruebe.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### D-07 — Calibración y Entradas/Salidas desde el ejecutable (engrane)

- **Modo:** En seco (sin vapor)  ·  **Origen:** C1 (tanda 3); S3a
- **Objetivo:** El menú de ajustes (PySide) abre con el ejecutable, se autentica con el backend y respeta roles y plausibilidad.
- **Precondiciones:** Ejecutable instalado. Usuario técnico e ingeniero. Patrón de temperatura.
- **Pasos:**
  1. Tocar el engrane; iniciar sesión en el menú de ajustes (técnico).
  2. Entradas/Salidas › Temperaturas › calibrar con dos puntos normales; luego una corrección de 20 °C; luego una grande confirmable.
  3. Modo prueba: encender una salida segura; cerrar la ventana con "✕ Salir".
  4. Iniciar un ciclo e intentar abrir calibración/modo prueba.
- **Resultado esperado:** Abre sin error (si no abre: revisar `scipy` en el spec). Calibración normal se guarda y audita; la absurda se rechaza con el motivo (no como fallo de conexión); la grande pide confirmación explícita. Al salir, el modo prueba termina. En ciclo, rechazado.
- **Criterio de aprobado/fallo:** Aprobado si ninguna escritura es posible sin sesión ni en ciclo y los rechazos muestran el motivo real.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### D-08 — Programas de usuario persistentes con el ejecutable

- **Modo:** En seco (sin vapor)  ·  **Origen:** C2 (tanda 3)
- **Objetivo:** Lo que el técnico edita en los programas de usuario no se pierde al cerrar ni al actualizar.
- **Precondiciones:** Ejecutable instalado en Archivos de programa. Sesión de técnico.
- **Pasos:**
  1. Editar un parámetro de un programa de usuario y cerrar el software.
  2. Reabrir y comprobar el valor.
  3. Reemplazar la carpeta del programa por una versión nueva y comprobar de nuevo.
  4. Dañar a propósito un archivo de usuario (`%ProgramData%\Especifika\Autoclave\programa\autoclave\cycles\user\*.json`) y reiniciar.
- **Resultado esperado:** El valor editado se conserva tras cerrar y tras actualizar; `factory` es solo lectura. Con el archivo dañado, aviso de arranque y se usa el programa de fábrica (nunca un ciclo inválido).
- **Criterio de aprobado/fallo:** Aprobado si no se pierde ninguna edición y un programa dañado jamás corre.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### D-09 — Menú Principal sin la tarjeta de secado; CIC-10 indica qué hacer

- **Modo:** En seco (sin vapor)  ·  **Origen:** S4; U5 (tanda 3)
- **Objetivo:** La tarjeta "Tiempo adicional de secado" ya no existe, y un estado seguro detenido indica cómo recuperarlo.
- **Precondiciones:** Equipo con el estado seguro detenido por el Principal sin lectura (desconectar la sonda Principal tras un ciclo en operación, o simulador).
- **Pasos:**
  1. Abrir el Menú Principal y revisar la fila de Reportes e Información (iconos incluidos).
  2. Con el estado seguro detenido, abrir la campana: leer el aviso y pulsar "Asignar sonda Principal".
  3. En OPCIONES › Parámetros del ciclo › Sensores, asignar otra sonda con lectura como Principal.
- **Resultado esperado:** Reportes e Información a mitad de ancho cada una, con iconos. El aviso dice "Revise la sonda Principal o asigne otra…"; NO ABRIR sigue vigente. Con otra sonda con lectura y no más fría que las demás, el protocolo continúa; si es más fría, sigue detenido.
- **Criterio de aprobado/fallo:** Aprobado si no hay ninguna forma de declarar la cámara segura a mano y el cambio de sonda solo libera con una lectura segura.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

## Bloque E. Ciclos de sólidos (en operación)

### E-01 — Instrumental 134 completo

- **Modo:** En operación (vapor)  ·  **Origen:** §5.3
- **Objetivo:** Un ciclo de sólidos a 134 °C / 7 min termina COMPLETADO con el ticket correcto.
- **Precondiciones:** PREPARADO, chaqueta en banda, puertas cerradas, carga de prueba.
- **Pasos:**
  1. Seleccionar Instrumental 134 e iniciar.
  2. Observar las fases en la pantalla de ciclo en curso.
  3. Al terminar, revisar el ticket.
  4. Abrir la puerta de descarga.
- **Resultado esperado:** Fases: PRECALENTAMIENTO, PREVACIO, CALENTAMIENTO, ESTERILIZACION, DESCOMPRESION, SECADO. COMPLETADO. El ticket muestra la temperatura del Principal. La puerta solo se habilita con la cámara segura.
- **Criterio de aprobado/fallo:** Aprobado si el resultado es COMPLETADO, las curvas son coherentes y la puerta no se pudo abrir antes de la cámara segura.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### E-02 — Instrumental 121 completo

- **Modo:** En operación (vapor)  ·  **Origen:** §5.3; T11
- **Objetivo:** Un ciclo de sólidos a 121 °C / 15 min termina COMPLETADO.
- **Precondiciones:** Como E-01.
- **Pasos:**
  1. Seleccionar Instrumental 121 e iniciar.
  2. Revisar fases, ticket y apertura.
- **Resultado esperado:** Como E-01, con meseta de 15 min a 121 °C.
- **Criterio de aprobado/fallo:** Aprobado si COMPLETADO y coherente.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### E-03 — SECADO alcanza vacío con la bomba y las válvulas cerradas

- **Modo:** En operación (vapor)  ·  **Origen:** T5 §1.6
- **Objetivo:** SECADO (modos 1/2) llega a `atm − rango_presion_atm` dentro de `timeout_pulso`.
- **Precondiciones:** Ciclo con SECADO modo 1 (p. ej. Instrumental 121 o Bowie & Dick).
- **Pasos:**
  1. Durante SECADO, anotar la presión mínima alcanzada y el tiempo.
  2. Verificar que rápida, lenta y chaqueta están cerradas.
  3. Repetir con la bomba desconectada (solo si es seguro).
- **Resultado esperado:** Con bomba: presión bajo ≈ atm − rango (≈70 kPa con atm 75) en < 180 s. Sin bomba: FALLO de SECADO a los `timeout_pulso` s.
- **Criterio de aprobado/fallo:** Aprobado si se alcanza el vacío con bomba y falla sin ella. Avisar si esas válvulas eran necesarias durante el secado.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### E-04 — Vigilar el corte por calidad de vapor del calentamiento

- **Modo:** En operación (vapor)  ·  **Origen:** CLAUDE.md (calentamiento)
- **Objetivo:** El corte "97 % del objetivo sin vapor saturado" no oscila indefinidamente.
- **Precondiciones:** Ciclo de 134 o 121.
- **Pasos:**
  1. Durante CALENTAMIENTO, registrar temperatura, presión y estado de `vapor_camara` cada 5 s en el tramo final.
  2. Comparar presión con P_sat(T).
- **Resultado esperado:** El vapor no queda oscilando entre el 97 % y el objetivo; la transición a ESTABLE/ESTERILIZACION ocurre.
- **Criterio de aprobado/fallo:** Aprobado si no hay oscilación sostenida (> 2 min) cerca del 97 %. Anotar si la sonda es rápida o hay fugas.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### E-05 — NO ABRIR en las dos pantallas con la cámara caliente

- **Modo:** En operación (vapor)  ·  **Origen:** §5.2
- **Objetivo:** Tras un ciclo, ambas pantallas muestran NO ABRIR hasta que la cámara es segura.
- **Precondiciones:** Fin de E-01 o E-02, antes de abrir.
- **Pasos:**
  1. Abrir la campana en las dos pantallas.
  2. Intentar abrir la puerta antes de la cámara segura.
- **Resultado esperado:** NO ABRIR con el motivo en ambas; apertura rechazada hasta cámara segura.
- **Criterio de aprobado/fallo:** Aprobado si no se abre antes de tiempo en ninguna puerta.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### E-06 — Operador del ciclo en ticket, historial y detalle

- **Modo:** En operación (vapor)  ·  **Origen:** O1 (tanda 3)
- **Objetivo:** El usuario con sesión que inicia el ciclo queda registrado.
- **Precondiciones:** Dos ciclos cortos: uno con sesión iniciada en la pantalla (Iniciar sesión) y otro sin sesión.
- **Pasos:**
  1. Con sesión, iniciar un ciclo y dejarlo terminar.
  2. Sin sesión, iniciar otro.
  3. Revisar el ticket impreso, Último ciclo, Historial y la reimpresión.
- **Resultado esperado:** El ciclo con sesión muestra `Operador: <usuario>` en el ticket y el operador en el detalle; el otro deja la línea para firmar y "—". Los ciclos antiguos siguen mostrándose.
- **Criterio de aprobado/fallo:** Aprobado si ambos casos coinciden entre ticket, historial y detalle.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

## Bloque F. Fallas durante el ciclo (en operación)

### F-01 — Paro de emergencia durante el ciclo

- **Modo:** En operación (vapor)  ·  **Origen:** B-01 en ciclo
- **Objetivo:** El paro en ciclo aborta, apaga salidas y lleva a estado seguro tras confirmar.
- **Precondiciones:** Ciclo en ESTERILIZACION.
- **Pasos:**
  1. Pulsar el paro.
  2. Esperar 30 s.
  3. Soltar y confirmar el estado seguro.
- **Resultado esperado:** Salidas apagadas al instante; resultado EMERGENCIA; tras confirmar, el protocolo ventea y enfría; NO ABRIR hasta cámara segura.
- **Criterio de aprobado/fallo:** Aprobado si ninguna salida queda encendida con el paro y la cámara llega a segura.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### F-02 — Pérdida de comunicación durante el ciclo

- **Modo:** En operación (vapor)  ·  **Origen:** §5.10 (T1)
- **Objetivo:** Desconectar la tarjeta en ciclo da COM-03 y la tarjeta queda en ALL_OFF.
- **Precondiciones:** Ciclo en CALENTAMIENTO.
- **Pasos:**
  1. Desconectar el USB 5 s.
  2. Reconectar.
  3. Revisar alarmas y resultado.
- **Resultado esperado:** COM-03 con su causa; el ciclo termina en FALLO_IO; la tarjeta apaga salidas por su watchdog; al reconectar, estado seguro.
- **Criterio de aprobado/fallo:** Aprobado si las salidas se apagan sin el PC y el ciclo no sigue "a ciegas".
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### F-03 — Corte de energía durante el ciclo

- **Modo:** En operación (vapor)  ·  **Origen:** §5.1 (T6)
- **Objetivo:** Un ciclo interrumpido por corte queda como INTERRUMPIDO y el arranque es seguro.
- **Precondiciones:** Ciclo en ESTERILIZACION.
- **Pasos:**
  1. Cortar la energía (PC y tarjeta).
  2. Restaurar y arrancar.
  3. Revisar el historial y el ticket.
- **Resultado esperado:** El ciclo aparece como INTERRUMPIDO; ALL_OFF al conectar; con cámara no segura, pide confirmación de estado seguro.
- **Criterio de aprobado/fallo:** Aprobado si nada se enciende solo y el registro queda INTERRUMPIDO.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### F-04 — Puerta abierta durante el ciclo = FALLO

- **Modo:** En operación (vapor)  ·  **Origen:** tanda 2 §1
- **Objetivo:** Con puertas manuales, perder el sensor de cerrada en ciclo provoca FALLO.
- **Precondiciones:** Ciclo en PREVACIO (presión baja, seguro de simular). NO hacerlo con presión positiva.
- **Pasos:**
  1. Desconectar el cable del sensor de cerrada de la puerta 1 (simula puerta abierta).
- **Resultado esperado:** FALLO del ciclo con el motivo de puerta; protocolo de fallo.
- **Criterio de aprobado/fallo:** Aprobado si el ciclo falla de inmediato (debounce).
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

## Bloque G. Líquidos (en operación, al final)

### G-01 — Líquidos con la sonda dentro del líquido

- **Modo:** En operación (vapor)  ·  **Origen:** §5.4; T11; HAZ-LIQ-01
- **Objetivo:** El programa Líquidos (121 °C / 15 min, sin prevacío ni secado) enfría con contrapresión hasta 80 °C antes de la rápida.
- **Precondiciones:** Frascos de vidrio con agua, volumen conocido; sonda flexible Principal (Cámara 1) DENTRO del líquido del frasco de mayor volumen; aire comprimido conectado.
- **Pasos:**
  1. Seleccionar Líquidos e iniciar.
  2. Verificar que no hay prevacío.
  3. Registrar temperatura del Principal y presión durante el enfriamiento.
  4. Verificar que la rápida (despresurización final) solo actúa con el Principal ≤ 80 °C.
  5. Al terminar, revisar que ningún frasco hirvió o se rompió.
- **Resultado esperado:** Esterilización con el Principal en 121 °C; enfriamiento con contrapresión (≈250 kPa); despresurización final solo ≤ 80 °C; sin secado; apertura solo ≤ 80 °C.
- **Criterio de aprobado/fallo:** Aprobado si no hay ebullición/rotura y la secuencia respeta 80 °C. Registrar el aire residual sin prevacío (diferencia T vs P_sat al inicio de la meseta).
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

## Registros que se deben conservar (expediente IEC 62304)

- Esta hoja firmada (cada prueba con valor observado, resultado y firma).
- `installation_profile.json` instalado (copia) y fecha de instalación.
- Exportación de `audit_log` y del historial de ciclos de la sesión de pruebas (base `data/` o respaldo JSONL de `data/respaldo_ciclos/`).
- Tickets impresos (o PDF) de cada ciclo E-01, E-02, E-03, E-06, F-01, F-02, F-03, G-01.
- Gráficas de cada ciclo (captura de la pantalla de ciclo en curso o del Historial).
- Log del backend (`logs/`) del día de pruebas.
- Versión del software (commit) y del firmware (Información del sistema) usados.
- Certificados de calibración de los patrones de temperatura y presión usados.
- Lista de desviaciones/no conformidades encontradas, con su informe de problema (IEC 62304 §9).
