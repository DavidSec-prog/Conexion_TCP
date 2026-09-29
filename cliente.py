import socket
import threading
import os
import time
import configparser
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk
from datetime import datetime


class ClienteGUI:
    def __init__(self):
        self.cargar_configuracion()
        
        self.root = tk.Tk()
        self.root.title("Cliente TCP - Distribución de Archivos")
        self.root.geometry("780x750")
        self.root.configure(bg='#1e1e2e')
        self.root.protocol("WM_DELETE_WINDOW", self.cerrar_cliente)
        
        self.TAMANO_MAXIMO = self.config_tamano_maximo * 1024 * 1024
        self.nombre_cliente = "Cliente Desconocido"
        self.directorio_descargas = "archivos_recibidos"
        self.crear_directorio_descargas()
        
        self.conectado = False
        self.reconectando = False
        self.debe_reconectar = True
        self.intentos_actuales = 0
        self.max_intentos = self.config_max_intentos
        self.tiempo_entre_intentos = self.config_tiempo_entre_intentos
        self.reconexiones_exitosas = 0
        self.archivos_recibidos = 0
        self.socket = None
        
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        
        main_frame = tk.Frame(self.root, bg='#1e1e2e')
        main_frame.grid(row=0, column=0, sticky='nsew', padx=10, pady=10)
        main_frame.grid_rowconfigure(3, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)
        
        # ===== ENCABEZADO =====
        title_frame = tk.Frame(main_frame, bg='#1e1e2e')
        title_frame.grid(row=0, column=0, sticky='ew', pady=(0, 8))
        
        self.nombre_label = tk.Label(
            title_frame, text="📁 Cliente",
            font=('Arial', 14, 'bold'), bg='#1e1e2e', fg='#89b4fa'
        )
        self.nombre_label.pack()
        
        # ===== ESTADO =====
        self.conn_frame = tk.Frame(main_frame, bg='#313244', relief='raised', bd=2)
        self.conn_frame.grid(row=1, column=0, sticky='ew', pady=(0, 8))
        
        tk.Label(
            self.conn_frame, text="🔌 ESTADO DE CONEXIÓN",
            font=('Arial', 10, 'bold'), bg='#313244', fg='#cdd6f4', pady=5
        ).pack()
        
        self.conn_status_label = tk.Label(
            self.conn_frame, text="🔴 Desconectado",
            font=('Arial', 12, 'bold'), bg='#313244', fg='#f38ba8', pady=5
        )
        self.conn_status_label.pack()
        
        self.reconnect_status = tk.Label(
            self.conn_frame, text="",
            font=('Arial', 10), bg='#313244', fg='#fab387'
        )
        self.reconnect_status.pack(pady=(0, 8))
        
        # ===== ACCIONES (solo enviar) =====
        actions_frame = tk.Frame(main_frame, bg='#313244', relief='raised', bd=2)
        actions_frame.grid(row=2, column=0, sticky='ew', pady=(0, 8))
        
        tk.Label(
            actions_frame, text="📤 ENVÍO DE ARCHIVOS",
            font=('Arial', 10, 'bold'), bg='#313244', fg='#cdd6f4', pady=5
        ).pack()
        
        btn_container = tk.Frame(actions_frame, bg='#313244')
        btn_container.pack(fill='x', padx=10, pady=8)
        
        self.btn_enviar = tk.Button(
            btn_container, text="📎 Seleccionar y Enviar Archivo",
            state=tk.DISABLED, command=self.enviar_archivo_dialogo,
            font=('Arial', 11, 'bold'), height=2,
            bg='#89b4fa', fg='#1e1e2e',
            activebackground='#b4befe', cursor='hand2'
        )
        self.btn_enviar.pack(fill='x')
        
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            btn_container, variable=self.progress_var, maximum=100
        )
        self.progress_bar.pack(fill='x', pady=(8, 3))
        
        self.progress_label = tk.Label(
            btn_container, text="", font=('Arial', 9),
            bg='#313244', fg='#6c7086'
        )
        self.progress_label.pack()
        
        # ===== LOG =====
        log_frame = tk.Frame(main_frame, bg='#313244')
        log_frame.grid(row=3, column=0, sticky='nsew')
        log_frame.grid_rowconfigure(1, weight=1)
        log_frame.grid_columnconfigure(0, weight=1)
        
        tk.Label(
            log_frame, text="📋 Registro de Actividad",
            font=('Arial', 11, 'bold'), bg='#313244', fg='#cdd6f4', pady=5
        ).grid(row=0, column=0, sticky='ew')
        
        self.log_text = scrolledtext.ScrolledText(
            log_frame, font=('Arial', 9), wrap=tk.WORD,
            padx=10, pady=10, bg='#1e1e2e', fg='#cdd6f4', height=12
        )
        self.log_text.grid(row=1, column=0, sticky='nsew')
        
        self.log_text.tag_config('success', foreground='#a6e3a1')
        self.log_text.tag_config('error', foreground='#f38ba8')
        self.log_text.tag_config('info', foreground='#89b4fa')
        self.log_text.tag_config('transfer', foreground='#cba6f7')
        self.log_text.tag_config('warning', foreground='#f9e2af')
        self.log_text.tag_config('reconnect', foreground='#fab387')
        
        # ===== ESTADÍSTICAS =====
        stats_frame = tk.Frame(main_frame, bg='#1e1e2e')
        stats_frame.grid(row=4, column=0, sticky='ew', pady=(8, 0))
        
        self.archivos_label = tk.Label(
            stats_frame, text="📥 Recibidos: 0",
            font=('Arial', 10, 'bold'), bg='#1e1e2e', fg='#a6e3a1'
        )
        self.archivos_label.pack(side='left')
        
        self.reconexiones_label = tk.Label(
            stats_frame, text="🔄 Reconexiones: 0",
            font=('Arial', 10, 'bold'), bg='#1e1e2e', fg='#fab387'
        )
        self.reconexiones_label.pack(side='right')
        
        # Iniciar
        threading.Thread(target=self.bucle_conexion, daemon=True).start()
        threading.Thread(target=self.hilo_recepcion, daemon=True).start()
        
        self.root.mainloop()
    
    def cargar_configuracion(self):
        config = configparser.ConfigParser()
        self.config_host = '127.0.0.1'
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
            if os.path.exists('config.ini'):
                config.read('config.ini')
                if 'CLIENTE' in config:
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
            ruta = os.path.join(os.getcwd(), self.directorio_descargas)
            if not os.path.exists(ruta):
                os.makedirs(ruta)
            self.directorio_descargas = ruta
        except:
            self.directorio_descargas = os.getcwd()
    
    def log(self, mensaje, tag='info'):
        timestamp = datetime.now().strftime('%H:%M:%S')
        try:
            self.root.after(0, lambda: self.log_text.insert(
                tk.END, f"[{timestamp}] {mensaje}\n", tag))
            self.root.after(0, lambda: self.log_text.see(tk.END))
        except:
            pass
    
    # ==================== CONEXIÓN ====================
    def bucle_conexion(self):
        while self.debe_reconectar:
            if not self.conectado:
                if self.intentar_conexion():
                    threading.Thread(target=self.hilo_ping, daemon=True).start()
                else:
                    self.ciclo_reconexion()
            else:
                time.sleep(1)
    
    def consultar_balanceador(self):
        """Se conecta al balanceador, recibe 'host:puerto\\n' y devuelve (host, puerto)."""
        try:
            sock_temp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock_temp.settimeout(self.config_timeout_conexion)
            sock_temp.connect((self.config_host_balanceador, self.config_puerto_balanceador))
            
            respuesta = sock_temp.recv(1024).decode('utf-8').strip()
            sock_temp.close()
            
            host, puerto = respuesta.split(':')
            self.log(f"📡 Balanceador asignó: {host}:{puerto}", 'info')
            return host, int(puerto)
        except Exception as e:
            self.log(f"[!] No se pudo contactar al balanceador: {e}", 'error')
            return None, None
    
    def intentar_conexion(self):
        try:
            # 1. Preguntar al balanceador qué servidor me toca
            servidor_host, servidor_puerto = self.consultar_balanceador()
            if servidor_host is None:
                return False
            
            # 2. Conectarse al servidor real asignado
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(self.config_timeout_conexion)
            self.socket.connect((servidor_host, servidor_puerto))
            
            nombre_len_bytes = self.recibir_exacto(2)
            if not nombre_len_bytes or len(nombre_len_bytes) < 2:
                return False
            
            nombre_len = int.from_bytes(nombre_len_bytes, byteorder='big')
            nombre_bytes = self.recibir_exacto(nombre_len)
            self.nombre_cliente = nombre_bytes.decode('utf-8')
            
            self.conectado = True
            self.reconectando = False
            self.intentos_actuales = 0
            
            self.root.after(0, lambda: self.root.title(
                f"{self.nombre_cliente} - Distribución de Archivos"))
            self.root.after(0, lambda: self.nombre_label.config(
                text=f"📁 {self.nombre_cliente}", fg='#a6e3a1'))
            
            self.log(f"✓ Conectado como {self.nombre_cliente} (servidor {servidor_host}:{servidor_puerto})", 'success')
            self.root.after(0, self.actualizar_estado_conectado)
            
            self.socket.settimeout(self.config_timeout_transferencia)
            return True
        except:
            return False
    
    def ciclo_reconexion(self):
        if self.reconectando:
            return
        
        self.reconectando = True
        self.intentos_actuales = 0
        
        self.root.after(0, lambda: self.conn_status_label.config(
            text="🟡 Servidor no disponible. Reintentando...",
            fg='#f9e2af'))
        
        self.log(f"⚠️ Servidor caído. {self.max_intentos} intentos cada {self.tiempo_entre_intentos}s...", 'warning')
        
        while self.intentos_actuales < self.max_intentos and self.debe_reconectar:
            self.intentos_actuales += 1
            
            self.root.after(0, lambda i=self.intentos_actuales: self.actualizar_ui_intentos(i))
            self.log(f"🔄 Intento {self.intentos_actuales}/{self.max_intentos}...", 'reconnect')
            
            for _ in range(self.tiempo_entre_intentos):
                if not self.debe_reconectar:
                    return
                time.sleep(1)
            
            if self.intentar_conexion():
                self.reconexiones_exitosas += 1
                self.root.after(0, self.actualizar_contador_reconexiones)
                self.reconectando = False
                threading.Thread(target=self.hilo_ping, daemon=True).start()
                return
        
        self.log(f"❌ Se agotaron los {self.max_intentos} intentos. Nuevo ciclo en {self.tiempo_entre_intentos}s...", 'error')
        self.root.after(0, lambda: self.conn_status_label.config(
            text="🔴 Servidor no disponible",
            fg='#f38ba8'))
        self.root.after(0, lambda: self.reconnect_status.config(
            text=f"⏳ Reintentando en {self.tiempo_entre_intentos}s...",
            fg='#f38ba8'))
        
        time.sleep(self.tiempo_entre_intentos)
        self.reconectando = False
        if self.debe_reconectar:
            self.ciclo_reconexion()
    
    def actualizar_ui_intentos(self, intento):
        self.conn_status_label.config(
            text=f"🟡 Reintentando conexión... ({intento}/{self.max_intentos})",
            fg='#f9e2af')
        self.reconnect_status.config(
            text=f"⏳ Intento {intento} de {self.max_intentos} | Esperando {self.tiempo_entre_intentos}s",
            fg='#fab387')
    
    def actualizar_estado_conectado(self):
        self.conn_status_label.config(text="🟢 Conectado al servidor", fg='#a6e3a1')
        self.reconnect_status.config(text="")
        self.btn_enviar.config(state=tk.NORMAL, bg='#89b4fa')
    
    def actualizar_contador_reconexiones(self):
        self.reconexiones_label.config(text=f"🔄 Reconexiones: {self.reconexiones_exitosas}")
    
    def hilo_ping(self):
        while self.conectado and self.debe_reconectar:
            try:
                time.sleep(self.config_intervalo_ping)
                if self.conectado and self.socket:
                    self.socket.sendall(b'P')
            except:
                break
    
    # ==================== RECEPCIÓN ====================
    def hilo_recepcion(self):
        while self.debe_reconectar:
            if self.conectado and self.socket:
                try:
                    tipo = self.socket.recv(1)
                    if not tipo:
                        self.desconectar()
                        continue
                    
                    if tipo == b'F':
                        self.recibir_archivo()
                    elif tipo == b'PONG':
                        pass
                except socket.timeout:
                    continue
                except:
                    if self.conectado:
                        self.desconectar()
                    time.sleep(0.5)
            else:
                time.sleep(0.5)
    
    def recibir_archivo(self):
        try:
            meta_len_bytes = self.recibir_exacto(4)
            if not meta_len_bytes or len(meta_len_bytes) != 4:
                return
            nombre_len = int(meta_len_bytes.decode('utf-8'))
            
            nombre_archivo = self.recibir_exacto(nombre_len).decode('utf-8')
            
            meta_size_bytes = self.recibir_exacto(10)
            tamano_archivo = int(meta_size_bytes.decode('utf-8'))
            
            if tamano_archivo > self.TAMANO_MAXIMO:
                self.consumir_bytes(tamano_archivo)
                return
            
            bytes_recibidos = self.recibir_exacto(tamano_archivo)
            if len(bytes_recibidos) != tamano_archivo:
                return
            
            nombre_limpio = self.sanitizar(nombre_archivo)
            ruta = os.path.join(self.directorio_descargas, f"recibido_{nombre_limpio}")
            
            with open(ruta, 'wb') as f:
                f.write(bytes_recibidos)
                f.flush()
                os.fsync(f.fileno())
            
            self.archivos_recibidos += 1
            self.log(f"✓ [RECIBIDO] {nombre_archivo} ({self.formatear_tamano(tamano_archivo)})", 'success')
            self.root.after(0, self.actualizar_contador_archivos)
            self.root.after(0, lambda n=nombre_archivo: self.mostrar_notificacion(n))
        except Exception as e:
            self.log(f"[!] Error recibir: {e}", 'error')
    
    def recibir_exacto(self, tamano):
        datos = b""
        while len(datos) < tamano:
            chunk = self.socket.recv(min(4096, tamano - len(datos)))
            if not chunk:
                raise ConnectionResetError("Cerrada")
            datos += chunk
        return datos
    
    def consumir_bytes(self, tamano):
        restantes = tamano
        while restantes > 0:
            chunk = self.socket.recv(min(4096, restantes))
            if not chunk:
                break
            restantes -= len(chunk)
    
    def desconectar(self):
        self.conectado = False
        try:
            if self.socket:
                self.socket.close()
        except:
            pass
        
        self.root.after(0, lambda: self.btn_enviar.config(state=tk.DISABLED))
        self.root.after(0, lambda: self.conn_status_label.config(
            text="🔴 Desconectado del servidor",
            fg='#f38ba8'))
        
        self.log("⚠️ Conexión perdida", 'warning')
        
        if self.debe_reconectar and not self.reconectando:
            threading.Thread(target=self.ciclo_reconexion, daemon=True).start()
    
    # ==================== ENVÍO ====================
    def enviar_archivo_dialogo(self):
        if not self.conectado:
            messagebox.showwarning("⚠️", "No está conectado al servidor")
            return
        
        ruta = filedialog.askopenfilename(
            title=f"Seleccionar archivo (máx. {self.config_tamano_maximo} MB)",
            filetypes=[
                ("Archivos", "*.pdf *.doc *.docx *.txt *.xls *.xlsx *.csv *.png *.jpg *.jpeg *.gif *.zip *.rar"),
                ("Todos", "*.*")])
        if not ruta:
            return
        
        if not os.path.isfile(ruta):
            return
        
        tamano = os.path.getsize(ruta)
        if tamano > self.TAMANO_MAXIMO:
            messagebox.showerror(
                "❌ Archivo Demasiado Grande",
                f"📄 {os.path.basename(ruta)}\n"
                f"📊 {self.formatear_tamano(tamano)}\n"
                f"⚠️ Máximo: {self.formatear_tamano(self.TAMANO_MAXIMO)}")
            self.log(f"[!] Rechazado: {os.path.basename(ruta)} ({self.formatear_tamano(tamano)})", 'error')
            return
        
        threading.Thread(target=self.tarea_enviar, args=(ruta,), daemon=True).start()
    
    def tarea_enviar(self, ruta):
        try:
            nombre = os.path.basename(ruta)
            tamano = os.path.getsize(ruta)
            
            self.root.after(0, lambda: self.progress_label.config(text=f"Enviando: {nombre}"))
            self.root.after(0, lambda: self.progress_var.set(0))
            self.root.after(0, lambda: self.btn_enviar.config(state=tk.DISABLED))
            
            with open(ruta, 'rb') as f:
                contenido = f.read()
            
            meta_len = str(len(nombre)).zfill(4).encode('utf-8')
            nombre_bytes = nombre.encode('utf-8')
            meta_size = str(tamano).zfill(10).encode('utf-8')
            
            paquete = b'F' + meta_len + nombre_bytes + meta_size + contenido
            self.socket.sendall(paquete)
            
            self.log(f"✓ Enviado: {nombre} ({self.formatear_tamano(tamano)})", 'success')
            
            self.root.after(0, lambda: self.progress_var.set(100))
            self.root.after(0, lambda: self.progress_label.config(text=f"✅ {nombre}"))
        except Exception as e:
            self.log(f"[!] Error enviar: {e}", 'error')
            messagebox.showerror("❌", f"Error: {e}")
        finally:
            self.root.after(0, lambda: self.btn_enviar.config(state=tk.NORMAL))
    
    def mostrar_notificacion(self, nombre):
        messagebox.showinfo(
            "🎉 Nuevo Archivo Recibido",
            f"{self.nombre_cliente}, recibiste:\n\n📄 {nombre}\n📁 En: archivos_recibidos/")
    
    def actualizar_contador_archivos(self):
        self.archivos_label.config(text=f"📥 Recibidos: {self.archivos_recibidos}")
    
    # ==================== UTILIDADES ====================
    def sanitizar(self, nombre):
        for c in ['/', '\\', ':', '*', '?', '"', '<', '>', '|']:
            nombre = nombre.replace(c, '_')
        return nombre[:200]
    
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