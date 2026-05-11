import tkinter as tk
import customtkinter as ctk
import logging
import time
import PIL.Image as image

#configuracion del logger
logger = logging.getLogger(__name__)
#-----------------------------------------------------------------------
def _actualizar_hora_fecha(label):
    ahora = time.strftime("%Y-%m-%d %H:%M:%S")
    label.config(text=ahora)
    label.after(1000, lambda: _actualizar_hora_fecha(label))

def _crear_encabezado(parent, titulo):
    encabezado = tk.Frame(
        parent,
        bg="#5789a7",
        height=50
    )
    encabezado.pack(fill=tk.X, side=tk.TOP)
    # el titulo esta dividido en 3 partes en el lado izquierdo esta el nombre de la empresa "ESPECIFIKA S.A.S" en el centro "Sistema de Autoclave de Vapor" y al lado derecho la fecha y hora actual
    #Parte del label de la izquierda con el nombre de la empresa
    empresa = tk.Label(
        encabezado,
        text="ESPECIFIKA S.A.S",
        font=("Segoe UI", 12, "italic"),
        bg="#5789a7",
        fg="black",
    )
    empresa.pack(side=tk.LEFT, padx=10)
    #Parte del label del centro con el nombre del sistema
    titulo = tk.Label(
        encabezado,
        text=titulo,
        font=("Segoe UI", 16),
        bg="#5789a7",
        fg="Black",
    )
    titulo.pack(side=tk.LEFT, expand=True)
    #Parte del label de la derecha con la fecha y hora actual
    hora_fecha = tk.Label(
        encabezado,
        font=("Segoe UI", 12),
        bg="#5789a7",
        fg="Black",
    )
    hora_fecha.pack(side=tk.RIGHT, padx=10)

    # Actualizar la hora y fecha cada segundo
    _actualizar_hora_fecha(hora_fecha)
#-----------------------------------------------------------------------
def _crear_fondo_principal(self):
    #este codigo creara un contenedor con las esquinas redondeadas, color blanco #ffffff mediante la libreria customtkinter que estara en la parte central de la ventana
    #separada del encavezado por un espacio de 10 pixeles y separada de los bordes laterales por un espacio correspondiente al 4% del ancho de la ventana
    #y una altura correspondiente al 75.25% de la altura de la ventana
    fondo = ctk.CTkFrame(
        self,
        corner_radius=30,
        bg_color="#b6ccd9",
        fg_color="#ffffff",
    )
    fondo.place(
        relx=0.04,
        rely=0.066,
        relwidth=0.92,
        relheight=0.7525,
        )
        
    return fondo
#-----------------------------------------------------------------------
def _crear_contenedor_informacion(self, relx, rely, relwidth, relheight):
    #este codigo creara un contenedor con las esquinas redondeadas, color blanco #2d4757 mediante la libreria customtkinter que estara en la parte central de la ventana
    #sera llamado desde otro modulo, por lo tanto resivira la ubicacion en la que debe estar el contenedor
    #tendra de altura el 10.5% de la altuda del espacio donde se coloque y de ancho el 29.4% del ancho del espacio donde se coloque
    info_frame = ctk.CTkFrame(
        self,
        corner_radius=40,
        bg_color="#ffffff",
        fg_color="#2d4757",
    )
    info_frame.place(
        relx=relx,
        rely=rely,
        relwidth=relwidth,
        relheight=relheight,
    )
    return info_frame
#-----------------------------------------------------------------------
def _info_contenedor(cont, titulo, valor, unidad):
    #este codigo creara los labels dentro del contenedor de informacion
    #titulo: es el valor que se mostrara en el label izquierdo del contenedor
    #valor: es el valor que se mostrara en el label central del contenedor
    #unidad: es el valor que se mostrara en el label derecho del contenedor
    #contenedor: es el contenedor donde se colocaran los labels
    titulo_label = ctk.CTkLabel(
        cont,
        text=titulo,
        font=("Segoe UI", 20, "bold"),
        bg_color="#2d4757",
        fg_color="#2d4757",
        text_color="white",
    )
    titulo_label.pack(side=tk.LEFT, padx=20)
    #unidad label a la derecha
    unidad_label = ctk.CTkLabel(
        cont,
        text=unidad,
        font=("Segoe UI", 20, "bold"),
        bg_color="#2d4757",
        fg_color="#2d4757",
        text_color="white",
    )
    unidad_label.pack(side=tk.RIGHT, padx=20)
    #valor label en el centro
    valor_label = ctk.CTkLabel(
        cont,
        text=valor,
        font=("Segoe UI", 20, "bold"),
        bg_color="#2d4757",
        fg_color="#2d4757",
        text_color="white",
    )
    valor_label.pack(side=tk.RIGHT, padx=10)
    
