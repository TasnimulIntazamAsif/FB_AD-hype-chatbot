import os
import re
import httpx
from openai import OpenAI
from dotenv import load_dotenv
import logging

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OpenAIClient:
    def __init__(self):
        api_key = os.getenv('OPENAI_API_KEY')

        # Remove proxy environment variables that cause issues
        for proxy_var in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']:
            if proxy_var in os.environ:
                del os.environ[proxy_var]

        try:
            if not api_key or api_key == '':
                logger.warning("OpenAI API key not found. Running in demo mode.")
                self.client = None
            else:
                http_client = httpx.Client(timeout=60.0)
                self.client = OpenAI(api_key=api_key, http_client=http_client)
                logger.info("OpenAI client initialized successfully")
        except Exception as e:
            logger.error(f"OpenAI init failed: {e}")
            self.client = None

        self.model = os.getenv('OPENAI_MODEL', 'gpt-4.1-mini')
        self.max_tokens = 800
        self.temperature = 0.7

    def generate_sql(self, user_question: str, schema_context: str, error_feedback: str = None) -> str:
        """Generate a PostgreSQL SELECT query from natural language."""
        if not self.client:
            raise ValueError("OpenAI API key is not configured.")

        system_prompt = """You are an expert PostgreSQL query writer for Facebook Ads analytics.
Return ONLY one valid PostgreSQL SELECT query. No explanation, no markdown fences.

Rules:
- You have access to ALL tables listed in the schema — do NOT default to ads_insights only
- Choose the table(s) that actually contain the data needed for the question
- Use JOINs when metrics are in one table and names/metadata in another (e.g. campaigns + ads_insights)
- Follow "Data Location Hints" when provided — they show where search terms were found
- Use ONLY tables and columns from the provided schema
- Tables are in the public schema (use public.table_name or schema.table_name)
- SELECT queries only — never INSERT, UPDATE, DELETE, or DDL
- Always include LIMIT (default 100 unless user asks for fewer rows)
- Use ILIKE '%term%' for case-insensitive partial matching on company/ad/campaign names
- For company/product questions (e.g. Managerium, People Desk), search account_name, campaign_name, ad_name, and name columns
- Use ROUND() for CTR, CPC, spend, and other metrics when aggregating
- Use COALESCE for nullable numeric fields in aggregations
- For Bengali questions, query English column values in the database
- Prefer meaningful column aliases (snake_case)
- Use GROUP BY correctly when using aggregate functions"""

        user_prompt = f"""Database Schema:
{schema_context}

User Question: {user_question}"""

        if error_feedback:
            user_prompt += f"""

The previous query failed. Fix it and return a corrected SELECT query only.
Error: {error_feedback}"""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0,
            max_tokens=600,
        )
        return self._clean_sql(response.choices[0].message.content.strip())

    @staticmethod
    def _clean_sql(raw_sql: str) -> str:
        sql = raw_sql.strip()
        if sql.startswith("```"):
            lines = [line for line in sql.split("\n") if not line.strip().startswith("```")]
            sql = "\n".join(lines).strip()
        sql = re.sub(r"^sql\s*", "", sql, flags=re.IGNORECASE)
        return sql.rstrip(";").strip()

    def _is_precise_question(self, question: str) -> bool:
        """Detect if the question is precise (needs simple answer) or broad (needs analysis)"""
        question_lower = question.lower()
        
        # Keywords that indicate precise questions
        precise_keywords = [
            'what is', 'what are', 'how much', 'how many', 'what was',
            'what\'s', 'show me', 'give me', 'tell me', 'list',
            'ctr', 'cpc', 'spend', 'impressions', 'clicks', 'conversions',
            'cost', 'roas', 'cpm', 'frequency', 'reach'
        ]
        
        # Keywords that indicate broad questions needing analysis
        broad_keywords = [
            'analyze', 'analysis', 'insights', 'trends', 'performance',
            'recommend', 'suggest', 'optimize', 'improve', 'strategy',
            'compare', 'best', 'worst', 'top', 'bottom', 'overview',
            'summary', 'report', 'evaluation', 'assessment'
        ]
        
        # Check for broad keywords first
        for keyword in broad_keywords:
            if keyword in question_lower:
                return False
        
        # Check for precise keywords
        for keyword in precise_keywords:
            if keyword in question_lower:
                return True
        
        # Default to broad if unclear
        return False
    
    def _needs_suggestions(self, question: str) -> bool:
        """Detect if the question explicitly asks for suggestions/recommendations"""
        question_lower = question.lower()
        suggestion_keywords = [
            'suggest', 'recommend', 'recommendation', 'advice', 'tip',
            'how to improve', 'optimize', 'better', 'should i', 'what should',
            'strategy', 'plan', 'action'
        ]
        return any(keyword in question_lower for keyword in suggestion_keywords)

    def analyze_ad_data(self, user_question: str, data: str, table_name: str = "query_result") -> str:
        """Analyze ad data using OpenAI"""
        if not self.client:
            return self._get_fallback_response(user_question, data)

        is_precise = self._is_precise_question(user_question)
        needs_suggestions = self._needs_suggestions(user_question)

        if is_precise:
            # For precise questions, give direct answer only
            prompt = f"""
You are an expert Facebook Ads analyst. Answer the user's question directly and concisely based on the data.
Do NOT provide extra analysis, insights, trends, or recommendations unless explicitly asked.

User Question: {user_question}

Data Source: {table_name}

Data from Database:
{data}

Provide ONLY a direct, clear answer to the question. Be specific and use the data. Keep it brief.
"""
        else:
            # For broad questions, provide comprehensive analysis
            sections = ["**Direct Answer:**\n- Clear and concise answer to the user's specific question"]
            
            sections.append("**Key Insights:**\n- 3-5 most important findings from the data\n- Highlight any standout metrics or anomalies")
            sections.append("**Trends:**\n- Any noticeable patterns in the data\n- Performance trends (improving or declining)")
            
            if needs_suggestions:
                sections.append("**Actionable Recommendations:**\n- 3-5 specific, actionable suggestions for improvement\n- Prioritize recommendations by impact\n- Include optimization strategies")
            
            sections.append("**Areas of Concern:**\n- Any red flags or areas needing attention\n- Underperforming metrics to watch")

            prompt = f"""
You are an expert Facebook Ads analyst. Analyze the following data and provide comprehensive insights.
The data may come from one or more database tables — interpret columns in context.

User Question: {user_question}

Data Source: {table_name}

Data from Database:
{data}

Please provide a well-structured analysis with the following sections:

{chr(10).join(sections)}

Format your response with clear section headers (bold with colon) and bullet points. Add a blank line between each section. Be specific and data-driven in your recommendations.
"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system",
                     "content": "You are an expert Facebook Ads analyst. Provide actionable insights."},
                    {"role": "user", "content": prompt}
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"OpenAI analysis error: {e}")
            return self._get_fallback_response(user_question, data)

    def get_campaign_insights(self, campaign_data: str) -> str:
        """Get deep insights about campaigns"""
        if not self.client:
            return self._get_campaign_fallback(campaign_data)

        prompt = f"""
