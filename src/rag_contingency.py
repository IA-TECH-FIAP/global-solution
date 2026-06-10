"""
EcoGlow - Copilot RAG (Cap10: LLMs, Alinhamento, Prompt Engineering e Agentes)

Implementa Retrieval-Augmented Generation de verdade:

  RETRIEVAL  -> busca semântica por similaridade de cosseno sobre vetores TF-IDF
                dos trechos do manual do IBAMA (substitui o antigo overlap de Jaccard).
  AUGMENT    -> monta um prompt estruturado (chat template system/user) combinando o
                contexto operacional em tempo real (sensor + vento) com os trechos
                recuperados.
  GENERATION -> chama um LLM real (Anthropic Claude ou OpenAI) quando há chave de API
                disponível, controlando a temperatura. Sem chave/rede, recai em um
                gerador determinístico estruturado (camada de fallback), mantendo o
                pipeline sempre funcional.

Uso (compatível com o backend): python rag_contingency.py "<pergunta>" <sensor_id> <vento>
"""

import os
import sys
import json
import re
import urllib.request

# Recuperação vetorial (Cap10 - RAG / busca semântica)
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    SKLEARN_OK = True
except Exception:  # noqa: BLE001
    SKLEARN_OK = False

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MANUAL_PATH = os.path.join(BASE_DIR, "..", "data", "manuais", "ibama_diretrizes.txt")
SENSORS_FILE = os.path.join(BASE_DIR, "..", "data", "sensors_telemetry.json")

# Modelo padrão Anthropic (mais recente). Pode ser sobrescrito por env.
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-8")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
LLM_TEMPERATURE = float(os.environ.get("ECOGLOW_LLM_TEMPERATURE", "0.3"))


# ---------------------------------------------------------------------------
# 1) Base de conhecimento -> chunks
# ---------------------------------------------------------------------------
def load_manual():
    """Carrega o manual de diretrizes e o divide em seções/parágrafos (chunks)."""
    if not os.path.exists(MANUAL_PATH):
        return []
    with open(MANUAL_PATH, "r", encoding="utf-8") as f:
        content = f.read()

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
            for item in part.split("\n\n"):
                item = item.strip()
                if item:
                    chunks.append({"section": current_section, "text": item})
    return chunks


# ---------------------------------------------------------------------------
# 2) RETRIEVAL - busca semântica por cosseno sobre vetores TF-IDF
# ---------------------------------------------------------------------------
def _jaccard(query, text):
    """Fallback lexical caso o sklearn não esteja disponível."""
    qa = set(re.findall(r'\w+', query.lower()))
    ta = set(re.findall(r'\w+', text.lower()))
    if not (qa | ta):
        return 0.0
    return len(qa & ta) / len(qa | ta)


def retrieve_relevant_chunks(query, chunks, top_k=3, min_score=0.02):
    """Recupera os trechos mais relevantes do manual para a consulta.

    Vetoriza consulta + chunks com TF-IDF e ranqueia por similaridade de cosseno
    (verdadeira busca em espaço vetorial). Sem sklearn, usa overlap de Jaccard.
    """
    if not chunks:
        return []

    texts = [c["text"] for c in chunks]

    if SKLEARN_OK:
        vectorizer = TfidfVectorizer(strip_accents="unicode", lowercase=True,
                                     ngram_range=(1, 2))
        matrix = vectorizer.fit_transform(texts + [query])
        sims = cosine_similarity(matrix[-1], matrix[:-1]).ravel()
    else:
        sims = [_jaccard(query, t) for t in texts]

    ranked = sorted(zip(sims, chunks), key=lambda x: x[0], reverse=True)
    out = []
    for score, chunk in ranked[:top_k]:
        if score > min_score:
            c = dict(chunk)
            c["score"] = round(float(score), 4)
            out.append(c)
    return out


