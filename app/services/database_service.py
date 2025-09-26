import psycopg2
from psycopg2 import sql
import os
from dotenv import load_dotenv
from typing import Dict, List, Optional

load_dotenv()

def get_db_connection():
    """Membaca kredensial dari .env dan membuat koneksi PostgreSQL."""
    try:
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            dbname=os.getenv("DB_NAME")
        )
        return conn
    except Exception as e:
        print(f"Error connecting to the database: {e}")
        return None

def save_contract_data(contract_id: str, extracted_text: str, metadata: Dict, risks: List[Dict], recommendations: List[str]):
    """
    Menyimpan data kontrak yang telah dianalisis ke basis data.
    """
    conn = get_db_connection()
    if conn:
        with conn.cursor() as cur:
            try:
                # Pastikan tabel ada. Gunakan JSONB untuk menyimpan struktur data kompleks.
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS contracts (
                        id VARCHAR(255) PRIMARY KEY,
                        full_text TEXT,
                        metadata JSONB,
                        risks JSONB,
                        recommendations JSONB
                    );
                """)
                
                # Masukkan data
                query = sql.SQL("""
                    INSERT INTO contracts (id, full_text, metadata, risks, recommendations)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO NOTHING;
                """)
                
                # Konversi data Python ke string JSON untuk penyimpanan JSONB
                cur.execute(query, (
                    contract_id, 
                    extracted_text, 
                    json.dumps(metadata), 
                    json.dumps(risks), 
                    json.dumps(recommendations)
                ))
                conn.commit()
                print(f"Contract ID {contract_id} data saved successfully!")
            except Exception as e:
                print(f"Error saving data to database: {e}")
            finally:
                conn.close()


def get_contract_text_by_object_key(object_key: str) -> Optional[str]:
    """
    Mengambil teks kontrak yang sudah di-OCR dari database berdasarkan object_key.
    Returns teks kontrak atau None jika tidak ditemukan.
    """
    conn = get_db_connection()
    if not conn:
        print("Failed to connect to database")
        return None
    
    try:
        with conn.cursor() as cur:
            # Cari berdasarkan object_key (asumsi object_key = contract_id)
            cur.execute("SELECT content FROM contracts WHERE hash = %s", (object_key,))
            result = cur.fetchone()
            
            if result:
                print(f"Found contract text for object_key: {object_key}")
                return result[0]
            else:
                print(f"Contract not found in database for object_key: {object_key}")
                return None
                
    except Exception as e:
        print(f"Error retrieving contract text: {e}")
        return None
    finally:
        conn.close()