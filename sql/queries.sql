-- Bank Telemarketing Conversion Analysis — SQL business questions
-- Table: clients (loaded from data/bank-full.csv by analysis.py into bank.db)
-- Target: y = 'yes' means the client subscribed to a term deposit.

-- Q1. Overall conversion rate
SELECT COUNT(*) AS clients_contacted,
       SUM(CASE WHEN y = 'yes' THEN 1 ELSE 0 END) AS subscriptions,
       ROUND(100.0 * SUM(CASE WHEN y = 'yes' THEN 1 ELSE 0 END) / COUNT(*), 2) AS conversion_pct
FROM clients;

-- Q2. Conversion by campaign month (timing effect + volume)
SELECT month,
       COUNT(*) AS contacts,
       ROUND(100.0 * SUM(CASE WHEN y = 'yes' THEN 1 ELSE 0 END) / COUNT(*), 2) AS conversion_pct
FROM clients
GROUP BY month
ORDER BY CASE month
    WHEN 'jan' THEN 1 WHEN 'feb' THEN 2 WHEN 'mar' THEN 3 WHEN 'apr' THEN 4
    WHEN 'may' THEN 5 WHEN 'jun' THEN 6 WHEN 'jul' THEN 7 WHEN 'aug' THEN 8
    WHEN 'sep' THEN 9 WHEN 'oct' THEN 10 WHEN 'nov' THEN 11 WHEN 'dec' THEN 12 END;

-- Q3. Conversion by contact channel
SELECT contact,
       COUNT(*) AS contacts,
       ROUND(100.0 * SUM(CASE WHEN y = 'yes' THEN 1 ELSE 0 END) / COUNT(*), 2) AS conversion_pct
FROM clients
GROUP BY contact
ORDER BY conversion_pct DESC;

-- Q4. Conversion by previous campaign outcome (strongest targeting signal)
SELECT poutcome,
       COUNT(*) AS contacts,
       ROUND(100.0 * SUM(CASE WHEN y = 'yes' THEN 1 ELSE 0 END) / COUNT(*), 2) AS conversion_pct
FROM clients
GROUP BY poutcome
ORDER BY conversion_pct DESC;

-- Q5. Conversion by number of contacts in this campaign (fatigue effect)
SELECT CASE WHEN campaign >= 5 THEN '5+' ELSE CAST(campaign AS TEXT) END AS contacts_in_campaign,
       COUNT(*) AS clients,
       ROUND(100.0 * SUM(CASE WHEN y = 'yes' THEN 1 ELSE 0 END) / COUNT(*), 2) AS conversion_pct
FROM clients
GROUP BY contacts_in_campaign
ORDER BY MIN(campaign);

-- Q6. Conversion by job segment (min. 500 clients for a stable rate)
SELECT job,
       COUNT(*) AS clients,
       ROUND(100.0 * SUM(CASE WHEN y = 'yes' THEN 1 ELSE 0 END) / COUNT(*), 2) AS conversion_pct
FROM clients
GROUP BY job
HAVING COUNT(*) >= 500
ORDER BY conversion_pct DESC;

-- Q7. Do existing borrowers convert? (housing loan / personal loan holders)
SELECT housing, loan,
       COUNT(*) AS clients,
       ROUND(100.0 * SUM(CASE WHEN y = 'yes' THEN 1 ELSE 0 END) / COUNT(*), 2) AS conversion_pct
FROM clients
GROUP BY housing, loan
ORDER BY conversion_pct DESC;

-- Q8. Repeat-contact economics: clients contacted in a previous campaign
--     vs first-time contacts
SELECT CASE WHEN previous = 0 THEN 'first-time contact' ELSE 'contacted before' END AS segment,
       COUNT(*) AS clients,
       ROUND(100.0 * SUM(CASE WHEN y = 'yes' THEN 1 ELSE 0 END) / COUNT(*), 2) AS conversion_pct
FROM clients
GROUP BY segment
ORDER BY conversion_pct DESC;
