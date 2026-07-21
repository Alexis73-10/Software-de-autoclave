import logging


def test_enqueue_envia_texto_a_print_raw(monkeypatch):
    llamadas = []

    def fake_print_raw(text, printer_name):
        llamadas.append((text, printer_name))
        return True

    monkeypatch.setattr(
        "autoclave.devices.printer.realtime_printer.print_raw", fake_print_raw
    )
    from autoclave.devices.printer.realtime_printer import RealtimePrinter

    rp = RealtimePrinter(printer_name="Impresora_Test")
    rp.enqueue("linea 1")
    rp._queue.join()

    assert llamadas == [("linea 1\n", "Impresora_Test")]


def test_excepcion_en_print_raw_no_detiene_el_worker(monkeypatch, caplog):
    llamadas = []

    def fake_print_raw(text, printer_name):
        llamadas.append(text)
        if text == "falla\n":
            raise RuntimeError("impresora desconectada")
        return True

    monkeypatch.setattr(
        "autoclave.devices.printer.realtime_printer.print_raw", fake_print_raw
    )
    from autoclave.devices.printer.realtime_printer import RealtimePrinter

    rp = RealtimePrinter()
    with caplog.at_level(logging.WARNING, logger="autoclave.devices.printer.realtime_printer"):
        rp.enqueue("falla")
        rp.enqueue("linea despues del fallo")
        rp._queue.join()

    assert llamadas == ["falla\n", "linea despues del fallo\n"]
    assert "error inesperado al imprimir" in caplog.text


def test_print_raw_false_loguea_warning_y_continua(monkeypatch, caplog):
    monkeypatch.setattr(
        "autoclave.devices.printer.realtime_printer.print_raw",
        lambda text, printer_name: False,
    )
    from autoclave.devices.printer.realtime_printer import RealtimePrinter

    rp = RealtimePrinter()
    with caplog.at_level(logging.WARNING, logger="autoclave.devices.printer.realtime_printer"):
        rp.enqueue("linea")
        rp._queue.join()

    assert "print_raw devolvió False" in caplog.text


def test_fragmentos_consecutivos_quedan_separados_por_salto_de_linea(monkeypatch):
    """Reproduce el bug reportado: el ticket de ciclo en tiempo real encola el
    encabezado y cada fila por separado (a diferencia de la reimpresión, que
    arma un único string con "\\n".join() antes de imprimir). format_header()
    y format_row() no terminan en salto de línea (están pensados para unirse
    con "\\n".join()); si RealtimePrinter no garantiza el salto al encolar,
    fragmentos consecutivos llegan pegados a la impresora física."""
    llamadas = []

    def fake_print_raw(text, printer_name):
        llamadas.append(text)
        return True

    monkeypatch.setattr(
        "autoclave.devices.printer.realtime_printer.print_raw", fake_print_raw
    )
    from autoclave.devices.printer.realtime_printer import RealtimePrinter

    rp = RealtimePrinter()
    rp.enqueue("encabezado sin salto")  # simula format_header()
    rp.enqueue("fila sin salto")        # simula format_row()
    rp._queue.join()

    texto_fisico = "".join(llamadas)  # lo que realmente concatena la impresora
    assert texto_fisico == "encabezado sin salto\nfila sin salto\n"


def test_fragmento_que_ya_termina_en_salto_no_se_duplica(monkeypatch):
    """format_footer() ya termina en salto de línea (las 5 líneas en blanco
    para el corte de papel); enqueue() no debe agregarle un salto extra."""
    llamadas = []

    def fake_print_raw(text, printer_name):
        llamadas.append(text)
        return True

    monkeypatch.setattr(
        "autoclave.devices.printer.realtime_printer.print_raw", fake_print_raw
    )
    from autoclave.devices.printer.realtime_printer import RealtimePrinter

    rp = RealtimePrinter()
    rp.enqueue("pie con saltos\n\n\n\n\n")
    rp._queue.join()

    assert llamadas == ["pie con saltos\n\n\n\n\n"]
