# python-etl/uploader_app.py
import os
import io
import logging
import psycopg2
from flask import Flask, request, jsonify, render_template, send_from_directory
from werkzeug.utils import secure_filename
from minio import Minio
from pipelines import structured_pipeline, pdf_pipeline, docx_pipeline, image_pipeline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BUCKET = os.getenv('MINIO_BUCKET', 'lakehouse-data')
ALLOWED_EXT = {
    'csv': 'structured',
    'json': 'structured',
    'parquet': 'structured',
    'pdf': 'pdf',
    'docx': 'docx',
    'doc': 'docx',
    'png': 'image',
    'jpg': 'image',
    'jpeg': 'image',
    'tiff': 'image',
}
MAX_CONTENT_LENGTH = 200 * 1024 * 1024  # 200MB example

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

minio_client = Minio(
    os.getenv('MINIO_ENDPOINT', 'minio:9000'),
    access_key=os.getenv('MINIO_ACCESS_KEY', 'minioadmin'),
    secret_key=os.getenv('MINIO_SECRET_KEY', 'minioadmin123'),
    secure=False
)

pg_conn = psycopg2.connect(
    host=os.getenv('POSTGRES_HOST', 'postgres'),
    database=os.getenv('POSTGRES_DB', 'lakehouse_db'),
    user=os.getenv('POSTGRES_USER', 'lakehouse_user'),
    password=os.getenv('POSTGRES_PASSWORD', 'lakehouse_pass')
)
pg_conn.autocommit = False

# helper: catalog updater
def update_catalog(bucket, object_name, object_size=None, file_format=None, row_count=None, text_extracted=False):
    cursor = pg_conn.cursor()
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS minio_data_catalog (
                catalog_id SERIAL PRIMARY KEY,
                bucket_name TEXT NOT NULL,
                object_name TEXT NOT NULL,
                object_size BIGINT,
                file_format TEXT,
                row_count INTEGER,
                text_extracted BOOLEAN DEFAULT FALSE,
                last_modified TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(bucket_name, object_name)
            )
        """)
        cursor.execute("""
            INSERT INTO minio_data_catalog (bucket_name, object_name, object_size, file_format, row_count, text_extracted)
            VALUES (%s,%s,%s,%s,%s,%s)
            ON CONFLICT (bucket_name, object_name) DO UPDATE
            SET object_size = EXCLUDED.object_size,
                file_format = EXCLUDED.file_format,
                row_count = EXCLUDED.row_count,
                text_extracted = EXCLUDED.text_extracted,
                last_modified = CURRENT_TIMESTAMP
        """, (bucket, object_name, object_size, file_format, row_count, text_extracted))
        pg_conn.commit()
    except Exception:
        pg_conn.rollback()
        logger.exception("Failed updating catalog")
        raise
    finally:
        cursor.close()

# @app.route('/upload', methods=['POST'])
# def upload_file():
#     if 'file' not in request.files:
#         return jsonify({"error": "No file part"}), 400
#     file = request.files['file']
#     if file.filename == '':
#         return jsonify({"error": "No selected file"}), 400
#     filename = secure_filename(file.filename)
#     ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
#     file_type = ALLOWED_EXT.get(ext)
#     if not file_type:
#         return jsonify({"error": f"Extension .{ext} not supported as of now."}), 400

#     # construct object name under raw/
#     object_name = f"raw/{file_type}/{filename}"
#     data = file.read()
#     # upload to MinIO
#     try:
#         minio_client.put_object(BUCKET, object_name, io.BytesIO(data), length=len(data), content_type=file.content_type)
#         logger.info(f"Uploaded file to MinIO at {object_name}")
#         # update catalog with size
#         update_catalog(BUCKET, object_name, object_size=len(data), file_format=file_type)
#     except Exception:
#         logger.exception("Failed uploading to MinIO")
#         return jsonify({"error": "upload failed"}), 500

#     # Dispatch to pipeline synchronously
#     try:
#         if file_type == 'structured':
#             structured_pipeline.process_minio_object(minio_client, BUCKET, object_name, pg_conn, update_catalog)
#         elif file_type == 'pdf':
#             pdf_pipeline.process_minio_object(minio_client, BUCKET, object_name, pg_conn, update_catalog)
#         elif file_type == 'docx':
#             docx_pipeline.process_minio_object(minio_client, BUCKET, object_name, pg_conn, update_catalog)
#         elif file_type == 'image':
#             # pass do_ocr flag if you want OCR; could be read from request form
#             do_ocr = request.form.get('ocr', 'false').lower() == 'true'
#             image_pipeline.process_minio_object(minio_client, BUCKET, object_name, pg_conn, update_catalog, do_ocr=do_ocr)
#         else:
#             # fallback
#             update_catalog(BUCKET, object_name, file_format=file_type)
#     except Exception:
#         # pipeline error; client should be informed
#         return jsonify({"error": "processing failed"}), 500

#     return jsonify({"status": "ok", "object": object_name}), 200

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    filename = secure_filename(file.filename)
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    file_type = ALLOWED_EXT.get(ext)

    if not file_type:
        return jsonify({"error": f"Extension .{ext} not supported"}), 400

    object_name = f"raw/{file_type}/{filename}"
    data = file.read()

    try:
        minio_client.put_object(
            BUCKET,
            object_name,
            io.BytesIO(data),
            length=len(data),
            content_type=file.content_type
        )
        logger.info(f"Uploaded file to MinIO at {object_name}")
        
        # Only catalog upload, NOT processed metadata
        update_catalog(BUCKET, object_name, object_size=len(data), file_format=file_type)
    except Exception:
        logger.exception("Failed uploading to MinIO")
        return jsonify({"error": "upload failed"}), 500

    # NO PROCESSING HERE ANYMORE
    return jsonify({"status": "ok", "object": object_name}), 200


if __name__ == "__main__":
    # ensure bucket exists
    if not minio_client.bucket_exists(BUCKET):
        minio_client.make_bucket(BUCKET)
    app.run(host="0.0.0.0", port=int(os.getenv('UPLOAD_PORT', 5000)))
