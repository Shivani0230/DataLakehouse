# python-etl/pipelines/structured_pipeline.py

import io
import csv
import pandas as pd
import chardet
from psycopg2.extras import execute_values
import logging
import re

logger = logging.getLogger(__name__)

def detect_encoding(byte_data, sample_size=10000):
    """Detect file encoding using chardet"""
    sample = byte_data[:sample_size]
    result = chardet.detect(sample)
    encoding = result.get('encoding', 'utf-8')
    confidence = result.get('confidence', 0)
    logger.info(f"Detected encoding: {encoding} (confidence: {confidence:.2f})")
    
    # Fallback encodings if confidence is low
    if confidence < 0.7:
        fallback_encodings = ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252']
        logger.warning(f"Low confidence encoding detection. Will try fallbacks: {fallback_encodings}")
        return fallback_encodings
    
    return [encoding] if encoding else ['utf-8']


def detect_delimiter(text_sample, max_sample=5000):
    """Enhanced delimiter detection with multiple strategies"""
    sample = text_sample[:max_sample]
    
    # Try csv.Sniffer first
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=',;\t|')
        delimiter = dialect.delimiter
        logger.info(f"Sniffer detected delimiter: {repr(delimiter)}")
        return delimiter
    except Exception as e:
        logger.warning(f"Sniffer failed: {e}. Using fallback detection.")
    
    # Fallback: count occurrences of common delimiters
    delimiters = [',', ';', '\t', '|', ':']
    lines = sample.split('\n')[:10]  # Check first 10 lines
    
    if not lines:
        return ','
    
    delimiter_counts = {d: [] for d in delimiters}
    
    for line in lines:
        if line.strip():
            for delim in delimiters:
                delimiter_counts[delim].append(line.count(delim))
    
    # Find delimiter with most consistent count across lines
    best_delimiter = ','
    best_score = 0
    
    for delim, counts in delimiter_counts.items():
        if not counts or all(c == 0 for c in counts):
            continue
        
        # Check consistency (same count in each line)
        avg_count = sum(counts) / len(counts)
        if avg_count > 0:
            variance = sum((c - avg_count) ** 2 for c in counts) / len(counts)
            score = avg_count / (1 + variance)  # Reward consistency
            
            if score > best_score:
                best_score = score
                best_delimiter = delim
    
    logger.info(f"Fallback detected delimiter: {repr(best_delimiter)}")
    return best_delimiter


def sanitize_column_name(col):
    """Sanitize column names for PostgreSQL compatibility"""
    # Remove or replace special characters
    col = str(col).strip()
    # Replace spaces and special chars with underscore
    col = re.sub(r'[^\w\s]', '_', col)
    col = re.sub(r'\s+', '_', col)
    # Remove leading/trailing underscores
    col = col.strip('_')
    # Ensure it doesn't start with a number
    if col and col[0].isdigit():
        col = 'col_' + col
    # Handle empty column names
    if not col:
        col = 'unnamed_column'
    # Lowercase for consistency
    col = col.lower()
    return col


def sanitize_table_name(object_name):
    """Create valid PostgreSQL table name from object path"""
    # Extract filename without path
    filename = object_name.split('/')[-1]
    # Remove extension
    table_name = filename.rsplit('.', 1)[0]
    # Sanitize
    table_name = re.sub(r'[^\w]', '_', table_name)
    table_name = table_name.strip('_').lower()
    
    # Add prefix to ensure uniqueness and avoid reserved words
    table_name = f"data_{table_name}"
    
    # Truncate if too long (PostgreSQL limit is 63 chars)
    if len(table_name) > 63:
        table_name = table_name[:63]
    
    logger.info(f"Table name: {table_name}")
    return table_name


def infer_postgres_type(series):
    """Infer PostgreSQL data type from pandas Series"""
    # Try to convert to numeric
    try:
        pd.to_numeric(series, errors='raise')
        if series.dtype == 'int64':
            return 'BIGINT'
        else:
            return 'NUMERIC'
    except (ValueError, TypeError):
        pass
    
    # Try to convert to datetime
    try:
        pd.to_datetime(series, errors='raise')
        return 'TIMESTAMP'
    except (ValueError, TypeError):
        pass
    
    # Check if boolean
    unique_vals = series.dropna().unique()
    if len(unique_vals) <= 2 and all(str(v).lower() in ['true', 'false', '1', '0', 'yes', 'no'] for v in unique_vals):
        return 'BOOLEAN'
    
    # Default to TEXT
    return 'TEXT'


