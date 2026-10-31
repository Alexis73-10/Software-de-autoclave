# S3b — CIC-10: salida autorizada cuando el estado seguro no puede terminar (propuesta)

Instrucción: `instruccion_claude_code_tanda_2.md` §2 S3 (T5): "diseña el camino más seguro; si requiere decisión de producto, déjalo PENDIENTE con la propuesta". **Estado: PENDIENTE de decisión de producto. No se implementó nada.**

## El problema

En `state_machine/estado_seguro.py` (T5), el protocolo de estado seguro puede quedar **detenido** y avisar con CIC-10 ("Estado seguro detenido", AVISO, con el motivo): por ejemplo, el sensor Principal sin lectura con tipo de carga líquida (nunca se escala a la rápida sin temperatura), o una escalada denegada. Hoy **no hay salida automática**: la cámara no se declara segura sin temperatura (falla cerrada). El equipo queda en NO ABRIR, sin que el operador tenga un camino definido.

## Qué hace hoy el software ante CIC-10

- CIC-10 es un aviso (no bloqueante) con el motivo del bloqueo; se resuelve solo cuando el protocolo vuelve a avanzar (p. ej. al volver la lectura del Principal).
- `camara_segura` sigue en falso: NO ABRIR, sin apertura de puertas desde la UI.
- La recuperación posible hoy es **física o de configuración**: reparar o reconectar el sensor, o reasignar el rol Principal a una sonda en buen estado (OPCIONES › Parámetros del ciclo › Sensores, técnico o ingeniero, fuera de CICLO). **Por verificar:** que un cambio de rol surta efecto sobre un protocolo ya en curso.

## Opciones

**A. Sin salida nueva (mantener falla cerrada), con camino documentado.** Es la opción más segura y la mínima: el aviso CIC-10 pasa a indicar qué hacer ("revise la sonda Principal o asigne otra como Principal"); el procedimiento queda en el manual de servicio.
- A favor: ningún atajo para abrir con vapor o presión.
- En contra: depende de que el técnico llegue; un equipo con el Principal averiado queda inutilizable hasta repararlo.

**B. Reasignación guiada del Principal desde el propio aviso.** Un botón en CIC-10 abre la pantalla de roles (técnico/ingeniero), con el aviso de "NO ABRIR" vigente, y verifica que la sonda elegida tenga lectura. No agrega ningún camino a la apertura.
- A favor: es el único cambio que mantiene la verificación por sensor.
- En contra: la sonda de reemplazo puede estar en un punto menos representativo (riesgo de HAZ-LIQ-01 para líquidos).

**C. "Declarar la cámara segura" manualmente (salida de mantenimiento).** Un ingeniero, con sesión, confirma haber verificado por medios independientes (manómetro y termómetro mecánicos) que la cámara está a presión atmosférica y por debajo de 80 °C. Habilita **una sola** apertura y queda auditado (usuario, hora, motivo, lecturas declaradas), con la alarma CIC-10 registrada.
- A favor: sale del bloqueo cuando no hay ningún sensor utilizable.
- En contra: es un bypass de la cámara segura por criterio humano; si el operador se equivoca, exposición a vapor o a líquido caliente a presión. Va contra el principio de que el software no abre sin evidencia.

## Recomendación

**A + B**, y **no implementar C** hasta contar con un procedimiento de servicio y un análisis de riesgos (ISO 14971) que lo acepten: C convierte un fallo de sensor en una decisión humana con consecuencia de seguridad. Si el producto exige C, mínimos:
- solo rol ingeniero, con confirmación por contraseña, nunca sin sesión;
- una sola apertura y vence a los pocos minutos;
- con presión y temperatura declaradas y comparadas con un límite alto razonable;
- doble confirmación en pantalla ("NO ABRIR" en rojo);
- auditoría completa y alarma persistente;
- prueba de banco dedicada.

## Decisión pedida a Cristian

1. ¿A + B, o se acepta C con las condiciones de arriba?
2. ¿Puede un cambio de rol del Principal liberar un estado seguro detenido? (hay que probarlo en banco; no se tocó).
