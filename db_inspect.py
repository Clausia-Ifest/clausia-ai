#!/usr/bin/env python3
"""
Script untuk melihat struktur database dan isinya
"""

from app.services.database_service import get_db_connection
import psycopg2

def inspect_database():
    """Inspeksi struktur dan isi database"""
    conn = get_db_connection()
    if not conn:
        print("❌ Tidak bisa terhubung ke database")
        return
    
    try:
        with conn.cursor() as cur:
            print("🔍 INSPEKSI DATABASE")
            print("=" * 50)
            
            # 1. Lihat semua tabel
            print("\n📋 DAFTAR TABEL:")
            cur.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                ORDER BY table_name;
            """)
            tables = cur.fetchall()
            
            if not tables:
                print("   Tidak ada tabel yang ditemukan")
                return
            
            for (table_name,) in tables:
                print(f"   - {table_name}")
            
            # 2. Untuk setiap tabel, tampilkan struktur dan sample data
            for (table_name,) in tables:
                print(f"\n📊 TABEL: {table_name}")
                print("-" * 30)
                
                # Struktur kolom
                print("   Kolom:")
                cur.execute("""
                    SELECT column_name, data_type, is_nullable, column_default
                    FROM information_schema.columns 
                    WHERE table_name = %s AND table_schema = 'public'
                    ORDER BY ordinal_position;
                """, (table_name,))
                
                columns = cur.fetchall()
                for col_name, data_type, nullable, default in columns:
                    null_str = "NULL" if nullable == "YES" else "NOT NULL"
                    default_str = f" DEFAULT {default}" if default else ""
                    print(f"     {col_name}: {data_type} {null_str}{default_str}")
                
                # Jumlah baris
                cur.execute(f"SELECT COUNT(*) FROM {table_name}")
                count = cur.fetchone()[0]
                print(f"   Jumlah baris: {count}")
                
                # Sample data (5 baris pertama)
                if count > 0:
                    print("   Sample data (5 baris pertama):")
                    cur.execute(f"SELECT * FROM {table_name} LIMIT 5")
                    rows = cur.fetchall()
                    
                    # Header kolom
                    col_names = [desc[0] for desc in cur.description]
                    print(f"     {' | '.join(col_names)}")
                    print(f"     {'-' * (len(' | '.join(col_names)))}")
                    
                    # Data rows
                    for row in rows:
                        # Potong string panjang untuk display
                        display_row = []
                        for val in row:
                            if isinstance(val, str) and len(val) > 50:
                                display_row.append(val[:47] + "...")
                            else:
                                display_row.append(str(val) if val is not None else "NULL")
                        print(f"     {' | '.join(display_row)}")
                
                print()
    
    except Exception as e:
        print(f"❌ Error inspecting database: {e}")
    finally:
        conn.close()


def check_contract_documents(contract_id: str = None):
    """Cek data spesifik contract_documents"""
    conn = get_db_connection()
    if not conn:
        print("❌ Tidak bisa terhubung ke database")
        return
    
    try:
        with conn.cursor() as cur:
            if contract_id:
                print(f"\n🔍 CONTRACT_DOCUMENTS untuk ID: {contract_id}")
                cur.execute("SELECT * FROM contract_documents WHERE id = %s", (contract_id,))
            else:
                print("\n🔍 SEMUA CONTRACT_DOCUMENTS:")
                cur.execute("SELECT * FROM contract_documents LIMIT 10")
            
            rows = cur.fetchall()
            if rows:
                col_names = [desc[0] for desc in cur.description]
                print(f"   {' | '.join(col_names)}")
                print(f"   {'-' * (len(' | '.join(col_names)) + 10)}")
                
                for row in rows:
                    print(f"   {' | '.join(str(val) if val else 'NULL' for val in row)}")
            else:
                print("   Tidak ada data ditemukan")
    
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        conn.close()


if __name__ == "__main__":
    print("🚀 Database Inspector")
    inspect_database()
    
    # Contoh cek contract tertentu (uncomment jika perlu)
    # check_contract_documents("sample-contract-id")
