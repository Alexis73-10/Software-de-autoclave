# O2f — Calibración de presión atmosférica, página de prueba e impresión de ganancias ★

## Qué se hizo

### Backend
- **`core/runtime/calibracion_atm.py`** (nuevo): `CalibracionAtm`, una medición a la vez, en su propio hilo.
  - Ventana continua de 120 s con `time.monotonic()` (reloj inyectable). Toma 24 muestras de `pres_camara`, una cada 5 s.
  - Las precondiciones se vigilan en cada sondeo (0,5 s), no solo al tomar una muestra:
    - alguna puerta en `ABIERTO` (en doble puerta basta una);
    - temperatura de seguridad (sensor Principal, falla cerrada) < 80 °C;
    - fuera de CICLO;
    - datos vigentes y lecturas válidas.
  - Si se pierde una precondición, si se cancela o si el muestreo se atrasa más de un periodo (`muestreo_irregular`): **aborta**, conserva el valor anterior y **no reintenta**.
  - **DECISIÓN SIN CONFIRMAR** (criterios de la instrucción, constantes del sistema):
    - promedio entre 60 y 105 kPa abs;
    - dispersión (máx − mín) ≤ 1,5 kPa;
    - si el valor difiere más de 5 kPa del anterior, queda en `por_confirmar`.
  - **DECISIÓN SIN CONFIRMAR** (adicional, por SAF-01 del revisor): también se pide confirmación cuando no hay un valor anterior válido.
  - La confirmación vence a los 5 min (se descarta). Al confirmar se vuelven a evaluar las precondiciones (SAF-03).
  - Auditoría:
    - eventos `calibracion_atm_ok`, `calibracion_atm_abortada` y `calibracion_atm_rechazada`;
    - en cada uno: valor anterior y nuevo, usuario, número de muestras, promedio, dispersión, valor intentado e iniciador.
- **`server.py`**, sección "O2f":
  - `GET /maintenance/atm-calibration` (estado, condiciones, criterios, referencia con su fecha y usuario).
  - `POST .../start`, `.../cancel`, `.../confirm` y `.../discard`: técnico e ingeniero; admin y operador reciben 403; sin token, 401.
  - `start` responde 409 con `condicion` si falta alguna precondición, o `calibracion_en_curso` si ya hay una medición.
  - La referencia se escribe con `ConfigManager.fijar(..., permitir_solo_lectura=True, aplicar=False)` fuera de `_sm_lock`. Después se publica en memoria dentro de `bloqueo_maquina()`, solo fuera de CICLO; si no se publica, se revierte la base. La API de parámetros sigue respondiendo 403 para `presion_atmosferica`.
  - Mientras mide, `PATCH`/`reset` de `/global_params` responden 409 `calibracion_en_curso`. Se comprueba dos veces, la segunda bajo `lock_cambios`.
  - `/status` expone `calibracion_atm_en_curso`.
  - `POST /printer/test-page` y `POST /maintenance/print/calibration`:
    - permisos: técnico e ingeniero;
    - usan la cola de la impresora térmica (`_encolar_en_impresora`): 409 con ciclo en curso y 503 si la impresora no está lista;
    - auditoría `impresora_prueba` / `impresion_ganancias`.
- **`services/domain/logging/ticket_mantenimiento.py`** (nuevo):
  - Página de prueba y ganancias/compensaciones de usuario de los 8 sensores, más la presión de referencia.
  - Texto cp437, 32 columnas, es/en según el idioma vigente.
  - Se imprimen en kPa abs, sin pasar por el módulo de unidades: son datos de calibración (regla 5).

### UI (QML, mockup 10)
- **Mantenimiento**: tres entradas nuevas arriba: "Calibrar presión atmosférica", "Página de prueba de impresora" e "Imprimir ganancias y compensaciones". El contenido pasa a ser desplazable.
- **`OpcionesCalibracionAtm.qml`**:
  - condiciones con ✓, mm:ss de 02:00 y número de muestras, barra de progreso;
  - promedio, dispersión y valor anterior con su fecha;
  - recuadro de criterios y resultado con el motivo;
  - Aplicar/Descartar cuando queda por confirmar.
  - La condición de temperatura se muestra con `Unidades`; las presiones de calibración, en kPa abs.
- **Bloqueo durante la medición** (`Opciones.navegacionBloqueada`): Atrás, Inicio, Cerrar sesión y el cajón quedan deshabilitados. Solo Cancelar está activo.
- `CalibracionAtmController` consulta el estado cada 1 s mientras la pantalla está abierta.
- Textos nuevos en es/en: sección `calibracion_atm`.

