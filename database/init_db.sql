CREATE DATABASE IF NOT EXISTS inventory_management;
USE inventory_management;

CREATE TABLE IF NOT EXISTS stocks (
    product_id VARCHAR(50) PRIMARY KEY,
    quantity INT NOT NULL
);

CREATE TABLE IF NOT EXISTS sales (
    id INT AUTO_INCREMENT PRIMARY KEY,
    product_id VARCHAR(50) NOT NULL,
    quantity INT NOT NULL,
    date DATE NOT NULL
);

-- Sample data for stocks
INSERT INTO stocks (product_id, quantity) VALUES
('PROD001', 100),
('PROD002', 150),
('PROD003', 75);

-- Sample data for sales
INSERT INTO sales (product_id, quantity, date) VALUES
('PROD001', 5, '2023-08-01'),
('PROD002', 3, '2023-08-01'),
('PROD001', 7, '2023-08-02'),
('PROD003', 2, '2023-08-02'),
('PROD002', 4, '2023-08-03'),
('PROD001', 6, '2023-08-03');

SELECT* FROM sales;

drop DATABASE inventory_management;