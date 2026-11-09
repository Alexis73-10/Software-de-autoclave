# Informe PRI: programa Prion 134 °C / 30 min (9-nov-2026)

Rama `ciclo-prion`, sin unir a `dev`, sin compilar. Pendiente: revisor de seguridad (la siembra toca `src/`) y merge.

## Cambios
- `src/autoclave/cycles/{factory,user}/prion.json`: programa 6, copia de Instrumental 134 con `cycle_id` `prion`, nombre «Prion 134°C», exposición 30 min y secado 30 min (F0 off, sólido, sin apertura automática, ya vigentes). `nombre_clave` solo en fábrica. i18n es/en: `ciclos_fabrica.prion.nombre`.
- **Decisión (a) de Cristian, siembra al cargar (PRI-05):** el inventario mostró que `cycles/factory` se refresca siempre en el equipo, pero `cycles/user` solo se siembra en la primera instalación, y la selección y edición exigen `source == "user"`; sin siembra Prion saldría solo en Opciones › Programas, sin poder elegirse. `utils/resources.sembrar_faltantes_usuario(raiz_ciclos)`, llamada desde `CycleManager.load_all_cycles` tras cargar fábrica y antes de usuario, copia a `cycles/user` los programas de fábrica no «vistos»:
  - sin `nombre_clave`, escritura atómica (.tmp + replace);
  - no pisa por mismo id, mismo número ni mismo archivo (aviso en el log);
  - marca `cycles/user/fabrica_vistos.lst` (extensión no `.json` para que el cargador no la lea como programa): lista de ids de fábrica ya procesados. Un programa borrado por el hospital no se recrea. La siembra inicial (primera instalación) también la escribe. Sin marca rigen como vistos los 5 programas anteriores (`bowe_dick`, `134_instrumental`, `instrumental_121`, `liquidos`, `textiles`), de modo que ni un legado borrado se recrea;
  - nunca lanza: cualquier error es un aviso en el log y se reintenta en el siguiente arranque (si falla la escritura no se marca como visto); sin `user` o sin `factory` no hace nada ni crea carpetas;
  - `.gitignore`: `src/autoclave/cycles/user/fabrica_vistos.lst`.
- Documentación: CLAUDE.md «Programa Prion (9-nov)», HAZ-PRI-01 (nombre, validación a cargo de Especifika, ISO 17665) y HAZ-PRI-02 (siembra), REQ-106, bloque PRI (PRI-01 ciclo, PRI-02 siembra) en la hoja de banco.

## Inventario resumido
- Nada en `src/` fija «5» programas ni rechaza `cycle_number` 6. Los `.spec` empaquetan `cycles/factory` entero. Detalle en `inventario.md`.
- `tools/asignar_programas_tuttnauer.py` e `importar_ciclo_tuttnauer.py`: solo mapean nombres de ciclos Tuttnauer importados; Prion no existe allí, sin cambio.

## Planta simulada (caudal abierto, valores provisionales; CALENTAMIENTO + ESTERILIZACION, el secado no se modela)
| Modo | Resultado | Inicio ESTERILIZACION | Duración ESTERILIZACION | Aislamientos | T Principal min / máx | P mín |
|---|---|---|---|---|---|---|
| cámara | COMPLETADO | 219 s | 1800,5 s | 0 | 134,30 / 134,88 °C | 312,0 kPa |
| chaqueta | COMPLETADO | 196 s | 1800,5 s | 0 | 134,50 / 134,63 °C | 310,7 kPa |
Sin alarma ni motivo en ningún modo (el resultado de la planta no expone los avisos no bloqueantes). SECADO: 30 min por parámetro (la planta no lo simula); queda para el banco PRI-01.

## Pruebas dedicadas (sin suite completa)
- Nuevas: `tests/test_pri_programa_prion.py` (valores, igualdad con Instrumental 134, i18n, carga limpia, planta cámara y chaqueta) y `tests/test_pri_siembra_faltantes.py` (equipo actualizado, selector, no pisa editado ni mismo número, idempotencia y no recrear lo borrado, legado sin marca, marca no es programa, sin `user`, sin fábrica, no escribible con reintento, fábrica ilegible, equipo nuevo igual que antes).
- Modificadas: `tests/test_t11_programas_integracion.py` (numeración con 6 programas, dos aserciones: [1..6] y mapa con `6: "prion"`), `tests/test_t12_opciones_parametros.py` (`/programas` devuelve [1..6]). `test_b6_selector_ciclo_backend.py` usa programas simulados, sin cambio; `test_t9_e9_refresco_config_fabrica.py` pasa sin cambio (compara con lo que trae fábrica).
- Corridas en verde: las anteriores más `test_t32_catalogo_migraciones`, `test_cri_migracion`, `test_i18n_linea_base`, `test_s2_cycle_select`, `test_c2_programas_persistentes`, `test_o1_gestion_programas`, `test_t17_copia_programa`, `test_t9_e9_entrega_neutra`, `test_t16_s4_programas`, `test_t15_rutas_equivalentes`, `test_arquitectura_capas`, `test_pam_planta`, `test_cri_planta`. No se corrió la suite completa.

## DECISIÓN SIN CONFIRMAR
- Regla PRI-06: un programa de usuario conserva su número frente a uno de fábrica con el mismo número; el de fábrica cede (queda sin número y fuera de la lista, con aviso en el log y sin `fabrica[6]`/`defecto(6)`). Aplica a cualquier número, también a futuros programas de fábrica y a programas Tuttnauer con el 6.
- La siembra no usa un número ocupado (programa de usuario o `numeros_usados.json`) y no siembra mientras haya un JSON de usuario o `numeros_usados.json` ilegible (aviso, reintento en el arranque siguiente).
- Prion se escribe y la marca se guarda con flush+fsync antes de `os.replace`.
- Nombre «Prion 134°C».
- Marca de «vistos» y el conjunto de 5 legados fijados en código; un equipo sin marca donde el hospital reasignó el número 6 no recibe Prion (aviso en el log).
- Los programas de fábrica nuevos futuros se sembrarán igual (comportamiento general de la siembra).

## DECISIÓN PENDIENTE
- MEDIA-3 (`habilitado` false de Prion en equipos actualizados), MEDIA-4 y el cambio de nombre: decisiones de Cristian, no implementadas.
- Revisión de seguridad de la siembra (toca `src/`).
- Banco PRI-01/02 y validación del proceso/rotulado (HAZ-PRI-01).
- Ajeno: `src/autoclave/ui_qml/qml/Pantallas/PantallaCicloEnCurso.qml` aparece modificado en el árbol por otra sesión; no es de esta rama y no se comiteó.
