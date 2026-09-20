-- Summarize the imported catalog.
SELECT
    COUNT(*) AS product_count,
    COUNT(DISTINCT category) AS category_count,
    MIN(price) AS min_price,
    MAX(price) AS max_price
FROM products;


-- Read a sample of imported products.
SELECT
    id,
    title,
    category,
    price,
    stock
FROM products
ORDER BY id
LIMIT 10;


-- Find products that are currently out of stock.
SELECT
    id,
    title,
    category,
    stock
FROM products
WHERE stock = 0
ORDER BY category, id;


-- Summarize product availability by category.
SELECT
    category,
    COUNT(*) AS product_count,
    COUNT(*) FILTER (WHERE stock > 0) AS available_product_count,
    COUNT(*) FILTER (WHERE stock = 0) AS out_of_stock_product_count
FROM products
GROUP BY category
ORDER BY category;