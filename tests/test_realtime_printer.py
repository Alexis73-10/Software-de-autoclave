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

    assert llamadas == [("linea 1", "Impresora_Test")]


def test_excepcion_en_print_raw_no_detiene_el_worker(monkeypatch, caplog):
    llamadas = []

    def fake_print_raw(text, printer_name):
        llamadas.append(text)
        if text == "falla":
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

    assert llamadas == ["falla", "linea despues del fallo"]
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
