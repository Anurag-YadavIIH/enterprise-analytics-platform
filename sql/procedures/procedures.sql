-- =====================================================================
-- Stored procedures, functions and triggers (PostgreSQL / PL/pgSQL).
-- =====================================================================
SET search_path TO olist, public;

-- ---------------------------------------------------------------
-- 1) Function: RFM segment for a single customer_unique_id.
-- ---------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_customer_rfm(p_customer_unique_id VARCHAR)
RETURNS TABLE (recency_days INT, frequency INT, monetary NUMERIC) AS $$
BEGIN
    RETURN QUERY
    SELECT
        (CURRENT_DATE - MAX(o.order_purchase_timestamp)::date)::int,
        COUNT(DISTINCT o.order_id)::int,
        ROUND(SUM(p.payment_value), 2)
    FROM fact_orders o
    JOIN dim_customers c ON o.customer_id = c.customer_id
    LEFT JOIN fact_payments p ON o.order_id = p.order_id
    WHERE c.customer_unique_id = p_customer_unique_id;
END;
$$ LANGUAGE plpgsql STABLE;

-- ---------------------------------------------------------------
-- 2) Procedure: refresh a materialized monthly-revenue snapshot.
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS mv_monthly_revenue (
    order_month DATE PRIMARY KEY,
    orders      INTEGER,
    revenue     NUMERIC(14,2),
    refreshed_at TIMESTAMP DEFAULT now()
);

CREATE OR REPLACE PROCEDURE sp_refresh_monthly_revenue()
LANGUAGE plpgsql AS $$
BEGIN
    TRUNCATE mv_monthly_revenue;
    INSERT INTO mv_monthly_revenue (order_month, orders, revenue)
    SELECT order_month, orders, revenue FROM vw_monthly_revenue;
    RAISE NOTICE 'mv_monthly_revenue refreshed: % rows',
        (SELECT COUNT(*) FROM mv_monthly_revenue);
END;
$$;

-- ---------------------------------------------------------------
-- 3) Audit trigger: track review-score changes.
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS review_audit (
    audit_id   BIGSERIAL PRIMARY KEY,
    review_id  VARCHAR(50),
    old_score  SMALLINT,
    new_score  SMALLINT,
    changed_at TIMESTAMP DEFAULT now()
);

CREATE OR REPLACE FUNCTION trg_review_score_audit()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.review_score IS DISTINCT FROM OLD.review_score THEN
        INSERT INTO review_audit (review_id, old_score, new_score)
        VALUES (OLD.review_id, OLD.review_score, NEW.review_score);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS review_score_audit ON fact_reviews;
CREATE TRIGGER review_score_audit
    BEFORE UPDATE ON fact_reviews
    FOR EACH ROW EXECUTE FUNCTION trg_review_score_audit();

-- ---------------------------------------------------------------
-- 4) Transaction example: atomic order cancellation.
-- ---------------------------------------------------------------
CREATE OR REPLACE PROCEDURE sp_cancel_order(p_order_id VARCHAR)
LANGUAGE plpgsql AS $$
BEGIN
    UPDATE fact_orders SET order_status = 'canceled' WHERE order_id = p_order_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Order % not found', p_order_id;
    END IF;
    -- (Additional compensating writes would go here, all in one transaction.)
END;
$$;
