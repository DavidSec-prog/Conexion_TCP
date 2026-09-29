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

        if os.path.exists('config.ini'):
            config.read('config.ini')
            if 'BALANCEADOR' in config:
                self.config_servidores_iniciales = config['BALANCEADOR'].get(
                    'servidores_iniciales', self.config_servidores_iniciales)
                self.config_max_clientes = int(config['BALANCEADOR'].get(
                    'max_clientes_por_servidor', self.config_max_clientes))
                self.config_puerto_balanceador = int(config['BALANCEADOR'].get(
                    'puerto_balanceador', self.config_puerto_balanceador))

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
        """Elige el siguiente servidor en orden circular (round-robin)."""
        servidor = self.servidores[self.indice_round_robin]
        servidor["clientes_actuales"] += 1
        self.indice_round_robin = (self.indice_round_robin + 1) % len(self.servidores)
        return servidor

    def mostrar_estado(self):
        print(f"Máximo de clientes por servidor: {self.config_max_clientes}")
        print(f"Puerto del balanceador: {self.config_puerto_balanceador}")
        print("Servidores iniciales:")
        for s in self.servidores:
            print(f"  - {s['host']}:{s['puerto']} | clientes: {s['clientes_actuales']}")


if __name__ == "__main__":
    b = Balanceador()
    b.mostrar_estado()

    print("\n--- Simulando 5 clientes conectándose ---")
    for i in range(1, 6):
        asignado = b.asignar_servidor()
        print(f"Cliente {i} -> {asignado['host']}:{asignado['puerto']}")

    print("\n--- Estado final ---")
    b.mostrar_estado()