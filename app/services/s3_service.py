import os
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv()

# Konfigurasi S3 compatible storage
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY")
S3_REGION = os.getenv("S3_REGION", "SouthJkt-a")
S3_ENDPOINT = os.getenv("S3_ENDPOINT", "https://is3.cloudhost.id")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")

# Inisialisasi S3 client
def get_s3_client():
    """Membuat S3 client dengan konfigurasi custom endpoint"""
    try:
        client = boto3.client(
            's3',
            aws_access_key_id=S3_ACCESS_KEY,
            aws_secret_access_key=S3_SECRET_KEY,
            region_name=S3_REGION,
            endpoint_url=S3_ENDPOINT
        )
        return client
    except Exception as e:
        print(f"Error creating S3 client: {e}")
        return None

def download_pdf_from_s3(object_key: str) -> bytes | None:
    """
    Download PDF file dari S3 berdasarkan object key/hash.
    Otomatis menambahkan prefix 'documents/' jika belum ada.
    Returns PDF bytes atau None jika gagal.
    """
    if not object_key or not object_key.strip():
        print("Object key is empty")
        return None
    
    # Tambahkan prefix documents/ jika belum ada
    if not object_key.startswith("documents/"):
        object_key = f"documents/{object_key}"
    
    client = get_s3_client()
    if not client:
        print("Failed to create S3 client")
        return None
    
    try:
        response = client.get_object(Bucket=S3_BUCKET_NAME, Key=object_key)
        pdf_bytes = response['Body'].read()
        print(f"Successfully downloaded {len(pdf_bytes)} bytes from S3 key: {object_key}")
        return pdf_bytes
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'NoSuchKey':
            print(f"Object not found in S3: {object_key}")
        elif error_code == 'AccessDenied':
            print(f"Access denied for S3 object: {object_key}")
        else:
            print(f"S3 ClientError: {e}")
        return None
    except Exception as e:
        print(f"Error downloading from S3: {e}")
        return None