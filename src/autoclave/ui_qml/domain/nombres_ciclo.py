# ui_qml/domain/nombres_ciclo.py
#
# I4 (tanda 6, parte QML): nombre de un programa en el idioma vigente.
#   1. Si el backend mandó `nombres: {es, en}` (GET /cycle, /programas), el del idioma.
#   2. Si no (Historial: la BD guarda el nombre tal como se llamaba el programa),
#      un nombre que coincide con el de un ciclo de fábrica en español se
#      muestra con el de ese ciclo en el idioma vigente.
#   3. Si no, el nombre tal cual (un programa renombrado se ve igual en los dos
#      idiomas, plan i18n §3.7).
# Nunca lanza: ante cualquier problema devuelve el nombre recibido.


def _idioma(idioma: str | None) -> str:
    from autoclave import i18n
    return idioma if idioma in i18n.IDIOMAS else i18n.idioma()


def nombre_programa(nombre, nombres=None, idioma: str | None = None):
    try:
        from autoclave import i18n
        lang = _idioma(idioma)
        if isinstance(nombres, dict):
            v = nombres.get(lang)
            if isinstance(v, str) and v:
                return v
        if not isinstance(nombre, str) or not nombre:
            return nombre
        fabrica = i18n.valor("ciclos_fabrica", i18n.IDIOMA_BASE)
        destino = i18n.valor("ciclos_fabrica", lang)
        if isinstance(fabrica, dict) and isinstance(destino, dict):
            buscado = nombre.strip().casefold()
            for clave, d in fabrica.items():
                es = d.get("nombre") if isinstance(d, dict) else None
                if isinstance(es, str) and es.casefold() == buscado:
                    otro = destino.get(clave)
                    traducido = otro.get("nombre") if isinstance(otro, dict) else None
                    if isinstance(traducido, str) and traducido:
                        return traducido.upper() if nombre.isupper() else traducido
        return nombre
    except Exception:
        return nombre
