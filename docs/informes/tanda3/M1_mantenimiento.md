# M1 — Próximo mantenimiento

## Hecho
- **Cálculo** (`core/runtime/mantenimiento.py`, lógica pura): primer mantenimiento = `installed_at` (created_at del perfil) + `intervalo_dias`; tras registrar uno, la base es esa fecha y los ciclos de ese momento; con `intervalo_ciclos` > 0 vence lo que ocurra primero (contador persistente). Estados: ok / proximo (≤14 días o ≤5 % de ciclos) / vencido / sin_dato / no_aplica. Reloj anterior a la instalación o al último registro → `sin_dato` ("—"), nunca un valor falso; además `POST` lo rechaza (409 `reloj_invalido`).
- **Configuración**: `data/mantenimiento.json` (atómico, validado 0..3650 días / 0..1 000 000 ciclos; ilegible o inválido → valores por defecto con log). Endpoint `PUT /maintenance/config` (técnico/ingeniero, audita `mantenimiento_configurado`).
- **Registro**: tabla `mantenimientos` (migración v5, solo anexar: triggers contra UPDATE/DELETE), `POST /maintenance/records` (técnico/ingeniero, tipo preventivo/correctivo/calibración/otro, observaciones ≤500; audita `mantenimiento_registrado`), `GET /maintenance/records`, `GET /maintenance` (abierto, solo lectura).
- **Aviso**: `SIS-04` (alias `MANTENIMIENTO_VENCIDO`), AVISO de baja prioridad, `bloquea_inicio=False`; vigilancia al arrancar y cada 10 min (hilo daemon) y al registrar/configurar. Nunca toca el ControlLoop ni el estado.
- **UI**: tarjeta "Próximo mantenimiento" (fecha o "VENCIDO"), ventana flotante (vencimiento, último, ciclos restantes), filas de Información del equipo (último mantenimiento y ciclos restantes, ya no "No disponible") y OPCIONES › Mantenimiento (`OpcionesMantenimiento.qml`, diseño provisional) con "Registrar mantenimiento realizado".
- Pruebas nuevas: cálculo (21), servicio y endpoints (permisos, auditoría, reloj, solo-anexar), UI (controlador y carga de pantalla), puente/domino del resumen, información del equipo.

## DECISIONES SIN CONFIRMAR
1. **Intervalos por defecto PROVISIONALES: 180 días, sin límite de ciclos.** No se encontró ningún intervalo documentado en `docs/`, `docs/riesgos/` ni `Documentacion/` (solo "B-03: no existe configuración de intervalos"). Cristian debe dar los definitivos (cambiarlos: `PUT /maintenance/config` o editar `data/mantenimiento.json`).
2. Los intervalos se configuran por API/archivo; no hay pantalla de edición (Parámetros del sistema sigue en PySide; la pantalla mínima pedida no la incluía).
3. La pantalla de OPCIONES solo captura el tipo (sin observaciones; el endpoint las admite).
4. La configuración vive en `data/mantenimiento.json` (no en `global_params.json`, que es un recurso empaquetado de solo lectura en el exe congelado).
5. Sin base de datos el último mantenimiento se desconoce y se calcula desde la instalación.

## Revisor
safety-reviewer solo para confirmar que no bloquea ciclos: ver abajo.

## Hallazgos del revisor (safety-reviewer): sin Críticos ni Altos; no bloquea ciclos
- Confirmado: ningún módulo de control referencia M1; SIS-04 es AVISO no bloqueante; todo el servicio captura excepciones; nada corre en el hilo del lazo.
- M1-03/M1-04 (Bajas) corregidas: una sola instancia del servicio y vigilancia idempotente; `/maintenance` nunca devuelve 500 (sin_dato / lista vacía).
- **M1-01 (Media, ACEPTADO como riesgo):** un reloj ADELANTADO puede sellar un mantenimiento con fecha futura que, por ser tabla de solo anexar, no se corrige y deja inutilizado el registro hasta esa fecha. No hay una referencia de tiempo independiente en el equipo (cada login escribe audit_log con la hora actual). Mitigación: la fecha la sella el servidor, el usuario/rol quedan auditados y el aviso es solo informativo. Alternativa: fila de anulación o confirmación explícita si la fecha supera en >30 días a la última actividad. Pendiente de decisión de Cristian.
- M1-02 (Baja): un aviso SIS-04 que aparezca durante un ciclo queda asociado a ese ciclo en el historial de alarmas. Aceptado.
