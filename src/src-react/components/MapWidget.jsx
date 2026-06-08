import React, { useEffect, useRef } from 'react';

export default function MapWidget({ sensors, onInjectFire }) {
  const mapContainerRef = useRef(null);
  const mapRef = useRef(null);
  const markersRef = useRef({});

  useEffect(() => {
    // Inicializar mapa se o Leaflet estiver disponível globalmente e o mapa ainda não foi criado
    if (window.L && !mapRef.current && mapContainerRef.current) {
      const LAT_CENTRO = -21.1775;
      const LON_CENTRO = -47.8103;

      const mapInstance = window.L.map(mapContainerRef.current).setView([LAT_CENTRO, LON_CENTRO], 14);

      window.L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
        attribution: 'Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS'
      }).addTo(mapInstance);

      mapRef.current = mapInstance;
    }

    return () => {
      // Opcional: não destruir para manter persistência de navegação ao alternar tabs
    };
  }, []);

  useEffect(() => {
    if (!mapRef.current || !window.L) return;

    sensors.forEach(sensor => {
      const isEmergency = sensor.status_risco === 'EMERGENCY';
      const iconClass = isEmergency ? 'sensor-emergency' : 'sensor-normal';
      
      const icon = window.L.divIcon({
        className: `custom-sensor-icon ${iconClass}`,
        html: `<div>${sensor.id_sensor.split('_N')[1]}</div>`,
        iconSize: [22, 22]
      });

      const popupId = `popup-btn-${sensor.id_sensor}`;
      const popupContent = `
        <div class="map-popup">
          <h3>🛰️ ESP32: ${sensor.id_sensor}</h3>
          <p><b>Temp:</b> ${sensor.temperature}°C</p>
          <p><b>Umidade Ar:</b> ${sensor.humidity}%</p>
          <p><b>Umidade Solo:</b> ${sensor.soil_moisture}%</p>
          <p><b>Status:</b> <span class="badge ${isEmergency ? 'badge-accent' : ''}">${sensor.status_risco}</span></p>
          <button id="${popupId}" class="btn btn-accent btn-sm" style="margin-top:0.5rem;width:100%;">Injetar Incêndio</button>
        </div>
      `;

      if (markersRef.current[sensor.id_sensor]) {
        // Atualizar marcador existente
        markersRef.current[sensor.id_sensor].setLatLng([sensor.latitude, sensor.longitude]);
        markersRef.current[sensor.id_sensor].setIcon(icon);
        markersRef.current[sensor.id_sensor].setPopupContent(popupContent);
      } else {
        // Criar novo marcador
        const marker = window.L.marker([sensor.latitude, sensor.longitude], { icon }).addTo(mapRef.current);
        marker.bindPopup(popupContent);
        
        // Listener para o botão de injeção dentro do popup do Leaflet
        marker.on('popupopen', () => {
          const btn = document.getElementById(popupId);
          if (btn) {
            btn.addEventListener('click', () => {
              onInjectFire(sensor.id_sensor);
              mapRef.current.closePopup();
            });
          }
        });

        markersRef.current[sensor.id_sensor] = marker;
      }

      // Se entrar em emergência, centralizar o mapa
      if (isEmergency && !markersRef.current[sensor.id_sensor]._focused) {
        markersRef.current[sensor.id_sensor]._focused = true;
        mapRef.current.panTo([sensor.latitude, sensor.longitude]);
      } else if (!isEmergency) {
        markersRef.current[sensor.id_sensor]._focused = false;
      }
    });
  }, [sensors, onInjectFire]);

  return (
    <div style={{ height: '100%', width: '100%', minHeight: '380px', position: 'relative' }}>
      <div ref={mapContainerRef} style={{ height: '100%', width: '100%', borderRadius: '8px' }} />
    </div>
  );
}