## Pruebas
- `tests/test_o2f_calibracion_atm.py` (58):
  - constantes y ventana completa;
  - que no termine antes de 120 s;
  - aborto por cada precondición, sin reintento;
  - precondiciones al iniciar y caso de doble puerta;
  - cancelar y muestreo atrasado;
  - rango del promedio, dispersión y confirmación;
  - vencimiento, revalidación al confirmar y carrera de vencimiento contra aplicación (TMG-01);
  - fallo de aplicación;
  - escritura real en `system_params` y reversión en CICLO;
  - matriz por rol de las 4 órdenes y de las 2 impresiones;
  - 401, 409/503 de impresión;
  - tickets es/en en cp437.
- `tests/test_o2f_calibracion_atm_qml.py` (3): pantalla offscreen con backend doble:
  - flujo completo y bloqueo de navegación;
  - mensajes de impresión;
  - técnico en CICLO.
- `tests/opciones_qml_doble.py`: banco reutilizable de OPCIONES para O2f, O2g y O2h.

## Capturas (1200×1920, offscreen; `TANDA6_CAPTURAS=1`)
`O2f_1_mantenimiento.png`, `O2f_2_condiciones.png`, `O2f_3_midiendo.png`, `O2f_4_cancelada.png`, `O2f_5_por_confirmar.png`, `O2f_6_puerta_cerrada.png`.

En las capturas offscreen los iconos de la barra inferior no muestran el atenuado de "deshabilitado": la barra no tiene estilo para ese estado, aunque los botones sí quedan inactivos.

## Revisión de agentes
- **timing-auditor**: sin Críticos ni Altos.
  - TMG-01 (Medio): el vencimiento o un error interno podían pisar el estado APLICANDO. **Corregido**: solo `_aceptar` sale de APLICANDO; tiene prueba.
  - TMG-02 (Bajo): la lectura de `context.estado` no era coherente. **Corregido**: se toma una instantánea bajo `bloqueo_maquina()`.
  - TMG-03 (Bajo): había una ventana TOCTOU con un PATCH. **Corregido**: el inicio se hace bajo `lock_cambios` y se vuelve a comprobar dentro de `_cambiar_serializado`.
  - TMG-04 (Bajo, **abierto**): el hilo es daemon. Si el proceso se cierra entre `fijar()` y `aplicar_valor()`, la base queda con el valor nuevo sin auditoría.
  - TMG-05 (Bajo, **abierto**): GET síncrono en el hilo GUI, igual que TMG-02 de O2a.
- **safety-reviewer**: sin Críticos ni Altos.
  - SAF-01 (Medio, **parcial**): se pide confirmación sin valor anterior. Sigue abierta la deriva por calibraciones sucesivas de ≤5 kPa: falta una referencia fija por sitio. Va como PREGUNTA.
  - SAF-02 (Medio, **abierto**): "puerta abierta" depende de `estado_puertas`. Va como PREGUNTA.
  - SAF-03 (Bajo): **corregido**; al confirmar se revalidan las precondiciones.
  - SAF-04 (Bajo): **corregido**; la auditoría registra `valor_intentado`.

## PREGUNTA PARA CRISTIAN
1. **Referencia fija por sitio (SAF-01).** ¿Se agrega al perfil de instalación una presión esperada (o la altitud) y se rechaza o exige ingeniero si la calibración se aleja más de ±5 kPa? Hoy, varias calibraciones seguidas de ≤5 kPa pueden mover la referencia por todo el rango 60–105 kPa. Eso desplaza la ventana de `camara_segura` (NO ABRIR).
2. **Puerta abierta (SAF-02).** ¿`ABIERTO` viene de un sensor de posición en todos los tipos de puerta, incluida `SimpleDoor`? ¿Se exige además que la presión inicial esté cerca de la referencia vigente?
3. Si arranca un ciclo durante `por_confirmar`, hoy la medición solo se rechaza al confirmar. ¿Debe descartarse en ese momento?

## Riesgo (para `docs/riesgos/`)
- **HAZ-ATM-01**: una referencia atmosférica errónea habilita NO ABRIR con presión residual.
  - Controles: precondiciones vigiladas en toda la ventana, rango, dispersión, confirmación por diferencia o sin valor anterior, revalidación al confirmar, aplicación solo fuera de CICLO, sin edición manual y auditoría.
  - Verificación: `test_o2f_*`.
