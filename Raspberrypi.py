import RPi.GPIO as GPIO
import time
import random

GPIO.setmode(GPIO.BCM)

# Pines de botones (solo 4)
btn1 = 26
btn2 = 25
btn3 = 23
btn4 = 24

botones = [btn1, btn2, btn3, btn4]

# Pines para LED y buzzer
led = 5
buzzer = 6

# Configuración botones con pull-up
for b in botones:
    GPIO.setup(b, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# LED y buzzer
GPIO.setup(led, GPIO.OUT)
GPIO.setup(buzzer, GPIO.OUT)

print("Sistema listo. Se mostrarán estímulos cada pocos segundos.")


def esperar_pulsacion():
    """Devuelve qué botón se pulsa."""
    while True:
        for b in botones:
            if GPIO.input(b) == GPIO.LOW:
                return b
        time.sleep(0.001)


try:
    while True:

        # Espera aleatoria antes del estímulo
        tiempo_aleatorio = random.uniform(2, 5)
        time.sleep(tiempo_aleatorio)

        # Estímulo
        GPIO.output(led, True)
        GPIO.output(buzzer, True)
        time.sleep(0.15)
        GPIO.output(buzzer, False)

        inicio = time.time()

        # Esperar a que el usuario pulse un botón
        boton_pulsado = esperar_pulsacion()
        fin = time.time()

        # Apagar LED
        GPIO.output(led, False)

        # Calcular tiempo de reacción
        reaccion_ms = (fin - inicio) * 1000

        print(f"Tiempo de reacción: {reaccion_ms:.2f} ms (botón GPIO {boton_pulsado})")

        time.sleep(1)

except KeyboardInterrupt:
    print("\nPrograma detenido.")

finally:
    GPIO.cleanup()
