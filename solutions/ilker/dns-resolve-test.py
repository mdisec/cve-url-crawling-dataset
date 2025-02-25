import psycopg2
import socket


# Veritabanı bağlantısı
def init_db():
    return psycopg2.connect(
        host="localhost",
        database="cve_db",
        user="ilker",
        password="123456"
    )


# DNS çözümlemesi yapma
def check_dns_resolve(url):
    try:
        # URL'yi hostname'e ayırıyoruz
        hostname = url.split('/')[2]
        # DNS çözümleme
        socket.gethostbyname(hostname)
        return True  # Çözümleme başarılı
    except socket.error:
        return False  # Çözümleme başarısız


# Domain resolve olanları kontrol et ve güncelle
def update_domain_resolve(conn):
    cursor = conn.cursor()
    # 'pending' statüsüne sahip URL'leri çekiyoruz (hem 'success' hem 'failed' olmayanlar)
    cursor.execute("SELECT id, url FROM cve_entries WHERE status NOT IN ('success', 'failed')")
    urls = cursor.fetchall()

    for url_id, url in urls:
        # DNS çözümlemesi yapıyoruz
        is_resolved = check_dns_resolve(url)

        # Domain çözümlemesi başarılıysa, 'domain_resolved' sütununu true yapıyoruz
        cursor.execute('''
            UPDATE cve_entries
            SET domain_resolved = %s
            WHERE id = %s
        ''', (is_resolved, url_id))

    conn.commit()
    print("DNS çözümleme işlemi tamamlandı.")


# Ana fonksiyon
def main():
    conn = init_db()

    update_domain_resolve(conn)

    conn.close()
    print("İşlem tamamlandı.")


if __name__ == "__main__":
    main()
