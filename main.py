"""
CLI entry point for sinvest.
Usage: python main.py

Runs data fetch + report generation without launching the Streamlit UI.
Not yet implemented — placeholder for Step 2+.
"""

from core.config_loader import load_config


def main():
    config = load_config()
    print(f"sinvest — base currency: {config['user']['base_currency']}")
    print("Data fetching not yet implemented. Run: streamlit run app.py")


if __name__ == "__main__":
    main()
