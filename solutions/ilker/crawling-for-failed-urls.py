import psycopg2
import requests
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed


# Veritabanı bağlantısı
def init_db():
    return psycopg2.connect(
        host="localhost",
        database="cve_content",
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


# Failed URL'leri getir
def get_failed_urls(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT id, cve_id, url FROM cve_urls WHERE status = 'failed'")
    return cursor.fetchall()


# URL işleme ve veritabanını güncelleme
def process_url(url_id, url, conn):
    content = fetch_url(url)
    cursor = conn.cursor()

    if content:
        cursor.execute('''
            UPDATE cve_urls 
            SET html_content = %s, last_updated = %s, status = %s 
            WHERE id = %s
        ''', (content, datetime.now(), 'success', url_id))
    else:
        cursor.execute('''
            UPDATE cve_urls 
            SET last_updated = %s 
            WHERE id = %s
        ''', (datetime.now(), url_id))

    conn.commit()


# Ana fonksiyon
def main():
    conn = init_db()
    failed_urls = get_failed_urls(conn)

    if not failed_urls:
        print("Failed olarak işaretlenmiş URL bulunamadı.")
        return

    total_urls = len(failed_urls)
    processed_urls = 0

    print(f"{total_urls} URL yeniden işlenecek.")

    with ThreadPoolExecutor(max_workers=30) as executor:
        futures = {executor.submit(process_url, url_id, url, conn): url_id for url_id, _, url in failed_urls}

        for future in as_completed(futures):
            processed_urls += 1
            if processed_urls % 10 == 0 or processed_urls == total_urls:
                progress = (processed_urls / total_urls) * 100
                print(f"İşlenen URL: {processed_urls}/{total_urls} (%{progress:.2f})")

    conn.close()
    print("İşlem tamamlandı.")


if __name__ == "__main__":
    main()
