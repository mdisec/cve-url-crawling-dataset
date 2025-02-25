import json
from datetime import datetime
import asyncio
import requests
from playwright.async_api import async_playwright
import psycopg2

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
            last_updated TIMESTAMP
        )
    ''')
    conn.commit()
    return conn

# Playwright ile HTML içeriği çekme
async def fetch_with_playwright(url, browser):
    try:
        page = await browser.new_page()
        # 'networkidle' yerine 'load' kullanarak daha hızlı yükleme
        await page.goto(url, wait_until='load', timeout=30000)  # 30 saniye timeout
        content_type = await page.evaluate('''() => {
            return document.contentType;
        }''')
        if content_type == 'application/pdf':
            await page.close()
            return None  # PDF dosyası, es geç
        html_content = await page.content()
        await page.close()
        return html_content  # HTML içeriği
    except Exception as e:
        print(f"Playwright Error: {e}")
        return None
    finally:
        await page.close()  # Sayfayı kapat

# Requests ile HTML içeriği çekme
async def fetch_with_requests(url):
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
        print(f"Requests Error: {e}")
        return None

# Wayback Machine'den HTML içeriği çekme
async def get_wayback_content(url):
    try:
        wayback_url = f"https://web.archive.org/web/{datetime.now().strftime('%Y%m%d')}000000id_/{url}"
        response = requests.get(wayback_url, timeout=10)
        if response.status_code == 200 and 'Archive' not in response.text:
            return response.text  # HTML içeriği
        else:
            return None
    except Exception as e:
        print(f"Wayback Error: {e}")
        return None

# URL işleme fonksiyonu
async def process_url(url, browser, semaphore):
    async with semaphore:
        # Önce PDF olup olmadığını kontrol et
        if url.lower().endswith('.pdf'):
            return None  # PDF dosyası, es geç

        content = await fetch_with_playwright(url, browser)
        if not content:
            content = await fetch_with_requests(url)
        if not content:
            content = await get_wayback_content(url)
        return content

# URL işleme ve veritabanına kaydetme
async def process_url_and_save(url, cve_id, conn, browser, semaphore, processed_urls, total_urls):
    content = await process_url(url, browser, semaphore)
    if content:  # Sadece HTML içeriği varsa kaydet
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO cve_urls 
            (cve_id, url, html_content, last_updated) 
            VALUES (%s, %s, %s, %s)
        ''', (cve_id, url, content, datetime.now()))
        conn.commit()

    # İlerleme bilgisini güncelle (her 100 URL'de bir)
    processed_urls[0] += 1
    if processed_urls[0] % 100 == 0:
        progress = (processed_urls[0] / total_urls) * 100
        print(f"İşlenen URL: {processed_urls[0]}/{total_urls} (%{progress:.2f})")

# Ana fonksiyon
async def main():
    conn = init_db()
    with open('dataset.json', 'r') as f:
        cve_data = json.load(f)

    # Toplam URL sayısını hesapla
    total_urls = sum(len(item['urls']) for item in cve_data)
    processed_urls = [0]  # İşlenen URL sayısını takip etmek için liste kullanıyoruz

    # Playwright tarayıcısını başlat
    async with async_playwright() as p:
        browser = await p.chromium.launch()

        # Aynı anda en fazla 10 URL işlenecek
        semaphore = asyncio.Semaphore(10)

        # Tüm CVE'lerin URL'lerini paralel olarak işle
        tasks = []
        for item in cve_data:
            cve_id = item['cve_id']
            urls = item['urls']
            for url in urls:
                task = asyncio.create_task(process_url_and_save(url, cve_id, conn, browser, semaphore, processed_urls, total_urls))
                tasks.append(task)
        await asyncio.gather(*tasks)

    conn.close()

if __name__ == "__main__":
    asyncio.run(main())