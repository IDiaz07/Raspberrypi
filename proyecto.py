import RPi.GPIO as GPIO
import time
import random
import threading
import sqlite3
from datetime import datetime
from multiprocessing import Process, Queue, Manager


def guardar_media_en_bd(media):
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
    cursor.execute(
        "INSERT INTO tiempos (fecha, media) VALUES (?, ?)",
        (fecha, media)
    )

    conn.commit()
    conn.close()


def proceso_hardware(q_cmd, q_evt):
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)

    botones = {"BTN1": 25, "BTN2": 27, "BTN3": 17, "BTN4": 24}
    leds = {"BTN1": 14, "BTN2": 15, "BTN3": 18, "BTN4": 8}
    buzzer = 13

    for pin in leds.values():
        GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, GPIO.LOW)

    for pin in botones.values():
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    GPIO.setup(buzzer, GPIO.OUT)
    GPIO.output(buzzer, GPIO.LOW)

    ultima = {b: 1 for b in botones}

    while True:
        for nombre, pin in botones.items():
            lectura = GPIO.input(pin)

            if lectura == GPIO.LOW and ultima[nombre]:
                q_evt.put(nombre)
                ultima[nombre] = 0

            if lectura == GPIO.HIGH:
                ultima[nombre] = 1

        if not q_cmd.empty():
            cmd = q_cmd.get()
            if cmd["tipo"] == "LED_ON":
                GPIO.output(leds[cmd["boton"]], True)
            elif cmd["tipo"] == "LED_OFF":
                GPIO.output(leds[cmd["boton"]], False)
            elif cmd["tipo"] == "BUZZ":
                GPIO.output(buzzer, True)
                time.sleep(0.2)
                GPIO.output(buzzer, False)
            elif cmd["tipo"] == "SHUTDOWN":
                GPIO.cleanup()
                return

        time.sleep(0.001)


def proceso_juego(q_cmd, q_evt, estado_juego):
    botones = ["BTN1", "BTN2", "BTN3", "BTN4"]

    print("Pulsa cualquier botón para comenzar")
    q_evt.get()

    while True:
        time.sleep(random.uniform(2, 4))
        objetivo = random.choice(botones)

        q_cmd.put({"tipo": "LED_ON", "boton": objetivo})
        q_cmd.put({"tipo": "BUZZ"})

        inicio = time.time()
        pulsado = q_evt.get()
        tiempo = round((time.time() - inicio) * 1000, 2)

        q_cmd.put({"tipo": "LED_OFF", "boton": objetivo})

        if pulsado == objetivo:
            estado_juego["ultimo_tiempo"] = tiempo
            estado_juego["tiempos"].append(tiempo)
            media_actual = sum(estado_juego["tiempos"]) / len(estado_juego["tiempos"])
            estado_juego["media_actual"] = round(media_actual, 2)

        else:
            if estado_juego["tiempos"]:
                media_final = sum(estado_juego["tiempos"]) / len(estado_juego["tiempos"])
                guardar_media_en_bd(media_final)
            q_cmd.put({"tipo": "SHUTDOWN"})
            estado_juego["fin_juego"] = True
            return


def proceso_web(estado_juego):
    from flask import Flask

    app = Flask(__name__)

    @app.route("/")
    def index():
        return f"""
        <h1>Juego de Reacción</h1>
        <p><b>Último tiempo:</b> {estado_juego['ultimo_tiempo']} ms</p>
        <p><b>Media partida:</b> {estado_juego['media_actual']} ms</p>
        <p><b>Aciertos:</b> {len(estado_juego['tiempos'])}</p>
        """

    app.run(host="0.0.0.0", port=8000, debug=False)


if __name__ == "__main__":
    q_cmd = Queue()
    q_evt = Queue()

    manager = Manager()
    estado_juego = manager.dict()
    estado_juego["ultimo_tiempo"] = 0
    estado_juego["media_actual"] = 0
    estado_juego["fin_juego"] = False
    estado_juego["tiempos"] = manager.list()

    pA = Process(target=proceso_hardware, args=(q_cmd, q_evt))
    pB = Process(target=proceso_juego, args=(q_cmd, q_evt, estado_juego))

    pA.start()
    pB.start()

    pB.join()
    pA.terminate()
