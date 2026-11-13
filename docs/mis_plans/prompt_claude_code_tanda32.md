# Tanda 32: enfriamiento de líquidos con contrapresión, modos 4 y 5 (7-nov-2026)

Responde e informa SOLO en español. Prioridad: velocidad por tarea; cambio mínimo. Máximo 4 subagentes a la vez, sin suite completa en los subagentes; 1 revisor de seguridad al final sobre el diff de LIQ-01 a LIQ-04. Decisiones de Cristian: todas las de este documento (7-nov), salvo las marcadas `DECISIÓN SIN CONFIRMAR`. Ante ambigüedad, lo seguro y `DECISIÓN SIN CONFIRMAR` en el informe.

## Requisito previo: espera a la tanda 31
La tanda 31 puede estar corriendo en ESTA MISMA carpeta. Mientras esperas NO escribas, cambies de rama ni hagas ninguna operación de git o de archivos en el repositorio; solo lee.
1. Revisa si existe `docs/informes/tanda31/CERRADO.txt` (los `CERRADO_intento*_bloqueado.txt` NO cuentan).
2. Si no existe, espera 5 minutos con un comando de espera del shell (`Start-Sleep -Seconds 300` o `sleep 300`; sin subagentes ni otras herramientas mientras esperas) y vuelve al paso 1. Tope: 14 horas.
3. Si existe y empieza con `BLOQUEADO:`, o se cumple el tope: crea `docs/informes/tanda32/CERRADO.txt` con `BLOQUEADO: tanda 31 no cerrada` (o su motivo) y termina.
4. Si existe sin bloqueo: espera 2 minutos, verifica que la rama actual sea `dev`, que el merge de la tanda 31 esté en `dev` y que no haya cambios pendientes en `src/`, `tests/`, `tools/` ni `packaging/` (los archivos de `docs/`, `AJUSTES.md` y `habblaud/` de Cristian no cuentan; no los toques). Si algo no cuadra, espera 5 minutos y repite (máximo 6 veces; luego BLOQUEADO).
Rama `tanda32` desde `dev`. Lleva `docs/informes/tanda32/estado.md` al día tras cada commit; al reanudar, sigue desde el primer paso pendiente.

## Contexto
- Código actual: `cycle_phases/descompresion.py` (`_tick_sub_enfriamiento`, `_tick_sub_descompresion`), `cycle_phases/protocolo_fallo.py` (`_tick_enfriamiento`, `_fin_enfriamiento`, rama de modo 3 lenta → rápida), `valvula_reposo.py`, `core/managers/catalogo_parametros.py` (`MARGEN_CONTRAPRESION_LIQUIDO`, `MODOS_CONTRAPRESION`, reglas de carga líquida), `core/runtime/steam.p_saturacion_kpa`, `core/runtime/lectura.carga_enfriada`, `cycles/{factory,user}/*.json`.
- Física del equipo (dicha por Cristian): en líquidos el Principal va dentro del líquido o en un recipiente testigo y la Referencia en el punto más frío de la cámara; envases abiertos o con tapa no sellada; el escape lento es una válvula de aguja regulable; la chaqueta tiene drenaje propio y se despresuriza con `descompresion_chaqueta`.
- La duplicación entre la fase DESCOMPRESION y el `ProtocoloFallo` (enfriamiento con contrapresión) se resuelve con un componente puro compartido en `cycle_phases/` (p. ej. `enfriamiento_contrapresion.py`) con pruebas propias; las dos clases lo usan.

## LIQ-01 Orden de arranque del enfriamiento (H3 + H6)
Al entrar a la sub-etapa de enfriamiento (modos 4 y 5):
- Aire comprimido como hoy (pulsos de 3 s cuando `pres_camara < presion_camara_enfriamiento`, inhibido con la trama AI vencida). El modo 5 abre la lenta desde el primer tick, como hoy.
- `descompresion_chaqueta` abierta fija (sin pulsos) desde el primer tick y durante toda la sub-etapa.
- Dos condiciones enclavadas (una vez cumplidas no se pierden en la sub-etapa): (a) presión de cámara alcanzada, `pres_camara >= presion_camara_enfriamiento` con lectura vigente; (b) chaqueta despresurizada, `pres_chaqueta <= presion_atmosferica + presion_despresurizacion_chaqueta` con lectura vigente.
- `agua_chaqueta` se abre solo con (a) y (b) cumplidas, y desde entonces queda abierta hasta el fin de la sub-etapa (no se cierra si luego baja la presión; eso lo maneja LIQ-02). Sin lectura de `pres_camara` o de `pres_chaqueta` la condición correspondiente no se cumple (falla cerrada).
- Tiempos máximos: si (b) no se cumple en `timeout_despresurizacion_chaqueta` → FALLO con código propio; si (a) no se cumple en `timeout_presurizacion_enfriamiento` → FALLO con código propio (`DECISIÓN SIN CONFIRMAR`: este segundo tope no lo pidió Cristian; sin él, un aire que no alcanza el objetivo solo terminaría en el timeout general del modo).
- El vapor de chaqueta sigue apagado (`chaqueta_en_enfriamiento`) y el corte D-CHQ no cambia.
- Se retiran `tiempo_apertura_chaqueta` y `tiempo_cierre_chaqueta` de `modo_4`/`modo_5` (catálogo, JSON, migración al cargar que los quita con auditoría y `.bak`, como las migraciones de la tanda 28/29). Lista en el informe cualquier otro uso que encuentres.
- Parámetros nuevos en `descompresion.modo_4` y `descompresion.modo_5`: `presion_despresurizacion_chaqueta` (kPa sobre la atmosférica, clase «diferencia», defecto 20, rango 5–50) y `timeout_despresurizacion_chaqueta` (min, defecto 3, rango 1–15); `timeout_presurizacion_enfriamiento` (min, defecto 3, rango 1–15, `DECISIÓN SIN CONFIRMAR`). Migración al cargar que los agrega con su defecto si faltan (auditoría, `.bak`).

