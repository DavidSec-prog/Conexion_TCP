import socket  #Comunicacion/Tunel con el servidor
import threading #Hilos
import os  # Rutas, archivos y directorios
import time # Pausas e intervalos
import re # Expresiones regulares para validar el formato "Cliente N"
import configparser #Leer config.ini
import tkinter as tk #Inetrfaz Grafica  GUI
from tkinter import filedialog, messagebox, scrolledtext, ttk #Submodulos de la GUI Caja de texto, scroll, mensajes etc
from datetime import datetime #Hora en log


class ClienteGUI:
    def __init__(self):     # Constructor // inicialziar objetos
        self.cargar_configuracion()
        #Inicialzia ventana principal
        self.root = tk.Tk()
        self.root.title("Cliente TCP - Distribución de Archivos") #Titulo principal de la ventana
        self.root.geometry("840x880")   #Tamaño de la ventana
        self.root.minsize(760, 740)     #Tamaño mínimo para evitar deformaciones
        self.root.configure(bg='#1e1e2e') # Color
        self.root.protocol("WM_DELETE_WINDOW", self.cerrar_cliente) #Al cerrar con x llama el metodo cerrar_cliente

        self.TAMANO_MAXIMO = self.config_tamano_maximo * 1024 * 1024  #Tamaño de bytes en MB para los archivos
        self.nombre_cliente = "Cliente Desconocido"  #Nombre del cliente se cambia al conectar
        self.directorio_descargas = "archivos_recibidos" #Carpeta donde se guarda el archivo
        self.crear_directorio_descargas()  #Iniciliza el metodo

        self.conectado = False  #Incializa si esta conectado
        self.reconectando = False   #Inicializa so esta reconectando
        self.debe_reconectar = True  #Inicializa si debe reconectar
        self.intentos_actuales = 0  #Incializa intentos de reconexion
        self.max_intentos = self.config_max_intentos  # Iniciliza los intentos max = incializa configiuracion max de intentos
        self.tiempo_entre_intentos = self.config_tiempo_entre_intentos #Inicializa tiempo entre intentos = conf tiempo de intentos
        self.reconexiones_exitosas = 0 #Incializa reconexiones exitosas
        self.archivos_recibidos = 0 #Inicializa Archivos recibidos
        self.socket = None
        # CAMBIO: guarda el último servidor asignado para reconectar al mismo puerto.
        self.servidor_host_actual = None
        self.servidor_puerto_actual = None # Incialzia el # de socket

        self.root.grid_rowconfigure(0, weight=1)    #Responsivo de forma vertical
        self.root.grid_columnconfigure(0, weight=1) #Responsivo de forma horizontal

        # ===== PALETA Y FUENTES =====
        # Se centralizan los colores y fuentes para mantener un diseño consistente.
        self.COLOR_BG = '#1e1e2e'            # Fondo principal
        self.COLOR_CARD = '#313244'          # Fondo de tarjetas
        self.COLOR_INPUT = '#45475a'         # Fondo de campos de entrada
        self.COLOR_TEXT = '#cdd6f4'          # Texto principal
        self.COLOR_TEXT_DIM = '#7f849c'      # Texto secundario
        self.COLOR_PRIMARY = '#89b4fa'       # Azul principal
        self.COLOR_PRIMARY_HOVER = '#b4befe' # Azul hover
        self.COLOR_SUCCESS = '#a6e3a1'       # Verde éxito
        self.COLOR_WARNING = '#f9e2af'       # Amarillo advertencia
        self.COLOR_ERROR = '#f38ba8'         # Rojo error
        self.COLOR_ORANGE = '#fab387'
        self.COLOR_ACCENT = '#cba6f7'
        self.FONT_FAMILY = 'Segoe UI' if os.name == 'nt' else 'Helvetica'
        self.FONT_TITLE = (self.FONT_FAMILY, 17, 'bold')
        self.FONT_SUB = (self.FONT_FAMILY, 9)
        self.FONT_SECTION = (self.FONT_FAMILY, 10, 'bold')
        self.FONT_STATUS = (self.FONT_FAMILY, 13, 'bold')
        self.FONT_BODY = (self.FONT_FAMILY, 10)
        self.FONT_BODY_BOLD = (self.FONT_FAMILY, 10, 'bold')
        self.FONT_BUTTON = (self.FONT_FAMILY, 11, 'bold')
        self.FONT_MONO = ('Consolas', 9)

        #Configuracion del tamaños y ajsutes responsivos de la interfaz
        main_frame = tk.Frame(self.root, bg=self.COLOR_BG)
        main_frame.grid(row=0, column=0, sticky='nsew', padx=16, pady=16)
        main_frame.grid_rowconfigure(3, weight=1)   # La fila del log se expande
        main_frame.grid_columnconfigure(0, weight=1)

        # ===== ENCABEZADO =====
        #Configuarcion de la interfaz del encabezado
        title_frame = tk.Frame(main_frame, bg=self.COLOR_BG)
        title_frame.grid(row=0, column=0, sticky='ew', pady=(0, 12))

        self.nombre_label = tk.Label(
            title_frame, text="Cliente",   #Titulo del cliente
            font=self.FONT_TITLE, bg=self.COLOR_BG, fg=self.COLOR_PRIMARY
        )
        self.nombre_label.pack()

        # Subtítulo con el host:puerto configurado (referencia visual del destino).
        self.subtitulo_label = tk.Label(
            title_frame,
            text=f"🌐 Servidor objetivo: {self.config_host}:{self.config_puerto}",
            font=self.FONT_SUB, bg=self.COLOR_BG, fg=self.COLOR_TEXT_DIM
        )
        self.subtitulo_label.pack(pady=(2, 0))


        # ===== ESTADO =====
        # Configuracion de la interfaz del estado
        self.conn_frame = tk.Frame(main_frame, bg=self.COLOR_CARD)
        self.conn_frame.grid(row=1, column=0, sticky='ew', pady=(0, 12))

        tk.Label(
            self.conn_frame, text="🔌 ESTADO DE CONEXIÓN",
            font=self.FONT_SECTION, bg=self.COLOR_CARD, fg=self.COLOR_TEXT, pady=8
        ).pack()

        self.conn_status_label = tk.Label(
            self.conn_frame, text="🔴 Desconectado",
            font=self.FONT_STATUS, bg=self.COLOR_CARD, fg=self.COLOR_ERROR, pady=4
        )
        self.conn_status_label.pack()

        self.reconnect_status = tk.Label(
            self.conn_frame, text="",
            font=self.FONT_SUB, bg=self.COLOR_CARD, fg=self.COLOR_ORANGE
        )
        self.reconnect_status.pack(pady=(0, 10))



        # ===== ACCIONES (solo enviar) =====
        # Configuracion del apartado de enviar archivo, tamaño, colores, contenedores, botones.
        actions_frame = tk.Frame(main_frame, bg=self.COLOR_CARD)
        actions_frame.grid(row=2, column=0, sticky='ew', pady=(0, 12))

        tk.Label(
            actions_frame, text=" ENVÍO DE ARCHIVOS",
            font=self.FONT_SECTION, bg=self.COLOR_CARD, fg=self.COLOR_TEXT, pady=8
        ).pack()

        btn_container = tk.Frame(actions_frame, bg=self.COLOR_CARD)
        btn_container.pack(fill='x', padx=16, pady=(0, 14))

        # ===== DESTINO DEL ENVÍO (Broadcast o Cliente específico) =====
        # Variable booleana que indica si el envío será a TODOS (Broadcast) o a UNO.
        self.broadcast_var = tk.BooleanVar(value=True)

        # Checkbutton para activar/desactivar el modo Broadcast.
        self.check_broadcast = tk.Checkbutton(
            btn_container,
            text="Broadcast",
            variable=self.broadcast_var,
            font=self.FONT_BODY_BOLD,
            bg=self.COLOR_CARD, fg=self.COLOR_TEXT,
            selectcolor=self.COLOR_BG,
            activebackground=self.COLOR_CARD, activeforeground=self.COLOR_PRIMARY,
            cursor='hand2', bd=0, highlightthickness=0
        )
        self.check_broadcast.pack(anchor='w', pady=(0, 10))

        # Etiqueta y caja de texto para el Cliente Destino (solo aplica si NO es Broadcast).
        destino_frame = tk.Frame(btn_container, bg=self.COLOR_CARD)
        destino_frame.pack(fill='x', pady=(0, 12))

        tk.Label(
            destino_frame,
            text="Cliente Destino: ",
            font=self.FONT_SUB,
            bg=self.COLOR_CARD, fg=self.COLOR_TEXT_DIM
        ).pack(anchor='w', pady=(0, 4))

        self.entry_destino = tk.Entry(
            destino_frame,
            font=self.FONT_BODY,
            bg=self.COLOR_INPUT, fg=self.COLOR_TEXT,
            insertbackground=self.COLOR_TEXT,
            relief='flat', bd=6,
            disabledbackground=self.COLOR_BG,
            disabledforeground=self.COLOR_TEXT_DIM,
            state=tk.DISABLED  # Deshabilitado porque Broadcast está activo por defecto
        )
        self.entry_destino.pack(fill='x', ipady=3)

        # Cuando cambie el check, se habilita o deshabilita el campo destino.
        self.broadcast_var.trace_add('write', self._toggle_destino)
        # ===== FIN DESTINO =====

        self.btn_enviar = tk.Button(
            btn_container, text="📎 Seleccionar y Enviar Archivo",
            state=tk.DISABLED, command=self.enviar_archivo_dialogo,
            font=self.FONT_BUTTON, height=2,
            bg=self.COLOR_PRIMARY, fg=self.COLOR_BG,
            activebackground=self.COLOR_PRIMARY_HOVER, activeforeground=self.COLOR_BG,
            relief='flat', bd=0, cursor='hand2',
            disabledforeground=self.COLOR_TEXT_DIM
        )
        self.btn_enviar.pack(fill='x', pady=(4, 10))
        # Efecto hover para dar feedback visual al pasar el mouse por el botón.
        self._bind_hover(self.btn_enviar, self.COLOR_PRIMARY, self.COLOR_PRIMARY_HOVER)

        # ===== BARRA DE PROGRESO =====
        # Se estiliza la barra de progreso con ttk.Style para un look moderno y limpio.
        style = ttk.Style()
        try:
            style.theme_use('clam')
        except:
            pass
        style.configure(
            'Modern.Horizontal.TProgressbar',
            troughcolor=self.COLOR_BG,
            background=self.COLOR_ACCENT,
            bordercolor=self.COLOR_BG,
            lightcolor=self.COLOR_ACCENT,
            darkcolor=self.COLOR_ACCENT,
            thickness=8
        )
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            btn_container, variable=self.progress_var, maximum=100,
            style='Modern.Horizontal.TProgressbar'
        )
        self.progress_bar.pack(fill='x', pady=(2, 4))

        self.progress_label = tk.Label(
            btn_container, text="", font=self.FONT_SUB,
            bg=self.COLOR_CARD, fg=self.COLOR_TEXT_DIM
        )
        self.progress_label.pack()

        # ===== LOG =====
        #Configuracion del contenedor de los LOGS, tamaño, colores, contendores, mensajes.

        log_frame = tk.Frame(main_frame, bg=self.COLOR_CARD)
        log_frame.grid(row=3, column=0, sticky='nsew')
        log_frame.grid_rowconfigure(1, weight=1)
        log_frame.grid_columnconfigure(0, weight=1)

        tk.Label(
            log_frame, text="📋 Registro de Actividad",
            font=self.FONT_SECTION, bg=self.COLOR_CARD, fg=self.COLOR_TEXT, pady=8
        ).grid(row=0, column=0, sticky='ew')

        self.log_text = scrolledtext.ScrolledText(
            log_frame, font=self.FONT_MONO, wrap=tk.WORD,
            padx=12, pady=12, bg=self.COLOR_BG, fg=self.COLOR_TEXT, height=12,
            relief='flat', bd=0, insertbackground=self.COLOR_TEXT
        )
        self.log_text.grid(row=1, column=0, sticky='nsew', padx=8, pady=(0, 8))

        self.log_text.tag_config('success', foreground=self.COLOR_SUCCESS)
        self.log_text.tag_config('error', foreground=self.COLOR_ERROR)
        self.log_text.tag_config('info', foreground=self.COLOR_PRIMARY)
        self.log_text.tag_config('transfer', foreground=self.COLOR_ACCENT)
        self.log_text.tag_config('warning', foreground=self.COLOR_WARNING)
        self.log_text.tag_config('reconnect', foreground=self.COLOR_ORANGE)

        # ===== ESTADÍSTICAS =====
        # Configuracion de contenedores, color de la recibidos y reconexiones
        stats_frame = tk.Frame(main_frame, bg=self.COLOR_BG)
        stats_frame.grid(row=4, column=0, sticky='ew', pady=(12, 0))

        self.archivos_label = tk.Label(
            stats_frame, text="📥 Recibidos: 0",
            font=self.FONT_BODY_BOLD, bg=self.COLOR_BG, fg=self.COLOR_SUCCESS
        )
        self.archivos_label.pack(side='left')

        self.reconexiones_label = tk.Label(
            stats_frame, text="🔄 Reconexiones: 0",
            font=self.FONT_BODY_BOLD, bg=self.COLOR_BG, fg=self.COLOR_ORANGE
        )
        self.reconexiones_label.pack(side='right')

        # Iniciar
        threading.Thread(target=self.bucle_conexion, daemon=True).start()  #Inciar el proceso de hilo de gestion de conexion y reconexion
        threading.Thread(target=self.hilo_recepcion, daemon=True).start()  #Iniciar proceso de hilo de escuchar datos entrantes

        self.root.mainloop()  #Incio de eventos de la biblioteca utilizada para el fronted


    # ==================== UTILIDADES DE UI ====================
    def _bind_hover(self, widget, color_normal, color_hover):
        """
        Aplica un efecto hover a un widget: cambia el color de fondo
        cuando el mouse entra y vuelve al color original cuando sale.
        Solo actúa si el widget está en estado normal (no deshabilitado).
        """
        def on_enter(e):
            if str(widget['state']) != 'disabled':
                widget.config(bg=color_hover)
        def on_leave(e):
            if str(widget['state']) != 'disabled':
                widget.config(bg=color_normal)
        widget.bind('<Enter>', on_enter)
        widget.bind('<Leave>', on_leave)


    # ==================== TOGGLE DESTINO ====================
    def _toggle_destino(self, *args):
        """
        Habilita el campo de texto 'Cliente Destino' cuando se desactiva Broadcast,
        y lo deshabilita cuando Broadcast está activo.
        """
        if self.broadcast_var.get():
            self.entry_destino.config(state=tk.DISABLED)
        else:
            self.entry_destino.config(state=tk.NORMAL)
            self.entry_destino.focus_set()  # Pone el cursor en el campo automáticamente


    def cargar_configuracion(self):
        config = configparser.ConfigParser() #Utiliza la biblioteca para leer config.ini
        self.config_host = '127.0.0.1'  #En caso que no haya lee los valores definidos a continuacion
        self.config_puerto = 5000
        self.config_max_intentos = 3
        self.config_tiempo_entre_intentos = 3
        self.config_timeout_conexion = 3
        self.config_timeout_transferencia = 30
        self.config_tamano_maximo = 2
        self.config_intervalo_ping = 3
        self.config_host_balanceador = '127.0.0.1'
        self.config_puerto_balanceador = 6000

        try:
            if os.path.exists('config.ini'):    #Si dentro de los asrchivos existe
                config.read('config.ini')       #Lee el archivo
                if 'CLIENTE' in config:     #Extrae las variables y los convierte en int cuando encuentre [cliente]
                    self.config_host = config['CLIENTE'].get('host', '127.0.0.1')
                    self.config_puerto = int(config['CLIENTE'].get('puerto', 5000))
                    self.config_max_intentos = int(config['CLIENTE'].get('max_intentos', 3))
                    self.config_tiempo_entre_intentos = int(config['CLIENTE'].get('tiempo_entre_intentos', 3))
                    self.config_timeout_conexion = int(config['CLIENTE'].get('timeout_conexion', 3))
                    self.config_timeout_transferencia = int(config['CLIENTE'].get('timeout_transferencia', 30))
                    self.config_tamano_maximo = int(config['CLIENTE'].get('tamano_maximo_mb', 2))
                    self.config_intervalo_ping = int(config['CLIENTE'].get('intervalo_ping', 3))
                    self.config_host_balanceador = config['CLIENTE'].get('host_balanceador', '127.0.0.1')
                    self.config_puerto_balanceador = int(config['CLIENTE'].get('puerto_balanceador', 6000))
            print("✓ Configuración cargada")
        except Exception as e:
            print(f"Error config: {e}")



    def crear_directorio_descargas(self):
        try:
            ruta = os.path.join(os.getcwd(), self.directorio_descargas) # Crea la carpeta archivos_recibidos
            if not os.path.exists(ruta):  #Valida si hay carpeta creada en la ruta
                os.makedirs(ruta)
            self.directorio_descargas = ruta #Si falla usa el directorio actual
        except:
            self.directorio_descargas = os.getcwd()



    def log(self, mensaje, tag='info'): #Añade mensaje y tag que es el color del mensaje
        timestamp = datetime.now().strftime('%H:%M:%S') #Obtiene la hora actual y el formato
        try:
            self.root.after(0, lambda: self.log_text.insert(    #  Inserta el mensaje y el tiempo en la pantalla de log
                tk.END, f"[{timestamp}] {mensaje}\n", tag))
            self.root.after(0, lambda: self.log_text.see(tk.END)) #le indicas al sistemas que cuando tengas 0 mls envie el mesajes completo y tk.END baja de forma automatica el scroll
        except:
            pass  #Omite algun error y evita cerrar la pantalla

    # ==================== CONEXIÓN ====================
    def bucle_conexion(self):
        while self.debe_reconectar:
            if not self.conectado:
                # CAMBIO: si ya hay un ciclo de reconexión corriendo, no interferir.
                # Esto evita que bucle_conexion y ciclo_reconexion intenten conectar a la vez.
                if not self.reconectando:
                    if self.intentar_conexion():
                        threading.Thread(target=self.hilo_ping, daemon=True).start()
                    else:
                        self.ciclo_reconexion()
            else:
                time.sleep(1)


    def intentar_conexion(self):
        """
        Estrategia:
        1. Si ya tenemos un servidor asignado → reintentar SIEMPRE ahí.
           NUNCA preguntar al balanceador mientras tengamos asignación.
           El balanceador ya se encarga de relanzarlo.
        2. Solo si NO tenemos servidor (primera conexión) → preguntar al balanceador.
        """
        # ===== Si ya tenemos servidor asignado, solo reintentar ahí =====
        if self.servidor_host_actual and self.servidor_puerto_actual:
            if self._conectar_a(self.servidor_host_actual, self.servidor_puerto_actual):
                return True
            # No liberar la asignación. Seguir reintentando al MISMO servidor.
            # El balanceador ya lo está relanzando.
            self.log(
                f"⏳ Esperando que {self.servidor_host_actual}:{self.servidor_puerto_actual} reviva...",
                'reconnect'
            )
            return False

        # ===== Solo si NO tenemos servidor, consultar al balanceador =====
        servidor_host, servidor_puerto = self.consultar_balanceador()
        if servidor_host is None:
            return False
        return self._conectar_a(servidor_host, servidor_puerto)

    def _conectar_a(self, servidor_host, servidor_puerto):
        """Intenta abrir una conexión al servidor especificado y completar el handshake."""
        # Cerrar socket anterior si existe
        try:
            if self.socket:
                self.socket.close()
        except:
            pass
        self.socket = None

        try:
            # 1. Crear socket y conectar
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(self.config_timeout_conexion)
            self.socket.connect((servidor_host, servidor_puerto))

            # 2. Guardar asignación
            self.servidor_host_actual = servidor_host
            self.servidor_puerto_actual = servidor_puerto

            # 3. Enviar identidad
            nombre_para_servidor = self.nombre_cliente if self.nombre_cliente != "Cliente Desconocido" else ""
            nombre_bytes = nombre_para_servidor.encode('utf-8')
            self.socket.sendall(
                b'C' + len(nombre_bytes).to_bytes(2, byteorder='big') + nombre_bytes
            )

            # 4. Recibir confirmación del servidor
            nombre_len_bytes = self.recibir_exacto(2)
            if not nombre_len_bytes or len(nombre_len_bytes) < 2:
                raise ConnectionError("El servidor no respondió correctamente")

            nombre_len = int.from_bytes(nombre_len_bytes, byteorder='big')
            nombre_bytes = self.recibir_exacto(nombre_len)
            self.nombre_cliente = nombre_bytes.decode('utf-8')

            # 5. Actualizar estado
            self.conectado = True
            self.reconectando = False
            self.intentos_actuales = 0

            self.root.after(0, lambda: self.root.title(
                f"{self.nombre_cliente} - Distribución de Archivos"))
            self.root.after(0, lambda: self.nombre_label.config(
                text=f"📁 {self.nombre_cliente}", fg='#a6e3a1'))

            self.log(
                f"✓ Conectado como {self.nombre_cliente} en {servidor_host}:{servidor_puerto}",
                'success'
            )
            self.root.after(0, self.actualizar_estado_conectado)

            self.socket.settimeout(self.config_timeout_transferencia)
            return True

        except Exception as e:
            # Cerrar socket fallido
            try:
                if self.socket:
                    self.socket.close()
            except:
                pass
            self.socket = None
            self.conectado = False
            self.log(f"[!] Falló conexión a {servidor_host}:{servidor_puerto}: {e}", 'error')
            return False


    def ciclo_reconexion(self):
        #Evista varias reconexiones simultaneas
        if self.reconectando:
            return

        #Incializa para recoenctar y # de intentos
        self.reconectando = True
        self.intentos_actuales = 0

        #Envia mensaje del error al no generar la conexion junto con numero de intetos de reconexion
        self.root.after(0, lambda: self.conn_status_label.config(
            text="🟡 Servidor no disponible. Reintentando...",
            fg='#f9e2af'))

        self.log(f"⚠️ Servidor caído. {self.max_intentos} intentos cada {self.tiempo_entre_intentos}s...", 'warning')

        # CAMBIO: se usa un bucle en lugar de llamarse recursivamente a sí mismo.
        # Evita acumular llamadas en la pila si el servidor permanece caído durante mucho tiempo.
        while self.debe_reconectar:
            self.intentos_actuales = 0

            while self.intentos_actuales < self.max_intentos and self.debe_reconectar:
                self.intentos_actuales += 1

                # Muestra la cantidad de intentos sobre el total
                self.root.after(0, lambda i=self.intentos_actuales: self.actualizar_ui_intentos(i))
                self.log(f"🔄 Intento {self.intentos_actuales}/{self.max_intentos}...", 'reconnect')

                #Entre intentos espera el tiempo correspodiente en trozos de 1s
                for _ in range(self.tiempo_entre_intentos):
                    if not self.debe_reconectar:
                        self.reconectando = False
                        return
                    time.sleep(1)

                # CAMBIO: intentar_conexion conserva el mismo servidor si ya existe una asignación.
                if self.intentar_conexion():
                    self.reconexiones_exitosas += 1
                    self.root.after(0, self.actualizar_contador_reconexiones)
                    self.reconectando = False
                    threading.Thread(target=self.hilo_ping, daemon=True).start()
                    return

            if not self.debe_reconectar:
                self.reconectando = False
                return

            #Apenas terminen el max de intentos lanza mensajes y comienza otro ciclo
            self.log(f"❌ Se agotaron los {self.max_intentos} intentos. Nuevo ciclo en {self.tiempo_entre_intentos}s...", 'error')
            self.root.after(0, lambda: self.conn_status_label.config(
                text="🔴 Servidor no disponible",
                fg='#f38ba8'))
            self.root.after(0, lambda: self.reconnect_status.config(
                text=f"⏳ Reintentando en {self.tiempo_entre_intentos}s...",
                fg='#f38ba8'))

            time.sleep(self.tiempo_entre_intentos)

        self.reconectando = False

    #Actualiza etiquetas de estado durante la reconexion
    def actualizar_ui_intentos(self, intento):
        self.conn_status_label.config(
            text=f"🟡 Reintentando conexión... ({intento}/{self.max_intentos})",
            fg='#f9e2af')
        self.reconnect_status.config(
            text=f"⏳ Intento {intento} de {self.max_intentos} | Esperando {self.tiempo_entre_intentos}s",
            fg='#fab387')

    #Pone en la UI en verde y habilita el boton en verde
    def actualizar_estado_conectado(self):
        self.conn_status_label.config(text="🟢 Conectado al servidor", fg='#a6e3a1')
        self.reconnect_status.config(text="")
        self.btn_enviar.config(state=tk.NORMAL, bg=self.COLOR_PRIMARY)

    #Actaulia en GUI el contadir de reconexiones
    def actualizar_contador_reconexiones(self):
        self.reconexiones_label.config(text=f"🔄 Reconexiones: {self.reconexiones_exitosas}")

    #Cada intervalo del ping envia un byte 'P' para mantener viva la conexion o detectar caidas
    def hilo_ping(self):
        while self.conectado and self.debe_reconectar:
            try:
                time.sleep(self.config_intervalo_ping)
                if self.conectado and self.socket:
                    self.socket.sendall(b'P')
            except Exception:
                # CAMBIO: si falla el ping, se fuerza la desconexión para iniciar la reconexión.
                if self.conectado:
                    self.desconectar()
                break

    # ==================== RECEPCIÓN ====================

    def hilo_recepcion(self):
        #Bucle infinito mientras debe reconectar
        while self.debe_reconectar:
            if self.conectado and self.socket:
                try:
                    tipo = self.socket.recv(1)  #Si esta conectado en 1 byte para saber el mensaje
                    if not tipo:
                        self.desconectar()
                        continue
                    #Si recibe F llama al metodo
                    if tipo == b'F':
                        self.recibir_archivo()
                    elif tipo == b'P':
                        # CAMBIO: el servidor responde PONG (4 bytes). Como ya leímos la P,
                        # consumimos los 3 bytes restantes para mantener sincronizado el protocolo.
                        respuesta_pong = self.recibir_exacto(3)
                        if respuesta_pong != b'ONG':
                            self.log("[!] Respuesta PONG inválida", 'warning')
                except socket.timeout:
                    continue
                except Exception:
                    if self.conectado:
                        self.desconectar()
                    time.sleep(0.5)
            else:
                time.sleep(0.5)

    def recibir_archivo(self):
        try:
            meta_len_bytes = self.recibir_exacto(4)  #Espera los 4 bytes del texto
            if not meta_len_bytes or len(meta_len_bytes) != 4: #Lee 4 bytes ASCII con la longitud del nombre
                return
            nombre_len = int(meta_len_bytes.decode('utf-8'))

            nombre_archivo = self.recibir_exacto(nombre_len).decode('utf-8') #Lee el nombre

            meta_size_bytes = self.recibir_exacto(10) #Ahoara exige leer los 10bytes
            tamano_archivo = int(meta_size_bytes.decode('utf-8')) #Convierte a enteros

            if tamano_archivo > self.TAMANO_MAXIMO: #Compara el tamaño dela rchvio con el maximo de archivo
                self.consumir_bytes(tamano_archivo)
                return

            #En caso que cumpla, le envia los bytes retntes, epro enc aso que se caiga no guarada archivos corruptos
            bytes_recibidos = self.recibir_exacto(tamano_archivo)
            if len(bytes_recibidos) != tamano_archivo:
                return

            #Limipa el mnombr eliminado y l ogaurda en el directorio y confirma el archivo recibido
            nombre_limpio = self.sanitizar(nombre_archivo)
            ruta = os.path.join(self.directorio_descargas, f"recibido_{nombre_limpio}")

            with open(ruta, 'wb') as f:
                f.write(bytes_recibidos)
                f.flush()
                os.fsync(f.fileno())

            #Incrementa archivos recibidos y confirma la entrega del archivo , nombre tamañao y actualiza el contador de la interfaz
            self.archivos_recibidos += 1
            self.log(f"✓ [RECIBIDO] {nombre_archivo} ({self.formatear_tamano(tamano_archivo)})", 'success')
            self.root.after(0, self.actualizar_contador_archivos)
            self.root.after(0, lambda n=nombre_archivo: self.mostrar_notificacion(n))
        except Exception as e:
            self.log(f"[!] Error recibir: {e}", 'error')



    def recibir_exacto(self, tamano):
        # Se crea una variabkes donde se va recibir los datos, lo cual lo que se reciba de la variable hasta que sea mayor al tamaño
        datos = b""
        while len(datos) < tamano:
            chunk = self.socket.recv(min(4096, tamano - len(datos))) #Va descontando del total socket recibido
            if not chunk:
                raise ConnectionResetError("Cerrada")   #Chunk valida si esta vacio  o no valida que este recibiendo los datos
            datos += chunk
        return datos

    def consumir_bytes(self, tamano):
        #Descarta los bytes que sobran del socket, los recibe pero elimina el restante de los bytes
        restantes = tamano
        while restantes > 0:
            chunk = self.socket.recv(min(4096, restantes))
            if not chunk:
                break
            restantes -= len(chunk)
    #Marca no conectado, cierra el socket deshabilita el boton
    def desconectar(self):
        self.conectado = False
        try:
            if self.socket:
                self.socket.close()
        except:
            pass
        self.socket = None

        self.root.after(0, lambda: self.btn_enviar.config(state=tk.DISABLED))
        self.root.after(0, lambda: self.conn_status_label.config(
            text="🔴 Desconectado del servidor",
            fg='#f38ba8'))

        self.log("⚠️ Conexión perdida", 'warning')

        # CAMBIO: solo lanzar ciclo de reconexión si no hay uno corriendo ya.
        if self.debe_reconectar and not self.reconectando:
            threading.Thread(target=self.ciclo_reconexion, daemon=True).start()


        # ==================== CONSULTA AL BALANCEADOR ====================
    def consultar_balanceador(self):
        """Se conecta al balanceador, envía su identidad actual (si la tiene)
        y recibe 'host:puerto|Cliente N'."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock_temp:
                sock_temp.settimeout(self.config_timeout_conexion)
                sock_temp.connect((self.config_host_balanceador, self.config_puerto_balanceador))

                # ===== ENVIAR IDENTIDAD =====
                # Si ya tenemos un nombre ("Cliente N"), pedimos reasignación al MISMO servidor.
                # Si no, somos un cliente nuevo.
                if self.nombre_cliente and self.nombre_cliente != "Cliente Desconocido":
                    mensaje = f"REASIGNAR|{self.nombre_cliente}".encode('utf-8')
                else:
                    mensaje = b"NUEVO"
                sock_temp.sendall(mensaje)

                respuesta = sock_temp.recv(1024).decode('utf-8').strip()

            partes = respuesta.split('|', 1)
            host, puerto = partes[0].split(':')

            if len(partes) == 2 and partes[1].strip():
                self.nombre_cliente = partes[1].strip()

            self.log(
                f"📡 Balanceador asignó: {host}:{puerto} para {self.nombre_cliente}",
                'info'
            )
            return host, int(puerto)
        except Exception as e:
            self.log(f"[!] No se pudo contactar al balanceador: {e}", 'error')
            return None, None    # ==================== ENVÍO ====================


    def enviar_archivo_dialogo(self):

        #Valida si no esta conectado
        if not self.conectado:
            messagebox.showwarning("⚠️", "No está conectado al servidor")
            return

        # ===== VALIDACIÓN DEL DESTINO =====
        # Si NO es Broadcast, se debe indicar un cliente destino válido.
        # Se acepta cualquier "Cliente N" donde N sea un entero positivo,
        # porque el sistema soporta N clientes dinámicos (no solo 3).
        if not self.broadcast_var.get():
            destino = self.entry_destino.get().strip()

            # 1. No puede estar vacío.
            if not destino:
                messagebox.showwarning(
                    "⚠️ Destino requerido",
                    "Debe escribir el Cliente Destino.\nEjemplo: Cliente 1, Cliente 7, Cliente 42..."
                )
                return

            # 2. Debe tener el formato "Cliente N" (N entero positivo).
            #    Se usa expresión regular para aceptar cualquier número.
            if not re.fullmatch(r"Cliente\s+\d+", destino, flags=re.IGNORECASE):
                messagebox.showwarning(
                    "⚠️ Formato inválido",
                    f"'{destino}' no tiene el formato correcto.\n"
                    "Use: 'Cliente N' (ej: Cliente 1, Cliente 5, Cliente 12)"
                )
                return

            # 3. Normaliza el nombre: "cliente 3" → "Cliente 3"
            numero = re.search(r"\d+", destino).group()
            destino = f"Cliente {numero}"
            self.entry_destino.delete(0, tk.END)
            self.entry_destino.insert(0, destino)
        # ===== FIN VALIDACIÓN =====

        #Abre la ventana pra buscar el archivo, se realizara un filtro solo para archivos
        ruta = filedialog.askopenfilename(
            title=f"Seleccionar archivo (máx. {self.config_tamano_maximo} MB)",
            filetypes=[
                ("Archivos", "*.pdf *.doc *.docx *.txt *.xls *.xlsx *.csv *.png *.jpg *.jpeg *.gif *.zip *.rar"),
                ("Todos", "*.*")])
        if not ruta:
            return

        if not os.path.isfile(ruta):
            return

        #Valida tamaño del archivo
        tamano = os.path.getsize(ruta)
        if tamano > self.TAMANO_MAXIMO:
            messagebox.showerror(
                "❌ Archivo Demasiado Grande",
                f"📄 {os.path.basename(ruta)}\n"
                f"📊 {self.formatear_tamano(tamano)}\n"
                f"⚠️ Máximo: {self.formatear_tamano(self.TAMANO_MAXIMO)}")
            self.log(f"[!] Rechazado: {os.path.basename(ruta)} ({self.formatear_tamano(tamano)})", 'error')
            return

        # ===== DESTINO FINAL =====
        # Se calcula el destino antes de lanzar el hilo de envío.
        # "ALL" significa Broadcast; cualquier otra cosa es un nombre de cliente.
        destino = "ALL" if self.broadcast_var.get() else self.entry_destino.get().strip()
        # ===== FIN DESTINO =====

        #Ejecucion de hilo segundo plano para enviar el archivo
        threading.Thread(target=self.tarea_enviar, args=(ruta, destino), daemon=True).start()

    def tarea_enviar(self, ruta, destino):
        """
        Envía el archivo indicado.
        destino = "ALL"       → Broadcast (todos los clientes)
        destino = "Cliente N" → Solo ese cliente
        """

        #Lee todo el archivo de memoria
        try:
            nombre = os.path.basename(ruta)
            tamano = os.path.getsize(ruta)

            self.root.after(0, lambda: self.progress_label.config(text=f"Enviando: {nombre}"))
            self.root.after(0, lambda: self.progress_var.set(0))
            self.root.after(0, lambda: self.btn_enviar.config(state=tk.DISABLED))

            with open(ruta, 'rb') as f:
                contenido = f.read()
            #Traduce a utf-8
            meta_len = str(len(nombre)).zfill(4).encode('utf-8')
            nombre_bytes = nombre.encode('utf-8')
            meta_size = str(tamano).zfill(10).encode('utf-8')

            # ===== CAMPO DESTINO (20 bytes fijos) =====
            # Se rellena con espacios a la derecha hasta 20 bytes para que el servidor
            # siempre lea la misma cantidad y no tenga que parsear longitudes variables.
            # Soporta hasta 20 caracteres (suficiente para "Cliente 999999999").
            destino_bytes = destino.encode('utf-8')[:20].ljust(20, b' ')
            # ===== FIN CAMPO DESTINO =====

            #Construccion del paquete y envio del paquete
            # El paquete queda: [F][4B len_nombre][nombre][10B tamaño][20B destino][contenido]
            paquete = b'F' + meta_len + nombre_bytes + meta_size + destino_bytes + contenido
            self.socket.sendall(paquete) #Envia el paquete por socket

            # ===== LOG SEGÚN EL DESTINO =====
            if destino == "ALL":
                self.log(f"✓ Enviado (Broadcast): {nombre} ({self.formatear_tamano(tamano)})", 'success')
            else:
                self.log(f"✓ Enviado a {destino}: {nombre} ({self.formatear_tamano(tamano)})", 'success')
            # ===== FIN LOG =====

            self.root.after(0, lambda: self.progress_var.set(100))
            self.root.after(0, lambda: self.progress_label.config(text=f"✅ {nombre}"))
        except Exception as e:
            self.log(f"[!] Error enviar: {e}", 'error')
            messagebox.showerror("❌", f"Error: {e}")
        finally:
            self.root.after(0, lambda: self.btn_enviar.config(state=tk.NORMAL))

    #Muestra la notificacion de archivos recibidos
    def mostrar_notificacion(self, nombre):
        messagebox.showinfo(
            "🎉 Nuevo Archivo Recibido",
            f"{self.nombre_cliente}, recibiste:\n\n📄 {nombre}\n📁 En: archivos_recibidos/")

    #Actualizar contador de archivos
    def actualizar_contador_archivos(self):
        self.archivos_label.config(text=f"📥 Recibidos: {self.archivos_recibidos}")

    # ==================== UTILIDADES ====================

    #Reemplaza caracteres no válidos para nombres de archivo y limita a 200 caracteres.
    def sanitizar(self, nombre):
        for c in ['/', '\\', ':', '*', '?', '"', '<', '>', '|']:
            nombre = nombre.replace(c, '_')
        return nombre[:200]

    #Convierte bytes a B, KB, MB o GB con dos decimales.
    def formatear_tamano(self, tamano):
        if tamano < 1024:
            return f"{tamano} B"
        elif tamano < 1024 * 1024:
            return f"{tamano/1024:.2f} KB"
        elif tamano < 1024 * 1024 * 1024:
            return f"{tamano/(1024*1024):.2f} MB"
        return f"{tamano/(1024*1024*1024):.2f} GB"

    def cerrar_cliente(self):
        self.debe_reconectar = False
        try:
            if self.socket:
                self.socket.close()
        except:
            pass
        self.root.destroy()


if __name__ == "__main__":
    ClienteGUI()