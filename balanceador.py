# balanceador.py
import configparser
import os
import socket
import threading
import subprocess
import sys
import time
from apscheduler.schedulers.background import BackgroundScheduler



class Balanceador:
    def __init__(self):
        self.cargar_configuracion()
        self.lock = threading.Lock()
        self.servidores = []
        self.activo = True
        self.total_dinamicos = 0

        self._lanzar_servidores_iniciales()


        self.scheduler = BackgroundScheduler()
        # verificar salud de cada servidor cada 2 segundos.
        self.scheduler.add_job(
            self._tarea_verificar_servidores,
            'interval',
            seconds=self.config_intervalo_health_check,
            id='health_check',
            replace_existing=True
        )
        # monitoreo de conexiones cada 5 segundos (log de estado).
        self.scheduler.add_job(
            self._tarea_monitorear_conexiones,
            'interval',
            seconds=5,
            id='monitorear_conexiones',
            replace_existing=True
        )
        self.scheduler.start()
        print("[SCHEDULER] Iniciado con 2 tareas programadas")

    def cargar_configuracion(self):
        config = configparser.ConfigParser()
        self.config_servidores_iniciales = "127.0.0.1:5000"
        self.config_max_clientes = 3
        self.config_puerto_balanceador = 6000
        self.config_puerto_base_dinamico = 5002
        self.config_intervalo_health_check = 2
        self.config_timeout_health_check = 5
        self.tiempo_relanzamiento = 10

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
    def ping_servidor(self, puerto, timeout=1.0):
        """Ping rápido con timeout configurable."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(timeout)
            s.connect(("127.0.0.1", puerto))
            s.sendall(b'H')
            s.close()
            return True
        except:
            return False

    # ==================== LANZAMIENTO DE SERVIDORES ====================
    def _crear_proceso_servidor(self, puerto):
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

    def _lanzar_servidores_iniciales(self):
        print("[BALANCEADOR] Lanzando servidores iniciales...")
        for entrada in self.config_servidores_iniciales.split(','):
            host, puerto = entrada.strip().split(':')
            puerto = int(puerto)
            proceso = self._crear_proceso_servidor(puerto)
            with self.lock:
                self.servidores.append({
                    "puerto": puerto,
                    "clientes_actuales": 0,
                    "proceso": proceso,
                    "caido": False,
                    "relanzando": False,
                    "es_dinamico": False
                })

    # WATCHDOG GLOBAL - APSCHEDULER
    def _tarea_verificar_servidores(self):
        """
        Verifica la salud de cada servidor y relanza los que se cayeron.
        """
        if not self.activo:
            return

        with self.lock:
            servidores_copia = list(self.servidores)

        for s in servidores_copia:
            if s.get("relanzando") or s.get("caido"):
                continue

            if not self.ping_servidor(s["puerto"]):
                print(f"Servidor {s['puerto']} no responde")
                with self.lock:
                    s["caido"] = True
                    s["relanzando"] = True
                    s["clientes_actuales"] = 0

                threading.Thread(
                    target=self._relanzar_servidor,
                    args=(s["puerto"],),
                    daemon=True
                ).start()

    def _tarea_monitorear_conexiones(self):
        """
        Muestra en consola el estado de todos los servidores.
        Sirve para trazabilidad y monitoreo continuo.
        """
        if not self.activo:
            return

        with self.lock:
            total = len(self.servidores)
            vivos = sum(1 for s in self.servidores
                        if not s.get("caido") and not s.get("relanzando"))
            clientes_totales = sum(s["clientes_actuales"] for s in self.servidores)

        print(f"[MONITOR] Servidores: {vivos}/{total} vivos | "
              f"Clientes asignados: {clientes_totales}")

    def _relanzar_servidor(self, puerto):
        """Espera el countdown y relanza UN servidor en el MISMO puerto."""
        print("=" * 60)
        print(f"  ⚠️  Servidor {puerto} se ha cerrado")
        print(f"  🔄 Protocolo de recuperación activado")
        print(f"  ⏳ Relanzando en {self.tiempo_relanzamiento} segundos...")
        print("=" * 60)

        for i in range(self.tiempo_relanzamiento, 0, -1):
            if not self.activo:
                return
            print(f"  ⏳ {i}...")
            time.sleep(1)

        if not self.activo:
            return

        proceso = self._crear_proceso_servidor(puerto)
        with self.lock:
            for s in self.servidores:
                if s["puerto"] == puerto:
                    s["proceso"] = proceso
                    s["caido"] = False
                    s["relanzando"] = False
                    s["clientes_actuales"] = 0
                    break
        print(f"[WATCHDOG] ✓ Servidor {puerto} relanzado")

    # ==================== ASIGNACIÓN (CON REGLAS ESTRICTAS) ====================
    def asignar_servidor(self):
        """
        Reglas de asignación:
        1. Ping inmediato a cada servidor para conocer su estado real AHORA.
        2. Si hay vivos con espacio → asignar al menos cargado.
        3. Si NO hay vivos con espacio PERO hay algún caído/relanzando → devolverlo.
           El cliente reintentará hasta que reviva. NO se crea dinámico.
        4. Si todos vivos y llenos → crear dinámico.
        """
        with self.lock:
            # ===== PASO 1: Actualizar estado real de cada servidor =====
            for s in self.servidores:
                if s.get("relanzando"):
                    continue
                if not self.ping_servidor(s["puerto"], timeout=0.5):
                    if not s.get("caido"):
                        # Recién caído → marcar y lanzar relanzamiento
                        s["caido"] = True
                        s["relanzando"] = True
                        s["clientes_actuales"] = 0
                        print(f"[BALANCEADOR] Servidor {s['puerto']} detectado caído al asignar")
                        threading.Thread(
                            target=self._relanzar_servidor,
                            args=(s["puerto"],),
                            daemon=True
                        ).start()
                else:
                    # Si estaba caído y ahora responde → marcarlo vivo
                    if s.get("caido") and not s.get("relanzando"):
                        s["caido"] = False

            # ===== PASO 2: Buscar vivos con espacio =====
            vivos_con_espacio = [
                s for s in self.servidores
                if not s.get("caido") and not s.get("relanzando")
                   and s["clientes_actuales"] < self.config_max_clientes
            ]

            if vivos_con_espacio:
                mejor = min(vivos_con_espacio, key=lambda s: s["clientes_actuales"])
                mejor["clientes_actuales"] += 1
                return mejor

            # ===== PASO 3: ¿Hay algún servidor caído/relanzando? =====
            # ⭐ Si SÍ → devolverlo. El cliente reintentará hasta que reviva.
            # ⭐ NO se crea dinámico.
            caidos = [
                s for s in self.servidores
                if s.get("caido") or s.get("relanzando")
            ]
            if caidos:
                print(f"[BALANCEADOR] Sin espacio, pero hay {len(caidos)} servidor(es) por revivir")
                print(f"[BALANCEADOR] Cliente reintentará hasta que {caidos[0]['puerto']} vuelva")
                return caidos[0]

            # ===== PASO 4: Todos vivos y llenos → crear dinámico =====
            print("[BALANCEADOR] Todos los servidores vivos y llenos → creando dinámico")
            nuevo_puerto = self.config_puerto_base_dinamico + self.total_dinamicos
            self.total_dinamicos += 1
            nuevo = {
                "puerto": nuevo_puerto,
                "clientes_actuales": 1,
                "proceso": None,
                "caido": False,
                "relanzando": False,
                "es_dinamico": True
            }
            self.servidores.append(nuevo)
            print(f"[ESCALAMIENTO] Creando servidor {nuevo_puerto} para el cliente nuevo")

        # Lanzar el proceso FUERA del lock (tarda ~5s)
        proceso = self._crear_proceso_servidor(nuevo_puerto)
        with self.lock:
            nuevo["proceso"] = proceso
        print(f"[ESCALAMIENTO] ✓ Servidor {nuevo_puerto} listo")
        return nuevo

    def mostrar_estado(self):
        print(f"Máximo de clientes por servidor: {self.config_max_clientes}")
        print(f"Puerto del balanceador: {self.config_puerto_balanceador}")
        print("Servidores actuales:")
        with self.lock:
            for s in self.servidores:
                if s.get("relanzando"):
                    estado = "RELANZANDO"
                elif s.get("caido"):
                    estado = "CAÍDO"
                else:
                    estado = "VIVO"
                print(f"  - 127.0.0.1:{s['puerto']} | clientes: {s['clientes_actuales']} | {estado}")

    # ==================== RED ====================
    def iniciar(self):
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind(("0.0.0.0", self.config_puerto_balanceador))
        server_socket.listen(10)

        print(f"[BALANCEADOR] Escuchando en puerto {self.config_puerto_balanceador}...")
        self.mostrar_estado()

        try:
            while self.activo:
                conn, addr = server_socket.accept()
                threading.Thread(
                    target=self.atender_cliente, args=(conn, addr), daemon=True
                ).start()
        except KeyboardInterrupt:
            self.cerrar()
        except Exception as e:
            print(f"[BALANCEADOR] Error en bucle principal: {e}")
            self.cerrar()

    def atender_cliente(self, conn, addr):
        try:
            servidor = self.asignar_servidor()
            if servidor is None:
                conn.sendall(b"ERROR:NO_SERVIDORES\n")
                return
            respuesta = f"127.0.0.1:{servidor['puerto']}\n"
            conn.sendall(respuesta.encode('utf-8'))
            print(f"[BALANCEADOR] Cliente desde {addr[0]} -> asignado a 127.0.0.1:{servidor['puerto']}")
        except Exception as e:
            print(f"[BALANCEADOR] Error atendiendo a {addr[0]}: {e}")
        finally:
            conn.close()

    # ==================== CIERRE ====================
    def cerrar(self):
        print("\n[BALANCEADOR] Cerrando y matando servidores hijos...")
        self.activo = False

        # ===== Apagar APScheduler limpiamente =====
        if hasattr(self, 'scheduler') and self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            print(" detenido")

        with self.lock:
            for s in self.servidores:
                proceso = s.get("proceso")
                if proceso:
                    try:
                        proceso.terminate()
                    except:
                        pass
        time.sleep(1)
        with self.lock:
            for s in self.servidores:
                proceso = s.get("proceso")
                if proceso:
                    try:
                        if proceso.poll() is None:
                            proceso.kill()
                    except:
                        pass
        print("[BALANCEADOR] Todo cerrado.")


if __name__ == "__main__":
    b = Balanceador()
    try:
        b.iniciar()
    except KeyboardInterrupt:
        b.cerrar()