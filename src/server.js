const express = require('express');
const http = require('http');
const WebSocket = require('ws');
const path = require('path');
const fs = require('fs');
const { exec } = require('child_process');

const app = express();
const server = http.createServer(app);
const wss = new WebSocket.Server({ server });

const PORT = process.env.PORT || 3000;
const PUBLIC_DIR = path.join(__dirname, 'public');
const DATA_DIR = path.join(__dirname, '..', 'data');
const TELEMETRY_FILE = path.join(DATA_DIR, 'sensors_telemetry.json');
const TRIGGER_FILE = path.join(DATA_DIR, 'fire_trigger.json');
const DETECTION_FILE = path.join(DATA_DIR, 'satellite_detections.json');
const NEWS_FILE = path.join(DATA_DIR, 'satelite_data.json');

// Utilizar o Python virtual env se existir, caso contrário usar python3 global
const PYTHON_PATH = fs.existsSync(path.join(__dirname, '..', 'venv', 'bin', 'python3'))
  ? path.join(__dirname, '..', 'venv', 'bin', 'python3')
  : 'python3';

const DIST_DIR = path.join(__dirname, 'dist');

// Raio (km) para considerar que uma detecção orbital e um sensor de solo apontam
// para o MESMO evento. ~2 km cobre a imprecisão do mapeamento pixel->GPS e o
// espaçamento da malha de sensores (~0.8 km entre nós).
const RECONCILE_RADIUS_KM = 2.0;

// Distância de Haversine entre dois pontos geográficos, em km.
function haversineKm(lat1, lon1, lat2, lon2) {
  const R = 6371; // raio da Terra (km)
  const toRad = (d) => (d * Math.PI) / 180;
  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(a));
}

function readJsonSafe(file) {
  try {
    if (fs.existsSync(file)) return JSON.parse(fs.readFileSync(file, 'utf8'));
  } catch (e) { /* leitura concorrente: ignorar tick */ }
  return [];
}

/**
 * RECONCILIAÇÃO DE DUAS ESCALAS (o "pulo do gato" do EcoGlow).
 * Cruza geograficamente as detecções de Visão Computacional (macro/orbital) com a
 * telemetria dos sensores de solo (micro). Quando uma detecção orbital coincide
 * espacialmente com um sensor em EMERGENCY, o alerta é consolidado no nível MÁXIMO.
 */
function reconcileAlerts() {
  const sensors = readJsonSafe(TELEMETRY_FILE);
  const detections = readJsonSafe(DETECTION_FILE);
  const emergencySensors = sensors.filter((s) => s.status_risco === 'EMERGENCY');

  const alerts = [];

  // 1) Cruzamento orbital x solo
  detections.forEach((det) => {
    let nearest = null;
    let nearestKm = Infinity;
    emergencySensors.forEach((s) => {
      const km = haversineKm(det.latitude, det.longitude, s.latitude, s.longitude);
      if (km < nearestKm) { nearestKm = km; nearest = s; }
    });

    if (nearest && nearestKm <= RECONCILE_RADIUS_KM) {
      alerts.push({
        nivel: 'MAXIMO',
        tipo: 'RECONCILIADO',
        motivo: 'Satélite e sensor de solo confirmam anomalia térmica na mesma área.',
        latitude: nearest.latitude,
        longitude: nearest.longitude,
        distancia_km: Number(nearestKm.toFixed(3)),
        sensor_id: nearest.id_sensor,
        deteccao_id: det.id_deteccao,
        sensor_temp: nearest.temperature,
        area_afetada_px: det.area_afetada_px,
        copilot_acionado: true,
      });
    } else {
      alerts.push({
        nivel: 'ATENCAO',
        tipo: 'ORBITAL',
        motivo: 'Foco detectado por satélite sem confirmação de sensor de solo próximo.',
        latitude: det.latitude,
        longitude: det.longitude,
        deteccao_id: det.id_deteccao,
        area_afetada_px: det.area_afetada_px,
        copilot_acionado: false,
      });
    }
  });

  // 2) Sensores em emergência ainda não confirmados por satélite
  emergencySensors.forEach((s) => {
    const jaReconciliado = alerts.some(
      (a) => a.tipo === 'RECONCILIADO' && a.sensor_id === s.id_sensor
    );
    if (!jaReconciliado) {
      alerts.push({
        nivel: 'ALTO',
        tipo: 'SOLO',
        motivo: 'Sensor de solo em EMERGENCY aguardando confirmação orbital.',
        latitude: s.latitude,
        longitude: s.longitude,
        sensor_id: s.id_sensor,
        sensor_temp: s.temperature,
        copilot_acionado: false,
      });
    }
  });

  const nivelMaximo = alerts.some((a) => a.nivel === 'MAXIMO');
  return {
    nivel_geral: nivelMaximo ? 'MAXIMO'
      : alerts.some((a) => a.nivel === 'ALTO') ? 'ALTO'
      : alerts.length ? 'ATENCAO' : 'NORMAL',
    raio_reconciliacao_km: RECONCILE_RADIUS_KM,
    total_alertas: alerts.length,
    alertas: alerts,
    timestamp: Date.now(),
  };
}

app.use(express.json());
// Servir arquivos do build do React (/dist) se existirem, caso contrário servir a pasta legada /public
if (fs.existsSync(DIST_DIR)) {
  app.use(express.static(DIST_DIR));
} else {
  app.use(express.static(PUBLIC_DIR));
}

