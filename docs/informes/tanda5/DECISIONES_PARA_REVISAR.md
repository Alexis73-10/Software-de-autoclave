# Tanda 5: decisiones para revisar (20-oct-2026)

## Resumen
1. E0: el trabajo de la otra sesión quedó en `dev`, en 8 commits por tema. No había churn de saltos de línea.
2. P1: el modo prueba se cierra por cualquier camino. Se corrigió el Alto TMG-01, un bloqueo de 5 s al cerrar.
3. P2: impresora habilitada en Parámetros del equipo. El admin **no ve** la sección (P2-1).
4. P3: renovación del token en PySide. El reingreso solo admite al mismo usuario y usa `QInputDialog` (P3-1).
5. O1: defectos del hospital, gestión de programas y entradas mostradas. La auditoría se revierte si falla. Las entradas todavía no se usan en Preciclo.
6. T1: matriz de transiciones y una corrección de seguridad: en líquidos el venteo de sobrepresión va por la **lenta** (D-19). Hay 12 preguntas abiertas para Cristian (abajo).
7. U1: unidades solo en presentación, con prueba estática. En ciclo se rechaza el cambio incluso al ingeniero (U1-5). La clasificación absoluto/diferencia va por nombre (U1-3).
8. I1: las 49 alarmas en es/en por código y parámetros, e idioma persistente. Siguen pendientes los motivos de puerta, los parámetros de `motivo_fallo` y `nombre_clave`.
9. I2/I3: literales QML y lecturas de Preciclo/Ciclo en la unidad elegida; ticket en idioma y unidades. Siguen pendientes las gráficas, el PDF y el correo.
10. O2 no se hizo. H1 ya tiene las pruebas nuevas. Push: ver estado.md.

Formato de cada entrada: decisión · motivo · alternativa · commit · cómo revertir.

| Id | Decisión | Motivo | Alternativa | Commit | Cómo revertir |
|---|---|---|---|---|---|
| E0-1 | No se agregó `.gitattributes` | No había churn de CRLF/LF | Añadir `* text=auto` en un commit aparte | — | Commit nuevo con el archivo |
| E0-2 | No se commitearon `cycles/user/bowe_dick.json`, `docs/catalogo_alarmas.2026-09-18.bak.md` ni `images/icono autoclave.jpg` | Parecen ediciones de prueba, un respaldo y un nombre con espacio. Además, `bowe_dick.json` (fábrica y usuario) lo está editando otra sesión ahora | Commitearlos | — | `git add` por ruta |
| P2-1 | El admin no ve Parámetros del equipo | O1 y U-7: el admin no ve secciones técnicas | Admin en solo lectura | 9681aee | Agregar `ROL_ADMIN` a `parametros_sistema` y `edicion_permitida` en False para el admin |
| P3-1 | El login de reintento en PySide usa `QInputDialog` | No hay teclado PySide reutilizable | Teclado propio | 2030a81 | Reemplazar `pedir_credenciales_dialogo` |
| O1-2 | Las escrituras de gestión de programas van dentro del lock de la máquina | Evita la carrera con `/cycle/select` | Dos fases con revalidación | 3f551ed | Mover la escritura fuera de `guard_estado` |
| U1-1 | Resolución: °C/°F 1; kPa 1; bar 2; mbar 0; psig 1; inHg 1 (diferencias en °F/psi con 2) | Legibilidad | Otra tabla | a78bdee | `DECIMALES` en `unidades.py` |
| U1-2 | En psi, psig o inHg a elegir si el rango cruza la atmosférica | Nunca un psi negativo | Ingreso siempre en kPa | a78bdee | `unidades_de_ingreso_psi` |
| U1-3 | Absoluto o diferencia según el prefijo del nombre (`rango_`, `brecha_`, `presion_add`…). `rango_calentamiento` no se convierte | El JSON no lo distingue | Campo `clase` en el JSON | a78bdee | `_PREFIJOS_DIFERENCIA`, `SIN_CONVERSION` |
| U1-4 | E/S y calibración no se convierten | Decisión del 20-oct sobre E/S | Convertir | a78bdee | — |
| U1-5 | En CICLO no se cambian las unidades, ni siquiera el ingeniero | Riesgo de leer mal un valor | Permitirlo al ingeniero | a78bdee | `guard_estado(..., excepcion_ingeniero=True)` en `put_units` |
| I1-1 | `GET /language` sin sesión | Lo necesitan login y espera | Exigir sesión | 2ecb0e3 | `Depends(requiere_rol())` |
| I3-1 | Ticket en psi: vacío en inHg con sufijo "v" en la misma columna | Ningún negativo; ancho fijo | Dos columnas | (commit de I3) | `_pres_fila` |
| I3-2 | El ticket en tiempo real usa la presentación vigente al iniciar el ciclo | Que todo el ticket quede coherente | Leerla en cada fila | (commit de I3) | `CycleLogger._presentacion` |

## PREGUNTAS PARA CRISTIAN (T1: no se cambiaron)
- **P-1:** el ack de COMPLETADO no exige cámara segura y no hay estado seguro después. *Rec.:* entrar a ES si la cámara no está segura.
- **P-2:** CIC-10 en la práctica exige técnico (reasignar la sonda), lo que contradice D-06. *Rec.:* ofrecer al operador "continuar con la referencia" o "ventear con la lenta".
- **P-3:** una trama DI vencida aborta el ciclo de inmediato y queda como EMERGENCIA. *Rec.:* tolerancia de 5 s y registrarla como fallo de conexión.
- **P-4:** el campo `bloquea_inicio` del catálogo no se usa. *Rec.:* que PREPARADO consulte `has_blocking_alarm()`.
- **P-5:** al salir de FALLA se resuelven también COM-02 y COM-03, que son de despeje manual. *Rec.:* no resolverlas por reinicio.
- **P-6:** el ack hace también de "Confirmar y llevar a estado seguro". *Rec.:* mostrar el texto de §15.2 en ese diálogo.
- **P-7:** `/cycle/abort` responde "ok" sin efecto cuando hay resultado pendiente o paro. *Rec.:* responder 409.
- **P-8:** HIBERNACION y EMERGENCIA son estados inalcanzables. *Rec.:* retirarlos.
- **P-9:** no se puede reimprimir el ticket de un ciclo INTERRUMPIDO. *Rec.:* permitirlo desde Historial.
- **P-10:** al arrancar con la cámara no segura solo sirve `/safe-state/confirm`. Verificar el botón en el equipo (H1 C-05).
- **P-11:** la cancelación vuelve a PREPARADO (como dice la spec). Se anota.
- **P-12:** en líquidos, el drenaje a presión atmosférica sigue por la rápida. ¿Aplica D-19 también ahí?
- **U1:** ¿el sensor de chaqueta es absoluto o manométrico? ¿Se separa `rango_calentamiento` en temperatura y presión?
