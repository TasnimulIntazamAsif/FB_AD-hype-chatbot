from database import DatabaseManager
import pandas as pd

print("Checking ads_insights table...")
print("-" * 50)

db = DatabaseManager()
try:
    db.connect()

    # Check if table exists
    query = """
            SELECT EXISTS (SELECT \
                           FROM information_schema.tables \
                           WHERE table_schema = 'public' \
                             AND table_name = 'ads_insights'); \
            """
    result = db.execute_query(query)
    exists = result[0]['exists'] if result else False

    if exists:
        print("Table 'ads_insights' exists!")

        # Get column info
        columns = db.get_table_schema('ads_insights')
        print(f"\nColumns found: {len(columns)}")
        print("First 20 columns:")
        for col in columns[:20]:
            print(f"  - {col['column_name']} ({col['data_type']})")

        # Get sample data
        print("\n" + "=" * 50)
        print("Sample data (first 3 rows):")
        print("=" * 50)
        sample = db.get_sample_data('ads_insights', limit=3)
        if sample:
            for i, row in enumerate(sample, 1):
                print(f"\n--- Row {i} ---")
                print(f"  Ad Name: {row.get('ad_name', 'N/A')[:50]}")
                print(f"  Campaign: {row.get('campaign_name', 'N/A')[:50]}")
                print(f"  Account: {row.get('account_name', 'N/A')}")
                print(f"  Impressions: {row.get('impressions', 0)}")
                print(f"  Clicks: {row.get('clicks', 0)}")
                print(f"  CTR: {row.get('ctr', 0)}")
                print(f"  CPC: {row.get('cpc', 0)}")
                print(f"  Spend: {row.get('spend', 0)}")

        # Get quick stats
        print("\n" + "=" * 50)
        print("Quick Statistics:")
        print("=" * 50)
        stats = db.get_quick_stats()
        if stats.get('stats'):
            s = stats['stats']
            print(f"  Total records: {s.get('total_records', 'N/A'):,}")
            print(f"  Total companies: {s.get('total_companies', 'N/A')}")
            print(f"  Total campaigns: {s.get('total_campaigns', 'N/A')}")
            print(f"  Total spend: ${s.get('total_spend', 0):,.2f}")
            print(f"  Total impressions: {s.get('total_impressions', 0):,}")
            print(f"  Total clicks: {s.get('total_clicks', 0):,}")
            print(f"  Average CTR: {s.get('avg_ctr', 0):.2f}%")
            print(f"  Average CPC: ${s.get('avg_cpc', 0):.2f}")

        # Get top companies
        print("\n" + "=" * 50)
        print("Top 5 Companies by Spend:")
        print("=" * 50)
        top_companies = db.get_top_companies(5)
        for company in top_companies:
            print(f"  {company.get('account_name', 'N/A')}: ${company.get('total_spend', 0):,.2f}")

    else:
        print("Table 'ads_insights' does not exist!")
        print("\nAvailable tables:")
        tables = db.get_table_names()
        for t in tables:
            print(f"  - {t}")

    db.close()

except Exception as e:
    print(f"Error: {e}")
    import traceback

    traceback.print_exc()