import RPi.GPIO as GPIO
import time
import random
import threading
import sqlite3
from datetime import datetime
from multiprocessing import Process, Queue, Manager
from flask import Flask, send_file


# ===========================================================
#   FUNCIÓN — GUARDAR MEDIA EN LA BASE DE DATOS
# ===========================================================

def guardar_media_en_bd(media):
    """Guarda la media final en la BD raspBerryBase.db"""
    conn = sqlite3.connect("/home/pi/raspBerryBase.db")
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tiempos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT,
            media REAL
        )
    """)

    fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("INSERT INTO tiempos (fecha, media) VALUES (?, ?)", (fecha, media))

    conn.commit()
    conn.close()



# ===========================================================
#   PROCESO A — HARDWARE
# ===========================================================

def proceso_hardware(q_cmd, q_evt):

    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)

    botones = {"BTN1": 25, "BTN2": 27, "BTN3": 17, "BTN4": 24}
    leds    = {"BTN1": 14, "BTN2": 15, "BTN3": 18, "BTN4": 8}
    buzzer  = 13
    gnd_pines = [23, 22, 16, 26]
    buzzer_gnd = 21

    apagar = {"value": False}

    GPIO.setup(buzzer_gnd, GPIO.OUT)
    GPIO.output(buzzer_gnd, GPIO.LOW)

    for g in gnd_pines:
        GPIO.setup(g, GPIO.OUT)
        GPIO.output(g, GPIO.LOW)

    for pin in botones.values():
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    for pin in leds.values():
        GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, GPIO.LOW)

    GPIO.setup(buzzer, GPIO.OUT)
    GPIO.output(buzzer, GPIO.LOW)

    ultima_lectura = {name: 1 for name in botones}
    cola_efectos = []
    lock = threading.Lock()


    # ----------- HILO DE BOTONES -----------
    def hilo_botones():
        while not apagar["value"]:
            for nombre, pin in botones.items():

                lectura = GPIO.input(pin)

                if lectura == GPIO.LOW and ultima_lectura[nombre] == 1:
                    time.sleep(0.02)
                    if GPIO.input(pin) == GPIO.LOW:
                        q_evt.put({"tipo": "BOTON", "valor": nombre})
                        ultima_lectura[nombre] = 0

                if lectura == GPIO.HIGH:
                    ultima_lectura[nombre] = 1

            time.sleep(0.001)


    # ----------- HILO DE EFECTOS -----------
    def hilo_efectos():
        while not apagar["value"]:
            with lock:
                e = cola_efectos.pop(0) if cola_efectos else None

            if e:
                t = e["tipo"]

                if t == "LED_ON":
                    GPIO.output(leds[e["boton"]], True)

                elif t == "LED_OFF":
                    GPIO.output(leds[e["boton"]], False)

                elif t == "BUZZ":
                    GPIO.output(buzzer, True)
                    time.sleep(0.15)
                    GPIO.output(buzzer, False)

                elif t == "BUZZ_LONG":
                    GPIO.output(buzzer, True)
                    time.sleep(0.40)
                    GPIO.output(buzzer, False)

                elif t == "SHUTDOWN":
                    apagar["value"] = True
                    return

            time.sleep(0.001)


    threading.Thread(target=hilo_botones, daemon=True).start()
    threading.Thread(target=hilo_efectos, daemon=True).start()


    # ----------- BUCLE PRINCIPAL -----------
    while True:
        if not q_cmd.empty():
            cmd = q_cmd.get()

            if cmd["tipo"] == "SHUTDOWN":
                apagar["value"] = True
                time.sleep(0.1)

                for pin_led in leds.values():
                    GPIO.output(pin_led, GPIO.LOW)
                GPIO.output(buzzer, GPIO.LOW)

                GPIO.cleanup()
                return

            with lock:
                cola_efectos.append(cmd)

        time.sleep(0.001)



# ===========================================================
#   PROCESO B — JUEGO
# ===========================================================

def proceso_juego(q_cmd, q_evt, estado_juego):

    print("Pulsa cualquier botón para comenzar...")

    while True:
        if not q_evt.empty() and q_evt.get()["tipo"] == "BOTON":
            break
        time.sleep(0.01)

    print("Juego iniciado.")
    botones = ["BTN1", "BTN2", "BTN3", "BTN4"]

    while True:

        espera = random.uniform(2, 5)
        print(f"\nPreparado… {espera:.2f}s")
        time.sleep(espera)

        objetivo = random.choice(botones)
        print(f"¡PULSA AHORA! ({objetivo})")

        q_cmd.put({"tipo": "LED_ON", "boton": objetivo})
        q_cmd.put({"tipo": "BUZZ"})

        inicio = time.time()
        pulsado = None

        while pulsado is None:
            if not q_evt.empty():
                pulsado = q_evt.get()["valor"]

        fin = time.time()
        tiempo = round((fin - inicio) * 1000, 2)

        estado_juego["ultimo_tiempo"] = tiempo
        estado_juego["tiempos"].append(tiempo)

        q_cmd.put({"tipo": "LED_OFF", "boton": objetivo})

        if pulsado == objetivo:
            estado_juego["ultimo_resultado"] = "Correcto"
            print(f"✔ Correcto: {objetivo} en {tiempo} ms")
            time.sleep(1)

        else:
            estado_juego["ultimo_resultado"] = "Incorrecto"
            print(f"✘ Incorrecto: pulsaste {pulsado}, era {objetivo}")
            q_cmd.put({"tipo": "BUZZ_LONG"})
            estado_juego["fin_juego"] = True
            return



# ===========================================================
#   PROCESO C — WEB (con historial)
# ===========================================================

def proceso_web(estado_juego):

    import logging
    logging.getLogger('werkzeug').setLevel(logging.ERROR)

    from flask.cli import show_server_banner
    show_server_banner = lambda *args: None

    app = Flask(__name__)

    # ----------- PÁGINA PRINCIPAL -----------
    @app.route("/")
    def index():
        return f"""
        <h1>Juego de Reacción</h1>
        <p><b>Resultado:</b> {estado_juego['ultimo_resultado']}</p>
        <p><b>Tiempo:</b> {estado_juego['ultimo_tiempo']} ms</p>
        <p><b>Intentos:</b> {len(estado_juego['tiempos'])}</p>

        <br><br>
        <a href="/historial" style="font-size:22px;">📊 Ver historial de partidas</a>
        """

    # ----------- HISTORIAL COMPLETO DESDE LA BD -----------
    @app.route("/historial")
    def historial():
        conn = sqlite3.connect("/home/pi/raspBerryBase.db")
        cursor = conn.cursor()

        cursor.execute("SELECT fecha, media FROM tiempos ORDER BY id DESC")
        datos = cursor.fetchall()

        conn.close()

        tabla = "<h1>Historial de Partidas</h1><table border=1 cellpadding=8>"
        tabla += "<tr><th>Fecha</th><th>Media (ms)</th></tr>"

        for fila in datos:
            tabla += f"<tr><td>{fila[0]}</td><td>{fila[1]}</td></tr>"

        tabla += "</table><br><a href='/'><b>Volver</b></a>"

        return tabla

    app.run(host="0.0.0.0", port=8000, debug=False)



# ===========================================================
#   MAIN
# ===========================================================

if __name__ == "__main__":

    q_cmd = Queue()
    q_evt = Queue()

    manager = Manager()
    estado_juego = manager.dict()
    estado_juego["ultimo_tiempo"] = 0
    estado_juego["ultimo_resultado"] = "N/A"
    estado_juego["fin_juego"] = False
    estado_juego["tiempos"] = manager.list()

    pA = Process(target=proceso_hardware, args=(q_cmd, q_evt))
    pB = Process(target=proceso_juego, args=(q_cmd, q_evt, estado_juego))
    pC = Process(target=proceso_web,    args=(estado_juego,))

    pA.start()
    pB.start()
    pC.start()

    try:
        while True:
            time.sleep(0.1)
            if estado_juego["fin_juego"]:
                raise KeyboardInterrupt

    except KeyboardInterrupt:

        print("\n→ Calculando media final...")

        if len(estado_juego["tiempos"]) > 0:
            media = sum(estado_juego["tiempos"]) / len(estado_juego["tiempos"])
            print(f"→ Media: {media:.2f} ms")
            guardar_media_en_bd(media)
            print("→ Guardado en la base de datos de la Raspberry")

        print("→ Apagando hardware...")

        q_cmd.put({"tipo": "SHUTDOWN"})
        time.sleep(0.3)

        pA.terminate()
        pB.terminate()
        pC.terminate()

        print("Juego finalizado correctamente.")
