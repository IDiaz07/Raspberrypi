import RPi.GPIO as GPIO
import time
import random

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

# ===== BOTONES =====
botones = {
    "BTN1": 25,
    "BTN2": 27,
    "BTN3": 17,
    "BTN4": 24
}

# ===== GND =====
gnd_pines = [23, 22, 16, 26]

# ===== LEDS =====
leds = {
    "BTN1": 14,
    "BTN2": 15,
    "BTN3": 18,
    "BTN4": 8
}

# ===== BUZZER =====
buzzer = 13

buzzer_gnd = 21
GPIO.setup(buzzer_gnd, GPIO.OUT)
GPIO.output(buzzer_gnd, GPIO.LOW)


# --- CONFIG ---
for gnd in gnd_pines:
    GPIO.setup(gnd, GPIO.OUT)
    GPIO.output(gnd, GPIO.LOW)

for pin in botones.values():
    GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

for pin in leds.values():
    GPIO.setup(pin, GPIO.OUT)
    GPIO.output(pin, GPIO.LOW)

GPIO.setup(buzzer, GPIO.OUT)
GPIO.output(buzzer, GPIO.LOW)

print("Sistema listo. Juego iniciado.")

# ===================
# ESPERAR PULSACIÓN
# ===================
def esperar_boton():
    while True:
        for nombre, pin in botones.items():
            if GPIO.input(pin) == GPIO.LOW:
                return nombre
        time.sleep(0.001)

# ===================
# BUCLE PRINCIPAL
# ===================
try:
    while True:

        # Elegir LED / botón objetivo
        objetivo = random.choice(list(leds.keys()))

        # Mostrar estímulo
        GPIO.output(leds[objetivo], True)
        GPIO.output(buzzer, True)
        time.sleep(0.15)
        GPIO.output(buzzer, False)

        inicio = time.time()

        # Esperar respuesta
        pulsado = esperar_boton()
        fin = time.time()

        # Apagar LED
        GPIO.output(leds[objetivo], False)

        # Calcular tiempo
        reaccion = (fin - inicio) * 1000

        if pulsado == objetivo:
            print(f"✔ Correcto: {objetivo} en {reaccion:.2f} ms")
            GPIO.output(leds[objetivo], True)
            time.sleep(0.3)
            GPIO.output(leds[objetivo], False)
        else:
            print(f"✘ Incorrecto: pulsaste {pulsado}, era {objetivo}")
            GPIO.output(buzzer, True)
            time.sleep(0.4)
            GPIO.output(buzzer, False)

        time.sleep(1)

except KeyboardInterrupt:
    print("\nJuego detenido")

finally:
    GPIO.cleanup()
