"""
SERVIDOR CON WATCHDOG INTEGRADO
================================

Un solo archivo que contiene:
  1. WATCHDOG: relanza el servidor si se cierra (X, kill, crash)
  2. SERVIDOR: GUI Tkinter con failover automático

USO:
    py servidor.py           → Servidor primario (con watchdog)
    py servidor.py backup    → Servidor backup (con watchdog)

CÓMO DETENER:
    Ctrl+C en la terminal del servidor → detiene el watchdog
    Cerrar la ventana con X → el watchdog relanza el servidor
"""

import socket
import threading
import tkinter as tk
from tkinter import scrolledtext
from datetime import datetime
import configparser
import os
import time
import sys
import subprocess
import signal


# ==================== CONFIGURACIÓN ====================
TIEMPO_RELANZAMIENTO = 10  # segundos


# ==================== MODO WATCHDOG ====================
def modo_watchdog(es_backup):
    """Lanza y vigila el servidor. Lo relanza cada vez que se cierra."""
    rol = "BACKUP" if es_backup else "PRIMARIO"
    directorio = os.path.dirname(os.path.abspath(__file__))
    script = os.path.abspath(__file__)
    
    # Comando que lanza el servidor (con --interno para no recursión)
    comando = [sys.executable, script, "--interno"]
    if es_backup:
        comando.append("backup")
    
    relanzamientos = 0
    proceso_actual = [None]
    detener = [False]
    
    def manejar_salida(sig=None, frame=None):
        detener[0] = True
        print()
        print("=" * 65)
        print(f"  🛑 WATCHDOG {rol} DETENIDO POR EL USUARIO")
        print(f"  El servidor ya no se relanzará automáticamente.")
        print("=" * 65)
        if proceso_actual[0] and proceso_actual[0].poll() is None:
            try:
                proceso_actual[0].terminate()
                proceso_actual[0].wait(timeout=3)
            except:
                try:
                    proceso_actual[0].kill()
                except:
                    pass
        sys.exit(0)
    
    signal.signal(signal.SIGINT, manejar_salida)
    
    # ===== BUCLE INFINITO =====
    while not detener[0]:
        try:
            # Limpiar pantalla
            os.system('cls' if os.name == 'nt' else 'clear')
            
            print()
            print("=" * 65)
            if relanzamientos == 0:
                print(f"  🐕 WATCHDOG {rol} INICIADO")
                print(f"  Vigilando el Servidor {rol}...")
            else:
                print(f"  🐕 WATCHDOG {rol} - RELANZAMIENTO #{relanzamientos}")
            print("=" * 65)
            print()
            print(f"  📁 Directorio:       {directorio}")
            print(f"  🚀 Servidor:         servidor.py {'backup' if es_backup else '(primario)'}")
            print(f"  ⏱️  Tiempo relanzamiento: {TIEMPO_RELANZAMIENTO}s")
            print(f"  🔢 Relanzamientos:   {relanzamientos}")
            print()
            print(f"  → Levantando servidor {rol}... ({time.strftime('%H:%M:%S')})")
            
            # Lanzar el servidor como subproceso
            proceso_actual[0] = subprocess.Popen(
                comando,
                cwd=directorio
            )
            
            print(f"  ✓ Servidor {rol} iniciado con PID {proceso_actual[0].pid}")
            print(f"  👁️  Watchdog vigilando...")
            print(f"  💡 Cierra la ventana del servidor para probar el relanzamiento")
            print(f"  💡 Presiona Ctrl+C aquí para detener el watchdog")
            print()
            print("-" * 65)
            
            # Esperar a que el servidor termine
            proceso_actual[0].wait()
            
            if detener[0]:
                break
            
            # El servidor terminó → RELANZAR SIEMPRE
            relanzamientos += 1
            print()
            print("=" * 65)
            print(f"  ⚠️  ALERTA: El servidor {rol} se ha cerrado")
            print(f"  🔄 Protocolo de recuperación activado")
            print(f"  ⏳ Relanzando en {TIEMPO_RELANZAMIENTO} segundos...")
            print("=" * 65)
            
            for i in range(TIEMPO_RELANZAMIENTO, 0, -1):
                if detener[0]:
                    break
                print(f"  ⏳ {i}...")
                time.sleep(1)
            
            if detener[0]:
                break
            
            print()
            print(f"  🔄 Relanzando servidor {rol}...")
            time.sleep(1)
            
        except KeyboardInterrupt:
            manejar_salida()
        except Exception as e:
            print(f"\n[!] ERROR en watchdog: {e}")
            print(f"[!] Reintentando en {TIEMPO_RELANZAMIENTO} segundos...")
            time.sleep(TIEMPO_RELANZAMIENTO)
    
    print()
    print("=" * 65)
    print(f"  🐕 WATCHDOG {rol} FINALIZADO")
    print(f"  Total de relanzamientos: {relanzamientos}")
    print("=" * 65)


