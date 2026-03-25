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
# CONSULTAR SENSOR (ESP32 #1)
# ============================================================

async def get_remote_signals(sensor_ip):
    try:
        reader, writer = await uasyncio.wait_for(
            uasyncio.open_connection(sensor_ip, 80), timeout=3)
        writer.write(b"GET /signals HTTP/1.0\r\nHost: sensor\r\n\r\n")
        await writer.drain()
        response = b""
        while True:
            chunk = await uasyncio.wait_for(reader.read(256), timeout=3)
            if not chunk: break
            response += chunk
        
        writer.close()
        await writer.wait_closed() # LÍNEA VITAL: Libera el socket al sistema operativo
        
        body = response.decode().split("\r\n\r\n")[-1]
        return json.loads(body)
    except Exception as e:
        print("Error sensor:", e)
        return None

# ============================================================
# REGLAS
# ============================================================

async def execute_action(action, pins):
    if "pulseOn" in action:
        ms = action.get("param", 100)
        for name in action["pulseOn"]:
            if name in pins:
                print("pulseOn {} → {}ms".format(name, ms))
                pins[name]["pin"].on()
                await uasyncio.sleep_ms(ms)
                pins[name]["pin"].off()
    elif "off" in action:
        for name in action["off"]:
            if name in pins:
                print("off →", name)
                pins[name]["pin"].off()
    elif "on" in action:
        for name in action["on"]:
            if name in pins:
                print("on →", name)
                pins[name]["pin"].on()

async def apply_rules(rules, remote_signals, pins, rule_state):
    now = time.ticks_ms()
    for i, rule in enumerate(rules):
        cond, action = rule[0], rule[1]

        # Detectar si la regla pide evaluar un estado ON u OFF
        if "off" in cond:
            name = cond["off"][0]
            target_state = "OFF"
            param_ms = cond.get("param", 0)
        elif "on" in cond:
            name = cond["on"][0]
            target_state = "ON"
            param_ms = cond.get("param", 0)
        else:
            continue

        # Obtener el estado real del sensor remoto
        state = remote_signals.get(name, "OFF" if target_state == "ON" else "ON")

        # Evaluar la regla con soporte de tiempo universal
        if state == target_state:
            if rule_state[i]["since"] is None:
                rule_state[i]["since"] = now
                rule_state[i]["done"] = False
            
            elapsed = time.ticks_diff(now, rule_state[i]["since"])
            
            # Si pasó el tiempo requerido y no se ha ejecutado aún
            if elapsed >= param_ms and not rule_state[i]["done"]:
                await execute_action(action, pins)
                rule_state[i]["done"] = True
        else:
            # Si el estado cambia (ej. se cierra la puerta), reiniciar cronómetro
            rule_state[i]["since"] = None
            rule_state[i]["done"] = False

async def sensor_task(sensor_ip, rules, pins, rule_state, shared):
    while True:
        data = await get_remote_signals(sensor_ip)
        if data is not None:
            shared["remote"] = data
            await apply_rules(rules, data, pins, rule_state)
        await uasyncio.sleep_ms(500)

# ============================================================
# SERVIDOR HTTP
# ============================================================

def send_response(writer, code, ctype, body):
    status = {200: "OK", 404: "Not Found"}.get(code, "OK")
    header = "HTTP/1.1 {} {}\r\nContent-Type: {}\r\nAccess-Control-Allow-Origin: *\r\nConnection: close\r\n\r\n".format(
        code, status, ctype)
    writer.write(header.encode() + (body.encode() if isinstance(body, str) else body))

async def handle(reader, writer, pins, cfg, rule_state, shared):
    try:
        req  = (await reader.read(1024)).decode()
        path = req.split(" ")[1] if " " in req else "/"

        if path in ("/", "/index.html"):
            send_response(writer, 200, "text/html", INDEX_HTML) # Usar RAM
        elif path == "/app.js":
            send_response(writer, 200, "application/javascript", APP_JS) # Usar RAM
        elif path == "/signals":
            send_response(writer, 200, "application/json", json.dumps(get_states(pins)))
        elif path == "/status":
            rules_info = []
            for i, rule in enumerate(cfg["rules"]):
                rules_info.append({
                    "condition": rule[0],
                    "action":    rule[1],
                    "since":     rule_state[i]["since"],
                    "done":      rule_state[i]["done"]
                })
            data = {
                "app":     cfg["app"],
                "version": cfg["version"],
                "signals": get_states(pins),
                "sensor":  shared.get("remote", {}),
                "rules":   rules_info
            }
            send_response(writer, 200, "application/json", json.dumps(data))
        else:
            send_response(writer, 404, "text/plain", "Not found")
    except Exception as e:
        print("Error cliente:", e)
    finally:
        await writer.drain()
        writer.close()
        await writer.wait_closed() # LÍNEA VITAL: Evita la fuga de memoria al cargar panel web

# ============================================================
# MAIN
# ============================================================

async def main():
    import secrets
    cfg        = load_json("config.json")
    ip         = connect_wifi(secrets.WIFI_SSID, secrets.WIFI_PASSWORD)
    sensor_ip  = cfg["sensor_ip"]
    pins       = init_pins(cfg["signals"])
    rules      = cfg["rules"]
    rule_state = [{"since": None, "done": False} for _ in rules]
    shared     = {"remote": {}}

    await uasyncio.start_server(
        lambda r, w: handle(r, w, pins, cfg, rule_state, shared), "0.0.0.0", 80)

    uasyncio.create_task(sensor_task(sensor_ip, rules, pins, rule_state, shared))

    print("ESP32 #2 listo → http://{}".format(ip))
    while True:
        await uasyncio.sleep(1)

uasyncio.run(main())