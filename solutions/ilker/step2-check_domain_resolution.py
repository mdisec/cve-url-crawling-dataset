import psycopg2
import concurrent.futures
import socket
from urllib.parse import urlparse

# Veritabanı bağlantısını başlat
def init_db():
    return psycopg2.connect(
        host="localhost",
        database="cve_db",
        user="ilker",
        password="123456"
    )

# Domain'in çözümlenip çözümlenmediğini kontrol et
def check_domain_resolution(domain):
    try:
        socket.getaddrinfo(domain, None, proto=socket.IPPROTO_TCP)
        return domain, True
    except socket.gaierror:
        return domain, False

# Ana işlem
def process_domains():
    conn = init_db()
    cur = conn.cursor()

    # URL'leri veritabanından çek
    cur.execute("SELECT id, url FROM cve_entries")
    rows = cur.fetchall()

    # Domainleri tekilleştir ve ID'leri sakla
    domain_map = {}
    for row_id, url in rows:
        domain = urlparse(url).netloc
        if domain:
            domain_map.setdefault(domain, []).append(row_id)

    # Paralel çözümleme başlat (ThreadPoolExecutor kullanarak)
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        results = executor.map(check_domain_resolution, domain_map.keys())

    # Sonuçları güncelle
    for domain, resolved in results:
        ids = domain_map[domain]
        cur.execute(
            "UPDATE cve_entries SET domain_resolved = %s WHERE id = ANY(%s)",
            (resolved, ids)
        )

    conn.commit()
    cur.close()
    conn.close()

# Çalıştır
process_domains()
