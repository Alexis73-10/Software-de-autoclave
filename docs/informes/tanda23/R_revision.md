# Tanda 23 — revisión R (parte AIN, AIN-R1/R2)

Revisor de seguridad (solo lectura) sobre `tanda-23-ain` frente a `dev`. Correcciones en 819ba50d con `tests/test_t23_ain_revision.py`.

| Id | Sev. | Hallazgo | Corrección |
|---|---|---|---|
| SAF-01 | MEDIA | `io_ports` del YAML de instancia no llevaba marca de formato: una copia persistente sin refrescar o una instancia propia del sitio con presión 9–12 se leería como AI 09–12 (canales crudos 16–19), válidos en FORMATO 2, sin CONFIGURACION_INVALIDA | Clave `io_ports_formato: 2` en `ACV-2026-001.yaml`; sin ella, `fabrica_desde_yaml` migra la presión (p − 8, mismo canal) con aviso en el log; fuera de 09–16 `puerto_inexistente`; marca desconocida `fabrica_invalida` (ErrorArranque) |
| SAF-02 | BAJA | Si la migración no se pudo escribir al arrancar, `guardar()`/`quitar_pendiente()` reescribían en FORMATO 2 sin la anotación: la fila `asignacion_io_migrada` no se escribía nunca | Ambos agregan la anotación (`registrada: false`) cuando el archivo en disco es FORMATO 1 |
| SAF-03 | BAJA | El `.bak` con el FORMATO 1 original se pisaba en el siguiente guardado | Copia única `asignacion_io.json.formato1.bak`, nunca sobrescrita |
| SAF-04 | BAJA | `puerto_de_registro` restaba 8 a todo registro con `formato != FORMATO` (un FORMATO 3 futuro se leería mal); literal duplicado en `rutas/io.py` | Resta 8 solo sin marca; marca desconocida → None (no se interpreta); `_FORMATO_PUERTO = asignacion_io.FORMATO` |
| SAF-05 | BAJA | El 422 de validación quitaba `grupo` de los errores | `grupo` se conserva |
| SAF-06 | BAJA | La prueba de equivalencia fijaba el desplazamiento 8 | Usa `converters.OFFSET_RAW_PRESION`; caso del YAML viejo cubierto |

Verificado sin hallazgo: ningún sensor cambia de canal físico (1680 combinaciones), migración idempotente que conserva DI/DO/temperatura/pendientes, RTD y AI sin mezcla en duplicados/búsquedas/UI, MOD-08/`all_off`/ADB-01..05 sin cambios más allá de `N_PRES`/`N_AI`, calibración 8→16 sin tocar 0–7, códigos `TARJETA_*` y persistidos intactos.

Preguntas abiertas del revisor (al informe): (1) comprobar en el banco que el principal responde fc04 0x0000 ×16 (si diera excepción en 0x0008–0x000F se perdería toda la trama AI: falla cerrada pero equipo inutilizable); (2) si hay equipos con YAML de instancia propio (exposición a SAF-01, ya corregido); (3) si hay transmisores cableados en AI 09–16.
