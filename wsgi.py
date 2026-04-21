import sys
import traceback

try:
    from app import app
    print("✓ App imported successfully")
except Exception as e:
    print("=" * 50)
    print("FATAL ERROR importing app:")
    print("=" * 50)
    traceback.print_exc()
    print("=" * 50)
    sys.exit(1)

if __name__ == "__main__":
    app.run()
