""""
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
import re


# ==================== CONFIGURACIÓN ====================
TIEMPO_RELANZAMIENTO = 10  # Tiempo que espera el watchdog antes de relanzar el servidor.

# ==================== MODO WATCHDOG ====================


def modo_watchdog(es_backup):
    """Lanza y vigila el servidor. Lo relanza cada vez que se cierra."""
    rol = "BACKUP" if es_backup else "PRIMARIO"
    directorio = os.path.dirname(os.path.abspath(__file__)) #Guarda la direccion y archivo donde este guardado el programa
    script = os.path.abspath(__file__)

    # Comando que lanza el servidor de forma intena, pero no utiliza recursion
    comando = [sys.executable, script, "--interno"]
    if es_backup:
        comando.append("backup")    #Abre el backup

    #Iniciliaza las variables
    relanzamientos = 0
    proceso_actual = [None]
    detener = [False]


    def manejar_salida(sig=None, frame=None):
        #Dadoo caso que se detenga = true aparece los siguientes comentarios
        detener[0] = True
        print()
        print("=" * 65)
        print(f"  WATCHDOG {rol} DETENIDO POR EL USUARIO")
        print(f"  El servidor ya no se relanzará automáticamente.")
        print("=" * 65)
        #valida si hy proceso corriendo en caso que si lo cierra
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
    # Si hay un proceso corriendo
    while not detener[0]:
        try:
            # Limpiar pantalla
            os.system('cls' if os.name == 'nt' else 'clear')

            print()
            print("=" * 65)
            #Inicia prier relazamiento del guardian y si != 0 levanta el relazamiento y imprimo direccion de carpteas servidor etc
            if relanzamientos == 0:
                print(f"  WATCHDOG {rol} INICIADO")
                print(f"  Vigilando el Servidor {rol}...")
            else:
                print(f"  WATCHDOG {rol} - RELANZAMIENTO #{relanzamientos}")
            print("=" * 65)
            print()
            print(f"  Directorio:       {directorio}")
            print(f"  Servidor:         servidor.py {'backup' if es_backup else '(primario)'}")
            print(f"  Tiempo relanzamiento: {TIEMPO_RELANZAMIENTO}s")
            print(f"  Relanzamientos:   {relanzamientos}")
            print()
            print(f"  Levantando servidor {rol}... ({time.strftime('%H:%M:%S')})")

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


            #Si se cierra el servidor que este en 0 o en -1, se imprime la cantidad de segundos para levnatar el relazamiento
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

        #Manejo de erores
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


# ==================== MODO SERVIDOR (GUI FRONTED) ====================
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
    #Funcion que carga la cnfiguracionde achivo y caso que no lo encuentre ejecuta lo que esta predeterminado
    def cargar_configuracion(self):
        config = configparser.ConfigParser()
        self.config_host = '127.0.0.1'
        self.config_puerto = 5000
        self.config_puerto_backup = 5001
        self.config_tamano_maximo = 2
        self.config_intervalo_heartbeat = 2
        self.config_timeout_heartbeat = 5
        self.config_tiempo_cesion = 3

        #Conexion del servidor para el servidor primario y el backup junto con el loclhost
        try:
            if os.path.exists('config.ini'):
                config.read('config.ini')
                if 'SERVIDOR' in config:
                    self.config_puerto = int(config['SERVIDOR'].get('puerto_primario', 5000))
                    ...
                if 'CLIENTE' in config:
                    self.config_host = config['CLIENTE'].get('host', '127.0.0.1')
                    self.config_tamano_maximo = int(config['CLIENTE'].get('tamano_maximo_mb', 2))
        except Exception as e:
            print(f"Error config: {e}")

        # ===== MODO POOL =====
        puerto_env = os.environ.get('SERVIDOR_PUERTO')
        if puerto_env:
            self.config_puerto = int(puerto_env)
            self.config_puerto_backup = self.config_puerto + 1000
            print(f"[SERVIDOR] Modo POOL: escuchando en {self.config_puerto}")

        self.config_relay_host = os.environ.get('SERVIDOR_RELAY_HOST', '127.0.0.1')
        self.config_relay_puerto = int(os.environ.get('SERVIDOR_RELAY_PUERTO', 6001))

    # ==================== ARRANQUE ====================
    #Al arracnar el servidor muestra la pantall de inicio
    def arrancar(self):
        self.log("=" * 55, 'success')
        self.log(f"  INICIANDO SERVIDOR (rol deseado: {self.rol.upper()})", 'success')
        self.log("=" * 55, 'success')

        #Arranca desde el puerto como activo en el puerto asignado
        if '--pool' in sys.argv:
            self.log(f"🔷 Modo POOL activado (puerto {self.config_puerto})", 'info')
            self.convertirse_en_activo()
            return
        #Si peude tomar el puerto lo abre desde ahi en caso que no use el backup
        if self.puede_tomar_puerto():
            self.log(f"Puerto {self.config_puerto} disponible - Tomando control", 'success')
            self.convertirse_en_activo()
        else:
            self.log(f"Puerto {self.config_puerto} ocupado - Actuando como BACKUP", 'warning')
            self.convertirse_en_backup()

    # Conexion con el scket server ara permitir cnexion de los clientes.
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
        #Valida si hay socket abierto e caso que si lo cierra
        try:
            if self.server_socket:
                try:
                    self.server_socket.close()
                except:
                    pass
            #Crea y configura el nuevo canal Socket
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.config_host, self.config_puerto))
            self.server_socket.listen(10)

            #Reconfigura e nuev scket creado
            self.es_activo = True
            self.servidor_activo = True
            #Muestra en pantalla la activacaion del servidor
            self.root.after(0, lambda: self.titulo_label.config(
                text=f"SERVIDOR {self.rol.upper()} (ACTIVO)", fg='#a6e3a1'))
            self.root.after(0, lambda: self.estado_label.config(
                text="🟢 ACTIVO", fg='#a6e3a1'))

            self.log(f"✓ Ahora escuchando en {self.config_host}:{self.config_puerto}", 'success')
            self.log(f"Esperando clientes...\n", 'info')

            #Ejecura 3 hilos al mismo tiempo aceptar_clientes, envia ping para valdiar si esta vivo, Monitoria el servidor backup
            threading.Thread(target=self.aceptar_clientes, daemon=True).start()

            # ===== MODO POOL: no participa del failover primario/backup =====
            if '--pool' not in sys.argv:
                threading.Thread(target=self.enviar_heartbeats, daemon=True).start()
                threading.Thread(target=self.monitorear_backup, daemon=True).start()

        except Exception as e:
            self.log(f"[!] Error activo: {e}", 'error')


    def convertirse_en_backup(self):
        # Inicliaza variables iniciales
        self.es_activo = False
        # Muestra en log la ejcuucon del backup
        self.root.after(0, lambda: self.titulo_label.config(
            text=f"SERVIDOR {self.rol.upper()} (BACKUP)", fg='#fab387'))
        self.root.after(0, lambda: self.estado_label.config(
            text="EN ESPERA", fg='#fab387'))

        self.log(f"Actuando como BACKUP", 'role')
        self.log(f"Monitoreando puerto {self.config_puerto_backup}...\n", 'info')

        #Ejecuta el hlo para monitorear el servidor primario
        threading.Thread(target=self.monitorear_primario, daemon=True).start()

        #Si server es primario (vuelve a la vida) se eejcutara un hilo para solcitar control como servidor principal.
        if self.rol == 'primario':
            self.log(f"Rol primario detectado - Solicitando control al backup", 'role')
            threading.Thread(target=self.solicitar_control, daemon=True).start()

    def aceptar_clientes(self):
        # CAMBIO: se guarda una referencia local al socket que este hilo debe vigilar.
        # Esto evita que un hilo viejo intente usar un socket que ya fue cerrado/reemplazado
        # cuando el servidor cambia de estado o vuelve a tomar el control.
        socket_escucha = self.server_socket

        if socket_escucha is None:
            return

        try:
            socket_escucha.settimeout(1.0)
        except OSError:
            return

        while self.servidor_activo and self.es_activo:
            try:
                # CAMBIO: si este hilo ya no corresponde al socket actual, termina
                # silenciosamente para no intentar aceptar sobre un socket cerrado.
                if self.server_socket is not socket_escucha:
                    break

                try:
                    client_socket, addr = socket_escucha.accept()
                except socket.timeout:
                    continue
                except OSError:
                    break

                # ===== LEER EL PRIMER BYTE PARA IDENTIFICAR EL TIPO =====
                client_socket.settimeout(1.0)
                try:
                    primer_byte = client_socket.recv(1)
                except:
                    primer_byte = b''
                client_socket.settimeout(None)

                # ===== CASO 1: HEALTH CHECK DEL BALANCEADOR (H) =====
                if primer_byte == b'H':
                    try:
                        client_socket.close()
                    except:
                        pass
                    continue

                # ===== CASO 2: QUERY DEL BALANCEADOR (Q) =====
                # Responde con la cantidad REAL de clientes (4 bytes big-endian).
                if primer_byte == b'Q':
                    try:
                        cantidad = len(self.clientes)
                        client_socket.sendall(cantidad.to_bytes(4, byteorder='big'))
                    except:
                        pass
                    try:
                        client_socket.close()
                    except:
                        pass
                    continue

                # ===== CASO 3: RELAY DESDE EL BALANCEADOR (R) =====
                # El balanceador reenvía aquí paquetes que otros servidores
                # quieren distribuir a clientes de ESTE servidor.
                if primer_byte == b'R':
                    try:
                        self._procesar_relay(client_socket)
                    except Exception as e:
                        self.log(f"[!] Error procesando relay: {e}", 'error')
                    try:
                        client_socket.close()
                    except:
                        pass
                    continue

                # ===== CASO 4: CLIENTE REAL (C) =====
                if primer_byte != b'C':
                    try:
                        client_socket.close()
                    except:
                        pass
                    continue

                # ===== IDENTIDAD LÓGICA DEL CLIENTE =====
                # Después de la 'C', el cliente envía el nombre lógico que ya tenía.
                # En la primera conexión será el nombre asignado por el balanceador.
                try:
                    nombre_len_bytes = self.recibir_exacto_socket(client_socket, 2)
                    nombre_len = int.from_bytes(nombre_len_bytes, byteorder='big')
                    if nombre_len > 0:
                        nombre_solicitado = self.recibir_exacto_socket(
                            client_socket, nombre_len).decode('utf-8').strip()
                    else:
                        nombre_solicitado = ''
                except Exception:
                    nombre_solicitado = ''

                # Si el cliente ya tiene un nombre (Cliente N), conservarlo.
                if nombre_solicitado and re.fullmatch(r'Cliente\s+\d+', nombre_solicitado, re.IGNORECASE):
                    nombre_cliente = self._normalizar_nombre_cliente(nombre_solicitado)
                    numero = int(re.search(r'(\d+)', nombre_cliente).group(1))
                    self.contador_clientes = max(self.contador_clientes, numero)

                    # Si el socket anterior todavía figura como activo, reemplazarlo.
                    for socket_anterior, info in list(self.clientes.items()):
                        if (info.get('nombre', '').lower() == nombre_cliente.lower()
                                and socket_anterior is not client_socket):
                            try:
                                socket_anterior.close()
                            except:
                                pass
                            del self.clientes[socket_anterior]
                            break
                else:
                    self.contador_clientes += 1
                    nombre_cliente = f"Cliente {self.contador_clientes}"

                # Guardar cliente con su lock de envío
                self.clientes[client_socket] = {
                    "nombre": nombre_cliente,
                    "addr": addr,
                    "ultimo_ping": time.time(),
                    "send_lock": threading.Lock()
                }

                # Confirmar nombre al cliente
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

            except OSError:
                break
            except Exception as e:
                if self.servidor_activo and self.es_activo and self.server_socket is socket_escucha:
                    self.log(f"[!] Error aceptar: {e}", 'error')
                break
    def recibir_exacto_socket(self, conn, tamano):
        datos = b""
        while len(datos) < tamano:
            parte = conn.recv(tamano - len(datos))
            if not parte:
                raise ConnectionError("Conexión cerrada durante el registro del cliente")
            datos += parte
        return datos
    def _procesar_relay(self, conn):
        """
        Recibe un paquete relay del balanceador y lo retransmite localmente.
        NO lo reenvía al balanceador (evita loops).

        Formato entrante (después del byte 'R'):
          [4B puerto_origen][4B len_nombre][nombre][10B tamaño][20B destino][contenido]
        """
        # Leer puerto de origen
        puerto_origen_bytes = self.recibir_exacto(conn, 4)
        if len(puerto_origen_bytes) < 4:
            return

        # Leer metadatos
        meta_len_bytes = self.recibir_exacto(conn, 4)
        if len(meta_len_bytes) < 4:
            return
        nombre_len = int(meta_len_bytes.decode('utf-8'))

        nombre_bytes = self.recibir_exacto(conn, nombre_len)
        meta_size_bytes = self.recibir_exacto(conn, 10)
        tamano_archivo = int(meta_size_bytes.decode('utf-8'))

        destino_bytes = self.recibir_exacto(conn, 20)
        destino = destino_bytes.decode('utf-8').strip()

        contenido = self.recibir_exacto(conn, tamano_archivo)
        if len(contenido) != tamano_archivo:
            return

        nombre_archivo = nombre_bytes.decode('utf-8')

        # Construir paquete para enviar a los clientes locales
        paquete = (
                b'F'
                + meta_len_bytes
                + nombre_bytes
                + meta_size_bytes
                + contenido
        )

        # Retransmitir localmente según destino
        if destino.upper() == 'ALL':
            receptores = self.retransmitir(paquete, remitente=None)
        else:
            receptores = self.retransmitir_a_uno(
                paquete, destino, remitente=None
            )

        self.log(
            f"📥 [RELAY] '{nombre_archivo}' ({self.formatear_tamano(tamano_archivo)}) desde servidor remoto",
            'transfer'
        )
        if receptores:
            self.log(f"   ↳ Retransmitido localmente a: {', '.join(receptores)}", 'success')

    def _enviar_relay_al_balanceador(self, meta_len_bytes, nombre_bytes,
                                     meta_size_bytes, destino_bytes, contenido):
        """Envía un paquete al hub de relay del balanceador para que lo
        redistribuya a los otros servidores."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3.0)
            sock.connect((self.config_relay_host, self.config_relay_puerto))

            # Formato: [4B puerto_origen][4B len_nombre][nombre][10B tamaño][20B destino][contenido]
            puerto_origen_bytes = self.config_puerto.to_bytes(4, byteorder='big')
            paquete = (
                    puerto_origen_bytes
                    + meta_len_bytes
                    + nombre_bytes
                    + meta_size_bytes
                    + destino_bytes
                    + contenido
            )
            sock.sendall(paquete)
            sock.close()
        except Exception as e:
            self.log(f"[!] No se pudo enviar relay al balanceador: {e}", 'error')
    #Metodo que permite comunciacion de cada cliente de forma individual para el hilo ejecutado
    def manejar_cliente(self, conn, addr, nombre_cliente):
        try:
            # El bucle corre mientras el servidor sea el PRINCIPAL y esté encendido
            while self.servidor_activo and self.es_activo:

                # PASO 1: Leer el primer byte del mensaje para identificar la acción (Etiqueta)
                tipo = conn.recv(1)
                if not tipo:
                    break  # Si el byte está vacío, el cliente cerró la conexión

                # Mantener vivo al cliente: actualiza la hora de su última señal recibida
                if conn in self.clientes:
                    self.clientes[conn]["ultimo_ping"] = time.time()

                # =========================================================================
                # CASO A: El cliente envía un PING de control
                # =========================================================================
                if tipo == b'P':
                    try:
                        # Responde inmediatamente con un PONG para confirmar que sigue en línea
                        conn.sendall(b'PONG')
                    except:
                        break  # Si falla el envío, rompe el bucle para desconectar

                # =========================================================================
                # CASO B: El cliente envía un ARCHIVO (Protocolo de Transferencia)
                # =========================================================================
                elif tipo == b'F':
                    # 1. Leer los primeros 4 bytes que indican cuánto mide el NOMBRE del archivo
                    meta_len_bytes = self.recibir_exacto(conn, 4)
                    if not meta_len_bytes:
                        break

                    # Convierte esos bytes a número (ej: "0012" -> 12)
                    nombre_len = int(meta_len_bytes.decode('utf-8'))

                    # 2. Leer los bytes exactos del NOMBRE del archivo usando la longitud obtenida
                    nombre_archivo = self.recibir_exacto(conn, nombre_len).decode('utf-8')

                    # 3. Leer los siguientes 10 bytes que contienen el TAMAÑO del archivo real
                    meta_size_bytes = self.recibir_exacto(conn, 10)
                    tamano_archivo = int(meta_size_bytes.decode('utf-8'))

                    #El cliente envia exactamente 20bytes
                    destino_bytes = self.recibir_exacto(conn, 20)
                    if not destino_bytes or len(destino_bytes) != 20:
                        break
                    destino = destino_bytes.decode('utf-8').strip()  # .strip() quita espacios de relleno

                    # 4. Control de seguridad: Validar si el archivo supera el límite permitido
                    if tamano_archivo > self.TAMANO_MAXIMO:
                        self.log(f"⚠️ {nombre_cliente}: excede límite", 'error')
                        # Consume los bytes de la red para descartarlos sin saturar la memoria
                        self.consumir_bytes(conn, tamano_archivo)
                        continue  # Salta al inicio del bucle para esperar la siguiente petición

                    # 5. Descargar los bytes reales que componen el contenido del archivo
                    bytes_recibidos = self.recibir_exacto(conn, tamano_archivo)
                    if len(bytes_recibidos) != tamano_archivo:
                        break  # Si la descarga se corta o está incompleta, desconecta al cliente

                    # 6. Registrar el éxito de la descarga en la interfaz gráfica
                    self.log(f"📥 {nombre_cliente} → '{nombre_archivo}' ({self.formatear_tamano(tamano_archivo)})", 'transfer')
                    self.archivos_transferidos += 1
                    self.actualizar_stats()

                    # 7. Retransmisión: Volver a empaquetar SIN el campo destino
                    #    (el cliente receptor NO espera el campo destino; solo el servidor lo lee)
                    paquete = b'F' + meta_len_bytes + nombre_archivo.encode('utf-8') + meta_size_bytes + bytes_recibidos

                    # ===== DECISIÓN DE RETRANSMISIÓN SEGÚN EL DESTINO =====
                    if destino.upper() == 'ALL':
                        self.log(f" Broadcast solicitado por {nombre_cliente}", 'info')
                        receptores = self.retransmitir(paquete, remitente=conn)
                    else:
                        self.log(f"Envío dirigido a '{destino}' (solicitado por {nombre_cliente})", 'info')
                        receptores = self.retransmitir_a_uno(paquete, destino, remitente=conn)
                    # ===== FIN DECISIÓN =====

                    # Si el archivo le llegó a otros usuarios, se muestra en los logs
                    if receptores:
                        self.log(f"   ↳ Retransmitido a: {', '.join(receptores)}", 'success')

                    # ===== RELAY A OTROS SERVIDORES =====
                    # Enviar el mismo paquete al hub del balanceador para que
                    # llegue a clientes conectados a OTROS servidores.
                    threading.Thread(
                        target=self._enviar_relay_al_balanceador,
                        args=(meta_len_bytes, nombre_archivo.encode('utf-8'),
                              meta_size_bytes, destino_bytes, bytes_recibidos),
                        daemon=True
                    ).start()
                    # ===== FIN RELAY =====

        except Exception:
            # Captura cualquier error inesperado para evitar que el servidor colapse por completo
            pass

        finally:
            # 1. Elimina al cliente del registro/diccionario de usuarios activos
            if conn in self.clientes:
                del self.clientes[conn]

            # 2. Cierra el canal (socket) de forma segura para liberar el puerto
            try:
                conn.close()
            except:
                pass

            # 3. Informa en pantalla la salida del usuario y actualiza los contadores de la GUI
            self.log(f"[-] {nombre_cliente} desconectado", 'warning')
            self.actualizar_stats()


    # ==================== HEARTBEATS ====================
    def enviar_heartbeats(self):
        # El bucle corre continuamente mientras este servidor sea el Principal Activo
        while self.servidor_activo and self.es_activo:
            try:
                # 1. Crear un socket TCP temporal exclusivo para mandar el latido
                hb = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

                # Configurar un tiempo de espera de 2 segundos para no quedarse congelado si el backup no responde
                hb.settimeout(2)

                # 2. Intentar conectarse a la IP del host y al puerto especial del Backup
                hb.connect((self.config_host, self.config_puerto_backup))

                # 3. Formatear y enviar el mensaje de latido incluyendo la marca de tiempo exacta (Timestamp)
                hb.sendall(f"HEARTBEAT|{time.time()}".encode('utf-8'))

                # Cerrar el socket de inmediato para liberar recursos tras mandar el mensaje
                hb.close()

                # 4. Éxito: Obtener la hora actual del sistema para mostrarla en la interfaz
                ahora = datetime.now().strftime('%H:%M:%S')

                self.root.after(0, lambda: self.hb_label.config(
                    text=f"{ahora}", fg='#94e2d5'))

            except:
                # 5. Fallo: Si el Backup está apagado o no responde, entra a esta sección
                # Cambia el texto de la GUI a color gris ('#6c7086') avisando que no hay un respaldo activo
                self.root.after(0, lambda: self.hb_label.config(
                    text="Sin backup", fg='#6c7086'))

            # Esperar el tiempo configurado (ej: 1 o 2 segundos) antes de enviar el siguiente latido
            time.sleep(self.config_intervalo_heartbeat)

    def monitorear_backup(self):
        try:
            # 1. Crear el socket TCP para escuchar en el puerto exclusivo de comunicación interna
            monitor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            monitor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) # Permitir reutilizar el puerto rápido
            monitor.bind((self.config_host, self.config_puerto_backup))
            monitor.listen(5)
            monitor.settimeout(1.0) # Espera máxima de 1 segundo en el accept para poder revisar el bucle

            self.log(f"👂 Escuchando puerto backup {self.config_puerto_backup}", 'info')

            # El bucle corre continuamente mientras este servidor siga siendo el Jefe Activo
            while self.servidor_activo and self.es_activo:
                try:
                    # 2. Quedarse esperando a que el otro servidor intente comunicarse
                    conn, addr = monitor.accept()
                    conn.settimeout(2) # Tiempo límite de 2 segundos para leer los datos del mensaje

                    try:
                        # 3. Leer el mensaje enviado por el otro servidor
                        data = conn.recv(1024).decode('utf-8')

                        # Si el mensaje es la orden secreta de reclamo de trono
                        if data == "SOLICITAR_CONTROL":
                            self.log("Solicitud de control recibida", 'warning')

                            # Lanza un hilo en segundo plano para apagar de forma segura este servidor
                            # y devolverle el mando al jefe legítimo
                            threading.Thread(target=self.ceder_control, daemon=True).start()
                            break # Rompe el ciclo de monitoreo actual ya que dejará de ser activo
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
        #manejo de retars de epticiones por red para que se ejcute 1 vez
        if self.cediendo_control:
            return
        self.cediendo_control = True
        self.log("=" * 55, 'warning')
        self.log(" CEDIENDO EL CONTROL AL PRIMARIO", 'warning')
        self.log("=" * 55, 'warning')
        #Recorre todos los sockets de los clientes y os desconecte ara que se conecte al nuevo
        for c in list(self.clientes.keys()):
            try:
                c.close()
            except:
                pass
        self.clientes.clear()
        self.actualizar_stats()
        #Apaga los sckets y los desconecta
        self.es_activo = False
        try:
            if self.server_socket:
                self.server_socket.close()
                self.server_socket = None
        except:
            pass
        #Tiempo de descanso segun loconfigurado en el archivo
        time.sleep(self.config_tiempo_cesion)

        self.cediendo_control = False
        self.log("✓ Control cedido. Ahora soy BACKUP", 'role')
        self.convertirse_en_backup() #Ejecuta e metodo ara monitorear de nuevo al servidor principal

    # ==================== SOLICITAR CONTROL ====================
    def solicitar_control(self):
        time.sleep(2)

        intentos = 0
        # Intenta reclamar el puesto un máximo de 5 veces mientras el servidor siga encendido
        while intentos < 5 and self.servidor_activo:
            intentos += 1
            try:
                # 1. Crear un socket TCP temporal para enviar la petición interna
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(3) # Tiempo de espera máximo de 3 segundos para conectar

                # 2. Conectarse al puerto de respaldo donde el Backup está escuchando
                s.connect((self.config_host, self.config_puerto_backup))

                # 3. Enviar la orden  para que el Backup inicie su función 'ceder_control'
                s.sendall(b"SOLICITAR_CONTROL")
                s.close()

                self.log(f"Solicitud de control enviada (intento {intentos}/5)", 'role')

                # Monitorea si el Backup ya soltó el puerto principal
                # Hace un bucle de 20 segundos (20 iteraciones de 1 segundo cada una)
                for _ in range(20):
                    time.sleep(1)

                    # Verifica si el puerto público ya está libre y disponible para usarse
                    if self.puede_tomar_puerto():
                        self.log("✓ Puerto liberado por el backup", 'success')

                        # El Primario toma su trono legítimo y abre las puertas a los clientes
                        self.convertirse_en_activo()
                        return # Termina la función con éxito absoluto

            except Exception as e:
                # Si el Backup no responde o la red falla, registra el error y espera antes del próximo intento
                self.log(f"[!] Error solicitar control: {e}", 'error')
                time.sleep(2)

        # Fin del plan: Si tras 5 intentos falló la comunicación o el Backup nunca soltó el puerto
        self.log("⚠️ No se pudo obtener el control. Siguiendo como backup.", 'warning')


    # ==================== MONITOREO (BACKUP) ====================
    def monitorear_primario(self):
        """
        Actúa como un perro guardián (Watchdog) mientras este servidor sea el BACKUP.
        Escucha los latidos de vida ('Heartbeats') del servidor Principal. Si deja de
        recibirlos por un tiempo límite, inicia el proceso de toma de control.
        """
        try:
            # 1. Crear el socket TCP para abrir el canal de escucha exclusivo del Backup
            monitor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            monitor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) # Evitar el error de puerto bloqueado
            monitor.bind((self.config_host, self.config_puerto_backup))
            monitor.listen(5)

            # Poner un temporizador de 1 segundo en el accept para que el bucle no se quede congelado
            monitor.settimeout(1.0)

            self.log(f"Backup escuchando en {self.config_host}:{self.config_puerto_backup}", 'info')

            # Inicializa la hora del último latido con el tiempo actual del sistema
            self.ultimo_heartbeat = time.time()

            # El bucle corre continuamente mientras el monitoreo esté encendido y sigamos siendo BACKUP
            while self.monitor_activo and not self.es_activo:
                try:
                    # 2. Quedarse esperando a que el servidor Principal mande su latido de vida
                    conn, addr = monitor.accept()
                    conn.settimeout(2) # Tiempo de espera máximo de 2 segundos para leer el mensaje

                    try:
                        # 3. Leer el mensaje que llegó por la red
                        data = conn.recv(1024).decode('utf-8')

                        # Si el mensaje empieza con la palabra clave "HEARTBEAT"
                        if data.startswith("HEARTBEAT"):
                            # Actualiza la hora exacta del último latido recibido con éxito
                            self.ultimo_heartbeat = time.time()

                            # Obtiene la hora actual para actualizar el reloj digital de la interfaz gráfica
                            ahora = datetime.now().strftime('%H:%M:%S')
                            self.root.after(0, lambda: self.hb_label.config(
                                text=f"{ahora}", fg='#94e2d5'))
                    except:
                        pass # Ignora errores si una lectura individual falla de golpe

                    conn.close() # Cierra la conexión de este latido específico

                except socket.timeout:
                    # 4. Fase de emergencia: Si pasa 1 segundo sin que nadie llame, salta el Timeout
                    if self.es_activo:
                        break # Si este servidor ya subió a activo mientras esperaba, sale del bucle

                    # Calcula matemáticamente cuántos segundos exactos lleva en silencio el Principal
                    sin_latido = time.time() - self.ultimo_heartbeat

                    # Si el tiempo en silencio supera el límite permitido y no estamos en medio de otra transición
                    if sin_latido > self.config_timeout_heartbeat and not self.tomando_control:
                        self.log(f"⚠️ Activo sin responder por {sin_latido:.1f}s", 'warning')
                        self.log(f"¡TOMA DE CONTROL!", 'error')

                        # Lanza un hilo en segundo plano para ascender este servidor a modo Activo de inmediato
                        threading.Thread(target=self.tomar_control, daemon=True).start()

                except OSError:
                    break

        except Exception as e:
            # Captura errores críticos al inicializar el puerto o el socket
            self.log(f"[!] Error monitoreo: {e}", 'error')

        finally:
            try:
                monitor.close()
            except:
                pass

    def tomar_control(self):
        """
        Inicia el proceso para que el servidor de respaldo (Backup) tome el control
        y pase a ser el servidor Activo cuando el principal deja de responder.
        """
        # Freno de mano: si ya se está ejecutando la toma de control, no hace nada más
        if self.tomando_control:
            return

        self.tomando_control = True

        self.log("=" * 55, 'reconnect')
        self.log("  🔴 TOMANDO EL CONTROL", 'reconnect')
        self.log("=" * 55, 'reconnect')

        intentos = 0
        # Intenta un máximo de 15 veces amarrar el puerto público mientras no sea activo
        while intentos < 15 and not self.es_activo:
            intentos += 1
            time.sleep(2) # Espera 2 segundos entre cada intento

            # Llama a la función que valida si el puerto de los clientes ya está libre
            if self.puede_tomar_puerto():
                self.log(f"✓ Puerto {self.config_puerto} disponible", 'success')
                break
            else:
                self.log(f"⏳ Puerto ocupado (intento {intentos}/15)", 'warning')

        # Apaga y vuelve a encender el monitor para reiniciar los hilos limpiamente
        self.monitor_activo = False
        time.sleep(0.5)
        self.monitor_activo = True

        self.tomando_control = False
        # Ejecuta la conversión a servidor principal y actualiza la pantalla
        self.convertirse_en_activo()
        self.log("✓ Ahora soy el servidor ACTIVO", 'success')

    # ==================== UTILIDADES ====================
    def recibir_exacto(self, conn, tamano):
        """
        Lee datos del socket en fragmentos de máximo 4KB hasta completar
        exactamente el tamaño (en bytes) solicitado. Evita pérdidas de datos.
        """
        datos = b""
        while len(datos) < tamano:
            try:
                # Lee un bloque calculando el mínimo entre 4KB o la cantidad que falta
                chunk = conn.recv(min(4096, tamano - len(datos)))
                if not chunk:
                    return datos # Si el cliente se desconecta, devuelve lo que tenga
                datos += chunk
            except:
                return datos # Si da error la lectura, retorna lo acumulado
        return datos

    def consumir_bytes(self, conn, tamano):
        """
        Lee y descarta una cantidad de bytes específicos de la red.
        Se usa para vaciar el búfer cuando un archivo supera el peso máximo.
        """
        restantes = tamano
        while restantes > 0:
            try:
                # Descarga fragmentos de hasta 4KB de la red y los ignora
                chunk = conn.recv(min(4096, restantes))
                if not chunk:
                    break
                restantes -= len(chunk) # Resta los bytes leídos de la cuenta pendiente
            except:
                break

    def retransmitir(self, paquete, remitente):
        """
        Reenvía el paquete (archivo) recibido a todos los clientes que estén conectados,
        exceptuando a la conexión que envió el archivo originalmente (remitente).
        """
        receptores = []
        a_eliminar = []
        # Recorre la lista de clientes actuales
        for cliente, info in list(self.clientes.items()):
            if cliente != remitente:
                try:
                    # Intenta mandarle los datos del archivo al usuario
                    cliente.sendall(paquete)
                    receptores.append(info['nombre']) # Guarda el nombre para los logs
                except:
                    # Si falla el envío (cliente desconectado), lo anota para borrarlo
                    a_eliminar.append(cliente)

        # Elimina del diccionario a los clientes que dieron error de red
        for c in a_eliminar:
            if c in self.clientes:
                del self.clientes[c]
        return receptores

    def log(self, mensaje, tag='info'):
        """
        Añade un mensaje con formato y hora actual a la caja de texto (Tkinter).
        Usa .after(0) para hacerlo de forma segura desde hilos secundarios.
        """
        timestamp = datetime.now().strftime('%H:%M:%S')
        try:
            # Inserta la línea de texto al final del componente visual
            self.root.after(0, lambda: self.log_text.insert(
                tk.END, f"[{timestamp}] {mensaje}\n", tag))
            # Desplaza la barra de scroll automáticamente hacia abajo
            self.root.after(0, lambda: self.log_text.see(tk.END))
        except:
            pass

    def actualizar_stats(self):
        """
        Actualiza las etiquetas informativas de la GUI mostrando el total
        de clientes conectados y archivos retransmitidos en tiempo real.
        """
        try:
            self.root.after(0, lambda: self.clientes_label.config(
                text=f"👥 Clientes: {len(self.clientes)}"))
            self.root.after(0, lambda: self.archivos_label.config(
                text=f"📁 Archivos: {self.archivos_transferidos}"))
        except:
            pass

    def formatear_tamano(self, tamano):
        """
        Convierte una cantidad de bytes pura en una cadena de texto legible
        con sus respectivas unidades (B, KB, MB, GB).
        """
        if tamano < 1024:
            return f"{tamano} B"
        elif tamano < 1024 * 1024:
            return f"{tamano/1024:.2f} KB"
        elif tamano < 1024 * 1024 * 1024:
            return f"{tamano/(1024*1024):.2f} MB"
        return f"{tamano/(1024*1024*1024):.2f} GB"

    def cerrar_servidor(self):
        """
        Cierre con la X - el watchdog relanzará el servidor.
        Apaga banderas, cierra el socket del servidor y de todos los clientes conectados.
        """
        self.servidor_activo = False
        self.monitor_activo = False
        self.es_activo = False

        try:
            # Cierra el canal principal si está abierto
            if self.server_socket:
                self.server_socket.close()
        except:
            pass
        # Cierra las conexiones de cada uno de los clientes registrados
        for c in list(self.clientes.keys()):
            try:
                c.close()
            except:
                pass
        # Destruye la ventana de la interfaz gráfica
        self.root.destroy()

    def _normalizar_nombre_cliente(self, nombre):
        # Extrae SOLO el número del texto (ignora espacios, mayúsculas, etc.)
        match = re.search(r'(\d+)', nombre)
        if match:
            return f"Cliente {match.group(1)}"
        return nombre.strip()

    def retransmitir_a_uno(self, paquete, nombre_destino, remitente):
        nombre_norm = self._normalizar_nombre_cliente(nombre_destino)

        # Recorre todos los clientes conectados buscando coincidencia.
        for cliente, info in list(self.clientes.items()):
            # Se salta al remitente (no se envía a sí mismo).
            if cliente == remitente:
                continue

            # Compara normalizado contra normalizado (ambos en minúsculas).
            if self._normalizar_nombre_cliente(info['nombre']).lower() == nombre_norm.lower():
                try:
                    cliente.sendall(paquete)
                    return [info['nombre']]  # Éxito: retorna el nombre del receptor.
                except:
                    # Si falla el envío, elimina al cliente desconectado.
                    if cliente in self.clientes:
                        del self.clientes[cliente]
                    return []

        self.log(f"⚠️ Destino '{nombre_destino}' no encontrado o desconectado", 'warning')
        return []

if __name__ == "__main__":
    args = sys.argv[1:]

    if "--interno" in args:
        args.remove("--interno")
        # Revisa si la palabra 'backup' está en los argumentos para definir el rol de inicio
        es_backup = "backup" in [a.lower() for a in args]
        # Instancia la clase de la interfaz gráfica pasándole el rol correspondiente
        ServidorGUI(rol_inicial='backup' if es_backup else 'primario')
    else:
        # Modo watchdog (padre)
        es_backup = len(args) > 0 and args[0].lower() == 'backup'
        modo_watchdog(es_backup)
