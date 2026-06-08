import React, { useState, useEffect, useRef } from 'react';
import ReactDOM from 'react-dom';
import { Maximize2, Minimize2, Send } from 'lucide-react';
import { marked } from 'marked';

export default function CopilotChat({ sensors, selectedSensorId, onSelectSensor }) {
  const [messages, setMessages] = useState([
    {
      sender: 'system',
      text: 'Olá! Sou o EcoGlow Copilot. Quando houver uma emergência ambiental, utilizarei RAG para consultar as diretrizes oficiais do IBAMA e gerar planos de fuga e contenção customizados.'
    }
  ]);
  const [query, setQuery] = useState('');
  const [windDirection, setWindDirection] = useState('Leste');
  const [isMaximized, setIsMaximized] = useState(false);
  const chatMessagesEndRef = useRef(null);

  // Auto scroll para a última mensagem
  useEffect(() => {
    chatMessagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!query.trim()) return;

    const userMsg = query;
    setMessages(prev => [...prev, { sender: 'user', text: userMsg }]);
    setQuery('');

    // Enviar para o backend RAG
    fetch('/api/copilot', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query: userMsg,
        sensorId: selectedSensorId,
        windDirection: windDirection
      })
    })
      .then(res => res.json())
      .then(data => {
        setMessages(prev => [...prev, { sender: 'assistant', text: data.answer }]);
      })
      .catch(() => {
        setMessages(prev => [...prev, { sender: 'system', text: 'Erro ao obter plano de contingência do Copilot.' }]);
      });
  };

  // Renderiza Markdown para HTML de forma segura
  const renderMarkdown = (text) => {
    // Configurar marked para quebras de linha automáticas
    marked.setOptions({
      breaks: true,
      gfm: true
    });
    const html = marked.parse(text);
    return { __html: html };
  };

  const chatContent = (
    <section className={`card ${isMaximized ? 'maximized' : ''}`} id="copilot-section" style={isMaximized ? {} : { height: '100%' }}>
      <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2>🤖 EcoGlow Copilot - RAG & Contingência</h2>
        <button 
          onClick={() => setIsMaximized(!isMaximized)} 
          className="btn btn-secondary btn-sm" 
          style={{ padding: '0.2rem 0.5rem', display: 'flex', alignItems: 'center', gap: '0.3rem' }}
          title={isMaximized ? "Minimizar Chat" : "Maximizar Chat"}
        >
          {isMaximized ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
          {isMaximized ? "Minimizar" : "Maximizar"}
        </button>
      </div>
      <div className="card-body chat-body">
        <div className="chat-messages" style={{ overflowY: 'auto', flex: 1 }}>
          {messages.map((msg, index) => (
            <div 
              key={index} 
              className={`message ${msg.sender}-message`}
              dangerouslySetInnerHTML={renderMarkdown(msg.text)}
            />
          ))}
          <div ref={chatMessagesEndRef} />
        </div>
        <div className="chat-controls" style={{ marginTop: '0.75rem' }}>
          <div className="copilot-inputs" style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.5rem', flexWrap: 'wrap' }}>
            <div>
              <label htmlFor="copilotSensorSelect" style={{ marginRight: '0.3rem', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Nó Foco:</label>
              <select 
                id="copilotSensorSelect" 
                value={selectedSensorId} 
                onChange={(e) => onSelectSensor(e.target.value)}
                style={{ background: '#0f172a', color: '#fff', border: '1px solid var(--border-color)', borderRadius: '4px', padding: '0.2rem 0.5rem' }}
              >
                {sensors.map(s => (
                  <option key={s.id_sensor} value={s.id_sensor}>
                    {s.id_sensor}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label htmlFor="copilotWindSelect" style={{ marginRight: '0.3rem', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Vento:</label>
              <select 
                id="copilotWindSelect" 
                value={windDirection} 
                onChange={(e) => setWindDirection(e.target.value)}
                style={{ background: '#0f172a', color: '#fff', border: '1px solid var(--border-color)', borderRadius: '4px', padding: '0.2rem 0.5rem' }}
              >
                <option value="Leste">Leste (Sotavento p/ Oeste)</option>
                <option value="Oeste">Oeste (Sotavento p/ Leste)</option>
                <option value="Norte">Norte (Sotavento p/ Sul)</option>
                <option value="Sul">Sul (Sotavento p/ Norte)</option>
              </select>
            </div>
          </div>
          <form onSubmit={handleSubmit} className="chat-form" style={{ display: 'flex', gap: '0.5rem' }}>
            <input 
              type="text" 
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Pergunte ao Copilot (ex: Como agir em rota de evacuação?)..." 
              required 
              style={{ flex: 1, background: 'rgba(0, 0, 0, 0.3)', border: '1px solid var(--border-color)', borderRadius: '6px', padding: '0.6rem 1rem', color: '#fff' }}
            />
            <button type="submit" className="btn btn-accent" style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
              <Send size={14} />
              Enviar
            </button>
          </form>
        </div>
      </div>
    </section>
  );

  if (isMaximized) {
    return ReactDOM.createPortal(
      <>
        <div className="modal-backdrop active" onClick={() => setIsMaximized(false)} />
        <div className="copilot-modal-wrapper">
          <div className="maximized-chat-container">
            {chatContent}
          </div>
        </div>
      </>,
      document.body
    );
  }

  return chatContent;
}
