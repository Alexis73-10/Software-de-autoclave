# P2 — Interruptor `impresora.habilitada`

- Nueva pantalla **OPCIONES › Parámetros del equipo** (`OpcionesParametrosEquipo.qml`, `ParametrosEquipoController`), con diseño PROVISIONAL. Tiene el interruptor "Impresora habilitada" sobre `GET/PUT /printer/config` (B5). Lo editan técnico e ingeniero; el técnico no puede hacerlo en CICLO, igual que en el resto de Opciones. La auditoría `impresora_configurada` en `audit_log` ya existía.
- El aviso SIS-05 sigue a la bandera sin reiniciar. `VigilanciaImpresora.aplicar_configuracion()` lo retira al deshabilitar y verifica de nuevo, en un hilo, al habilitar. El endpoint la llama a través de `context.aplicar_config_impresora()`.
- `habilitada` ahora es `StrictBool`: rechaza `"false"`, `0` y `null`, igual que SAF-06.
- Valor por defecto: habilitada. Si el archivo no existe, se toma como habilitada; el equipo de pruebas lleva impresora.
- Textos nuevos es/en (`opciones.equipo_*`), anotados como "sin revisar".

**DECISIÓN SIN CONFIRMAR P2-1:** el admin no ve la sección. La instrucción de P2 dice "admin solo lectura", pero O1 y U-7 dicen que el admin no ve las secciones técnicas, así que se dejó lo más restrictivo. Para revertir: agregar `ROL_ADMIN` a los roles de `parametros_sistema` en `permisos_opciones.py` y devolver `False` en `edicion_permitida` para el admin en esa sección.

Pruebas: `tests/test_p2_parametros_equipo.py` y 3 pruebas nuevas en `tests/test_b5_aviso_impresora.py` (interruptor aplicado de inmediato, el endpoint lo aplica, solo booleanos JSON).
