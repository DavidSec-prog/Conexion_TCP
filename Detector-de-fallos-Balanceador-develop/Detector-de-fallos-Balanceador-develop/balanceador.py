# balanceador.py
import configparser
import os
import re
import socket
import threading
import subprocess
import sys
import time
from apscheduler.schedulers.background import BackgroundScheduler


class Balanceador:
    def __init__(self):
        self.cargar_configuracion()
        self.lock = threading.RLock()
        self.servidores = []
        self.activo = True
        self.total_dinamicos = 0
        self.contador_clientes_global = 0
        # CAMBIO: registro de qué puerto tiene asignado cada cliente.
        # Permite que al reconectar vuelva al MISMO servidor.
        self.registro_clientes = {}

        self._lanzar_servidores_iniciales()

        self.scheduler = BackgroundScheduler()
        self.scheduler.add_job(
            self._tarea_verificar_servidores,
            'interval',
            seconds=self.config_intervalo_health_check,
            id='health_check',
            replace_existing=True
        )
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
        self.config_puerto_base_dinamico = 5010
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
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(timeout)
            s.connect(("127.0.0.1", puerto))
            s.sendall(b'H')
            s.close()
            return True
        except:
            return False

    # ==================== LANZAMIENTO ====================
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
            entrada = entrada.strip()
            if not entrada:
                continue
            host, puerto = entrada.split(':')
            puerto = int(puerto)
            proceso = self._crear_proceso_servidor(puerto)
            with self.lock:
                self.servidores.append({
                    "puerto": puerto,
                    "clientes_actuales": 0,
                    "proceso": proceso,
                    "caido": proceso is None,
                    "relanzando": proceso is None,
                    "iniciando": False,
                    "es_dinamico": False
                })
                if proceso is None:
                    threading.Thread(
                        target=self._relanzar_servidor,
                        args=(puerto,),
                        daemon=True
                    ).start()

    # ==================== WATCHDOG ====================
    def _tarea_verificar_servidores(self):
        if not self.activo:
            return
        with self.lock:
            servidores_copia = list(self.servidores)
        for s in servidores_copia:
            if s.get("iniciando") or s.get("relanzando"):
                continue
            if not self.ping_servidor(s["puerto"], timeout=self.config_timeout_health_check):
                print(f"Servidor {s['puerto']} no responde")
                with self.lock:
                    if s.get("caido") or s.get("relanzando"):
                        continue
                    s["caido"] = True
                    s["relanzando"] = True
                threading.Thread(
                    target=self._relanzar_servidor,
                    args=(s["puerto"],),
                    daemon=True
                ).start()

    def _tarea_monitorear_conexiones(self):
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

        # Verificar antes de crear (evita duplicados)
        if self.ping_servidor(puerto):
            print(f"[WATCHDOG] Servidor {puerto} ya está vivo. Cancelando relanzamiento.")
            with self.lock:
                for s in self.servidores:
                    if s["puerto"] == puerto:
                        s["caido"] = False
                        s["relanzando"] = False
                        s["iniciando"] = False
                        break
            return

        proceso = self._crear_proceso_servidor(puerto)
        with self.lock:
            for s in self.servidores:
                if s["puerto"] == puerto:
                    s["proceso"] = proceso
                    s["caido"] = proceso is None
                    s["relanzando"] = proceso is None
                    s["iniciando"] = False
                    break
        if proceso is not None:
            print(f"[WATCHDOG] ✓ Servidor {puerto} relanzado")
        else:
            print(f"[WATCHDOG] ⚠️ No fue posible relanzar {puerto}")

    # ==================== ASIGNACIÓN ====================
    def asignar_servidor(self, nombre_cliente=None):
        """
        Reglas:
        0. Si el cliente YA tenía un puerto asignado, devolverlo (aunque esté relanzando).
           El cliente reintentará hasta que reviva. NO se crea dinámico.
        1. Si hay vivos con espacio → asignar al menos cargado.
        2. Si no hay vivos con espacio pero hay alguno relanzando/iniciando → devolverlo.
        3. Si todos vivos y llenos → crear UN dinámico.
        """
        with self.lock:
            # ===== PASO 0: REGLA DE REASIGNACIÓN =====
            if nombre_cliente and nombre_cliente in self.registro_clientes:
                puerto_original = self.registro_clientes[nombre_cliente]
                for s in self.servidores:
                    if s["puerto"] != puerto_original:
                        continue
                    if s.get("relanzando") or s.get("iniciando"):
                        print(f"[BALANCEADOR] {nombre_cliente} vuelve a "
                              f"{puerto_original} (relanzando)")
                        return s
                    if (not s.get("caido")
                            and s["clientes_actuales"] < self.config_max_clientes):
                        print(f"[BALANCEADOR] {nombre_cliente} vuelve a {puerto_original}")
                        return s
                    break

            # ===== PASO 1: actualizar estado real =====
            for s in self.servidores:
                if s.get("iniciando") or s.get("relanzando"):
                    continue
                if not self.ping_servidor(s["puerto"], timeout=0.5):
                    if not s.get("caido"):
                        s["caido"] = True
                        s["relanzando"] = True
                        print(f"[BALANCEADOR] Servidor {s['puerto']} detectado caído al asignar")
                        threading.Thread(
                            target=self._relanzar_servidor,
                            args=(s["puerto"],),
                            daemon=True
                        ).start()
                else:
                    if s.get("caido") and not s.get("relanzando"):
                        s["caido"] = False

            # ===== PASO 2: vivos con espacio =====
            vivos_con_espacio = [
                s for s in self.servidores
                if not s.get("caido") and not s.get("relanzando")
                   and s["clientes_actuales"] < self.config_max_clientes
            ]
            if vivos_con_espacio:
                mejor = min(vivos_con_espacio, key=lambda s: s["clientes_actuales"])
                mejor["clientes_actuales"] += 1
                return mejor

            # ===== PASO 3: pendientes (iniciando o relanzando) =====
            pendientes = [
                s for s in self.servidores
                if (s.get("iniciando") or s.get("relanzando"))
                   and s["clientes_actuales"] < self.config_max_clientes
            ]
            if pendientes:
                mejor = min(pendientes, key=lambda s: s["clientes_actuales"])
                estado = "iniciando" if mejor.get("iniciando") else "relanzando"
                print(f"[BALANCEADOR] Servidor {mejor['puerto']} {estado}; "
                      f"cliente reservado")
                return mejor

            # ===== PASO 4: crear dinámico =====
            nuevo_puerto = self.config_puerto_base_dinamico + self.total_dinamicos
            puertos_existentes = {s["puerto"] for s in self.servidores}
            while nuevo_puerto in puertos_existentes:
                self.total_dinamicos += 1
                nuevo_puerto = self.config_puerto_base_dinamico + self.total_dinamicos

            self.total_dinamicos += 1
            nuevo = {
                "puerto": nuevo_puerto,
                "clientes_actuales": 1,
                "proceso": None,
                "caido": False,
                "relanzando": False,
                "iniciando": True,
                "es_dinamico": True
            }
            self.servidores.append(nuevo)
            print(f"[ESCALAMIENTO] Creando servidor {nuevo_puerto}")

        proceso = self._crear_proceso_servidor(nuevo["puerto"])
        with self.lock:
            nuevo["proceso"] = proceso
            nuevo["iniciando"] = False
            nuevo["caido"] = proceso is None
            nuevo["relanzando"] = proceso is None

        if proceso is not None:
            print(f"[ESCALAMIENTO] ✓ Servidor {nuevo['puerto']} listo")
        else:
            print(f"[ESCALAMIENTO] ⚠️ Servidor {nuevo['puerto']} no pudo iniciar")

        return nuevo

    def mostrar_estado(self):
        print(f"Máximo de clientes por servidor: {self.config_max_clientes}")
        print(f"Puerto del balanceador: {self.config_puerto_balanceador}")
        print("Servidores actuales:")
        with self.lock:
            for s in self.servidores:
                if s.get("iniciando"):
                    estado = "INICIANDO"
                elif s.get("relanzando"):
                    estado = "RELANZANDO"
                elif s.get("caido"):
                    estado = "CAÍDO"
                else:
                    estado = "VIVO"
                print(f"  - 127.0.0.1:{s['puerto']} | clientes: "
                      f"{s['clientes_actuales']} | {estado}")

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
        """
        Protocolo cliente → balanceador:
          - "NUEVO"                 → cliente nuevo
          - "REASIGNAR|Cliente N"   → cliente que ya tenía nombre, quiere volver
        Respuesta balanceador → cliente:
          - "host:puerto|Cliente N"
        """
        try:
            # ===== LEER IDENTIDAD DEL CLIENTE =====
            try:
                conn.settimeout(2.0)
                mensaje = conn.recv(1024).decode('utf-8').strip()
            except:
                mensaje = "NUEVO"

            # ===== DECIDIR NOMBRE =====
            nombre_cliente = None
            if mensaje.startswith("REASIGNAR|"):
                nombre_solicitado = mensaje.split("|", 1)[1].strip()
                # Validar formato "Cliente N"
                if re.fullmatch(r"Cliente\s+\d+", nombre_solicitado, re.IGNORECASE):
                    numero = int(re.search(r"\d+", nombre_solicitado).group())
                    nombre_cliente = f"Cliente {numero}"
                    # Sincronizar el contador global sin incrementarlo
                    with self.lock:
                        self.contador_clientes_global = max(
                            self.contador_clientes_global, numero
                        )

            if nombre_cliente is None:
                # Cliente nuevo → asignar nombre nuevo
                with self.lock:
                    self.contador_clientes_global += 1
                    nombre_cliente = f"Cliente {self.contador_clientes_global}"

            # ===== ASIGNAR SERVIDOR =====
            servidor = self.asignar_servidor(nombre_cliente)
            if servidor is None:
                conn.sendall(b"ERROR:NO_SERVIDORES\n")
                return

            # ===== REGISTRAR =====
            with self.lock:
                self.registro_clientes[nombre_cliente] = servidor["puerto"]

            respuesta = f"127.0.0.1:{servidor['puerto']}|{nombre_cliente}\n"
            conn.sendall(respuesta.encode('utf-8'))
            print(f"[BALANCEADOR] {nombre_cliente} desde {addr[0]} -> "
                  f"127.0.0.1:{servidor['puerto']}")

        except Exception as e:
            print(f"[BALANCEADOR] Error atendiendo a {addr[0]}: {e}")
        finally:
            conn.close()

    # ==================== CIERRE ====================
    def cerrar(self):
        print("\n[BALANCEADOR] Cerrando y matando servidores hijos...")
        self.activo = False

        if hasattr(self, 'scheduler') and self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            print("  [SCHEDULER] detenido")

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