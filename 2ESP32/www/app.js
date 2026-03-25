function badge(state) {
    return state === "ON"
        ? '<span class="badge bg-success fs-6">ON</span>'
        : '<span class="badge bg-danger  fs-6">OFF</span>';
}

async function fetchStatus() {
    try {
        const data = await fetch("/status").then(r => r.json());
        document.getElementById("appName").textContent    = data.app;
        document.getElementById("appVersion").textContent = "v" + data.version;

        // Señales locales
        let sh = "";
        for (const [name, state] of Object.entries(data.signals || {})) {
            sh += `<div class="mb-2"><b>${name}</b> &nbsp; ${badge(state)}</div>`;
        }
        document.getElementById("signals").innerHTML = sh || "<p class='text-muted'>Sin señales</p>";

        // Sensor remoto
        let ss = "";
        for (const [name, state] of Object.entries(data.sensor || {})) {
            ss += `<div class="mb-2"><b>${name}</b> &nbsp; ${badge(state)}</div>`;
        }
        document.getElementById("sensorSignals").innerHTML = ss || "<p class='text-muted'>Sin datos</p>";

        // Reglas
        let rh = "";
        (data.rules || []).forEach((rule, i) => {
            const icon  = rule.done ? "✅" : "⏳";
            const cond  = JSON.stringify(rule.condition);
            const act   = JSON.stringify(rule.action);
            rh += `<div class="mb-1 small">${icon} <code>${cond} → ${act}</code></div>`;
        });
        document.getElementById("rules").innerHTML = rh || "<p class='text-muted'>Sin reglas</p>";

    } catch(e) {
        console.error("Error:", e);
    }
}

fetchStatus();
setInterval(fetchStatus, 2000);