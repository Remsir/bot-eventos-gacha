from flask import Flask
from threading import Thread

app = Flask(__name__)  # Usar __name__ es más estándar


@app.route("/")
def home():
    return "Estoy vivo!"


def run():
    app.run(host="0.0.0.0", port=8080,
            debug=False)  # debug=False evita reinicios innecesarios


def iniciar_web():
    thread = Thread(target=run)
    thread.daemon = True  # 🔧 Hace que no bloquee el cierre del programa
    thread.start()