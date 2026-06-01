# EcoGlow - Plataforma Inteligente de Prevenção e Contingência de Desastres Rurais

<p align="center">
  <img src="../../assets/logo-fiap.png" alt="FIAP Logo" width="40%">
</p>

## 👨‍🎓 Integrantes:
| Nome | RM |
|------|-----|
| Giulia Bugatti Fonseca | 562675 |
| Mahmod Ahmad Issa | 561426 |
| Matheus Cardoso Oliveira Lima | 565844 |
| Silas Fernandes de Souza Fonseca | 564246 |

## 👩‍🏫 Professores:
### Tutor(a)
- [Caique Nonato da Silva Bezerra](https://www.linkedin.com/in/caique-nonato/)
### Coordenador(a)
- [André Godoi Chiovato](https://www.linkedin.com/in/andregodoichiovato/)

---

## 📜 Descrição do Projeto

O **EcoGlow** é uma plataforma inteligente e descentralizada projetada para a antecipação, detecção e resposta a desastres ambientais, focando primariamente em queimadas e desmatamento. O principal diferencial da plataforma é a **reconciliação de dados em duas escalas**:
1. **Escala Micro (Solo)**: Capturada localmente através de uma malha inteligente de 30 nós sensores simulando o hardware ESP32. Estes nós operam com lógica de *Edge Computing*, processando a temperatura e a umidade do ar na ponta para disparar alertas instantâneos de emergência e aumentar a frequência de transmissão em tempo real via protocolo simulado LoRaWAN.
2. **Escala Macro (Orbital)**: Capturada por imagens aéreas orbitais de satélites ( Sentinel / Landsat) processadas em tempo real com **Visão Computacional (OpenCV)** para detecção automática de plumas de fumaça, calor em infravermelho e cicatrizes de desmatamento recente.

O EcoGlow atua como um **orquestrador de contingência**. Quando o satélite e um sensor de solo detectam anomalias térmicas na mesma coordenada geográfica, o sistema consolida o alerta máximo e aciona o **EcoGlow Copilot**. Esse assistente inteligente baseado em **RAG (Retrieval-Augmented Generation)** realiza buscas semânticas em manuais técnicos oficiais (como diretrizes de combate a incêndio do IBAMA e planos de evacuação rural) para gerar um plano de ação personalizado em formato Markdown (ex: rotas de fuga contra a direção do vento, posicionamento de caminhões-pipa e diretrizes de proteção individual).

---

## 📁 Estrutura de Pastas

A organização dos arquivos e códigos no repositório segue a seguinte divisão:

- <b>data/</b>: Contém arquivos de dados estruturados gerados e consumidos pelos módulos.
  - `manuais/ibama_diretrizes.txt`: Base de conhecimento contendo as diretrizes do IBAMA para RAG.
  - `sensors_telemetry.json`: Telemetria em tempo real dos 30 sensores terrestres.
  - `satellite_detections.json`: Histórico de focos de incêndio detectados via OpenCV.
  - `satelite_data.json`: Alertas espaciais coletados por automação/scraping.
- <b>src/</b>: Todo o código fonte e lógica de software do EcoGlow.
  - `public/`: Interface web do Dashboard (HTML, CSS customizado, Javascript dinâmico com Leaflet e Chart.js).
  - `iot_simulator.py`: Simulador da rede de sensores terrestres ESP32 e lógica de Edge Computing.
  - `vision_satellite.py`: Pipeline de Visão Computacional OpenCV para detecção de focos de calor.
  - `news_scraper.py`: Script de scraping para coleta de alertas espaciais.
  - `rag_contingency.py`: Motor de buscas RAG e geração de planos de evacuação/Copilot.
  - `server.js`: Servidor backend Node.js (Express & WebSockets) integrando APIs e Python.
- <b>README.md</b>: Este guia explicativo do projeto.

---

## 🔧 Como Executar o Projeto

Siga o passo a passo abaixo para executar o EcoGlow localmente em sua máquina:

### Pré-requisitos
- Node.js (v18 ou superior instalado)
- Python 3.10 ou superior

### Passo a Passo de Execução

1. **Clone o repositório e acesse a pasta do projeto:**
   ```bash
   cd 2TIAO/Global-Solution
   ```

2. **Crie e ative o ambiente virtual do Python (recomendado):**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Instale as dependências de Python:**
   ```bash
   pip install opencv-python numpy
   ```

4. **Instale as dependências do Node.js:**
   ```bash
   cd src
   npm install
   ```

5. **Inicie o Simulador de Sensores IoT (deixe rodando em um terminal):**
   ```bash
   # Certifique-se de estar na pasta do projeto e com o venv ativo
   python3 src/iot_simulator.py
   ```

6. **Inicie o Servidor Central do EcoGlow (em outro terminal):**
   ```bash
   # Na pasta 2TIAO/Global-Solution/src/
   npm run dev
   ```

7. **Acesse o Dashboard:**
   Abra o seu navegador e acesse `http://localhost:3000`.

---

## 📎 Links e Observações

- **Vídeo Demonstrativo**: *[Link do Vídeo no YouTube - Não Listado]* (Adicionar link após postagem).
- **Competição e Pódio**: **QUERO CONCORRER** (Opção de participação ativada).
- **Decisões Técnicas**: A escolha de simular redes LoRaWAN é fundamental, visto que a comunicação por Wi-Fi ou redes móveis convencionais em áreas agrícolas remotas é inviável tecnicamente.

---

## 📋 Licença

<img style="height:22px!important;margin-left:3px;vertical-align:text-bottom;" src="https://mirrors.creativecommons.org/presskit/icons/cc.svg?ref=chooser-v1"><img style="height:22px!important;margin-left:3px;vertical-align:text-bottom;" src="https://mirrors.creativecommons.org/presskit/icons/by.svg?ref=chooser-v1"><p xmlns:cc="http://creativecommons.org/ns#" xmlns:dct="http://purl.org/dc/terms/"><a property="dct:title" rel="cc:attributionURL" href="https://github.com/SabrinaOtoni/TEMPLATE-FIAP-GRAD-ON-IA">MODELO GIT FIAP</a> por <a rel="cc:attributionURL dct:creator" property="cc:attributionName" href="https://fiap.com.br">FIAP</a> está licenciado sobre <a href="http://creativecommons.org/licenses/by/4.0/?ref=chooser-v1" target="_blank" rel="license noopener noreferrer" style="display:inline-block;">Attribution 4.0 International</a>.</p>
