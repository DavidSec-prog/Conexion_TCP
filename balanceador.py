# balanceador.py
import configparser
import os


class Balanceador:
    def __init__(self):
        self.cargar_configuracion()
        self.servidores = self.inicializar_servidores()
        self.indice_round_robin = 0

    def cargar_configuracion(self):
        config = configparser.ConfigParser()
        # Valores por defecto, por si el .ini no existe o falta la sección
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
        """Convierte 'host:puerto,host:puerto' en una lista de diccionarios."""
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
        """Busca un servidor con espacio disponible en orden round-robin.
        Si todos están llenos, crea uno nuevo."""
        total = len(self.servidores)
        for i in range(total):
            indice = (self.indice_round_robin + i) % total
            servidor = self.servidores[indice]
            if servidor["clientes_actuales"] < self.config_max_clientes:
                servidor["clientes_actuales"] += 1
                self.indice_round_robin = (indice + 1) % total
                return servidor

        # Ningún servidor tiene espacio -> crear uno nuevo
        nuevo = self.crear_servidor_dinamico()
        nuevo["clientes_actuales"] += 1
        self.indice_round_robin = (self.servidores.index(nuevo) + 1) % len(self.servidores)
        return nuevo

    def crear_servidor_dinamico(self):
        """Agrega un nuevo servidor a la lista con un puerto del rango dinámico."""
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


if __name__ == "__main__":
    b = Balanceador()
    b.mostrar_estado()

    print("\n--- Simulando 8 clientes conectándose ---")
    for i in range(1, 9):
        asignado = b.asignar_servidor()
        print(f"Cliente {i} -> {asignado['host']}:{asignado['puerto']}")

    print("\n--- Estado final ---")
    b.mostrar_estado()