# ---------------------------------------------------------------------------
# 3) Contexto operacional (telemetria do sensor)
# ---------------------------------------------------------------------------
def get_sensor_info(sensor_id):
    if not (sensor_id and os.path.exists(SENSORS_FILE)):
        return "Nenhum sensor de solo associado."
    try:
        with open(SENSORS_FILE, "r") as f:
            for s in json.load(f):
                if s["id_sensor"] == sensor_id:
                    return (
                        f"Sensor Terrestre: {s['id_sensor']}\n"
                        f"- Coordenadas: Lat {s['latitude']}, Lon {s['longitude']}\n"
                        f"- Temperatura: {s['temperature']}°C\n"
                        f"- Umidade do Ar: {s['humidity']}%\n"
                        f"- Umidade do Solo: {s['soil_moisture']}%\n"
                        f"- Status de Risco: {s['status_risco']}"
                    )
    except Exception:  # noqa: BLE001
        pass
    return "Nenhum sensor de solo associado."


# ---------------------------------------------------------------------------
# 4) AUGMENT - montagem do prompt (chat template system/user do Cap10)
# ---------------------------------------------------------------------------
def build_messages(query, sensor_info, manual_context, wind_direction):
    system = (
        "Você é o EcoGlow Copilot, um assistente de brigada de incêndio florestal. "
        "Responda SEMPRE em português do Brasil e em formato Markdown. "
        "Baseie-se ESTRITAMENTE nas diretrizes oficiais do IBAMA fornecidas no contexto; "
        "se a informação não estiver no contexto, diga explicitamente que não há diretriz "
        "específica (não invente — evite alucinações). Seja objetivo, acionável e priorize "
        "a segurança da equipe de campo."
    )
    user = (
        f"#### Contexto operacional em tempo real\n"
        f"{sensor_info}\n"
        f"- Direção do vento: {wind_direction}\n\n"
        f"#### Trechos recuperados do manual do IBAMA (RAG)\n"
        f"{manual_context}\n\n"
        f"#### Pergunta do brigadista\n{query}\n\n"
        f"Gere um **Plano de Ação & Contingência** com: rota de fuga coerente com o vento, "
        f"posicionamento de recursos (caminhão-pipa/brigada), EPIs e hidratação."
    )
    return system, user


# ---------------------------------------------------------------------------
# 5) GENERATION - chamada a um LLM real (Anthropic / OpenAI) via HTTP
# ---------------------------------------------------------------------------
def _http_post_json(url, headers, payload, timeout=30):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def call_llm(system, user, temperature=LLM_TEMPERATURE):
    """Tenta gerar a resposta com um LLM real. Retorna (texto, provider) ou (None, None)."""
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    if anthropic_key:
        try:
            data = _http_post_json(
                "https://api.anthropic.com/v1/messages",
                {"x-api-key": anthropic_key, "anthropic-version": "2023-06-01",
                 "content-type": "application/json"},
                {"model": ANTHROPIC_MODEL, "max_tokens": 1024, "temperature": temperature,
                 "system": system, "messages": [{"role": "user", "content": user}]})
            return data["content"][0]["text"], f"Anthropic/{ANTHROPIC_MODEL}"
        except Exception as exc:  # noqa: BLE001
            print(f"[LLM] Falha Anthropic: {exc}", file=sys.stderr)

    openai_key = os.environ.get("OPENAI_API_KEY")
    if openai_key:
        try:
            data = _http_post_json(
                "https://api.openai.com/v1/chat/completions",
                {"Authorization": f"Bearer {openai_key}", "content-type": "application/json"},
                {"model": OPENAI_MODEL, "temperature": temperature,
                 "messages": [{"role": "system", "content": system},
                              {"role": "user", "content": user}]})
            return data["choices"][0]["message"]["content"], f"OpenAI/{OPENAI_MODEL}"
        except Exception as exc:  # noqa: BLE001
            print(f"[LLM] Falha OpenAI: {exc}", file=sys.stderr)

    return None, None


