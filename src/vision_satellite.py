"""
EcoGlow - Visão Computacional Orbital (Cap11: Arquiteturas, Fine-Tuning e o Futuro da Visão)

Pipeline em DUAS ETAPAS, alinhado ao conteúdo do capítulo:

  1) Proposta de regiões (region proposal) com OpenCV: segmentação HSV por cor de
     fogo + operações morfológicas + detecção de contornos. Gera candidatos a foco.

  2) Classificação por Machine Learning (HOG + SVM): cada região candidata é
     recortada, descrita pelo histograma de gradientes orientados (HOG) e
     classificada por uma Máquina de Vetores de Suporte linear (LinearSVC),
     exatamente a abordagem clássica do Cap11 (Código-fonte 1). Isso filtra falsos
     positivos (ex.: telhados/solo alaranjado) que a simples limiarização de cor
     deixaria passar.

O classificador é treinado uma única vez sobre um conjunto sintético de patches
(fogo x não-fogo) e cacheado em disco. Aceita também imagens reais via argumento de
linha de comando (Sentinel/Landsat/NASA FIRMS).
"""

import os
import sys
import json

import cv2
import numpy as np

# Dependências de ML são opcionais: se ausentes, caímos para heurística de cor.
try:
    from skimage.feature import hog
    from sklearn.svm import LinearSVC
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import make_pipeline
    import joblib
    ML_AVAILABLE = True
except Exception:  # noqa: BLE001
    ML_AVAILABLE = False

# ---------------------------------------------------------------------------
# Diretórios
# ---------------------------------------------------------------------------
PUBLIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "public")
os.makedirs(PUBLIC_DIR, exist_ok=True)
OUTPUT_IMG = os.path.join(PUBLIC_DIR, "processed_satellite.jpg")
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
os.makedirs(DATA_DIR, exist_ok=True)
DETECTION_FILE = os.path.join(DATA_DIR, "satellite_detections.json")
MODEL_FILE = os.path.join(DATA_DIR, "fire_hog_svm.joblib")

# Parâmetros do descritor HOG (mesmos do Cap11)
PATCH_SIZE = (64, 64)
HOG_PARAMS = dict(orientations=9, pixels_per_cell=(8, 8),
                  cells_per_block=(2, 2), block_norm="L2-Hys")


def random_in_range(low, high):
    return int(np.random.randint(low, high))


# ---------------------------------------------------------------------------
# Geração de imagem orbital sintética (mock) para demonstração
# ---------------------------------------------------------------------------
def generate_mock_satellite_image():
    """Imagem aérea sintética de fazenda (talhões verdes/marrons) com um foco de
    incêndio ativo (calor laranja/amarelo) e pluma de fumaça cinza."""
    img = np.zeros((400, 600, 3), dtype=np.uint8)

    for r in range(4):
        for c in range(6):
            color = [random_in_range(20, 60), random_in_range(100, 180), random_in_range(20, 70)]
            if (r + c) % 3 == 0:
                color = [random_in_range(10, 40), random_in_range(70, 110), random_in_range(50, 100)]
            img[r * 100:(r + 1) * 100, c * 100:(c + 1) * 100] = color
            cv2.rectangle(img, (c * 100, r * 100), ((c + 1) * 100, (r + 1) * 100), (40, 50, 40), 1)

    fire_x, fire_y = 350, 180
    # Pluma de fumaça deslocando-se para Noroeste (vento de Sudeste)
    for i in range(15):
        radius = int(12 + i * 2.5)
        offset_x = -i * 8 + np.random.randint(-10, 10)
        offset_y = -i * 5 + np.random.randint(-8, 8)
        gray_val = np.random.randint(180, 220)
        cv2.circle(img, (fire_x + offset_x, fire_y + offset_y), radius, (gray_val,) * 3, -1)

    # Foco de calor (núcleo branco -> amarelo -> laranja)
    cv2.circle(img, (fire_x, fire_y), 25, (0, 69, 255), -1)
    cv2.circle(img, (fire_x, fire_y), 12, (0, 215, 255), -1)
    cv2.circle(img, (fire_x, fire_y), 5, (255, 255, 255), -1)

    # "Pegadinha": um telhado/solo alaranjado que NÃO é fogo (testa o classificador)
    cv2.rectangle(img, (80, 300), (140, 345), (20, 90, 200), -1)
    return img


