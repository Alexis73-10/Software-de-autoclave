# Planeación — Interfaz de doble pantalla en PC único

**Proyecto:** Software-de-autoclave — Especifika S.A.S.
**Versión:** 1.0 (borrador para revisión)
**Fecha:** 2026-08-12
**Clasificación IEC 62304:** Clase C
**Estado:** especificación de diseño. **No implementar hasta cerrar los ítems de verificación de la §14.**

---

## 1. Propósito y alcance

Define la arquitectura de la capa de presentación para el despliegue en **PC único con dos monitores táctiles verticales**, donde cada monitor representa una puerta del autoclave de doble puerta y ambos comandan el mismo backend.

### 1.1 Dentro del alcance

- Arquitectura de procesos: lanzador, backend, dos procesos de interfaz
- Resolución de identidad de puerta y vinculación determinista monitor ↔ puerta
- Elección de framework de interfaz y su justificación regulatoria
- Contrato de datos UI ↔ backend (telemetría e histórico)
- Traducción del sistema de diseño Especifika HMI v1.0.0 al stack elegido
- Estrategia de escalado del lienzo
- Gráfica de ciclo: muestreo, persistencia, decimación y re-hidratación
- Indicador de fases dinámico y representación del sub-estado AISLAMIENTO
- Teclados en pantalla
- Plan de migración desde `ui/` (tkinter) y `ui_pyside/`

### 1.2 Fuera del alcance

- Envío de reportes por red y conectividad en general → **documento propio** (ver §3, hallazgo UI-07)
- Pantalla de diagnóstico v2 para tableta o portátil externo (diferida)
- Aplicación web interna Flask de generación de códigos de activación
- Diseño gráfico de pantallas individuales (mockups) — este documento define el marco, no la maqueta
- Lógica de proceso, máquina de estados de ciclo y lógica de puertas — residen en el backend y no se modifican aquí

### 1.3 Documentos de referencia

| Documento | Uso en esta especificación |
|---|---|
| `sistema-diseno-especifika-v1.html` v1.0.0 | Sistema de diseño. Se adopta íntegro **excepto §13.1 y §15.3** |
| `tokens.json` / `tokens.css` v1.0.0 | Fuente única de color, tipografía, espaciado y movimiento |
| `DISEÑO_INTERFAZ_-P1_mockup.jpg` | Referencia visual. Requiere las correcciones de la §12 |
| `planeacion_alimentacion_camara_desde_chaqueta.md` | Origen del sub-estado AISLAMIENTO |
| `planeacion_f0.md` | Origen de la métrica F0 |

---

## 2. Registro de decisiones

