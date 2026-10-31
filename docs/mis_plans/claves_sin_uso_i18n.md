# Claves de es.json sin uso (D-19)

Generado por `tools/claves_sin_uso_i18n.py` el 14/10/2026. **Solo lista: no se borra ninguna clave sin autorización de Cristian.**

- Claves de texto en `src/autoclave/i18n/es.json`: 383
- Sin uso detectado: 11

Criterio (conservador): una clave cuenta como usada si aparece completa en un .qml o en el Python de alcance D-02, si empieza por el prefijo de una familia dinámica que aparece en ese código, o si la lee por su nombre corto un generador de PDF de `ui_qml/exportacion`. Puede haber claves que el script da por usadas sin que lo estén (p. ej. toda una familia dinámica), pero no al revés salvo usos fuera de ese código (vistas PySide, tkinter).

## Claves sin uso

| Clave | Texto en español |
|---|---|
| `modulos.programas` | PROGRAMAS |
| `modulos.impresion` | IMPRESIÓN |
| `modulos.mantenimiento` | MANTENIMIENTO |
| `modulos.conectividad` | CONECTIVIDAD |
| `sensores` | (list de 5 elementos) |
| `acciones.guardar` | Guardar cambios |
| `acciones.restablecer` | Restablecer valores |
| `acciones.reconocer` | Reconocer |
| `acciones.borrar` | Borrar |
| `exportacion.duracion` | Duración |
| `sistema.modo_prueba` | MODO PRUEBA ACTIVO — los ciclos no son válidos para carga estéril |

## Prefijos de familias dinámicas encontrados

- `arranque.`
- `equipo.`
- `estados.`
- `exportacion.impresora_`
- `fases.`
- `formulario.`
- `instalacion.`
- `instalacion.clase_`
- `instalacion.paso_`
- `instalacion.puerta_`
- `instalacion.puerta_pc_`
- `instalacion.sonda_`
- `instalacion.sum_`
- `instalacion.vapor_`
- `menu.`
- `menu.resultado_`
- `opciones.secciones.`
- `reportes.`
- `sesion.`
- `teclado.`
- `validacion.`
