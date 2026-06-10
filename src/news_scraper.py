"""
EcoGlow - Coletor de Hiperautomação (Cap02: Scraping, APIs e RPA Seguro)

Este módulo materializa as boas práticas do capítulo de Hiperautomação:
  * Inspeção ética do arquivo robots.txt (Robots Exclusion Protocol / RFC 9309)
    ANTES de qualquer coleta, respeitando as diretivas Disallow.
  * Scraping de DOM com BeautifulSoup + seletores CSS (não apenas leitura de RSS).
  * Rate limiting com espera exponencial (exponential backoff) entre tentativas.
  * Verificação TLS/SSL ATIVA (RPA Seguro) e User-Agent identificável.
  * Logging detalhado de conformidade para fins de auditoria (LGPD/GDPR).

Fonte primária: artigo "Incêndio florestal" da Wikipédia (HTML estável, robots.txt
real e temática aderente ao EcoGlow). Em caso de falha de rede, usa-se um fallback
local para não interromper o pipeline.
"""

import os
import json
import time
import logging
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Configuração de caminhos e logging de auditoria
# ---------------------------------------------------------------------------
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
os.makedirs(DATA_DIR, exist_ok=True)
OUTPUT_FILE = os.path.join(DATA_DIR, "satelite_data.json")
LOG_FILE = os.path.join(DATA_DIR, "scraper_audit.log")

logger = logging.getLogger("ecoglow.scraper")
if not logger.handlers:
    logger.setLevel(logging.INFO)
    _fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    _fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    _fh.setFormatter(_fmt)
    _sh = logging.StreamHandler()
    _sh.setFormatter(_fmt)
    logger.addHandler(_fh)
    logger.addHandler(_sh)

# Identificação honesta do agente (boa prática de RPA seguro)
USER_AGENT = "EcoGlowBot/1.0 (+projeto educacional FIAP; contato silas23.fr@gmail.com)"
HEADERS = {"User-Agent": USER_AGENT}

TARGET_URL = "https://pt.wikipedia.org/wiki/Inc%C3%AAndio_florestal"

# Parâmetros de educação/cortesia para com o servidor
REQUEST_TIMEOUT = 10        # segundos
RATE_LIMIT_DELAY = 1.5      # pausa mínima entre requisições (Crawl-delay implícito)
MAX_RETRIES = 3             # tentativas com backoff exponencial


