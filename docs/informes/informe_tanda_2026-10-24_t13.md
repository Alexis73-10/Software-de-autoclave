**Hay compilación I y se recomienda instalarla el lunes 26-oct EN LUGAR DE LA H.** La USB va armada desde `entrega/2026-10-24_i/usb/`, con `Autoclave_Setup_1.0.0-i.exe`. Siga la sección 8h del LEEME (H → I, o G → I si el equipo sigue en la G), deje marcada «Actualizar (conserva los datos)» y después siga el bloque T12 de la hoja de banco, que ya trae las cifras de la I.

# Tanda 13: índice (24-oct-2026, noche)

Mini-tanda VAP-01. La rama `tanda-13` salió de `dev` en d22a67f, que ya contenía la tanda 12 y la L0. Se unió a `dev` con `--no-ff` (1abcf28) y la suite en verde. La etiqueta es `inst-2026-10-24-i`. El estado detallado está en `docs/informes/tanda13/estado.md`. No hubo subagentes ni revisor.

## Resumen por etapa
| Etapa | Qué | Informe |
|---|---|---|
| A0 | Precondición cumplida (tanda 12 cerrada y en `dev`); rama y documentos (d054632) | `tanda13/estado.md` |
| S13 | `steam.py` con IAPWS-IF97 región 4: `Psat(134)` = 304,20 kPa (antes 302,26). Se escribieron 226 pruebas, primero en rojo; se recalcularon 11 tests; la suite dio **7817 passed** (b84e758) | `tanda13/S13_saturacion_if97.md` |
| K13 | Compilación **I** (incluye L0). Verificador neutro OK. Prueba de humo OK (2 pantallas, asistente de 9 pasos). Ensayos H → I y G → I OK (consigna mostrada a 134 °C: 304,2 kPa; chaqueta 328,2 kPa). Setup compilado y no ejecutado. SHA-256 y `usb/` listos | `tanda13/K13_compilacion_i.md` |
| Z | Unión a `dev`, push de `dev`, `tanda-13` y la etiqueta | este índice |

## Lo que cambia para el lunes
- Todos los umbrales derivados de Psat suben unos 2 kPa a 134 °C:
  - falla por presión baja de esterilización: 302,2 kPa;
  - techo con `presion_add` 9: 313,2 kPa;
  - consigna de chaqueta: 328,2 kPa;
  - entrada a sostener: P ≥ 302,2 kPa.
- La hoja de banco (bloque T12) ya está recalculada. F0 no cambia.
- La I trae también la **Licencia L0**: el asistente tiene el paso «Contraseñas» y aparece el aviso SIS-07 si una cuenta conserva la contraseña de fábrica. Para una instalación limpia, los códigos deben salir del `GeneradorCodigos.exe` nuevo (huella 1742ee57).

## DECISIONES SIN CONFIRMAR y preguntas
1. **`catalogo_parametros._psat`**: es la única excepción a «solo `steam.py`». Sin ella, un programa de usuario corrupto (temperatura fuera de la tabla) dejaba de cargar y su lugar lo ocupaba en silencio el programa de fábrica. Con ella sigue quedando DAÑADO, como antes. Ver S13 §4.1.
2. **Rango en presión de `t_saturacion_c`**: es el equivalente exacto del rango en temperatura de la decisión 3 (0,6117–22064 kPa). S13 §10.1.
3. **PREGUNTA:** una lectura viva por encima de 373,9 °C (sensor roto) ahora hace fallar el tick. El estado es seguro: se apagan las salidas y el ciclo termina en FALLO por temperatura alta o por tiempo límite. Pero el motivo inmediato solo queda en el log. Se propone, para la tanda 14, un filtro de plausibilidad de 0–200 °C que lo trate como «sin lectura». S13 §4.2.
4. Sigue abierto el **problema urgente 1 de la tanda 12** (techo frente a salida de RECUPERACION a 134 °C); la tabla nueva no lo cambia (decisión 8).
5. Siguen las 2 rojas ajenas de `test_config_correo`, que dependen de `data/correo_equipo.json` local, igual que en L0.
