# Menú de instalación — requisitos de UI y pantallas (borrador v1, 12-oct-2026)

> **Adenda 2026-10-14 (tanda, T2/E1b):** `vapor_source` ya existe en el perfil, la validación y `storage`. Valores `generator | boiler | mixed` (no `interno | externo | mixto`); la UI y las claves `instalacion.vapor_*` se renombraron igual. La salida de la fuente ausente se bloquea en `SetOutput.set_output`. Campo ausente = ambas salidas (perfiles anteriores).

Reemplaza el asistente tkinter `installation/wizard.py`. Solo UI: el puente Python y la integración con el arranque quedan fuera (ver §6).

## 1. Cómo funciona hoy (código)

- `main.py` (y `ui/main.py`): si `get_installation_profile()` devuelve `None` (no existe o es inválido) lanza `launch_installation_wizard()`; si no se completa, el software se cierra. Si el reloj es anterior a `created_at`, error y cierre (`clock_guard`).
- El asistente tiene 5 pasos: (1) serie + código de activación, (2) clase de equipo, (3) puertas, (4) enfriamiento (se omite si `cooling_level_max == 0`), (5) datos finales.
- Código de activación: HMAC-SHA256 de `serie:fecha` → 12 caracteres base32; **solo válido el día de emisión** (`activation.py`).
- Clases (`equipment.py`): `mesa_n`, `mesa_b`, `mesa_b_lab`, `piso`, `piso_lab`, con capacidades (vacío, chaqueta, líquidos, `door_count_max`, `cooling_level_max`). Al elegir la clase se recortan puertas y enfriamiento.
- Puertas: `door_count` 1–2 (fijo en 1 si la clase solo admite una) y `door_type` (`simple`, `motorized`, `locking`, `motorized_locking`, `advanced`); `door_id` = puerta que gestiona este PC.
- Datos: `model_id`; `supply_inputs` (5 entradas, todas activas por defecto: falla cerrada); `temperature_probes` (4 sondas; `temp_camara` obligatoria, no se puede desactivar).
- Al instalar: `delete_profile()` + `save()` con `locked=True`; después el perfil no se puede cambiar desde el software (solo `tools/declarar_*.py`, con respaldo y registro).
- `factory_dialog.py` (clave de fabricante) existe pero **no lo llama nadie**.

## 2. Pantallas creadas

Archivo `ui_qml/qml/Pantallas/Instalacion.qml` (una pantalla con pasos). Mismo lienzo, tema, tarjeta blanca y botones que Nuevo Usuario/Opciones; textos en `es.json` sección `instalacion`.

| # | Paso | Contenido |
|---|---|---|
| 1 | Activación | Serie y código (teclado alfanumérico, máx. 20 y 12), errores bajo el campo |
| 2 | Tipo de equipo | 5 tarjetas con chips de capacidades (vacío, chaqueta, líquidos, puertas) |
| 3 | Puertas | Número de puertas (fijo si la clase admite una), tipo de puerta, puerta de este PC (solo con 2) |
| 4 | Enfriamiento | Nivel 0…máximo de la clase; se omite si el máximo es 0 |
| 5 | Fuente de vapor | Generador interno / caldera externa / mixto (**nuevo**) |
| 6 | Datos | Modelo, 5 interruptores de suministro, 4 de sondas (cámara 1 bloqueada con candado) |
| 7 | Resumen | Todos los datos, aviso de perfil bloqueado, confirmación antes de escribir |
| — | Resultado | Instalación completada (señal `instalacionCompletada`); error de guardado se muestra en el resumen |

Componentes nuevos en `Componentes/`: `CampoFormulario`, `OpcionTarjeta`, `SelectorSegmentos`, `FilaInterruptor`, `IndicadorPasos`, `BotonFormulario`. Sin barra de navegación ni campana: aún no hay sesión ni backend.

Capturas: `docs/mockups/instalacion/`.

## 3. Cambios respecto al asistente actual (por revisar)

- **INS-01** El tipo de equipo, el tipo de puerta y la fuente de vapor empiezan **sin selección** y son obligatorios (hoy vienen preseleccionados `mesa_b` y `advanced`, lo que permite instalar un perfil equivocado sin darse cuenta). El nivel de enfriamiento sigue en 0 y los interruptores en "activo" (falla cerrada).
- **INS-02** "Puerta de este PC" solo aparece con 2 puertas (hoy aparece siempre y con clase de 2 puertas permite 2 aun con `door_count=1`).
- **INS-03** Se agrega resumen + confirmación antes de escribir un perfil que queda bloqueado.
- **INS-04** El código de activación no tiene límite de intentos en el código actual; no se agregó.

## 4. Fuente de vapor (nuevo campo)

Decisión registrada: el menú debe permitir elegirla para cualquier equipo (interno, externo, mixto) y se elimina la salida de vapor de la fuente que el equipo no tiene (en mixto quedan las dos). El campo `vapor_source` **aún no existe** en `InstallationProfile`, `validate_profile_data` ni `storage`; la UI ya lo envía en el perfil (`interno | externo | mixto`). Corresponde a la etapa E1b.

## 5. Contrato con el puente (`puente`)

- `clases`: lista de `{valor, vacio, chaqueta, liquidos, puertasMax, enfriamientoMax}` (de `get_capabilities`).
- `validarCodigo(serie, codigo) -> bool` (`validate_installation_code`; registrar el intento inválido en el log, como hoy).
- `instalar(perfil) -> {ok, error}`; `perfil` usa los nombres de `installation_profile.json`: `serial_number` (mayúsculas), `model_id`, `equipment_class`, `door_count`, `door_type`, `door_id`, `cooling_level`, `vapor_source`, `supply_inputs`, `temperature_probes`. El puente completa `machine_id`, `role`, `created_at`, `locked`.
- Señal `instalacionCompletada()`: hoy el texto dice "Reinicie el software"; el host decide.

## 6. Pendiente

1. Puente Python real y llamada desde el arranque QML (ARR-02 / MIG-07); retirar `wizard.py` después.
2. Campo `vapor_source` en perfil, validación y salidas por fuente (E1b).
3. Diálogo de clave de fabricante: ¿se necesita? Hoy no se usa.
4. Catálogo en inglés (`planeacion_i18n.md`): las cadenas nuevas están en `es.json`; falta la traducción.
5. Probar con el teclado real (`python -m autoclave.ui_qml.prueba_instalacion`): el render se verificó con un teclado simulado.
6. Nombres de los tipos de puerta: etiquetas provisionales a partir del enum; confirmar con el equipo.
