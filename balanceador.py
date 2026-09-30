# balanceador.py
import configparser
import os
import socket
import threading
import subprocess
import sys
import time


class Balanceador:
    def __init__(self):
        self.cargar_configuracion()
        self.lock = threading.Lock()  # protege servidores + indice_round_robin
        self.indice_round_robin = 0
        self.servidores = []
        # Detectar qué servidores iniciales están vivos (arrancados manualmente).
        self._detectar_servidores_iniciales()

    def cargar_configuracion(self):
        config = configparser.ConfigParser()
        self.config_servidores_iniciales = "127.0.0.1:5000,127.0.0.1:5002"
        self.config_max_clientes = 3
        self.config_puerto_balanceador = 6000
        self.config_puerto_base_dinamico = 5010
        self.config_intervalo_health_check = 2
        self.config_timeout_health_check = 5

        if os.path.exists('config.ini'):
            config.read('config.ini')
            if 'BALANCEADOR' in config:
                self.config_servidores_iniciales = config['BALANCEADOR'].get(
                    'servidores_iniciales', self.config_servidores_iniciales)
                self.config_max_clientes = int(config['BALANCEADOR'].get(
                    'max_clientes_por_servidor', self.config_max_clientes))
                self.config_puerto_balanceador = int(config['BALANCEADOR'].get(
                    'puerto_balanceador', self.config_puerto_balanceador))
                self.config_puerto_base_dinamico = int(config['BALANCEADOR'].get(
                    'puerto_base_dinamico', self.config_puerto_base_dinamico))
                self.config_intervalo_health_check = int(config['BALANCEADOR'].get(
                    'intervalo_health_check', self.config_intervalo_health_check))
                self.config_timeout_health_check = int(config['BALANCEADOR'].get(
                    'timeout_health_check', self.config_timeout_health_check))

    # ==================== HEALTH CHECK ====================
    def ping_servidor(self, puerto):
        """Verifica si un servidor está vivo abriendo y cerrando un socket TCP."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1)
            s.connect(("127.0.0.1", puerto))
            s.close()
            return True
        except:
            return False

    # ==================== DETECCIÓN INICIAL ====================
    def _detectar_servidores_iniciales(self):
        """Detecta cuáles servidores iniciales están vivos (arrancados manualmente)."""
        print("[BALANCEADOR] Detectando servidores iniciales...")
        for entrada in self.config_servidores_iniciales.split(','):
            host, puerto = entrada.strip().split(':')
            puerto = int(puerto)

            if self.ping_servidor(puerto):
                print(f"[BALANCEADOR] ✓ Servidor {host}:{puerto} detectado")
                self.servidores.append({
                    "host": host,
                    "puerto": puerto,
                    "clientes_actuales": 0,
                    "proceso": None,
                    "manual": True,
                    "pendiente": False
                })
            else:
                print(f"[BALANCEADOR] ✗ Servidor {host}:{puerto} NO responde (¿lo arrancaste?)")

    # ==================== LANZAMIENTO DE SERVIDORES DINÁMICOS ====================
    def lanzar_proceso_servidor(self, puerto):
        """Lanza servidor.py y espera a que el puerto esté realmente abierto."""
        try:
            env = os.environ.copy()
            env['SERVIDOR_PUERTO'] = str(puerto)
            directorio = os.path.dirname(os.path.abspath(__file__))
            script = os.path.join(directorio, 'servidor.py')
            proceso = subprocess.Popen(
                [sys.executable, script, '--interno', '--pool'],
                cwd=directorio,
                env=env
            )
            print(f"[BALANCEADOR] Servidor lanzado en {puerto} (PID {proceso.pid})")

            esperado = 0.0
            while esperado < 20.0:
                if self.ping_servidor(puerto):
                    print(f"[BALANCEADOR] ✓ Servidor {puerto} listo")
                    return proceso
                time.sleep(0.5)
                esperado += 0.5

            print(f"[BALANCEADOR] ⚠️ Servidor {puerto} no abrió el puerto tras 20s")
            return proceso
        except Exception as e:
            print(f"[BALANCEADOR] Error lanzando servidor en {puerto}: {e}")
            return None

    def _lanzar_dinamico_async(self, puerto):
        """Se ejecuta en hilo paralelo. Lanza el servidor y actualiza la lista."""
        proceso = self.lanzar_proceso_servidor(puerto)
        with self.lock:
            for s in self.servidores:
                if s["puerto"] == puerto:
                    s["proceso"] = proceso
                    s["pendiente"] = False
                    break
        if proceso:
            threading.Thread(
                target=self.vigilar_dinamico,
                args=(puerto, proceso),
                daemon=True
            ).start()

    def vigilar_dinamico(self, puerto, proceso):
        """Watchdog: si el servidor dinámico muere, lo relanza tras 10s."""
        proceso.wait()
        print(f"[WATCHDOG] Servidor {puerto} caído. Relanzando en 10s...")
        time.sleep(10)
        self._lanzar_dinamico_async(puerto)

    # ==================== ASIGNACIÓN ====================
    def asignar_servidor(self):
        """Thread-safe: busca servidor con espacio o crea uno nuevo."""
        with self.lock:
            # 1. Servidores NO pendientes con espacio
            total = len(self.servidores)
            for i in range(total):
                indice = (self.indice_round_robin + i) % total
                servidor = self.servidores[indice]
                if (not servidor.get("pendiente")
                        and servidor["clientes_actuales"] < self.config_max_clientes):
                    servidor["clientes_actuales"] += 1
                    self.indice_round_robin = (indice + 1) % total
                    return servidor

            # 2. Si hay algún pendiente, devolverlo (no crear otro)
            for s in self.servidores:
                if s.get("pendiente"):
                    print(f"[BALANCEADOR] Servidor {s['puerto']} pendiente, reutilizando")
                    return s

            # 3. Todos llenos → crear dinámico
            nuevo = self.crear_servidor_dinamico()
            nuevo["clientes_actuales"] += 1
            self.indice_round_robin = (
                    (self.servidores.index(nuevo) + 1) % len(self.servidores)
            )
            return nuevo

    def crear_servidor_dinamico(self):
        """Crea el registro y lanza el proceso EN PARALELO (sin bloquear el lock)."""
        cantidad_dinamicos = sum(
            1 for s in self.servidores if s["puerto"] >= self.config_puerto_base_dinamico
        )
        nuevo_puerto = self.config_puerto_base_dinamico + cantidad_dinamicos

        nuevo_servidor = {
            "host": "127.0.0.1",
            "puerto": nuevo_puerto,
            "clientes_actuales": 0,
            "proceso": None,
            "manual": False,
            "pendiente": True
        }
        self.servidores.append(nuevo_servidor)
        print(f"[ESCALAMIENTO] Nuevo servidor creado: 127.0.0.1:{nuevo_puerto}")

        threading.Thread(
            target=self._lanzar_dinamico_async,
            args=(nuevo_puerto,),
            daemon=True
        ).start()

        return nuevo_servidor

    def mostrar_estado(self):
        print(f"Máximo de clientes por servidor: {self.config_max_clientes}")
        print(f"Puerto del balanceador: {self.config_puerto_balanceador}")
        print("Servidores actuales:")
        for s in self.servidores:
            estado = "PENDIENTE" if s.get("pendiente") else ("manual" if s.get("manual") else "listo")
            print(f"  - {s['host']}:{s['puerto']} | clientes: {s['clientes_actuales']} | {estado}")

    # ==================== RED ====================
    def iniciar(self):
        """Abre el socket del balanceador y empieza a aceptar clientes."""
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind(("0.0.0.0", self.config_puerto_balanceador))
        server_socket.listen(10)

        print(f"[BALANCEADOR] Escuchando en puerto {self.config_puerto_balanceador}...")
        self.mostrar_estado()

        while True:
            conn, addr = server_socket.accept()
            threading.Thread(
                target=self.atender_cliente, args=(conn, addr), daemon=True
            ).start()

    def atender_cliente(self, conn, addr):
        """Responde con host:puerto del servidor asignado y cierra la conexión."""
        try:
            servidor = self.asignar_servidor()
            respuesta = f"{servidor['host']}:{servidor['puerto']}\n"
            conn.sendall(respuesta.encode('utf-8'))
            print(f"[BALANCEADOR] Cliente desde {addr[0]} -> asignado a {servidor['host']}:{servidor['puerto']}")
        except Exception as e:
            print(f"[BALANCEADOR] Error atendiendo a {addr[0]}: {e}")
        finally:
            conn.close()


if __name__ == "__main__":
    b = Balanceador()
    b.iniciar()