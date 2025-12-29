# python-etl/pipelines/pdf_pipeline.py

import io
import logging
import hashlib

from minio import Minio
from pypdf import PdfReader
import pdfplumber
import pandas as pd
import psycopg2

logger = logging.getLogger(__name__)


def calculate_file_hash(data: bytes) -> str:
    """Return SHA-256 hash of a bytes buffer."""
    return hashlib.sha256(data).hexdigest()


def is_duplicate(pg_conn, content_hash: str) -> bool:
    """
    Check in minio_data_catalog if this hash already exists.
    If yes, we can skip heavy processing.
    """
    if pg_conn is None:
        return False

    cursor = pg_conn.cursor()
    try:
        cursor.execute(
            """
            SELECT 1 FROM minio_data_catalog
            WHERE content_hash = %s
            LIMIT 1
            """,
            (content_hash,),
        )
        return cursor.fetchone() is not None
    finally:
        cursor.close()


def _ensure_unstructured_table(pg_conn):
    """
    Make sure unstructured_documents table exists with all required columns.
    This is backward-compatible if the table was created earlier without certain columns.
    """
    cursor = pg_conn.cursor()
    try:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS unstructured_documents (
                id SERIAL PRIMARY KEY,
                object_name TEXT NOT NULL,
                file_type TEXT,
                text_content TEXT,
                content_hash TEXT UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        pg_conn.commit()
    except Exception:
        pg_conn.rollback()
        logger.exception("[pdf] Failed ensuring unstructured_documents table")
        raise
    finally:
        cursor.close()


def _save_unstructured_doc(
    pg_conn,
    object_name: str,
    file_type: str,
    text: str,
    content_hash: str,
):
    """
    Save raw extracted text + hash into unstructured_documents.
    Used for search / QA later.
    """
    _ensure_unstructured_table(pg_conn)
    cursor = pg_conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO unstructured_documents 
                (object_name, file_type, text_content, content_hash)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (content_hash) DO UPDATE
            SET text_content = EXCLUDED.text_content,
                object_name = EXCLUDED.object_name
            """,
            (object_name, file_type, text, content_hash),
        )
        pg_conn.commit()
        logger.info(f"[pdf] Saved text to unstructured_documents for {object_name}")
    except Exception:
        pg_conn.rollback()
        logger.exception("[pdf] Failed inserting into unstructured_documents")
        raise
    finally:
        cursor.close()


def _process_extracted_table(
    minio_client,
    bucket_name: str,
    table_df: pd.DataFrame,
    table_key: str,
    pg_conn,
    catalog_updater,
):
    """
    Process a single extracted table from PDF:
    1. Upload CSV to MinIO
    2. Create PostgreSQL table
    3. Update catalog
    """
    try:
        # 1. Upload CSV to MinIO
        csv_bytes = table_df.to_csv(index=False).encode("utf-8")
        minio_client.put_object(
            bucket_name,
            table_key,
            io.BytesIO(csv_bytes),
            length=len(csv_bytes),
            content_type="text/csv",
        )
        logger.info(f"[pdf] Uploaded table CSV -> {table_key}")

        # 2. Create sanitized table name for PostgreSQL
        from pipelines.structured_pipeline import sanitize_table_name, sanitize_column_name, infer_postgres_type
        
        table_name = sanitize_table_name(table_key)
        
        # Sanitize column names
        table_df.columns = [sanitize_column_name(col) for col in table_df.columns]
        
        # Handle duplicate column names
        cols = pd.Series(table_df.columns)
        for dup in cols[cols.duplicated()].unique():
            cols[cols == dup] = [f"{dup}_{i}" if i != 0 else dup for i in range(sum(cols == dup))]
        table_df.columns = cols
        
        # 3. Load to PostgreSQL
        cursor = pg_conn.cursor()
        
        # Drop existing table
        cursor.execute(f'DROP TABLE IF EXISTS "{table_name}"')
        
        # Create table with inferred types
        column_defs = []
        for col in table_df.columns:
            pg_type = infer_postgres_type(table_df[col])
            column_defs.append(f'"{col}" {pg_type}')
        
        create_sql = f'CREATE TABLE "{table_name}" ({", ".join(column_defs)})'
        cursor.execute(create_sql)
        logger.info(f"[pdf] Created table: {table_name}")
        
        # Bulk insert
        buffer = io.StringIO()
        table_df.to_csv(buffer, index=False, header=False, sep='\t', na_rep='\\N')
        buffer.seek(0)
        
        cursor.copy_expert(
            f'COPY "{table_name}" FROM STDIN WITH (FORMAT CSV, DELIMITER E\'\\t\', NULL \'\\N\')',
            buffer
        )
        
        pg_conn.commit()
        logger.info(f"[pdf] Loaded {len(table_df)} rows into {table_name}")
        cursor.close()

        # 4. Update catalog for the extracted table CSV
        catalog_updater(
            object_name=table_key,
            object_size=len(csv_bytes),
            file_format='csv',
            row_count=len(table_df),
            text_extracted=False,
            content_hash=None
        )

    except Exception as e:
        logger.exception(f"[pdf] Failed processing table {table_key}: {e}")
        if pg_conn:
            pg_conn.rollback()


def process_minio_object(
    minio_client: Minio,
    bucket_name: str,
    object_name: str,
    pg_conn,
    catalog_updater,
):
    """
    Main entry point for PDF processing.

    Steps:
    1. Downloads raw PDF from MinIO
    2. Computes SHA256 hash and checks for duplicates
    3. Extracts plain text with PyPDF
    4. Saves text to:
       - MinIO: processed/unstructured/text-extracted/<file>.txt
       - Postgres: unstructured_documents table
    5. Extracts tables with pdfplumber:
       - Uploads each as CSV to processed/structured/pdf-tables/<file>_table_X.csv
       - Creates PostgreSQL table for each
       - Updates catalog for each table
    6. Updates catalog for original PDF file
    """
    logger.info(f"[pdf] Processing {object_name}")

    # 1. Download from MinIO
    response = minio_client.get_object(bucket_name, object_name)
    data = response.read()
    response.close()
    response.release_conn()

    file_size = len(data)
    file_hash = calculate_file_hash(data)
    file_root = object_name.split("/")[-1].rsplit(".", 1)[0]

    # 2. Check for duplicates
    if is_duplicate(pg_conn, file_hash):
        logger.info(
            f"[pdf] Duplicate detected via content_hash, "
            f"skipping heavy processing: {object_name}"
        )
        # Still update catalog with basic info
        try:
            catalog_updater(
                object_name=object_name,
                object_size=file_size,
                file_format="pdf",
                row_count=0,
                text_extracted=False,
                content_hash=file_hash,
            )
        except Exception:
            logger.exception("[pdf] Failed catalog update for duplicate")
        return

    # 3. Extract text using pypdf
    logger.info(f"[pdf] Extracting text from PDF...")
    reader = PdfReader(io.BytesIO(data))
    full_text = ""
    page_count = len(reader.pages)
    
    for page_num, page in enumerate(reader.pages, 1):
        try:
            page_text = page.extract_text() or ""
            full_text += page_text
            if page_num % 10 == 0:
                logger.info(f"[pdf] Processed {page_num}/{page_count} pages")
        except Exception as e:
            logger.warning(f"[pdf] Failed to extract text from page {page_num}: {e}")
    
    logger.info(f"[pdf] Extracted {len(full_text)} characters of text from {page_count} pages")

    # 4. Upload text to MinIO
    if full_text.strip():
        text_bytes = full_text.encode("utf-8")
        text_path = f"processed/unstructured/text-extracted/{file_root}.txt"

        minio_client.put_object(
            bucket_name,
            text_path,
            io.BytesIO(text_bytes),
            length=len(text_bytes),
            content_type="text/plain",
        )
        logger.info(f"[pdf] Uploaded extracted text -> {text_path}")

        # 5. Save unstructured text to Postgres
        if pg_conn is not None:
            _save_unstructured_doc(
                pg_conn=pg_conn,
                object_name=object_name,
                file_type="pdf",
                text=full_text,
                content_hash=file_hash,
            )
    else:
        logger.warning(f"[pdf] No text extracted from {object_name}")

    # 6. Extract tables using pdfplumber
    logger.info(f"[pdf] Extracting tables from PDF...")
    table_count = 0
    total_rows = 0
    
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            for page_idx, page in enumerate(pdf.pages):
                try:
                    tables = page.extract_tables()
                    
                    if not tables:
                        continue
                    
                    for table_idx, table in enumerate(tables):
                        if not table or len(table) < 2:
                            logger.debug(f"[pdf] Skipping empty table on page {page_idx + 1}")
                            continue

                        # Convert to DataFrame (first row as header)
                        try:
                            df = pd.DataFrame(table[1:], columns=table[0])
                            
                            # Clean the dataframe
                            df = df.dropna(how='all')  # Remove empty rows
                            df = df.replace('', None)  # Replace empty strings with None
                            
                            if df.empty:
                                continue
                            
                            # Generate unique table key
                            table_key = (
                                f"processed/structured/pdf-tables/"
                                f"{file_root}_page{page_idx + 1}_table{table_idx + 1}.csv"
                            )

                            # Process this table
                            _process_extracted_table(
                                minio_client=minio_client,
                                bucket_name=bucket_name,
                                table_df=df,
                                table_key=table_key,
                                pg_conn=pg_conn,
                                catalog_updater=catalog_updater,
                            )

                            table_count += 1
                            total_rows += len(df)
                            logger.info(
                                f"[pdf] Processed table {table_count}: "
                                f"{len(df)} rows, {len(df.columns)} columns"
                            )
                            
                        except Exception as table_error:
                            logger.warning(
                                f"[pdf] Failed to process table {table_idx + 1} "
                                f"on page {page_idx + 1}: {table_error}"
                            )
                            
                except Exception as page_error:
                    logger.warning(f"[pdf] Error processing page {page_idx + 1}: {page_error}")
                    
    except Exception as e:
        logger.exception(f"[pdf] Error during table extraction (pdfplumber): {e}")

    logger.info(f"[pdf] Extracted {table_count} tables with {total_rows} total rows")

    # 7. Update catalog for original PDF file
    try:
        catalog_updater(
            object_name=object_name,
            object_size=file_size,
            file_format="pdf",
            row_count=table_count,
            text_extracted=bool(full_text.strip()),
            content_hash=file_hash,
        )
        logger.info(f"[pdf] Updated catalog for {object_name}")
    except Exception as e:
        logger.exception(f"[pdf] Failed catalog update for {object_name}: {e}")
        raise

    logger.info(
        f"[pdf] ✅ Completed processing: {object_name} | "
        f"pages={page_count} | tables={table_count} | rows={total_rows} | "
        f"text_chars={len(full_text)}"
    )