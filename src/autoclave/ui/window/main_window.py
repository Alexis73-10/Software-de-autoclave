# autoclave/ui/main_window.py

#Importar librerias necesarias
import PIL.Image as image
import tkinter as tk
import customtkinter as ctk
import logging
import autoclave.ui.components.components as components
from autoclave.ui.cycle.cycle_window import CycleWindow
from autoclave.utils.resources import resource_path


#configuracion del logger
logger = logging.getLogger(__name__)
#variables globales de la interfaz

#----------------------------------------------------------------------
class InterfazPrincipal(tk.Tk):

    #inicializacion de la interfaz principal
    def __init__(self, ui_service, door_commands):
        super().__init__()
        
        self._cargar_imagenes()  # ← aquí SIEMPRE primero

        # 🔹 Configuración de la ventana
        self.title("Autoclave de vapor")
        self.geometry("1280x720")
        self.configure(bg="#b6ccd9")

        # 👉 usa fullscreen solo en producción
        self.attributes("-fullscreen", True)

        self.bind("<Configure>", self._resize)

        # 🔹 Layout principal (grid)
        self.grid_rowconfigure(0, weight=1)  # header
        self.grid_rowconfigure(1, weight=18)  # contenido
        self.grid_rowconfigure(2, weight=1)  # footer
        self.grid_columnconfigure(0, weight=1)

        # 🔹 Secciones principales
        self.header = ctk.CTkFrame(self, fg_color="#b6ccd9")
        self.header.grid(row=0, column=0, sticky="nsew")

        self.body = ctk.CTkFrame(self, fg_color="white", corner_radius=30)
        self.body.grid(row=1, column=0, sticky="nsew", padx=20, pady=10)

        self.footer = ctk.CTkFrame(self, fg_color="#b6ccd9")
        self.footer.grid(row=2, column=0, sticky="nsew")

        # 🔹 Configuración del body
        self.body.grid_columnconfigure(0, weight=1)  # izquierda
        self.body.grid_columnconfigure(1, weight=3)  # derecha
        self.body.grid_rowconfigure(0, weight=1)

        # 🔹 Paneles internos
        self.panel_estados = ctk.CTkFrame(self.body, fg_color="white")
        self.panel_estados.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        self.panel_main = ctk.CTkFrame(self.body, fg_color="white")
        self.panel_main.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)

        # 🔹 Servicios
        self.ui_service = ui_service
        self.door_commands = door_commands

        # 🔹 Variables UI
        self.cycle_name = self.ui_service.get_cycle_param("display_name")
        self.n_ciclo = tk.IntVar(value=1)

        # ⚠️ NO llamar backend aquí (evita crasheos al inicio)
        self.prep_ciclo = "Cargando..."
        self.alarmas_activas = []
        self.alarm_labels = []

        # 🔹 Construcción UI
        components._crear_encabezado(self.header, "T-MAX6")
        self.crear_layout()
        self._pie_pagina()

        # 🔹 Loop de actualización UI
        self.after(500, self.update_ui)

        # 🔹 Estado inicial de botones
        self.after(600, self.actualizar_boton)
        self.after(600, self.actualizar_puerta_dos)
        self.after(600, self.actualizar_listo)

        logger.info("✅ Interfaz creada correctamente.")

    # ------------------------------------------------------------------
    # Creación de la interfaz
    # ------------------------------------------------------------------
    
    def _cargar_imagenes(self):

        w,h = self._escalar(0.1,0.08)

        self.img_start = ctk.CTkImage(
            light_image=image.open(resource_path("autoclave/images/start_cycle.png")),
            dark_image=image.open(resource_path("autoclave/images/start_cycle.png")),
            size=(w, h),
        )

        self.img_puerta1_abierta = ctk.CTkImage(
            light_image=image.open(resource_path("autoclave/images/open_door_1.png")),
            dark_image=image.open(resource_path("autoclave/images/open_door_1.png")),
            size=(w, h),
        )

        self.img_puerta1_cerrada = ctk.CTkImage(
            light_image=image.open(resource_path("autoclave/images/close_door_1.png")),
            dark_image=image.open(resource_path("autoclave/images/close_door_1.png")),
            size=(w, h),
        )

        self.img_puerta2_abierta = ctk.CTkImage(
            light_image=image.open(resource_path("autoclave/images/open_door_2.png")),
            dark_image=image.open(resource_path("autoclave/images/open_door_2.png")),
            size=(w, h),
        )

        self.img_puerta2_cerrada = ctk.CTkImage(
            light_image=image.open(resource_path("autoclave/images/close_door_2.png")),
            dark_image=image.open(resource_path("autoclave/images/close_door_2.png")),
            size=(w, h),
        )

        # 🔹 iconos footer
        self.img_info = ctk.CTkImage(
            light_image=image.open(resource_path("autoclave/images/info_icon.png")),
            dark_image=image.open(resource_path("autoclave/images/info_icon.png")),
            size=(50, 40),
        )

        self.img_power = ctk.CTkImage(
            light_image=image.open(resource_path("autoclave/images/power_icon.png")),
            dark_image=image.open(resource_path("autoclave/images/power_icon.png")),
            size=(50, 40),
        )

        self.img_login = ctk.CTkImage(
            light_image=image.open(resource_path("autoclave/images/login_icon.png")),
            dark_image=image.open(resource_path("autoclave/images/login_icon.png")),
            size=(50, 40),
        )

    def crear_layout(self):

        self.panel_main.grid_rowconfigure(0, weight=1)  # título
        self.panel_main.grid_rowconfigure(1, weight=1)  # línea
        self.panel_main.grid_rowconfigure(2, weight=6)  # contenido
        self.panel_main.grid_rowconfigure(3, weight=2)  # botones

        self.panel_main.grid_columnconfigure(0, weight=1)

        fondo = components._crear_fondo_principal(self.panel_main)

        def contenedor_estados(parent):
            estados = ctk.CTkFrame(
                parent,
                corner_radius=40,
                bg_color="#ffffff",
                fg_color="#2d4757",
            )
            estados.place(
                relx=0.03,
                rely=0.06,
                relwidth=0.9,
                relheight=0.9,
            )
            
            def numero_ciclo(cont):
                #este codigo creara un label dentro del contenedor estados, que mostrara el numero de ciclo actual
                #el label estara en la parte superior del contenedor estados, centrado, separado del borde superior por un espacio correspondiente al 10% de la altura del contenedor estados
                #este numero tendra un tamaño equivalente al 50% del ancho del contenedor estados
                #el label tendra un color de fondo #2d4757 y un color de letra blanco, con una fuente Segoe UI de tamaño 24 y negrita
                ciclo_label = ctk.CTkLabel(
                    cont,
                    text=self.n_ciclo.get(),
                    font=("Segoe UI", 80, "bold"),
                    bg_color="#2d4757",
                    fg_color="#2d4757",
                    text_color="white",
                )
                ciclo_label.place(
                    relx=0.5,
                    rely=0.05,
                    anchor="n",
                )
            numero_ciclo(estados)
            
            def estado_actual(cont):
                #este codigo creara un label dentro del contenedor estados, que mostrara el estado actual del sistema
                #almacenado en la variable prep_ciclo de tipo StringVar
                #el label estara debajo del label del numero de ciclo, alineado a la hisquierda del contenedor estados, separado del borde izquierdo por un espacio correspondiente al 5% del ancho del contenedor estados
                #y separado del label del numero de ciclo por un espacio correspondiente al 5% de la altura del contenedor estados

                self.estado_label = ctk.CTkLabel(
                    cont,
                    text= self.prep_ciclo,
                    font=("Segoe UI", 20, "bold"),
                    bg_color="#2d4757",
                    fg_color="#2d4757",
                    text_color="white",
                    
                )
                self.estado_label.place(
                    relx=0.05,
                    rely=0.3,
                    anchor="w",
                )
                

            estado_actual(estados)
            
            self.contenedor = estados

        contenedor_estados(self.panel_estados)

        def titulo_ciclo(parent):
            #este codigo creara un label dentro del contenedor fondo, que mostrara el titulo "Ciclo de esterilizacion"
            #este label estara en la parte superior central del contenedor fondo, separado del borde superior por un espacio correspondiente al 9% de la altura del contenedor fondo
            #tendra un ancho correspondiente al 40% del ancho del contenedor fondo
            texto= self.cycle_name.upper()

            titulo_label = ctk.CTkLabel(
                parent,
                text= texto,
                font=self._font(60),
                text_color="Black",
            )
            titulo_label.place(
                relx=0.5,
                rely=0.05,
                anchor="n"
            )
        titulo_ciclo(fondo)
    
        def linea_separadora(fondo):
            #este codigo creara una linea separadora horizontal dentro del contenedor fondo
            #esta linea estara en la parte superior del contenedor fondo, separada del borde superior por un espacio correspondiente al 18% de la altura del contenedor fondo
            #tendra un ancho correspondiente al 92% del ancho del contenedor fondo y una altura de 2 pixeles
            linea = ctk.CTkFrame(
                fondo,
                bg_color="#ffffff",
                fg_color="black",
            )
            linea.place(
                relx=0.5,
                rely=0.24,
                anchor="n",
                relwidth=0.9,
                relheight=0.008,
            )
        linea_separadora(fondo)

        #este fragmento de codigo creara 3 contenedores dentro del contenedor fondo llamando a la funcion _crear_contenedor_informacion desde el modulo components
        #estos contenedores estaran dispuests de forma vertical en la parte dereca del contenedor fondo a una distancia del borde hisquierdo correspondoente al 32.4% del ancho del contenedor fondo
        #el primer contenedor estara separado del borde superior del contenedor fondo por un espacio correspondiente al 26% de la altura del contenedor fondo
        #una separacion entre cada contenedor correspondiente al 5% de la altura del contenedor fondo
        def parm_temp(fondo):
            contenedor1 = components._crear_contenedor_informacion(
                fondo,
                relx=0.324,
                rely=0.26,
                relwidth=0.294,
                relheight=0.105,
            )
            def info_par_temp(cont):
                components._info_contenedor(
                cont,
                "Temp.Ester",
                "134",
                "°C"
            )
            info_par_temp(contenedor1)
        parm_temp(fondo)

        def parm_tiempo(fondo):
            contenedor2 = components._crear_contenedor_informacion(
                fondo,
                relx=0.324,
                rely=0.26 + 0.105 + 0.05,
                relwidth=0.294,
                relheight=0.105,
        )
            def info_par_tiempo(cont):
                components._info_contenedor(
                cont,
                "Tiempo.Ester",
                "5",
                "min"
            )
            info_par_tiempo(contenedor2)
        parm_tiempo(fondo)
        
        def parm_secado(fondo):
            contenedor3 = components._crear_contenedor_informacion(
            fondo,
            relx=0.324,
            rely=0.26 + 0.105 + 0.05 + 0.105 + 0.05,
            relwidth=0.294,
            relheight=0.105,
        )
            def info_par_secado(cont):
                components._info_contenedor(
                cont,
                "Tiempo.Secado",
                "2",
                "min"
            ) 
            info_par_secado(contenedor3)
        parm_secado(fondo)

        #este fragmento de codigo creara 3 contenedores dentro del contenedor fondo llamando a la funcion _crear_contenedor_informacion desde el modulo components
        #estos contenedores estaran dispuests de forma vertical en la parte derecha del contenedor fondo a una distancia del borde izquierdo correspondoente al 65.8% del ancho del contenedor fondo
        #el primer contenedor estara separado del borde superior del contenedor fondo por un espacio correspondiente al 26% de la altura del contenedor fondo
        #una separacion entre cada contenedor correspondiente al 5% de la altura del contenedor fondo
        def inf_t_cam(fondo):
            #actualizaciond el contenedor:
            #el valor de la temperatura de la camara actualizara por medio del control loop
            #por lo cual leera un estado actual llamado temp_camara
            self.contenedor_t_cam = components._crear_contenedor_informacion(
                fondo,
                relx=0.658,
                rely=0.26,
                relwidth=0.294,
                relheight=0.105,
            )
            label = components._info_sensors(
                self.contenedor_t_cam,
                "Temp.Cam",
                "°C",
            )
            #valor label en el centro
            self.temp_cam = ctk.CTkLabel(
                self.contenedor_t_cam,
                text="---",
                font=("Segoe UI", 20, "bold"),
                bg_color="#2d4757",
                fg_color="#2d4757",
                text_color="white",
            )
            self.temp_cam.pack(side=tk.RIGHT, padx=10)
            
            
        inf_t_cam(fondo)
        
        def inf_t_ref(fondo):
            self.contenedor_t_ref = components._crear_contenedor_informacion(
                fondo,
                relx=0.658,
                rely=0.26 + 0.105 + 0.05,
                relwidth=0.294,
                relheight=0.105,
            )

            label = components._info_sensors(
                self.contenedor_t_ref,
                "Temp.Ref",
                "°C",
            )
            #valor label en el centro
            self.temp_ref = ctk.CTkLabel(
                self.contenedor_t_ref,
                text="---",
                font=("Segoe UI", 20, "bold"),
                bg_color="#2d4757",
                fg_color="#2d4757",
                text_color="white",
            )
            self.temp_ref.pack(side=tk.RIGHT, padx=10)
        
        inf_t_ref(fondo)
        
        def inf_pres_cam(fondo):
            contenedor6 = components._crear_contenedor_informacion(
                fondo,
                relx=0.658,
                rely=0.26 + 0.105 + 0.05 + 0.105 + 0.05,
                relwidth=0.294,
                relheight=0.105,
            )
            label = components._info_sensors(
                contenedor6,
                "Pres.Cam",
                "kPa",
            )
            #valor label
            self.pres_cam = ctk.CTkLabel(
                contenedor6,
                text="---",
                font=("Segoe UI", 20, "bold"),
                bg_color="#2d4757",
                fg_color="#2d4757",
                text_color="white",
            )
            self.pres_cam.pack(side=tk.RIGHT, padx=10)

        inf_pres_cam(fondo)
