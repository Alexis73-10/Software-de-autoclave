# O2a — Parámetros del equipo completo ★

## Qué se hizo

### Backend
- **Archivo de fábrica** `config/global_params.json` reescrito con los defectos y rangos de `planeacion_opciones.md` v4 §3.2:
  - cada entrada lleva `min`, `max` y `grupo` (submenú);
  - `temp_max_apertura` pasa de 120 a **80 °C** (techo 120);
  - `tiempo_standby` pasa de 5 a **10 min**, rango 0–60 (0 = desactivada);
  - `timeout_puerta` 5–600 s e intervalos de impresión 10–3600 s (sin 0);
  - presión de empaque 100–400 kPa y vacío de empaque 0–100 kPa;
  - nuevo `timeout_chaqueta` (60 min, 10–180), **sin conectar a la lógica**;
  - `presion_atmosferica` con `"solo_lectura": true`.
- **Eliminados** `temp_max` y `tipo_puerta`: ningún lector los usaba.
- **Erratas corregidas con alias.** `presion_admosferica` pasa a `presion_atmosferica` e `intervalo_imprecion_esterilizacion` a `intervalo_impresion_esterilizacion`.
  - `ConfigManager.get()` acepta los dos nombres.
  - Los lectores y las pruebas que usan el nombre viejo siguen funcionando.
  - Una fila guardada con la errata también se toma.
- **Tabla `system_params`** (migración **v8**; la v7 la usó I4). Guarda valor, defecto, mínimo, máximo, usuario y fecha del último cambio.
  - Al abrir la base, `ConfigManager.vincular_bd` siembra las filas que falten y toma los valores vigentes.
  - Una fila fuera de rango o de otro tipo se ignora: vale el valor de fábrica y queda registrado en el log.
  - Sin base de datos rigen los valores de fábrica y no se puede cambiar nada (503).
- **Endpoints**
  - `GET /system_params`: lista con metadatos para la pantalla.
  - `GET /global_params/{clave}`.
  - `PATCH /global_params/{clave}` con `{"valor": n}`.
  - `POST /global_params/{clave}/reset`.
  - Reglas:
    - Piden token. Técnico e ingeniero pueden; admin y operador reciben **403**.
    - Con ciclo en curso responden **409**, también al ingeniero.
    - `presion_atmosferica` responde 403 (solo la cambia O2f, con `fijar(..., permitir_solo_lectura=True)`).
    - Un valor fuera de rango o de tipo inválido responde 422.
  - Cada cambio queda en la bitácora como `param_sistema_cambio`, con el valor anterior y el nuevo.
  - `GET /global_params` devuelve una instantánea con los valores vigentes.
- **Se aplica sin reiniciar (OPC-11).** El cambio se escribe primero en la base y después en memoria, dentro de `guard_estado`.
  - Todos los lectores llaman a `config.get()` en cada uso. Ya lo hacían `ServicioPuertas`, `AdvancedDoor`, `camara_segura`, `ciclo.py`, `preparacion.py`, `protocolo_fallo.py` y `cycle_logger`.
  - El único que copiaba el valor al construirse era `preparado.tiempo_estable`, que pasa a ser una property.
  - La UI relee `/global_params` en su sondeo (suspensión).
- **Suspensión.** `minutos_standby(0)` ya no se convierte en 5: con 0, la suspensión queda desactivada. El defecto es 10.
- **Permisos de la decisión 1.9** (prevalece sobre O2a):
  - `PUT /language`: admin e ingeniero, también en ciclo.
  - `PUT /units`: solo el ingeniero y fuera de ciclo.
  - Se actualizaron las pruebas de I1 y U1.

