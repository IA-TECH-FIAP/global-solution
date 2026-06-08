import React, { useEffect, useRef } from 'react';

export default function TelemetryChart({ sensors }) {
  const canvasRef = useRef(null);
  const chartRef = useRef(null);

  useEffect(() => {
    if (window.Chart && canvasRef.current && !chartRef.current) {
      const ctx = canvasRef.current.getContext('2d');
      chartRef.current = new window.Chart(ctx, {
        type: 'line',
        data: {
          labels: [],
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
  }, []);

  useEffect(() => {
    if (!chartRef.current || sensors.length === 0) return;

    // Calcular médias atuais
    const sumTemp = sensors.reduce((acc, s) => acc + s.temperature, 0);
    const sumHum = sensors.reduce((acc, s) => acc + s.humidity, 0);
    const avgTemp = (sumTemp / sensors.length).toFixed(1);
    const avgHum = (sumHum / sensors.length).toFixed(1);
    const now = new Date().toLocaleTimeString();

    const chart = chartRef.current;
    chart.data.labels.push(now);
    chart.data.datasets[0].data.push(avgTemp);
    chart.data.datasets[1].data.push(avgHum);

    if (chart.data.labels.length > 15) {
      chart.data.labels.shift();
      chart.data.datasets[0].data.shift();
      chart.data.datasets[1].data.shift();
    }

    chart.update('none');
  }, [sensors]);

  return (
    <div style={{ height: '100%', minHeight: '220px', width: '100%' }}>
      <canvas ref={canvasRef} />
    </div>
  );
}