| # | Decisión | Justificación |
|---|---|---|
| D-01 | Dos procesos de interfaz independientes | Aislamiento de fallos entre HMIs (hallazgo UI-02) |
| D-02 | Lanzador dedicado supervisa backend y ambas UIs; las UIs son clientes puros | Restaura la simetría entre pantallas; desacopla el componente crítico del más propenso a fallar |
| D-03 | `deployment_mode` en `installation_profile.json` + `--door N` por proceso | El perfil ya no puede contener un único `door_id` |
| D-04 | Pantallas funcionalmente simétricas | Requisito de operación |
| D-05 | Arbitraje de comandos concurrentes por orden de llegada, en el backend | La interfaz nunca arbitra |
| D-06 | Estado de la otra puerta visible pero **no operable** | Evita el 403 inexplicable; conserva la separación de responsabilidad del operador |
| D-07 | Framework: **QML / Qt Quick sobre PySide6** | Cero SOUP añadido en dispositivo Clase C; cero superficie de red |
| D-08 | Alcance visual: profundidad, sombras, degradados y transiciones. **Sin 3D en tiempo real** | Presupuesto de GPU en Intel N150 con dos paneles |
| D-09 | Orientación vertical fija en ambos monitores, rotada por el sistema operativo | Elimina la detección de orientación en tiempo de ejecución |
| D-10 | Sistema operativo: Windows | Definido por el despliegue |
| D-11 | Lienzo lógico fijo 800 × 1280 con **escalado uniforme** | Fidelidad al sistema de diseño; cero reflow |
| D-12 | Telemetría por **WebSocket a 1 Hz**; histórico por REST | Evita que la interfaz acumule estado propio |
| D-13 | Gráfica en pantalla: **sin líneas de consigna**, solo divisores de cambio de fase | Legibilidad operativa |
| D-14 | Gráfica del **reporte impreso: con líneas de consigna** | Evidencia auditable (ISO 17665) |
| D-15 | Indicador de fases **dinámico y congelado al confirmar el ciclo** | Ver D-16 |
| D-16 | Una fase omitida en marcha se marca **OMITIDA**, no desaparece | Ocultarla retroactivamente borra evidencia de proceso |
| D-17 | Objetivo táctil mínimo 48 px (9.8 mm en el panel de 12.1") | Operación sin guante, panel capacitivo |
| D-18 | Dos teclados: numérico con **coma decimal** y alfanumérico sin tildes, con `ñ` y caracteres especiales | Requisito de operación |
| D-19 | Coma decimal en toda la presentación y entrada; punto **solo** en persistencia, API y JSON | Conversión en un único punto del código |
| D-20 | Reinicio automático de UI **con registro en el log de auditoría** | Trazabilidad Clase C |
| D-21 | Tema oscuro incluido en la primera versión | Los tokens ya lo definen completo |
| D-22 | Función de red **diferida** a documento propio | Hallazgo UI-07 |
| D-23 | Muestreo de registro 1 Hz; persistencia como **blob comprimido por ciclo** | ~55 MB/año frente a ~500 MB/año con fila por muestra |
| D-24 | Reloj: **modelo A** (local autoritativo, ajuste manual autenticado y registrado) en v1 | La red está diferida |

---

## 3. Hallazgos

| ID | Severidad | Estado | Descripción |
|---|---|---|---|
| UI-01 | **Seguridad (ISO 14971)** | Mitigado en §5 | Un mapeo invertido monitor ↔ puerta hace que el operador comande la puerta equivocada. Sin realimentación física correctiva |
| UI-02 | Disponibilidad | Cerrado por D-01 | Un proceso con dos ventanas deja sin HMI a la segunda puerta si la primera falla |
| UI-03 | **Seguridad** | Mitigado en §4.4 | El cierre de la UI ejecuta `reset_outputs()` y mata el backend. Con dos pantallas, apagar una HMI apagaría un ciclo activo de la otra puerta |
| UI-04 | Bloqueante | Cerrado por D-07 | El §13.1 del sistema de diseño prescribe React/TypeScript, incompatible con la decisión de framework |
| UI-05 | Diseño | Abierto — §12 | El sistema de diseño y los mockups son mono-puerta; falta identidad de puerta, estado de la otra puerta, controles de puerta y alarma severidad 4 |
| UI-06 | Técnico | Mitigado en §7.3 | El renderizador SVG de Qt (SVG Tiny 1.2) no resuelve `currentColor` ni variables CSS |
| UI-07 | **Crítico** | **Abierto — bloquea la función de red** | La conexión a red reactiva H-03: API de accionamiento de puertas sin autenticación escuchando en todas las interfaces |
| UI-08 | Integridad de datos | Mitigado en §9.4 | Con reinicio automático de UI, la curva del ciclo no puede residir solo en memoria de la interfaz |
| C-01 | **Seguridad** | Abierto — V-05 | Todo temporizado de proceso debe usar reloj monótono. Un salto del reloj de pared corrompe la integración de F0 y los timeouts de puerta |

### 3.1 Detalle de UI-07

Con el equipo aislado, H-03 era latente: exigía acceso físico al PC. Conectado a una red corporativa, cualquier dispositivo del mismo segmento puede accionar una puerta del autoclave mediante una petición HTTP sin credenciales. Este es exactamente el peligro que fundamenta la clasificación Clase C, por un vector no mitigado.

**Condiciones previas obligatorias antes de habilitar cualquier función de red:**

1. Enlazar el servidor de control a `127.0.0.1` exclusivamente
2. Topología asimétrica: el equipo **empuja** reportes hacia afuera; nada de afuera entra al control
3. Servicio de reportes separado, autenticado y con TLS
4. Definir la regla de precedencia entre `clock_guard` y NTP (ver §11)
5. Nueva entrada en la matriz de riesgos ISO 14971
6. Evaluación de aplicabilidad de 21 CFR Part 11 para el registro de auditoría

---

## 4. Arquitectura de procesos

### 4.1 Topología

```
                    ┌──────────────────────────────┐
                    │  autoclave.launcher          │
                    │  (proceso supervisor)        │
                    └──────────────┬───────────────┘
                                   │ crea y supervisa
              ┌────────────────────┼────────────────────┐
              ▼                    ▼                    ▼
    ┌──────────────────┐  ┌────────────────┐  ┌────────────────┐
    │ autoclave.backend│  │ UI --door 1    │  │ UI --door 2    │
    │ FastAPI/uvicorn  │  │ QML, monitor A │  │ QML, monitor B │
    │ 127.0.0.1:8000   │  └───────┬────────┘  └───────┬────────┘
    │ máquina de       │          │ WS + REST         │
    │ estados, control │◄─────────┴───────────────────┘
    │ lógica de puertas│
    └────────┬─────────┘
             │ serial 115200
             ▼
      ESP32 esclavo de I/O
```

### 4.2 Responsabilidades del lanzador

`autoclave.launcher` asume todo lo que hoy hace `main.py` antes de instanciar la ventana:

1. Verificación de activación y licencia
2. Verificación de `clock_guard` (una sola vez, no por UI)
3. Arranque del backend y espera del healthcheck
4. Resolución del binding monitor ↔ puerta (§5)
5. Lanzamiento de dos procesos de UI con `--door N --screen <id>`
6. Supervisión: reinicio de una UI caída, con notificación al backend para el log de auditoría (D-20)
7. Apagado ordenado del conjunto
8. Terminación en cascada mediante Job Object de Windows

**Regla:** ninguna UI puede terminar el backend. Ninguna UI conoce la existencia de la otra como proceso.

### 4.3 Argumentos de línea de comandos de la UI

```
python -m autoclave.ui --door {1|2} --screen <screen-id> [--dev] [--scale <f>]
```

| Argumento | Descripción |
|---|---|
| `--door` | Identidad de puerta. Obligatorio. Sin valor por defecto |
| `--screen` | Identificador del monitor resuelto por el lanzador |
| `--dev` | Modo desarrollo: ventana redimensionable en lugar de pantalla completa |
| `--scale` | Factor de escala explícito, solo en modo desarrollo |

### 4.4 Separación entre cerrar la HMI y apagar el equipo (UI-03)

| Acción | Efecto actual (incorrecto) | Efecto especificado |
|---|---|---|
| Cerrar la ventana de una UI | `reset_outputs()` + `terminate()` del backend | Solo termina ese proceso de UI. El lanzador la relanza |
| "Apagar equipo" en la interfaz | Idéntico al anterior | Comando al backend, **condicionado al estado global**. Rechazado si hay un ciclo activo en cualquier puerta, con motivo mostrado al operador |

El apagado de salidas es una decisión del backend basada en el estado de la máquina, nunca un efecto secundario del ciclo de vida de una ventana.

---

## 5. Identidad de puerta y vinculación de pantalla

### 5.1 Naturaleza del riesgo (UI-01)

En la topología anterior de dos PC, la separación entre puestos de operación era **física**: el PC del lado sucio no podía comandar el lado limpio por accidente. En PC único con dos monitores, esa separación pasa a ser **una asociación en software** entre un identificador de monitor y un número de puerta.

Vías de fallo: reconexión de cables durante servicio, cambio del orden de enumeración del sistema operativo tras actualización de controlador, reemplazo de un monitor, arranque con un monitor desconectado.

Consecuencia: el operador del lado limpio abre la puerta del lado sucio creyendo que abre la suya. No existe realimentación física que corrija el error antes de que ocurra.

### 5.2 Mitigaciones (defensa en capas)

| Capa | Mitigación |
|---|---|
| M-1 | Vinculación por **identificador de hardware del monitor** (`QScreen.serialNumber()`, derivado del EDID), **nunca por índice de pantalla ni por posición** |
| M-2 | Persistencia del mapeo en `installation_profile.json`, escrito durante la puesta en marcha |
| M-3 | **Verificación en arranque:** si un identificador esperado no está presente, el lanzador **no arranca las UIs** y muestra una pantalla de error con instrucción de servicio |
| M-4 | **Identidad de puerta permanente en pantalla:** región invariante del header, no un chip secundario. Debe ser legible a 2 m |
| M-5 | Diferenciación cromática entre puertas, **secundaria y nunca única** (no puede ser la única señal: operarios con deficiencia de visión cromática) |
| M-6 | **Confirmación táctil en puesta en marcha:** el asistente solicita tocar la pantalla del lado indicado y verifica de qué monitor procede el evento |
| M-7 | Los comandos de puerta llevan `source_door`; el backend **registra en auditoría** el origen de todo comando |

### 5.3 Estructura en `installation_profile.json`

```json
{
  "deployment_mode": "single_pc_dual_screen",
  "doors": [
    { "id": 1, "role": "carga",    "screen_serial": "<EDID>", "screen_model": "FT121TMCAPIP65HBOB" },
    { "id": 2, "role": "descarga", "screen_serial": "<EDID>", "screen_model": "FT121TMCAPIP65HBOB" }
  ]
}
```

Valores admitidos de `deployment_mode`: `single_pc_single_screen`, `single_pc_dual_screen`, `dual_pc` (heredado).

### 5.4 Ítem de verificación V-UI-01

Confirmar en banco que Windows expone `QScreen.serialNumber()` **no vacío** para los paneles Faytech. Algunos controladores lo devuelven en blanco.

**Plan alternativo si es vacío:** `model()` + posición geométrica como clave compuesta, con M-6 elevado de recomendable a **obligatorio** en cada arranque, no solo en puesta en marcha.

---

## 6. Contrato UI ↔ backend

### 6.1 Principios (heredados del §13.3 del sistema de diseño)

1. **Sin lógica de proceso en la interfaz.** La UI no decide si un ciclo puede iniciarse ni si una puerta puede abrirse. Refleja el estado reportado
2. **Optimismo prohibido en acciones de proceso.** Todo comando muestra estado intermedio "Enviando…" hasta confirmación del backend. Se permite actualización optimista solo en preferencias de interfaz
3. **Frontera de confianza.** Todo mensaje entrante se valida antes de entrar al estado de la UI. Un valor fuera de rango se descarta y se registra; no se pinta
4. **Sin acumulación ilimitada.** Buffers de anillo de tamaño fijo. El panel puede estar encendido semanas

### 6.2 Telemetría — WebSocket `/ws/telemetry`, 1 Hz

```json
{
  "ts": "2026-08-12T16:00:03Z",
  "tMonotonic": 923.412,
  "cycleId": 1043,
  "cycleNumber": "03",
  "state": "RUNNING",
  "stateReason": null,
  "program": { "id": 7, "name": "Botellones vacios" },
  "phasePlan": ["PURGA","PRECALENTAMIENTO","PREVACIO","CALENTAMIENTO",
                "ESTERILIZACION","DESCOMPRESION","SECADO"],
  "phaseStatus": { "PURGA": "COMPLETADA", "PRECALENTAMIENTO": "OMITIDA",
                   "PREVACIO": "COMPLETADA", "CALENTAMIENTO": "COMPLETADA",
                   "ESTERILIZACION": "ACTIVA", "DESCOMPRESION": "PENDIENTE",
                   "SECADO": "PENDIENTE" },
  "phase": { "code": "ESTERILIZACION", "index": 4, "elapsedS": 312 },
  "isolation": { "active": true, "count": 2, "max": 5 },
  "elapsedS": 923,
  "remainingS": 900,
  "metrics": {
    "t_camara":   { "v": 121.3, "u": "C"   },
    "t_chaqueta": { "v": 124.1, "u": "C"   },
    "p_camara":   { "v": 105.2, "u": "kPa", "ref": "manometrica" },
    "f0":         { "v": 8.4,   "u": "min" }
  },
  "doors": {
    "1": { "state": "CERRADA", "moving": false, "interlock": "BLOQUEADA" },
    "2": { "state": "CERRADA", "moving": false, "interlock": "BLOQUEADA" }
  },
  "alarms": [
    { "id": "SOBREPRESION_CAMARA", "severity": 2, "ts": "...", "acked": false }
  ]
}
```

Notas:

- `phasePlan` se resuelve al confirmar el ciclo y **no cambia durante la ejecución** (D-15). Las omisiones se reflejan en `phaseStatus`, nunca eliminando la fase del plan (D-16)
- `doors` incluye **ambas** puertas. Cada UI opera la propia y muestra la otra en modo lectura (D-06)
- `p_camara.ref` es obligatorio y debe mostrarse junto al valor. La diferencia manométrica/absoluta en Bogotá es de 74.6 kPa
- `tMonotonic` acompaña a `ts` para permitir a la UI detectar saltos del reloj de pared (C-01)

### 6.3 Endpoints REST

| Método | Ruta | Uso |
|---|---|---|
| `GET` | `/status` | Healthcheck del lanzador y estado inicial |
| `GET` | `/cycle/series?from=<s>` | Re-hidratación de la curva tras reinicio de UI |
| `GET` | `/cycle/{id}/report` | Datos del reporte, incluidas las consignas (D-14) |
| `POST` | `/doors/{name}/open` | Requiere `source_door`. Sujeto a interlock del backend |
| `POST` | `/doors/{name}/close` | Requiere `source_door` |
| `POST` | `/cycle/start` | Arbitrado por orden de llegada (D-05) |
| `GET` | `/programs` | Catálogo de programas |
| `PATCH` | `/cycle/parameters` | Parámetros del ciclo activo |

### 6.4 Reconexión

Reintento con retroceso exponencial 1, 2, 4, 8, máximo 15 s. Heartbeat cada 5 s. La UI expone `connectionState` para el indicador "Sin señal".

**Regla de degradación:** perdida la conexión, la interfaz **congela** los valores mostrados, los marca visiblemente como no vigentes con su antigüedad, y **deshabilita todos los comandos de proceso**. Nunca muestra un valor obsoleto como si fuera actual.

---

## 7. Sistema de diseño → QML

### 7.1 Adopción

Se adoptan íntegros los capítulos §0–§12 y §14 del sistema de diseño. Se **descartan** §13.1 (tabla de librerías React) y §15.3 (mapeo a Tailwind). El §13.3 (reglas de arquitectura) se adopta sin cambios: es stack-agnóstico.

### 7.2 Tokens

`tokens.json` sigue siendo la **fuente única**. Un paso de compilación genera `Tokens.qml` (singleton) a partir de él.

- Prohibido editar `Tokens.qml` a mano; es un artefacto generado
- Prohibido declarar hexadecimales en cualquier componente. La regla del §0.2 se mantiene y se verifica en revisión de código
- El cambio de tema claro/oscuro conmuta la tabla activa del singleton, sin recompilar

### 7.3 Iconos (UI-06)

El renderizador SVG de Qt implementa SVG Tiny 1.2 y no resuelve `currentColor` ni variables CSS.

**Contrato de entrega al diseñador:**

| Requisito | Valor |
|---|---|
| Lienzo | `viewBox="0 0 24 24"`, sin `width`/`height` |
| Área segura | 20 × 20 px |
| Estilo | Contorno 2 px, remates y uniones redondeados |
| Trazo | **Expandido a trayectoria** |
| Color | **Monocromo puro**, sin colores literales |
| Prohibido | `<style>`, máscaras, filtros, efectos, rasterizados incrustados, metadatos de editor |
| Nombre | `icon-{nombre-kebab}-24.svg` |

**Implementación:** el componente `Icon` de QML aplica el tinte en tiempo de ejecución sobre la textura. Los dos iconos multitono autorizados se tratan aparte, rasterizados a tamaño fijo o convertidos a geometría QML nativa.

**Logotipo:** SVG con texto en curvas, cuatro variantes (blanco, color, monocromo oscuro, isotipo), **más PDF o EPS vectorial** para reportes impresos.

### 7.4 Corrección del inventario de iconos de fase

El §7.2 del sistema de diseño enumera 6 iconos de fase con nombres que no corresponden al pipeline real de 7 fases:

| Sistema de diseño | Real | Acción |
|---|---|---|
| carga/purga | **PURGA** | Renombrar |
| precalentamiento | **PRECALENTAMIENTO** | Sin cambio |
| vacío | **PREVACIO** | Renombrar |
| — | **CALENTAMIENTO** | **Icono nuevo — falta** |
| esterilización | **ESTERILIZACION** | Sin cambio |
| enfriamiento | **DESCOMPRESION** | Renombrar y **rediseñar el glifo** |
| secado | **SECADO** | Sin cambio |

**Iconos adicionales a encargar:** `AISLAMIENTO` (indicador superpuesto) y `F0` (métrica de letalidad acumulada).

### 7.5 Tipografía

Inter en formato **TTF u OTF** (Qt no consume WOFF2 en `FontLoader`), empaquetada con la aplicación. Prohibida la carga desde CDN.

Inter se distribuye bajo SIL Open Font License 1.1. **Debe registrarse en el inventario SOUP** con versión y licencia.

---

## 8. Lienzo y escalado

### 8.1 Geometría verificada

```
Faytech 12.1" @ 1280 × 800 → diagonal 1509 px / 12.1" = 124.7 PPI
Rotado a vertical: 800 × 1280 — coincide exactamente con el lienzo del sistema de diseño

--touch-min:     48 px →  9.8 mm   ✓ ≥ 9 mm sin guante
--touch-process: 64 px → 13.0 mm   ✓
```

Los supuestos A1 y A2 del §0.3 del sistema de diseño quedan **confirmados**. El panel real es mayor que el supuesto (12.1" frente a ~10"), por lo que los objetivos táctiles resultan más holgados, no más apretados.

### 8.2 Estrategia de escalado (D-11)

Lienzo lógico fijo de 800 × 1280. Un contenedor raíz aplica escalado uniforme según la geometría real, conservando la relación 5:8 con letterbox cuando la ventana no la respeta.

```
scale = min(anchoVentana / 800, altoVentana / 1280)
```

- **Producción:** pantalla completa sobre el `QScreen` resuelto. `scale = 1.0`
- **Desarrollo:** dos ventanas de 400 × 640 (`scale = 0.5`) lado a lado en un monitor horizontal. Permite probar simetría e interlock cruzado sin hardware

**Regla:** ninguna vista contiene ramas condicionales por tamaño. La UI recibe una geometría y un `door_id`, y desconoce si proceden de un monitor físico o de una ventana de desarrollo.

### 8.3 Rotación

La rotación a vertical la ejecuta el sistema operativo. La aplicación se diseña contra la geometría ya rotada.

**Se elimina** la detección de orientación en tiempo de ejecución existente (`is_portrait`, `check_orientation_changed`, el manejador `_on_configure`): con orientación fija es código muerto que solo añade rutas de fallo.

---

## 9. Gráfica de ciclo

### 9.1 Series

| Serie | Token | Eje |
|---|---|---|
| Temperatura de cámara | `--chart-series-1` | °C |
| Temperatura de camisa | `--chart-series-2` | °C |
| Presión de cámara | `--chart-series-3` | kPa |
| F0 acumulado | por asignar | min |

La temperatura de camisa es **variable de control primaria** desde el rediseño de la topología de admisión de vapor. Su presencia en la gráfica es obligatoria y debe estar correctamente rotulada.

`--chart-series-4` (consigna, trazo discontinuo) queda **sin uso en pantalla** y **se usa en el reporte impreso** (D-13, D-14).

### 9.2 Dimensionamiento

| Parámetro | Valor |
|---|---|
| Muestreo | 1 Hz uniforme |
| Ciclo mínimo (10 min) | 600 muestras/serie |
| Ciclo típico (2 h) | 7 200 muestras/serie |
| Ciclo máximo (5 h) | 18 000 muestras/serie |
| Anillo en UI | 20 000 muestras/serie |
| Memoria del anillo | ~320 KB (4 series, float32 + marca de tiempo) |

### 9.3 Decimación de render

Ancho útil del lienzo: 768 − 2 × 16 px de margen = **736 px**.

Decimación por **mínimo y máximo de cubeta**, nunca por promedio: promediar puede ocultar un pico transitorio de presión, que es justamente lo que el operador necesita ver.

- 368 cubetas × 2 puntos = 736 puntos dibujados
- Ciclo de 5 h: ~49 muestras por cubeta
- Ciclo de 10 min: sin decimación (600 < 736)

### 9.4 Persistencia y re-hidratación (UI-08)

Con reinicio automático de UI (D-20), la curva **no puede residir solo en memoria de la interfaz**: un reinicio a los 40 min de un ciclo de 90 dejaría la gráfica vacía y el operador perdería la evidencia visual del proceso en marcha.

- **El backend persiste** la serie completa del ciclo
- **La UI re-hidrata** con `GET /cycle/series` al montar la vista
- **Formato:** blob comprimido, **una fila por ciclo**

| Estrategia | Filas/año | Almacenamiento/año |
|---|---|---|
| Una fila por muestra | ~13 M | ~500 MB |
| **Blob comprimido por ciclo** | ~1 825 | **~55 MB** |

Base del cálculo: 5 ciclos/día, promedio 2 h.

### 9.5 Presupuesto de rendimiento

Heredado del §13.3: arranque a primera pantalla útil ≤ 2 s; respuesta táctil visible ≤ 100 ms; la gráfica en vivo no debe provocar redibujado de las tarjetas de métrica.

---

## 10. Indicador de fases y AISLAMIENTO

### 10.1 Pipeline

`PURGA → PRECALENTAMIENTO → PREVACIO → CALENTAMIENTO → ESTERILIZACION → DESCOMPRESION → SECADO`

### 10.2 Comportamiento dinámico

El indicador se construye a partir de `phasePlan`, resuelto al confirmar el ciclo (D-15). Las fases no aplicables al programa no se dibujan.

Estados por fase: `PENDIENTE`, `ACTIVA`, `COMPLETADA`, `OMITIDA`.

**Regla (D-16):** una fase omitida durante la ejecución se marca `OMITIDA` con tratamiento visual atenuado, pero **permanece visible**. Eliminarla del indicador en marcha alteraría la representación del proceso ante los ojos del operador y borraría evidencia.

### 10.3 AISLAMIENTO

AISLAMIENTO es un **sub-estado ortogonal**: ocurre dentro de CALENTAMIENTO y ESTERILIZACION sin interrumpirlas. La acumulación de F0 continúa durante el aislamiento — es una acción sobre la presión, no una interrupción de la esterilización.

**Prohibido representarlo como un paso más del indicador lineal.** Sería incorrecto y sugeriría al operador que la esterilización se detuvo.

Representación especificada:

- Indicador superpuesto sobre la fase activa, no un elemento del indicador de fases
- Muestra el contador de recurrencia `count / max_cierres_camara`
- Al alcanzar el máximo, se escala a la alarma `SOBREPRESION_RECURRENTE_CAMARA` con la presentación correspondiente a su severidad
- La gráfica marca los intervalos de aislamiento como banda de fondo, no como divisor de fase

---

## 11. Reloj (D-24, C-01)

### 11.1 Modelo v1 — reloj local autoritativo

- NTP deshabilitado
- Ajuste solo manual, con autenticación de administrador y registro en el log de auditoría
- `clock_guard` estricto: cualquier retroceso no autenticado es manipulación

### 11.2 Modelo futuro cuando llegue la red

- NTP contra servidor fijo configurado
- Corrección automática si el desfase es ≤ 5 s, **aplicada por deslizamiento gradual, nunca por salto**
- Desfase mayor: requiere administrador y queda registrado
- `clock_guard` tolera retrocesos acotados de origen conocido

### 11.3 Reloj monótono (C-01)

**Todo temporizado de proceso** —duración de fases, integración de F0, timeouts de apertura y cierre de puerta, debounce de AISLAMIENTO— debe usar reloj monótono.

El reloj de pared se usa **exclusivamente** para el sello de tiempo de los registros.

Justificación: F0 acumula sobre `dt`. Un `dt` negativo o un salto del reloj falsea la letalidad acumulada de forma silenciosa, sin ninguna señal para el operador.

Estado actual **no verificado** → ítem V-05.

---

## 12. Correcciones al mockup (UI-05)

### 12.1 Elementos ausentes que deben añadirse

| # | Elemento | Razón |
|---|---|---|
| 1 | **Identidad de puerta permanente** en región invariante del header | Mitigación M-4 de UI-01 |
| 2 | **Estado de la otra puerta**, solo lectura | D-06 |
| 3 | **Controles de apertura y cierre de la puerta propia** | Ausentes en los seis mockups. Es la función que fundamenta la clasificación Clase C |
| 4 | **Alarma severidad 4** (`fullscreen`, `blocking`) | Definida en `tokens.json`, sin maqueta |
| 5 | **Tarjeta de métrica F0** | Variable de letalidad acumulada |
| 6 | **Indicador de AISLAMIENTO** | §10.3 |

### 12.2 Inconsistencias a corregir

| # | Observación | Corrección |
|---|---|---|
| 7 | El indicador muestra 6 fases; la gráfica muestra 4 divisores | Unificar contra el pipeline de 7 fases de §10.1 |
| 8 | Leyendas "Tiempo 1" y "Temp 1 · 085.0 °C" para lo que `tokens.json` define como temperatura de camisa | Rotular correctamente. La temperatura de camisa es variable de control primaria |
| 9 | Unidad escrita como "°Kpa" | `kPa`, sin símbolo de grado. Añadir indicación manométrica/absoluta |
| 10 | Valores con punto decimal (`121.0`) frente a teclado con coma | Coma en toda la presentación (D-19) |
| 11 | Cero a la izquierda en valores de proceso (`085.0`) | Eliminar. Con `tabular-nums` el ancho ya es estable; parece un dígito significativo |
| 12 | "¿Olvidó su contraseña?" en equipo sin canal de recuperación | Definir el flujo real (restablecimiento por administrador desde Usuarios) o retirar el enlace |

---

## 13. Teclados en pantalla (D-18)

El teclado del sistema operativo es inadecuado para uso táctil industrial. Se implementan dos teclados propios.

### 13.1 Numérico

- Uso: parámetros de ciclo, valores de calibración
- **Separador decimal: coma**
- Sin punto decimal en el teclado — evita ambigüedad de entrada
- Signo negativo solo donde el campo lo admita
- Teclas de al menos 64 × 64 px
- Muestra rango válido y unidad del campo activo
- Validación de rango en vivo, con el botón de confirmación deshabilitado si está fuera de rango

### 13.2 Alfanumérico

- Uso: inicio de sesión, nombres de programa, datos de usuario
- Distribución QWERTY español
- **Sin tildes.** Con `ñ`
- Caracteres especiales incluido `@`
- Teclas de al menos 48 × 48 px
- Alternancia mayúsculas/minúsculas y capa de símbolos

### 13.3 Conversión decimal (D-19)

Coma en presentación y entrada; punto en persistencia, API y JSON de parámetros. La conversión reside en **un único módulo** de formateo con pruebas unitarias, conforme al §13.3 del sistema de diseño ("el formateo de números y unidades vive en `domain`, en funciones puras, nunca dentro de un componente").

---

## 14. Ítems de verificación abiertos

| ID | Descripción | Bloquea |
|---|---|---|
| **V-UI-01** | Confirmar que Windows expone `QScreen.serialNumber()` no vacío para los paneles Faytech | Implementación de §5 |
| **V-UI-02** | Medir rendimiento de QML con dos ventanas escaladas en Intel N150: 60 fps sostenidos con gráfica en vivo | Confirmación de D-07/D-08 |
| **V-UI-03** | Confirmar que la rotación por software de Windows no degrada la latencia táctil de los paneles | Confirmación de D-09 |
| **V-05** | ~~Verificar en `ControlLoop._tick()` si el temporizado de proceso usa reloj monótono~~ — **Cerrado 2026-08-12.** `control_loop.py:_acumular_f0` ya usaba `time.monotonic()` correctamente. Pero los temporizadores de fase y de puerta usaban `time.time()` (reloj de pared) en `precalentamiento.py`, `purga.py`, `prevacio.py`, `calentamiento.py`, `esterilizacion.py`, `descompresion.py`, `secado.py`, `protocolo_fallo.py`, `preparado.py` y el timeout de apertura automática en `ciclo.py` — vulnerables a saltos de reloj (C-01). Corregido a `time.monotonic()` en los 10 archivos, con TDD (test de inmunidad a salto de reloj de pared por archivo). Ninguno persiste el timer entre reinicios, así que el cambio es seguro | ~~Integridad de F0 (C-01)~~ Cerrado |
| **V-UI-04** | Confirmar duración máxima real de ciclo y frecuencia de ciclos/día para dimensionar la retención de registros — **investigado 2026-08-12, sigue abierto**: `data/autoclave.db` tiene 71 ciclos reales (65 con `fecha_fin`), pero duran de segundos a ~39 min (promedio 3.8 min) — son ciclos de desarrollo/prueba, no representativos de un ciclo de esterilización real (~2h asumido en §9.4). No se puede cerrar con estos datos sin inducir a error; necesita datos de campo reales o una cifra de referencia del fabricante/regulatorio | §9.4 |

---

## 15. Plan de implementación por fases

Ninguna fase inicia hasta que este documento esté aprobado.

| Fase | Contenido | Depende de |
|---|---|---|
| **F1** | `autoclave.launcher`: supervisión de procesos, resolución de binding de pantalla, argumentos de UI. Separación de cerrar HMI / apagar equipo (UI-03) | V-UI-01 |
| **F2** | Generador de `Tokens.qml`, componente `Icon`, empaquetado de Inter, biblioteca de primitivas del §9 del sistema de diseño | Entrega de iconos SVG |
| **F3** | Cliente WebSocket, capa de validación de frontera, contenedor de escalado uniforme — **parcial, hecho en aislamiento 2026-08-12**: `ui_qml/components/ContenedorEscalado.qml` (escalado uniforme + letterbox, D-11/§8.2), `ui_qml/domain/telemetria.py` (validación de frontera de forma del mensaje, §6.1 principio 3 — sin umbrales numéricos de plausibilidad física, no especificados), `ui_qml/domain/reconexion.py` (retroceso exponencial 1/2/4/8/15s, §6.4). **Sin hacer:** el cliente WebSocket real (transporte) — depende de decisiones de arquitectura (librería, integración con el backend FastAPI real) que no existen todavía; no es aislable de la misma forma que lo anterior | F1 |
| **F4** | Estructura de aplicación: header con identidad de puerta, navegación inferior, menú principal | F2, F3 |
| **F5** | Vista de ciclo: métricas, indicador de fases dinámico, AISLAMIENTO, gráfica con decimación y re-hidratación | F4, V-05 |
| **F6** | Controles de puerta propia y visualización de la otra puerta | F4 |
| **F7** | ~~Teclados en pantalla~~ — **Hecho 2026-08-12.** `ui_qml/domain/{teclado_numerico,teclado_alfanumerico}.py` (funciones puras) + `ui_qml/controllers/*_controller.py` (puentes QObject) + `ui_qml/components/{TecladoNumerico,TecladoAlfanumerico}.qml`. Nota de implementación: `Repeater` no incuba sus delegates sin una `QQuickWindow` con render loop activo (confirmado empíricamente, no se resuelve con `QQuickView`/`show()` en este entorno) — las grillas de teclas se construyen con `Component.createObject()` (síncrono) en vez de `Repeater` | F2 |
| **F8** | ~~Alarmas, cuatro niveles de severidad incluida la pantalla bloqueante~~ — **Componentes hechos en aislamiento 2026-08-12** (F4 real, el shell de la app, sigue bloqueado por V-UI-01): `ui_qml/domain/alarmas.py` (clasificación por severidad + selección de la alarma bloqueante activa) + `ui_qml/components/alarms/{AlarmaToast,AlarmaBanner,AlarmaBloqueante}.qml`, sin controller (presentacionales puros, emiten `reconocida()`/`dismissed()`; el host que los orquesta con datos reales de telemetría es trabajo de F4/integración, no hecho todavía) | F4 |
| **F9** | Tema oscuro y verificación visual completa — **parcial 2026-08-12**: `ui_qml/design/register.py` registra `Tokens.qml` como singleton importable (`import Autoclave.Design 1.0`), con prueba de que `Tokens.dark` conmuta la tabla activa y se comparte entre todos los componentes cargados en el mismo `QQmlEngine` (D-21). **No hecho:** ningún componente existente (Icon, teclados, alarmas) consume `Tokens` todavía — siguen tomando colores como propiedad explícita del llamador (decisión deliberada de desacoplamiento, no un olvido). Retocar sus colores por defecto para que sigan el tema es trabajo de diseño visual (qué token mapea a qué elemento) sin mockup de referencia para la mayoría — no se inventa aquí. La "verificación visual completa" real sigue bloqueada por F4 | F4–F8 |
| **F10** | Retirada de `ui/` (tkinter) y consolidación de `ui_pyside/` | F4–F9 |

**Fuera de este plan:** red y envío de reportes (bloqueado por UI-07), pantalla de diagnóstico v2, aplicación Flask de activación.

---

## 16. Historial de revisiones

| Versión | Fecha | Cambios |
|---|---|---|
| 1.0 | 2026-08-12 | Versión inicial. Decisiones D-01 a D-24. Hallazgos UI-01 a UI-08 y C-01 |
