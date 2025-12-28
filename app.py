# ÖTEGEZEGEN TESPİT PLATFORMU
# Created by Hızır Kaan ERKAN, Fatma YALÇIN, Sefa GAKÇI, İrem ARIOĞLU

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import pandas as pd
import numpy as np
import requests
from datetime import datetime
import io

app = Flask(__name__)
CORS(app)

# NASA API URL
NASA_API_URL = "https://exoplanetarchive.ipac.caltech.edu/TAP/sync"


# Fonksiyonlar
def normalize_star_mag(mag, source):
    try:
        mag = float(mag)
        if mag <= 0:
            return None

        if source == 'toi':
            # TESS magnitude (Tmag)
            return max(0.0, min(1.0, (13.0 - mag) / 5.0))
        elif source == 'koi':
            # Kepler magnitude (KepMag)
            return max(0.0, min(1.0, (14.0 - mag) / 6.0))
        elif source == 'file':
            # Bilinmeyen Veriler
            return max(0.0, min(1.0, (13.5 - mag) / 6.0))
        return None
    except:
        return None


def f_depth(x):
    return 1.0 if x > 500 else 0.3


def f_period(x):
    return 1.0 if x < 30 else 0.4


def f_duration(x):
    return 1.0 if x < 10 else 0.6


def calculate_score(period, duration, depth, star_mag, source='toi'):
    try:
        period = float(period)
        duration = float(duration)

        # Kepler için duration günden saate çevirme
        if source == 'koi':
            duration *= 24.0

        # Kepler için depth çok küçük olabilir (0-1 arası), ppm'e çevirme
        if source == 'koi' and depth < 1:
            depth *= 1e6

        depth = float(depth)
        star_mag_norm = normalize_star_mag(star_mag, source)

        if star_mag_norm is None:
            return None

        w = (0.58, 0.27, 0.08, 0.07)
        score = (
                w[0] * star_mag_norm +
                w[1] * f_depth(depth) +
                w[2] * f_period(period) +
                w[3] * f_duration(duration)
        )
        return 100.0 * score
    except:
        return None


def get_label(score, mid=46.0, high=80.0):
    if score >= high:
        return "CP"
    if score >= mid:
        return "PC"
    return "APC"


def load_nasa_csv(source):
    return pd.read_csv(
        source,
        engine="python",
        comment="#",
        skip_blank_lines=True
    )


def safe_float(x):
    try:
        if pd.isna(x):
            return None
        return float(str(x).strip())
    except:
        return None


def find_columns(df):
    col_map = {}
    columns_lower = {col.lower().strip(): col for col in df.columns}

    print(f"📋 Bulunan kolonlar: {list(df.columns)}")  # Debug için

    # ID kolonu
    id_keys = ['kepid', 'koi', 'koi_name', 'toi', 'tic', 'pl_name', 'id', 'object', 'name', 'hostname', 'tid',]
    for key in id_keys:
        if key in columns_lower:
            col_map['id'] = columns_lower[key]
            break

    # Period kolonu
    period_keys = ['orbper', 'period', 'pl_orbper', 'orbital_period', 'per', 'koi_period', 'pl_orbper']
    for key in period_keys:
        if key in columns_lower:
            col_map['period'] = columns_lower[key]
            break

    # Duration kolonu
    duration_keys = ['trandur', 'pl_trandur', 'duration', 'transit_duration', 't_dur', 'pl_trandurh', 'koi_duration']
    for key in duration_keys:
        if key in columns_lower:
            col_map['duration'] = columns_lower[key]
            break

    # Depth kolonu
    depth_keys = ['trandept', 'pl_trandep', 'depth', 'transit_depth', 'ppm', 'koi_depth', 'pl_trandep']
    for key in depth_keys:
        if key in columns_lower:
            col_map['depth'] = columns_lower[key]
            break

    # Star magnitude kolonu
    mag_keys = ['tmag', 'st_tmag', 'tic_tmag', 'kepmag', 'koi_kepmag', 'mag', 't_mag', 'sy_tmag', 'st_mag']
    for key in mag_keys:
        if key in columns_lower:
            col_map['star_mag'] = columns_lower[key]
            break

    print(f"✅ Eşleşen kolonlar: {col_map}")  # Debug için
    return col_map


