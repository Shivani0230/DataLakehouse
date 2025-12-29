# airflow/dags/ingest_local_folder_dag.py

import os
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator
from minio import Minio

# Landing bucket (same as Flask uploader)
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin123")
MINIO_BUCKET = os.getenv("LANDING_BUCKET", "lakehouse-data")

LOCAL_FOLDER = "/opt/airflow/sample"


def ingest_local_files():
    client = Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=False,
    )

    # Ensure landing bucket exists
    if not client.bucket_exists(MINIO_BUCKET):
        client.make_bucket(MINIO_BUCKET)

    for fname in os.listdir(LOCAL_FOLDER):
        fpath = os.path.join(LOCAL_FOLDER, fname)

        if not os.path.isfile(fpath):
            continue

        object_name = f"raw/{fname}"

        with open(fpath, "rb") as f:
            size = os.path.getsize(fpath)
            client.put_object(
                MINIO_BUCKET,
                object_name,
                f,
                length=size,
                content_type="application/octet-stream",
            )

        print(f"[INGEST] Uploaded {fname} -> {MINIO_BUCKET}/raw/")
        os.remove(fpath)  # only after successful upload


default_args = {
    "owner": "airflow",
    "retries": 3,
    "retry_delay": timedelta(seconds=10),
}

with DAG(
    dag_id="ingestionDAG",  # <= your clean name for the ingestion DAG
    default_args=default_args,
    description="Loads files from local folder into MinIO landing raw/",
    schedule=timedelta(seconds=30),  # every 30 seconds
    start_date=datetime(2025, 1, 1),
    catchup=False,
) as dag:

    ingest_task = PythonOperator(
        task_id="ingest_local_folder",
        python_callable=ingest_local_files,
    )
