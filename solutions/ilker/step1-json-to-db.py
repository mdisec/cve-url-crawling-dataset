import psycopg2
import json
from datetime import datetime

# Veritabanı bağlantısı
def init_db():
    return psycopg2.connect(
        host="localhost",
        database="cve_db",
        user="ilker",
        password="123456"
    )

# JSON verisini okuma ve veritabanına ekleme
def process_json_data(json_data):
    conn = init_db()
    cursor = conn.cursor()

    for entry in json_data:
        cve_id = entry["cve_id"]
        for url in entry["urls"]:
            try:
                # URL'yi ve CVE ID'sini veritabanına kaydediyoruz
                cursor.execute("""
                    INSERT INTO cve_entries (cve_id, url, last_updated, status, domain_resolved) 
                    VALUES (%s, %s, %s, %s, %s)
                """, (cve_id, url, datetime.now(), 'pending', False))

                conn.commit()  # Değişiklikleri kaydet

            except Exception as e:
                print(f"Hata oluştu: {e}")
                conn.rollback()  # Hata durumunda geri al

    cursor.close()
    conn.close()

# JSON dosyasını okuma
def read_json_file(file_path):
    with open(file_path, 'r') as f:
        return json.load(f)

# Ana işlem
if __name__ == "__main__":
    # JSON dosyasının yolunu girin
    json_file_path = "../../dataset.json"  # JSON dosyasının yolu
    data = read_json_file(json_file_path)
    process_json_data(data)
    print("Veri başarıyla kaydedildi.")
