# Tanda 28, flujo D — informe

## A11. Card del cursor de la gráfica (5-nov)

**Qué cambió.** La card (globo) del cursor de `GraficaCiclo.qml` ya no tiene posición fija (cubría las curvas y la línea del cursor). La posición la calcula la función pura `ui_qml/domain/posicion_card.py::posicionar_card`, que llega a QML por el singleton `Autoclave.PosicionCard` (`bridge/posicion_card_qml.py`, registrado en `bridge/__init__.py`); QML solo dibuja en `pos.x`/`pos.y` y pasa los puntos de las curvas (`_curvasCerca`, con el vecino de cada lado para no perder tramos largos).

**Regla (`DECISIÓN SIN CONFIRMAR`, interpretación del prompt).**
- La card queda entera a un costado de la línea del cursor (reserva = radio del punto + 8 px): nunca tapa el cursor.
- Candidatos por lado (el de más espacio primero; derecha si empatan) y 25 alturas dentro del área de trazado (68..1059 x yArriba..yAbajo): se prueban de la mitad opuesta a los puntos de las curvas hacia la otra; gana la primera sin cruce con ninguna curva (se miden los segmentos, no solo los puntos).
- Un lado que no cabe entero no es candidato; si ninguna posición queda libre, se elige la de menor cruce (`libre = False`). El prompt decía «si no cabe, al costado»: aquí la card siempre va al costado, porque colocarla encima del cursor lo taparía.
- Ancho y alto de la card no cambian (AJ-03 sigue igual); colores solo de `Colores`, sin `elide`.

**Pruebas.** `tests/test_t28d_posicion_card.py` (14: curvas altas, bajas, cruzadas, sin hueco, bordes, datos inválidos, tramo largo) y `tests/test_t28d_card_grafica_qml.py` (en QML, claro y oscuro: dentro del área, sin tapar el cursor, con hueco). Capturas en `capturas/card_{altas,bajas,cruzadas}_{claro,oscuro}.png` (`A11_CAPTURAS=1`; en offscreen la sombra `layer` no se pinta, la prueba la quita solo para la captura).

**Hallazgos.**
- AJ28D-01 (BAJA): con curvas que ocupan todo el alto a ambos lados del cursor no hay hueco y la card cubre lo mínimo posible; es el límite de la regla.
- AJ28D-02 (BAJA): el cálculo corre en cada movimiento del cursor (≈3 × hasta ~950 puntos filtrados al rango de la card); sin medir en el equipo real.

**Banco (T28, pendiente).** Arrastrar el cursor sobre un ciclo real en las dos pantallas táctiles: la card no cubre curvas ni cursor en los extremos izquierdo y derecho, con curvas altas, bajas y cruzadas, en claro y oscuro; fluidez del arrastre.
