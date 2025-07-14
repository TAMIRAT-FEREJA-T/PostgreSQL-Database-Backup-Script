import psycopg2
from psycopg2 import OperationalError, Error, sql
import datetime
import textwrap
import os

# Master connection parameters (to discover databases)
MASTER_HOST = ''
MASTER_USER = ''
MASTER_PASS = ''
MASTER_PORT = '5432'

# Output directory
BACKUP_DIR = "postgres_backups"
os.makedirs(BACKUP_DIR, exist_ok=True)

def get_db_connection(host, user, password, dbname="postgres", port="5432"):
    """Establish connection to PostgreSQL database"""
    try:
        conn = psycopg2.connect(
            host=host,
            database=dbname,
            user=user,
            password=password,
            port=port
        )
        conn.autocommit = False  # We'll manage transactions manually
        return conn
    except OperationalError as e:
        print(f"Connection error to {dbname}: {e}")
        return None

def write_to_file(filepath, content, mode='a'):
    """Write content to file with specified mode"""
    try:
        with open(filepath, mode, encoding='utf-8') as f:
            f.write(content)
    except IOError as e:
        print(f"Error writing to file {filepath}: {e}")

def get_all_databases(conn):
    """Get list of all databases except system databases"""
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT datname 
            FROM pg_database 
            WHERE datname NOT IN ('template0', 'template1', 'postgres')
            AND datistemplate = false
            ORDER BY datname
        """)
        databases = [db[0] for db in cursor.fetchall()]
        cursor.close()
        return databases
    except Error as e:
        print(f"Error fetching databases: {e}")
        return []

def get_database_info(conn, db_name):
    """Get database version and metadata"""
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT version()")
        version = cursor.fetchone()[0]
        
        cursor.execute("SELECT current_user")
        db_user = cursor.fetchone()[0]
        
        cursor.close()
        return version, db_name, db_user
    except Error as e:
        print(f"Error getting database info: {e}")
        return None, db_name, None

def get_all_schemas(conn):
    """Get list of all schemas in the current database"""
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT schema_name 
            FROM information_schema.schemata 
            WHERE schema_name NOT LIKE 'pg_%' 
            AND schema_name != 'information_schema'
            ORDER BY schema_name
        """)
        schemas = [schema[0] for schema in cursor.fetchall()]
        cursor.close()
        return schemas
    except Error as e:
        print(f"Error fetching schemas: {e}")
        return []

def get_all_tables(conn, schema='public'):
    """Get list of all tables in a specific schema"""
    try:
        cursor = conn.cursor()
        cursor.execute(sql.SQL("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = %s
            AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """), [schema])
        tables = [table[0] for table in cursor.fetchall()]
        cursor.close()
        return tables
    except Error as e:
        print(f"Error fetching tables in schema {schema}: {e}")
        return []

def get_table_definition(conn, table_name, schema='public'):
    """Generate CREATE TABLE statement using system catalogs"""
    try:
        cursor = conn.cursor()
        
        # Get table columns
        cursor.execute(sql.SQL("""
            SELECT 
                a.attname as column_name,
                pg_catalog.format_type(a.atttypid, a.atttypmod) as data_type,
                CASE WHEN a.attnotnull THEN 'NOT NULL' ELSE '' END as not_null,
                COALESCE(pg_catalog.pg_get_expr(d.adbin, d.adrelid), '') as default_value
            FROM 
                pg_catalog.pg_attribute a
            LEFT JOIN 
                pg_catalog.pg_attrdef d ON (a.attrelid = d.adrelid AND a.attnum = d.adnum)
            WHERE 
                a.attrelid = (%s || '.' || %s)::regclass
                AND a.attnum > 0
                AND NOT a.attisdropped
            ORDER BY 
                a.attnum
        """), [schema, table_name])
        columns = cursor.fetchall()
        
        # Get primary key
        cursor.execute(sql.SQL("""
            SELECT 
                a.attname
            FROM 
                pg_index i
            JOIN 
                pg_attribute a ON (a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey))
            WHERE 
                i.indrelid = (%s || '.' || %s)::regclass
                AND i.indisprimary
        """), [schema, table_name])
        primary_keys = [pk[0] for pk in cursor.fetchall()]
        
        # Build CREATE TABLE statement
        create_table = f"CREATE TABLE {schema}.{table_name} (\n"
        column_defs = []
        
        for col in columns:
            col_def = f"    {col[0]} {col[1]}"
            if col[2]:
                col_def += f" {col[2]}"
            if col[3]:
                col_def += f" DEFAULT {col[3]}"
            column_defs.append(col_def)
        
        create_table += ",\n".join(column_defs)
        
        if primary_keys:
            create_table += f",\n    PRIMARY KEY ({', '.join(primary_keys)})"
        
        create_table += "\n);"
        
        # Get indexes
        cursor.execute(sql.SQL("""
            SELECT indexname, indexdef 
            FROM pg_indexes 
            WHERE schemaname = %s AND tablename = %s
        """), [schema, table_name])
        indexes = cursor.fetchall()
        
        # Get foreign keys
        cursor.execute(sql.SQL("""
            SELECT
                conname,
                pg_get_constraintdef(oid) as condef
            FROM
                pg_constraint
            WHERE
                conrelid = (%s || '.' || %s)::regclass
                AND contype = 'f'
        """), [schema, table_name])
        foreign_keys = cursor.fetchall()
        
        cursor.close()
        return create_table, indexes, foreign_keys
    except Error as e:
        print(f"Error getting definition for table {schema}.{table_name}: {e}")
        return None, [], []

def get_table_data(conn, table_name, schema='public'):
    """Get all data from a specific table"""
    try:
        cursor = conn.cursor()
        
        # Get column names
        cursor.execute(sql.SQL("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_schema = %s
            AND table_name = %s
            ORDER BY ordinal_position
        """), [schema, table_name])
        columns = [col[0] for col in cursor.fetchall()]
        
        # Get table data with proper schema qualification
        cursor.execute(sql.SQL("SELECT * FROM {}.{}").format(
            sql.Identifier(schema),
            sql.Identifier(table_name)
        ))
        rows = cursor.fetchall()
        
        cursor.close()
        return columns, rows
    except Error as e:
        print(f"Error fetching data from table {schema}.{table_name}: {e}")
        return [], []

