import React, { useState, useEffect } from 'react';
import { ShieldAlert, RefreshCw } from 'lucide-react';

export default function SatelliteCV() {
  const [detections, setDetections] = useState([]);
  const [imgTimestamp, setImgTimestamp] = useState(Date.now());
  const [isLoading, setIsLoading] = useState(false);

  const loadDetections = () => {
    fetch('/api/detections')
      .then(res => res.json())
      .then(data => setDetections(data))
      .catch(() => {});
  };

  useEffect(() => {
    loadDetections();
  }, []);

  const handleRunCV = () => {
    setIsLoading(true);
    fetch('/api/run-cv', { method: 'POST' })
      .then(res => res.json())
      .then(() => {
        setImgTimestamp(Date.now());
        loadDetections();
      })
      .finally(() => {
        setIsLoading(false);
      });
  };

  return (
    <div className="satellite-body" style={{ display: 'flex', flexDirection: 'column', gap: '1rem', height: '100%' }}>
      <div className="card-header" style={{ padding: '0 0 0.75rem 0', borderBottom: '1px solid rgba(255, 255, 255, 0.08)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2>🛰️ Visão Computacional Orbital</h2>
        <button onClick={handleRunCV} className="btn btn-primary btn-sm" disabled={isLoading} style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
          <RefreshCw size={14} className={isLoading ? 'spin-animation' : ''} />
          {isLoading ? 'Processando...' : 'Processar Imagem'}
        </button>
      </div>
      <div className="image-container" style={{ position: 'relative', height: '200px', borderRadius: '8px', overflow: 'hidden', border: '1px solid rgba(255, 255, 255, 0.1)' }}>
        <img id="satelliteImage" src={`/processed_satellite.jpg?t=${imgTimestamp}`} alt="Visão Orbital Processada" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
        <div className="scan-overlay"></div>
      </div>
      <div className="detection-list" style={{ background: 'rgba(0, 0, 0, 0.25)', borderRadius: '6px', padding: '0.75rem', fontFamily: 'var(--font-mono)', fontSize: '0.8rem', height: '130px', overflowY: 'auto' }}>
        {detections.length === 0 ? (
          <p className="placeholder-text">Nenhum foco de incêndio detectado orbitalmente.</p>
        ) : (
          detections.map(det => (
            <div key={det.id_deteccao} className="detection-item" style={{ marginBottom: '0.5rem', borderBottom: '1px dashed rgba(255, 255, 255, 0.1)', paddingBottom: '0.25rem' }}>
              <ShieldAlert size={12} className="text-danger" style={{ display: 'inline', marginRight: '4px', verticalAlign: 'middle' }} />
              <b className="text-danger">[ALERT] {det.id_deteccao}</b><br />
              Coordenadas: {det.latitude}, {det.longitude}<br />
              Foco: {det.area_afetada_px}px² | Risco: {det.criticidade}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
