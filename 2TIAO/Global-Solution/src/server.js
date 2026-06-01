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

app.use(express.json());
app.use(express.static(PUBLIC_DIR));

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
