# ui_qml/bridge/acciones_ciclos.py
#
# Acciones de impresión y correo del Menú Principal, fuera del hilo de la GUI,
# sobre ciclos del Historial y sobre el resumen por periodo de Reportes:
#   - Imprimir: POST /cycle/history/print; el backend los encola en la impresora
#     térmica (lo rechaza con 409 durante un ciclo y con 503 si Windows no
#     reporta la impresora lista: desconectada, sin papel, no instalada o error).
#   - Enviar por correo: por cada ciclo pide GET /cycle/history/{id}/ticket y
#     /graph, arma un PDF con la gráfica y el ticket (exportacion/pdf_ciclo.py) y
#     lo envía por SMTP con el remitente de exportacion/config_correo.py (un PDF,
#     o varios en un ZIP), como lo hacía ui_pyside/views/ciclos.py.
#   - Resumen por periodo: POST /report/summary/print (mismas reglas que la
#     reimpresión) o GET /report/summary -> PDF (exportacion/pdf_resumen.py) -> correo.
# Una acción a la vez (`ocupado`); el resultado llega por accionTerminada(éxito,
# mensaje) para que la pantalla lo muestre.

import logging
import smtplib
import tempfile
import threading
from pathlib import Path

import requests
from PySide6.QtCore import Property, QObject, Signal, Slot

from autoclave.core.runtime.progreso_ciclo import FASES_UI
from autoclave.services.domain.logging.ticket_formatter import format_ticket
from autoclave.ui_qml.domain import reporte_resumen
from autoclave.ui_qml.domain import resumen_sistema as dominio
from autoclave.ui_qml.domain.ciclo_en_curso import AcumuladorGrafica
from autoclave.ui_qml.exportacion import config_correo, correo

logger = logging.getLogger(__name__)


def _en_hilo(tarea) -> None:
    threading.Thread(target=tarea, daemon=True, name="acciones-ciclos").start()


def _generar_pdf(*args) -> None:
    # importación diferida: QtGui solo hace falta al enviar
    from autoclave.ui_qml.exportacion.pdf_ciclo import generar_pdf
    generar_pdf(*args)


def _generar_pdf_resumen(*args) -> None:
    from autoclave.ui_qml.exportacion.pdf_resumen import generar_pdf_resumen
    generar_pdf_resumen(*args)


class _ErrorConMensaje(Exception):
    """Fallo ya traducido al mensaje que verá el usuario."""