# HTML Template
HTML_TEMPLATE = '''<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ÖTEGEZEGEN TESPİT PLATFORMU - NASA Ötegezegen Arşivi Analizi</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }

        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
            color: #fff;
            min-height: 100vh;
            padding: 20px;
        }

        .stars {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            pointer-events: none;
            z-index: 0;
        }

        .star {
            position: absolute;
            width: 2px;
            height: 2px;
            background: white;
            border-radius: 50%;
            animation: twinkle 3s infinite;
        }

        @keyframes twinkle {
            0%, 100% { opacity: 0.3; }
            50% { opacity: 1; }
        }

        .container {
            max-width: 1200px;
            margin: 0 auto;
            position: relative;
            z-index: 1;
        }

        header {
            text-align: center;
            padding: 40px 20px;
            background: rgba(255, 255, 255, 0.05);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            margin-bottom: 30px;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }

        h1 {
            font-size: 3em;
            margin-bottom: 10px;
            background: linear-gradient(45deg, #00d4ff, #7b2ff7);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .subtitle { color: #aaa; font-size: 1.1em; }

        .tabs {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }

        .tab {
            flex: 1;
            min-width: 200px;
            padding: 15px 25px;
            background: rgba(255, 255, 255, 0.05);
            border: 2px solid rgba(255, 255, 255, 0.1);
            border-radius: 10px;
            cursor: pointer;
            transition: all 0.3s;
            text-align: center;
        }

        .tab:hover {
            background: rgba(255, 255, 255, 0.1);
            border-color: #00d4ff;
            transform: translateY(-2px);
        }

        .tab.active {
            background: linear-gradient(45deg, #00d4ff, #7b2ff7);
            border-color: transparent;
            box-shadow: 0 5px 20px rgba(0, 212, 255, 0.4);
        }

        .content {
            background: rgba(255, 255, 255, 0.05);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            padding: 30px;
            border: 1px solid rgba(255, 255, 255, 0.1);
            display: none;
        }

        .content.active {
            display: block;
            animation: fadeIn 0.5s;
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .form-group { margin-bottom: 20px; }

        label {
            display: block;
            margin-bottom: 8px;
            color: #00d4ff;
            font-weight: 500;
        }

        input, select {
            width: 100%;
            padding: 12px;
            background: rgba(0, 0, 0, 0.3);
            border: 1px solid rgba(255, 255, 255, 0.2);
            border-radius: 8px;
            color: #fff;
            font-size: 16px;
            transition: all 0.3s;
        }

        input:focus, select:focus {
            outline: none;
            border-color: #00d4ff;
            box-shadow: 0 0 15px rgba(0, 212, 255, 0.3);
        }

        button {
            padding: 12px 30px;
            background: linear-gradient(45deg, #00d4ff, #7b2ff7);
            border: none;
            border-radius: 8px;
            color: white;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s;
            margin-right: 10px;
            margin-top: 10px;
        }

        button:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 20px rgba(0, 212, 255, 0.4);
        }

        button:disabled { opacity: 0.5; cursor: not-allowed; }

        .result-card {
            background: rgba(0, 0, 0, 0.3);
            border: 1px solid rgba(255, 255, 255, 0.2);
            border-radius: 12px;
            padding: 20px;
            margin-top: 20px;
        }

        .score-display {
            font-size: 3em;
            text-align: center;
            margin: 20px 0;
            font-weight: bold;
            background: linear-gradient(45deg, #00d4ff, #7b2ff7);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .label-badge {
            display: inline-block;
            padding: 8px 20px;
            border-radius: 20px;
            font-weight: 600;
            margin: 10px 5px;
        }

        .label-CP { background: linear-gradient(45deg, #00ff88, #00d4ff); }
        .label-PC { background: linear-gradient(45deg, #ffaa00, #ff6b00); }
        .label-APC { background: linear-gradient(45deg, #ff0055, #aa00ff); }

        .data-table { width: 100%; overflow-x: auto; margin-top: 20px; }

        table { width: 100%; border-collapse: collapse; }

        th, td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }

        th { background: rgba(0, 212, 255, 0.2); font-weight: 600; }
        tr:hover { background: rgba(255, 255, 255, 0.05); }

        .loading { text-align: center; padding: 40px; }

        .spinner {
            border: 4px solid rgba(255, 255, 255, 0.1);
            border-top: 4px solid #00d4ff;
            border-radius: 50%;
            width: 50px;
            height: 50px;
            animation: spin 1s linear infinite;
            margin: 0 auto;
        }

        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }

        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin: 20px 0;
        }

        .stat-card {
            background: rgba(0, 0, 0, 0.3);
            border: 1px solid rgba(255, 255, 255, 0.2);
            border-radius: 10px;
            padding: 15px;
            text-align: center;
        }

        .stat-value {
            font-size: 2em;
            font-weight: bold;
            color: #00d4ff;
        }

        .stat-label { color: #aaa; margin-top: 5px; }

        .error-message {
            background: rgba(255, 0, 0, 0.2);
            border: 1px solid rgba(255, 0, 0, 0.5);
            color: #ff6b6b;
            padding: 15px;
            border-radius: 8px;
            margin: 15px 0;
        }

        .info-message {
            background: rgba(0, 212, 255, 0.1);
            border: 1px solid rgba(0, 212, 255, 0.3);
            color: #00d4ff;
            padding: 15px;
            border-radius: 8px;
            margin: 15px 0;
        }
        .chart-container {
        background: rgba(0, 0, 0, 0.3);
        border: 1px solid rgba(255, 255, 255, 0.2);
        border-radius: 12px;
        padding: 20px;
        margin: 20px 0;
        max-width: 600px;
        margin-left: auto;
        margin-right: auto;
        }

        .chart-container h4 {
        color: #00d4ff;
        margin-bottom: 15px;
         text-align: center;
        }

        .chart-wrapper {
        position: relative;
        height: 300px;
        }
        
        
        .creators {
            text-align: center;
            margin-top: 30px;
            padding: 20px;
            color: #aaa;
            font-size: 0.9em;
        }
    </style>
</head>
<body>
    <div class="stars" id="stars"></div>

    <div class="container">
        <header>
            <h1>🛰️ÖTEGEZEGEN TESPİT PLATFORMU🛰️</h1>
            <p class="subtitle">NASA Verileriyle Geliştirilmiş Analiz Aracı</p>
        </header>

        <div class="tabs">
            <div class="tab active" onclick="showTab('manual', this)">📝 Manuel Giriş</div>
            <div class="tab" onclick="showTab('nasa', this)">🛰️ NASA Arşiv Analizi</div>
            <div class="tab" onclick="showTab('file', this)">📁 Dosya Analizi</div>
        </div>
        
        <div id="manual" class="content active">
    <h2>Manuel Gezegen Verisi Girişi</h2>
    <div class="form-group">
        <label>Yörünge Periyodu (gün)</label>
        <input type="number" id="period" step="0.01" placeholder="Örn: 3.5">
    </div>
    <div class="form-group">
        <label>Transit Süresi (saat)</label>
        <input type="number" id="duration" step="0.01" placeholder="Örn: 2.3">
    </div>
    <div class="form-group">
        <label>Transit Derinliği (ppm)</label>
        <input type="number" id="depth" step="1" placeholder="Örn: 850">
    </div>
    <div class="form-group">
        <label>Yıldız Parlaklığı (Mag)</label>
        <input type="number" id="star_mag" step="0.01" placeholder="Örn: 11.5">
    </div>
    <div class="form-group">
        <label>Veri Kaynağı</label>
        <select id="manualSource">
            <option value="toi">TESS (TOI)</option>
            <option value="koi">Kepler (KOI)</option>
        </select>
    </div>
    <button onclick="calculateScore()">🧮 Hesapla</button>
    <button onclick="clearManual()">🗑️ Temizle</button>
    <div id="manualResult"></div>
    
    <div id="queryHistory" style="margin-top: 30px; padding: 20px; background: rgba(0, 0, 0, 0.2); border-radius: 12px; border: 1px solid rgba(255, 255, 255, 0.1);"></div>
</div>

        <div id="nasa" class="content">
            <h2>NASA ÖTEGEZEGEN ARŞİVİ</h2>
            <p class="subtitle">TESS (TOI) ve Kepler (KOI) otomatik analiz</p>
            <div class="form-group">
                <label>Veri Kaynağı</label>
                <select id="nasaSource">
                    <option value="toi">🛰️ TESS Objects of Interest (TOI)</option>
                    <option value="koi">🔭 Kepler Objects of Interest (KOI)</option>
                </select>
            </div>
            <button onclick="fetchNasaAuto()" id="nasaBtn">🚀 Veriyi Getir ve Analiz Et</button>
            <button onclick="exportResults('nasa')" id="exportNasaBtn" style="display:none;">💾 Excel'e İndir</button>
            <div id="nasaResult"></div>
        </div>

        <div id="file" class="content">
            <h2>CSV/Excel Dosya Analizi</h2>
            <div class="info-message">
                <strong>📋 Desteklenen Kolon İsimleri:</strong><br>
                • ID: toi, tic, kepid, koi, pl_name, id<br>
                • Periyot: period, orbper, koi_period, pl_orbper<br>
                • Süre: duration, trandur, koi_duration, pl_trandur<br>
                • Derinlik: depth, trandept, koi_depth, pl_trandep<br>
                • Parlaklık: tmag, kepmag, koi_kepmag, st_tmag
            </div>
            <div class="form-group">
                <label>Dosya Seç (CSV, XLS, XLSX)</label>
                <input type="file" id="fileInput" accept=".csv,.xlsx,.xls">
            </div>
            <div class="form-group">
                <label>Veri Kaynağı (Dosya için)</label>
                <select id="fileSource">
                    <option value="file">Otomatik Algıla</option>
                    <option value="toi">TESS Verisi</option>
                    <option value="koi">Kepler Verisi</option>
                </select>
            </div>
            <button onclick="analyzeFile()" id="fileBtn">📊 Analiz Et</button>
            <button onclick="exportResults('file')" id="exportFileBtn" style="display:none;">💾 Excel'e İndir</button>
            <div id="fileResult"></div>
        </div>

        <div class="creators">
            Created by Hızır Kaan ERKAN, Fatma YALÇIN, Sefa GAKÇI, İrem ARIOĞLU
        </div>
    </div>

    <script>
        let currentData = null;

        function createStars() {
            const starsContainer = document.getElementById('stars');
            for (let i = 0; i < 100; i++) {
                const star = document.createElement('div');
                star.className = 'star';
                star.style.left = Math.random() * 100 + '%';
                star.style.top = Math.random() * 100 + '%';
                star.style.animationDelay = Math.random() * 3 + 's';
                starsContainer.appendChild(star);
            }
        }
        createStars();

        window.addEventListener('DOMContentLoaded', function() {
        displayHistory();
        });
        // Sorgu geçmişi için localStorage kullanımı
        const HISTORY_KEY = 'exoplanet_query_history';
        const MAX_HISTORY = 10;

        function saveToHistory(query, result) {
        let history = JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]');
    
        // Yeni sorguyu ekle
         history.unshift({
        timestamp: new Date().toISOString(),
        query: query,
        result: result
        });
    
        // Sadece son 10 tanesini tut
         history = history.slice(0, MAX_HISTORY);
    
         localStorage.setItem(HISTORY_KEY, JSON.stringify(history));
            }

        function loadHistory() {
        return JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]');
            }

        function clearHistory() {
        localStorage.removeItem(HISTORY_KEY);
        displayHistory();
            }

        function displayHistory() {
        const history = loadHistory();
        const historyDiv = document.getElementById('queryHistory');
    
        if (history.length === 0) {
        historyDiv.innerHTML = '<p style="color: #aaa; text-align: center;">Henüz sorgu geçmişi yok</p>';
        return;
        }
    
        let html = '<h4 style="color: #00d4ff; margin-bottom: 15px;">📋 Son 10 Sorgu</h4>';
        html += '<div style="max-height: 400px; overflow-y: auto;">';
    
        history.forEach((item, index) => {
        const date = new Date(item.timestamp);
        const timeStr = date.toLocaleString('tr-TR');
        
        html += `
            <div class="history-item" onclick="loadQueryFromHistory(${index})" style="
                background: rgba(0, 0, 0, 0.3);
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 8px;
                padding: 12px;
                margin-bottom: 10px;
                cursor: pointer;
                transition: all 0.3s;
            " onmouseover="this.style.background='rgba(0, 212, 255, 0.1)'; this.style.borderColor='#00d4ff'" 
               onmouseout="this.style.background='rgba(0, 0, 0, 0.3)'; this.style.borderColor='rgba(255, 255, 255, 0.2)'">
                <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                    <span style="color: #00d4ff; font-weight: 600;">Sorgu ${index + 1}</span>
                    <span style="color: #aaa; font-size: 0.9em;">${timeStr}</span>
                </div>
                <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; font-size: 0.9em;">
                    <div><strong>Periyot:</strong> ${item.query.period} gün</div>
                    <div><strong>Süre:</strong> ${item.query.duration} saat</div>
                    <div><strong>Derinlik:</strong> ${item.query.depth} ppm</div>
                    <div><strong>Parlaklık:</strong> ${item.query.star_mag}</div>
                </div>
                <div style="margin-top: 8px; text-align: center;">
                    <span style="color: #fff; font-weight: bold;">Skor: ${item.result.score}</span>
                    <span class="label-badge label-${item.result.label}" style="margin-left: 10px; font-size: 0.85em;">${item.result.label}</span>
                </div>
            </div>
        `;
    });
    
    html += '</div>';
    html += '<button onclick="clearHistory()" style="margin-top: 15px; background: rgba(255, 0, 0, 0.5);">🗑️ Geçmişi Temizle</button>';
    
    historyDiv.innerHTML = html;
}

function loadQueryFromHistory(index) {
    const history = loadHistory();
    const item = history[index];
    
    if (item) {
        document.getElementById('period').value = item.query.period;
        document.getElementById('duration').value = item.query.duration;
        document.getElementById('depth').value = item.query.depth;
        document.getElementById('star_mag').value = item.query.star_mag;
        document.getElementById('manualSource').value = item.query.source;
        
        // Sonucu göster
        document.getElementById('manualResult').innerHTML = `
            <div class="result-card">
                <h3>Sonuç (Geçmişten Yüklendi)</h3>
                <div class="score-display">${item.result.score}</div>
                <div style="text-align: center;">
                    <span class="label-badge label-${item.result.label}">${getLabelName(item.result.label)}</span>
                </div>
                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="stat-value">${item.result.period}</div>
                        <div class="stat-label">Periyot (gün)</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">${item.result.duration}</div>
                        <div class="stat-label">Süre (saat)</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">${item.result.depth}</div>
                        <div class="stat-label">Derinlik (ppm)</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">${item.result.star_mag}</div>
                        <div class="stat-label">Parlaklık (Mag)</div>
                    </div>
                </div>
            </div>
        `;
        document.getElementById('manual').scrollIntoView({ behavior: 'smooth' });
    }
}
        function showTab(tabName, el) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.content').forEach(c => c.classList.remove('active'));
            el.classList.add('active');
            document.getElementById(tabName).classList.add('active');
        }

        function getLabelName(label) {
            const names = {
                'CP': 'Confirmed Planet',
                'PC': 'Planet Candidate',
                'APC': 'Ambiguous Planet Candidate'
            };
            return names[label] || label;
        }
                async function calculateScore() {
    const period = parseFloat(document.getElementById('period').value);
    const duration = parseFloat(document.getElementById('duration').value);
    const depth = parseFloat(document.getElementById('depth').value);
    const star_mag = parseFloat(document.getElementById('star_mag').value);
    const source = document.getElementById('manualSource').value;

    if (isNaN(period) || isNaN(duration) || isNaN(depth) || isNaN(star_mag)) {
        alert('Lütfen tüm alanları doldurun!');
        return;
    }

    try {
        const response = await fetch('/api/calculate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ period, duration, depth, star_mag, source })
        });

        if (!response.ok) throw new Error('Hesaplama hatası');

        const data = await response.json();
        
        saveToHistory(
            { period, duration, depth, star_mag, source },
            data
        );
        
        displayHistory();
                document.getElementById('manualResult').innerHTML = `
                    <div class="result-card">
                        <h3>Sonuç</h3>
                        <div class="score-display">${data.score}</div>
                        <div style="text-align: center;">
                            <span class="label-badge label-${data.label}">${getLabelName(data.label)}</span>
                        </div>
                        <div class="stats-grid">
                            <div class="stat-card">
                                <div class="stat-value">${data.period}</div>
                                <div class="stat-label">Periyot (gün)</div>
                            </div>
                            <div class="stat-card">
                                <div class="stat-value">${data.duration}</div>
                                <div class="stat-label">Süre (saat)</div>
                            </div>
                            <div class="stat-card">
                                <div class="stat-value">${data.depth}</div>
                                <div class="stat-label">Derinlik (ppm)</div>
                            </div>
                            <div class="stat-card">
                                <div class="stat-value">${data.star_mag}</div>
                                <div class="stat-label">Parlaklık (Mag)</div>
                            </div>
                        </div>
                    </div>
                `;
            } catch (error) {
                document.getElementById('manualResult').innerHTML = `
                    <div class="error-message">Hata: ${error.message}</div>
                `;
            }
        }

            function clearManual() {
                document.getElementById('period').value = '';
                document.getElementById('duration').value = '';
                document.getElementById('depth').value = '';
                document.getElementById('star_mag').value = '';
                document.getElementById('manualResult').innerHTML = '';
                document.getElementById('manualSource').value = 'toi';
                }
        async function fetchNasaAuto() {
            const btn = document.getElementById('nasaBtn');
            btn.disabled = true;
            const source = document.getElementById('nasaSource').value;

            document.getElementById('nasaResult').innerHTML = `
                <div class="loading">
                    <div class="spinner"></div>
                    <p>${source.toUpperCase()} verileri indiriliyor ve analiz ediliyor...</p>
                </div>
            `;

            try {
                const response = await fetch(`/api/nasa_auto?source=${source}`);
                if (!response.ok) throw new Error('NASA bağlantı hatası');

                const result = await response.json();
                currentData = { type: source, data: result.data };
                displayResults('nasaResult', result.data, result.stats);
                document.getElementById('exportNasaBtn').style.display = 'inline-block';
            } catch (error) {
                document.getElementById('nasaResult').innerHTML = `
                    <div class="error-message">${error.message}</div>
                `;
            } finally {
                btn.disabled = false;
            }
        }

        async function analyzeFile() {
            const fileInput = document.getElementById('fileInput');
            if (!fileInput.files.length) {
                alert('Lütfen bir dosya seçin!');
                return;
            }

            const btn = document.getElementById('fileBtn');
            btn.disabled = true;

            document.getElementById('fileResult').innerHTML = `
                <div class="loading">
                    <div class="spinner"></div>
                    <p>Dosya analiz ediliyor...</p>
                </div>
            `;

            const formData = new FormData();
            formData.append('file', fileInput.files[0]);
            formData.append('source', document.getElementById('fileSource').value);

            try {
                const response = await fetch('/api/analyze_file', {
                    method: 'POST',
                    body: formData
                });

                if (!response.ok) {
                    const errorData = await response.json();
                    throw new Error(errorData.error || 'Dosya analiz hatası');
                }

                const result = await response.json();
                currentData = { type: 'file', data: result.data };
                displayResults('fileResult', result.data, result.stats);
                document.getElementById('exportFileBtn').style.display = 'inline-block';
            } catch (error) {
                document.getElementById('fileResult').innerHTML = `
                    <div class="error-message">Hata: ${error.message}</div>
                `;
            } finally {
                btn.disabled = false;
            }
        }

        function createClassificationChart(data, targetId) {
        // Sınıflandırma sayılarını hesaplayalım
        const counts = {
        'CP': 0,
        'PC': 0,
        'APC': 0
         };
    
        data.forEach(row => {
        counts[row.label]++;
        });
    
        // Canvas oluşturma
         const canvasId = `chart-${targetId}`;
        const chartHtml = `
        <div class="chart-container">
            <h4>📊 Sınıflandırma Dağılımı</h4>
            <div class="chart-wrapper">
                <canvas id="${canvasId}"></canvas>
            </div>
            <div style="text-align: center; margin-top: 15px; color: #aaa;">
                <span style="color: #00ff88;">■</span> CP: ${counts.CP} | 
                <span style="color: #ffaa00;">■</span> PC: ${counts.PC} | 
                <span style="color: #ff0055;">■</span> APC: ${counts.APC}
             </div>
         </div>
            `;
    
        return { html: chartHtml, counts, canvasId };
        }

        function renderChart(canvasId, counts) {
        const ctx = document.getElementById(canvasId);
        if (!ctx) return;
    
        new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: [
                'Confirmed Planet (CP)',
                'Planet Candidate (PC)',
                'Ambiguous Planet Candidate (APC)'
            ],
            datasets: [{
                data: [counts.CP, counts.PC, counts.APC],
                backgroundColor: [
                    'rgba(0, 255, 136, 0.8)',
                    'rgba(255, 170, 0, 0.8)',
                    'rgba(255, 0, 85, 0.8)'
                ],
                borderColor: [
                    'rgba(0, 255, 136, 1)',
                    'rgba(255, 170, 0, 1)',
                    'rgba(255, 0, 85, 1)'
                ],
                borderWidth: 2
            }]
             },
         options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        color: '#ffffff',
                        padding: 15,
                        font: {
                            size: 12
                        }
                    }
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const label = context.label || '';
                            const value = context.parsed || 0;
                            const total = context.dataset.data.reduce((a, b) => a + b, 0);
                            const percentage = ((value / total) * 100).toFixed(1);
                            return `${label}: ${value} (${percentage}%)`;
                        }
                    }
                }
            }
                }
             });
                }
                
        function displayResults(targetId, data, stats) {
         // Grafik verileri
        const chartData = createClassificationChart(data, targetId);
    
        let html = `
        <div class="result-card">
            <h3>Analiz Sonuçları</h3>
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-value">${stats.total}</div>
                    <div class="stat-label">Toplam Kayıt</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">${stats.mean}</div>
                    <div class="stat-label">Ortalama Skor</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">${stats.median}</div>
                    <div class="stat-label">Medyan</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">${stats.pass_rate}%</div>
                    <div class="stat-label">Geçme Oranı (≥80)</div>
                </div>
            </div>
            
            ${chartData.html}
            
            <h4>En İyi ${Math.min(100, data.length)} Aday</h4>
            <div class="data-table">
                <table>
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Skor</th>
                            <th>Label</th>
                            <th>Periyot</th>
                            <th>Süre</th>
                            <th>Derinlik</th>
                            <th>Parlaklık</th>
                        </tr>
                    </thead>
                    <tbody>
                    `;

            data.slice(0, 100).forEach(row => {
             html += `
            <tr>
                <td>${row.id}</td>
                <td><strong>${row.score}</strong></td>
                <td><span class="label-badge label-${row.label}">${row.label}</span></td>
                <td>${row.period}</td>
                <td>${row.duration}</td>
                <td>${row.depth}</td>
                <td>${row.star_mag}</td>
             </tr>
             `;
            });

        html += `</tbody></table></div></div>`;
        document.getElementById(targetId).innerHTML = html;
    
            // Grafik render 
            setTimeout(() => renderChart(chartData.canvasId, chartData.counts), 100);
            }
        async function exportResults(type) {
            if (!currentData || !currentData.data || currentData.data.length === 0) {
                alert('Dışa aktarılacak veri yok!');
                return;
            }

            try {
                const response = await fetch('/api/export', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ data: currentData.data })
                });

                if (!response.ok) throw new Error('Export hatası');

                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `exoplanet_results_${Date.now()}.xlsx`;
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                document.body.removeChild(a);

                alert('Excel dosyası başarıyla indirildi!');
            } catch (error) {
                alert('Dışa aktarma hatası: ' + error.message);
            }
        }
    </script>
</body>
</html>'''


