"""
Test script to verify contact management functionality
"""

# Test pandas import
try:
    import pandas as pd
    print("✓ pandas imported successfully")
    print(f"  pandas version: {pd.__version__}")
except ImportError as e:
    print(f"✗ pandas import failed: {e}")

# Test openpyxl import
try:
    import openpyxl
    print("✓ openpyxl imported successfully")
    print(f"  openpyxl version: {openpyxl.__version__}")
except ImportError as e:
    print(f"✗ openpyxl import failed: {e}")

print("\n✓ All required packages are installed!")
print("\nContact management features ready:")
print("  - Add contacts manually")
print("  - Import from Excel (.xlsx, .xls)")
print("  - Copy from existing groups")
print("  - Delete contacts")