// Rota específica para servir a imagem dinâmica processada por OpenCV
app.get('/processed_satellite.jpg', (req, res) => {
  const customPublicPath = path.join(PUBLIC_DIR, 'processed_satellite.jpg');
  const customDistPath = path.join(DIST_DIR, 'processed_satellite.jpg');
  
  if (fs.existsSync(customDistPath)) {
    return res.sendFile(customDistPath);
  } else if (fs.existsSync(customPublicPath)) {
    return res.sendFile(customPublicPath);
  }
  return res.status(404).send('Imagem não processada ainda.');
});

// Endpoint: Telemetria atualizada dos 30 sensores
app.get('/api/telemetry', (req, res) => {
  if (fs.existsSync(TELEMETRY_FILE)) {
    const data = fs.readFileSync(TELEMETRY_FILE, 'utf8');
    return res.json(JSON.parse(data));
  }
  return res.json([]);
});

// Endpoint: Notícias/Alertas cósmicos do satélite raspados
app.get('/api/satellites', (req, res) => {
  if (fs.existsSync(NEWS_FILE)) {
    const data = fs.readFileSync(NEWS_FILE, 'utf8');
    return res.json(JSON.parse(data));
  }
  return res.json([]);
});

// Endpoint: Detecções de Visão Computacional Orbital
app.get('/api/detections', (req, res) => {
  if (fs.existsSync(DETECTION_FILE)) {
    const data = fs.readFileSync(DETECTION_FILE, 'utf8');
    return res.json(JSON.parse(data));
  }
  return res.json([]);
});

// Endpoint: Reconciliação de duas escalas (satélite x sensor de solo)
app.get('/api/reconciliation', (req, res) => {
  return res.json(reconcileAlerts());
});

// Endpoint: Injetar simulador de emergência/incêndio em nós
app.post('/api/trigger-fire', (req, res) => {
  const { id_sensor } = req.body;
  if (!id_sensor) return res.status(400).json({ error: 'id_sensor é obrigatório' });

  let triggers = [];
  if (fs.existsSync(TRIGGER_FILE)) {
    try {
      triggers = JSON.parse(fs.readFileSync(TRIGGER_FILE, 'utf8'));
      if (!Array.isArray(triggers)) triggers = [];
    } catch (e) {
      triggers = [];
    }
  }
  
  if (!triggers.includes(id_sensor)) {
    triggers.push(id_sensor);
  }
  
  fs.writeFileSync(TRIGGER_FILE, JSON.stringify(triggers, null, 2));
  return res.json({ success: true, active_triggers: triggers });
});

// Endpoint: Resetar simulador de emergência/incêndio
app.post('/api/reset-triggers', (req, res) => {
  if (fs.existsSync(TRIGGER_FILE)) {
    fs.unlinkSync(TRIGGER_FILE);
  }
  return res.json({ success: true });
});

// Endpoint: Executar Scraping
app.post('/api/run-scraper', (req, res) => {
  const scriptPath = path.join(__dirname, 'news_scraper.py');
  exec(`"${PYTHON_PATH}" "${scriptPath}"`, (error, stdout, stderr) => {
    if (error) {
      console.error(`Erro no Scraper: ${error.message}`);
      return res.status(500).json({ error: error.message });
    }
    return res.json({ success: true, output: stdout });
  });
});

// Endpoint: Executar Visão Computacional Orbital
app.post('/api/run-cv', (req, res) => {
  const scriptPath = path.join(__dirname, 'vision_satellite.py');
  exec(`"${PYTHON_PATH}" "${scriptPath}"`, (error, stdout, stderr) => {
    if (error) {
      console.error(`Erro no OpenCV Satellite: ${error.message}`);
      return res.status(500).json({ error: error.message });
    }
    return res.json({ success: true, output: stdout });
  });
});

// Endpoint: Consultar Copilot RAG
app.post('/api/copilot', (req, res) => {
  const { query, sensorId, windDirection } = req.body;
  const scriptPath = path.join(__dirname, 'rag_contingency.py');
  
  // Tratar argumentos para o terminal de forma segura
  const safeQuery = query ? query.replace(/"/g, '\\"') : "Ajuda de contingência";
  const safeSensorId = sensorId || "ESP32_N01";
  const safeWind = windDirection || "Leste";

  exec(`"${PYTHON_PATH}" "${scriptPath}" "${safeQuery}" "${safeSensorId}" "${safeWind}"`, (error, stdout, stderr) => {
    if (error) {
      console.error(`Erro no RAG: ${error.message}`);
      return res.status(500).json({ error: error.message });
    }
    return res.json({ answer: stdout });
  });
});

// Transmissão de telemetria por WebSockets
wss.on('connection', (ws) => {
  console.log('Cliente conectado ao WebSocket do EcoGlow.');
  
  const interval = setInterval(() => {
    if (fs.existsSync(TELEMETRY_FILE)) {
      try {
        const data = fs.readFileSync(TELEMETRY_FILE, 'utf8');
        ws.send(JSON.stringify({ type: 'telemetry', data: JSON.parse(data) }));
        // Empurra também o estado de reconciliação de duas escalas a cada tick
        ws.send(JSON.stringify({ type: 'reconciliation', data: reconcileAlerts() }));
      } catch (e) {
        // Ignorar conflitos temporários de leitura concorrente
      }
    }
  }, 1000);

  ws.on('close', () => {
    clearInterval(interval);
    console.log('Cliente desconectado.');
  });
});

// Iniciar servidor Node.js
server.listen(PORT, () => {
  console.log(`Servidor EcoGlow rodando na porta ${PORT}`);
  console.log(`Caminho Python utilizado: ${PYTHON_PATH}`);
  
  // Rodar primeira carga dos scripts para popular dados
  exec(`"${PYTHON_PATH}" "${path.join(__dirname, 'news_scraper.py')}"`);
  exec(`"${PYTHON_PATH}" "${path.join(__dirname, 'vision_satellite.py')}"`);
});
