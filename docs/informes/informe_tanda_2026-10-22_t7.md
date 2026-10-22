**INSTALAR: `entrega/2026-10-22_b/`** (compilación B, etiqueta `inst-2026-10-22-b`). Respaldo: `entrega/2026-10-22_a/`. Guía: `entrega/LEEME_INSTALACION.md`.

# Tanda 7 — Índice (noche 21/22-oct-2026)

## Resumen (10 líneas)
1. Hay ejecutable instalable: **B** en `entrega/2026-10-22_b/` (08:08), con zip, SHA-256 y LEEME. La A (00:34) queda de respaldo.
2. La B lleva L1, P1, M1, C2, M2 y Q1, todas unidas a `dev` con la suite en verde tras cada unión (final: 5405 passed, 3 skipped, 3 xfailed).
3. P1 corrigió 5 fallas que estorbaban lo de hoy: E/S en modo prueba (momentáneas, `aire_atmosferico_camara`, vigilante), calibración de la Referencia y la intro trabada.
4. M1: el asistente calcula el modelo `SPK-SAT …` (paso Cámara), sin clases de mesa.
5. C2: el correo a una dirección escrita a mano ya se envía y el resultado sale de lo que aceptó el servidor, por destinatario.
6. M2: Mantenimiento E1 (MNT-01, 02, 03 y 05).
7. Q1: decisión 1.3 completa (R1-P1 a P5, T2-a, b y c). La revisión encontró 1 Alto (F0 acreditado tras un corte del enlace): corregido; re-revisión con 0 Altos/Críticos. Un Alto preexistente en `dev` (SEN-01, presión 0 kPa) queda como pregunta.
8. D2 (depuración) se unió DESPUÉS de K2; no está en ninguna compilación.
9. La sesión principal se detuvo de 01:43 a 06:10 por el límite de uso; los subagentes ya habían terminado el código.
10. R6 no tuvo objeto (la tanda 6 cerró completa). Push: ver la sección "Push".

## Etapas
| Etapa | Estado | Informe |
|---|---|---|
| A0 | Hecha | `tanda7/estado.md` |
| K1 | Hecha (compilación A) | `tanda7/K1_compilacion_a.md` |
| L1 | Unida | `tanda7/L1_lock_soup.md` |
| P1 | Unida | `tanda7/P1_preparacion_instalacion.md` |
| M1 | Unida | `tanda7/M1_asistente_modelo.md` (+ `tanda7/capturas/`) |
| C2 | Unida | `tanda7/C2_correo_manual.md` |
| M2 | Unida | `tanda7/M2_mantenimiento_e1.md` |
| R6 | Sin objeto | `tanda7/estado.md` |
| Q1 ★ | Unida (revisores sin Altos/Críticos abiertos) | `tanda7/Q1_preguntas_abiertas.md`, `tanda7/Q1_ensayo_tabla.md` |
| K2 | Hecha (compilación B) | `tanda7/K2_compilacion_b.md` |
| D2 | Unida después de K2 (no está en ninguna compilación) | `tanda7/D2_depuracion.md` |
| Z | Hecha | este índice |

Decisiones sin confirmar de todas las etapas: cada informe, y las de la sesión principal en `tanda7/DECISIONES_PARA_REVISAR.md` (SP-1 a SP-9).

## PROBLEMAS CONOCIDOS PARA MAÑANA (con rodeo; detalle en el LEEME)
| Problema | Rodeo |
|---|---|
| Canales fuera de `io_enabled` de `ACV-2026-001.yaml` (Cámara 2, `descompresion_lenta`, …) no aparecen en E/S | Agregarlos al YAML instalado con Autoclave cerrado (LEEME §6.1) |
| La calibración que viaja con el programa no es neutra (valores de banco) | "Restaurar por defecto" en cada sensor antes de calibrar (LEEME §6.2) |
| Presión: los dos puntos deben distar ≥ 50 kPa | Punto alto ≥ 125 kPa abs; cómo obtenerlo: verificar en sitio |
| Calibrar exige la tarjeta conectada en la pantalla táctil | Menú de ajustes `Autoclave.exe --rol ajustes` |
| Con el paro de emergencia activo, OPCIONES no abre | Liberar el paro o cablearlo cerrado |
| Un solo monitor: la ventana de la puerta 2 tapa la de la puerta 1 | Acceso directo con `--una-pantalla` |
| Reloj adelantado al instalar → ARR_RELOJ al corregirlo | Ajustar la hora antes del asistente; si ya pasó, reinstalar el perfil (LEEME §7) |
| El texto final del asistente dice "Reinicie el software" | No hace falta: pulsar Continuar |
| La prueba de humo de la B no recorrió los 8 pasos del asistente (pantalla de la oficina de 1536×864) | Verificar en sitio; cubierto por las pruebas QML de M1 |

