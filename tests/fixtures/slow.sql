SELECT DISTINCT *
FROM orders o
JOIN customers c ON LOWER(c.email) = LOWER(o.email)
WHERE YEAR(o.created_at) = 2026
  AND o.total * 1.2 > 100
  AND c.name LIKE '%smith'
  AND c.note = 'LIKE ''%x'' in a string'
  AND o.id NOT IN (SELECT order_id FROM refunds)
  AND (SELECT COUNT(*) FROM items i WHERE i.order_id = o.id) > 0
GROUP BY o.id
HAVING o.status = 'paid'
ORDER BY RAND()
LIMIT 20 OFFSET 50000;
SELECT name, (SELECT MAX(x.ts) FROM logins x WHERE x.user_id = u.id) AS last_login FROM users u UNION SELECT name, NULL FROM admins;
SELECT * FROM a, b;
