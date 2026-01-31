from flask import Flask, jsonify, request, render_template_string
from kiteconnect import KiteConnect
from datetime import datetime
import threading
import time

# ================= USER CONFIG =================
API_KEY = "oxc7tfxwa3n5zvqq"
ACCESS_TOKEN = "uX7tcUq6Akqm1P8r2vr2RCnXozMvxy2V"
EXPIRY = "26203"          # MANUAL
STRIKE_RANGE = 500       # ATM ±500
STRIKE_STEP = 50
FETCH_INTERVAL = 180     # 3 minutes
# ==============================================

app = Flask(__name__)

kite = KiteConnect(api_key=API_KEY)
kite.set_access_token(ACCESS_TOKEN)

symbols = {}     # { "25200CE": "NFO:NIFTY25JAN25200CE" }
oi_data = {}     # { "25200CE": [[time, oi], ...] }

# ================= STRIKE GENERATION =================
def generate_symbols():
    global symbols

    ltp = kite.ltp("NSE:NIFTY 50")["NSE:NIFTY 50"]["last_price"]
    atm = round(ltp / 50) * 50

    strikes = range(atm - STRIKE_RANGE, atm + STRIKE_RANGE + STRIKE_STEP, STRIKE_STEP)

    for strike in strikes:
        symbols[f"{strike}CE"] = f"NFO:NIFTY{EXPIRY}{strike}CE"
        symbols[f"{strike}PE"] = f"NFO:NIFTY{EXPIRY}{strike}PE"

    print(f"Generated {len(symbols)} NIFTY option symbols")

# ================= OI FETCH LOOP =================
def fetch_oi():
    while True:
        try:
            quotes = kite.quote(list(symbols.values()))
            now = datetime.now().strftime("%H:%M")

            for key, symbol in symbols.items():
                oi = quotes[symbol]["oi"]

                if key not in oi_data:
                    oi_data[key] = []

                oi_data[key].append([now, oi])

            print(f"OI updated @ {now}")

        except Exception as e:
            print("OI fetch error:", e)

        time.sleep(FETCH_INTERVAL)

# ================= FLASK ROUTES =================
@app.route("/")
def index():
    return render_template_string(HTML_PAGE)

@app.route("/strikes")
def strikes():
    return jsonify(sorted(symbols.keys()))

@app.route("/get_multi_oi", methods=["POST"])
def get_multi_oi():
    selected = request.json
    return jsonify({s: oi_data.get(s, []) for s in selected})

# ================= HTML + JS =================
HTML_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>NIFTY OI Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>

<body style="font-family: Arial; margin: 20px">

<h2>NIFTY Option OI — ATM ±500</h2>

<select id="strikes" multiple size="15" style="width:220px"></select>
<br><br>
<button onclick="loadOI()">Plot Selected Strikes</button>

<canvas id="oiChart" height="100"></canvas>

<script>
let chart;
let selectedStrikes = [];
const ctx = document.getElementById("oiChart").getContext("2d");

// Load strikes
fetch("/strikes")
.then(res => res.json())
.then(data => {
    const sel = document.getElementById("strikes");
    data.forEach(s => {
        const opt = document.createElement("option");
        opt.value = s;
        opt.text = s;
        sel.appendChild(opt);
    });
});

// Button click
function loadOI() {
    selectedStrikes = Array.from(
        document.getElementById("strikes").selectedOptions
    ).map(o => o.value);

    if (selectedStrikes.length === 0) {
        alert("Select at least one strike");
        return;
    }
    updateChart();
}

// 🔁 Auto update graph (NO HTML refresh)
function updateChart() {
    if (selectedStrikes.length === 0) return;

    fetch("/get_multi_oi", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(selectedStrikes)
    })
    .then(res => res.json())
    .then(data => {

        const labels = data[selectedStrikes[0]].map(x => x[0]);
        const datasets = [];

        Object.keys(data).forEach(strike => {
            datasets.push({
                label: strike,
                data: data[strike].map(x => x[1]),
                borderWidth: 2
            });
        });

        if (chart) chart.destroy();

        chart = new Chart(ctx, {
            type: "line",
            data: { labels, datasets },
            options: {
                responsive: true,
                animation: false,
                interaction: { mode: "index", intersect: false },
                plugins: {
                    legend: { position: "top" }
                }
            }
        });
    });
}

// ⏱️ Refresh every 3 minutes
setInterval(updateChart, 180000);
</script>

</body>
</html>
"""

# ================= MAIN =================
if __name__ == "__main__":
    generate_symbols()
    threading.Thread(target=fetch_oi, daemon=True).start()
    app.run(debug=False)
