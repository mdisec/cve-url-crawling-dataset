import json
from datetime import datetime
import psycopg2
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

# Veritabanı bağlantısı
def init_db():
    conn = psycopg2.connect(
        host="localhost",
        database="cve_content",
        user="ilker",
        password="123456"
    )
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cve_urls (
            id SERIAL PRIMARY KEY,
            cve_id TEXT,
            url TEXT,
            html_content TEXT,
            last_updated TIMESTAMP,
            status TEXT DEFAULT 'pending'  -- 'success', 'failed'
        )
    ''')
    conn.commit()
    return conn

# URL'yi çekme fonksiyonu
def fetch_url(url):
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            content_type = response.headers.get('Content-Type', '')
            if 'application/pdf' in content_type:
                return None  # PDF dosyası, es geç
            return response.text  # HTML içeriği
        else:
            return None
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None

# URL işleme ve veritabanına kaydetme
def process_url(url, cve_id, conn):
    content = fetch_url(url)
    cursor = conn.cursor()
    if content:
        # HTML içeriği varsa kaydet
        cursor.execute('''
            INSERT INTO cve_urls 
            (cve_id, url, html_content, last_updated, status) 
            VALUES (%s, %s, %s, %s, %s)
        ''', (cve_id, url, content, datetime.now(), 'success'))
    else:
        # Çekilemeyen URL'leri işaretle
        cursor.execute('''
            INSERT INTO cve_urls 
            (cve_id, url, last_updated, status) 
            VALUES (%s, %s, %s, %s)
        ''', (cve_id, url, datetime.now(), 'failed'))
    conn.commit()

# Ana fonksiyon
def main():
    conn = init_db()
    with open('dataset.json', 'r') as f:
        cve_data = json.load(f)

    # Toplam URL sayısını hesapla
    total_urls = sum(len(item['urls']) for item in cve_data)
    processed_urls = 0

    # Paralel işleme için ThreadPoolExecutor kullan
    with ThreadPoolExecutor(max_workers=30) as executor:
        futures = []
        for item in cve_data:
            cve_id = item['cve_id']
            urls = item['urls']
            for url in urls:
                futures.append(executor.submit(process_url, url, cve_id, conn))

        # İlerleme bilgisini güncelle
        for future in as_completed(futures):
            processed_urls += 1
            if processed_urls % 100 == 0:
                progress = (processed_urls / total_urls) * 100
                print(f"İşlenen URL: {processed_urls}/{total_urls} (%{progress:.2f})")

    conn.close()
    print("Tüm URL'ler işlendi.")

if __name__ == "__main__":
    main()