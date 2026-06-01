import time
import json
import random
import os
import sys

# Diretórios e arquivos
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
TELEMETRY_FILE = os.path.join(DATA_DIR, "sensors_telemetry.json")
TRIGGER_FILE = os.path.join(DATA_DIR, "fire_trigger.json")

# Garantir existência do diretório data
os.makedirs(DATA_DIR, exist_ok=True)

# Coordenada central da fazenda (interior de SP - região agrícola de Ribeirão Preto)
LAT_CENTRO = -21.1775
LON_CENTRO = -47.8103

# Inicializar os 30 sensores em grid inteligente (5x6)
sensors = []
id_counter = 1
for r in range(5):
    for c in range(6):
        # Pequeno offset geográfico para espalhar os sensores em ~1000 hectares
        lat = LAT_CENTRO + (r * 0.008) - 0.016
        lon = LON_CENTRO + (c * 0.008) - 0.020
        sensors.append({
            "id_sensor": f"ESP32_N{id_counter:02d}",
            "latitude": round(lat, 6),
            "longitude": round(lon, 6),
            "temperature": round(random.uniform(22.0, 31.0), 1),
            "humidity": round(random.uniform(40.0, 65.0), 1),
            "soil_moisture": round(random.uniform(45.0, 70.0), 1),
            "status_risco": "OK",
            "transmission_interval": 10, # segundos (padrão)
            "last_update": time.time()
        })
        id_counter += 1

print(f"Simulador IoT iniciado com {len(sensors)} sensores terrestres georreferenciados.")

def evaluate_edge_computing(sensor):
    """
    Simula o processamento local (Edge Computing) no ESP32.
    Caso a temperatura cruze o limiar de 48 graus e a umidade do ar caia abaixo de 15%,
    o sensor muda seu status para EMERGENCY e reduz o intervalo de transmissão para 1s.
    """
    if sensor["temperature"] >= 48.0 and sensor["humidity"] <= 15.0:
        sensor["status_risco"] = "EMERGENCY"
        sensor["transmission_interval"] = 1 # Transmissão acelerada em tempo real
    else:
        sensor["status_risco"] = "OK"
        sensor["transmission_interval"] = 10 # Intervalo normal de baixo consumo

try:
    while True:
        # Verificar se existe algum gatilho de fogo injetado pelo dashboard/usuário
        active_triggers = []
        if os.path.exists(TRIGGER_FILE):
            try:
                with open(TRIGGER_FILE, "r") as f:
                    trigger_data = json.load(f)
                    if isinstance(trigger_data, list):
                        active_triggers = trigger_data
                    elif isinstance(trigger_data, dict):
                        active_triggers = [trigger_data.get("id_sensor")]
            except Exception as e:
                pass

        # Atualizar dados dos sensores
        current_time = time.time()
        for sensor in sensors:
            # Se o sensor estiver com fogo injetado (emergência simulada)
            if sensor["id_sensor"] in active_triggers:
                sensor["temperature"] = round(random.uniform(52.0, 68.0), 1)
                sensor["humidity"] = round(random.uniform(8.0, 14.9), 1)
                sensor["soil_moisture"] = round(random.uniform(5.0, 12.0), 1)
            else:
                # Variação natural do clima
                sensor["temperature"] = round(sensor["temperature"] + random.uniform(-0.4, 0.4), 1)
                sensor["humidity"] = round(sensor["humidity"] + random.uniform(-0.5, 0.5), 1)
                sensor["soil_moisture"] = round(sensor["soil_moisture"] + random.uniform(-0.3, 0.3), 1)

                # Manter limites realistas do clima normal
                sensor["temperature"] = max(18.0, min(sensor["temperature"], 38.0))
                sensor["humidity"] = max(30.0, min(sensor["humidity"], 85.0))
                sensor["soil_moisture"] = max(30.0, min(sensor["soil_moisture"], 90.0))

            # Executar Edge Computing
            evaluate_edge_computing(sensor)
            sensor["last_update"] = round(current_time)

        # Salvar telemetria atualizada em JSON
        with open(TELEMETRY_FILE, "w") as f:
            json.dump(sensors, f, indent=2)

        # Se houver algum sensor em emergência, acelerar o loop de simulação
        has_emergency = any(s["status_risco"] == "EMERGENCY" for s in sensors)
        sleep_time = 1 if has_emergency else 2
        time.sleep(sleep_time)

except KeyboardInterrupt:
    print("\nSimulador IoT finalizado.")