# Routes
@app.route('/api/analyze_file', methods=['POST'])
def analyze_file():
    source = request.form.get('source', 'file')
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'Empty filename'}), 400

        if file.filename.endswith('.csv'):
            df = load_nasa_csv(file)
        elif file.filename.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(file)
        else:
            return jsonify({'error': 'Unsupported format'}), 400

        col_mapping = find_columns(df)

        #Otomatik kaynak algılama sistemi (TOI / KOI)
        if source == 'file':
            cols = [c.lower() for c in df.columns]

            if any('kepmag' in c or 'koi_' in c for c in cols):
                source = 'koi'
            elif any('tmag' in c or 'toi' in c for c in cols):
                source = 'toi'

        results = []
        for _, row in df.iterrows():
            try:
                period = safe_float(row[col_mapping['period']]) if 'period' in col_mapping else None
                duration = safe_float(row[col_mapping['duration']]) if 'duration' in col_mapping else None
                depth = safe_float(row[col_mapping['depth']]) if 'depth' in col_mapping else None
                star_mag = safe_float(row[col_mapping['star_mag']]) if 'star_mag' in col_mapping else None

                if None in [period, duration, depth, star_mag]:
                    continue

                score = calculate_score(period, duration, depth, star_mag, source)
                if score is None:
                    continue

                if 'id' in col_mapping:
                    raw_id = row[col_mapping['id']]
                    obj_id = f"FILE-{raw_id}"
                else:
                    obj_id = f"ROW-{_ + 1}"
                results.append({
                    'id': str(obj_id),
                    'period': round(period, 2),
                    'duration': round(duration, 2),
                    'depth': round(depth, 0),
                    'star_mag': round(star_mag, 2),
                    'score': round(score, 1),
                    'label': get_label(score)
                })
            except:
                continue

        results.sort(key=lambda x: x['score'], reverse=True)

        scores = [r['score'] for r in results]
        stats = {
            'total': len(results),
            'mean': round(np.mean(scores), 2) if scores else 0,
            'median': round(np.median(scores), 2) if scores else 0,
            'std': round(np.std(scores), 2) if scores else 0,
            'pass_rate': round((sum(1 for s in scores if s >= 80) / len(scores) * 100), 2) if scores else 0
        }

        return jsonify({'data': results, 'stats': stats})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/export', methods=['POST'])
