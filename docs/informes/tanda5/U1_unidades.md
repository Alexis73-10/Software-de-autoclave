# U1 — Cambio de unidades (núcleo y selector) ★

## Qué se hizo
- **`core/runtime/unidades.py`** es el módulo único y neutral, sin Qt. Lo usan QML y lo usarán el ticket, el PDF y el correo (I3).
  - Temperatura en °C o °F. Kelvin no se ofrece.
  - Presión en kPa, bar o mbar, siempre absolutos, o en psi. En psi se muestra psig si P ≥ P_atm e inHg de vacío si P < P_atm. Nunca se muestra un psi negativo.
  - Las diferencias y tasas se convierten sin desplazamiento: Δ°F = 1,8·Δ°C y Δpsi = ΔkPa / 6,894757.
  - `P_atm` es `presion_admosferica` del equipo. Si no está disponible, en psi se muestra "—".
  - Entrada de datos (`*_a_interna`): un valor negativo en psig o inHg, o un psi sin P_atm, se rechaza.
  - `ConfigUnidades` guarda `data/unidades.json`. Si el archivo falta o es inválido, se usan °C y kPa.
- **Backend:**
  - `GET /units` devuelve las unidades y `p_atm` (null si no hay valor).
  - `PUT /units` lo pueden usar técnico e ingeniero, con auditoría `unidades_configuradas`. El admin recibe 403.
  - **En CICLO devuelve 409 a todos, también al ingeniero.** Es un cambio de presentación que en pleno ciclo se presta a una lectura errónea.
- **QML:**
  - Singleton `Autoclave.Unidades` (`ui_qml/bridge/unidades_qml.py`). Consulta `/units` cada 3 s en un hilo, así el cambio se ve en caliente en las dos pantallas del equipo de dos puertas.
  - Expone `temp`, `pres`, `dtemp`, `dpres` y `parametro`. Para la entrada: `unidadIngreso`, `aMostrar` / `aMostrarEn`, `aInterna` e `ingresosPsi`.
- **Selector** en OPCIONES › Parámetros del equipo: chips °C/°F y kPa / bar / mbar / psig-inHg, con texto de ayuda.
- **Parámetros del ciclo:**
  - Los valores en °C o kPa (actual, por defecto, mín. y máx., lista y nuevo valor) se muestran en las unidades elegidas.
  - El valor tecleado se convierte a la unidad interna, se redondea (2 decimales en float, entero en int) y se valida contra el mín./máx. internos antes de guardarse.
  - En psi, cuando el rango cruza la atmosférica, se ofrece elegir psig o inHg.

## NO se convierten
Lógica de control, alarmas, umbrales, BD, JSON, API y `audit_log` (guardan el valor interno con su unidad). Tampoco **Entradas/Salidas ni la calibración por sensor**, que siguen en °C y kPa absolutos con cuentas ADC (**DECISIÓN SIN CONFIRMAR U1-4**, por la decisión del 20-oct sobre E/S).

## Decisiones sin confirmar
- **U1-1:** resolución de presentación: °C/°F 1 decimal; kPa 1; bar 2; mbar 0; psig 1; inHg 1.
- **U1-2:** en psi, si el rango del parámetro cruza la atmosférica, se elige psig o inHg para ese ingreso; si no lo cruza, la unidad es fija.
- **U1-3:** un parámetro en °C o kPa se trata como **diferencia** si su nombre empieza por `rango_`, `brecha_`, `presion_add`, `temperatura_add`, `delta_`, `histeresis`, `margen`, `diferencia`, `banda` o `tolerancia`. Así quedan clasificados los perfiles actuales:
  - Absolutos: `temperatura_calentamiento`, `temperatura_esterilizacion`, `temperatura_estabilizacion`, `temperatura_enfriamiento`, `temp_max_apertura`, `presion_chaqueta`, `presion_precalentamiento`, `presion_alta/baja_pulso_*`, `presion_*_secado`, `presion_cambio`, `presion_camara_enfriamiento`.
  - Diferencias: `rango_calentamiento`, `presion_add_calentamiento`, `rango_temp_estabilizacion`, `rango_presion_estabilizacion`, `rango_temperatura_estabilizacion`, `brecha_*`, `presion_add_esterilizacion`, `rango_presion_ester`, `rango_temperatura_ester`, `rango_presion_chaqueta`, `rango_chaqueta_secado`.
  - Tasas (°C/min, kPa/min): se convierten como diferencias.
- **U1-4:** E/S y calibración, sin conversión (ver arriba).
- **U1-5:** en CICLO el cambio de unidades se rechaza también al ingeniero.

## Pendiente (va en I2/I3)
- Preciclo, Ciclo, gráficas, Historial, ticket, PDF y correo todavía muestran °C y kPa: pasan por el formateador en I2 (QML) e I3 (salidas del backend).

## Revisión (safety-reviewer)
Sin Críticos ni Altos. Nada de control, alarmas ni puertas importa el módulo.
- **Medio SAF-01:** la firma de `ingresosPsi` no coincidía con la llamada desde QML. En psi siempre se tecleaba en psig, así que no se podía ingresar un vacío y un 0 se guardaba como P_atm. **Corregido**, con una prueba que compara la firma con el QML.
- **Medio SAF-02:** si las unidades cambiaban con la ventana de ajuste abierta, lo tecleado se interpretaba en la unidad nueva. **Corregido:** `aInterna` usa la unidad fijada al abrir la ventana, y un cambio de unidades descarta lo tecleado y lo avisa.
- **Bajo SAF-03:** `rango_calentamiento` se usa como banda de temperatura y también de presión. **Ya no se convierte** (`SIN_CONVERSION`) y se muestra en su unidad original. Queda **PREGUNTA PARA CRISTIAN**: separarlo en dos parámetros.
- **Bajo SAF-04:** las diferencias pequeñas se veían iguales. Ahora llevan un decimal más en °F y psi (dos en total).
- ~~Pregunta 1 (chaqueta absoluta o manométrica)~~ **Resuelta** (decisión 1.2 de la tanda 6): el sensor de chaqueta es ABSOLUTO; lo fija `tests/test_c1d_chaqueta_absoluta.py`.
- **Pregunta 2:** P_atm fuera de 50–110 kPa ahora se trata como ausente (en psi se muestra "—"; el backend devuelve null).
- **Pregunta 3:** antes de convertir las lecturas en vivo (I2), conviene repetir esta revisión.

## Riesgo
Entrada **HAZ-UNI-01** en `docs/riesgos/registro_riesgos.md`.

## Pruebas
- `tests/test_u1_unidades.py` (64): ida y vuelta, diferencias, psig/inHg a ambos lados de la atmosférica y justo en ella, P_atm ausente, rechazo de psi negativo, resolución, clasificación, prueba estática de importaciones, configuración y endpoints (permisos, 409 en ciclo, 422, cambio en caliente).
- `tests/test_u1_unidades_qml.py` (8).
