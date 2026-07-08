import argparse
import datetime
import json
import os
import sys
from config import load_config
from graph import build_workflow, GraphState
from email_sender import send_email
from db import NewsDatabase

DRAFT_FILE = "draft.json"

def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass # fallback for older python versions without reconfigure
        
    parser = argparse.ArgumentParser(description="The Morning Drop - Automated News Brief")
    parser.add_argument("--draft", action="store_true", help="Run phase 1: Fetch and curate stories, then pause for review.")
    parser.add_argument("--approve", action="store_true", help="Run phase 2: Use approved stories to generate and send the email.")
    parser.add_argument("--dry-run", action="store_true", help="If combined with --approve or --auto, will not send the email or update DB.")
    parser.add_argument("--auto", action="store_true", help="Run full pipeline automatically (no human review). Designed for scheduled/cron use.")
    args = parser.parse_args()

    try:
        config = load_config()
    except Exception as e:
        print(f"Configuration Error: {e}")
        return

    workflow = build_workflow()
    
    if args.draft:
        print(f"[{datetime.datetime.now()}] PHASE 1: DRAFTING STORIES")
        initial_state = {
            "config": config,
            "raw_articles": [],
            "filtered_articles": [],
            "curated_articles": [],
            "domain_briefings": {},
            "final_briefing": ""
        }
        
        # We only want to run up to the curation node
        # We can do this by executing nodes step-by-step or running to a breakpoint
        # LangGraph allows streaming node outputs
        curated_articles = []
        for output in workflow.stream(initial_state):
            if "cross_dedup" in output:
                curated_articles = output["cross_dedup"]["curated_articles"]
                break  # Stop after cross-category dedup
                
        # Save to draft.json
        with open(DRAFT_FILE, "w", encoding="utf-8") as f:
            json.dump(curated_articles, f, indent=4)
            
        print("\n*** HUMAN IN THE LOOP: DRAFT READY ***")
        print(f"Curated {len(curated_articles)} stories. Review '{DRAFT_FILE}'.")
        print("Remove any stories you don't like from the file.")
        print("When ready, run: python main.py --approve\n")
        return

    if args.approve:
        print(f"[{datetime.datetime.now()}] PHASE 2: APPROVE & SEND")
        if not os.path.exists(DRAFT_FILE):
            print(f"Error: {DRAFT_FILE} not found. Please run --draft first.")
            return
            
        with open(DRAFT_FILE, "r", encoding="utf-8") as f:
            curated_articles = json.load(f)
            
        # Manually create state bypassing fetch and curation
        state = {
            "config": config,
            "raw_articles": [],
            "filtered_articles": [],
            "curated_articles": curated_articles,
            "domain_briefings": {},
            "final_briefing": "",
            "sports_scores": "",
        }
        
        # We only need to run analyze and format
        # Instead of using the full graph which starts at fetch, 
        # we can just invoke the nodes directly since our pipeline is simple.
        from graph import cross_dedup_node, fetch_sports_scores_node, analyze_and_narrate_node, format_briefing_node

        state.update(cross_dedup_node(state))
        state.update(fetch_sports_scores_node(state))
        state.update(analyze_and_narrate_node(state))
        state.update(format_briefing_node(state))
        
        final_briefing = state["final_briefing"]
        
        if args.dry_run:
            print("\n" + "="*50)
            print("DRY RUN MODE: Final Briefing Output")
            print("="*50)
            print(final_briefing)
            print("="*50)
            print("Done.")
        else:
            print("-> Delivering email...")
            if final_briefing and "No new articles found today." not in final_briefing:
                subject = f"The Morning Drop 🌅 - {datetime.date.today().strftime('%b %d, %Y')}"
                try:
                    send_email(
                        sender_email=config.gmail_address,
                        app_password=config.gmail_app_password,
                        recipient_email=config.app_config.recipient_email,
                        subject=subject,
                        content=final_briefing
                    )
                    
                    print("-> Updating database with processed articles...")
                    db = NewsDatabase()
                    for article in curated_articles:
                        db.mark_processed(article["link"], article["domain"])
                    
                    db.prune_old_records(days=30)
                    
                    # Clean up draft file
                    os.remove(DRAFT_FILE)
                    
                    print("Pipeline completed successfully.")
                    
                except Exception as e:
                    print(f"Failed to send email: {e}")
            else:
                print("No new articles to send. Skipping email.")
        return

    if args.auto:
        print(f"[{datetime.datetime.now()}] AUTO MODE: Running full pipeline (no human review)...")
        from graph import fetch_rss_node, deduplicate_node, curation_node, cross_dedup_node, fetch_sports_scores_node, analyze_and_narrate_node, format_briefing_node

        state = {
            "config": config,
            "raw_articles": [],
            "filtered_articles": [],
            "curated_articles": [],
            "domain_briefings": {},
            "final_briefing": "",
            "sports_scores": "",
        }

        state.update(fetch_rss_node(state))
        state.update(deduplicate_node(state))
        state.update(curation_node(state))
        state.update(cross_dedup_node(state))
        state.update(fetch_sports_scores_node(state))
        state.update(analyze_and_narrate_node(state))
        state.update(format_briefing_node(state))

        final_briefing = state["final_briefing"]

        if args.dry_run:
            print("\n" + "="*50)
            print("DRY RUN MODE: Final Briefing Output")
            print("="*50)
            print(final_briefing)
            print("="*50)
            print("Done.")
        else:
            print("-> Delivering email...")
            if final_briefing and "No new articles found today." not in final_briefing:
                subject = f"The Morning Drop 🌅 - {datetime.date.today().strftime('%b %d, %Y')}"
                try:
                    send_email(
                        sender_email=config.gmail_address,
                        app_password=config.gmail_app_password,
                        recipient_email=config.app_config.recipient_email,
                        subject=subject,
                        content=final_briefing
                    )

                    print("-> Updating database with processed articles...")
                    db = NewsDatabase()
                    for article in state["curated_articles"]:
                        db.mark_processed(article["link"], article["domain"])

                    db.prune_old_records(days=30)
                    print("Auto pipeline completed successfully.")

                except Exception as e:
                    print(f"Failed to send email: {e}")
                    sys.exit(1)
            else:
                print("No new articles to send. Skipping email.")
        return

    # If no flags are provided, print help
    parser.print_help()

if __name__ == "__main__":
    main()
