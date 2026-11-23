# services/domain/exportacion/pdf_basico.py
#
# Modo fábrica, Etapa 4: escritor de PDF mínimo en Python puro (sin Qt ni
# bibliotecas externas), para que el backend pueda generar el paquete de
# liberación. El PDF del correo (ui_qml/exportacion/pdf_ciclo.py) dibuja con
# QPainter sobre QPdfWriter y necesita un QGuiApplication, que el proceso del
# backend no tiene; además la capa backend no puede importar la interfaz
# (tests/test_arquitectura_capas.py). DECISIÓN SIN CONFIRMAR (E4-D1).
#
# Alcance: páginas A4, las 4 fuentes estándar de PDF (Helvetica y Courier, con
# su negrita) en WinAnsiEncoding (cp1252: cubre el español y «°»; lo que no
# entra sale como «?»), texto, líneas, polilíneas y rectángulos. Coordenadas
# en puntos con el origen ARRIBA a la izquierda (y crece hacia abajo). La
# salida es determinista (sin fechas de creación): mismo contenido, mismos
# bytes.

import zlib

ANCHO_A4 = 595.28
ALTO_A4 = 841.89

FUENTES = {"normal": ("F1", "Helvetica"), "negrita": ("F2", "Helvetica-Bold"),
           "mono": ("F3", "Courier"), "mono_negrita": ("F4", "Courier-Bold")}
# ancho de un carácter de Courier en unidades de la fuente (1000 = tamaño)
ANCHO_MONO = 0.6


def _texto_pdf(s: str) -> bytes:
    """Cadena literal de PDF en cp1252, con los caracteres especiales escapados."""
    crudo = str(s).replace("\r", " ").replace("\n", " ").replace("\t", "    ")
    datos = crudo.encode("cp1252", "replace")
    salida = bytearray(b"(")
    for b in datos:
        if b in (0x28, 0x29, 0x5C):          # ( ) \
            salida += b"\\" + bytes([b])
        elif b < 0x20:
            salida += b" "
        else:
            salida.append(b)
    salida += b")"
    return bytes(salida)


def _num(v: float) -> str:
    texto = f"{float(v):.2f}".rstrip("0").rstrip(".")
    return texto if texto not in ("-0", "") else "0"


def _color(rgb) -> str:
    return " ".join(_num(c) for c in rgb)


class DocumentoPdf:
    """Documento en memoria. `bytes()` lo serializa; cada página lleva al pie
    `pie` y «Página n de N» si `numerar` es True."""

    def __init__(self, titulo: str = "", pie: str = "", numerar: bool = True,
                 ancho: float = ANCHO_A4, alto: float = ALTO_A4):
        self.titulo = titulo
        self.pie = pie
        self.numerar = numerar
        self.ancho = ancho
        self.alto = alto
        self._paginas: list[list[bytes]] = []
        self.nueva_pagina()

    @property
    def paginas(self) -> int:
        return len(self._paginas)

    def nueva_pagina(self) -> None:
        self._paginas.append([])

    def _op(self, texto) -> None:
        self._paginas[-1].append(texto if isinstance(texto, bytes) else texto.encode("ascii"))

    def _y(self, y: float) -> float:
        return self.alto - y

    # ── dibujo ─────────────────────────────────────────────────────────
    def texto(self, x: float, y: float, s: str, tam: float = 9, fuente: str = "mono",
              color=(0, 0, 0)) -> None:
        """Texto con la línea base en (x, y)."""
        nombre = FUENTES.get(fuente, FUENTES["mono"])[0]
        self._op(f"BT /{nombre} {_num(tam)} Tf {_color(color)} rg "
                 f"{_num(x)} {_num(self._y(y))} Td ".encode("ascii") + _texto_pdf(s) + b" Tj ET")

    def linea(self, x1, y1, x2, y2, grosor: float = 0.5, color=(0, 0, 0),
              discontinua: bool = False) -> None:
        guion = "[3 2] 0 d " if discontinua else "[] 0 d "
        self._op(f"q {guion}{_num(grosor)} w {_color(color)} RG {_num(x1)} {_num(self._y(y1))} m "
                 f"{_num(x2)} {_num(self._y(y2))} l S Q")

    def polilinea(self, puntos, grosor: float = 0.8, color=(0, 0, 0)) -> None:
        """Una línea por tramo continuo; un punto None corta el trazo."""
        tramos, actual = [], []
        for p in puntos:
            if p is None:
                if len(actual) > 1:
                    tramos.append(actual)
                actual = []
            else:
                actual.append(p)
        if len(actual) > 1:
            tramos.append(actual)
        for tramo in tramos:
            ops = [f"{_num(tramo[0][0])} {_num(self._y(tramo[0][1]))} m"]
            ops += [f"{_num(x)} {_num(self._y(y))} l" for x, y in tramo[1:]]
            self._op(f"q [] 0 d 1 j {_num(grosor)} w {_color(color)} RG " + " ".join(ops) + " S Q")

    def rectangulo(self, x, y, ancho, alto, grosor: float = 0.5, color=(0, 0, 0),
                   relleno=None) -> None:
        """Rectángulo con la esquina superior izquierda en (x, y)."""
        base = f"{_num(x)} {_num(self._y(y + alto))} {_num(ancho)} {_num(alto)} re"
        if relleno is not None:
            self._op(f"q {_color(relleno)} rg {base} f Q")
        if grosor > 0:
            self._op(f"q [] 0 d {_num(grosor)} w {_color(color)} RG {base} S Q")

    # ── serialización ──────────────────────────────────────────────────
    def bytes(self) -> bytes:
        objetos: list[bytes] = []

        def agregar(contenido: bytes) -> int:
            objetos.append(contenido)
            return len(objetos)

        catalogo = agregar(b"")           # se completa al final
        raiz_paginas = agregar(b"")
        fuentes = {}
        for clave, (nombre, base) in FUENTES.items():
            fuentes[nombre] = agregar(f"<< /Type /Font /Subtype /Type1 /BaseFont /{base} "
                                      f"/Encoding /WinAnsiEncoding >>".encode("ascii"))
        recursos = ("<< /Font << " + " ".join(f"/{n} {i} 0 R" for n, i in fuentes.items())
                    + " >> >>")
        hijos = []
        total = len(self._paginas)
        for n, ops in enumerate(self._paginas, start=1):
            pie = list(ops)
            if self.pie or self.numerar:
                marca = self.pie
                if self.numerar:
                    marca = (marca + "   " if marca else "") + f"Página {n} de {total}"
                pie.append(f"BT /F1 7 Tf 0.33 0.33 0.33 rg 40 22 Td ".encode("ascii")
                           + _texto_pdf(marca) + b" Tj ET")
            flujo = zlib.compress(b"\n".join(pie), 9)
            contenido = agregar(f"<< /Length {len(flujo)} /Filter /FlateDecode >>\nstream\n"
                                .encode("ascii") + flujo + b"\nendstream")
            hijos.append(agregar(f"<< /Type /Page /Parent {raiz_paginas} 0 R "
                                 f"/MediaBox [0 0 {_num(self.ancho)} {_num(self.alto)}] "
                                 f"/Resources {recursos} /Contents {contenido} 0 R >>"
                                 .encode("ascii")))
        objetos[raiz_paginas - 1] = (f"<< /Type /Pages /Count {total} /Kids ["
                                     + " ".join(f"{h} 0 R" for h in hijos) + "] >>").encode("ascii")
        objetos[catalogo - 1] = f"<< /Type /Catalog /Pages {raiz_paginas} 0 R >>".encode("ascii")
        info = agregar(b"<< /Title " + _texto_pdf(self.titulo)
                       + b" /Producer (Especifika Autoclave) >>")

        salida = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        posiciones = []
        for i, contenido in enumerate(objetos, start=1):
            posiciones.append(len(salida))
            salida += f"{i} 0 obj\n".encode("ascii") + contenido + b"\nendobj\n"
        xref = len(salida)
        salida += f"xref\n0 {len(objetos) + 1}\n0000000000 65535 f \n".encode("ascii")
        for p in posiciones:
            salida += f"{p:010d} 00000 n \n".encode("ascii")
        salida += (f"trailer\n<< /Size {len(objetos) + 1} /Root {catalogo} 0 R /Info {info} 0 R >>\n"
                   f"startxref\n{xref}\n%%EOF\n").encode("ascii")
        return bytes(salida)