def _info_sensors(cont, titulo, unidad):
    #este codigo creara los labels dentro del contenedor de informacion
    #titulo: es el valor que se mostrara en el label izquierdo del contenedor
    #valor: es el valor que se mostrara en el label central del contenedor
    #unidad: es el valor que se mostrara en el label derecho del contenedor
    #contenedor: es el contenedor donde se colocaran los labels
    titulo_label = ctk.CTkLabel(
        cont,
        text=titulo,
        font=("Segoe UI", 20, "bold"),
        bg_color="#2d4757",
        fg_color="#2d4757",
        text_color="white",
    )
    titulo_label.pack(side=tk.LEFT, padx=20)
    #unidad label a la derecha
    unidad_label = ctk.CTkLabel(
        cont,
        text=unidad,
        font=("Segoe UI", 20, "bold"),
        bg_color="#2d4757",
        fg_color="#2d4757",
        text_color="white",
    )
    unidad_label.pack(side=tk.RIGHT, padx=20)
    #valor label en el centro
#-----------------------------------------------------------------------
def _crear_pie_pagina(self):
    #el pie de pagina estara en la parte inferior de la ventana principal, centrado con un ancho correnpondiante al 55% del ancho de la ventana, con esquinas redondeadas de 40px
    #y una altura correspondiente al 12% de la altura de la ventana, con un color de fondo #5789a7
    pie_pagina = ctk.CTkFrame(
        self,
        corner_radius=40,
        bg_color="#b6ccd9",
        fg_color="#5789a7",
    )
    pie_pagina.place(
        relx=0.2,
        rely=0.85,
        relwidth=0.6,
        relheight=0.12,
    )
    return pie_pagina
#-----------------------------------------------------------------------
def _crear_boton_menu(self, texto, comando, posicion):
    #boton alargado a lo ancho para el menu 
    #esquinas redondeadas de 20px
    #ocupara el 80% del ancho del contenedor donde se coloque y el 15% de la altura del contenedor donde se coloque
    rx, ry, rw, rh = posicion
    boton = ctk.CTkButton(
        self,
        text=texto,
        font=("Segoe UI", 20, "bold"),
        corner_radius=20,
        command=comando,
    )
    boton.place(
        relx=rx,
        rely=ry,
        relwidth=rw,
        relheight=rh,
    )
    return boton

def _frame_widgets(self, posicion):
    #creara  un frame reutilizable segun se requiera
    #este frame tendra esquinas redondeadas de 20px
    #tendra un ancho correspondiente al 90% del ancho del contenedor donde se coloque y una altura correspondiente al 10% de la altura del contenedor donde se coloque
    rx, ry, rw, rh = posicion
    frame = ctk.CTkFrame(
        self,
        corner_radius=10,
        bg_color="white",
        fg_color="#2d4757",
    )
    frame.place(
        relx=rx,
        rely=ry,
        relwidth=rw,
        relheight=rh,
    )
    return frame
    
def _label_entry(frame, label_text):
    #creara una etiqueta y una entrada dentro de un frame
    #la etiqueta estara a la izquierda y la entrada a la derecha
    #la etiqueta ocupara el 30% del ancho del frame y la entrada el 65% del ancho del frame
    #la altura de ambos sera del 90% de la altura del frame
    lbl = ctk.CTkLabel(
        frame,
        text=label_text,
        font=("Segoe UI", 24, "bold"),
        bg_color="#2d4757",
        fg_color="#2d4757",
        text_color="white",
        anchor="w",
    )
    lbl.place(
        relx=0.05,
        rely=0.05,
        relwidth=0.5,
        relheight=0.9,
    )
    entry = ctk.CTkEntry(
        frame,
        font=("Segoe UI", 16, "bold"),
        bg_color="#2d4757",
        fg_color="#ffffff",
        text_color="black",
    )
    entry.place(
        relx=0.6,
        rely=0.1,
        relwidth=0.39,   # <- el ajuste verdadero
        relheight=0.8,
    )

    return entry

def _crear_tabla(contenedor, datos):
    # Crear frame principal de la tabla
    tabla_frame = ctk.CTkFrame(
        contenedor,
        corner_radius=10,
        bg_color="#ffffff",
        fg_color="#d9e6f0",
    )
    tabla_frame.pack(pady=20, fill=tk.BOTH, expand=True)

    # Obtener columnas desde las claves del primer diccionario
    columnas = list(datos[0].keys()) if datos else []

    # Crear encabezados con bordes simulados
    for j, col in enumerate(columnas):
        # Borde
        borde = ctk.CTkFrame(
            tabla_frame,
            fg_color="black",
            corner_radius=0,
        )
        borde.grid(row=0, column=j, sticky="nsew")

        encabezado = ctk.CTkLabel(
            borde,
            text=col,
            font=("Segoe UI", 16, "bold"),
            fg_color="#5789a7",
            text_color="white",
            corner_radius=0,
        )
        encabezado.pack(fill="both", expand=True, padx=1, pady=1)

    # Crear las celdas
    for i, fila in enumerate(datos):
        for j, col in enumerate(columnas):
            borde = ctk.CTkFrame(
                tabla_frame,
                fg_color="black",
                corner_radius=0,
            )
            borde.grid(row=i + 1, column=j, sticky="nsew")

            celda = ctk.CTkLabel(
                borde,
                text=str(fila[col]),
                font=("Segoe UI", 14),
                fg_color="white",
                text_color="black",
                corner_radius=0,
            )
            celda.pack(fill="both", expand=True, padx=1, pady=1)

    # Ajustar columnas al tamaño disponible
    for j in range(len(columnas)):
        tabla_frame.grid_columnconfigure(j, weight=1)

    return tabla_frame
