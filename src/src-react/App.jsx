import React, { useState, useEffect } from 'react';
import { Smartphone, Monitor, Info, Bell, RefreshCw } from 'lucide-react';
import MapWidget from './components/MapWidget';
import TelemetryChart from './components/TelemetryChart';
import SatelliteCV from './components/SatelliteCV';
import CopilotChat from './components/CopilotChat';
import './style-react.css';

export default function App() {
  const [sensors, setSensors] = useState([]);
  const [selectedSensorId, setSelectedSensorId] = useState('ESP32_N01');
  const [viewMode, setViewMode] = useState('desktop'); // 'desktop' ou 'mobile'
  const [mobileTab, setMobileTab] = useState('map'); // 'map', 'satellite', 'chart', 'copilot'
  const [toasts, setToasts] = useState([]);
  const [activeEmergencySensors] = useState(new Set());

  // WebSocket Connection
  useEffect(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}`;
    const ws = new WebSocket(wsUrl);

    ws.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        if (payload.type === 'telemetry') {
          setSensors(payload.data);

          // Verificar novas emergências para Toasts
          payload.data.forEach(sensor => {
            const isEmergency = sensor.status_risco === 'EMERGENCY';
            if (isEmergency && !activeEmergencySensors.has(sensor.id_sensor)) {
              activeEmergencySensors.add(sensor.id_sensor);
              showToast(`🔥 EMERGÊNCIA RURAL: ${sensor.id_sensor} detectou pico de calor!`);
              setSelectedSensorId(sensor.id_sensor);
            } else if (!isEmergency && activeEmergencySensors.has(sensor.id_sensor)) {
              activeEmergencySensors.delete(sensor.id_sensor);
            }
          });
        }
      } catch (err) {}
    };

    ws.onclose = () => {
      // Reconectar em caso de queda
      setTimeout(() => {
        window.location.reload();
      }, 5000);
    };

    return () => ws.close();
  }, []);

  const showToast = (message) => {
    const id = Date.now();
    setToasts(prev => [...prev, { id, message }]);
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id));
    }, 4500);
  };

  const handleInjectFire = (sensorId) => {
    fetch('/api/trigger-fire', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id_sensor: sensorId })
    })
      .then(res => res.json())
      .then(() => {
        showToast(`Comando enviado para ${sensorId}`);
      });
  };

  const handleResetSimulation = () => {
    fetch('/api/reset-triggers', { method: 'POST' })
      .then(res => res.json())
      .then(() => {
        showToast('Simulador de incêndio resetado.');
      });
  };

  return (
    <div className={`app-container ${viewMode}-mode`}>
      <div className="stars-overlay"></div>

      {/* Header */}
      <header className="app-header">
        <div className="header-logo">
          <span className="logo-glow"></span>
          <h1>EcoGlow</h1>
          <span className="badge badge-accent">React PWA V2.0</span>
        </div>
        
        {/* Toggle de Visualização Mobile/Desktop */}
        <div className="view-toggle-controls">
          <button 
            onClick={() => setViewMode('desktop')} 
            className={`btn btn-secondary btn-sm ${viewMode === 'desktop' ? 'active-toggle' : ''}`}
            title="Visualização Desktop"
          >
            <Monitor size={14} /> Desktop
          </button>
          <button 
            onClick={() => setViewMode('mobile')} 
            className={`btn btn-secondary btn-sm ${viewMode === 'mobile' ? 'active-toggle' : ''}`}
            title="Simular Layout Mobile"
          >
            <Smartphone size={14} /> Mobile
          </button>
        </div>

        <div className="header-status">
          <div className="status-item desktop-only">
            <span className="status-dot online"></span>
            <span>Gateway LoRaWAN: Ativo</span>
          </div>
          <button onClick={handleResetSimulation} className="btn btn-secondary">Resetar Simulação</button>
        </div>
      </header>

      {/* Layout Principal */}
      {viewMode === 'desktop' ? (
        // VISUALIZAÇÃO DESKTOP (GRID INTEGRADO)
        <main className="app-grid">
          <section className="card grid-span-4" id="map-section">
            <div className="card-header">
              <h2>📍 Sensoriamento Terrestre (1.000 Hectares)</h2>
              <div className="card-actions">
                <span className="legend-item"><span className="legend-dot normal"></span> Normal</span>
                <span className="legend-item"><span class="legend-dot emergency"></span> Emergência (Edge)</span>
              </div>
            </div>
            <div className="card-body">
              <MapWidget sensors={sensors} onInjectFire={handleInjectFire} />
            </div>
          </section>

          <section className="card grid-span-2" id="satellite-section">
            <div className="card-body">
              <SatelliteCV />
            </div>
          </section>

          <section className="card grid-span-3" id="telemetry-section">
            <div className="card-header">
              <h2>📊 Histórico Microclimático da Fazenda</h2>
            </div>
            <div className="card-body">
              <TelemetryChart sensors={sensors} />
            </div>
          </section>

          <section className="card grid-span-3">
            <CopilotChat 
              sensors={sensors} 
              selectedSensorId={selectedSensorId} 
              onSelectSensor={setSelectedSensorId} 
            />
          </section>
        </main>
      ) : (
        // VISUALIZAÇÃO MOBILE (ABAS RESPONSIVAS DENTRO DE FRAME DE DISPOSITIVO)
        <div className="mobile-frame-container">
          <div className="mobile-phone-frame">
            <div className="mobile-phone-content">
              
              {/* Conteúdo da Aba Ativa */}
              <div className="mobile-active-tab-content" style={{ padding: '1rem', flex: 1, overflowY: 'auto' }}>
                {mobileTab === 'map' && (
                  <div className="card" style={{ height: '100%' }}>
                    <div className="card-header">
                      <h2>📍 Mapa de Sensores</h2>
                    </div>
                    <div className="card-body" style={{ minHeight: '300px' }}>
                      <MapWidget sensors={sensors} onInjectFire={handleInjectFire} />
                    </div>
                  </div>
                )}

                {mobileTab === 'satellite' && (
                  <div className="card" style={{ height: '100%' }}>
                    <div className="card-body">
                      <SatelliteCV />
                    </div>
                  </div>
                )}

                {mobileTab === 'chart' && (
                  <div className="card" style={{ height: '100%' }}>
                    <div className="card-header">
                      <h2>📊 Histórico de Sensores</h2>
                    </div>
                    <div className="card-body">
                      <TelemetryChart sensors={sensors} />
                    </div>
                  </div>
                )}

                {mobileTab === 'copilot' && (
                  <CopilotChat 
                    sensors={sensors} 
                    selectedSensorId={selectedSensorId} 
                    onSelectSensor={setSelectedSensorId} 
                  />
                )}
              </div>

              {/* Barra de Navegação Inferior (Mobile) */}
              <nav className="mobile-tab-navigation">
                <button 
                  onClick={() => setMobileTab('map')} 
                  className={`tab-item ${mobileTab === 'map' ? 'active-tab' : ''}`}
                >
                  📍<span>Mapa</span>
                </button>
                <button 
                  onClick={() => setMobileTab('satellite')} 
                  className={`tab-item ${mobileTab === 'satellite' ? 'active-tab' : ''}`}
                >
                  🛰️<span>Satélite</span>
                </button>
                <button 
                  onClick={() => setMobileTab('chart')} 
                  className={`tab-item ${mobileTab === 'chart' ? 'active-tab' : ''}`}
                >
                  📊<span>Gráficos</span>
                </button>
                <button 
                  onClick={() => setMobileTab('copilot')} 
                  className={`tab-item ${mobileTab === 'copilot' ? 'active-tab' : ''}`}
                >
                  🤖<span>Copilot</span>
                </button>
              </nav>
            </div>
          </div>
        </div>
      )}

      {/* Toasts Flutuantes */}
      <div className="toast-container">
        {toasts.map(t => (
          <div key={t.id} className="toast">
            {t.message}
          </div>
        ))}
      </div>
    </div>
  );
}
