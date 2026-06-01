// Configuração Inicial do Mapa Leaflet
const LAT_CENTRO = -21.1775;
const LON_CENTRO = -47.8103;

const map = L.map('map').setView([LAT_CENTRO, LON_CENTRO], 14);

// Camada de satélite oficial gratuita (Esri World Imagery) para visual de mapa premium
L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
    attribution: 'Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community'
}).addTo(map);

// Referências DOM
const runCvBtn = document.getElementById('runCvBtn');
const satelliteImg = document.getElementById('satelliteImage');
const detectionsList = document.getElementById('detectionsList');
const copilotSensorSelect = document.getElementById('copilotSensorSelect');
const copilotWindSelect = document.getElementById('copilotWindSelect');
const chatForm = document.getElementById('chatForm');
const queryInput = document.getElementById('queryInput');
const chatMessages = document.getElementById('chatMessages');
const resetBtn = document.getElementById('resetSimulationBtn');
const toastContainer = document.getElementById('toastContainer');

// Estrutura de dados globais
let sensorMarkers = {};
let activeEmergencySensors = new Set();
let chartInstance = null;

// Inicializar Gráficos Chart.js
function initCharts() {
    const ctx = document.getElementById('telemetryChart').getContext('2d');
    chartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [], // Timestamps
            datasets: [
                {
                    label: 'Temp Média (°C)',
                    data: [],
                    borderColor: '#ff007f',
                    backgroundColor: 'rgba(255, 0, 127, 0.1)',
                    borderWidth: 2,
                    tension: 0.3
                },
                {
                    label: 'Umidade Média (%)',
                    data: [],
                    borderColor: '#00f0ff',
                    backgroundColor: 'rgba(0, 240, 255, 0.1)',
                    borderWidth: 2,
                    tension: 0.3
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: {
                    grid: { color: 'rgba(255,255,255,0.05)' },
                    ticks: { color: '#a0aec0', font: { size: 9 } }
                },
                y: {
                    grid: { color: 'rgba(255,255,255,0.05)' },
                    ticks: { color: '#a0aec0' }
                }
            },
            plugins: {
                legend: { labels: { color: '#f0f4f8' } }
            }
        }
    });
}

// Atualizar estatísticas e históricos do gráfico
function updateChartData(sensors) {
    if (!chartInstance) return;
    
    // Calcular médias atuais
    const sumTemp = sensors.reduce((acc, s) => acc + s.temperature, 0);
    const sumHum = sensors.reduce((acc, s) => acc + s.humidity, 0);
    const avgTemp = (sumTemp / sensors.length).toFixed(1);
    const avgHum = (sumHum / sensors.length).toFixed(1);
    
    const now = new Date().toLocaleTimeString();
    
    // Adicionar aos dados
    chartInstance.data.labels.push(now);
    chartInstance.data.datasets[0].data.push(avgTemp);
    chartInstance.data.datasets[1].data.push(avgHum);
    
    // Limitar histórico a 15 pontos no gráfico
    if (chartInstance.data.labels.length > 15) {
        chartInstance.data.labels.shift();
        chartInstance.data.datasets[0].data.shift();
        chartInstance.data.datasets[1].data.shift();
    }
    
    chartInstance.update('none'); // Update silent
}

// Injetar Popups e Marcadores do Mapa
function updateMapMarkers(sensors) {
    // Carregar opções do dropdown do Copilot uma vez
    if (copilotSensorSelect.options.length <= 1) {
        copilotSensorSelect.innerHTML = '';
        sensors.forEach(s => {
            const opt = document.createElement('option');
            opt.value = s.id_sensor;
            opt.textContent = `${s.id_sensor} (Lat ${s.latitude})`;
            copilotSensorSelect.appendChild(opt);
        });
    }

    sensors.forEach(sensor => {
        const isEmergency = sensor.status_risco === 'EMERGENCY';
        const iconClass = isEmergency ? 'sensor-emergency' : 'sensor-normal';
        
        // Criar ícone circular personalizado com o ID do sensor
        const icon = L.divIcon({
            className: `custom-sensor-icon ${iconClass}`,
            html: `<div>${sensor.id_sensor.split('_N')[1]}</div>`,
            iconSize: [22, 22]
        });

        const popupContent = `
            <div class="map-popup">
                <h3>🛰️ ESP32: ${sensor.id_sensor}</h3>
                <p><b>Temp:</b> ${sensor.temperature}°C</p>
                <p><b>Umidade Ar:</b> ${sensor.humidity}%</p>
                <p><b>Umidade Solo:</b> ${sensor.soil_moisture}%</p>
                <p><b>Status:</b> <span class="badge ${isEmergency ? 'badge-accent' : ''}">${sensor.status_risco}</span></p>
                <button class="btn btn-accent btn-sm" style="margin-top:0.5rem;width:100%;" onclick="injectFire('${sensor.id_sensor}')">Injetar Incêndio</button>
            </div>
        `;

        if (sensorMarkers[sensor.id_sensor]) {
            // Atualizar existente
            sensorMarkers[sensor.id_sensor].setLatLng([sensor.latitude, sensor.longitude]);
            sensorMarkers[sensor.id_sensor].setIcon(icon);
            sensorMarkers[sensor.id_sensor].setPopupContent(popupContent);
        } else {
            // Criar novo
            const marker = L.marker([sensor.latitude, sensor.longitude], { icon }).addTo(map);
            marker.bindPopup(popupContent);
            sensorMarkers[sensor.id_sensor] = marker;
        }

        // Sistema de notificação (Toast) para novas emergências
        if (isEmergency && !activeEmergencySensors.has(sensor.id_sensor)) {
            activeEmergencySensors.add(sensor.id_sensor);
            showToast(`🔥 EMERGÊNCIA RURAL: ${sensor.id_sensor} detectou pico de calor!`);
            
            // Focar mapa no sensor afetado
            map.panTo([sensor.latitude, sensor.longitude]);
            
            // Alterar seletor do Copilot automaticamente
            copilotSensorSelect.value = sensor.id_sensor;
        } else if (!isEmergency && activeEmergencySensors.has(sensor.id_sensor)) {
            activeEmergencySensors.delete(sensor.id_sensor);
        }
    });
}

