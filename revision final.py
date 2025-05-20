import tkinter as tk
import requests
import math
import threading
import time
import pygame
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# === CONFIGURACIÓN ===
pico_ip = "192.168.1.83"
zona_muerta = 0.5
umbral_mov = 0.7
ultimo_comando = None
mover_activo = False
distancia_actual = 100
datos_temperatura = []
datos_humedad = []
timestamplist = []



# === FUNCIONES CONTROL CARRO ===
def enviar_comando(comando):
    global ultimo_comando
    if comando != ultimo_comando:
        try:
            url = f"http://{pico_ip}/{comando}"
            response = requests.get(url)
            if response.status_code == 200:
                print(f"Comando {comando} enviado con éxito")
            else:
                print(f"Error al enviar {comando}: {response.status_code}")
        except Exception as e:
            print(f"Error de conexión: {e}")
        ultimo_comando = comando

def manejar_tecla(event):
    
    tecla = event.keysym.lower()
    if tecla == "w":
        enviar_comando("adelante")
    elif tecla == "s":
        enviar_comando("atras")
    elif tecla == "a":
        enviar_comando("girar_izquierda")
    elif tecla == "d":
        enviar_comando("girar_derecha")
    elif tecla == "space":
        enviar_comando("detener")

# === FUNCIONES SERVO ===
def mover_servo(angulo):
    try:
        url = f"http://{pico_ip}/mover?angulo={int(angulo)}"
        requests.get(url)
    except Exception as e:
        print(f"Error al mover el servo: {e}")

def barrido_servo():
    global mover_activo
    mover_activo = True
    while mover_activo:
        for angulo in range(0, 181, 10):
            mover_servo(angulo)
            actualizar_slider_visual(angulo)
            time.sleep(0.5)
            if not mover_activo: return
        for angulo in range(180, -1, -10):
            mover_servo(angulo)
            actualizar_slider_visual(angulo)
            time.sleep(0.5)
            if not mover_activo: return

def iniciar_barrido():
    global mover_activo
    if not mover_activo:  # Evitar crear el hilo si ya está activo
        hilo = threading.Thread(target=barrido_servo)
        hilo.daemon = True
        hilo.start()

def detener_barrido():
    global mover_activo
    mover_activo = False

def resetear_angulo():
    mover_servo(90)
    actualizar_slider_visual(90)
    label_angulo.config(text="Ángulo: 90°")

# === GAMEPAD ===
def leer_gamepad():
    pygame.init()
    pygame.joystick.init()
    if pygame.joystick.get_count() == 0:
        print("No se detectó ningún gamepad.")
        return
    joystick = pygame.joystick.Joystick(0)
    joystick.init()
    angulo_servo = 90

    time.sleep(1)  # Esperar a que se estabilice el estado de botones
    barrido_activo = False  # Bandera para evitar reinicios múltiples

    while True:
        pygame.event.pump()
        x_axis = joystick.get_axis(0)
        y_axis = joystick.get_axis(1)
        servo_axis = joystick.get_axis(3)
        comando = "ninguno"


        if abs(x_axis) < zona_muerta and abs(y_axis) < zona_muerta:
            comando = "detener"
        elif abs(y_axis) > abs(x_axis):
            comando = "adelante" if y_axis < -umbral_mov else "atras"
        else:
            comando = "girar_derecha" if x_axis > umbral_mov else "girar_izquierda"

        if joystick.get_button(0):  # Cuadrado → detener
            comando = "detener"
        enviar_comando(comando)

        # Control del servo con joystick derecho
        if abs(servo_axis) > 0.1:
            angulo_servo -= servo_axis * 5
            angulo_servo = max(0, min(180, angulo_servo))
            mover_servo(angulo_servo)
            actualizar_slider_visual(angulo_servo)

        # Control del barrido (evita reiniciar si ya está activo)
        if joystick.get_button(3) and not barrido_activo:  # Triángulo → iniciar
            iniciar_barrido()
            barrido_activo = True
        if joystick.get_button(2):  # Cuadrado → detener
            detener_barrido()
            barrido_activo = False
        if joystick.get_button(1):  # Círculo → resetear
            resetear_angulo()

        time.sleep(0.1)