## PREGUNTAS PARA CRISTIAN
**Seguridad / ciclo (no afectan la instalación de hoy):**
- **SEN-01 (Alto, preexistente en `dev`):** un transductor de presión de cámara sin señal da 0,0 kPa (el convertidor recorta) y el ciclo y el protocolo de fallo lo toman como lectura válida: ESTERILIZACION pasa a RECUPERACION con vapor continuo y luego FALLO por presión baja, y el protocolo lo trata como vacío (abre el aire atmosférico, no la lenta). ¿Se trata `pres == 0` (o bajo un piso físico) como sensor ausente? ¿El transductor es 4-20 mA? (SP-7)
- R1-P4: ¿el paso a `solo_lenta` por pérdida del Principal debe habilitar también `permite_salir_de_falla` cuando la causa original del fallo fue otra? (SAF-01/SEN-02/TMG-07; el debounce de 3 lecturas ya se agregó)
- T2-a: ¿la desconexión total de menos de 5 s y la ventana tras reconectar también deben pausar la exposición? (SAF-02/TMG-02)
- ¿La pausa acumulada en ESTERILIZACION debe tener tope o correr también el timeout de F0? (TMG-03)
- T2-b cuenta 3 ticks con el enlace "ok", no 3 tramas distintas (una sola trama DI puede cubrir 3 ticks). ¿Se cuentan tramas? (TMG-04)
- Modos 4/5 con líquido: perder el Principal en el enfriamiento con contrapresión ventea por la lenta. ¿Está aceptado en el fichero de riesgos?
- Q1-P1 a Q1-P7 (ver `Q1_preguntas_abiertas.md`): ACK del ALL_OFF sin respuesta, otros temporizadores durante la tolerancia, abort en desconexión total, "Sin datos de la tarjeta" en la reimpresión, textos en la QML, "carga no estéril" en la pantalla de resultado.

**Instalación y equipo (P1):** `io_enabled` del YAML del equipo; calibración neutra en las compilaciones de entrega; riesgo de `aire_atmosferico_camara` en modo prueba con la cámara presurizada; detección de un solo monitor; aviso en pantalla si Windows rechaza el apagado; texto final del asistente.

**Modelo (M1):** "Clase: piso_lab" sin traducir en el ticket de arranque; ¿capacidad y carga también en ticket/PDF?

**Correo (C2):** rechazo parcial en rojo o en verde con nota; paso de confirmación o casillas.

**Mantenimiento (M2):** ¿renombrar "Último mantenimiento" a "Último preventivo"? P-3 (`otro`) y MNT-04 siguen abiertas.

**Dependencias (L1):** lock completo del entorno o solo del producto (venv limpio); SOUP no importados; `pyproject.toml` desalineado.

**Depuración (D2):** ver las preguntas P1 a P6 de `D2_depuracion.md` (arneses QML de prueba, `_email_dialog.py`, dominios QML sin cablear, imágenes de diseño, posibles funciones muertas en zonas de seguridad, `estudio/`) y la tabla de ramas con commits propios sin unir.

## Lo que quedó sin hacer y dónde está
- Hallazgos Medios/Bajos pendientes de la revisión de Q1 (TMG-02..05, 08..12; SEN-05, 06, 08; re-revisión TMG-02): listados en `Q1_preguntas_abiertas.md`, sin rama.
- Pendientes Bajos de P1 (TMG-02, 04, 05; SEN-02, 03, 04) y SEN-01 de P1 (alias `temp_camara_2` de Líquidos): en `P1_preparacion_instalacion.md`.
- **Prueba intermitente:** `tests/test_opciones_qml.py::test_ingeniero_edita_con_ciclo_en_curso` falló una vez en la suite final (`atras_regresa` en False) con un código idéntico al que pasó; pasa 5/5 aislada y la corrida repetida quedó en verde (5382 passed). Es de temporización de la QML bajo carga; no se tocó.
- Hallazgos abiertos de O2f de la tanda 6 (TMG-04/05, SAF-01/02): sin cambios.

## Recordatorios (decisión 1.5, no se tocaron)
- El formulario del preventivo (P-1 a P-10 de `planeacion_mantenimiento.md`).
- El retiro del código de los equipos de mesa.
- El predictivo.

## Push
(ver abajo, se completa en Z)