# ---------------------------------------------------------------------------
# 1) Camada de conformidade: robots.txt (adaptado do Código-fonte 1 do Cap02)
# ---------------------------------------------------------------------------
def fetch_robots(domain_url: str) -> dict:
    """Lê e interpreta o robots.txt do domínio, retornando diretivas do user-agent '*'.

    A inspeção é considerada obrigatória em projetos de webscraping éticos: garante
    que a automação respeite as intenções do administrador do domínio.
    """
    parsed = urlparse(domain_url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    robots_url = urljoin(base, "/robots.txt")
    directives = {"allow": [], "disallow": [], "crawl_delay": None}

    try:
        resp = requests.get(robots_url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    except requests.RequestException as exc:
        logger.warning("Falha ao obter robots.txt (%s): %s", robots_url, exc)
        return directives

    if resp.status_code != 200:
        logger.info("robots.txt indisponível (HTTP %s) em %s; assumindo coleta liberada.",
                    resp.status_code, robots_url)
        return directives

    ua_block = False
    for line in resp.text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, value = line.partition(":")
        key, value = key.strip().lower(), value.strip()
        if key == "user-agent":
            # Aplicamos regras do agente genérico '*' (cenário didático)
            ua_block = (value == "*")
        elif ua_block and key == "disallow" and value:
            directives["disallow"].append(value)
        elif ua_block and key == "allow" and value:
            directives["allow"].append(value)
        elif ua_block and key == "crawl-delay":
            try:
                directives["crawl_delay"] = float(value)
            except ValueError:
                pass

    logger.info("robots.txt lido: %d Disallow, %d Allow, crawl-delay=%s",
                len(directives["disallow"]), len(directives["allow"]),
                directives["crawl_delay"])
    return directives


def is_path_allowed(url: str, directives: dict) -> bool:
    """Verifica se o caminho da URL é permitido conforme as diretivas do robots.txt."""
    path = urlparse(url).path or "/"
    # Allow tem precedência sobre Disallow para o prefixo mais específico (simplificado)
    for allowed in directives.get("allow", []):
        if path.startswith(allowed):
            return True
    for blocked in directives.get("disallow", []):
        if blocked and path.startswith(blocked):
            logger.warning("Coleta BLOQUEADA por robots.txt: '%s' casa com Disallow '%s'",
                           path, blocked)
            return False
    return True


# ---------------------------------------------------------------------------
# 2) Requisição educada com espera exponencial (exponential backoff)
# ---------------------------------------------------------------------------
def polite_get(url: str, crawl_delay: float = None) -> requests.Response:
    """GET com verificação TLS ativa, rate limiting e backoff exponencial.

    Limitar requisições e aplicar espera exponencial evita sobrecarregar o servidor
    e demonstra conformidade em auditorias (Cap02).
    """
    delay = max(RATE_LIMIT_DELAY, crawl_delay or 0)
    time.sleep(delay)  # rate limiting básico antes de cada requisição

    last_exc = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            # verify=True mantém a verificação de certificado TLS (RPA Seguro)
            resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT, verify=True)
            if resp.status_code == 200:
                logger.info("GET %s -> 200 (tentativa %d)", url, attempt)
                return resp
            if resp.status_code in (429, 503):
                # Servidor pedindo para desacelerar: respeitamos com backoff
                wait = (2 ** attempt) + 0.5
                logger.warning("HTTP %s em %s; aguardando %.1fs (backoff)",
                               resp.status_code, url, wait)
                time.sleep(wait)
                continue
            resp.raise_for_status()
        except requests.RequestException as exc:
            last_exc = exc
            wait = (2 ** attempt)  # 2s, 4s, 8s...
            logger.warning("Erro na tentativa %d para %s: %s; backoff %.1fs",
                           attempt, url, exc, wait)
            time.sleep(wait)

    raise RuntimeError(f"Falha ao coletar {url} após {MAX_RETRIES} tentativas: {last_exc}")


# ---------------------------------------------------------------------------
# 3) Extração de conteúdo via DOM com seletores CSS (BeautifulSoup)
# ---------------------------------------------------------------------------
def scrape_wildfire_knowledge():
    """Coleta conhecimento sobre incêndios florestais respeitando robots.txt.

    Percorre o DOM com seletores CSS, associando cada parágrafo à seção (h2) a que
    pertence, produzindo itens estruturados úteis ao painel/base de conhecimento.
    """
    logger.info("Iniciando coleta ética de alertas ambientais em %s", TARGET_URL)

    # Passo 1 - Conformidade: ler robots.txt antes de tudo
    directives = fetch_robots(TARGET_URL)
    if not is_path_allowed(TARGET_URL, directives):
        raise PermissionError(f"Coleta de {TARGET_URL} proibida pelo robots.txt do domínio.")

    # Passo 2 - Requisição educada
    resp = polite_get(TARGET_URL, crawl_delay=directives.get("crawl_delay"))

    # Passo 3 - Parsing do DOM e travessia com seletores CSS
    soup = BeautifulSoup(resp.text, "html.parser")
    content = soup.select_one("div.mw-parser-output")
    if content is None:
        raise ValueError("Container principal do artigo não encontrado no DOM.")

    coletado_em = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
    secao_atual = "Introdução"
    alerts = []

    # Iteramos sobre os filhos diretos para manter a associação seção -> parágrafo
    for el in content.find_all(["h2", "p"], recursive=True):
        if el.name == "h2":
            titulo_secao = el.select_one(".mw-headline")
            secao_atual = (titulo_secao.get_text(strip=True)
                           if titulo_secao else el.get_text(strip=True)) or secao_atual
            continue

        texto = el.get_text(" ", strip=True)
        # Remove marcadores de citação tipo [1], [carece de fontes] etc.
        if len(texto) < 60:
            continue

        # Primeiro link interno do parágrafo (seletor de atributo CSS)
        link_el = el.select_one('a[href^="/wiki/"]')
        link = urljoin(TARGET_URL, link_el["href"]) if link_el else TARGET_URL

        alerts.append({
            "titulo": f"[{secao_atual}] {texto[:60].rstrip()}...",
            "link": link,
            "data_publicacao": coletado_em,
            "fonte": "Wikipédia - Incêndio florestal (scraping DOM)",
            "descricao": texto[:300] + ("..." if len(texto) > 300 else ""),
        })

        if len(alerts) >= 12:  # limite de cortesia: não exaurir a página
            break

    if not alerts:
        raise ValueError("Nenhum parágrafo relevante extraído do DOM.")

    logger.info("Coleta concluída: %d itens extraídos via seletores CSS.", len(alerts))
    return alerts


# ---------------------------------------------------------------------------
# 4) Fallback resiliente
# ---------------------------------------------------------------------------
def _fallback_data():
    logger.warning("Usando dados locais de fallback (coleta externa indisponível).")
    agora = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
    return [
        {
            "titulo": "[Prevenção] Frente de ar seco eleva risco de ignição...",
            "link": "https://pt.wikipedia.org/wiki/Inc%C3%AAndio_florestal",
            "data_publicacao": agora,
            "fonte": "Fallback local",
            "descricao": ("Baixa umidade do ar combinada a altas temperaturas cria "
                          "condições críticas para a propagação rápida de queimadas em "
                          "pastagens secas."),
        },
        {
            "titulo": "[Monitoramento] Satélites detectam plumas de aerossóis...",
            "link": "https://pt.wikipedia.org/wiki/Inc%C3%AAndio_florestal",
            "data_publicacao": agora,
            "fonte": "Fallback local",
            "descricao": ("Níveis elevados de fumaça associados a focos de calor exigem "
                          "reconciliação com a telemetria de solo para confirmação."),
        },
    ]


def scrape_space_news():
    """Ponto de entrada usado pelo backend. Mantém o nome por compatibilidade."""
    try:
        alerts = scrape_wildfire_knowledge()
    except Exception as exc:  # noqa: BLE001 - queremos resiliência total no pipeline
        logger.error("Falha na coleta ética: %s", exc)
        alerts = _fallback_data()

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(alerts, f, indent=2, ensure_ascii=False)
    logger.info("%d itens salvos em %s", len(alerts), OUTPUT_FILE)
    return alerts


if __name__ == "__main__":
    scrape_space_news()
