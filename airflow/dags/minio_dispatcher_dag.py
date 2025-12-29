from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
import logging
import os
from minio import Minio
import psycopg2

# Import your pipelines (ensure python-etl is mounted into /opt/python-etl)
import sys
sys.path.insert(0, "/opt/python-etl")
from pipelines import structured_pipeline, pdf_pipeline, docx_pipeline, image_pipeline

logger = logging.getLogger(__name__)

# ENV-driven config
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "minio_datalake:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin123")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "lakehouse-data")

PG_HOST = os.getenv("POSTGRES_HOST", "postgres")
PG_DB = os.getenv("POSTGRES_DB", "lakehouse_db")
PG_USER = os.getenv("POSTGRES_USER", "lakehouse_user")
PG_PASS = os.getenv("POSTGRES_PASSWORD", "lakehouse_pass")
PG_PORT = os.getenv("POSTGRES_PORT", "5432")

# helper: check catalog for object_name
def is_processed_in_catalog(conn, bucket, object_name):
    cur = conn.cursor()
    try:
        cur.execute("SELECT 1 FROM minio_data_catalog WHERE bucket_name=%s AND object_name=%s LIMIT 1", (bucket, object_name))
        r = cur.fetchone()
        return bool(r)
    finally:
        cur.close()

def scan_and_dispatch(**context):
    # connect minio
    minio_client = Minio(MINIO_ENDPOINT, access_key=MINIO_ACCESS_KEY, secret_key=MINIO_SECRET_KEY, secure=False)
    # connect postgres
    pg_conn = psycopg2.connect(host=PG_HOST, database=PG_DB, user=PG_USER, password=PG_PASS, port=PG_PORT)
    try:
        # list objects under raw/
        objects = minio_client.list_objects(MINIO_BUCKET, prefix="raw/", recursive=True)
        for obj in objects:
            object_name = obj.object_name
            logger.info("Found object: %s", object_name)

            if is_processed_in_catalog(pg_conn, MINIO_BUCKET, object_name):
                logger.info("Already in catalog, skipping: %s", object_name)
                continue

            # detect type by path or extension
            ext = object_name.rsplit(".", 1)[-1].lower() if "." in object_name else ""
            if object_name.startswith("raw/structured") or ext in ("csv","json","parquet"):
                logger.info("Dispatching structured pipeline for %s", object_name)
                structured_pipeline.process_minio_object(minio_client, MINIO_BUCKET, object_name, pg_conn, lambda *a, **k: None)
            elif ext in ("pdf",):
                logger.info("Dispatching pdf pipeline for %s", object_name)
                pdf_pipeline.process_minio_object(minio_client, MINIO_BUCKET, object_name, pg_conn, lambda *a, **k: None)
            elif ext in ("docx","doc"):
                logger.info("Dispatching docx pipeline for %s", object_name)
                docx_pipeline.process_minio_object(minio_client, MINIO_BUCKET, object_name, pg_conn, lambda *a, **k: None)
            elif ext in ("png","jpg","jpeg","tiff"):
                logger.info("Dispatching image pipeline for %s", object_name)
                image_pipeline.process_minio_object(minio_client, MINIO_BUCKET, object_name, pg_conn, lambda *a, **k: None, do_ocr=False)
            else:
                logger.info("Unknown extension, skipping: %s", object_name)
    finally:
        pg_conn.close()

default_args = {
    "owner": "nimish",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=2),
}

with DAG(
    dag_id="minio_dispatcher",
    default_args=default_args,
    description="Scan MinIO raw/ and dispatch existing pipelines for unprocessed objects",
    schedule_interval=timedelta(minutes=5),
    start_date=datetime(2025, 1, 1),
    catchup=False,
    max_active_runs=1,
) as dag:

    scan_task = PythonOperator(
        task_id="scan_and_dispatch",
        python_callable=scan_and_dispatch,
        provide_context=True,
    )

    scan_task
