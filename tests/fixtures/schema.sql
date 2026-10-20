-- e-commerce
CREATE TABLE customers (
  id SERIAL PRIMARY KEY,
  email VARCHAR(255) NOT NULL UNIQUE,
  created_at TIMESTAMP
);
CREATE TABLE IF NOT EXISTS public.orders (
  id BIGINT PRIMARY KEY,
  customer_id INT NOT NULL REFERENCES customers(id),
  status TEXT,
  total NUMERIC(10,2) DEFAULT 0
);
CREATE TABLE `products` (`id` int, `name` varchar(100), `price` decimal(10,2), PRIMARY KEY (`id`));
CREATE TABLE order_items (
  order_id BIGINT,
  product_id INT,
  qty INT CHECK (qty > 0),
  CONSTRAINT fk_o FOREIGN KEY (order_id) REFERENCES orders (id),
  CONSTRAINT fk_p FOREIGN KEY (product_id) REFERENCES products (id),
  PRIMARY KEY (order_id, product_id)
);
CREATE TABLE audit_log (id INT, note TEXT);
