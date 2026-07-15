"""
MCP Server for AD Analytics Chatbot
====================================
এই সার্ভারটি MCP (Model Context Protocol) ক্লায়েন্টদের (যেমন Claude Desktop, Cursor)
আমাদের AD অ্যানালাইসিস চ্যাটবট ব্যবহার করার সুযোগ দেয়।

Run: python mcp_server.py
"""

import os
import sys
import logging
from pathlib import Path

# Project root path যোগ করুন
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastmcp import FastMCP
from chatbot import ADPreferenceChatbot
from dotenv import load_dotenv

# Environment variables লোড করুন
load_dotenv()

# Logging কনফিগার করুন
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================
# Chatbot ইনিশিয়ালাইজ করুন
# ============================================
chatbot: ADPreferenceChatbot | None = None

def get_chatbot() -> ADPreferenceChatbot:
    """Singleton pattern এ chatbot ইনিশিয়ালাইজ করুন"""
    global chatbot
    if chatbot is None:
        logger.info("Initializing AD Preference Chatbot...")
        chatbot = ADPreferenceChatbot()
        if not chatbot.initialize():
            logger.error("Failed to initialize chatbot. Check database connection.")
            logger.warning("Running in limited mode - database may not be connected")
        else:
            logger.info("Chatbot initialized successfully!")
    return chatbot

# MCP সার্ভার তৈরি করুন
mcp = FastMCP("AD Analytics Bot")


# ============================================
# MCP TOOL: ask_ad_analytics
# ============================================
@mcp.tool()
def ask_ad_analytics(question: str) -> str:
    """
    Ask questions about Facebook Ads data from the database.

    This tool can answer questions about:
    - Campaign performance (CTR, CPC, impressions, clicks, spend)
    - Company/account spending analysis
    - Lead generation campaigns
    - Platform and device performance
    - Specific company performance (e.g., iBOS Limited, Managerium)
    - Best performing ads and campaigns

    Examples:
    - "What are the best performing ads?"
    - "Which company spent the most on ads?"
    - "Show me iBOS Limited campaign performance"
    - "How many ads for Managerium?"
    - "What is the total cost for People Desk?"
    - "Analyze lead generation campaigns"

    Args:
        question (str): Natural language question about ad data

    Returns:
        str: Detailed response with data and AI analysis
    """
    try:
        bot = get_chatbot()

        if not bot:
            return "⚠️ Chatbot is not available. Please check the server logs."

        # Check if database is connected
        if not bot.db_manager.is_connected():
            return (
                "⚠️ Database is not connected. Please check your `.env` file and ensure:\n"
                "1. DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD are correct\n"
                "2. The database server is running\n"
                "3. Your network can reach the database server"
            )

        # Process the question
        logger.info(f"Processing question: {question[:50]}...")
        result = bot.process_question(question)

        # Extract response
        response = result.get("response", "Sorry, I could not process your question.")

        # Add metadata if available
        if result.get("data_found"):
            rows = result.get("rows_returned", 0)
            query_type = result.get("query_type", "unknown")
            response += f"\n\n📊 *Found {rows} records | Query type: {query_type}*"

        # Add SQL if available (for debugging)
        if result.get("sql_query"):
            sql_preview = result['sql_query'][:200]
            response += f"\n\n🔍 *SQL: {sql_preview}...*"

        return response

    except Exception as e:
        logger.error(f"Error in ask_ad_analytics: {e}")
        return f"❌ An error occurred: {str(e)}"


# ============================================
# MCP TOOL: get_table_info
# ============================================
@mcp.tool()
def get_table_info() -> str:
    """
    Get information about available tables in the database.

    Returns:
        str: List of available tables and their row counts
    """
    try:
        bot = get_chatbot()

        if not bot or not bot.db_manager.is_connected():
            return "Database is not connected. Please check your configuration."

        tables = bot.db_manager.get_table_names()
        if not tables:
            return "No tables discovered in the database."

        result = "📊 **Available Tables:**\n\n"
        for table in tables:
            try:
                count = bot.db_manager.get_table_row_count(table)
                result += f"• `{table}` - {count:,} rows\n"
            except:
                result += f"• `{table}` - (count unavailable)\n"

        return result

    except Exception as e:
        return f"❌ Error getting table info: {str(e)}"


