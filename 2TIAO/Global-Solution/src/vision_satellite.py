import cv2
import numpy as np
import os
import sys
import json

# Diretórios
PUBLIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "public")
os.makedirs(PUBLIC_DIR, exist_ok=True)

OUTPUT_IMG = os.path.join(PUBLIC_DIR, "processed_satellite.jpg")
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
DETECTION_FILE = os.path.join(DATA_DIR, "satellite_detections.json")

def generate_mock_satellite_image():
    """
    Gera uma imagem sintética imitando uma visão aérea/orbital de uma fazenda (campos verdes/marrons)
    com um foco de incêndio ativo (círculo vermelho/laranja e pluma de fumaça cinza).
    """
    # Criar fundo representando campos agrícolas
    img = np.zeros((400, 600, 3), dtype=np.uint8)
    
    # Preencher com tons de verde e marrom representando plantações
    for r in range(4):
        for c in range(6):
            color = [random_in_range(20, 60), random_in_range(100, 180), random_in_range(20, 70)] # verde/marrom
            if (r + c) % 3 == 0:
                color = [random_in_range(10, 40), random_in_range(70, 110), random_in_range(50, 100)] # marrom/seco
            img[r*100:(r+1)*100, c*100:(c+1)*100] = color
            
            # Desenhar divisões de talhões
            cv2.rectangle(img, (c*100, r*100), ((c+1)*100, (r+1)*100), (40, 50, 40), 1)

    # Injetar foco de incêndio ativo
    # Centro do fogo em coordenadas de pixels (x: 350, y: 180)
    fire_x, fire_y = 350, 180
    
    # Pluma de fumaça (cinza semitransparente)
    # Fumaça deslocando-se para Noroeste (devido a vento Sudeste)
    for i in range(15):
        radius = int(12 + i * 2.5)
        offset_x = -i * 8 + np.random.randint(-10, 10)
        offset_y = -i * 5 + np.random.randint(-8, 8)
        gray_val = np.random.randint(180, 220)
        cv2.circle(img, (fire_x + offset_x, fire_y + offset_y), radius, (gray_val, gray_val, gray_val), -1)

    # Foco de calor (amarelo e laranja brilhante no centro)
    cv2.circle(img, (fire_x, fire_y), 25, (0, 69, 255), -1)      # Laranja (BGR: 0, 69, 255)
    cv2.circle(img, (fire_x, fire_y), 12, (0, 215, 255), -1)     # Amarelo (BGR: 0, 215, 255)
    cv2.circle(img, (fire_x, fire_y), 5, (255, 255, 255), -1)    # Centro branco (calor extremo)

    return img

def random_in_range(low, high):
    return int(np.random.randint(low, high))

def process_satellite_imagery(img_path=None):
    """
    Processa a imagem orbital para identificar o foco de calor (incêndio) usando OpenCV.
    Aplica conversão HSV, limiarização por máscara de cor e encontra contornos do incêndio.
    """
    if img_path and os.path.exists(img_path):
        img = cv2.imread(img_path)
    else:
        # Gerar imagem mock se nenhum arquivo for fornecido
        img = generate_mock_satellite_image()

    # Cópia para anotações visuais
    annotated = img.copy()

    # Converter para o espaço de cores HSV para segmentar as cores do fogo
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    # Definir limites para tons de fogo (laranja/vermelho/amarelo brilhantes)
    # Laranja/Vermelho tem Hues baixos (0-25) e altos valores de saturação e brilho
    lower_fire = np.array([0, 130, 180])
    upper_fire = np.array([25, 255, 255])
    
    # Criar máscara para o fogo
    mask = cv2.inRange(hsv, lower_fire, upper_fire)

    # Operações morfológicas para remover pequenos ruídos da máscara
    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    # Encontrar os contornos das chamas/focos de calor detectados
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    detections = []
    
    for idx, cnt in enumerate(contours):
        area = cv2.contourArea(cnt)
        if area > 10:  # Ignorar pequenas áreas insignificantes
            x, y, w, h = cv2.boundingRect(cnt)
            
            # Centroide do foco detectado
            cx = x + w // 2
            cy = y + h // 2

            # Mapear coordenadas de pixel para coordenadas GPS correspondentes
            # Coordenadas da fazenda (mapeando a largura de 600px e altura de 400px)
            LAT_CENTRO = -21.1775
            LON_CENTRO = -47.8103
            
            # Mapeamento linear simples de pixel para coordenadas GPS
            lat_detectada = LAT_CENTRO + ((200 - cy) * 0.0001)
            lon_detectada = LON_CENTRO + ((cx - 300) * 0.0001)

            detections.append({
                "id_deteccao": f"ORBITAL_{idx+1:02d}",
                "pixel_x": cx,
                "pixel_y": cy,
                "latitude": round(lat_detectada, 6),
                "longitude": round(lon_detectada, 6),
                "area_afetada_px": area,
                "criticidade": "CRITICAL" if area > 200 else "WARNING"
            })

            # Desenhar caixa delimitadora e círculo ao redor do foco
            cv2.rectangle(annotated, (x - 10, y - 10), (x + w + 10, y + h + 10), (0, 0, 255), 2)
            cv2.drawMarker(annotated, (cx, cy), (0, 255, 255), cv2.MARKER_CROSS, 15, 2)
            
            # Texto explicativo na imagem
            label = f"ALERTA CALOR: {area:.0f}px"
            cv2.putText(annotated, label, (x - 10, y - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)

    # Salvar a imagem processada com as anotações na pasta public para o dashboard renderizar
    cv2.imwrite(OUTPUT_IMG, annotated)
    
    # Salvar detecções em arquivo JSON
    with open(DETECTION_FILE, "w") as f:
        json.dump(detections, f, indent=2)

    print(f"Visão Computacional executada. {len(detections)} foco(s) de calor detectado(s).")
    print(f"Imagem anotada salva em: {OUTPUT_IMG}")

if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else None
    process_satellite_imagery(path)
