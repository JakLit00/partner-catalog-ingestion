CREATE TABLE products (
    id BIGINT PRIMARY KEY,
    title TEXT NOT NULL,
    category TEXT NOT NULL,
    price NUMERIC NOT NULL,
    stock BIGINT NOT NULL,

    CONSTRAINT products_id_positive
        CHECK (id > 0),

    CONSTRAINT products_title_not_blank
        CHECK (length(btrim(title)) > 0),

    CONSTRAINT products_category_not_blank
        CHECK (length(btrim(category)) > 0),

    CONSTRAINT products_price_valid
        CHECK (
            price >= 0
            AND price NOT IN (
                'NaN'::numeric,
                'Infinity'::numeric,
                '-Infinity'::numeric
            )
        ),

    CONSTRAINT products_stock_non_negative
        CHECK (stock >= 0)
);