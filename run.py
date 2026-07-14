import argparse
import sys
import uvicorn
from src.database import init_db
from src.gaper_scraper import scrape_gaper_brand, get_brand_profile
from src.discovery import discover_threads
from src.pipeline import run_pipeline, approve_and_queue_post
import config

def main():
    parser = argparse.ArgumentParser(description="Gaper SEO/GEO/AEO AI Backlink & Citation Agent")
    parser.add_argument("--dashboard", action="store_true", help="Launch the FastAPI QA panel dashboard")
    parser.add_argument("--discover", action="store_true", help="Run SERP and RSS discovery pipelines")
    parser.add_argument("--scrape-brand", action="store_true", help="Rescrape details and logo from Gaper.io website")
    parser.add_argument("--process", type=str, metavar="URL", help="Run the full backlink pipeline for a single target URL")
    
    args = parser.parse_args()
    
    # Initialize DB (Auto-creates SQLite file and tables)
    print("Initializing SQLite Database (gaper_agent.db)...")
    init_db()
    
    if args.scrape_brand:
        print("Scraping brand details from Gaper.io...")
        profile = scrape_gaper_brand()
        print("\n--- Brand Profile ---")
        print(f"Description: {profile.get('description')}")
        print(f"Logo: {profile.get('logo_url')}")
        print(f"USPs:\n{profile.get('usps')}")
        return
        
    if args.discover:
        print("Running discovery pipeline (Google SERP and RSS checks)...")
        urls = discover_threads()
        print(f"\nDiscovery finished! Found {len(urls)} fresh opportunities.")
        for u in urls:
            print(f"- {u}")
        return
        
    if args.process:
        url = args.process
        print(f"Processing URL: {url}...")
        try:
            res = run_pipeline(url)
            print("\n--- Pipeline Result ---")
            print(f"ID: {res['thread_id']}")
            print(f"Status: {res['status']}")
            print(f"Is Ghost: {res['is_ghost']}")
            print(f"Scores: SEO {res['scores']['seo']}%, GEO {res['scores']['geo']}%, AEO {res['scores']['aeo']}%")
            print(f"Generated Reply:\n{res['reply_text']}")
            
            # Interactive prompt for approval
            approve = input("\nDo you want to approve and queue this post? (y/N): ").strip().lower()
            if approve in ('y', 'yes'):
                approve_and_queue_post(res['thread_id'])
                print("Post queued successfully.")
        except Exception as e:
            print(f"Pipeline error: {e}", file=sys.stderr)
        return
        
    if args.dashboard:
        # Pre-scrape brand if empty
        get_brand_profile()
        
        print("\n" + "="*50)
        print("🚀 Launching Gaper Backlink Dashboard")
        print("🔗 Open http://localhost:8000 in your browser to view the QA Panel")
        print("="*50 + "\n")
        
        uvicorn.run("src.dashboard:app", host="localhost", port=8000, reload=False)
        return
        
    parser.print_help()

if __name__ == "__main__":
    main()