// Injetar Incêndio
window.injectFire = function(sensorId) {
    fetch('/api/trigger-fire', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id_sensor: sensorId })
    })
    .then(res => res.json())
    .then(data => {
        showToast(`Comando enviado para ${sensorId}`);
        map.closePopup();
    });
};

// Exibir Toasts/Alertas
function showToast(message) {
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.textContent = message;
    toastContainer.appendChild(toast);
    setTimeout(() => {
        toast.remove();
    }, 4500);
}

// Conectar ao WebSocket do servidor para atualização contínua em tempo real
function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(`${protocol}//${window.location.host}`);
    
    ws.onmessage = (event) => {
        const payload = JSON.parse(event.data);
        if (payload.type === 'telemetry') {
            updateMapMarkers(payload.data);
            updateChartData(payload.data);
        }
    };

    ws.onclose = () => {
        setTimeout(connectWebSocket, 2000); // Reconexão automática se cair
    };
}

// Carregar detecções do satélite obtidas via OpenCV
function loadSatelliteDetections() {
    fetch('/api/detections')
        .then(res => res.json())
        .then(data => {
            detectionsList.innerHTML = '';
            if (data.length === 0) {
                detectionsList.innerHTML = '<p class="placeholder-text">Nenhum foco de incêndio detectado orbitalmente.</p>';
                return;
            }
            data.forEach(det => {
                const item = document.createElement('div');
                item.className = 'detection-item';
                item.innerHTML = `
                    💥 <b class="text-danger">[ALERT] ${det.id_deteccao}</b><br>
                    Coordenadas: ${det.latitude}, ${det.longitude}<br>
                    Foco: ${det.area_afetada_px}px² | Risco: ${det.criticidade}
                `;
                detectionsList.appendChild(item);
            });
        });
}

// Botão para re-processar imagem de satélite
runCvBtn.addEventListener('click', () => {
    runCvBtn.textContent = 'Processando...';
    runCvBtn.disabled = true;
    
    fetch('/api/run-cv', { method: 'POST' })
        .then(res => res.json())
        .then(data => {
            // Recarregar imagem do satélite forçando bypass de cache
            satelliteImg.src = 'processed_satellite.jpg?t=' + new Date().getTime();
            loadSatelliteDetections();
            showToast('🛰️ Visão Computacional Orbital atualizada!');
            runCvBtn.textContent = 'Processar Imagem';
            runCvBtn.disabled = false;
        })
        .catch(err => {
            showToast('Erro ao executar Visão Computacional.');
            runCvBtn.textContent = 'Processar Imagem';
            runCvBtn.disabled = false;
        });
});

// Formulário Copilot RAG Chat
chatForm.addEventListener('submit', (e) => {
    e.preventDefault();
    const query = queryInput.value.trim();
    if (!query) return;
    
    // Renderizar mensagem do usuário
    appendMessage(query, 'user');
    queryInput.value = '';

    // Enviar dados
    fetch('/api/copilot', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            query: query,
            sensorId: copilotSensorSelect.value,
            windDirection: copilotWindSelect.value
        })
    })
    .then(res => res.json())
    .then(data => {
        appendMessage(data.answer, 'assistant');
    })
    .catch(() => {
        appendMessage('Erro ao obter plano de contingência do Copilot.', 'system');
    });
});

function appendMessage(text, sender) {
    const msg = document.createElement('div');
    msg.className = `message ${sender}-message`;
    
    // Converter Markdown simplificado para HTML
    let formattedText = text
        .replace(/\n/g, '<br>')
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        .replace(/👉 (.*?)/g, '👉 <strong>$1</strong>');
        
    msg.innerHTML = formattedText;
    chatMessages.appendChild(msg);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Botão Resetar Simulação
resetBtn.addEventListener('click', () => {
    fetch('/api/reset-triggers', { method: 'POST' })
        .then(res => res.json())
        .then(() => {
            showToast('Simulador de incêndio resetado.');
        });
});

// Inicialização
window.addEventListener('DOMContentLoaded', () => {
    initCharts();
    connectWebSocket();
    loadSatelliteDetections();
});
