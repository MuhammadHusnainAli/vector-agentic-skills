# Operational Report Queries

### Inventory Status Report

```sql
SELECT 
    p.sku,
    p.name,
    c.name AS category,
    
    i.quantity_on_hand,
    i.reorder_point,
    i.reorder_quantity,
    
    COALESCE(s.units_sold_7d, 0) AS sold_last_7d,
    COALESCE(s.units_sold_30d, 0) AS sold_last_30d,
    ROUND(COALESCE(s.units_sold_30d, 0) / 30.0, 1) AS daily_velocity,
    
    CASE 
        WHEN i.quantity_on_hand <= 0 THEN 0
        WHEN COALESCE(s.units_sold_30d, 0) = 0 THEN 999
        ELSE ROUND(i.quantity_on_hand / (s.units_sold_30d / 30.0), 0)
    END AS days_of_stock,
    
    CASE 
        WHEN i.quantity_on_hand <= 0 THEN 'OUT OF STOCK'
        WHEN i.quantity_on_hand <= i.reorder_point THEN 'REORDER NOW'
        WHEN i.quantity_on_hand <= i.reorder_point * 1.5 THEN 'LOW STOCK'
        WHEN i.quantity_on_hand > s.units_sold_30d * 6 THEN 'OVERSTOCK'
        ELSE 'OK'
    END AS status,
    
    CASE 
        WHEN i.quantity_on_hand <= i.reorder_point THEN i.reorder_quantity
        ELSE 0
    END AS suggested_order

FROM products p
JOIN inventory i ON p.id = i.product_id
JOIN categories c ON p.category_id = c.id
LEFT JOIN (
    SELECT 
        product_id,
        SUM(CASE WHEN order_date >= CURRENT_DATE - 7 THEN quantity ELSE 0 END) AS units_sold_7d,
        SUM(CASE WHEN order_date >= CURRENT_DATE - 30 THEN quantity ELSE 0 END) AS units_sold_30d
    FROM order_items oi
    JOIN orders o ON oi.order_id = o.id
    WHERE o.status = 'completed'
    GROUP BY product_id
) s ON p.id = s.product_id

WHERE p.is_active = true
ORDER BY 
    CASE 
        WHEN i.quantity_on_hand <= 0 THEN 1
        WHEN i.quantity_on_hand <= i.reorder_point THEN 2
        WHEN i.quantity_on_hand <= i.reorder_point * 1.5 THEN 3
        ELSE 4
    END,
    p.name;
```

### Order Fulfillment Report

```sql
SELECT 
    DATE(order_date) AS order_date,
    
    COUNT(*) AS total_orders,
    COUNT(*) FILTER (WHERE status = 'pending') AS pending,
    COUNT(*) FILTER (WHERE status = 'processing') AS processing,
    COUNT(*) FILTER (WHERE status = 'shipped') AS shipped,
    COUNT(*) FILTER (WHERE status = 'delivered') AS delivered,
    
    ROUND(100.0 * COUNT(*) FILTER (WHERE status = 'delivered') / COUNT(*), 1) AS fulfillment_rate,
    
    ROUND(AVG(EXTRACT(EPOCH FROM (ship_date - order_date)) / 3600) 
        FILTER (WHERE ship_date IS NOT NULL), 1) AS avg_hours_to_ship,
    
    ROUND(AVG(EXTRACT(EPOCH FROM (delivery_date - ship_date)) / 86400) 
        FILTER (WHERE delivery_date IS NOT NULL), 1) AS avg_days_in_transit,
    
    COUNT(*) FILTER (WHERE ship_date > order_date + INTERVAL '2 days') AS late_shipments,
    
    SUM(total) FILTER (WHERE status NOT IN ('cancelled', 'refunded')) AS fulfilled_revenue

FROM orders
WHERE order_date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY DATE(order_date)
ORDER BY order_date DESC;
```

### Customer Service Report

```sql
SELECT 
    DATE_TRUNC('week', created_at) AS week,
    
    COUNT(*) AS total_tickets,
    COUNT(*) FILTER (WHERE status = 'open') AS open_tickets,
    COUNT(*) FILTER (WHERE status = 'resolved') AS resolved_tickets,
    
    ROUND(100.0 * COUNT(*) FILTER (WHERE status = 'resolved') / COUNT(*), 1) AS resolution_rate,
    
    ROUND(AVG(EXTRACT(EPOCH FROM (first_response_at - created_at)) / 3600) 
        FILTER (WHERE first_response_at IS NOT NULL), 1) AS avg_first_response_hours,
    
    ROUND(AVG(EXTRACT(EPOCH FROM (resolved_at - created_at)) / 3600) 
        FILTER (WHERE resolved_at IS NOT NULL), 1) AS avg_resolution_hours,
    
    COUNT(*) FILTER (WHERE priority = 'high') AS high_priority,
    COUNT(*) FILTER (WHERE category = 'refund') AS refund_requests,
    COUNT(*) FILTER (WHERE category = 'shipping') AS shipping_issues,
    
    ROUND(AVG(satisfaction_score) FILTER (WHERE satisfaction_score IS NOT NULL), 2) AS avg_csat

FROM support_tickets
WHERE created_at >= CURRENT_DATE - INTERVAL '12 weeks'
GROUP BY DATE_TRUNC('week', created_at)
ORDER BY week DESC;
```
