# Hotfix ES: retiro del protocolo automático de estado seguro (6-nov-2026)

Responde e informa SOLO en español. Rama `hotfix-estado-seguro` desde `dev`. Lleva `docs/informes/hotfix_estado_seguro/estado.md` (paso → Hecho/Pendiente, último commit) al día tras cada commit; al reanudar, sigue desde el primer paso pendiente. Máximo 2 subagentes a la vez. Prioridad: velocidad y cambio mínimo.

## Contexto
En el equipo de pruebas (1.0.0-alpha.16) el equipo queda bloqueado indefinidamente en estado seguro, tras un COMPLETADO y en cada arranque («Arranque con la cámara no segura»), con presión, temperatura, entradas y paro en condición normal (verificado por Cristian). No sale ni reiniciando y la UI no dice el motivo. Con el protocolo, en modo 1, la descompresión rápida queda abierta todo el tiempo.

Decisión de Cristian (6-nov): se retira el protocolo automático de estado seguro (`ProtocoloEstadoSeguro` actuando después de CICLO y en el arranque). Cada fase y los estados PREPARACION, PREPARADO y FALLA conservan sus recuperaciones, alarmas y bloqueos; PREPARACION nivela la cámara al encender.

## Paso 1. Diagnóstico (máximo 20 min, no bloquea el paso 2)
Determina por qué `ProtocoloEstadoSeguro.update()` nunca llega a `_TICKS_SEGUROS` con las condiciones físicas en rango. Revisa al menos: `_ai_vigente()`/`lectura_ai` con `ModbusLink.estado_ultima_ai()`; `requiere_confirmacion` y `datos_vigentes`; `temp_seguridad()` devolviendo None porque el Principal de alguno de los programas de `programas_para_seguridad()` (seleccionado, último ciclo, protocolo, recuperación; instantánea del último ciclo o `_programa_desconocido()`) no está declarado o no lee; `temp_max_ciclo`.
IMPORTANTE: `camara_segura.evaluar()` también decide «NO ABRIR» y el bloqueo de inicio. Si la causa afecta esa evaluación, corrígela también: tras el hotfix el equipo NO puede quedar bloqueado por NO ABRIR con las condiciones físicas en rango. Anota la causa en `docs/informes/hotfix_estado_seguro/R_informe.md`.

## Paso 2. Retiro
1. Arranque: `ControlLoop._procesar_recuperacion()` ya no inicia el protocolo (ni ciclo interrumpido ni arranque normal). El ciclo interrumpido se sigue cerrando y registrando como interrumpido (bitácora, ticket). PREPARACION nivela la cámara como siempre.
2. `StateMachine` en CICLO: COMPLETADO, FALLO y CANCELADO ya no llaman a `estado_seguro.iniciar()`. El protocolo de fallo de `CicloState` sigue igual DENTRO del ciclo; al salir de CICLO sus válvulas se cierran (`ProtocoloFallo.finalizar()`) y el estado siguiente maneja la cámara.
3. FALLA debe manejar la presión de cámara igual que PREPARACION (sobrepresión: venteo, con carga líquida por la lenta, `carga_liquida`; vacío: aire atmosférico). Verifícalo; si no lo hace, impleméntalo reutilizando lo de PREPARACION.
4. Paro de emergencia real: se conserva la confirmación por software tras soltarlo (decisión previa de Cristian), pero al confirmar no corre ningún protocolo: el equipo pasa a PREPARACION. Confirmado por Cristian el 6-nov.
5. «NO ABRIR» y el bloqueo de inicio por cámara no segura se conservan, pero la UI debe mostrar el motivo concreto con su valor y su límite (`camara_segura.motivos()`; p. ej. «Temperatura 92 °C, máximo 80 °C»). Ningún texto vuelve a decir solo «ciclo terminó en estado no seguro».
6. UI: se retiran los textos de causa del estado seguro (`estado_seguro_causa_*`), la sección de estado seguro y todo lo que dependa del protocolo activo, salvo la confirmación del paro. `/status.estado_seguro` se conserva con la misma forma y `activo: false`, para no romper clientes.
7. Alarmas que solo emitía el protocolo (p. ej. CIC-10): ya no se emiten; el catálogo se conserva para el historial.
8. No se toca: fases del ciclo, fallas, debounce, D-CHQ, VCH-AIS, ESG-02 del modo prueba (salvo lo que dependa del protocolo activo), reasignación de E/S.

## Paso 3. Pruebas, riesgo y cierre
- Pruebas nuevas: arranque con cámara no segura (normal e interrumpido) sin protocolo; COMPLETADO, FALLO y CANCELADO sin protocolo; FALLA ventea sobrepresión (líquido por la lenta) y abre aire con vacío; paro real → confirmar → PREPARACION; NO ABRIR con motivo. Ajusta o retira las pruebas del protocolo retirado, con la lista en el informe.
- Riesgo HAZ-ES-RET-01 en `docs/riesgos/registro_riesgos.md`, aceptado por Cristian el 6-nov: tras un fallo o cancelación con líquido caliente ya no hay enfriamiento con contrapresión (modos 4/5); la cámara se ventea por la lenta desde FALLA/PREPARACION.
- 1 subagente revisor de seguridad, solo sobre el diff. Corrige lo ALTA y MEDIA.
- Suite completa en verde, actualiza `CLAUDE.md` (sección del estado seguro), merge a `dev`, `python tools/entrega/compilar_entrega.py`. Si la compilación se detiene (p. ej. LIC-01), anótalo y dale a Cristian el comando.
- Último acto: `docs/informes/hotfix_estado_seguro/CERRADO.txt` (fecha, commit del merge, suite, versión compilada o motivo de no compilar). Si te bloqueas por algo que necesite a Cristian, escríbelo igual con `BLOQUEADO:` en la primera línea.
