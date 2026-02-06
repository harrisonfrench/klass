-- Database Schema for Flask Starter Kit
-- Run this file to create the required database structure

-- Create sample_table
CREATE TABLE sample_table (
    sample_table_id INT AUTO_INCREMENT PRIMARY KEY,
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    date_of_birth DATE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Add indexes for common queries
CREATE INDEX idx_sample_table_name ON sample_table (last_name, first_name);
CREATE INDEX idx_sample_table_dob ON sample_table (date_of_birth);