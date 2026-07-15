from database import DatabaseManager
from openai_client import OpenAIClient
from sql_validator import validate_readonly_sql
import logging
from typing import Dict, Any, List
import re
from datetime import datetime, date
from decimal import Decimal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ADPreferenceChatbot:
    def __init__(self):
        self.db_manager = DatabaseManager()
        self.openai_client = OpenAIClient()
        self.conversation_history = []

    def initialize(self) -> bool:
        """Initialize database connection"""
        try:
            self.db_manager.connect()
            logger.info("Chatbot initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Initialization failed: {e}")
            return False

    def _detect_language(self, text: str) -> str:
        """Detect if text is Bengali or English"""
        bengali_chars = re.compile(r'[\u0980-\u09FF]')
        if len(bengali_chars.findall(text)) > 2:
            return 'bn'
        return 'en'

    def _is_greeting(self, text: str) -> bool:
        """Check if the message is a greeting"""
        text_lower = text.lower().strip()
        greetings = ['hi', 'hello', 'hey', 'hola', 'greetings', 'হাই', 'হ্যালো', 'নমস্কার', 'আসসালামু আলাইকুম', 'ওহে',
                     'কেমন আছ', 'good morning', 'good evening']
        return any(g in text_lower for g in greetings) and len(text.split()) <= 3

    def _format_datetime(self, value):
        """Format datetime object to string"""
        if isinstance(value, datetime):
            return value.strftime('%Y-%m-%d %H:%M')
        return str(value) if value else 'N/A'

    def _get_greeting(self, language: str) -> Dict[str, Any]:
        """Get greeting response"""
        if language == 'bn':
            response = """👋 হ্যালো! স্বাগতম AD বিশ্লেষণ চ্যাটবটে!

আমি আপনার ফেসবুক অ্যাড ডাটা বিশ্লেষণে সাহায্য করতে পারি।

📊 আমি যা করতে পারি:
• যেকোনো টেবিল থেকে ডেটা খুঁজে বিশ্লেষণ
• সেরা পারফর্মিং বিজ্ঞাপন দেখাতে
• কোম্পানির ব্যয় বিশ্লেষণ করতে (যেমন: Managerium, People Desk)
• লিড জেনারেশন ক্যাম্পেইন ট্র্যাক করতে
• প্ল্যাটফর্ম ও ডিভাইস বিশ্লেষণ করতে

💡 এখনই জিজ্ঞেস করুন:
• "Managerium এর জন্য কত ad হয়েছে?"
• "People Desk এর total cost কত?"
• "সবচেয়ে ভালো CTR কোন বিজ্ঞাপনের?"

আমি আপনার প্রশ্নের জন্য অপেক্ষা করছি! 🚀"""
        else:
            response = """👋 Hello! Welcome to AD Analytics Chatbot!

I can help you analyze your Facebook Ads data.

📊 What I can do:
• Search and analyze data from any table in your database
• Show best performing ads
• Analyze company spending (e.g. Managerium, People Desk)
• Track lead generation campaigns
• Platform & device analysis

💡 Ask me now:
• "How many ads for Managerium?"
• "What is the total cost for People Desk?"
• "Show me ads with highest CTR"

I'm ready to help! 🚀"""

        return {
            "response": response,
            "data_found": True,
            "rows_returned": 0,
            "query_type": "greeting"
        }

    def _get_help(self, language: str) -> Dict[str, Any]:
        """Get help message with suggestions"""
        if language == 'bn':
            response = """🤔 আমি বুঝতে পারিনি আপনার প্রশ্ন।

আমি এই বিষয়ে সাহায্য করতে পারি:

📊 আমি যা বিশ্লেষণ করতে পারি:
• বিজ্ঞাপন পারফরম্যান্স (CTR, ক্লিক, ইম্প্রেশন)
• ব্যয় বিশ্লেষণ (CPC, CPM, মোট ব্যয়)
• লিড জেনারেশন ক্যাম্পেইন
• নির্দিষ্ট কোম্পানির ডাটা
• প্ল্যাটফর্ম ও ডিভাইস বিশ্লেষণ

💡 আপনি এই প্রশ্নগুলো করতে পারেন:
• "সবচেয়ে ভালো CTR কোন বিজ্ঞাপনের?"
• "কোন কোম্পানি সবচেয়ে বেশি খরচ করেছে?"
• "লিড জেনারেশন ক্যাম্পেইন দেখাও"
• "iBOS লিমিটেডের পারফরম্যান্স কেমন?"
• "সেরা ক্যাম্পেইন কোনগুলো?"
• "কোন ডিভাইসে ভালো পারফর্ম করে?"

ইংরেজিতেও প্রশ্ন করতে পারেন!"""
        else:
            response = """🤔 I didn't understand your question.

I can help you with these topics:

📊 What I can analyze:
• Ad Performance (CTR, clicks, impressions)
• Spending Analysis (CPC, CPM, total spend)
• Lead Generation Campaigns
• Specific Company Data
• Platform & Device Analysis

💡 You can ask these questions:
• "Show me ads with highest CTR"
• "Which company spent the most?"
• "Show lead generation campaigns"
• "iBOS Limited performance"
• "Best campaigns by CTR"
• "Which platform performs best?"

You can ask in Bengali too!"""

        return {
            "response": response,
            "data_found": True,
            "rows_returned": 0,
            "query_type": "help"
        }

    def _format_data_for_llm(self, data: List[Dict], table_name: str) -> str:
        """Format data for LLM analysis"""
        if not data:
            return "No data available."

        rows = []
        for row in data[:20]:
            row_str = " | ".join([f"{k}: {v}" for k, v in row.items() if v is not None])
            rows.append(row_str)

        return "\n".join(rows)

    def _serialize_results(self, rows: List[Dict]) -> List[Dict]:
        """Convert database rows to JSON-serializable dicts."""
        return [{key: self._serialize_value(value) for key, value in row.items()} for row in rows]

    @staticmethod
    def _serialize_value(value):
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        if isinstance(value, Decimal):
            return float(value)
        return value

    def _format_preview_table(self, rows: List[Dict], max_rows: int = 10) -> str:
        """Format query results as a readable text preview."""
        if not rows:
            return "No rows returned."

        preview_rows = rows[:max_rows]
        keys = list(preview_rows[0].keys())
        lines = []

        for i, row in enumerate(preview_rows, 1):
            parts = [f"{key}: {row.get(key, 'N/A')}" for key in keys[:6]]
            lines.append(f"{i}. " + " | ".join(parts))

        if len(rows) > max_rows:
            lines.append(f"\n... and {len(rows) - max_rows} more rows (see SQL inspector panel)")

        return "\n".join(lines)

    @staticmethod
    def _extract_tables_from_sql(sql_query: str) -> List[str]:
        """Extract referenced table names from a SQL query."""
        if not sql_query:
            return []
        pattern = re.compile(
            r'(?:FROM|JOIN)\s+(?:public\.)?["\']?([a-zA-Z_][a-zA-Z0-9_]*)["\']?',
            re.IGNORECASE,
        )
        seen = set()
        tables = []
        for match in pattern.findall(sql_query):
            name = match.lower()
            if name not in seen and name not in {'select', 'where', 'group', 'order', 'limit'}:
                seen.add(name)
                tables.append(match)
        return tables

    def process_question(self, user_question: str) -> Dict[str, Any]:
        """Process user question: greeting/help or NL2SQL + LLM analysis."""

        language = self._detect_language(user_question)

        if self._is_greeting(user_question):
            greeting = self._get_greeting(language)
            greeting["sql_query"] = None
            greeting["sql_results"] = []
            return greeting

        return self._process_with_nl2sql(user_question, language)

    def _process_with_nl2sql(self, user_question: str, language: str) -> Dict[str, Any]:
        """Generate SQL with LLM, execute on DB, analyze results with LLM."""
        result = {
            "response": "",
            "data_found": False,
            "rows_returned": 0,
            "query_type": "nl2sql",
            "sql_query": None,
            "sql_results": [],
        }

        if not self.db_manager.is_connected():
            result["response"] = (
                "দুঃখিত, ডেটাবেসে সংযোগ নেই। `.env` ফাইলে DB credentials যাচাই করুন।"
                if language == "bn"
                else "Database is not connected. Please check DB credentials in `.env`."
            )
            return result

        if not self.openai_client.client:
            result["response"] = (
                "প্রশ্নের SQL তৈরি করতে OpenAI API key দরকার। `.env` ফাইলে `OPENAI_API_KEY` যোগ করুন।"
                if language == "bn"
                else "OpenAI API key is required for natural language queries. Add `OPENAI_API_KEY` to `.env`."
            )
            return result

        schema = self.db_manager.get_relevant_schema_for_ai(user_question)
        sql_query = None
        last_error = None

        for attempt in range(3):
            try:
                sql_query = self.openai_client.generate_sql(
                    user_question, schema, error_feedback=last_error
                )
                is_valid, normalized_sql = validate_readonly_sql(sql_query)
                if not is_valid:
                    raise ValueError(normalized_sql)

                sql_query = normalized_sql
                rows = self.db_manager.execute_query(sql_query)
                serialized = self._serialize_results(rows)

                result["sql_query"] = sql_query
                result["sql_results"] = serialized
                result["rows_returned"] = len(rows)
                result["data_found"] = len(rows) > 0

                if not rows:
                    result["response"] = (
                        f"আপনার প্রশ্নের জন্য কোনো ডেটা পাওয়া যায়নি।\n\n**Generated SQL:**\n```sql\n{sql_query}\n```"
                        if language == "bn"
                        else f"No data found for your question.\n\n**Generated SQL:**\n```sql\n{sql_query}\n```"
                    )
                    return result

                data_str = self._format_data_for_llm(rows, "query_result")
                tables_used = self._extract_tables_from_sql(sql_query)
                source_label = ", ".join(tables_used) if tables_used else "database"
                llm_analysis = self.openai_client.analyze_ad_data(
                    user_question, data_str, source_label
                )
                result["response"] = self._build_nl2sql_response(
                    rows, llm_analysis, language, len(rows)
                )
                return result

            except Exception as e:
                last_error = str(e)
                logger.warning(f"NL2SQL attempt {attempt + 1} failed: {e}")

        result["sql_query"] = sql_query
        if language == "bn":
            result["response"] = (
                f"দুঃখিত, SQL query execute করতে সমস্যা হয়েছে।\n\n"
                f"**Error:** {last_error}\n\n"
                f"**Generated SQL:**\n```sql\n{sql_query or 'N/A'}\n```"
            )
        else:
            result["response"] = (
                f"Sorry, I could not execute the generated SQL.\n\n"
                f"**Error:** {last_error}\n\n"
                f"**Generated SQL:**\n```sql\n{sql_query or 'N/A'}\n```"
            )
        return result

    def _build_nl2sql_response(
        self, rows: List[Dict], analysis: str, language: str, total_rows: int
    ) -> str:
        preview = self._format_preview_table(rows)

        if language == "bn":
            return (
                f"**আপনার প্রশ্নের উত্তর:**\n\n"
                f"{'─' * 50}\n\n"
                f"**ডেটাবেস ফলাফল:** ({total_rows}টি সারি)\n\n"
                f"{preview}\n\n"
                f"{'─' * 50}\n\n"
                f"{analysis}"
            )

        return (
            f"**Answer to Your Question:**\n\n"
            f"{'─' * 50}\n\n"
            f"**Database Results:** ({total_rows} rows)\n\n"
            f"{preview}\n\n"
            f"{'─' * 50}\n\n"
            f"{analysis}"
        )

    # ============ LLM INTEGRATED METHODS (legacy helpers) ============

    def _get_top_ctr_with_llm(self, question: str, language: str) -> Dict[str, Any]:
        """Get top CTR ads with LLM analysis"""
        query = """
                SELECT ad_name, ROUND(ctr, 2) as ctr_percent, clicks, impressions, ROUND(spend, 2) as spend_usd
                FROM public.ads_insights
                WHERE ctr > 0 \
                  AND ad_name IS NOT NULL \
                  AND ad_name != ''
                ORDER BY ctr DESC LIMIT 10 \
                """
        results = self.db_manager.execute_query(query)

        if not results:
            msg = "কোনো বিজ্ঞাপন পাওয়া যায়নি।" if language == 'bn' else "No ads found."
            return {"response": msg, "data_found": False, "rows_returned": 0}

        # Format data for LLM
        data_str = self._format_data_for_llm(results, "ads_insights")

        # Get LLM analysis
        llm_analysis = self.openai_client.analyze_ad_data(question, data_str, "ads_insights")

        if language == 'bn':
            response = "**সর্বোচ্চ CTR সহ শীর্ষ ১০ বিজ্ঞাপন:**\n\n"
            response += "─" * 50 + "\n\n"
            for i, ad in enumerate(results, 1):
                response += f"{i}. {ad['ad_name'][:55]}\n"
                response += f"   CTR: {ad['ctr_percent']}%  |  ক্লিক: {ad['clicks']:,}  |  ইম্প্রেশন: {ad['impressions']:,}  |  ব্যয়: ${ad['spend_usd']:,.2f}\n\n"
            response += "\n" + "─" * 50 + "\n\n"
            response += llm_analysis
        else:
            response = "**Top 10 Ads by CTR:**\n\n"
            response += "─" * 50 + "\n\n"
            for i, ad in enumerate(results, 1):
                response += f"{i}. {ad['ad_name'][:55]}\n"
                response += f"   CTR: {ad['ctr_percent']}%  |  Clicks: {ad['clicks']:,}  |  Impressions: {ad['impressions']:,}  |  Spend: ${ad['spend_usd']:,.2f}\n\n"
            response += "\n" + "─" * 50 + "\n\n"
            response += llm_analysis

        return {
            "response": response,
            "data_found": True,
            "rows_returned": len(results),
            "query_type": "top_ctr_llm"
        }

    def _get_ibos_with_llm(self, question: str, language: str) -> Dict[str, Any]:
        """Get iBOS performance with LLM analysis"""
        query = """
                WITH campaign_stats AS (SELECT campaign_name, \
                                               ROUND(SUM(spend), 2) as total_spend, \
                                               SUM(clicks)          as total_clicks, \
                                               ROUND(AVG(ctr), 2)   as avg_ctr, \
                                               ROW_NUMBER()            OVER (PARTITION BY campaign_name ORDER BY SUM(spend) DESC) as rn \
                                        FROM public.ads_insights \
                                        WHERE account_name ILIKE '%ibos%'
                GROUP BY campaign_name
                    )
                SELECT campaign_name, total_spend as spend, total_clicks as clicks, avg_ctr as ctr
                FROM campaign_stats \
                WHERE rn = 1 \
                ORDER BY total_spend DESC LIMIT 10 \
                """
        results = self.db_manager.execute_query(query)

        if not results:
            msg = "iBOS লিমিটেডের কোনো তথ্য পাওয়া যায়নি।" if language == 'bn' else "No iBOS data found."
            return {"response": msg, "data_found": False, "rows_returned": 0}

        total_spend = sum(r['spend'] for r in results)
        total_clicks = sum(r['clicks'] for r in results)

        data_str = self._format_data_for_llm(results, "ads_insights")
        llm_analysis = self.openai_client.analyze_ad_data(question, data_str, "ads_insights")

        if language == 'bn':
            response = "**iBOS লিমিটেড - ক্যাম্পেইন পারফরম্যান্স:**\n\n"
            response += "─" * 50 + "\n\n"
            response += "সারাংশ:\n"
            response += f"   মোট ব্যয়: ${total_spend:,.2f}\n"
            response += f"   মোট ক্লিক: {total_clicks:,}\n"
            response += f"   মোট ক্যাম্পেইন: {len(results)}\n\n"
            response += "ক্যাম্পেইন লিস্ট:\n"
            response += "─" * 40 + "\n"
            for i, camp in enumerate(results, 1):
                response += f"\n{i}. {camp['campaign_name'][:55]}\n"
                response += f"   ব্যয়: ${camp['spend']:,.2f}  |  ক্লিক: {camp['clicks']:,}  |  CTR: {camp['ctr']}%"
            response += "\n\n" + "─" * 50 + "\n\n"
            response += llm_analysis
        else:
            response = "**iBOS Limited - Campaign Performance:**\n\n"
            response += "─" * 50 + "\n\n"
            response += "Summary:\n"
            response += f"   Total Spend: ${total_spend:,.2f}\n"
            response += f"   Total Clicks: {total_clicks:,}\n"
            response += f"   Total Campaigns: {len(results)}\n\n"
            response += "Campaign List:\n"
            response += "─" * 40 + "\n"
            for i, camp in enumerate(results, 1):
                response += f"\n{i}. {camp['campaign_name'][:55]}\n"
                response += f"   Spend: ${camp['spend']:,.2f}  |  Clicks: {camp['clicks']:,}  |  CTR: {camp['ctr']}%"
            response += "\n\n" + "─" * 50 + "\n\n"
            response += llm_analysis

        return {
            "response": response,
            "data_found": True,
            "rows_returned": len(results),
            "query_type": "ibos_llm"
        }

    def _get_spending_with_llm(self, question: str, language: str) -> Dict[str, Any]:
        """Get spending analysis with LLM"""
        query = """
                SELECT account_name, \
                       ROUND(SUM(spend), 2)          as total_spend,
                       COUNT(DISTINCT campaign_name) as campaign_count,
                       SUM(impressions)              as total_impressions, \
                       SUM(clicks)                   as total_clicks,
                       ROUND(AVG(ctr), 2)            as avg_ctr
                FROM public.ads_insights
                WHERE spend > 0 \
                  AND account_name IS NOT NULL
                GROUP BY account_name \
                ORDER BY total_spend DESC LIMIT 5 \
                """
        results = self.db_manager.execute_query(query)

        if not results:
            msg = "কোনো কোম্পানির তথ্য পাওয়া যায়নি।" if language == 'bn' else "No company data found."
            return {"response": msg, "data_found": False, "rows_returned": 0}

        data_str = self._format_data_for_llm(results, "ads_insights")
        llm_analysis = self.openai_client.analyze_ad_data(question, data_str, "ads_insights")

        if language == 'bn':
            response = "**শীর্ষ ব্যয়কারী কোম্পানি:**\n\n"
            response += "─" * 50 + "\n\n"
            for i, comp in enumerate(results, 1):
                response += f"{i}. {comp['account_name']}\n"
                response += f"   মোট ব্যয়: ${comp['total_spend']:,.2f}\n"
                response += f"   ক্যাম্পেইন: {comp['campaign_count']}  |  ইম্প্রেশন: {comp['total_impressions']:,}  |  ক্লিক: {comp['total_clicks']:,}\n"
                response += f"   গড় CTR: {comp['avg_ctr']}%\n\n"
            response += "\n" + "─" * 50 + "\n\n"
            response += llm_analysis
        else:
            response = "**Top Spending Companies:**\n\n"
            response += "─" * 50 + "\n\n"
            for i, comp in enumerate(results, 1):
                response += f"{i}. {comp['account_name']}\n"
                response += f"   Total Spend: ${comp['total_spend']:,.2f}\n"
                response += f"   Campaigns: {comp['campaign_count']}  |  Impressions: {comp['total_impressions']:,}  |  Clicks: {comp['total_clicks']:,}\n"
                response += f"   Avg CTR: {comp['avg_ctr']}%\n\n"
            response += "\n" + "─" * 50 + "\n\n"
            response += llm_analysis

        return {
            "response": response,
            "data_found": True,
            "rows_returned": len(results),
            "query_type": "spending_llm"
        }

    def _get_platform_with_llm(self, question: str, language: str) -> Dict[str, Any]:
        """Get platform data with LLM analysis"""
        query = """
                SELECT platform, \
                       device, \
                       ROUND(SUM(spend), 2) as total_spend,
                       SUM(impressions)     as total_impressions, \
                       SUM(clicks)          as total_clicks,
                       ROUND(AVG(ctr), 2)   as avg_ctr, \
                       ROUND(AVG(cpc), 2)   as avg_cpc
                FROM public.ads_insights_platform_and_device
                WHERE spend > 0 \
                GROUP BY platform, device
                ORDER BY total_spend DESC LIMIT 10 \
                """
        results = self.db_manager.execute_query(query)

        if not results:
            msg = "কোনো প্ল্যাটফর্ম ডেটা পাওয়া যায়নি।" if language == 'bn' else "No platform data found."
            return {"response": msg, "data_found": False, "rows_returned": 0}

        data_str = self._format_data_for_llm(results, "ads_insights_platform_and_device")
        llm_analysis = self.openai_client.get_platform_insights(data_str)

        if language == 'bn':
            response = "**প্ল্যাটফর্ম ও ডিভাইস পারফরম্যান্স:**\n\n"
            response += "─" * 50 + "\n\n"
            for i, row in enumerate(results, 1):
                response += f"{i}. {row['platform']} - {row['device']}\n"
                response += f"   ব্যয়: ${row['total_spend']:,.2f}  |  ইম্প্রেশন: {row['total_impressions']:,}\n"
                response += f"   ক্লিক: {row['total_clicks']:,}  |  CTR: {row['avg_ctr']}%  |  CPC: ${row['avg_cpc']}\n\n"
            response += "\n" + "─" * 50 + "\n\n"
            response += llm_analysis
        else:
            response = "**Platform & Device Performance:**\n\n"
            response += "─" * 50 + "\n\n"
            for i, row in enumerate(results, 1):
                response += f"{i}. {row['platform']} - {row['device']}\n"
                response += f"   Spend: ${row['total_spend']:,.2f}  |  Impressions: {row['total_impressions']:,}\n"
                response += f"   Clicks: {row['total_clicks']:,}  |  CTR: {row['avg_ctr']}%  |  CPC: ${row['avg_cpc']}\n\n"
            response += "\n" + "─" * 50 + "\n\n"
            response += llm_analysis

        return {
            "response": response,
            "data_found": True,
            "rows_returned": len(results),
            "query_type": "platform_llm"
        }

    def _get_campaigns_with_llm(self, question: str, language: str) -> Dict[str, Any]:
        """Get campaigns with LLM analysis"""
        query = """
                SELECT id, \
                       name, \
                       objective, \
                       status,
                       ROUND(daily_budget, 2) as daily_budget, \
                       start_time
                FROM public.campaigns \
                ORDER BY start_time DESC LIMIT 20 \
                """
        results = self.db_manager.execute_query(query)

        if not results:
            msg = "কোনো ক্যাম্পেইন পাওয়া যায়নি।" if language == 'bn' else "No campaigns found."
            return {"response": msg, "data_found": False, "rows_returned": 0}

        data_str = self._format_data_for_llm(results, "campaigns")
        llm_analysis = self.openai_client.get_campaign_insights(data_str)

        if language == 'bn':
            response = "**সব ক্যাম্পেইন:**\n\n"
            response += "─" * 50 + "\n\n"
            for i, row in enumerate(results, 1):
                start_time = self._format_datetime(row.get('start_time'))
                response += f"{i}. {row['name'][:50] if row['name'] else 'N/A'}\n"
                response += f"   ID: {row['id']}  |  উদ্দেশ্য: {row['objective']}  |  স্ট্যাটাস: {row['status']}\n"
                response += f"   বাজেট: ${row['daily_budget'] if row['daily_budget'] else 'N/A'}  |  শুরু: {start_time}\n\n"
            response += "\n" + "─" * 50 + "\n\n"
            response += llm_analysis
        else:
            response = "**All Campaigns:**\n\n"
            response += "─" * 50 + "\n\n"
            for i, row in enumerate(results, 1):
                start_time = self._format_datetime(row.get('start_time'))
                response += f"{i}. {row['name'][:50] if row['name'] else 'N/A'}\n"
                response += f"   ID: {row['id']}  |  Objective: {row['objective']}  |  Status: {row['status']}\n"
                response += f"   Budget: ${row['daily_budget'] if row['daily_budget'] else 'N/A'}  |  Started: {start_time}\n\n"
            response += "\n" + "─" * 50 + "\n\n"
            response += llm_analysis

        return {
            "response": response,
            "data_found": True,
            "rows_returned": len(results),
            "query_type": "campaigns_llm"
        }

    # ============ ADDITIONAL LLM METHODS ============

    def _get_top_campaigns_with_llm(self, question: str, language: str) -> Dict[str, Any]:
        """Get top campaigns with LLM"""
        query = """
                SELECT campaign_name, \
                       ROUND(AVG(ctr), 2)   as avg_ctr,
                       ROUND(SUM(spend), 2) as total_spend, \
                       SUM(clicks)          as total_clicks
                FROM public.ads_insights \
                WHERE spend > 0 \
                  AND campaign_name IS NOT NULL
                GROUP BY campaign_name \
                HAVING AVG(ctr) > 0
                ORDER BY avg_ctr DESC LIMIT 10 \
                """
        results = self.db_manager.execute_query(query)

        if not results:
            msg = "কোনো ক্যাম্পেইন পাওয়া যায়নি।" if language == 'bn' else "No campaigns found."
            return {"response": msg, "data_found": False, "rows_returned": 0}

        data_str = self._format_data_for_llm(results, "ads_insights")
        llm_analysis = self.openai_client.analyze_ad_data(question, data_str, "ads_insights")

        if language == 'bn':
            response = "**সেরা ক্যাম্পেইন (CTR অনুযায়ী):**\n\n" + "─" * 50 + "\n\n"
            for i, camp in enumerate(results, 1):
                response += f"{i}. {camp['campaign_name'][:55]}\n"
                response += f"   CTR: {camp['avg_ctr']}%  |  ব্যয়: ${camp['total_spend']:,.2f}  |  ক্লিক: {camp['total_clicks']:,}\n\n"
            response += "\n" + "─" * 50 + "\n\n" + llm_analysis
        else:
            response = "**Top Campaigns by CTR:**\n\n" + "─" * 50 + "\n\n"
            for i, camp in enumerate(results, 1):
                response += f"{i}. {camp['campaign_name'][:55]}\n"
                response += f"   CTR: {camp['avg_ctr']}%  |  Spend: ${camp['total_spend']:,.2f}  |  Clicks: {camp['total_clicks']:,}\n\n"
            response += "\n" + "─" * 50 + "\n\n" + llm_analysis

        return {
            "response": response,
            "data_found": True,
            "rows_returned": len(results),
            "query_type": "top_campaigns_llm"
        }

    def _get_lead_with_llm(self, question: str, language: str) -> Dict[str, Any]:
        """Get lead generation with LLM"""
        query = """
                SELECT campaign_name, \
                       ROUND(SUM(spend), 2)                          as total_spend, \
                       SUM(clicks)                                   as total_clicks,
                       ROUND(AVG(ctr), 2)                            as avg_ctr,
                       ROUND(SUM(spend) / NULLIF(SUM(clicks), 0), 2) as cost_per_click
                FROM public.ads_insights
                WHERE (objective = 'LEAD_GENERATION' OR campaign_name ILIKE '%lead%')
                GROUP BY campaign_name \
                ORDER BY total_spend DESC LIMIT 10 \
                """
        results = self.db_manager.execute_query(query)

        if not results:
            msg = "কোনো লিড জেনারেশন ক্যাম্পেইন পাওয়া যায়নি।" if language == 'bn' else "No lead generation campaigns found."
            return {"response": msg, "data_found": False, "rows_returned": 0}

        data_str = self._format_data_for_llm(results, "ads_insights")
        llm_analysis = self.openai_client.analyze_ad_data(question, data_str, "ads_insights")

        if language == 'bn':
            response = "**লিড জেনারেশন ক্যাম্পেইন:**\n\n" + "─" * 50 + "\n\n"
            for i, camp in enumerate(results, 1):
                response += f"{i}. {camp['campaign_name'][:50]}\n"
                response += f"   ব্যয়: ${camp['total_spend']:,.2f}  |  ক্লিক: {camp['total_clicks']:,}  |  CTR: {camp['avg_ctr']}%\n"
                response += f"   প্রতি ক্লিকে খরচ: ${camp['cost_per_click']}\n\n"
            response += "\n" + "─" * 50 + "\n\n" + llm_analysis
        else:
            response = "**Lead Generation Campaigns:**\n\n" + "─" * 50 + "\n\n"
            for i, camp in enumerate(results, 1):
                response += f"{i}. {camp['campaign_name'][:50]}\n"
                response += f"   Spend: ${camp['total_spend']:,.2f}  |  Clicks: {camp['total_clicks']:,}  |  CTR: {camp['avg_ctr']}%\n"
                response += f"   Cost Per Click: ${camp['cost_per_click']}\n\n"
            response += "\n" + "─" * 50 + "\n\n" + llm_analysis

        return {
            "response": response,
            "data_found": True,
            "rows_returned": len(results),
            "query_type": "lead_llm"
        }

    def _get_cpc_with_llm(self, question: str, language: str) -> Dict[str, Any]:
        """Get CPC with LLM"""
        query = """
                SELECT account_name, \
                       ROUND(AVG(cpc), 2) as avg_cpc,
                       ROUND(MIN(cpc), 2) as min_cpc, \
                       ROUND(MAX(cpc), 2) as max_cpc, \
                       SUM(clicks)        as clicks
                FROM public.ads_insights \
                WHERE cpc > 0 \
                  AND account_name IS NOT NULL
                GROUP BY account_name \
                ORDER BY avg_cpc ASC LIMIT 10 \
                """
        results = self.db_manager.execute_query(query)

        if not results:
            msg = "কোনো CPC তথ্য পাওয়া যায়নি।" if language == 'bn' else "No CPC data found."
            return {"response": msg, "data_found": False, "rows_returned": 0}

        data_str = self._format_data_for_llm(results, "ads_insights")
        llm_analysis = self.openai_client.analyze_ad_data(question, data_str, "ads_insights")

        if language == 'bn':
            response = "**কস্ট পার ক্লিক (CPC) বিশ্লেষণ:**\n\n" + "─" * 50 + "\n\n"
            for comp in results:
                response += f"{comp['account_name']}\n"
                response += f"   গড় CPC: ${comp['avg_cpc']}  |  সর্বনিম্ন: ${comp['min_cpc']}  |  সর্বোচ্চ: ${comp['max_cpc']}\n"
                response += f"   মোট ক্লিক: {comp['clicks']:,}\n\n"
            response += "\n" + "─" * 50 + "\n\n" + llm_analysis
        else:
            response = "**Cost Per Click (CPC) Analysis:**\n\n" + "─" * 50 + "\n\n"
            for comp in results:
                response += f"{comp['account_name']}\n"
                response += f"   Avg CPC: ${comp['avg_cpc']}  |  Min: ${comp['min_cpc']}  |  Max: ${comp['max_cpc']}\n"
                response += f"   Total Clicks: {comp['clicks']:,}\n\n"
            response += "\n" + "─" * 50 + "\n\n" + llm_analysis

        return {
            "response": response,
            "data_found": True,
            "rows_returned": len(results),
            "query_type": "cpc_llm"
        }

    def _get_action_with_llm(self, question: str, language: str) -> Dict[str, Any]:
        """Get action types with LLM"""
        query = """
                SELECT action_type, \
                       ROUND(SUM(action_value), 0) as total_actions,
                       ROUND(SUM(spend), 2)        as total_spend
                FROM public.ads_insights_action_type \
                WHERE spend > 0
                GROUP BY action_type \
                ORDER BY total_actions DESC LIMIT 20 \
                """
        results = self.db_manager.execute_query(query)

        if not results:
            msg = "কোনো অ্যাকশন টাইপ ডেটা পাওয়া যায়নি।" if language == 'bn' else "No action type data found."
            return {"response": msg, "data_found": False, "rows_returned": 0}

        data_str = self._format_data_for_llm(results, "ads_insights_action_type")
        llm_analysis = self.openai_client.analyze_ad_data(question, data_str, "ads_insights_action_type")

        if language == 'bn':
            response = "🎯 অ্যাকশন টাইপ বিশ্লেষণ\n" + "-" * 40 + "\n\n"
            for i, row in enumerate(results, 1):
                response += f"{i}. {row['action_type']}\n"
                response += f"   মোট অ্যাকশন: {row['total_actions']:,}  |  মোট ব্যয়: ${row['total_spend']:,.2f}\n\n"
            response += "\n" + "=" * 50 + "\n🧠 **AI বিশ্লেষণ:**\n\n" + llm_analysis
        else:
            response = "🎯 Action Type Analysis\n" + "-" * 40 + "\n\n"
            for i, row in enumerate(results, 1):
                response += f"{i}. {row['action_type']}\n"
                response += f"   Total Actions: {row['total_actions']:,}  |  Total Spend: ${row['total_spend']:,.2f}\n\n"
            response += "\n" + "=" * 50 + "\n🧠 **AI Analysis:**\n\n" + llm_analysis

        return {
            "response": response,
            "data_found": True,
            "rows_returned": len(results),
            "query_type": "action_llm"
        }

    def _get_creative_with_llm(self, question: str, language: str) -> Dict[str, Any]:
        """Get creatives with LLM"""
        query = "SELECT id, name, object_type, status FROM public.ad_creatives LIMIT 20"
        results = self.db_manager.execute_query(query)

        if not results:
            msg = "কোনো ক্রিয়েটিভ পাওয়া যায়নি।" if language == 'bn' else "No creatives found."
            return {"response": msg, "data_found": False, "rows_returned": 0}

        data_str = self._format_data_for_llm(results, "ad_creatives")
        llm_analysis = self.openai_client.analyze_ad_data(question, data_str, "ad_creatives")

        if language == 'bn':
            response = "🎨 অ্যাড ক্রিয়েটিভ\n" + "-" * 40 + "\n\n"
            for i, row in enumerate(results, 1):
                response += f"{i}. {row['name'][:50] if row['name'] else 'N/A'}\n"
                response += f"   ID: {row['id']}  |  টাইপ: {row['object_type']}  |  স্ট্যাটাস: {row['status']}\n\n"
            response += "\n" + "=" * 50 + "\n🧠 **AI বিশ্লেষণ:**\n\n" + llm_analysis
        else:
            response = "🎨 Ad Creatives\n" + "-" * 40 + "\n\n"
            for i, row in enumerate(results, 1):
                response += f"{i}. {row['name'][:50] if row['name'] else 'N/A'}\n"
                response += f"   ID: {row['id']}  |  Type: {row['object_type']}  |  Status: {row['status']}\n\n"
            response += "\n" + "=" * 50 + "\n🧠 **AI Analysis:**\n\n" + llm_analysis

        return {
            "response": response,
            "data_found": True,
            "rows_returned": len(results),
            "query_type": "creative_llm"
        }

    def _get_overview_with_llm(self, question: str, language: str) -> Dict[str, Any]:
        """Get overview with LLM"""
        query = """
                SELECT COUNT(DISTINCT account_name)  as companies,
                       COUNT(DISTINCT campaign_name) as campaigns,
                       ROUND(SUM(spend), 2)          as total_spend,
                       SUM(impressions)              as impressions, \
                       SUM(clicks)                   as clicks,
                       ROUND(AVG(ctr), 2)            as avg_ctr, \
                       ROUND(AVG(cpc), 2)            as avg_cpc
                FROM public.ads_insights \
                WHERE spend > 0 \
                """
        results = self.db_manager.execute_query(query)

        if not results or not results[0]['companies']:
            msg = "কোনো তথ্য পাওয়া যায়নি।" if language == 'bn' else "No data found."
            return {"response": msg, "data_found": False, "rows_returned": 0}

        stats = results[0]
        data_str = self._format_data_for_llm([stats], "ads_insights")
        llm_analysis = self.openai_client.analyze_ad_data(question, data_str, "ads_insights")

        if language == 'bn':
            response = "📊 AD প্ল্যাটফর্মের সারাংশ\n" + "=" * 50 + "\n\n"
            response += f"🏢 সক্রিয় কোম্পানি: {stats['companies']}\n"
            response += f"📢 মোট ক্যাম্পেইন: {stats['campaigns']}\n"
            response += f"💰 মোট ব্যয়: ${stats['total_spend']:,.2f}\n"
            response += f"👁️ মোট ইম্প্রেশন: {stats['impressions']:,}\n"
            response += f"👆 মোট ক্লিক: {stats['clicks']:,}\n"
            response += f"📈 গড় CTR: {stats['avg_ctr']}%\n"
            response += f"💵 গড় CPC: ${stats['avg_cpc']}\n\n"
            response += "=" * 50 + "\n🧠 **AI বিশ্লেষণ:**\n\n" + llm_analysis
        else:
            response = "📊 AD Platform Overview\n" + "=" * 50 + "\n\n"
            response += f"🏢 Active Companies: {stats['companies']}\n"
            response += f"📢 Total Campaigns: {stats['campaigns']}\n"
            response += f"💰 Total Spend: ${stats['total_spend']:,.2f}\n"
            response += f"👁️ Total Impressions: {stats['impressions']:,}\n"
            response += f"👆 Total Clicks: {stats['clicks']:,}\n"
            response += f"📈 Average CTR: {stats['avg_ctr']}%\n"
            response += f"💵 Average CPC: ${stats['avg_cpc']}\n\n"
            response += "=" * 50 + "\n🧠 **AI Analysis:**\n\n" + llm_analysis

        return {
            "response": response,
            "data_found": True,
            "rows_returned": 1,
            "query_type": "overview_llm"
        }

    def close(self):
        """Close database connection"""
        self.db_manager.close()