# === SENSOR Y GRAFICA ===
def actualizar_sensores():
    global distancia_actual
    try:
        # Leer sensor DHT (Temperatura y Humedad)
        r1 = requests.get(f"http://{pico_ip}/sensor", timeout=3)
        if r1.ok:
            datos = r1.json()
            temperatura = datos['temperature']
            humedad = max(0, datos["humidity"] - 5)

            # Limitar la humedad al rango [0, 100]
            humedad = max(0, min(100, humedad))  # Limitar humedad entre 0 y 100
            print(f"Humedad recibida: {humedad}")  # Agregar log para ver el valor real

            label_temp.config(text=f"Temperatura: {temperatura} °C")
            label_hum.config(text=f"Humedad: {humedad} %")

            # Guardar los datos en las listas
            datos_temperatura.append(temperatura)
            datos_humedad.append(humedad)
            timestamplist.append(time.strftime("%H:%M:%S"))

            # Actualizar la gráfica
            ax.clear()
            ax.plot(timestamplist[-20:], datos_temperatura[-20:], label="Temp (°C)")
            ax.plot(timestamplist[-20:], datos_humedad[-20:], label="Humedad (%)")
            ax.set_title("Sensor DHT")
            ax.set_xlabel("Hora")
            ax.set_ylabel("Valor")
            ax.legend()
            ax.grid(True)
            canvas_grafica.draw()

        # Leer sensor ultrasónico
        r2 = requests.get(f"http://{pico_ip}/ultrasonico", timeout=5)
        if r2.ok:
            datos = r2.json()
            distancia_actual = datos['distancia']
            label_distancia.config(text=f"Distancia: {distancia_actual} cm")

        if distancia_actual is not None and 1 < distancia_actual < 15:
            if ultimo_comando != "detener":
                enviar_comando("detener")
            label_alerta.config(text="¡Obstáculo detectado!")
            time.sleep(0.1)
            root.after(2000, actualizar_sensores)
            return
        
        label_alerta.config(text="Sin Obstáculos")  # Limpia alerta si no hay obstáculo
        root.after(2000, actualizar_sensores)

    except Exception as e:
        print(f"Error al leer sensores: {e}")
        root.after(2000, actualizar_sensores)  # Reintentar después de 2 segundos


# === INTERFAZ TKINTER ===
root = tk.Tk()
root.title("Control del Carrito con Sensores")
root.geometry("1400x900")
root.configure(bg="#242323")

# Estructura
frame_izq = tk.Frame(root, bg="#242323")
frame_izq.pack(side="left", fill="y", padx=10, pady=10)
frame_der = tk.Frame(root, bg="#242323")
frame_der.pack(side="right", fill="both", expand=True, padx=10, pady=10)

# Botones
tk.Button(frame_izq, text="Iniciar", bg="#0B5ED7", fg="white",
          font=("Minecraft Dungeons", 14), width=20, command=lambda: print("Iniciado")).pack(pady=5)
tk.Button(frame_izq, text="Detener", bg="#DC3545", fg="white",
          font=("Minecraft Dungeons", 14), width=20, command=lambda: print("Detenido")).pack(pady=5)
tk.Button(frame_izq, text="Exportar a Excel", bg="#28A745", fg="white",
          font=("Minecraft Dungeons", 14), width=20, command=lambda: pd.DataFrame({
              "Tiempo": timestamplist,
              "Temperatura": datos_temperatura,
              "Humedad": datos_humedad
          }).to_excel("lecturas.xlsx", index=False)).pack(pady=5)
# Botones adicionales para el control del servomotor
tk.Button(frame_izq, text="Iniciar Barrido", bg="#FF9900", fg="white", 
          font=("Minecraft Dungeons", 14), width=20, command=iniciar_barrido).pack(pady=5)
