import psycopg2
import requests
import asyncio
import socket
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse


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


# DNS çözümleme fonksiyonu
async def check_domain_resolution(domain):
    loop = asyncio.get_event_loop()
    try:
        await loop.getaddrinfo(domain, None, proto=socket.IPPROTO_TCP)
        return domain, True
    except socket.gaierror:
        return domain, False


# Domain çözümleme sonucunu cve_urls tablosunda güncelleme
def update_domain_resolution_status(conn, resolved_domains, unresolved_domains):
    cursor = conn.cursor()

    # Çözümleme sonucu başarıyla gerçekleşmiş domain'leri güncelle
    for domain in resolved_domains:
        cursor.execute("""
            UPDATE cve_urls
            SET domain_resolved = TRUE
            WHERE url LIKE %s
        """, (f"%{domain}%",))

    # Çözümleme sonucu başarısız olan domain'leri güncelle
    for domain in unresolved_domains:
        cursor.execute("""
            UPDATE cve_urls
            SET domain_resolved = FALSE
            WHERE url LIKE %s
        """, (f"%{domain}%",))

    conn.commit()


# URL işleme ve veritabanını güncelleme fonksiyonu
def process_url(url, conn, cve_url_map):
    content = fetch_url(url)
    cursor = conn.cursor()
    last_updated = datetime.now()

    # Eğer domain çözümleme başarılıysa HTML içeriğini çek
    domain = urlparse(url).netloc
    cursor.execute("""
        SELECT domain_resolved FROM cve_urls WHERE url LIKE %s LIMIT 1
    """, (f"%{domain}%",))
    domain_resolved = cursor.fetchone()

    if domain_resolved and domain_resolved[0]:  # Eğer domain çözümlemesi başarılıysa
        if content:
            # URL'nin bulunduğu tüm satırlara HTML içeriğini ekle
            for url_id in cve_url_map[url]:
                cursor.execute('''
                    UPDATE cve_urls 
                    SET html_content = %s, last_updated = %s, status = %s, domain_resolved = %s
                    WHERE id = %s
                ''', (content, last_updated, 'success', True, url_id))
        else:
            # İçerik çekilemediyse sadece güncelleme yap
            for url_id in cve_url_map[url]:
                cursor.execute('''
                    UPDATE cve_urls 
                    SET last_updated = %s, domain_resolved = %s 
                    WHERE id = %s
                ''', (last_updated, False, url_id))
    else:  # Eğer domain çözümlemesi başarısızsa
        for url_id in cve_url_map[url]:
            cursor.execute('''
                UPDATE cve_urls 
                SET last_updated = %s, domain_resolved = %s 
                WHERE id = %s
            ''', (last_updated, False, url_id))

    conn.commit()


# Veritabanına yeni sütun ekleme
def add_column_if_not_exists(conn):
    cursor = conn.cursor()
    cursor.execute("""
        DO $$
        BEGIN
            -- html_content sütunu ekleme kontrolü
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'cve_urls' AND column_name = 'html_content') THEN
                ALTER TABLE cve_urls ADD COLUMN html_content TEXT;
            END IF;
            -- last_updated sütunu ekleme kontrolü
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'cve_urls' AND column_name = 'last_updated') THEN
                ALTER TABLE cve_urls ADD COLUMN last_updated TIMESTAMP;
            END IF;
            -- status sütunu ekleme kontrolü
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'cve_urls' AND column_name = 'status') THEN
                ALTER TABLE cve_urls ADD COLUMN status VARCHAR(50);
            END IF;
            -- domain_resolved sütunu ekleme kontrolü
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'cve_urls' AND column_name = 'domain_resolved') THEN
                ALTER TABLE cve_urls ADD COLUMN domain_resolved BOOLEAN DEFAULT FALSE;
            END IF;
        END
        $$;
    """)
    conn.commit()


# Ana fonksiyon
def main():
    conn = init_db()

    # Yeni sütunlar
    add_column_if_not_exists(conn)

    failed_urls = get_failed_urls(conn)

    if not failed_urls:
        print("Failed olarak işaretlenmiş URL bulunamadı.")
        return

    # Unique URL ve CVE eşlemesi oluşturma
    cve_url_map = {}
    unique_urls = set()
    unique_domains = set()

    for url_id, cve_id, url in failed_urls:
        if url not in cve_url_map:
            cve_url_map[url] = []
        cve_url_map[url].append(url_id)
        unique_urls.add(url)
        unique_domains.add(urlparse(url).netloc)

    unique_urls = list(unique_urls)
    unique_domains = list(unique_domains)

    print(f"Toplam benzersiz URL: {len(unique_urls)}")

    # Domain çözümleme
    loop = asyncio.get_event_loop()
    results = loop.run_until_complete(asyncio.gather(*[check_domain_resolution(domain) for domain in unique_domains]))

    resolved_domains = {domain for domain, resolved in results if resolved}
    unresolved_domains = {domain for domain, resolved in results if not resolved}

    # Domain çözümleme sonuçlarını cve_urls tablosuna kaydet
    update_domain_resolution_status(conn, resolved_domains, unresolved_domains)

    # Domain çözümlemesi başarılı olan URL'leri işleme
    total_urls = len(unique_urls)
    processed_urls = 0

    with ThreadPoolExecutor(max_workers=30) as executor:
        futures = {executor.submit(process_url, url, conn, cve_url_map): url for url in unique_urls}

        for future in as_completed(futures):
            processed_urls += 1
            if processed_urls % 10 == 0 or processed_urls == total_urls:
                progress = (processed_urls / total_urls) * 100
                print(f"İşlenen URL: {processed_urls}/{total_urls} (%{progress:.2f})")

    conn.close()
    print("İşlem tamamlandı.")


if __name__ == "__main__":
    main()
