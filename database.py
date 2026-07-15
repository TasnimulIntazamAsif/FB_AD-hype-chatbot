import os
import re
import threading
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import logging
from typing import List, Dict, Any, Optional

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TEXT_COLUMN_TYPES = frozenset({
    'character varying', 'varchar', 'text', 'char', 'character', 'name',
})

SEARCHABLE_COLUMN_HINTS = re.compile(
    r'name|title|account|campaign|company|ad_|description|objective|label|brand|client',
    re.IGNORECASE,
)

TABLE_PURPOSE_HINTS = {
    'ads_insights': 'Main ad performance metrics: spend, clicks, impressions, CTR, CPC per ad/campaign/account',
    'ads_insights_platform_and_device': 'Performance broken down by platform and device',
    'ads_insights_action_type': 'Conversion/action metrics by action type',
    'campaigns': 'Campaign metadata: name, objective, status, budget, schedule',
    'ad_sets': 'Ad set metadata: targeting, budget, schedule',
    'ad_creatives': 'Ad creative assets and metadata',
    'custom_conversions': 'Custom conversion definitions',
    'activities': 'Account activity log',
}


class DatabaseManager:
    def __init__(self):
        self.conn_params = {
            'host': os.getenv('DB_HOST'),
            'port': int(os.getenv('DB_PORT', 5432)),
            'dbname': os.getenv('DB_NAME'),
            'user': os.getenv('DB_USER'),
            'password': os.getenv('DB_PASSWORD')
        }
        self.schema = os.getenv('DB_SCHEMA', 'public')
        self.connection = None
        self.main_table = 'ads_insights'
        self.tables: List[str] = []
        self._schema_cache: Dict[str, List[Dict[str, Any]]] = {}
        self._row_count_cache: Dict[str, int] = {}
        self._lock = threading.RLock()

    def _connect_unlocked(self):
        """Open a new database connection (caller must hold _lock)."""
        self.connection = psycopg2.connect(**self.conn_params)
        self._row_count_cache.clear()
        self.discover_tables()

    def connect(self):
        """Establish database connection"""
        with self._lock:
            try:
                self._connect_unlocked()
                logger.info("Database connection established successfully!")
                return self.connection
            except Exception as e:
                self.connection = None
                logger.error(f"Database connection failed: {e}")
                raise

    def ensure_connection(self):
        """Ensure an active connection exists; reconnect if the server closed it."""
        with self._lock:
            if self.connection is None or self.connection.closed:
                logger.info("Reconnecting to database...")
                self._connect_unlocked()
                return self.connection

            try:
                with self.connection.cursor() as cursor:
                    cursor.execute("SELECT 1")
                return self.connection
            except psycopg2.Error as e:
                logger.warning(f"Stale database connection detected, reconnecting: {e}")
                try:
                    self.connection.close()
                except psycopg2.Error:
                    pass
                self.connection = None
                self._connect_unlocked()
                return self.connection

    def is_connected(self) -> bool:
        """Return True if the database connection is alive."""
        try:
            self.ensure_connection()
            return True
        except Exception as e:
            logger.error(f"Database connectivity check failed: {e}")
            return False

    def discover_tables(self) -> List[str]:
        """Discover all user tables in the configured schema."""
        if not self.connection:
            return []

        query = """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = %s
              AND table_type = 'BASE TABLE'
            ORDER BY table_name;
        """
        try:
            with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query, (self.schema,))
                rows = cursor.fetchall()
            self.tables = [row['table_name'] for row in rows]
            self._schema_cache.clear()
            logger.info(f"Discovered {len(self.tables)} tables in schema '{self.schema}'")
            return self.tables
        except Exception as e:
            logger.error(f"Table discovery failed: {e}")
            return self.tables

    def get_table_names(self) -> List[str]:
        """Get all table names (auto-discovers if needed)."""
        with self._lock:
            if not self.tables and self.connection:
                self.discover_tables()
            return list(self.tables)

    def get_table_schema(self, table_name: str) -> List[Dict[str, Any]]:
        """Get schema for specific table"""
        if table_name in self._schema_cache:
            return self._schema_cache[table_name]

        self.ensure_connection()
        query = """
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            ORDER BY ordinal_position;
        """
        try:
            with self._lock:
                with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(query, (self.schema, table_name))
                    columns = cursor.fetchall()
            self._schema_cache[table_name] = columns
            return columns
        except Exception as e:
            logger.error(f"Error getting schema for {table_name}: {e}")
            return []

    def _is_text_column(self, column: Dict[str, Any]) -> bool:
        data_type = (column.get('data_type') or '').lower()
        return data_type in TEXT_COLUMN_TYPES

    def _get_searchable_columns(self, table_name: str) -> List[str]:
        columns = self.get_table_schema(table_name)
        searchable = []
        for col in columns:
            name = col['column_name']
            if self._is_text_column(col) and SEARCHABLE_COLUMN_HINTS.search(name):
                searchable.append(name)
        return searchable

    def get_table_row_count(self, table_name: str) -> int:
        """Return approximate row count for a table."""
        if table_name in self._row_count_cache:
            return self._row_count_cache[table_name]

        query = f'SELECT COUNT(*) AS count FROM {self.schema}."{table_name}"'
        try:
            result = self.execute_query(query)
            count = int(result[0]['count']) if result else 0
            self._row_count_cache[table_name] = count
            return count
        except Exception as e:
            logger.debug(f"Row count failed for {table_name}: {e}")
            return 0

    def get_distinct_text_samples(
        self, table_name: str, column_name: str, limit: int = 8
    ) -> List[str]:
        """Get sample distinct non-empty text values from a column."""
        query = f"""
            SELECT DISTINCT "{column_name}" AS value
            FROM {self.schema}."{table_name}"
            WHERE "{column_name}" IS NOT NULL
              AND TRIM("{column_name}"::text) != ''
            ORDER BY "{column_name}"
            LIMIT {limit}
        """
        try:
            rows = self.execute_query(query)
            return [str(row['value'])[:80] for row in rows if row.get('value') is not None]
        except Exception as e:
            logger.debug(f"Distinct samples failed for {table_name}.{column_name}: {e}")
            return []

    @staticmethod
    def extract_search_terms(user_question: str) -> List[str]:
        """Extract likely entity/search terms from a natural language question."""
        stop_words = {
            'the', 'and', 'for', 'with', 'from', 'that', 'this', 'what', 'which', 'show',
            'many', 'much', 'have', 'has', 'were', 'was', 'are', 'how', 'when', 'where',
            'koto', 'kon', 'kemne', 'kemon', 'ache', 'hoy', 'hobe', 'dakho', 'dekhao',
            'beshi', 'sob', 'er', 'jonno', 'theke', 'gulo', 'ta', 'te', 'ki', 'ke',
            'amr', 'amar', 'apnar', 'cost', 'spend', 'spent', 'ads', 'ad', 'campaign',
            'performance', 'analysis', 'analyze', 'data', 'total', 'best', 'top',
        }

        terms: List[str] = []
        quoted = re.findall(r'"([^"]+)"|\'([^\']+)\'', user_question)
        for pair in quoted:
            phrase = (pair[0] or pair[1]).strip()
            if len(phrase) >= 2:
                terms.append(phrase)

        cleaned = re.sub(r'[\u0980-\u09FF]+', ' ', user_question)
        cleaned = re.sub(r'[^\w\s\-&]', ' ', cleaned)
        words = [w.strip() for w in cleaned.split() if len(w.strip()) >= 3]
        filtered = [w for w in words if w.lower() not in stop_words]

        for i in range(len(filtered) - 1):
            phrase = f"{filtered[i]} {filtered[i + 1]}"
            if phrase.lower() not in stop_words and phrase not in terms:
                terms.append(phrase)

        for word in filtered:
            if word not in terms:
                terms.append(word)

        seen = set()
        unique_terms = []
        for term in terms:
            key = term.lower()
            if key not in seen:
                seen.add(key)
                unique_terms.append(term)
        return unique_terms[:8]

    def search_entities_across_tables(self, search_terms: List[str]) -> List[Dict[str, Any]]:
        """Find which tables/columns contain values matching the search terms."""
        if not search_terms:
            return []

        self.ensure_connection()
        matches: List[Dict[str, Any]] = []
        tables = self.get_table_names()

        with self._lock:
            for table in tables:
                if table.endswith('_airbyte_tmp'):
                    continue

                for column in self._get_searchable_columns(table):
                    for term in search_terms:
                        query = f"""
                            SELECT COUNT(*) AS match_count
                            FROM {self.schema}."{table}"
                            WHERE "{column}"::text ILIKE %s
                        """
                        try:
                            self.connection.rollback()
                            with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
                                cursor.execute(query, (f'%{term}%',))
                                result = cursor.fetchall()
                            count = int(result[0]['match_count']) if result else 0
                            if count > 0:
                                matches.append({
                                    'term': term,
                                    'table': table,
                                    'column': column,
                                    'match_count': count,
                                })
                        except psycopg2.Error as e:
                            logger.debug(f"Entity search failed on {table}.{column}: {e}")
                            self.connection.rollback()

        return matches

    def rank_tables_for_question(
        self, user_question: str, entity_matches: List[Dict[str, Any]]
    ) -> List[str]:
        """Rank tables by relevance to the user question."""
        question_lower = user_question.lower()
        scores: Dict[str, int] = {table: 0 for table in self.get_table_names()}

        priority_tables = [
            'ads_insights',
            'ads_insights_platform_and_device',
            'ads_insights_action_type',
            'campaigns',
            'ad_sets',
            'ad_creatives',
            'custom_conversions',
            'activities',
        ]
        for idx, table in enumerate(priority_tables):
            if table in scores:
                scores[table] += max(1, 20 - idx)

        for table in scores:
            if table.replace('_', ' ') in question_lower or table in question_lower:
                scores[table] += 15
            columns = self.get_table_schema(table)
            for col in columns:
                col_name = col['column_name'].lower()
                if col_name in question_lower or col_name.replace('_', ' ') in question_lower:
                    scores[table] += 5

        for match in entity_matches:
            scores[match['table']] = scores.get(match['table'], 0) + 25

        keyword_map = {
            'platform': ['ads_insights_platform_and_device'],
            'device': ['ads_insights_platform_and_device'],
            'creative': ['ad_creatives'],
            'campaign': ['campaigns', 'ads_insights'],
            'conversion': ['custom_conversions', 'ads_insights_action_type'],
            'action': ['ads_insights_action_type'],
            'lead': ['ads_insights', 'campaigns'],
            'cpc': ['ads_insights'],
            'ctr': ['ads_insights'],
            'spend': ['ads_insights', 'ads_insights_platform_and_device'],
            'cost': ['ads_insights', 'ads_insights_platform_and_device'],
        }
        for keyword, related_tables in keyword_map.items():
            if keyword in question_lower:
                for table in related_tables:
                    if table in scores:
                        scores[table] += 10

        ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        return [table for table, score in ranked if score > 0]

    def get_relevant_schema_for_ai(self, user_question: str, max_tables: int = 12) -> str:
        """Build schema context focused on tables relevant to the user's question."""
        try:
            self.ensure_connection()
        except Exception:
            return "No schema information available."

        if not self.tables:
            self.discover_tables()

        search_terms = self.extract_search_terms(user_question)
        entity_matches = self.search_entities_across_tables(search_terms)
        ranked_tables = self.rank_tables_for_question(user_question, entity_matches)

        if not ranked_tables:
            ranked_tables = self.get_table_names()[:max_tables]
        else:
            for table in self.get_table_names():
                if table not in ranked_tables:
                    ranked_tables.append(table)
            ranked_tables = ranked_tables[:max_tables]

        sections = [
            "You have access to ALL tables in this database. Pick the table(s) that contain "
            "the data needed to answer the question. Use JOINs when metrics and metadata live "
            "in different tables.",
            f"Database schema: {self.schema}",
            f"Total tables available: {len(self.get_table_names())}",
        ]

        if entity_matches:
            sections.append("\n=== Data Location Hints (pre-searched) ===")
            for match in entity_matches[:15]:
                sections.append(
                    f"- Term '{match['term']}' found in {self.schema}.{match['table']}.{match['column']} "
                    f"({match['match_count']} matching rows)"
                )
        elif search_terms:
            sections.append(
                f"\nNo exact text matches found for: {', '.join(search_terms)}. "
                "Try ILIKE with partial names on account_name, campaign_name, ad_name, and name columns."
            )

        sections.append("\n=== Relevant Tables ===")
        for table in ranked_tables:
            columns = self.get_table_schema(table)
            if not columns:
                continue

            row_count = self.get_table_row_count(table)
            purpose = TABLE_PURPOSE_HINTS.get(table, "General data table")
            col_info = [f"  - {col['column_name']} ({col['data_type']})" for col in columns]
            sections.append(
                f"Table: {self.schema}.{table} (~{row_count} rows)\n"
                f"Purpose: {purpose}\n" + "\n".join(col_info)
            )

            sample_lines = []
            for col_name in self._get_searchable_columns(table)[:3]:
                samples = self.get_distinct_text_samples(table, col_name, limit=5)
                if samples:
                    sample_lines.append(f"  Sample {col_name}: {', '.join(samples)}")
            if sample_lines:
                sections.append("Sample values:\n" + "\n".join(sample_lines))

        return "\n\n".join(sections)

    def get_full_schema_for_ai(self, user_question: Optional[str] = None) -> str:
        """Get schema for NL2SQL — focused when a question is provided, full otherwise."""
        if user_question:
            return self.get_relevant_schema_for_ai(user_question)
        return self._get_all_tables_schema()

    def _get_all_tables_schema(self) -> str:
        """Get complete schema for every discovered table."""
        if not self.tables and self.connection:
            self.discover_tables()

        schemas = []
        for table in self.get_table_names():
            columns = self.get_table_schema(table)
            if columns:
                row_count = self.get_table_row_count(table)
                purpose = TABLE_PURPOSE_HINTS.get(table, "General data table")
                col_info = [f"  - {col['column_name']} ({col['data_type']})" for col in columns]
                schemas.append(
                    f"Table: {self.schema}.{table} (~{row_count} rows)\n"
                    f"Purpose: {purpose}\n" + "\n".join(col_info)
                )
        return "\n\n".join(schemas) if schemas else "No schema information available."

    def execute_query(self, query: str) -> List[Dict[str, Any]]:
        """Execute a custom query and return results"""
        self.ensure_connection()

        try:
            with self._lock:
                self.connection.rollback()
                with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(query)
                    if cursor.description:
                        results = cursor.fetchall()
                        logger.info(f"Query returned {len(results)} rows")
                        return results
                    self.connection.commit()
                    return []
        except psycopg2.Error as e:
            logger.error(f"Query execution failed: {e}")
            with self._lock:
                if self.connection:
                    self.connection.rollback()
            raise

    def get_sample_data(self, table_name: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Get sample data from a table"""
        try:
            query = f'SELECT * FROM {self.schema}."{table_name}" LIMIT {limit};'
            return self.execute_query(query)
        except Exception as e:
            logger.error(f"Error getting sample data: {e}")
            return []

    def get_table_schemas_for_ai(self, limit_tables: int = 10) -> str:
        """Get all table schemas for AI context"""
        if not self.tables and self.connection:
            self.discover_tables()

        schemas = []
        for table in self.get_table_names()[:limit_tables]:
            columns = self.get_table_schema(table)
            if columns:
                col_info = [f"    {col['column_name']} ({col['data_type']})" for col in columns[:10]]
                schemas.append(f"Table: {table}\n" + "\n".join(col_info))

        return "\n\n".join(schemas) if schemas else "No schema information available."

    def get_schema_dict(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get schema as a dictionary for API responses."""
        schema = {}
        for table in self.get_table_names():
            columns = self.get_table_schema(table)
            if columns:
                schema[table] = columns
        return schema

    # ============ SPECIFIC TABLE QUERIES ============

    def get_ads_insights_data(self, limit: int = 20) -> List[Dict]:
        """Get data from ads_insights table"""
        query = f"""
            SELECT 
                ad_name, campaign_name, account_name,
                impressions, clicks, ctr, cpc, spend,
                date_start, objective
            FROM {self.schema}.ads_insights
            WHERE spend > 0
            ORDER BY date_start DESC
            LIMIT {limit}
        """
        return self.execute_query(query)

    def get_ad_creatives_data(self, limit: int = 20) -> List[Dict]:
        """Get data from ad_creatives table"""
        query = f"""
            SELECT 
                id, name, object_story_id,
                object_type, status, url_tags
            FROM {self.schema}.ad_creatives
            LIMIT {limit}
        """
        return self.execute_query(query)

    def get_platform_device_data(self, limit: int = 20) -> List[Dict]:
        """Get data from ads_insights_platform_and_device table"""
        query = f"""
            SELECT 
                ad_name, campaign_name,
                impressions, clicks, ctr, spend,
                platform, device
            FROM {self.schema}.ads_insights_platform_and_device
            WHERE spend > 0
            ORDER BY spend DESC
            LIMIT {limit}
        """
        return self.execute_query(query)

    def get_custom_conversions_data(self, limit: int = 20) -> List[Dict]:
        """Get data from custom_conversions table"""
        query = f"""
            SELECT 
                id, name, description,
                conversion_type, status,
                retention_days, rule
            FROM {self.schema}.custom_conversions
            LIMIT {limit}
        """
        return self.execute_query(query)

    def get_ad_sets_data(self, limit: int = 20) -> List[Dict]:
        """Get data from ad_sets table"""
        query = f"""
            SELECT 
                id, name, campaign_id,
                status, start_time, end_time,
                daily_budget, lifetime_budget
            FROM {self.schema}.ad_sets
            LIMIT {limit}
        """
        return self.execute_query(query)

    def get_campaigns_data(self, limit: int = 20) -> List[Dict]:
        """Get data from campaigns table"""
        query = f"""
            SELECT 
                id, name, objective,
                status, start_time, stop_time,
                daily_budget, lifetime_budget
            FROM {self.schema}.campaigns
            LIMIT {limit}
        """
        return self.execute_query(query)

    def get_activities_data(self, limit: int = 20) -> List[Dict]:
        """Get data from activities table"""
        query = f"""
            SELECT 
                id, name, created_time,
                activity_type, status
            FROM {self.schema}.activities
            ORDER BY created_time DESC
            LIMIT {limit}
        """
        return self.execute_query(query)

    def get_action_type_data(self, limit: int = 20) -> List[Dict]:
        """Get data from ads_insights_action_type table"""
        query = f"""
            SELECT 
                ad_name, campaign_name,
                action_type, action_value,
                impressions, clicks, spend
            FROM {self.schema}.ads_insights_action_type
            WHERE spend > 0
            ORDER BY spend DESC
            LIMIT {limit}
        """
        return self.execute_query(query)

    def get_quick_stats(self) -> Dict[str, Any]:
        """Get quick statistics from all tables"""
        stats = {}

        try:
            # ads_insights stats
            query = f"""
                SELECT 
                    COUNT(*) as total_records,
                    COUNT(DISTINCT account_name) as total_companies,
                    COUNT(DISTINCT campaign_name) as total_campaigns,
                    ROUND(SUM(spend), 2) as total_spend,
                    SUM(impressions) as total_impressions,
                    SUM(clicks) as total_clicks,
                    ROUND(AVG(ctr), 2) as avg_ctr
                FROM {self.schema}.ads_insights
                WHERE spend > 0
            """
            stats['ads_insights'] = self.execute_query(query)[0] if self.execute_query(query) else {}

            # Other table counts
            for table in ['campaigns', 'ad_sets', 'ad_creatives', 'custom_conversions']:
                query = f"SELECT COUNT(*) as count FROM {self.schema}.{table}"
                result = self.execute_query(query)
                stats[f'{table}_count'] = result[0]['count'] if result else 0

        except Exception as e:
            logger.error(f"Error getting stats: {e}")

        return stats

    def close(self):
        """Close database connection"""
        with self._lock:
            if self.connection:
                self.connection.close()
                self.connection = None
                logger.info("Database connection closed")