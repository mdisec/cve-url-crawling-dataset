import psycopg2
import requests
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import random


# Veritabanı bağlantısı
def init_db():
    return psycopg2.connect(
        host="localhost",
        database="cve_db",  # Veritabanı adını doğru girdiğinizden emin olun
        user="ilker",
        password="123456"
    )


# URL'yi çekme fonksiyonu
def fetch_url(url):
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            content_type = response.headers.get('Content-Type', '')
            if 'application/pdf' in content_type:
                return None  # PDF dosyalarını kaydetme
            return response.text  # HTML içeriği
    except Exception as e:
        print(f"Error fetching {url}: {e}")
    return None


# domain_resolved true olan URL'leri getir
def get_urls_to_process(conn):
    cursor = conn.cursor()
    cursor.execute(
        "SELECT DISTINCT url FROM cve_entries WHERE domain_resolved = true AND html_content IS NULL")
    return cursor.fetchall()


# URL işleme ve veritabanını güncelleme
def process_url(url, conn):
    content = fetch_url(url)
    cursor = conn.cursor()

    # HTML içeriği varsa güncelle, yoksa hata durumunu kaydet
    if content:
        cursor.execute('''
            UPDATE cve_entries 
            SET html_content = %s, last_updated = %s, status = %s 
            WHERE url = %s
        ''', (content, datetime.now(), 'success', url))
    else:
        cursor.execute('''
            UPDATE cve_entries 
            SET status = %s, last_updated = %s, error_message = %s 
            WHERE url = %s
        ''', ('failed', datetime.now(), 'Error fetching content', url))

    conn.commit()


# Ana fonksiyon
def main():
    conn = init_db()
    urls_to_process = get_urls_to_process(conn)

    if not urls_to_process:
        print("Domain resolved true olan işlenecek URL bulunamadı.")
        return

    # URL'leri rastgele karıştır
    random.shuffle(urls_to_process)

    total_urls = len(urls_to_process)
    processed_urls = 0

    print(f"{total_urls} URL işlenecek.")

    with ThreadPoolExecutor(max_workers=30) as executor:
        futures = {executor.submit(process_url, url[0], conn): url[0] for url in urls_to_process}

        for future in as_completed(futures):
            processed_urls += 1
            if processed_urls % 10 == 0 or processed_urls == total_urls:
                progress = (processed_urls / total_urls) * 100
                print(f"İşlenen URL: {processed_urls}/{total_urls} (%{progress:.2f})")

    conn.close()
    print("İşlem tamamlandı.")


if __name__ == "__main__":
    main()