def process_minio_object(minio_client, bucket_name, object_name, pg_conn, catalog_updater):
    """
    Main entry point for structured data processing.
    Called by etl_manager.run_pipeline_for_object()
    
    Handles CSV, JSON, Parquet files.
    """
    logger.info(f"[structured] Processing {object_name}")
    resp = None

    try:
        # 1. Read raw data from MinIO
        resp = minio_client.get_object(bucket_name, object_name)
        data = resp.read()
        logger.info(f"[structured] Downloaded {len(data)} bytes")

        # 2. Detect encoding
        encodings = detect_encoding(data)
        
        df = None
        last_error = None
        
        # 3. Try reading with different encodings
        for encoding in encodings:
            try:
                logger.info(f"[structured] Attempting to decode with {encoding}")
                text = data.decode(encoding)
                
                # 4. Detect delimiter
                delimiter = detect_delimiter(text)
                
                # 5. Read CSV with pandas - multiple attempts with different parameters
                read_attempts = [
                    # Attempt 1: Standard read
                    {
                        'sep': delimiter,
                        'engine': 'python',
                        'encoding': encoding,
                        'on_bad_lines': 'skip',
                        'quoting': csv.QUOTE_MINIMAL
                    },
                    # Attempt 2: More lenient
                    {
                        'sep': delimiter,
                        'engine': 'python',
                        'encoding': encoding,
                        'on_bad_lines': 'skip',
                        'quoting': csv.QUOTE_ALL,
                        'escapechar': '\\'
                    },
                    # Attempt 3: No quoting
                    {
                        'sep': delimiter,
                        'engine': 'python',
                        'encoding': encoding,
                        'on_bad_lines': 'skip',
                        'quoting': csv.QUOTE_NONE,
                        'error_bad_lines': False
                    }
                ]
                
                for attempt_num, read_params in enumerate(read_attempts, 1):
                    try:
                        logger.info(f"[structured] Read attempt {attempt_num}")
                        df = pd.read_csv(io.BytesIO(data), **read_params)
                        
                        if df is not None and not df.empty:
                            logger.info(f"[structured] Successfully read {len(df)} rows with {len(df.columns)} columns")
                            break
                    except Exception as attempt_error:
                        logger.warning(f"[structured] Attempt {attempt_num} failed: {attempt_error}")
                        last_error = attempt_error
                        continue
                
                if df is not None and not df.empty:
                    break
                    
            except Exception as encoding_error:
                logger.warning(f"[structured] Encoding {encoding} failed: {encoding_error}")
                last_error = encoding_error
                continue
        
        # Check if we successfully read the data
        if df is None or df.empty:
            raise ValueError(f"Failed to read CSV with all attempted methods. Last error: {last_error}")
        
        # 6. Clean and sanitize the DataFrame
        logger.info(f"[structured] Cleaning dataframe...")
        
        # Sanitize column names
        df.columns = [sanitize_column_name(col) for col in df.columns]
        
        # Handle duplicate column names
        cols = pd.Series(df.columns)
        for dup in cols[cols.duplicated()].unique():
            cols[cols == dup] = [f"{dup}_{i}" if i != 0 else dup for i in range(sum(cols == dup))]
        df.columns = cols
        
        # Remove completely empty rows
        df = df.dropna(how='all')
        
        # Strip whitespace from string columns
        for col in df.select_dtypes(include=['object']).columns:
            df[col] = df[col].apply(lambda x: x.strip() if isinstance(x, str) else x)
        
        # Replace various null representations
        null_values = ['nan', 'NaN', 'NA', 'N/A', 'null', 'NULL', 'None', '']
        df = df.replace(null_values, None)
        
        logger.info(f"[structured] Cleaned dataframe: {len(df)} rows, {len(df.columns)} columns")

        # 7. Create table name
        table_name = sanitize_table_name(object_name)

        # 8. Load to PostgreSQL
        cursor = pg_conn.cursor()
        
        # Drop existing table
        cursor.execute(f'DROP TABLE IF EXISTS "{table_name}"')
        
        # Create table with inferred types
        use_smart_types = True  # Set to False to use TEXT for everything
        
        if use_smart_types:
            column_defs = []
            for col in df.columns:
                pg_type = infer_postgres_type(df[col])
                column_defs.append(f'"{col}" {pg_type}')
        else:
            column_defs = [f'"{col}" TEXT' for col in df.columns]
        
        create_sql = f'CREATE TABLE "{table_name}" ({", ".join(column_defs)})'
        cursor.execute(create_sql)
        logger.info(f"[structured] Created table: {table_name}")
        
        # Bulk insert using COPY (fastest method)
        buffer = io.StringIO()
        df.to_csv(buffer, index=False, header=False, sep='\t', na_rep='\\N')
        buffer.seek(0)
        
        cursor.copy_expert(
            f'COPY "{table_name}" FROM STDIN WITH (FORMAT CSV, DELIMITER E\'\\t\', NULL \'\\N\')',
            buffer
        )
        
        pg_conn.commit()
        logger.info(f"[structured] Loaded {len(df)} rows into {table_name}")
        cursor.close()

        # 9. Write Parquet to MinIO for analytics
        logger.info(f"[structured] Writing Parquet file...")
        parquet_buffer = io.BytesIO()
        df.to_parquet(parquet_buffer, index=False, engine='pyarrow', compression='snappy')
        parquet_buffer.seek(0)

        parquet_name = object_name.replace('raw/', 'processed/structured/').rsplit('.', 1)[0] + '.parquet'
        minio_client.put_object(
            bucket_name, 
            parquet_name, 
            parquet_buffer, 
            length=parquet_buffer.getbuffer().nbytes,
            content_type='application/octet-stream'
        )
        logger.info(f"[structured] Parquet saved to: {parquet_name}")

        # 10. Update catalog - FIXED SIGNATURE
        catalog_updater(
            object_name=object_name,
            object_size=len(data),
            file_format='csv',
            row_count=len(df),
            text_extracted=False,
            content_hash=None
        )
        
        logger.info(f"[structured] ✅ Successfully processed {object_name}")

    except Exception as e:
        if pg_conn:
            pg_conn.rollback()
        logger.exception(f"[structured] ❌ Error processing {object_name}: {str(e)}")
        raise

    finally:
        if resp:
            resp.close()
            resp.release_conn()