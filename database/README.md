# Database Setup

This directory contains the database structure and sample data for the Flask starter kit.

## Files

- `schema.sql` - Database table definitions and structure
- `seed_data.sql` - Sample data for testing and development

## Setup Instructions

### 1. Prerequisites
- MySQL server installed and running
- Database created (you can name it anything)
- Database credentials configured in your `.env` file

### 2. Create Database Structure
Run the schema file to create the required tables:

```bash
mysql -h [host] -u [username] -p [database_name] < database/schema.sql
```

Or using your database management tool, execute the contents of `schema.sql`.

### 3. Load Sample Data (Optional)
To populate the database with sample records for testing:

```bash
mysql -h [host] -u [username] -p [database_name] < database/seed_data.sql
```

## Database Structure

### sample_table
- `sample_table_id` (INT, Primary Key, Auto Increment)
- `first_name` (VARCHAR(50), NOT NULL)
- `last_name` (VARCHAR(50), NOT NULL) 
- `date_of_birth` (DATE, NOT NULL)
- `created_at` (TIMESTAMP, Default: Current timestamp)
- `updated_at` (TIMESTAMP, Auto-update on modification)

## Notes

- The schema includes helpful indexes for common query patterns
- Timestamps are automatically managed by MySQL
- Sample data includes 10 test records with realistic names and dates

## Environment Variables

Make sure your `.env` file contains the correct database connection information:

```
DB_HOST=your_database_host
DB_USER=your_database_user
DB_PASSWORD=your_database_password
DB_NAME=your_database_name
```