# A1 — Apagado de Windows en cualquier estado

Pruebas: 3587 → 3620 (suite completa en verde, junto con A2).

## Cambios
- `POST /system/shutdown` se permite en cualquier estado de máquina salvo CICLO, y salvo estado seguro ACTUANDO. Ya no exige cámara segura, datos vigentes ni ausencia de modo prueba. Se permite con FALLA, EMERGENCIA, paro, sin tarjeta y cámara no segura.
- Se mantienen: ventana principal, confirmación de la UI, segundo apagado rechazado, apagado real de Windows solo con el exe o `AUTOCLAVE_APAGADO_REAL=1`.
- Bitácora `apagar_equipo` con estado, motivo "fuera de servicio solicitado", cámara segura, tarjeta conectada, paro y modo prueba.
- Secuencia con degradación segura: `iniciar_apagado()` ahora manda ALL_OFF de inmediato bajo el lock (SAF-01); cada paso (stop, historial, logger de ciclo, cierre de BD) corre con tope de 8 s y un fallo no impide el siguiente ni el `shutdown`; `shutdown` con timeout; si no arranca el hilo, se apaga en línea. `ControlLoop.stop()` cierra el puerto aunque `all_off` lance.
- Modo prueba y salidas manuales se rechazan mientras se apaga (SAF-02).
- UI: aviso en el diálogo de confirmación cuando `camaraNoSegura` (es/en, `equipo.apagar_camara_no_segura`, anotado en revision_traducciones).

## Revisores
- safety-reviewer: 1 Alta (SAF-01, corregida), SAF-02 corregida; SAF-03/04/06 Medias/Bajas aceptadas (ver abajo).
- timing-auditor: TMG-01/02/03/04 corregidas (topes, timeout, BaseException, fallback de hilo); TMG-05 informativa.

## DECISIONES SIN CONFIRMAR
1. "Estado seguro en curso" = protocolo activo Y no pausado (sin paro, sin confirmación pendiente y con datos vigentes). Un estado seguro pausado por paro o esperando confirmación SÍ permite apagar. Alternativa: rechazar siempre que `estado_seguro.activo`. Revertir: reemplazar `_estado_seguro_en_marcha()` por `estado_seguro.activo`.
2. El modo prueba NO bloquea el apagado (un técnico reparando suele estar en él). Antes era 409.
3. El aviso de cámara no segura solo existe en el diálogo (no bloquea).

## Pendientes / observaciones
- SAF-04: la UI no avisa específicamente de "estado seguro pausado". SAF-03: falta registrar `recuperacion_pendiente` en la bitácora. SAF-06: fuera del exe el proceso sigue vivo con el lazo detenido (solo desarrollo).
- Prueba B-06 de la hoja de banco: se actualiza en H1.
- Comprobación manual: con el exe, apagar en FALLA y con la tarjeta desconectada; volver a encender y verificar arranque normal.
