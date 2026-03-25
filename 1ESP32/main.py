import network, json, time, uasyncio
from machine import Pin

# ============================================================
# UTILIDADES
# ============================================================

def load_file(path):
    with open(path) as f:
        return f.read()

def load_json(path):
    with open(path) as f:
        return json.load(f)

# PRE-CARGA DE ARCHIVOS WEB EN RAM (Corrección de velocidad/memoria)
try:
    INDEX_HTML = load_file("www/index.html")
    APP_JS = load_file("www/app.js")
except:
    INDEX_HTML = "<html><body><h1>Error cargando index.html</h1></body></html>"
    APP_JS = ""

# ============================================================
# WIFI
# ============================================================

def connect_wifi(ssid, password):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    
    # Forzar IP Estática para que el ESP32 #2 siempre lo encuentre
    wlan.ifconfig(('192.207.110.202', '255.255.255.0', '192.207.110.1', '8.8.8.8')) 
    
    if not wlan.isconnected():
        wlan.connect(ssid, password)
        print("Conectando", end="")
        for _ in range(20):
            if wlan.isconnected(): break
            time.sleep(1)
            print(".", end="")
    if wlan.isconnected():
        ip = wlan.ifconfig()[0]
        print("\nConectado! IP:", ip)
        return ip
    raise Exception("WiFi fallido")

# ============================================================
# PINES
# ============================================================

def init_pins(signals):
    pins = {}
    for name, (num, direction) in signals.items():
        p = Pin(num, Pin.IN, Pin.PULL_UP) if direction == "IN" else Pin(num, Pin.OUT)
        if direction == "OUT": p.off()
        pins[name] = {"pin": p, "dir": direction}
        print("Pin {} → GPIO{} {}".format(name, num, direction))
    return pins

def get_states(pins):
    return {name: ("ON" if d["pin"].value() else "OFF") for name, d in pins.items()}

# ============================================================
# SERVIDOR HTTP
# ============================================================

def send_response(writer, code, ctype, body):
    status = {200: "OK", 404: "Not Found"}.get(code, "OK")
    header = "HTTP/1.1 {} {}\r\nContent-Type: {}\r\nAccess-Control-Allow-Origin: *\r\nConnection: close\r\n\r\n".format(
        code, status, ctype)
    writer.write(header.encode() + (body.encode() if isinstance(body, str) else body))

async def handle(reader, writer, pins, cfg):
    try:
        req  = (await reader.read(1024)).decode()
        path = req.split(" ")[1] if " " in req else "/"

        if path in ("/", "/index.html"):
            send_response(writer, 200, "text/html", INDEX_HTML) # Usar variable en RAM
        elif path == "/app.js":
            send_response(writer, 200, "application/javascript", APP_JS) # Usar variable en RAM
        elif path == "/signals":
            send_response(writer, 200, "application/json", json.dumps(get_states(pins)))
        elif path == "/status":
            data = {"app": cfg["app"], "version": cfg["version"], "signals": get_states(pins)}
            send_response(writer, 200, "application/json", json.dumps(data))
        else:
            send_response(writer, 404, "text/plain", "Not found")
    except Exception as e:
        print("Error cliente:", e)
    finally:
        await writer.drain()
        writer.close()
        await writer.wait_closed()  # LÍNEA VITAL: Evita la fuga de memoria y cuelgues

# ============================================================
# MAIN
# ============================================================

async def main():
    import secrets
    cfg  = load_json("config.json")
    ip   = connect_wifi(secrets.WIFI_SSID, secrets.WIFI_PASSWORD)
    pins = init_pins(cfg["signals"])

    await uasyncio.start_server(lambda r, w: handle(r, w, pins, cfg), "0.0.0.0", 80)
    print("ESP32 #1 listo → http://{}".format(ip))

    while True:
        await uasyncio.sleep(1)

uasyncio.run(main())