class AccionesCiclos(QObject):
    ocupadoChanged = Signal()
    correoChanged = Signal()
    accionTerminada = Signal(bool, str)
    _terminado = Signal(bool, str)          # emitida desde el hilo de trabajo

    def __init__(self, backend_client, textos: dict, parent=None, cargar_config=config_correo.cargar,
                 ejecutar=_en_hilo, generar_pdf=_generar_pdf, enviar=correo.enviar,
                 generar_pdf_resumen=_generar_pdf_resumen):
        super().__init__(parent)
        self._backend = backend_client
        self._textos = textos
        self._cargar_config = cargar_config
        self._ejecutar = ejecutar
        self._generar_pdf = generar_pdf
        self._generar_pdf_resumen = generar_pdf_resumen
        self._enviar = enviar
        self._ocupado = False
        self._config = cargar_config()
        self._terminado.connect(self._al_terminar)

    def _tx(self, seccion: str, clave: str, **valores) -> str:
        texto = (self._textos.get(seccion) or {}).get(clave, clave)
        return texto.format(**valores) if valores else texto

    # ── estado ───────────────────────────────────────────────────────────

    @Property(bool, notify=ocupadoChanged)
    def ocupado(self) -> bool:
        return self._ocupado

    @Property(bool, notify=correoChanged)
    def correoConfigurado(self) -> bool:
        return self._config.configurado

    @Property("QVariantList", notify=correoChanged)
    def destinos(self) -> list:
        """Destinos por defecto: [{nombre, correo}]."""
        return self._config.destinos

    @Slot()
    def actualizarCorreo(self) -> None:
        """Relee la configuración (al abrir la ventana: se edita a mano por ahora)."""
        self._config = self._cargar_config()
        self.correoChanged.emit()

    def _empezar(self, tarea) -> bool:
        if self._ocupado:
            return False
        self._ocupado = True
        self.ocupadoChanged.emit()

        def envoltura():
            try:
                exito, mensaje = tarea()
            except _ErrorConMensaje as e:
                exito, mensaje = False, str(e)
            except Exception:
                logger.exception("Acción sobre ciclos fallida")
                exito, mensaje = False, self._tx("exportacion", "error_envio")
            self._terminado.emit(exito, mensaje)

        self._ejecutar(envoltura)
        return True

    def _al_terminar(self, exito: bool, mensaje: str) -> None:
        self._ocupado = False
        self.ocupadoChanged.emit()
        self.accionTerminada.emit(exito, mensaje)

    # ── imprimir ─────────────────────────────────────────────────────────

    @Slot("QVariantList")
    def imprimir(self, ids: list) -> None:
        ids = [int(i) for i in ids]
        if not ids:
            return

        def tarea():
            r = self._post_impresion("/cycle/history/print", {"ids": ids})
            return True, self._tx("exportacion", "impreso", n=r.get("impresos", len(ids)))

        self._empezar(tarea)

    @Slot(str, str)
    def imprimirResumen(self, periodo: str, fecha: str) -> None:
        """Resumen del periodo de calendario que contiene `fecha` (ISO)."""
        def tarea():
            self._post_impresion("/report/summary/print", {"periodo": periodo, "fecha": fecha})
            return True, self._tx("exportacion", "impreso_resumen")

        self._empezar(tarea)

    def _post_impresion(self, ruta: str, cuerpo: dict) -> dict:
        """POST de impresión con sus errores traducidos al aviso de la pantalla."""
        try:
            return self._backend.post(ruta, cuerpo)
        except requests.HTTPError as e:
            codigo = getattr(e.response, "status_code", None)
            if codigo == 409:
                raise _ErrorConMensaje(self._tx("exportacion", "imprimir_en_ciclo"))
            if codigo == 503:
                raise _ErrorConMensaje(self._mensaje_impresora(e.response))
            raise _ErrorConMensaje(self._tx("exportacion", "imprimir_error"))
        except Exception as e:
            logger.debug("impresión no disponible: %s", e)
            raise _ErrorConMensaje(self._tx("exportacion", "imprimir_error"))

    def _mensaje_impresora(self, respuesta) -> str:
        """Aviso del estado de la impresora que devolvió el backend (503)."""
        try:
            estado = respuesta.json()["detail"]["impresora"]
        except Exception:
            estado = "error"
        if estado not in ("desconectada", "sin_papel", "no_instalada"):
            estado = "error"
        return self._tx("exportacion", "impresora_" + estado)

    # ── enviar por correo ────────────────────────────────────────────────

    @Slot("QVariantList", str)
    def enviarCorreo(self, ids: list, destino: str) -> None:
        ids = [int(i) for i in ids]
        destino = (destino or "").strip()
        if not ids:
            return
        config = self._config

        def tarea():
            self._validar_envio(config, destino)
            pdfs, ciclos = self._pdfs(ids)
            serie = ciclos[0].get("serie") or ""
            numeros = ", ".join(f"{c['numero_ciclo']:06d}" for c in ciclos)
            self._enviar_mensaje(config, destino,
                                 self._tx("exportacion", "asunto", serie=serie, ciclos=numeros),
                                 self._tx("exportacion", "cuerpo"),
                                 correo.adjunto(pdfs, self._tx("exportacion", "nombre_zip")))
            return True, self._tx("exportacion", "enviado", n=len(ids), destino=destino)

        self._empezar(tarea)

    @Slot(str, str, str)
    def enviarResumen(self, periodo: str, fecha: str, destino: str) -> None:
        """PDF del resumen del periodo que contiene `fecha` (ISO), por correo."""
        destino = (destino or "").strip()
        config = self._config

        def tarea():
            self._validar_envio(config, destino)
            try:
                r = self._backend.get("/report/summary", params={"periodo": periodo, "fecha": fecha})
            except Exception as e:
                logger.debug("resumen del periodo no disponible: %s", e)
                raise _ErrorConMensaje(self._tx("exportacion", "error_datos"))
            desde, hasta = r.get("desde", ""), r.get("hasta", "")
            texto_periodo = self._tx("exportacion", "periodo_resumen",
                                     desde=dominio.formatear_fecha(desde),
                                     hasta=dominio.formatear_fecha(hasta))
            nombre = f"resumen_{desde}_{hasta}.pdf"
            with tempfile.TemporaryDirectory() as carpeta:
                ruta = Path(carpeta) / nombre
                self._generar_pdf_resumen(ruta, {
                    "empresa": self._tx("exportacion", "empresa", modelo=r.get("modelo") or "",
                                        serie=r.get("serie") or ""),
                    "titulo": self._tx("exportacion", "titulo_resumen"),
                    "periodo": texto_periodo,
                    "resumen": reporte_resumen.presentable(r),
                }, dict(self._textos.get("reportes") or {}))
                contenido = ruta.read_bytes()
            self._enviar_mensaje(config, destino,
                                 self._tx("exportacion", "asunto_resumen", serie=r.get("serie") or "",
                                          periodo=texto_periodo),
                                 self._tx("exportacion", "cuerpo_resumen"),
                                 (nombre, contenido, "pdf"))
            return True, self._tx("exportacion", "enviado_resumen", destino=destino)

        self._empezar(tarea)

    def _validar_envio(self, config, destino: str) -> None:
        if not config_correo.correo_valido(destino):
            raise _ErrorConMensaje(self._tx("exportacion", "correo_invalido"))
        if not config.configurado:
            raise _ErrorConMensaje(self._tx("exportacion", "correo_no_configurado"))

    def _enviar_mensaje(self, config, destino: str, asunto: str, cuerpo: str, archivo) -> None:
        mensaje = correo.armar_mensaje(config.remitente, destino, asunto, cuerpo, archivo)
        try:
            self._enviar(config, mensaje)
        except smtplib.SMTPAuthenticationError:
            raise _ErrorConMensaje(self._tx("exportacion", "error_autenticacion"))
        except (smtplib.SMTPException, OSError) as e:
            logger.warning("Envío de correo fallido: %s", e)
            raise _ErrorConMensaje(self._tx("exportacion", "error_envio"))

    def _pdfs(self, ids: list) -> tuple[list, list]:
        """[(nombre, bytes)] de cada ciclo y sus datos, en el orden pedido."""
        pdfs, ciclos = [], []
        with tempfile.TemporaryDirectory() as carpeta:
            for ciclo_id in ids:
                try:
                    ticket = self._backend.get(f"/cycle/history/{ciclo_id}/ticket")
                    grafica = self._backend.get(f"/cycle/history/{ciclo_id}/graph")
                except Exception as e:
                    logger.debug("datos del ciclo %s no disponibles: %s", ciclo_id, e)
                    raise _ErrorConMensaje(self._tx("exportacion", "error_datos"))
                ciclo = ticket["ciclo"]
                acumulador = AcumuladorGrafica()
                acumulador.incorporar(grafica)
                nombre = f"ciclo_{ciclo['numero_ciclo']:06d}.pdf"
                ruta = Path(carpeta) / nombre
                self._generar_pdf(ruta, self._datos_pdf(ciclo), format_ticket(ciclo, ticket["lecturas"]),
                                  acumulador.datos(), acumulador.inicios_de_fase(FASES_UI),
                                  self._textos_pdf())
                pdfs.append((nombre, ruta.read_bytes()))
                ciclos.append(ciclo)
        return pdfs, ciclos

    def _datos_pdf(self, ciclo: dict) -> dict:
        fila = dominio.ciclo_presentable({
            "id": ciclo.get("id"), "numero_ciclo": ciclo.get("numero_ciclo"),
            "fecha_inicio": ciclo.get("fecha_inicio"), "fecha_fin": ciclo.get("fecha_fin"),
            "programa_nombre": ciclo.get("nombre_ciclo"), "resultado": ciclo.get("resultado")})
        clave = fila["resultado"]
        resultado = self._tx("menu", "resultado_" + clave.lower()) if clave else dominio.SIN_DATO
        if fila["resultado_detalle"]:
            resultado += f" ({fila['resultado_detalle']})"
        fin = dominio.formatear_fecha(ciclo.get("fecha_fin"))
        hora_fin = dominio.formatear_hora(ciclo.get("fecha_fin"))
        return {
            "empresa": self._tx("exportacion", "empresa", modelo=ciclo.get("modelo") or "",
                                serie=ciclo.get("serie") or ""),
            "titulo": self._tx("exportacion", "titulo", numero=f"{ciclo['numero_ciclo']:06d}",
                               programa=ciclo.get("nombre_ciclo") or dominio.SIN_DATO),
            "campos": [
                (self._tx("exportacion", "inicio"), f"{fila['fecha']}  {fila['hora']}"),
                (self._tx("exportacion", "fin"),
                 f"{fin}  {hora_fin}" if fin != dominio.SIN_DATO else dominio.SIN_DATO),
                (self._tx("exportacion", "resultado"), resultado),
            ],
        }

    def _textos_pdf(self) -> dict:
        ciclo = self._textos.get("ciclo") or {}
        return {
            "fases": self._textos.get("fases") or {},
            "series": {"temp_camara": ciclo.get("serie_temp_camara", ""),
                       "temp_ref": ciclo.get("serie_temp_ref", ""),
                       "pres_camara": ciclo.get("serie_presion", "")},
            **{k: self._tx("exportacion", k)
               for k in ("eje_tiempo", "eje_temp", "eje_pres", "sin_grafica", "ticket")},
        }
