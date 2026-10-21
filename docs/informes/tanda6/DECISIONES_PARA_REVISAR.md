# Tanda 6: decisiones para revisar

Formato: decisión · motivo · alternativa · commit · cómo revertir.

## T2 (respuestas a T1)
| Id | Decisión | Motivo | Alternativa | Commit | Cómo revertir |
|---|---|---|---|---|---|
| T2-1 | Tolerancia de DI vencida = 4 s | WD del firmware V3 = 5 s; 1 s de margen. Ese WD mide PC→tarjeta y no protege este caso | 5 s | 5d7c93b | `_TOLERANCIA_DI_VENCIDA_SEG` en `ciclo.py` |
| T2-2 | Durante la tolerancia: vapor de cámara y chaqueta OFF, la fase no corre; 3 ticks vigentes reinician | Revisión TMG-01/02/03, SAF-01 | Seguir la fase con solo AI | 5d7c93b | Bloque P-3 de `ciclo.py` |
| T2-3 | Despeje manual de COM-02/03 = reconocimiento explícito con botón DESPEJAR nuevo (usuario "operador", sin rol) | Sin botón, con P-4 el equipo quedaba bloqueado desde QML | Exigir sesión; despejar al volver el enlace | 25727f6 | `DESPEJE_POR_RECONOCIMIENTO` y el botón en `PanelNotificaciones.qml` |
| T2-4 | Un 0 de un sensor de temperatura en uso = sin lectura en ciclo | Coherencia con `estado_sensor`/`temp_seguridad` (SEN-01) | Solo None | 5d7c93b | Lista `ausentes` en `ciclo.py` |
| T2-5 | P-12: 3 lecturas en o bajo el menor `temp_max_apertura` para la rápida; sin valor global, siempre la lenta | Debounce estándar; falla segura | Sin debounce | 5b1afa9 | `_liquido_frio_para_rapida` |
| T2-6 | Se conservan el alias `DISTINTO_DE_CICLO_E_HIBERNACION` y el manejador muerto de HIBERNACION en `Main.qml` | Cambio mínimo | Renombrar o quitar | commit P-8 | — |
| T2-7 | Marca "CARGA NO ESTÉRIL" solo en INTERRUMPIDO | Es lo pedido en P-9 | Todos los fallos | 34552db | `format_footer` |

## PREGUNTAS PARA CRISTIAN (T2)
- ¿Los segundos de tolerancia por DI vencida cuentan como exposición en ESTERILIZACION?
- ¿DESPEJAR debe exigir el enlace "ok" o una sesión?
- ¿La marca "no estéril" también para FALLO/CANCELADO/EMERGENCIA?