# ---------------------------------------------------------------------------
# 6) Camada de fallback determinística (quando não há LLM disponível)
# ---------------------------------------------------------------------------
def _rota_fuga(query, wind_direction):
    if not any(k in query.lower() for k in ("vento", "fuga", "evacuar", "rota", "evacu")):
        return ("Foco ativo em monitoramento preventivo. Caso o sensor acuse EMERGENCY "
                "(Temp > 48°C), posicione a brigada a pelo menos 100m da linha de fogo e "
                "utilize abafadores ou aceiros preventivos de 3 metros de largura.")
    d = (wind_direction or "").upper()
    laterais = {"LESTE": "Oeste", "OESTE": "Leste", "NORTE": "Sul", "SUL": "Norte"}
    perigo = next((v for k, v in laterais.items() if k in d), None)
    if perigo:
        return (f"⚠️ **DIRETRIZ DE EVACUAÇÃO CRÍTICA (Vento de {wind_direction}):**\n"
                f"O vento empurra chamas e gases tóxicos para o **{perigo}**. "
                f"**NÃO evacue para o {perigo}.**\n"
                f"👉 **Rotas recomendadas:** desloque a equipe perpendicularmente ao fluxo, "
                f"para o **Norte** ou para o **Sul** (ou contra o vento, se houver via limpa).")
    return ("⚠️ **DIRETRIZ DE EVACUAÇÃO:** Evacue em direção perpendicular ao fluxo do vento "
            "para evitar a fumaça tóxica.")


def fallback_generation(query, sensor_info, manual_context, wind_direction):
    plano = _rota_fuga(query, wind_direction)
    return f"""### 🤖 EcoGlow Copilot - Plano de Ação & Contingência

Com base no contexto operacional em tempo real e nas diretrizes oficiais do IBAMA:

#### 📊 Contexto Operacional Atual:
{sensor_info}
- **Direção do Vento:** {wind_direction}

---

#### 📖 Trechos Relevantes Recuperados (RAG · cosseno TF-IDF):
{manual_context}

---

#### 🚨 Plano de Ação Recomendado:
{plano}

- **Equipamentos Obrigatórios (EPI):** Máscara de carvão ativado, óculos de proteção contra fumaça, capacete e luvas de couro.
- **Hidratação:** Ingestão de 500ml de água a cada 30 minutos de trabalho ativo.
"""


# ---------------------------------------------------------------------------
# 7) Orquestração RAG completa
# ---------------------------------------------------------------------------
def generate_response(query, sensor_id=None, wind_direction="Leste"):
    chunks = load_manual()
    retrieved = retrieve_relevant_chunks(query, chunks)
    sensor_info = get_sensor_info(sensor_id)

    if retrieved:
        manual_context = "\n\n".join(
            f"({c['section']} · score={c['score']}): {c['text']}" for c in retrieved)
    else:
        manual_context = ("Nenhuma diretriz específica do IBAMA encontrada na busca "
                          "semântica para esta consulta.")

    system, user = build_messages(query, sensor_info, manual_context, wind_direction)

    # Tenta o LLM real; se indisponível, usa a camada de fallback determinística.
    llm_text, provider = call_llm(system, user)
    if llm_text:
        return (f"_(Geração via {provider} · RAG por cosseno TF-IDF · "
                f"temperatura {LLM_TEMPERATURE})_\n\n{llm_text}")

    return fallback_generation(query, sensor_info, manual_context, wind_direction)


if __name__ == "__main__":
    query = sys.argv[1] if len(sys.argv) > 1 else "O que fazer se o vento soprar de Leste?"
    sensor_id = sys.argv[2] if len(sys.argv) > 2 else "ESP32_N01"
    wind_direction = sys.argv[3] if len(sys.argv) > 3 else "Leste"
    print(generate_response(query, sensor_id, wind_direction))
