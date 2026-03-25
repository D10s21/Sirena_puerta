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

        let html = "";
        for (const [name, state] of Object.entries(data.signals || {})) {
            html += `<div class="mb-2"><b>${name}</b> &nbsp; ${badge(state)}</div>`;
        }
        document.getElementById("signals").innerHTML = html;
    } catch(e) {
        console.error("Error:", e);
    }
}

fetchStatus();
setInterval(fetchStatus, 2000);