## LIQ-02 Vigilancia de la contrapresión durante el enfriamiento (H4)
- Mínimo dinámico, recalculado en cada tick: `P_min = p_saturacion_kpa(T_Principal) + MARGEN_CONTRAPRESION_LIQUIDO` (30 kPa, el mismo de la regla al guardar). Riesgo físico: el líquido de un envase abierto hierve cuando su presión de vapor supera la presión total de la cámara (aire + vapor).
- Se arma cuando se cumple la condición (a) de LIQ-01 por primera vez (antes la cámara todavía se está presurizando y lo cubre el tope de LIQ-01) y vigila hasta el fin de la sub-etapa de enfriamiento.
- Con `pres_camara < P_min`: el aire sigue reponiendo (control de LIQ-01 sin cambios). 10 s seguidos bajo el mínimo → aviso no bloqueante con código propio (pantalla, campana, ticket; se despeja solo al recuperar). 60 s seguidos → FALLO con código propio y protocolo de fallo de líquidos (sigue con contrapresión). Si la presión vuelve sobre el mínimo, el conteo se reinicia. Tiempos 10 y 60 s: aprobados por Cristian, `DECISIÓN SIN CONFIRMAR` hasta el banco (constantes con nombre).
- Sin lectura del Principal o de `pres_camara`, o con la trama AI vencida: cuenta como bajo el mínimo (falla cerrada). La pérdida del Principal sigue además con su manejo actual (SEN-02 / `en_enfriamiento_con_contrapresion`).
- Dentro del `ProtocoloFallo` (el ciclo ya falló) se aplica LIQ-01 igual y LIQ-02 solo como aviso, sin un segundo fallo (`DECISIÓN SIN CONFIRMAR`).
- Si el perfil tiene cableada la entrada de suministro `aire_comprimido`, revisa cómo se vigila hoy durante el enfriamiento y anótalo en el informe; no cambies su lógica en esta tanda.

## LIQ-03 Opción lenta → rápida en el modo 5 (H8)
- Parámetros nuevos en `descompresion.modo_5`: `descompresion_lenta_rapida` (bool, defecto false) y `presion_cambio` (kPa absolutos, defecto 150, rango 1–400 como `modo_3.presion_cambio`). Regla de coherencia al guardar y al cargar: con la opción activa, `presion_cambio < presion_camara_enfriamiento`.
- Con la opción activa, al terminar el enfriamiento (Principal enfriada, 3 lecturas) la descompresión final mantiene la lenta abierta (y `descompresion_chaqueta`), con la rápida cerrada, hasta `pres_camara <= presion_cambio`; entonces lenta OFF y rápida ON hasta el fin de siempre (`_en_presion_fin`). Sin lectura de presión, no se cambia a la rápida. Desactivada: idéntico a hoy. El modo 4 no cambia.
- Igual en el `ProtocoloFallo` cuando sale del enfriamiento de un modo 5 con la opción activa.
- Debe aparecer en el menú de parámetros del modo 5 (Parámetros del ciclo) con rótulos es/en; verifica que la pantalla lo muestre y que se oculte o deshabilite `presion_cambio` si la UI ya tiene ese patrón (si no, déjalo visible).
- Migración al cargar que agrega los dos con su defecto si faltan.

## LIQ-04 Contrapresión de fábrica
`descompresion.modo_4.presion_camara_enfriamiento` y `modo_5.presion_camara_enfriamiento` = 300 kPa abs en `cycles/factory/liquidos.json` y `cycles/user/liquidos.json` (antes 250). Los demás programas no cambian. No se migran los programas ya instalados en equipos (decisión de Cristian: «de fábrica, se ajusta luego»). Comprueba que 300 cumple las reglas actuales (mínimo Psat(121) + 30 = 235; alivio 385).

## Cierre
- Pruebas: componente puro (orden aire → chaqueta → agua, enclavamientos, topes, sin lectura), LIQ-02 (armado, 10 s aviso, 60 s fallo, recuperación reinicia, falla cerrada, en protocolo solo aviso), LIQ-03 (activo/inactivo, sin lectura, coherencia), migraciones (idempotentes, auditoría, `.bak`), LIQ-04 y la pantalla del modo 5; suite completa en verde.
- Actualiza el texto de progreso de T30-02 solo si deja de ser correcto; si añades estados de la sub-etapa para la pantalla, textos es/en sin abreviar (D8-5.4).
- `CLAUDE.md` (sección «Tanda 32»), riesgos nuevos en `docs/riesgos/registro_riesgos.md` (ebullición por pérdida de contrapresión, golpe de ariete / choque térmico en chaqueta, aguja del modo 5 mal ajustada como residual de puesta en marcha), trazabilidad REQ, banco (bloque T32: presurización y despresurización con tiempos reales, ajuste de la aguja del modo 5 con la carga máxima sosteniendo el objetivo, prueba de LIQ-02 cortando el aire) e informe `docs/informes/tanda32/R32_informe.md` con todas las `DECISIÓN SIN CONFIRMAR`.
- Merge a `dev`. NO compiles: al cerrar, di que no se compiló y da el comando `python tools/entrega/compilar_entrega.py`.
- Último acto: `docs/informes/tanda32/CERRADO.txt` (fecha, commit del merge, suite). Bloqueo que necesite a Cristian: igual, con `BLOQUEADO:` en la primera línea.
