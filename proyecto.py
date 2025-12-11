import RPi.GPIO as GPIO
import time
import random
import threading
from multiprocessing import Process, Queue, Manager
from flask import Flask


# ===========================================================
#   FUNCIÓN GLOBAL: APAGAR TODO (LEDs y buzzer)
# ===========================================================

def apagar_todo(led_pines, buzzer):
    """Apaga todos los LEDs y el buzzer."""
    for pin in led_pines.values():
        GPIO.output(pin, GPIO.LOW)
    GPIO.output(buzzer, GPIO.LOW)


# ===========================================================
#   PROCESO A — HARDWARE (2 HILOS)
# ===========================================================

def proceso_hardware(q_cmd, q_evt):

    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)

    botones = {"BTN1": 25, "BTN2": 27, "BTN3": 17, "BTN4": 24}
    leds    = {"BTN1": 14, "BTN2": 15, "BTN3": 18, "BTN4": 8}
    buzzer = 13
    gnd_pines = [23, 22, 16, 26]
    buzzer_gnd = 21

    # ---- CONFIGURACIÓN ----
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

    # ---- Estados para antirrebote ----
    ultima_lectura = {name: 1 for name in botones}

    # ---- Cola para efectos ----
    cola_efectos = []
    lock_efectos = threading.Lock()

    # ===========================================================
    # HILO 1: LECTOR DE BOTONES (ANTIRREBOTE REAL)
    # ===========================================================
    def hilo_botones():
        while True:
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

    # ===========================================================
    # HILO 2: EFECTOS (LEDs + BUZZER)
    # ===========================================================
    def hilo_efectos():
        while True:
            with lock_efectos:
                e = cola_efectos.pop(0) if cola_efectos else None

            if e:
                tipo = e["tipo"]

                if tipo == "LED_ON":
                    GPIO.output(leds[e["boton"]], True)

                elif tipo == "LED_OFF":
                    GPIO.output(leds[e["boton"]], False)

                elif tipo == "BUZZ":
                    GPIO.output(buzzer, True)
                    time.sleep(0.15)
                    GPIO.output(buzzer, False)

                elif tipo == "BUZZ_LONG":
                    GPIO.output(buzzer, True)
                    time.sleep(0.40)
                    GPIO.output(buzzer, False)

            time.sleep(0.001)

    # Lanzar hilos
    threading.Thread(target=hilo_botones, daemon=True).start()
    threading.Thread(target=hilo_efectos, daemon=True).start()

    # ---- BUCLE PRINCIPAL DEL HARDWARE ----
    while True:
        if not q_cmd.empty():
            with lock_efectos:
                cola_efectos.append(q_cmd.get())
        time.sleep(0.001)



# ===========================================================
#   PROCESO B — JUEGO
# ===========================================================

def proceso_juego(q_cmd, q_evt, estado_juego):

    print("Pulsa cualquier botón para comenzar...")

    # esperar primer botón
    while True:
        if not q_evt.empty():
            ev = q_evt.get()
            if ev["tipo"] == "BOTON":
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
                e = q_evt.get()
                if e["tipo"] == "BOTON":
                    pulsado = e["valor"]
            time.sleep(0.001)

        fin = time.time()
        tiempo = round((fin - inicio) * 1000, 2)

        q_cmd.put({"tipo": "LED_OFF", "boton": objetivo})

        estado_juego["ultimo_tiempo"] = tiempo

        if pulsado == objetivo:
            estado_juego["ultimo_resultado"] = "Correcto"
        else:
            estado_juego["ultimo_resultado"] = "Incorrecto"
            q_cmd.put({"tipo": "BUZZ_LONG"})

        print(f"Resultado: {estado_juego['ultimo_resultado']} ({tiempo} ms)")
        time.sleep(1)



# ===========================================================
#   PROCESO C — WEB (SIN LOGS, SIN WARNINGS, SIN BANNER)
# ===========================================================

def proceso_web(estado_juego):

    # ---- ELIMINAR TODOS LOS LOGS DE FLASK ----
    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)

    # ---- OCULTAR BANNER DEL SERVIDOR ----
    from flask.cli import show_server_banner
    show_server_banner = lambda *args: None

    app = Flask(__name__)

    @app.route("/")
    def index():
        return f"""
        <h1>Juego de Reacción</h1>
        <p><b>Resultado:</b> {estado_juego['ultimo_resultado']}</p>
        <p><b>Tiempo:</b> {estado_juego['ultimo_tiempo']} ms</p>
        """

    app.run(host="0.0.0.0", port=8000, debug=False)



# ===========================================================
#   MAIN (arranca los 3 procesos)
# ===========================================================

if __name__ == "__main__":

    q_cmd = Queue()
    q_evt = Queue()

    manager = Manager()
    estado_juego = manager.dict()
    estado_juego["ultimo_tiempo"] = 0
    estado_juego["ultimo_resultado"] = "N/A"

    # Pines para apagado al salir
    leds_info = {"BTN1": 14, "BTN2": 15, "BTN3": 18, "BTN4": 8}
    buzzer_pin = 13

    pA = Process(target=proceso_hardware, args=(q_cmd, q_evt))
    pB = Process(target=proceso_juego, args=(q_cmd, q_evt, estado_juego))
    pC = Process(target=proceso_web,    args=(estado_juego,))

    pA.start()
    pB.start()
    pC.start()

    try:
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nApagando LEDs y cerrando procesos...")

        GPIO.setmode(GPIO.BCM)
        apagar_todo(leds_info, buzzer_pin)

        pA.terminate()
        pB.terminate()
        pC.terminate()

        GPIO.cleanup()
        print("Todo apagado correctamente.")
