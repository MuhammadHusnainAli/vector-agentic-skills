WITH monthly AS (
  SELECT customer_id, DATE_TRUNC('month', created_at) AS m, SUM(total) AS revenue
  FROM orders
  WHERE status <> 'cancelled, (refunded)'
  GROUP BY customer_id, DATE_TRUNC('month', created_at)
), ranked AS (SELECT * FROM monthly)
SELECT DISTINCT c.email,
       m.m,
       m.revenue,
       RANK() OVER (PARTITION BY m.m ORDER BY m.revenue DESC) AS rnk,
       (SELECT COUNT(*) FROM orders o2 WHERE o2.customer_id = c.id) AS lifetime_orders
FROM monthly m
JOIN customers c ON c.id = m.customer_id
LEFT OUTER JOIN segments s USING (customer_id)
WHERE m.revenue BETWEEN 100 AND 5000
  AND c.email NOT LIKE '%@test.com'
  AND (s.tier = 'gold' OR s.tier IS NULL)
GROUP BY c.email, m.m, m.revenue, c.id
HAVING COUNT(*) > 1
ORDER BY m.m DESC, rnk
LIMIT 50;