tk.Button(frame_izq, text="Detener Barrido", bg="#FF0000", fg="white", 
          font=("Minecraft Dungeons", 14), width=20, command=detener_barrido).pack(pady=5)
tk.Button(frame_izq, text="Resetear Ángulo", bg="#28A745", fg="white", 
          font=("Minecraft Dungeons", 14), width=20, command=resetear_angulo).pack(pady=5)
# Cerrar correctamente
def cerrar():
    global mover_activo
    mover_activo = False
    mover_servo(90)
    root.quit()
    root.destroy()

# Botón para cerrar la aplicación
tk.Button(frame_izq, text="Cerrar", bg="#DC3545", fg="white", 
          font=("Minecraft Dungeons", 14), width=20, command = cerrar).pack(pady=5)


# Etiquetas
label_temp = tk.Label(frame_izq, text="Temperatura: -- °C", font=("Arial", 14), bg="#f0f0f0")
label_temp.pack(pady=5)
label_hum = tk.Label(frame_izq, text="Humedad: -- %", font=("Arial", 14), bg="#f0f0f0")
label_hum.pack(pady=5)
label_distancia = tk.Label(frame_izq, text="Distancia: -- cm", font=("Arial", 14))
label_distancia.pack(pady=5)
label_alerta = tk.Label(frame_izq, text="", font=("Arial", 12), fg="red")
label_alerta.pack()

# Gráfica
frame_grafica = tk.Frame(frame_der, bg="#242323")
frame_grafica.pack(fill="both", expand=True)
fig, ax = plt.subplots(figsize=(7, 4), dpi=100)
canvas_grafica = FigureCanvasTkAgg(fig, master=frame_grafica)
canvas_grafica.draw()
canvas_grafica.get_tk_widget().pack(fill="both", expand=True)

# Slider circular visual
canvas = tk.Canvas(frame_izq, width=250, height=250, bg="#dddddd")
canvas.pack(pady=10)
centro_x, centro_y, radio = 125, 125, 100
radio_marcador = 8
canvas.create_oval(centro_x - radio, centro_y - radio, centro_x + radio, centro_y + radio)
brazo = canvas.create_line(centro_x, centro_y, centro_x, centro_y - (radio - 50), width=3, fill="blue")
marcador = canvas.create_oval(centro_x - radio_marcador, centro_y - radio,
                              centro_x + radio_marcador, centro_y - radio, fill="red")
label_angulo = tk.Label(frame_izq, text="Ángulo: 90°", font=("Arial", 14), bg="#dddddd")
label_angulo.pack()
canvas.bind("<B1-Motion>", lambda e: actualizar_angulo(e))

def actualizar_angulo(event):
    x, y = event.x - centro_x, centro_y - event.y
    angulo = math.degrees(math.atan2(y, x))
    if angulo < 0: angulo += 360
    if 0 <= angulo <= 180:
        actualizar_slider_visual(angulo)
        mover_servo(angulo)

def actualizar_slider_visual(angulo):
    marcador_x = centro_x + radio * math.cos(math.radians(angulo))
    marcador_y = centro_y - radio * math.sin(math.radians(angulo))
    canvas.coords(marcador, marcador_x - radio_marcador, marcador_y - radio_marcador,
                             marcador_x + radio_marcador, marcador_y + radio_marcador)
    brazo_x = centro_x + (radio - 50) * math.cos(math.radians(angulo))
    brazo_y = centro_y - (radio - 50) * math.sin(math.radians(angulo))
    canvas.coords(brazo, centro_x, centro_y, brazo_x, brazo_y)
    label_angulo.config(text=f"Ángulo: {int(angulo)}°")


root.protocol("WM_DELETE_WINDOW", cerrar)
root.bind("<KeyPress>", manejar_tecla)
root.focus_set()

# Lanzar hilos
threading.Thread(target=leer_gamepad, daemon=True).start()
actualizar_sensores()
root.mainloop()