# ==================== MODO SERVIDOR (GUI) ====================
class ServidorGUI:
    def __init__(self, rol_inicial='primario'):
        self.rol = rol_inicial
        self.cargar_configuracion()
        
        self.clientes = {}
        self.contador_clientes = 0
        self.archivos_transferidos = 0
        self.TAMANO_MAXIMO = self.config_tamano_maximo * 1024 * 1024
        
        self.servidor_activo = True
        self.tomando_control = False
        self.cediendo_control = False
        self.ultimo_heartbeat = time.time()
        self.es_activo = False
        self.monitor_activo = True
        
        # ===== VENTANA =====
        self.root = tk.Tk()
        self.root.geometry("850x700")
        self.root.configure(bg='#1e1e2e')
        self.root.protocol("WM_DELETE_WINDOW", self.cerrar_servidor)
        
        self.root.grid_rowconfigure(1, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        
        # Título
        title_frame = tk.Frame(self.root, bg='#1e1e2e')
        title_frame.grid(row=0, column=0, sticky='ew', padx=10, pady=(10, 5))
        
        self.titulo_label = tk.Label(
            title_frame, text=f"🖥️ SERVIDOR {self.rol.upper()}",
            font=('Arial', 16, 'bold'), bg='#1e1e2e', fg='#89b4fa'
        )
        self.titulo_label.pack()
        
        self.subtitulo_label = tk.Label(
            title_frame,
            text=f"Puerto activo: {self.config_puerto} | Backup: {self.config_puerto_backup}",
            font=('Arial', 9), bg='#1e1e2e', fg='#6c7086'
        )
        self.subtitulo_label.pack()
        
        # Log
        log_frame = tk.Frame(self.root, bg='#313244')
        log_frame.grid(row=1, column=0, sticky='nsew', padx=10, pady=5)
        log_frame.grid_rowconfigure(1, weight=1)
        log_frame.grid_columnconfigure(0, weight=1)
        
        tk.Label(
            log_frame, text="📋 Bitácora del Servidor",
            font=('Arial', 11, 'bold'), bg='#313244', fg='#cdd6f4', pady=5
        ).grid(row=0, column=0, sticky='ew')
        
        self.log_text = scrolledtext.ScrolledText(
            log_frame, bg='#1e1e2e', fg='#a6e3a1',
            font=('Consolas', 9), wrap=tk.WORD, padx=10, pady=10
        )
        self.log_text.grid(row=1, column=0, sticky='nsew')
        
        self.log_text.tag_config('info', foreground='#89b4fa')
        self.log_text.tag_config('success', foreground='#a6e3a1')
        self.log_text.tag_config('warning', foreground='#f9e2af')
        self.log_text.tag_config('error', foreground='#f38ba8')
        self.log_text.tag_config('transfer', foreground='#cba6f7')
        self.log_text.tag_config('reconnect', foreground='#fab387')
        self.log_text.tag_config('heartbeat', foreground='#94e2d5')
        self.log_text.tag_config('role', foreground='#cba6f7')
        
        # Estadísticas
        stats_frame = tk.Frame(self.root, bg='#1e1e2e')
        stats_frame.grid(row=2, column=0, sticky='ew', padx=10, pady=(5, 10))
        
        self.estado_label = tk.Label(
            stats_frame, text="🔴 INICIANDO...",
            font=('Arial', 11, 'bold'), bg='#1e1e2e', fg='#f38ba8'
        )
        self.estado_label.pack(side='left', padx=5)
        
        self.clientes_label = tk.Label(
            stats_frame, text="👥 Clientes: 0",
            font=('Arial', 10, 'bold'), bg='#1e1e2e', fg='#f9e2af'
        )
        self.clientes_label.pack(side='left', padx=15)
        
        self.archivos_label = tk.Label(
            stats_frame, text="📁 Archivos: 0",
            font=('Arial', 10, 'bold'), bg='#1e1e2e', fg='#f9e2af'
        )
        self.archivos_label.pack(side='left', padx=15)
        
        self.hb_label = tk.Label(
            stats_frame, text="💓 --",
            font=('Arial', 10, 'bold'), bg='#1e1e2e', fg='#94e2d5'
        )
        self.hb_label.pack(side='left', padx=15)
        
        self.server_socket = None
        
        # Arrancar
        self.root.after(100, self.arrancar)
        
        self.root.mainloop()
    
    def cargar_configuracion(self):
        config = configparser.ConfigParser()
        self.config_host = '127.0.0.1'
        self.config_puerto = 5000
        self.config_puerto_backup = 5001
        self.config_tamano_maximo = 2
        self.config_intervalo_heartbeat = 2
        self.config_timeout_heartbeat = 5
        self.config_tiempo_cesion = 3
        
        try:
            if os.path.exists('config.ini'):
                config.read('config.ini')
                if 'SERVIDOR' in config:
                    self.config_puerto = int(config['SERVIDOR'].get('puerto_primario', 5000))
                    self.config_puerto_backup = int(config['SERVIDOR'].get('puerto_backup', 5001))
                    self.config_intervalo_heartbeat = int(config['SERVIDOR'].get('intervalo_heartbeat', 2))
                    self.config_timeout_heartbeat = int(config['SERVIDOR'].get('timeout_heartbeat', 5))
                    self.config_tiempo_cesion = int(config['SERVIDOR'].get('tiempo_cesion', 3))
                if 'CLIENTE' in config:
                    self.config_host = config['CLIENTE'].get('host', '127.0.0.1')
                    self.config_tamano_maximo = int(config['CLIENTE'].get('tamano_maximo_mb', 2))
        except Exception as e:
            print(f"Error config: {e}")
    
    # ==================== ARRANQUE ====================
    def arrancar(self):
        self.log("=" * 55, 'success')
        self.log(f"  🚀 INICIANDO SERVIDOR (rol deseado: {self.rol.upper()})", 'success')
        self.log("=" * 55, 'success')
        
        if self.puede_tomar_puerto():
            self.log(f"✓ Puerto {self.config_puerto} disponible - Tomando control", 'success')
            self.convertirse_en_activo()
        else:
            self.log(f"⚠️ Puerto {self.config_puerto} ocupado - Actuando como BACKUP", 'warning')
            self.convertirse_en_backup()
    
    def puede_tomar_puerto(self):
        try:
            test = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            test.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            test.settimeout(1)
            test.bind((self.config_host, self.config_puerto))
            test.close()
            return True
        except:
            return False
    
    def convertirse_en_activo(self):
        try:
            if self.server_socket:
                try:
                    self.server_socket.close()
                except:
                    pass
            
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.config_host, self.config_puerto))
            self.server_socket.listen(10)
            
            self.es_activo = True
            self.servidor_activo = True
            
            self.root.after(0, lambda: self.titulo_label.config(
                text=f"🖥️ SERVIDOR {self.rol.upper()} (ACTIVO)", fg='#a6e3a1'))
            self.root.after(0, lambda: self.estado_label.config(
                text="🟢 ACTIVO", fg='#a6e3a1'))
            
            self.log(f"✓ Ahora escuchando en {self.config_host}:{self.config_puerto}", 'success')
            self.log(f"Esperando clientes...\n", 'info')
            
            threading.Thread(target=self.aceptar_clientes, daemon=True).start()
            threading.Thread(target=self.enviar_heartbeats, daemon=True).start()
            threading.Thread(target=self.monitorear_backup, daemon=True).start()
            
        except Exception as e:
            self.log(f"[!] Error activo: {e}", 'error')
    
    def convertirse_en_backup(self):
        self.es_activo = False
        
        self.root.after(0, lambda: self.titulo_label.config(
            text=f"🖥️ SERVIDOR {self.rol.upper()} (BACKUP)", fg='#fab387'))
        self.root.after(0, lambda: self.estado_label.config(
            text="💤 EN ESPERA", fg='#fab387'))
        
        self.log(f"💤 Actuando como BACKUP", 'role')
        self.log(f"Monitoreando puerto {self.config_puerto_backup}...\n", 'info')
        
        threading.Thread(target=self.monitorear_primario, daemon=True).start()
        
        if self.rol == 'primario':
            self.log(f"📨 Rol primario detectado - Solicitando control al backup", 'role')
            threading.Thread(target=self.solicitar_control, daemon=True).start()
    
    # ==================== SERVIDOR ACTIVO ====================
    def aceptar_clientes(self):
        while self.servidor_activo and self.es_activo:
            try:
                if self.server_socket is None:
                    break
                self.server_socket.settimeout(1.0)
                try:
                    client_socket, addr = self.server_socket.accept()
                except socket.timeout:
                    continue
                except OSError:
                    break
                
                self.contador_clientes += 1
                nombre_cliente = f"Cliente {self.contador_clientes}"
                
                self.clientes[client_socket] = {
                    "nombre": nombre_cliente,
                    "addr": addr,
                    "ultimo_ping": time.time()
                }
                
                try:
                    nombre_bytes = nombre_cliente.encode('utf-8')
                    client_socket.send(len(nombre_bytes).to_bytes(2, byteorder='big'))
                    client_socket.send(nombre_bytes)
                except:
                    pass
                
                self.log(f"[+] {nombre_cliente} conectado desde {addr[0]}:{addr[1]}", 'success')
                self.actualizar_stats()
                
                threading.Thread(
                    target=self.manejar_cliente,
                    args=(client_socket, addr, nombre_cliente),
                    daemon=True
                ).start()
            except Exception as e:
                if self.servidor_activo and self.es_activo:
                    self.log(f"[!] Error aceptar: {e}", 'error')
                    break
    
    def manejar_cliente(self, conn, addr, nombre_cliente):
        try:
            while self.servidor_activo and self.es_activo:
                tipo = conn.recv(1)
                if not tipo:
                    break
                
                if conn in self.clientes:
                    self.clientes[conn]["ultimo_ping"] = time.time()
                
                if tipo == b'P':
                    try:
                        conn.sendall(b'PONG')
                    except:
                        break
                
                elif tipo == b'F':
                    meta_len_bytes = self.recibir_exacto(conn, 4)
                    if not meta_len_bytes:
                        break
                    nombre_len = int(meta_len_bytes.decode('utf-8'))
                    nombre_archivo = self.recibir_exacto(conn, nombre_len).decode('utf-8')
                    
                    meta_size_bytes = self.recibir_exacto(conn, 10)
                    tamano_archivo = int(meta_size_bytes.decode('utf-8'))
                    
                    if tamano_archivo > self.TAMANO_MAXIMO:
                        self.log(f"⚠️ {nombre_cliente}: excede límite", 'error')
                        self.consumir_bytes(conn, tamano_archivo)
                        continue
                    
                    bytes_recibidos = self.recibir_exacto(conn, tamano_archivo)
                    if len(bytes_recibidos) != tamano_archivo:
                        break
                    
                    self.log(f"📥 {nombre_cliente} → '{nombre_archivo}' ({self.formatear_tamano(tamano_archivo)})", 'transfer')
                    self.archivos_transferidos += 1
                    self.actualizar_stats()
                    
                    paquete = b'F' + meta_len_bytes + nombre_archivo.encode('utf-8') + meta_size_bytes + bytes_recibidos
                    receptores = self.retransmitir(paquete, remitente=conn)
                    
                    if receptores:
                        self.log(f"   ↳ Retransmitido a: {', '.join(receptores)}", 'success')
        except Exception:
            pass
        finally:
            if conn in self.clientes:
                del self.clientes[conn]
            try:
                conn.close()
            except:
                pass
            self.log(f"[-] {nombre_cliente} desconectado", 'warning')
            self.actualizar_stats()
    
    # ==================== HEARTBEATS ====================
    def enviar_heartbeats(self):
        while self.servidor_activo and self.es_activo:
            try:
                hb = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                hb.settimeout(2)
                hb.connect((self.config_host, self.config_puerto_backup))
                hb.sendall(f"HEARTBEAT|{time.time()}".encode('utf-8'))
                hb.close()
                ahora = datetime.now().strftime('%H:%M:%S')
                self.root.after(0, lambda: self.hb_label.config(
                    text=f"💓 {ahora}", fg='#94e2d5'))
            except:
                self.root.after(0, lambda: self.hb_label.config(
                    text="💓 Sin backup", fg='#6c7086'))
            time.sleep(self.config_intervalo_heartbeat)
    
    def monitorear_backup(self):
        try:
            monitor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            monitor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            monitor.bind((self.config_host, self.config_puerto_backup))
            monitor.listen(5)
            monitor.settimeout(1.0)
            
            self.log(f"👂 Escuchando puerto backup {self.config_puerto_backup}", 'info')
            
            while self.servidor_activo and self.es_activo:
                try:
                    conn, addr = monitor.accept()
                    conn.settimeout(2)
                    try:
                        data = conn.recv(1024).decode('utf-8')
                        if data == "SOLICITAR_CONTROL":
                            self.log("📨 Solicitud de control recibida", 'warning')
                            threading.Thread(target=self.ceder_control, daemon=True).start()
                            break
                    except:
                        pass
                    conn.close()
                except socket.timeout:
                    continue
                except OSError:
                    break
        except Exception:
            pass
        finally:
            try:
                monitor.close()
            except:
                pass
    
    def ceder_control(self):
        if self.cediendo_control:
            return
        
        self.cediendo_control = True
        self.log("=" * 55, 'warning')
        self.log("  🔄 CEDIENDO EL CONTROL AL PRIMARIO", 'warning')
        self.log("=" * 55, 'warning')
        
        for c in list(self.clientes.keys()):
            try:
                c.close()
            except:
                pass
        self.clientes.clear()
        self.actualizar_stats()
        
        self.es_activo = False
        try:
            if self.server_socket:
                self.server_socket.close()
                self.server_socket = None
        except:
            pass
        
        time.sleep(self.config_tiempo_cesion)
        
        self.cediendo_control = False
        self.log("✓ Control cedido. Ahora soy BACKUP", 'role')
        self.convertirse_en_backup()
    
    # ==================== SOLICITAR CONTROL ====================
    def solicitar_control(self):
        time.sleep(2)
        
        intentos = 0
        while intentos < 5 and self.servidor_activo:
            intentos += 1
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(3)
                s.connect((self.config_host, self.config_puerto_backup))
                s.sendall(b"SOLICITAR_CONTROL")
                s.close()
                self.log(f"📨 Solicitud de control enviada (intento {intentos}/5)", 'role')
                
                for _ in range(20):
                    time.sleep(1)
                    if self.puede_tomar_puerto():
                        self.log("✓ Puerto liberado por el backup", 'success')
                        self.convertirse_en_activo()
                        return
            except Exception as e:
                self.log(f"[!] Error solicitar control: {e}", 'error')
                time.sleep(2)
        
        self.log("⚠️ No se pudo obtener el control. Siguiendo como backup.", 'warning')
    
    # ==================== MONITOREO (BACKUP) ====================
    def monitorear_primario(self):
        try:
            monitor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            monitor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            monitor.bind((self.config_host, self.config_puerto_backup))
            monitor.listen(5)
            monitor.settimeout(1.0)
            
            self.log(f"👂 Backup escuchando en {self.config_host}:{self.config_puerto_backup}", 'info')
            self.ultimo_heartbeat = time.time()
            
            while self.monitor_activo and not self.es_activo:
                try:
                    conn, addr = monitor.accept()
                    conn.settimeout(2)
                    try:
                        data = conn.recv(1024).decode('utf-8')
                        if data.startswith("HEARTBEAT"):
                            self.ultimo_heartbeat = time.time()
                            ahora = datetime.now().strftime('%H:%M:%S')
                            self.root.after(0, lambda: self.hb_label.config(
                                text=f"💓 {ahora}", fg='#94e2d5'))
                    except:
                        pass
                    conn.close()
                except socket.timeout:
                    if self.es_activo:
                        break
                    
                    sin_latido = time.time() - self.ultimo_heartbeat
                    if sin_latido > self.config_timeout_heartbeat and not self.tomando_control:
                        self.log(f"⚠️ Activo sin responder por {sin_latido:.1f}s", 'warning')
                        self.log(f"🚨 ¡TOMA DE CONTROL!", 'error')
                        threading.Thread(target=self.tomar_control, daemon=True).start()
                except OSError:
                    break
        except Exception as e:
            self.log(f"[!] Error monitoreo: {e}", 'error')
        finally:
            try:
                monitor.close()
            except:
                pass
    
    def tomar_control(self):
        if self.tomando_control:
            return
        
        self.tomando_control = True
        
        self.log("=" * 55, 'reconnect')
        self.log("  🔴 TOMANDO EL CONTROL", 'reconnect')
        self.log("=" * 55, 'reconnect')
        
        intentos = 0
        while intentos < 15 and not self.es_activo:
            intentos += 1
            time.sleep(2)
            
            if self.puede_tomar_puerto():
                self.log(f"✓ Puerto {self.config_puerto} disponible", 'success')
                break
            else:
                self.log(f"⏳ Puerto ocupado (intento {intentos}/15)", 'warning')
        
        self.monitor_activo = False
        time.sleep(0.5)
        self.monitor_activo = True
        
        self.tomando_control = False
        self.convertirse_en_activo()
        self.log("✓ Ahora soy el servidor ACTIVO", 'success')
    
    # ==================== UTILIDADES ====================
    def recibir_exacto(self, conn, tamano):
        datos = b""
        while len(datos) < tamano:
            try:
                chunk = conn.recv(min(4096, tamano - len(datos)))
                if not chunk:
                    return datos
                datos += chunk
            except:
                return datos
        return datos
    
    def consumir_bytes(self, conn, tamano):
        restantes = tamano
        while restantes > 0:
            try:
                chunk = conn.recv(min(4096, restantes))
                if not chunk:
                    break
                restantes -= len(chunk)
            except:
                break
    
    def retransmitir(self, paquete, remitente):
        receptores = []
        a_eliminar = []
        for cliente, info in list(self.clientes.items()):
            if cliente != remitente:
                try:
                    cliente.sendall(paquete)
                    receptores.append(info['nombre'])
                except:
                    a_eliminar.append(cliente)
        for c in a_eliminar:
            if c in self.clientes:
                del self.clientes[c]
        return receptores
    
    def log(self, mensaje, tag='info'):
        timestamp = datetime.now().strftime('%H:%M:%S')
        try:
            self.root.after(0, lambda: self.log_text.insert(
                tk.END, f"[{timestamp}] {mensaje}\n", tag))
            self.root.after(0, lambda: self.log_text.see(tk.END))
        except:
            pass
    
    def actualizar_stats(self):
        try:
            self.root.after(0, lambda: self.clientes_label.config(
                text=f"👥 Clientes: {len(self.clientes)}"))
            self.root.after(0, lambda: self.archivos_label.config(
                text=f"📁 Archivos: {self.archivos_transferidos}"))
        except:
            pass
    
    def formatear_tamano(self, tamano):
        if tamano < 1024:
            return f"{tamano} B"
        elif tamano < 1024 * 1024:
            return f"{tamano/1024:.2f} KB"
        elif tamano < 1024 * 1024 * 1024:
            return f"{tamano/(1024*1024):.2f} MB"
        return f"{tamano/(1024*1024*1024):.2f} GB"
    
    def cerrar_servidor(self):
        """Cierre con la X - el watchdog relanzará el servidor"""
        self.servidor_activo = False
        self.monitor_activo = False
        self.es_activo = False
        
        try:
            if self.server_socket:
                self.server_socket.close()
        except:
            pass
        for c in list(self.clientes.keys()):
            try:
                c.close()
            except:
                pass
        self.root.destroy()


# ==================== PUNTO DE ENTRADA ====================
if __name__ == "__main__":
    args = sys.argv[1:]
    
    # Modo interno (hijo del watchdog)
    if "--interno" in args:
        args.remove("--interno")
        es_backup = "backup" in [a.lower() for a in args]
        ServidorGUI(rol_inicial='backup' if es_backup else 'primario')
    else:
        # Modo watchdog (padre)
        es_backup = len(args) > 0 and args[0].lower() == 'backup'
        modo_watchdog(es_backup)