# ============================================
# MCP TOOL: get_schema
# ============================================
@mcp.tool()
def get_schema(table_name: str = None) -> str:
    """
    Get schema information for a specific table or all tables.

    Args:
        table_name (str, optional): Specific table name. If None, shows all tables.

    Returns:
        str: Schema information with column names and data types
    """
    try:
        bot = get_chatbot()

        if not bot or not bot.db_manager.is_connected():
            return "Database is not connected. Please check your configuration."

        tables = bot.db_manager.get_table_names()

        if table_name:
            if table_name not in tables:
                return f"Table '{table_name}' not found. Available tables: {', '.join(tables)}"
            tables_to_show = [table_name]
        else:
            tables_to_show = tables[:10]  # Limit to 10 tables for readability

        result = f"📋 **Schema Information**\n\n"
        for table in tables_to_show:
            columns = bot.db_manager.get_table_schema(table)
            if columns:
                result += f"**Table: {table}**\n"
                for col in columns[:15]:
                    result += f"  • {col['column_name']} ({col['data_type']})\n"
                if len(columns) > 15:
                    result += f"  ... and {len(columns) - 15} more columns\n"
                result += "\n"

        return result

    except Exception as e:
        return f"❌ Error getting schema: {str(e)}"


# ============================================
# MCP TOOL: get_quick_stats
# ============================================
@mcp.tool()
def get_quick_stats() -> str:
    """
    Get quick statistics about the ad data.

    Returns:
        str: Summary statistics including total spend, impressions, clicks, etc.
    """
    try:
        bot = get_chatbot()

        if not bot or not bot.db_manager.is_connected():
            return "Database is not connected. Please check your configuration."

        stats = bot.db_manager.get_quick_stats()

        if not stats or not stats.get('ads_insights'):
            return "No statistics available."

        s = stats['ads_insights']
        result = "📊 **Quick Statistics:**\n\n"
        result += f"• Total Records: {s.get('total_records', 0):,}\n"
        result += f"• Total Companies: {s.get('total_companies', 0)}\n"
        result += f"• Total Campaigns: {s.get('total_campaigns', 0)}\n"
        result += f"• Total Spend: ${s.get('total_spend', 0):,.2f}\n"
        result += f"• Total Impressions: {s.get('total_impressions', 0):,}\n"
        result += f"• Total Clicks: {s.get('total_clicks', 0):,}\n"
        result += f"• Average CTR: {s.get('avg_ctr', 0)}%\n"

        # Add other table counts
        for table in ['campaigns', 'ad_sets', 'ad_creatives', 'custom_conversions']:
            key = f'{table}_count'
            if key in stats:
                result += f"• {table.replace('_', ' ').title()}: {stats[key]}\n"

        return result

    except Exception as e:
        return f"❌ Error getting stats: {str(e)}"


# ============================================
# SERVER RUN
# ============================================
if __name__ == "__main__":
    print("=" * 60)
    print("🤖 AD Analytics MCP Server")
    print("=" * 60)
    print("\n📌 This server provides MCP tools for Facebook Ads data analysis.")
    print("📌 Tools available:")
    print("   • ask_ad_analytics - Ask questions about ad data")
    print("   • get_table_info - Get list of available tables")
    print("   • get_schema - Get table schema information")
    print("   • get_quick_stats - Get quick statistics")
    print("\n🔌 Starting MCP server on stdio transport...")
    print("   (For use with Claude Desktop, Cursor, or other MCP clients)")
    print("=" * 60)

    # MCP সার্ভার রান করুন
    mcp.run()