"""
run.py
Single command to launch the Streamlit app.
Usage: python run.py
"""
import subprocess
import sys
import os

def main():
    os.makedirs("data/uploads", exist_ok=True)
    print("\nScientific Paper Comparison Engine")
    print("=" * 40)
    print("Starting Streamlit app...")
    print("URL: http://localhost:8501\n")

    subprocess.run([
        sys.executable, "-m", "streamlit", "run",
        "frontend/app.py",
        "--server.port", "8501",
        "--server.address", "localhost",
    ])

if __name__ == "__main__":
    main()