def export_results():
    try:
        data = request.json.get('data', [])

        if not data:
            return jsonify({'error': 'No data'}), 400

        df = pd.DataFrame(data)

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Results')
        output.seek(0)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"exoplanet_results_{timestamp}.xlsx"

        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/')
def index():
    return HTML_TEMPLATE


@app.route('/api/calculate', methods=['POST'])
def calculate():
    try:
        data = request.json
        period = data.get('period')
        duration = data.get('duration')
        depth = data.get('depth')
        star_mag = data.get('star_mag')
        source = data.get('source', 'toi')

        score = calculate_score(period, duration, depth, star_mag, source)
        if score is None:
            return jsonify({'error': 'Invalid input'}), 400

        return jsonify({
            'score': round(score, 1),
            'label': get_label(score),
            'period': round(float(period), 2),
            'duration': round(float(duration), 2),
            'depth': round(float(depth), 1),
            'star_mag': round(float(star_mag), 2)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/nasa_auto', methods=['GET'])
def nasa_auto():
    try:
        source = request.args.get('source', 'toi')

        if source == 'toi':
            query = "select * from toi"
        elif source == 'koi':
            query = """SELECT kepid, koi_period, koi_duration, koi_depth, koi_kepmag FROM cumulative WHERE koi_disposition IN ('CANDIDATE','CONFIRMED') AND koi_period IS NOT NULL AND koi_duration IS NOT NULL AND koi_depth IS NOT NULL AND koi_kepmag IS NOT NULL """
        else:
            return jsonify({'error': 'Invalid data source'}), 400

        params = {
            'query': query,
            'format': 'csv'
        }

        r = requests.get(NASA_API_URL, params=params, timeout=60)
        r.raise_for_status()

        df = load_nasa_csv(io.StringIO(r.text))

        col_mapping = find_columns(df)
        results = []

        for _, row in df.iterrows():
            try:
                period = safe_float(row[col_mapping.get('period')])
                duration = safe_float(row[col_mapping.get('duration')])
                depth = safe_float(row[col_mapping.get('depth')])
                star_mag = safe_float(row[col_mapping.get('star_mag')])


                if None in [period, duration, depth, star_mag]:
                    continue

                score = calculate_score(period, duration, depth, star_mag, source)
                if score is None:
                    continue

                raw_id = row[col_mapping['id']]

                if source == 'toi':
                    obj_id = f"TOI-{raw_id}"
                elif source == 'koi':
                    obj_id = f"KOI-{raw_id}"
                else:
                    obj_id = str(raw_id)

                results.append({
                    'id': str(obj_id),
                    'period': round(period, 2),
                    'duration': round(duration, 2),
                    'depth': round(depth, 0),
                    'star_mag': round(star_mag, 2),
                    'score': round(score, 1),
                    'label': get_label(score)
                })
            except:
                continue

        results.sort(key=lambda x: x['score'], reverse=True)

        scores = [r['score'] for r in results]
        stats = {
            'total': len(results),
            'mean': round(np.mean(scores), 2) if scores else 0,
            'median': round(np.median(scores), 2) if scores else 0,
            'pass_rate': round(
                sum(1 for s in scores if s >= 80) / len(scores) * 100, 2
            ) if scores else 0
        }

        return jsonify({'data': results, 'stats': stats})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("    🛰️ ÖTEGEZEGEN TESPİT PLATFORMU")
    print("=" * 60)
    print("\n📌 Geliştirici: Hızır Kaan ERKAN, Fatma YALÇIN, Sefa GAKÇI, İrem ARIOĞLU")
    print("\n🚀 Server başlatılıyor...")
    print("🌐 URL: http://localhost:5000")
    print("\n💡 Özellikler:")
    print("   ✓ Manuel veri girişi")
    print("   ✓ NASA Ötegezegen Arşivi Analizi (TESS + Kepler)")
    print("   ✓ CSV/Excel dosya analizi")
    print("   ✓ Excel çıktısı")
    print("\n⏹️  Durdurmak için: Ctrl+C")
    print("=" * 60 + "\n")