Analyze these Facebook ad campaigns and provide comprehensive insights:

{campaign_data}

Please provide a well-structured analysis with the following sections:

🎯 **Campaign Performance Overview**
- Summary of overall campaign performance

🏆 **Best Performing Campaigns**
- Top campaigns and why they're performing well
- Key success factors

⚠️ **Underperforming Campaigns**
- Campaigns that need attention
- Reasons for poor performance

💡 **Optimization Strategies**
- Specific recommendations to improve performance
- A/B testing suggestions

💰 **Budget Allocation Recommendations**
- How to redistribute budget for better ROI
- Priority campaigns to fund

Format with clear headers and bullet points. Be specific and actionable.
"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a Facebook Ads optimization expert."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.6,
                max_tokens=600
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Campaign insights error: {e}")
            return self._get_campaign_fallback(campaign_data)

    def get_platform_insights(self, platform_data: str) -> str:
        """Get platform and device insights"""
        if not self.client:
            return self._get_platform_fallback(platform_data)

        prompt = f"""
Analyze this platform and device performance data:

{platform_data}

Please provide a well-structured analysis with the following sections:

🎯 **Performance Overview**
- Summary of platform and device performance

🏆 **Best Performing Platforms/Devices**
- Top performers and why they're successful
- Key metrics that stand out

⚠️ **Underperforming Platforms/Devices**
- Platforms/devices needing attention
- Reasons for poor performance

💡 **Optimization Recommendations**
- How to improve performance across platforms
- Device-specific optimization strategies

💰 **Budget Allocation Strategy**
- Where to allocate budget for best ROI
- Platform prioritization recommendations

Format with clear headers and bullet points. Be specific and actionable.
"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert in ad platform optimization."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.6,
                max_tokens=500
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Platform insights error: {e}")
            return self._get_platform_fallback(platform_data)

    def _get_fallback_response(self, question: str, data: str) -> str:
        """Fallback when OpenAI is not available"""
        return """
**Direct Answer:**
Based on the data retrieved, here's what I found for your question.

**Key Insights:**
• Review the data above for key metrics
• Compare performance against your benchmarks

**Trends:**
• Monitor CTR trends over time
• Track spend vs performance ratios

**Actionable Recommendations:**
• Focus on ads with CTR above 3%
• Optimize CPC based on industry averages
• A/B test different ad creatives
• Allocate more budget to top performers

**Areas of Concern:**
• Watch for underperforming campaigns
• Monitor unusual spend patterns

**Data Summary:**
""" + data[:500] + """

*To get detailed AI-powered insights, please add your OpenAI API key to the .env file.*
"""

    def _get_campaign_fallback(self, data: str) -> str:
        return """
🎯 **Campaign Performance Overview**
Review the campaign data above to understand overall performance.

🏆 **Best Performing Campaigns**
• Focus on campaigns with highest CTR
• Identify what makes them successful

⚠️ **Underperforming Campaigns**
• Pause campaigns with poor performance
• Analyze why they're underperforming

💡 **Optimization Strategies**
• A/B test different ad creatives
• Refine targeting parameters
• Test different bidding strategies

💰 **Budget Allocation Recommendations**
• Increase budget for top performers
• Reduce spend on underperforming campaigns
• Test new campaigns with small budgets

💡 *Add OpenAI API key for detailed AI-powered analysis.*
"""

    def _get_platform_fallback(self, data: str) -> str:
        return """
🎯 **Performance Overview**
Review the platform and device data above to understand performance.

🏆 **Best Performing Platforms/Devices**
• Focus on platforms with best ROI
• Identify top-performing device types

⚠️ **Underperforming Platforms/Devices**
• Analyze why certain platforms underperform
• Consider pausing poor performers

💡 **Optimization Recommendations**
• Implement device-specific optimizations
• Test different platform combinations
• Refine targeting by platform

💰 **Budget Allocation Strategy**
• Allocate more budget to top performers
• Test new platforms with small budgets
• Monitor performance by device type

💡 *Add OpenAI API key for detailed AI-powered analysis.*
"""