class Flujo:
    """Texto que fluye de arriba abajo con salto de página automático. Usa
    Courier para el cuerpo (las columnas se alinean con espacios)."""

    def __init__(self, doc: DocumentoPdf, margen: float = 40, arriba: float = 50,
                 abajo: float = 45):
        self.doc = doc
        self.margen = margen
        self.arriba = arriba
        self.abajo = abajo
        self.y = arriba

    @property
    def ancho_util(self) -> float:
        return self.doc.ancho - 2 * self.margen

    def columnas(self, tam: float = 8.5) -> int:
        return max(20, int(self.ancho_util / (ANCHO_MONO * tam)))

    def espacio(self, alto: float) -> None:
        """Salta de página si no caben `alto` puntos más."""
        if self.y + alto > self.doc.alto - self.abajo:
            self.doc.nueva_pagina()
            self.y = self.arriba

    def titulo(self, texto: str, tam: float = 14) -> None:
        self.espacio(tam * 2)
        self.y += tam
        self.doc.texto(self.margen, self.y, texto, tam, "negrita")
        self.y += tam * 0.6

    def seccion(self, texto: str, tam: float = 11) -> None:
        self.espacio(tam * 4)
        self.y += tam * 2.2
        self.doc.texto(self.margen, self.y, texto, tam, "negrita")
        self.y += 3
        self.doc.linea(self.margen, self.y, self.doc.ancho - self.margen, self.y, 0.6,
                       (0.6, 0.6, 0.6))
        self.y += tam * 0.5

    def linea(self, texto: str = "", tam: float = 8.5, negrita: bool = False,
              sangria: int = 0) -> None:
        """Una o varias líneas (corta las que no caben en el ancho)."""
        ancho = self.columnas(tam) - sangria
        trozos = envolver(str(texto), ancho) or [""]
        for i, trozo in enumerate(trozos):
            self.espacio(tam * 1.35)
            self.y += tam * 1.25
            prefijo = " " * (sangria + (2 if i else 0))
            self.doc.texto(self.margen, self.y, prefijo + trozo, tam,
                           "mono_negrita" if negrita else "mono")

    def separacion(self, alto: float = 6) -> None:
        self.y += alto


def envolver(texto: str, ancho: int) -> list[str]:
    """Corta `texto` en líneas de hasta `ancho` caracteres, por palabras; una
    palabra más larga que el ancho se parte."""
    salida = []
    for parrafo in str(texto).splitlines() or [""]:
        actual = ""
        for palabra in parrafo.split(" "):
            while len(palabra) > ancho:
                if actual:
                    salida.append(actual)
                    actual = ""
                salida.append(palabra[:ancho])
                palabra = palabra[ancho:]
            candidato = palabra if not actual else actual + " " + palabra
            if len(candidato) <= ancho:
                actual = candidato
            else:
                salida.append(actual)
                actual = palabra
        salida.append(actual)
    return salida
