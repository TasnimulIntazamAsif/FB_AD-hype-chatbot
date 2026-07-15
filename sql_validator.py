import re

FORBIDDEN_KEYWORDS = re.compile(
    r'\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|GRANT|REVOKE|EXECUTE|COPY|MERGE|CALL)\b',
    re.IGNORECASE,
)


def validate_readonly_sql(sql: str) -> tuple[bool, str]:
    """Validate and normalize a read-only SQL query."""
    query = sql.strip().rstrip(";")

    if not query:
        return False, "Empty SQL query."

    if FORBIDDEN_KEYWORDS.search(query):
        return False, "Only read-only SELECT queries are permitted."

    if not re.match(r"^\s*(WITH\s+|SELECT\s+)", query, re.IGNORECASE | re.DOTALL):
        return False, "Query must start with SELECT or WITH ... SELECT."

    if ";" in query:
        return False, "Multiple SQL statements are not allowed."

    if not re.search(r"\bLIMIT\b", query, re.IGNORECASE):
        query = f"{query} LIMIT 100"

    return True, query
