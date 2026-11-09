# Inventario PRI (9-nov)

## Qué fija la lista/cantidad de programas de fábrica
- Código: ninguno fija «5» ni un tope de `cycle_number` (`CycleManager._load_from_folder` carga todo `*.json`; `_descartar_numeros_repetidos` solo rechaza repetidos). 6 es un número libre (1..5 ocupados). Ninguna validación rechaza un programa de fábrica 6 en `src/`.
- Pruebas que enumeran: `test_b6_selector_ciclo_backend.py:146`, `test_t11_programas_integracion.py:174`, `test_t12_opciones_parametros.py:40` (esperan [1..5]); `test_t9_e9_refresco_config_fabrica.py:82` (compara con fábrica, debería seguir). Sin actualizar aún (el plan se detuvo tras el paso 3).
- Herramientas: `tools/asignar_programas_tuttnauer.py`, `importar_ciclo_tuttnauer.py` (sin revisar a fondo), `verificar_entrega_neutra.py` (revisa cycles/factory).
- Empaquetado: `.spec` incluyen la carpeta `cycles/factory` completa (el archivo nuevo va solo).

## Cómo llega un programa de fábrica nuevo a un equipo ya instalado
- `utils/resources._sembrar`: `autoclave/cycles/factory` es `_SOLO_FABRICA`: se copia SIEMPRE desde el paquete → `prion.json` aparece en `cycles/factory` del equipo.
- `cycles/user` NO se toca: `_sembrar_usuario_desde_fabrica` solo corre si `cycles/user` no existe (primera instalación). En un equipo ya instalado nadie crea `user/prion.json`.
- Efecto: `CycleManager` carga `prion` con `source="factory"`. `GET /programas` lo lista (origen fábrica, `editable` false), pero `GET /programas/seleccionables` (`programas.py:110`) y `POST /cycle/select` (`ciclo.py:119`, 422 `programa_de_fabrica`) solo admiten `source == "user"`. Es decir: aparece en Opciones › Programas pero NO en el selector de Preciclo ni se puede ejecutar ni editar. Solo equipos nuevos (con siembra) lo tendrían operativo.
- Resuelve la decisión de Cristian: ver R_informe / CERRADO (DECISIÓN PENDIENTE).