# ---------------------------------------------------------------------------
# ETAPA 2 - Classificador HOG + SVM
# ---------------------------------------------------------------------------
def _make_fire_patch():
    """Sintetiza um patch 64x64 contendo um foco de calor (radial: branco->laranja)."""
    p = np.zeros((*PATCH_SIZE, 3), dtype=np.uint8)
    p[:] = [random_in_range(15, 60), random_in_range(70, 150), random_in_range(20, 70)]
    cx, cy = random_in_range(24, 40), random_in_range(24, 40)
    cv2.circle(p, (cx, cy), random_in_range(16, 24), (0, 69, 255), -1)
    cv2.circle(p, (cx, cy), random_in_range(8, 14), (0, 215, 255), -1)
    cv2.circle(p, (cx, cy), random_in_range(3, 6), (255, 255, 255), -1)
    return p


def _make_nonfire_patch():
    """Patch 64x64 de não-fogo: talhão liso, fumaça cinza, borda de talhão ou
    mancha alaranjada chapada (telhado/solo seco) — sem o gradiente radial do fogo."""
    kind = random_in_range(0, 4)
    p = np.zeros((*PATCH_SIZE, 3), dtype=np.uint8)
    if kind == 0:  # campo verde/marrom
        p[:] = [random_in_range(15, 60), random_in_range(80, 180), random_in_range(20, 80)]
    elif kind == 1:  # fumaça cinza
        g = random_in_range(170, 220)
        p[:] = [g, g, g]
        cv2.circle(p, (32, 32), random_in_range(18, 28), (g - 20,) * 3, -1)
    elif kind == 2:  # divisão de talhão (linhas)
        p[:] = [random_in_range(20, 60), random_in_range(90, 160), random_in_range(20, 70)]
        cv2.line(p, (0, 32), (64, 32), (40, 50, 40), 2)
        cv2.line(p, (32, 0), (32, 64), (40, 50, 40), 2)
    else:  # mancha alaranjada CHAPADA (sem gradiente de calor) - principal falso positivo
        p[:] = [random_in_range(10, 40), random_in_range(70, 110), random_in_range(170, 220)]
    return p


def _hog_descriptor(bgr_patch):
    """Extrai o descritor HOG do patch (em escala de cinza, como no Cap11)."""
    gray = cv2.cvtColor(cv2.resize(bgr_patch, PATCH_SIZE), cv2.COLOR_BGR2GRAY)
    return hog(gray, **HOG_PARAMS)


def train_fire_classifier(n_per_class=160, force=False):
    """Treina (ou carrega do cache) um classificador HOG + SVM para fogo x não-fogo."""
    if not ML_AVAILABLE:
        return None
    if os.path.exists(MODEL_FILE) and not force:
        try:
            return joblib.load(MODEL_FILE)
        except Exception:  # noqa: BLE001
            pass

    X, y = [], []
    for _ in range(n_per_class):
        X.append(_hog_descriptor(_make_fire_patch()));   y.append(1)
        X.append(_hog_descriptor(_make_nonfire_patch())); y.append(0)

    # Pipeline: normalização (SVMs são sensíveis à escala) + SVM linear
    clf = make_pipeline(StandardScaler(), LinearSVC(C=1.0, max_iter=5000))
    clf.fit(np.array(X), np.array(y))
    try:
        joblib.dump(clf, MODEL_FILE)
    except Exception:  # noqa: BLE001
        pass
    return clf