### UI (QML)
- **`OpcionesParametrosEquipo.qml` rehecho según los mockups 3, 4 y 5:**
  - **Entrada:** 7 tarjetas (6 en rejilla de 2 columnas y "Configuración de la máquina" a lo ancho), con el texto guía.
  - **Submenú:** filas con nombre, rango y defecto en gris, y el valor vigente con su unidad.
    - Los valores pasan por `Unidades`; las brechas (clase "diferencia") se convierten sin desplazamiento.
    - En Impresión va además el interruptor de impresora (P2).
    - En Sistema, la presión atmosférica aparece en solo lectura, con la fecha y el usuario de la última calibración.
  - **Ventana de ajuste:** la misma de Parámetros del ciclo (Actual, Por defecto, Mínimo y Máximo; teclado numérico; Cancelar, Por defecto y Guardar arriba). "Por defecto" usa `POST .../reset`.
  - **Configuración de la máquina:**
    - selectores de Idioma, Temperatura y Presión, cada uno con confirmación;
    - la nota "absolutas; psi manométrico y vacío en inHg";
    - número de serie y modelo en solo lectura, leídos del perfil.
- **Permisos en la pantalla** (`permisos_opciones.motivo_parametro_equipo`, `motivo_idioma` y `motivo_unidades`):
  - el técnico ve el idioma y las unidades deshabilitados, con el motivo;
  - el admin ve todo en solo lectura (sin ">" ni ventana de ajuste) pero puede cambiar el idioma;
  - con ciclo en curso, los parámetros y las unidades quedan bloqueados.
- **Navegación:** Atrás cierra la ventana de ajuste y después sube del submenú a la entrada. Si hay un valor sin guardar, pregunta antes.
- **Cambios en `Opciones.qml`:** pasa `rol` y `estadoMaquina`, encadena `retroceder()` y suma `cambiosPendientes`. No se tocaron `Main.qml`, Preciclo, Ciclo ni `BarraInferiorMenu*`.
- **Textos nuevos en es y en:** `opciones.equipo_*`, `parametros_equipo.*` y `parametros_equipo_desc.*`.

## Pruebas
`tests/test_o2a_parametros_equipo.py` (75):
- defectos, rangos y submenús;
- eliminados y alias;
- siembra, persistencia y recarga;
- rechazos (fuera de rango, tipo, NaN, bool, solo lectura);
- fila fuera de rango y fila con errata;
- OPC-11 (`preparado`) y suspensión 0;
- **matriz por rol** de PATCH, reset, idioma y unidades;
- 401 sin token, 409 en ciclo (técnico e ingeniero) y bitácora;
- controlador (PATCH entero, reset, mensajes, matriz de motivos);
- textos es/en;
- pantalla QML offscreen por rol (7 tarjetas, ">", selectores habilitados).

## Capturas (1200×1920, offscreen)
En `capturas/`:

| Archivo | Contenido |
|---|---|
| `O2a_1_entrada.png` | Entrada |
| `O2a_2_puerta.png` | Puerta |
| `O2a_3_sistema.png` | Sistema, con la atmosférica calibrada |
| `O2a_4_ajuste_brecha.png` | Ventana de ajuste de la brecha |
| `O2a_5_maquina_ingeniero.png` | Configuración de la máquina, ingeniero |
| `O2a_6_maquina_tecnico.png` | Configuración de la máquina, técnico (deshabilitada con motivo) |
| `O2a_7_admin_puerta.png` | Puerta, admin en solo lectura |
| `O2a_8_impresion_ciclo_ingeniero.png` | Impresión, ingeniero con ciclo en curso |

## Revisión de agentes
- **timing-auditor**
  - TMG-01 (Alto): la escritura en SQLite dentro de `guard_estado` podía detener el tick hasta 10 s. **Corregido.** Ahora el cambio va en dos fases:
    1. `fijar(aplicar=False)` escribe fuera del guard.
    2. Dentro del guard solo se aplica en memoria (`aplicar_valor`).
    3. Si responde 409, `revertir_bd` deshace la escritura.
    Todo el cambio se serializa con `lock_cambios`.
  - TMG-03 (Medio): `tiempo_estable` sin valor lanzaba TypeError. **Corregido:** ahora usa el defecto de 5 s, finito y con tope.
  - TMG-04 (Bajo): la siembra se hacía dentro del lock. **Corregido:** pasa fuera.
  - TMG-02 (Medio): el controlador QML hace las llamadas síncronas en el hilo GUI, acotadas por el plazo de `sesion_backend`. **Abierto**, igual que en las demás pantallas de OPCIONES.