#-----------------------------------------------------------------------
    #botones inferiores para control de la puerta y ciclo
#-----------------------------------------------------------------------
        def boton_puerta_1(fondo, door_commands):
            #creacion del boton para abrir y cerrar la puerta
            #este boton estara en la parte inferior izquierda del contenedor fondo, separado del borde izquierdo por un espacio correspondiente al 4.5% del ancho del contenedor fondo
            #y separado del borde inferior por un espacio correspondiente al 5% de la altura del contenedor fondo
            #tendra una n de puerta hubicada en src/autoclave/images/open_door.png
                
            def accion():
                estado_actual = self.ui_service.get_estado_puerta("Puerta 1")
                
                if estado_actual == "ABIERTO":
                    door_commands.close("Puerta 1")
                else:
                    door_commands.open("Puerta 1")
                    
            #creacion del boton
            self.boton_puerta = ctk.CTkButton(
                fondo,
                text="",
                compound="left",
                fg_color="white",
                hover_color="lightgray",
                command=accion
            )
            
            self.boton_puerta.place(
                relx=0.324,
                rely=0.73,
            )
        boton_puerta_1(fondo, self.door_commands)

        def boton_puerta_2(fondo, door_commands, door_index="Puerta 2"):
            #esto mostrara el estado de la segunda puerta
            #este estara en la parte inferior central del contenedor fondo, separado del borde izquierdo por un espacio correspondiente al 47.5% del ancho del contenedor fondo
            #y separado del borde inferior por un espacio correspondiente al 5% de la altura del contenedor fondo
            #tendra una imagen de puerta hubicada en src/autoclave/images/
            
            def accion_boton_2():
                estado_actual = self.ui_service.get_estado_puerta(door_index)
                
                if estado_actual == "ABIERTO":
                    door_commands.close(door_index)
                else:
                    door_commands.open(door_index)
                    
            
            self.boton_puerta_dos = ctk.CTkButton(
                fondo,
                text="",
                compound="left",
                fg_color="white",
                hover_color="lightgray",
                command=accion_boton_2
            )
            self.boton_puerta_dos.place(
                relx=0.384,
                rely=0.728,
            )
        boton_puerta_2(fondo, self.door_commands, door_index="Puerta 2")


        def boton_iniciar_ciclo(fondo):
            #creacion del boton para iniciar el ciclo
            #este boton estara en la parte inferior derecha del contenedor fondo, separado del borde derecho por un espacio correspondiente al 4.5% del ancho del contenedor fondo
            #y separado del borde inferior por un espacio correspondiente al 5% de la altura del contenedor fondo
            #tendra una imagen de inicio hubicada en src/autoclave/images/start_cycle.png


            #el boton al ser presionado llamara a la funcion start_cycle
            self.boton_iniciar = ctk.CTkButton(
                fondo,
                text="",
                compound="left",
                #banco
                fg_color="white",
                #gris claro
                hover_color="lightgray",
                command=self.start_cycle
            )
            self.boton_iniciar.place(
                relx=0.85,
                rely=0.73,
            )

        boton_iniciar_ciclo(fondo)

    def _pie_pagina(self):

        # 🔹 configurar el footer (contenedor base)
        height = int(self.winfo_screenheight() * 0.1)
        self.footer.configure(
            fg_color="transparent",
            height = height,
        )

        # 🔹 caja interna centrada (80% ancho)
        self.footer_box = ctk.CTkFrame(
            self.footer,
            fg_color="#5789a7",
            corner_radius=50
        )

        self.footer_box.place(
            relx=0.5,
            rely=0.5,
            anchor="center",
            relwidth=0.6,
            relheight=0.8
        )

        # 🔹 layout interno
        self.footer_box.grid_columnconfigure(0, weight=1)
        self.footer_box.grid_columnconfigure(1, weight=1)
        self.footer_box.grid_columnconfigure(2, weight=1)
        self.footer_box.grid_rowconfigure(0, weight=1   )

        # 🔹 BOTÓN INFO (izquierda)
        self.btn_info = ctk.CTkButton(
            self.footer_box,
            text="",
            image=self.img_info,
            fg_color="#5789a7",
            hover_color="#406080",
            corner_radius=50,
            width=60,
            height=60
        )
        self.btn_info.grid(row=0, column=0, sticky="w", padx=20)

        # 🔹 BOTÓN APAGAR (centro)
        self.btn_power = ctk.CTkButton(
            self.footer_box,
            text="",
            image=self.img_power,
            fg_color="#5789a7",
            hover_color="#406080",
            corner_radius=50,
            command=self.apagar_equipo,
            width=60,
            height=60
        )
        self.btn_power.grid(row=0, column=1)

        # 🔹 BOTÓN LOGIN (derecha)
        self.btn_login = ctk.CTkButton(
            self.footer_box,
            text="",
            image=self.img_login,
            fg_color="#5789a7",
            hover_color="#406080",
            corner_radius=50,
            command=self.login_user,
            width=80,
            height=60
        )
        self.btn_login.grid(row=0, column=2, sticky="e", padx=20)

    def start_cycle(self):
        #funcion para iniciar el ciclo de esterilizacion
        #esta funcion abrira una nueva ventana llamando a la clase CycleWindow del modulo cycle_window
        logger.info("▶️ Iniciando ciclo de esterilización...")
        cycle_window = CycleWindow(self)
        cycle_window.grab_set()

    def apagar_equipo(self):
        #funcion para apagar el equipo
        logger.info("⏻ Apagando equipo...")
        #la pantalla se oscurecera y aparecera un mensaje de apagando equipo, luego de 3 segundos la aplicacion se cerrara
        self.withdraw()
        apagando_ventana = tk.Toplevel(self)
        apagando_ventana.geometry("400x200")
        apagando_ventana.title("Apagando equipo")
        apagando_ventana.configure(bg="#37596C")
        #transparencia
        apagando_ventana.wm_attributes("-alpha", 0.9)
        apagando_ventana.attributes("-fullscreen", True)
        mensaje = ctk.CTkLabel(
            apagando_ventana,
            text="Apagando equipo...",
            font=("Segoe UI", 40, "bold"),
            bg_color="#37596C",
            fg_color="#37596C",
            text_color="white",
        )
        mensaje.pack(expand=True)
        apagando_ventana.after(3000, self.destroy)

    def login_user(self):
        #funcion para login de usuario
        pass  # Implementar funcionalidad de login aquí

    def actualizar_sensores(self,):
        #funcion para actualizar el valor de la temperatura de la camara
        valor_temp = self.ui_service.get_sensores_temp()
        valor_pres = self.ui_service.get_sensores_pres()

        self.temp_cam.configure(text=str(valor_temp["temp_camara"]))
        self.temp_ref.configure(text=str(valor_temp["temp_ref"]))
        self.pres_cam.configure(text=str(valor_pres["pres_camara"]))
        
        #llama a esta funcion cada 500ms para actualizar el valor

    def actualizar_fase_actual(self):
        estado = self.ui_service.get_estado_global()
        print("Estado global:", estado)
        self.estado_label.configure(text=estado)

    def actualizar_boton(self):
        estado_actual = self.ui_service.get_estado_puerta("Puerta 1")
        
        if estado_actual == "CERRADO":
            img= self.img_puerta1_cerrada
            
        else:
            img= self.img_puerta1_abierta

        self.boton_puerta.configure(image=img)
        self.boton_puerta.image = img 

    def actualizar_puerta_uno(self):
        estado_puerta_1 = self.ui_service.get_estado_puerta("Puerta 1")
        
        if estado_puerta_1 == "CERRADO":
            img= self.img_puerta1_cerrada
        else:
            img= self.img_puerta1_abierta
        
        self.boton_puerta.configure(image=img)
        self.boton_puerta.image = img  # Mantener una referencia a la imagen

    def actualizar_puerta_dos(self):
        estado_puerta_2 = self.ui_service.get_estado_puerta("Puerta 2")
        
        if estado_puerta_2 == "CERRADO":
            img= self.img_puerta2_cerrada
        else:
            img= self.img_puerta2_abierta
        
        self.boton_puerta_dos.configure(image=img)
        self.boton_puerta_dos.image = img  # Mantener una referencia a la imagen

    def actualizar_listo (self):
        preparado = self.ui_service.get_estado_flag("LISTO_PARA_CICLO")

        if preparado:
            self.boton_iniciar.configure(state="normal")
        else:
            self.boton_iniciar.configure(state="disabled")

    def actualizar_alarmas(self):
        # 1. borrar SOLO los labels de alarmas
        for lbl in self.alarm_labels:
            lbl.destroy()
        self.alarm_labels.clear()

        # 2. obtener alarmas nuevas
        alarmas = self.ui_service.get_alarmas()

        # 3. crear labels nuevos
        for i, alarma in enumerate(alarmas):
            alarma_label = ctk.CTkLabel(
                self.contenedor,
                text=f"[{alarma['level']}] {alarma['id']}",
                font=("Segoe UI", 16),
                bg_color="#2d4757",
                fg_color="#2d4757",
                text_color="white",
            )
            alarma_label.place(
                relx=0.05,
                rely=0.4 + i * 0.05,
                anchor="w",
            )

            self.alarm_labels.append(alarma_label)

    def toggle_door(self):
        door=self.door_commands.doors[0]
        status=door.state.name
        
        if status == "ABIERTO":
            self.door_commands.request_close(door)
            
        else:
            self.door_commands.request_open(door)

    def update_ui(self):
        if not hasattr(self, "_tick"):
            self._tick = 0

        self._tick += 1

        try:
            # 🔥 1. UNA sola actualización backend
            self.ui_service.update()

            # 🔹 cada 0.5s (rápido)
            self.actualizar_sensores()

            # 🔹 cada 1s (lento)
            if self._tick % 2 == 0:
                self.actualizar_fase_actual()
                self.actualizar_alarmas()
                self.actualizar_listo()
                self.actualizar_boton()
                self.actualizar_puerta_dos()

        except Exception as e:
            logger.debug(f"⚠️ Error UI loop: {e}")

        self.after(500, self.update_ui)

    def _escalar(self, w, h):
        return int(self.winfo_width() * w), int(self.winfo_height() * h)
    
    def _resize(self, event):
        if event.widget != self:
            return

        # evitar recalcular demasiado
        if hasattr(self, "_last_size"):
            if self._last_size == (self.winfo_width(), self.winfo_height()):
                return

        self._last_size = (self.winfo_width(), self.winfo_height())

        self._cargar_imagenes()
        
        # refrescar botones
        self.actualizar_puerta_uno()
        self.actualizar_puerta_dos()
        self.boton_iniciar.configure(image=self.img_start)

    def _font(self, size):
        base = min(self.winfo_width(), self.winfo_height())
        escala = base / 720
        return ("Segoe UI", int(size * escala), "bold")