Tanda 19 UNIDA a `dev` (junto con la tanda 18, merge 0bbc82f) y ENTREGADA como 1.0.0-alpha.3 (621a289, etiqueta `v1.0.0-alpha.3`; sin push).

# Índice — tanda 19 (27-oct-2026): enlace Modbus TCP con los módulos Ebyte M31-U

- Informe único: `docs/informes/tanda19/R19_informe.md`
- Estado: `docs/informes/tanda19/estado.md`; verificaciones V: `docs/informes/tanda19/V19_notas.md`; línea base: `docs/informes/tanda19/base_suite.txt`
- Anomalías de la entrega: `docs/versiones/anomalias_conocidas_1.0.0-alpha.3.md` (MED-01..03, AN-29..AN-32)
- Hoja de banco: bloque M en `docs/mis_plans/hoja_pruebas_banco_equipo_pruebas.md` (M-0 red, M-1..M-6)
- Riesgos: MED-01..MED-03 en `docs/riesgos/registro_riesgos.md`; SOUP: pymodbus 3.16.1 en `docs/riesgos/lista_soup.md`

## Para Cristian, primero

1. **La adenda del banco (`docs/mis_plans/adenda_tanda_19_banco.md`) no está aplicada**: con los datos reales, la alpha.3 no conecta con los módulos (principal como esclavo 0, firmware con prefijo, 0x0C37 contador, posible reinicio tras configurar). Hace falta la sesión corta de corrección antes de usarla en el banco (AN-32).
2. Pregunta abierta (AN-30, V19-s1-02): con Modbus, TARJETA_MODULOS_ORDEN o TARJETA_WATCHDOG en ciclo invalidan la conexión y el protocolo de fallo no puede ventear hasta reconectar. ¿Se acepta, o se pospone la invalidación durante el CICLO?
3. MED-01 (ALTA): exactitud de las PT100 del módulo (±1,1 °C a 134 °C) frente a umbrales de 0,1 °C / 1 K / 2 K; bloquea la liberación clínica hasta M-4.
4. Equipos serial ya instalados: el buzzer pasa a DO 25 (recablear) y `enlace_io.json` debe decir `serial`.
5. Push (no ejecutado): `git push origin dev v1.0.0-alpha.3` (y opcionalmente `git push origin tanda-18 tanda-19`).

Resultado de la suite: verde, 8838 recolectadas (8521 de la base + 317 nuevas); las únicas rojas fueron caídas de trabajador Qt en paralelo que pasan en serie. R: 0 hallazgos altos.
