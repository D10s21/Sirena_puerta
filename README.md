# 🔔 Sistema de Alarma Inalámbrico con ESP32

[![MicroPython](https://img.shields.io/badge/MicroPython-1.20%2B-blue?logo=python)](https://micropython.org/)
[![ESP32](https://img.shields.io/badge/Hardware-ESP32-red)](https://www.espressif.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Sistema de alarma distribuido basado en dos placas **ESP32** que se comunican entre sí a través de Wi-Fi local. Un ESP32 monitoriza un sensor de apertura (puerta/ventana) y el otro gestiona la lógica de alarma y controla la sirena.

---

## 📐 Arquitectura del Sistema

```
                      RED Wi-Fi LOCAL
                           │
         ┌─────────────────┴─────────────────┐
         │                                   │
  ┌──────▼──────┐   GET /signals (500ms)  ┌──▼────────────┐
  │  ESP32 #1   │ ◄─────────────────────► │   ESP32 #2    │
  │   SENSOR    │  {"SEN": "ON"/"OFF"}    │   SIRENA      │
  │             │                         │               │
  │ Pin 13 ←──[🚪Sensor magnético]        │ Pin 33 ──►[🔔Sirena]
  │             │                         │ Pin 32 ──►[AUX]
  │ IP Estática │                         │ IP Dinámica   │
  │ Panel Web ✅│                         │ Panel Web ✅  │
  └─────────────┘                         └───────────────┘
```

La comunicación usa una arquitectura **Cliente-Servidor HTTP** con `uasyncio`, lo que permite que ambos ESP32 sirvan su panel web y gestionen la lógica de alarma de forma completamente asíncrona y no bloqueante.

---

## ⚙️ Lógica de Funcionamiento

El comportamiento de la alarma se define enteramente en el `config.json` del **ESP32 #2**, sin necesidad de modificar el código fuente.

> **Convención del sensor:**
> `ON` = Puerta **abierta** · `OFF` = Puerta **cerrada**

| Tiempo puerta abierta | Evento |
|---|---|
| 0 – 9 segundos | Puerta abierta. Cronómetro iniciado. |
| 10 segundos | ⚠️ Pulso de advertencia (100 ms) |
| 15 segundos | ⚠️ Segundo pulso de advertencia (100 ms) |
| 20 segundos | 🚨 Sirena continua activada |
| Puerta cerrada | ✅ Sirena apagada. Cronómetros reiniciados. |

---

## 📂 Estructura de Archivos

```
ESP32 #1 (Sensor)            ESP32 #2 (Sirena)
├── secrets.py               ├── secrets.py
├── config.json              ├── config.json
├── main.py                  ├── main.py
└── www/                     └── www/
    ├── index.html                ├── index.html
    └── app.js                    └── app.js
```

---

## 🔌 Hardware

### ESP32 #1 — Sensor

| Pin | Modo | Descripción |
|-----|------|-------------|
| GPIO 13 | IN | Sensor magnético de puerta/ventana (Pull-Up interno) |

### ESP32 #2 — Sirena

| Pin | Modo | Descripción |
|-----|------|-------------|
| GPIO 33 | OUT | Control de sirena |
| GPIO 32 | OUT | Salida auxiliar (AUXOUT) |

> ⚠️ **Importante:** Los pines del ESP32 trabajan a **3.3V**. Para activar una sirena de 5V o superior, usa un módulo de relé, optoacoplador o transistor (MOSFET / TIP120) en el pin 33 para proteger la placa.

---

## 🚀 Instalación

### 1. Requisitos previos

- MicroPython 1.20+ instalado en ambas placas ESP32
- [Thonny IDE](https://thonny.org/) para subir los archivos

### 2. Configurar credenciales Wi-Fi

Crea `secrets.py` en **ambas** placas:

```python
WIFI_SSID     = "TU_NOMBRE_DE_RED"
WIFI_PASSWORD = "TU_CONTRASEÑA"
```

### 3. Configurar IP del sensor

El **ESP32 #1** usa IP estática `192.207.110.202`. Asegúrate de que esté disponible en tu red o cámbiala en `main.py`.

Actualiza el `config.json` del **ESP32 #2** con esa IP:

```json
"sensor_ip": "192.207.110.202"
```

### 4. Subir archivos con Thonny

Para cada ESP32, sube los archivos respetando la estructura de directorios:

```
Raíz del dispositivo
├── secrets.py
├── config.json
├── main.py
└── www/
    ├── index.html
    └── app.js
```

> ⚠️ La carpeta `www/` debe crearse manualmente en Thonny antes de subir `index.html` y `app.js`.

### 5. Arrancar y verificar

Al iniciar, cada ESP32 imprime su IP en la consola. Abre un navegador en la misma red y accede al panel de cada dispositivo:

```
http://192.207.110.202   ← ESP32 #1 (Sensor)
http://<IP_DHCP>         ← ESP32 #2 (Sirena)
```

---

## 📡 API HTTP

Ambos ESP32 exponen los siguientes endpoints:

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/` | GET | Panel de control web |
| `/status` | GET | Estado completo en JSON |
| `/signals` | GET | Estado de señales en JSON |

### Ejemplo de respuesta `/signals`

```json
{"SEN": "ON"}
```

### Ejemplo de respuesta `/status` (ESP32 #2)

```json
{
  "app": "LABORATORIO_SIRENA",
  "version": "1.0",
  "signals": {"SIREN": "OFF", "AUXOUT": "OFF"},
  "sensor":  {"SEN": "ON"},
  "rules": [
    {"condition": {"off": ["SEN"], "param": 10000}, "action": {"pulseOn": ["SIREN"], "param": 100}, "done": false}
  ]
}
```

---

## 🛠️ Detalles Técnicos

- **Asincronía total:** Tanto el servidor web como el motor de reglas corren en el mismo bucle `uasyncio`, sin bloqueos entre sí.
- **Archivos web en RAM:** `index.html` y `app.js` se cargan en memoria RAM al arrancar para evitar lecturas constantes a la flash y lograr respuestas HTTP más rápidas.
- **Cierre seguro de sockets:** Se usa `await writer.wait_closed()` tras cada petición para liberar correctamente los descriptores de red y prevenir fugas de memoria en sesiones largas.
- **Motor de reglas configurable:** Toda la lógica de tiempos y actuaciones se define en `config.json`, sin modificar el código fuente.

---

## 📝 Configuración de Reglas (`config.json`)

Las reglas siguen el formato `[condición, acción]`. Condiciones disponibles:

| Clave | Parámetro | Descripción |
|-------|-----------|-------------|
| `"on"` | — | Se cumple cuando la señal está activa |
| `"off"` | `"param": ms` | Se cumple cuando la señal lleva X ms inactiva |

Acciones disponibles:

| Clave | Parámetro | Descripción |
|-------|-----------|-------------|
| `"on"` | — | Activa la señal |
| `"off"` | — | Desactiva la señal |
| `"pulseOn"` | `"param": ms` | Pulso activo durante X milisegundos |

---

## 📄 Licencia

Distribuido bajo la licencia **MIT**. Consulta el archivo [LICENSE](LICENSE) para más detalles.
