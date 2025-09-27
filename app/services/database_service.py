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
            cur.execute("SELECT content FROM documents WHERE hash = %s", (object_key,))
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


def get_contract_text_by_id(contract_id: str) -> Optional[str]:
    """
    Mengambil semua content dari contract_id dan menggabungkannya.
    Returns teks kontrak gabungan atau None jika tidak ditemukan.
    """
    conn = get_db_connection()
    if not conn:
        print("Failed to connect to database")
        return None
    
    try:
        with conn.cursor() as cur:
            # Ambil semua document_hash yang terkait dengan contract_id
            cur.execute("SELECT document_hash FROM contract_documents WHERE contract_id = %s", (contract_id,))
            hash_results = cur.fetchall()
            
            if not hash_results:
                print(f"No documents found for contract_id: {contract_id}")
                return None
            
            # Ambil content dari semua document_hash
            all_content = []
            for (document_hash,) in hash_results:
                cur.execute("SELECT content FROM documents WHERE hash = %s", (document_hash,))
                content_result = cur.fetchone()
                if content_result and content_result[0]:
                    all_content.append(content_result[0])
            
            if not all_content:
                print(f"No content found for contract_id: {contract_id}")
                return None
            
            # Gabungkan semua content dengan separator
            combined_text = "\n\n--- DOKUMEN BERIKUTNYA ---\n\n".join(all_content)
            print(f"Found {len(hash_results)} documents for contract_id: {contract_id}, total text length: {len(combined_text)} chars")
            return combined_text
                
    except Exception as e:
        print(f"Error retrieving contract text: {e}")
        return None
    finally:
        conn.close()


def get_chat_history(session_id: str, contract_id: str) -> List[Dict[str, str]]:
    """
    Mengambil riwayat chat untuk session_id dan contract_id tertentu.
    Returns list of dict dengan format [{"role": "user/assistant", "content": "..."}]
    """
    conn = get_db_connection()
    if not conn:
        print("Failed to connect to database")
        return []
    
    try:
        with conn.cursor() as cur:
            # Ambil chat history berdasarkan session_id dan contract_id
            cur.execute("""
                SELECT content, is_answer, created_at 
                FROM chats 
                WHERE contract_id = %s 
                ORDER BY created_at ASC
            """, (contract_id,))
            
            rows = cur.fetchall()
            chat_history = []
            
            for content, is_answer, created_at in rows:
                role = "assistant" if is_answer else "user"
                chat_history.append({
                    "role": role,
                    "content": content
                })
            
            print(f"Retrieved {len(chat_history)} chat messages for contract_id: {contract_id}")
            return chat_history
                
    except Exception as e:
        print(f"Error retrieving chat history: {e}")
        return []
    finally:
        conn.close()


def save_chat_message(session_id: str, contract_id: str, content: str, is_answer: bool) -> bool:
    """
    Menyimpan pesan chat ke database.
    Returns True jika berhasil, False jika gagal.
    """
    conn = get_db_connection()
    if not conn:
        print("Failed to connect to database")
        return False
    
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO chats (contract_id, content, is_answer) 
                VALUES (%s, %s, %s)
            """, (contract_id, content, is_answer))
            
            conn.commit()
            print(f"Saved chat message: {'answer' if is_answer else 'question'} for contract_id: {contract_id}")
            return True
                
    except Exception as e:
        print(f"Error saving chat message: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


def get_contract_documents_info(contract_id: str) -> List[Dict[str, str]]:
    """
    Mengambil informasi dokumen yang terkait dengan contract_id.
    Returns list of dict dengan informasi dokumen.
    """
    conn = get_db_connection()
    if not conn:
        print("Failed to connect to database")
        return []
    
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT cd.document_hash, cd.url, cd.category, d.meta_data, d.content
                FROM contract_documents cd
                JOIN documents d ON cd.document_hash = d.hash
                WHERE cd.contract_id = %s
                ORDER BY cd.created_at ASC
            """, (contract_id,))
            
            rows = cur.fetchall()
            documents = []
            
            for document_hash, url, category, meta_data, content in rows:
                documents.append({
                    "document_hash": document_hash,
                    "url": url,
                    "category": category,
                    "meta_data": meta_data,
                    "content": content[:500] + "..." if len(content) > 500 else content  # Preview content
                })
            
            print(f"Retrieved {len(documents)} documents for contract_id: {contract_id}")
            return documents
                
    except Exception as e:
        print(f"Error retrieving contract documents: {e}")
        return []
    finally:
        conn.close()