def classify_region(clf, bgr_patch):
    """Retorna (is_fire, score) para uma região candidata usando o SVM."""
    if clf is None or bgr_patch.size == 0:
        return True, None  # sem ML: aceita a proposta de cor (fallback)
    feat = _hog_descriptor(bgr_patch).reshape(1, -1)
    pred = int(clf.predict(feat)[0])
    score = float(clf.decision_function(feat)[0])
    return pred == 1, score


# ---------------------------------------------------------------------------
# ETAPA 1 + 2 - Pipeline completo
# ---------------------------------------------------------------------------
def process_satellite_imagery(img_path=None):
    if img_path and os.path.exists(img_path):
        img = cv2.imread(img_path)
        if img is None:
            print(f"Aviso: não foi possível ler '{img_path}'. Gerando imagem mock.")
            img = generate_mock_satellite_image()
    else:
        img = generate_mock_satellite_image()

    annotated = img.copy()

    # --- ETAPA 1: proposta de regiões por segmentação de cor (OpenCV) ---
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    lower_fire = np.array([0, 130, 180])
    upper_fire = np.array([25, 255, 255])
    mask = cv2.inRange(hsv, lower_fire, upper_fire)
    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # --- ETAPA 2: classificador HOG + SVM ---
    clf = train_fire_classifier()
    metodo = "HOG+SVM" if clf is not None else "heuristica_cor"

    LAT_CENTRO, LON_CENTRO = -21.1775, -47.8103
    detections = []
    descartadas = 0

    for idx, cnt in enumerate(contours):
        area = cv2.contourArea(cnt)
        if area <= 10:
            continue
        x, y, w, h = cv2.boundingRect(cnt)

        # Recorte da região candidata (com margem) para o classificador
        pad = 8
        y0, y1 = max(0, y - pad), min(img.shape[0], y + h + pad)
        x0, x1 = max(0, x - pad), min(img.shape[1], x + w + pad)
        roi = img[y0:y1, x0:x1]

        is_fire, score = classify_region(clf, roi)
        if not is_fire:
            descartadas += 1
            # Marca em azul a região rejeitada pelo ML (falso positivo de cor)
            cv2.rectangle(annotated, (x, y), (x + w, y + h), (255, 120, 0), 1)
            continue

        cx, cy = x + w // 2, y + h // 2
        lat_detectada = LAT_CENTRO + ((200 - cy) * 0.0001)
        lon_detectada = LON_CENTRO + ((cx - 300) * 0.0001)

        detections.append({
            "id_deteccao": f"ORBITAL_{idx + 1:02d}",
            "pixel_x": cx, "pixel_y": cy,
            "latitude": round(lat_detectada, 6),
            "longitude": round(lon_detectada, 6),
            "area_afetada_px": area,
            "metodo_deteccao": metodo,
            "ml_confianca": round(score, 3) if score is not None else None,
            "criticidade": "CRITICAL" if area > 200 else "WARNING",
        })

        cv2.rectangle(annotated, (x - 10, y - 10), (x + w + 10, y + h + 10), (0, 0, 255), 2)
        cv2.drawMarker(annotated, (cx, cy), (0, 255, 255), cv2.MARKER_CROSS, 15, 2)
        conf = f" ({score:.1f})" if score is not None else ""
        cv2.putText(annotated, f"FOGO {area:.0f}px{conf}", (x - 10, y - 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)

    cv2.imwrite(OUTPUT_IMG, annotated)
    with open(DETECTION_FILE, "w") as f:
        json.dump(detections, f, indent=2)

    print(f"Visão Computacional ({metodo}) executada.")
    print(f"  Regiões candidatas (cor): {len(detections) + descartadas} | "
          f"confirmadas pelo SVM: {len(detections)} | descartadas: {descartadas}")
    print(f"  Imagem anotada salva em: {OUTPUT_IMG}")


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else None
    process_satellite_imagery(path)
