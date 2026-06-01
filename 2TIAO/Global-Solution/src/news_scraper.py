import urllib.request
import xml.etree.ElementTree as ET
import json
import os
import ssl

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
os.makedirs(DATA_DIR, exist_ok=True)
OUTPUT_FILE = os.path.join(DATA_DIR, "satelite_data.json")

def scrape_space_news():
    """
    Realiza automação/scraping no feed de RSS de notícias espaciais da NASA
    ou do NOAA Space Weather para manter a base de conhecimento de eventos cósmicos e climáticos atualizada.
    """
    print("Iniciando scraping automático de alertas cósmicos...")
    url = "https://www.nasa.gov/feed/"
    
    # Criar um contexto SSL amigável (ignorar erros de certificado autoassinado se houver)
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko)'
    }
    
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, context=ctx, timeout=8) as response:
            xml_data = response.read()
            
        root = ET.fromstring(xml_data)
        alerts = []
        
        # Parsear os elementos RSS do XML
        for item in root.findall(".//item")[:10]:
            title = item.find("title").text if item.find("title") is not None else "Alerta Espacial"
            link = item.find("link").text if item.find("link") is not None else ""
            pub_date = item.find("pubDate").text if item.find("pubDate") is not None else ""
            desc = item.find("description").text if item.find("description") is not None else ""
            
            alerts.append({
                "titulo": title,
                "link": link,
                "data_publicacao": pub_date,
                "descricao": desc[:250] + "..." if len(desc) > 250 else desc
            })
            
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(alerts, f, indent=2, ensure_ascii=False)
            
        print(f"Scraping concluído com sucesso. {len(alerts)} notícias salvas em {OUTPUT_FILE}.")
        return alerts

    except Exception as e:
        print(f"Erro ao acessar feed oficial (usando dados locais de fallback): {e}")
        # Dados de fallback em caso de falha de conexão/rede externa
        fallback_data = [
            {
                "titulo": "Alerta Solar: Flare Classe X detectado em região ativa AR3615",
                "link": "https://www.nasa.gov/solar-storm",
                "data_publicacao": "Mon, 01 Jun 2026 12:00:00 GMT",
                "descricao": "Erupção solar de alta intensidade pode causar flutuações magnéticas e interferir em comunicações LoRa e satélites nas próximas 48 horas."
            },
            {
                "titulo": "Satélites detectam nova pluma de aerossóis na América do Sul",
                "link": "https://www.nasa.gov/satellite-monitoring",
                "data_publicacao": "Mon, 01 Jun 2026 10:15:00 GMT",
                "descricao": "Níveis de fumaça elevados devido a focos de queima controlada e seca severa no Centro-Oeste brasileiro."
            }
        ]
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(fallback_data, f, indent=2, ensure_ascii=False)
        return fallback_data

if __name__ == "__main__":
    scrape_space_news()
