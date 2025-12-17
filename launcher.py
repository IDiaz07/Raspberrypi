from flask import Flask, render_template, redirect
import subprocess
import signal
import sqlite3
import os

app = Flask(__name__)

PROGRAMA = "/home/pi/web_juego/proyecto.py"
DB_PATH = "/home/pi/raspBerryBase.db"

proceso = None


@app.route("/")
def index():
    global proceso

    if proceso and proceso.poll() is not None:
        proceso = None

    estado = "En ejecución" if proceso else "Parado"

    return render_template(
        "index.html",
        estado=estado
    )


@app.route("/start")
def start():
    global proceso
    if not proceso:
        proceso = subprocess.Popen(
            ["sudo", "python3", PROGRAMA],
            preexec_fn=os.setsid
        )
    return redirect("/")


@app.route("/stop")
def stop():
    global proceso
    if proceso:
        proceso.send_signal(signal.SIGINT)
        proceso = None
    return redirect("/")


@app.route("/resultados")
def resultados():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT fecha, media FROM tiempos ORDER BY id DESC")
    datos = cursor.fetchall()
    conn.close()

    return render_template("resultados.html", datos=datos)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