- **safety-reviewer**
  - SAF-01 (Alto): los valores de empaque podían quedar incoherentes con la atmosférica, y la puerta se daría por sellada sin estarlo. **Corregido** con `_incoherencia`, que es fail-closed y responde 422 `incoherente`. Las reglas:
    - `presion_empaque` ≥ atm + 20 kPa y `presion_empaque` × 0,6 > atm;
    - `vacio_empaque` ≤ atm − 10 kPa y menor que `presion_empaque`.
  - En la segunda pasada no hubo Críticos ni Altos. Sus Medios (carrera entre dos PATCH y comportamiento fail-open sin referencia) quedaron corregidos.
  - **Abiertos:**
    - SAF-02 (Medio): un técnico puede subir `temp_max_apertura` hasta 120 °C. Va como PREGUNTA.
    - SAF-03 (Medio): los respaldos `or 101.3`, `or 120` y `or 20` de los lectores no son fail-closed. Es anterior a O2a y no se tocó la lógica de puertas.
    - SAF-04 (Medio): un cambio en PREPARADO no reinicia la ventana de estabilidad.
    - SAF-05 (Bajo): los lectores siguen usando el alias.
    - SAF-06 (Bajo): un fallo de la siembra solo queda en el log.
    - TMG-01a (Bajo): un fallo de `revertir_bd` solo queda en el log.

## Integraciones pendientes
- **Main.qml:** ninguna obligatoria. La pantalla vive dentro de OPCIONES.
- **Idioma en la otra ventana.** Al cambiar el idioma, esta ventana lo aplica con `i18n.fijar_idioma`. La otra ventana QML no lo lee del backend: nadie llama a `GET /language` al arrancar ni en el sondeo. Hace falta engancharlo en el puente (`ui_bridge`/`app.py`).
- **Selectores de U1.** No había otra pantalla con selectores de idioma o unidades: U1 los tenía aquí mismo. No hace falta dejar un acceso en otra pantalla.

## PREGUNTA PARA CRISTIAN: dónde conectar `timeout_chaqueta`
Se usaría en el control de chaqueta de PREPARACION/PREPARADO (`preparado.py`, cerca de `presion_chaqueta`, línea ~138, y en el equivalente de `preparacion.py`):
- Se arma un temporizador `time.monotonic()` al encender el equipo o al entrar en PREPARACION.
- Si vence sin que `pres_chaqueta` alcance `presion_chaqueta − rango`, sale una alarma que impide iniciar ciclo (`bloquea_inicio` en el catálogo).

¿Se confirma ese punto y que la alarma sea bloqueante con despeje automático al alcanzar la presión?

## Riesgo (para `docs/riesgos/`)
- **HAZ-PAR-01:** un parámetro del equipo mal configurado (por ejemplo, una temperatura de apertura alta) puede abrir la puerta con la cámara caliente.
  - Control:
    - rangos de §3.2 validados en el backend;
    - techo de 120 °C;
    - solo técnico e ingeniero, fuera de ciclo;
    - bitácora con el valor anterior y el nuevo;
    - una fila inválida en la base se ignora.
  - Verificación: `test_o2a_*`.
- **HAZ-PAR-02:** un cambio a mitad de ciclo alteraría la lógica en curso.
  - Control: 409 en CICLO para todos los roles; el cambio se aplica dentro del guard de estado.
  - Verificación: `test_409_en_ciclo_tambien_ingeniero`.
