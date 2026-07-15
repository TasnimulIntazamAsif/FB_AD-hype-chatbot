import os
import sys
import psycopg2
import psycopg2.extras
from fastmcp import FastMCP
from dotenv import load_dotenv
from typing import List, Dict, Any, Optional

# .env ফাইল থেকে কনফিগারেশন লোড করুন
load_dotenv()

# ডাটাবেস কনফিগারেশন
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
    "dbname": os.getenv("DB_NAME", "postgres"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "")
}

# MCP সার্ভার তৈরি করুন
mcp = FastMCP("PostgreSQL Database Server 🗄️")


def get_db_connection():
    """ডাটাবেস কানেকশন তৈরি করুন"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        print(f"Database connection error: {e}")
        return None


# ============================================================
# টুল ১: ডাটাবেসের সব টেবিলের তালিকা
# ============================================================
@mcp.tool
def list_all_tables() -> List[Dict[str, Any]]:
    """
    ডাটাবেসের সব টেবিলের নাম এবং তাদের কলামের সংখ্যা দেখান।
    """
    conn = get_db_connection()
    if not conn:
        return [{"error": "Database connection failed"}]

    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute("""
                    SELECT table_name,
                           (SELECT COUNT(*)
                            FROM information_schema.columns
                            WHERE table_name = t.table_name
                              AND table_schema = 'public') as column_count
                    FROM information_schema.tables t
                    WHERE table_schema = 'public'
                    ORDER BY table_name;
                    """)
        tables = cur.fetchall()
        cur.close()
        conn.close()
        return [dict(table) for table in tables]
    except Exception as e:
        return [{"error": f"Error fetching tables: {str(e)}"}]


# ============================================================
# টুল ২: টেবিলের ডাটা দেখান
# ============================================================
@mcp.tool
def view_table_data(table_name: str, limit: int = 100) -> Dict[str, Any]:
    """
    একটি নির্দিষ্ট টেবিলের সম্পূর্ণ ডাটা দেখান।
    """
    conn = get_db_connection()
    if not conn:
        return {"error": "Database connection failed"}

    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute("""
                    SELECT column_name, data_type
                    FROM information_schema.columns
                    WHERE table_name = %s
                      AND table_schema = 'public'
                    ORDER BY ordinal_position;
                    """, (table_name,))
        columns = cur.fetchall()
        if not columns:
            return {"error": f"Table '{table_name}' not found"}

        query = f"SELECT * FROM {table_name} LIMIT %s;"
        cur.execute(query, (limit,))
        rows = cur.fetchall()
        cur.close()
        conn.close()

        column_names = [col['column_name'] for col in columns]
        return {
            "table_name": table_name,
            "columns": column_names,
            "rows": [dict(row) for row in rows],
            "total_rows_fetched": len(rows)
        }
    except Exception as e:
        return {"error": f"Error: {str(e)}"}


# ============================================================
# টুল ৩: টেবিলের স্কিমা
# ============================================================
@mcp.tool
def describe_table(table_name: str) -> Dict[str, Any]:
    """
    একটি টেবিলের সম্পূর্ণ স্কিমা দেখান।
    """
    conn = get_db_connection()
    if not conn:
        return {"error": "Database connection failed"}

    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute("""
                    SELECT column_name,
                           data_type,
                           is_nullable,
                           column_default
                    FROM information_schema.columns
                    WHERE table_name = %s
                      AND table_schema = 'public'
                    ORDER BY ordinal_position;
                    """, (table_name,))
        columns = cur.fetchall()
        if not columns:
            return {"error": f"Table '{table_name}' not found"}
        cur.close()
        conn.close()
        return {
            "table_name": table_name,
            "schema": [dict(col) for col in columns]
        }
    except Exception as e:
        return {"error": f"Error: {str(e)}"}


# ============================================================
# টুল ৪: কাস্টম SQL
# ============================================================
@mcp.tool
def run_query(query: str, limit: int = 100) -> Dict[str, Any]:
    """
    কাস্টম SQL কোয়েরি রান করুন (শুধুমাত্র SELECT)।
    """
    query_lower = query.strip().lower()
    if not query_lower.startswith("select"):
        return {"error": "Only SELECT queries are allowed"}

    if "limit" not in query_lower:
        query = f"{query.rstrip(';')} LIMIT {limit};"

    conn = get_db_connection()
    if not conn:
        return {"error": "Database connection failed"}

    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute(query)
        rows = cur.fetchall()
        column_names = [desc[0] for desc in cur.description] if cur.description else []
        cur.close()
        conn.close()
        return {
            "query": query,
            "columns": column_names,
            "rows": [dict(row) for row in rows],
            "row_count": len(rows)
        }
    except Exception as e:
        return {"error": f"Query error: {str(e)}"}


# ============================================================
# রিসোর্স
# ============================================================
@mcp.resource("database://tables")
def get_tables_list() -> str:
    """ডাটাবেসের সব টেবিলের তালিকা"""
    tables = list_all_tables()
    if isinstance(tables, list) and len(tables) > 0:
        if "error" in tables[0]:
            return f"Error: {tables[0]['error']}"
        result = "📋 Database Tables:\n" + "=" * 30 + "\n"
        for table in tables:
            result += f"📊 {table['table_name']} ({table['column_count']} columns)\n"
        return result
    return "No tables found"


# ============================================================
# প্রম্পট
# ============================================================
@mcp.prompt
def analyze_database() -> str:
    """ডাটাবেস বিশ্লেষণের জন্য প্রম্পট"""
    return """
    You are a database analyst. Please help me understand my PostgreSQL database.
    First, list all the tables using the list_all_tables tool.
    Then, for each table, use describe_table to understand its structure.
    Finally, use view_table_data to see sample data.
    """


# ============================================================
# সার্ভার রান করুন
# ============================================================
if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--http":
        import uvicorn
        app = mcp.http_app()
        uvicorn.run(app, host="127.0.0.1", port=8000) 
    else:
        mcp.run()