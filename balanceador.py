# balanceador.py
import configparser
import os
import socket
import threading


class Balanceador:
    def __init__(self):
        self.cargar_configuracion()
        self.servidores = self.inicializar_servidores()
        self.indice_round_robin = 0
        self.lock = threading.Lock()  # protege servidores + indice_round_robin

    def cargar_configuracion(self):
        config = configparser.ConfigParser()
        self.config_servidores_iniciales = "127.0.0.1:5000,127.0.0.1:5002"
        self.config_max_clientes = 3
        self.config_puerto_balanceador = 6000
        self.config_puerto_base_dinamico = 5010

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

    def inicializar_servidores(self):
        servidores = []
        for entrada in self.config_servidores_iniciales.split(','):
            host, puerto = entrada.strip().split(':')
            servidores.append({
                "host": host,
                "puerto": int(puerto),
                "clientes_actuales": 0
            })
        return servidores

    def asignar_servidor(self):
        """Thread-safe: busca servidor con espacio o crea uno nuevo."""
        with self.lock:
            total = len(self.servidores)
            for i in range(total):
                indice = (self.indice_round_robin + i) % total
                servidor = self.servidores[indice]
                if servidor["clientes_actuales"] < self.config_max_clientes:
                    servidor["clientes_actuales"] += 1
                    self.indice_round_robin = (indice + 1) % total
                    return servidor

            nuevo = self.crear_servidor_dinamico()
            nuevo["clientes_actuales"] += 1
            self.indice_round_robin = (self.servidores.index(nuevo) + 1) % len(self.servidores)
            return nuevo

    def crear_servidor_dinamico(self):
        """Se llama SIEMPRE dentro de self.lock ya adquirido (ver asignar_servidor)."""
        cantidad_dinamicos = sum(
            1 for s in self.servidores if s["puerto"] >= self.config_puerto_base_dinamico
        )
        nuevo_puerto = self.config_puerto_base_dinamico + cantidad_dinamicos
        nuevo_servidor = {
            "host": "127.0.0.1",
            "puerto": nuevo_puerto,
            "clientes_actuales": 0
        }
        self.servidores.append(nuevo_servidor)
        print(f"[ESCALAMIENTO] Nuevo servidor creado: 127.0.0.1:{nuevo_puerto}")
        return nuevo_servidor

    def mostrar_estado(self):
        print(f"Máximo de clientes por servidor: {self.config_max_clientes}")
        print(f"Puerto del balanceador: {self.config_puerto_balanceador}")
        print("Servidores actuales:")
        for s in self.servidores:
            print(f"  - {s['host']}:{s['puerto']} | clientes: {s['clientes_actuales']}")

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
            print(f"[BALANCEADOR] Cliente {addr} -> asignado a {servidor['host']}:{servidor['puerto']}")
        except Exception as e:
            print(f"[BALANCEADOR] Error atendiendo a {addr}: {e}")
        finally:
            conn.close()


if __name__ == "__main__":
    b = Balanceador()
    b.iniciar()