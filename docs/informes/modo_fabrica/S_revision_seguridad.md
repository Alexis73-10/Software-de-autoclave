# Revisión de seguridad independiente de la rama modo-fabrica (f4a9aa9f..3ac53ce9)

Agente safety-reviewer (solo lectura), 22-nov-2026. Resumen de los hallazgos; las correcciones van en el informe `S_correcciones.md`.

| Id | Severidad | Hallazgo |
|---|---|---|
| SAF-01 | ALTA | La fase 2 del cierre (`cierre_fabrica.completar_cierre_si_pendiente`) no valida nada antes de borrar. Basta un `cierre_fabrica.json` vacío en `data/` de un equipo ENTREGADO para que el arranque borre `respaldo_ciclos`, ponga los contadores en cero y borre logs y `.corrupta-*`. Con un `autoclave.db.nueva` fabricado en FÁBRICA, el equipo vuelve a FÁBRICA y sin registros (contradice FAB-01 y FAB-03). |
| SAF-02 | ALTA | Si un paso crítico falla, se escribe una BD_BLOQUEADA propia y el equipo queda en modo sin base, que permite ciclos. El arranque siguiente borra esos ciclos reales de `respaldo_ciclos` y reinicia la numeración. |
| SAF-03 | MEDIA | `_guardar_marca` se traga el error. Si además el `unlink` final falla, los pasos destructivos se repiten en el siguiente arranque. |
| SAF-04 | MEDIA | Un código v1 cuenta como primera instalación. ENTREGADO vive solo en la base: si la base y el perfil se pierden en campo, una reinstalación con v1 o con un INS vigente deja el equipo en FÁBRICA en campo. |
| SAF-05 | BAJA | Lo que se escribe en la base entre la copia que va al paquete y la marca no llega al paquete. |
| SAF-06 | BAJA | `_limpiar_restos` sobrescribe con ceros en cada arranque cualquier `autoclave.db.vieja*`, aunque no la haya dejado un cierre. |
| SAF-07 | BAJA | El rechazo del paquete de liberación al restaurar depende solo del campo `tipo` del manifiesto, que se puede editar recalculando el hash. |
| SAF-08 | BAJA | Una calibración del equipo con `poly` no pasa la prueba de plausibilidad. |

Verificado sin hallazgos: triggers y ausencia de `DROP TRIGGER`; lectura del estado con falla hacia ENTREGADO; transacción de entrada; `REI` nunca entra; base nueva del cierre; fase 1 sin cambios ante un fallo; lazo detenido con todo apagado antes de la marca; middleware 409 durante el cierre; calibración «defecto» por función con comprobación de canal; coherencia de los parámetros de fábrica del equipo; numeración y borrado de programas; secretos fuera del paquete.

Preguntas abiertas:
1. ¿Se emiten códigos v1 para reinstalaciones?
2. ¿El desinstalador borra `datos\autoclave.db`?
3. ¿Hay secretos de correo en `system_params`, los logs o `cycles/user`?
4. ¿Qué límite usa `programas_para_seguridad()` si se borra el programa del último ciclo?
5. ¿La pantalla debe avisar cuando «defecto» cae al neutro?
