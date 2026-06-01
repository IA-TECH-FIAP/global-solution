import os
import sys
import json
import re

# Caminhos dos arquivos
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MANUAL_PATH = os.path.join(BASE_DIR, "..", "data", "manuais", "ibama_diretrizes.txt")
SENSORS_FILE = os.path.join(BASE_DIR, "..", "data", "sensors_telemetry.json")

def load_manual():
    """Carrega o manual de diretrizes e o divide em seções/parágrafos (chunks)."""
    if not os.path.exists(MANUAL_PATH):
        return []
    with open(MANUAL_PATH, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Dividir por blocos demarcados por colchetes [SEÇÃO ...]
    sections = re.split(r'(\[SEÇÃO \d+ - [^\]]+\])', content)
    
    chunks = []
    current_section = "Introdução"
    
    for part in sections:
        part = part.strip()
        if not part:
            continue
        if part.startswith("[SEÇÃO"):
            current_section = part
        else:
            # Dividir subitens
            items = part.split("\n\n")
            for item in items:
                item = item.strip()
                if item:
                    chunks.append({
                        "section": current_section,
                        "text": item
                    })
    return chunks

def calculate_similarity(query, chunk_text):
    """Calcula similaridade de cosseno simplificada (Jaccard token overlap) para RAG."""
    def get_words(text):
        return set(re.findall(r'\w+', text.lower()))
    
    query_words = get_words(query)
    chunk_words = get_words(chunk_text)
    
    intersection = query_words.intersection(chunk_words)
    union = query_words.union(chunk_words)
    
    if not union:
        return 0.0
    return len(intersection) / len(union)

def retrieve_relevant_chunks(query, chunks, top_k=2):
    """Recupera os trechos do manual mais relevantes para a dúvida do usuário."""
    ranked = []
    for chunk in chunks:
        score = calculate_similarity(query, chunk["text"])
        ranked.append((score, chunk))
    
    # Ordenar por score decrescente
    ranked.sort(key=lambda x: x[0], reverse=True)
    return [item[1] for item in ranked[:top_k] if item[0] > 0.0]

def generate_response(query, sensor_id=None, wind_direction="Leste"):
    """
    Simula e gera a resposta do Copilot baseando-se no contexto atual
    e nos trechos recuperados do manual via RAG.
    """
    chunks = load_manual()
    retrieved = retrieve_relevant_chunks(query, chunks)
    
    # Obter dados do sensor se fornecido
    sensor_info = "Nenhum sensor de solo associado."
    if sensor_id and os.path.exists(SENSORS_FILE):
        try:
            with open(SENSORS_FILE, "r") as f:
                sensors = json.load(f)
                for s in sensors:
                    if s["id_sensor"] == sensor_id:
                        sensor_info = (
                            f"Sensor Terrestre: {s['id_sensor']}\n"
                            f"- Coordenadas: Lat {s['latitude']}, Lon {s['longitude']}\n"
                            f"- Temperatura: {s['temperature']}°C\n"
                            f"- Umidade do Ar: {s['humidity']}%\n"
                            f"- Umidade do Solo: {s['soil_moisture']}%\n"
                            f"- Status de Risco: {s['status_risco']}"
                        )
                        break
        except Exception:
            pass

    # Trechos do manual recuperados
    manual_context = ""
    if retrieved:
        manual_context = "\n\n".join([f"({c['section']}): {c['text']}" for c in retrieved])
    else:
        manual_context = "Nenhuma diretriz específica do IBAMA encontrada na busca semântica para esta consulta."

    # Criar resposta estruturada em Markdown de altíssimo nível (simulando a chamada do LLM)
    # A resposta é construída dinamicamente baseada nos dados reais recuperados do RAG
    
    # Se a dúvida for sobre vento/rota de fuga
    rota_fuga = ""
    if "vento" in query.lower() or "fuga" in query.lower() or "evacuar" in query.lower() or "rota" in query.lower():
        direcao = wind_direction.upper()
        if "LESTE" in direcao:
            rota_fuga = (
                "⚠️ **DIRETRIZ DE EVACUAÇÃO CRÍTICA (Vento de Leste):**\n"
                "Como o vento sopra de Leste para Oeste, a pluma de fumaça e as chamas estão se propagando para o Oeste. "
                "**NÃO evacue para o Oeste.**\n"
                "👉 **Rotas recomendadas:** Desloque a equipe de campo imediatamente pelas rotas laterais ao fluxo: para o **Norte** ou para o **Sul**."
            )
        elif "OESTE" in direcao:
            rota_fuga = (
                "⚠️ **DIRETRIZ DE EVACUAÇÃO CRÍTICA (Vento de Oeste):**\n"
                "Como o vento sopra de Oeste para Leste, a propagação está ocorrendo para o Leste. "
                "**NÃO evacue para o Leste.**\n"
                "👉 **Rotas recomendadas:** Desloque a equipe de campo imediatamente para o **Norte** ou para o **Sul**."
            )
        else:
            rota_fuga = (
                "⚠️ **DIRETRIZ DE EVACUAÇÃO:**\n"
                "Evacue em direção perpendicular ao fluxo do vento para evitar fumaça tóxica."
            )

    # Construir o retorno formatado
    response_md = f"""### 🤖 EcoGlow Copilot - Plano de Ação & Contingência

Com base no contexto operacional em tempo real e nas diretrizes oficiais do IBAMA:

#### 📊 Contexto Operacional Atual:
{sensor_info}
- **Direção do Vento:** {wind_direction}

---

#### 📖 Trechos Relevantes Recuperados (RAG):
{manual_context}

---

#### 🚨 Plano de Ação Recomendado:
{rota_fuga if rota_fuga else "Foco ativo em monitoramento preventivo. Caso o sensor acuse EMERGENCY (Temp > 48°C), posicione a brigada rural a pelo menos 100m da linha de fogo e utilize abafadores ou aceiros preventivos de 3 metros de largura."}

- **Equipamentos Obrigatórios (EPI):** Máscara de carvão ativado, óculos de proteção contra fumaça, capacete e luvas de couro.
- **Hidratação:** Ingestão de 500ml de água a cada 30 minutos de trabalho ativo.
"""
    return response_md

if __name__ == "__main__":
    # Suportar chamada direta via linha de comando
    query = sys.argv[1] if len(sys.argv) > 1 else "O que fazer se o vento soprar de Leste?"
    sensor_id = sys.argv[2] if len(sys.argv) > 2 else "ESP32_N01"
    wind_direction = sys.argv[3] if len(sys.argv) > 3 else "Leste"
    
    response = generate_response(query, sensor_id, wind_direction)
    print(response)
