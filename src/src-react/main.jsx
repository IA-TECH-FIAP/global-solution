import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);

// Registrar Service Worker do PWA se estiver em produção
if ('serviceWorker' in navigator && import.meta.env.PROD) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js', { scope: '/' })
      .then(reg => {
        console.log('PWA Service Worker registrado com sucesso: ', reg.scope);
      })
      .catch(err => {
        console.error('Falha ao registrar Service Worker do PWA: ', err);
      });
  });
}