def backup_database(host, user, password, db_name, port="5432"):
    """Backup a single database with all its schemas and tables"""
    print(f"\nStarting backup of database: {db_name}")
    
    # Create database-specific backup file
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = os.path.join(BACKUP_DIR, f"{db_name}_backup_{timestamp}.sql")
    
    # Connect to the specific database
    conn = get_db_connection(host, user, password, db_name, port)
    if not conn:
        print(f"Failed to connect to database {db_name}. Skipping.")
        return
    
    try:
        # Get database info
        version, db_name, db_user = get_database_info(conn, db_name)
        
        # Write header to output file
        header = f"""
-- FULL DATABASE BACKUP
-- Date: {datetime.datetime.now()}
-- Database: {db_name}
-- Host: {host}
-- User: {db_user}
-- PostgreSQL Version: {version}

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SET check_function_bodies = false;
SET client_min_messages = warning;
SET row_security = off;

"""
        write_to_file(output_file, header, mode='w')
        
        # Get all schemas in this database
        schemas = get_all_schemas(conn)
        if not schemas:
            print(f"No schemas found in database {db_name}.")
            return
        
        # Process each schema
        for schema in schemas:
            write_to_file(output_file, f"\n\n-- SCHEMA: {schema}\n")
            
            # Create schema if not public
            if schema != 'public':
                write_to_file(output_file, f"CREATE SCHEMA IF NOT EXISTS {schema};\n")
                write_to_file(output_file, f"SET search_path TO {schema};\n\n")
            
            # Get all tables in this schema
            tables = get_all_tables(conn, schema)
            if not tables:
                write_to_file(output_file, f"-- No tables found in schema {schema}\n")
                continue
            
            # Process each table
            for table in tables:
                print(f"Backing up {schema}.{table}")
                
                # Write table header
                write_to_file(output_file, f"\n\n-- {'='*50}\n")
                write_to_file(output_file, f"-- TABLE: {schema}.{table}\n")
                write_to_file(output_file, f"-- {'='*50}\n\n")
                
                # Get and write table structure
                table_def, indexes, foreign_keys = get_table_definition(conn, table, schema)
                if table_def:
                    write_to_file(output_file, "-- TABLE STRUCTURE\n")
                    write_to_file(output_file, table_def + "\n\n")
                
                if indexes:
                    write_to_file(output_file, "-- INDEXES\n")
                    for idx in indexes:
                        write_to_file(output_file, idx[1] + ";\n")
                    write_to_file(output_file, "\n")
                
                if foreign_keys:
                    write_to_file(output_file, "-- FOREIGN KEYS\n")
                    for fk in foreign_keys:
                        write_to_file(output_file, f"ALTER TABLE {schema}.{table} ADD CONSTRAINT {fk[0]} {fk[1]};\n")
                    write_to_file(output_file, "\n")
                
                # Get and write table data
                columns, rows = get_table_data(conn, table, schema)
                if rows:
                    write_to_file(output_file, "-- TABLE DATA\n")
                    write_to_file(output_file, f"-- {len(rows)} rows\n\n")
                    
                    # Write COPY statements for efficient data loading
                    write_to_file(output_file, f"COPY {schema}.{table} ({', '.join(columns)}) FROM stdin;\n")
                    for row in rows:
                        # Convert each value to string and escape special characters
                        row_str = []
                        for value in row:
                            if value is None:
                                row_str.append("\\N")  # PostgreSQL NULL representation
                            elif isinstance(value, str):
                                # Escape backslashes and newlines
                                escaped = value.replace('\\', '\\\\').replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
                                row_str.append(escaped)
                            elif isinstance(value, datetime.datetime):
                                row_str.append(value.isoformat())
                            elif isinstance(value, datetime.date):
                                row_str.append(value.isoformat())
                            elif isinstance(value, bytes):
                                row_str.append("\\x" + value.hex())
                            else:
                                row_str.append(str(value))
                        write_to_file(output_file, "\t".join(row_str) + "\n")
                    write_to_file(output_file, "\\.\n\n")
        
        # Reset search path at the end
        write_to_file(output_file, "\nSET search_path TO public;\n")
        
        print(f"Database {db_name} backup complete. Saved to {output_file}")
    
    except Error as e:
        print(f"Error during backup of {db_name}: {e}")
        conn.rollback()
    finally:
        conn.close()

def backup_all_databases():
    """Main function to backup all databases"""
    print("Starting PostgreSQL backup process...")
    
    # Connect to master database to discover all databases
    master_conn = get_db_connection(MASTER_HOST, MASTER_USER, MASTER_PASS, "postgres", MASTER_PORT)
    if not master_conn:
        print("Failed to connect to master database. Exiting.")
        return
    
    # Get all databases
    databases = get_all_databases(master_conn)
    master_conn.close()
    
    if not databases:
        print("No databases found to backup.")
        return
    
    print(f"Found {len(databases)} databases to backup.")
    
    # Backup each database
    for db in databases:
        backup_database(MASTER_HOST, MASTER_USER, MASTER_PASS, db, MASTER_PORT)
    
    print("\nAll database backups completed successfully.")

if __name__ == "__main__":
    backup_all_databases()