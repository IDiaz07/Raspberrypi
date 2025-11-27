import RPi.GPIO as GPIO
import time

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

# Configuración botones (PIN SEÑAL)
botones = {
    "BTN1": 25,
    "BTN2": 27,
    "BTN3": 17,
    "BTN4": 24
}

# Pines GND asociados
gnd_pines = [23, 22, 16, 26]

# Configurar GNDs como salida en bajo
for gnd in gnd_pines:
    GPIO.setup(gnd, GPIO.OUT)
    GPIO.output(gnd, GPIO.LOW)

# Configurar botones como entradas con pull-up
for nombre, pin in botones.items():
    GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

print("=== PRUEBA DE BOTONES ===")
print("Presiona cualquier botón...\n")

try:
    while True:
        for nombre, pin in botones.items():
            if GPIO.input(pin) == GPIO.LOW:
                print(f"{nombre} PRESIONADO")
                time.sleep(0.3)  # anti-rebote simple
        time.sleep(0.05)

except KeyboardInterrupt:
    print("\nPrograma finalizado")

finally:
    GPIO.cleanup()
