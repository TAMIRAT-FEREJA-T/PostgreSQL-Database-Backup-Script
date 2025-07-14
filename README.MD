# 📂 PostgreSQL Database Backup Script

A complete Python solution for backing up PostgreSQL databases, including schemas, tables, and data.

## Table of Contents
- [Features](#-features)
- [Requirements](#-requirements)
- [Installation](#-installation)
- [Configuration](#-configuration)
- [Usage](#-usage)
- [Sample Output](#-sample-output)
- [Security](#-security)
- [Automation](#-automation)
- [Troubleshooting](#-troubleshooting)
- [License](#-license)

## ✨ Features
✔ **Complete Database Backup**  
- Backs up all databases (excluding system DBs)
- Preserves schemas, tables, views, and data
- Handles indexes, constraints, and foreign keys

✔ **Intelligent Data Export**  
- Uses PostgreSQL's efficient COPY format
- Properly escapes special characters
- Supports binary data (hex format)
- Handles NULL values correctly

✔ **Safety First**  
- Read-only operations
- Transaction-safe with rollback on errors
- Credentials never stored to disk

✔ **Convenience**  
- Automatic timestamped filenames
- Clear console output
- Configurable connection parameters

## 📋 Requirements
- Python 3.6+
- `psycopg2` package
- PostgreSQL 9.5+ (tested up to 15)
- Read access to target databases

## 🛠 Installation
```bash
# Install psycopg2 (PostgreSQL adapter)
pip install psycopg2-binary
⚙ Configuration
Edit these variables at the top of the script:

python
MASTER_HOST = 'your-db-host'      # PostgreSQL server address
MASTER_USER = 'your-username'     # DB username with read access
MASTER_PASS = 'your-password'     # DB password
MASTER_PORT = '5432'              # PostgreSQL port

# Optional:
BACKUP_DIR = "postgres_backups"   # Custom backup directory
🚀 Usage
bash
# Basic usage
python postgres_backup.py

# Expected output:
Starting PostgreSQL backup process...
Found 5 databases to backup.

Starting backup of database: inventory
Backing up public.products
Backing up public.users
...
Database inventory backup complete. Saved to postgres_backups/inventory_backup_20231115_143045.sql
📄 Sample Output
sql
-- FULL DATABASE BACKUP
-- Date: 2023-11-15 14:30:45.123456
-- Database: ecommerce
-- PostgreSQL Version: PostgreSQL 14.5

SET statement_timeout = 0;
-- [connection settings]

-- SCHEMA: public

-- ============================================
-- TABLE: public.products
-- ============================================
CREATE TABLE public.products (
    product_id serial NOT NULL,
    name varchar(100) NOT NULL,
    price numeric(10,2) DEFAULT 0.00,
    PRIMARY KEY (product_id)
);

-- INDEXES
CREATE INDEX idx_products_name ON public.products USING btree (name);

-- 5 rows of data
COPY public.products (product_id, name, price) FROM stdin;
1   Widget A   19.99
2   Gadget B   29.50
...
🔒 Security
Important Notes:

The script only performs READ operations

Never modifies your database

Credentials exist only in memory during execution

Backups are stored locally

Best Practices:

Use a dedicated backup user with read-only privileges

Store backup files securely

Test restore procedures regularly

Consider encrypting sensitive backups

🤖 Automation
Linux/Mac (cron)
bash
# Edit crontab
crontab -e

# Add this line (runs daily at 2 AM)
0 2 * * * /usr/bin/python3 /path/to/postgres_backup.py >> /var/log/pg_backup.log 2>&1
Windows (Task Scheduler)
Create Basic Task

Set trigger to "Daily"

Action: "Start a program"

Program: python.exe

Arguments: "C:\path\to\postgres_backup.py"

🐛 Troubleshooting
Common Issues:

Error	Solution
Connection failed	Verify credentials, check firewall
Permission denied	Ensure user has read access
Missing psycopg2	Run pip install psycopg2-binary
Encoding errors	Add # -*- coding: utf-8 -*- to script
Verbose Logging:
Add this to the script for detailed output:

python
import logging
logging.basicConfig(level=logging.DEBUG)
📜 License
MIT License - Free for both commercial and personal use.

🤝 Contributing
Fork the repository

Create your feature branch

Submit a pull request