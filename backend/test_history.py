#!/usr/bin/env python3
"""
MySMSMantra API Test – SMS History / Report (GET Method)
"""

import requests
import json
from datetime import date

# ---------- CONFIG ----------
API_BASE_REPORT = "https://api.mylogin.co.in/api/v2/SMS"
API_KEY = "****"
CLIENT_ID = "****"

START = 0
LENGTH = 50
FROM_DATE = "2025-10-01"
END_DATE = date.today().strftime("%Y-%m-%d")


def fetch_sms_history(api_key, client_id, start, length, fromdate, enddate):
    """
    Fetch SMS history/report using MySMSMantra API (GET method - documented format)
    """
    url = (
        f"{API_BASE_REPORT}?ApiKey={api_key}&"
        f"ClientId={client_id}&"
        f"start={start}&"
        f"length={length}&"
        f"fromdate={fromdate}&"
        f"enddate={enddate}"
    )

    print("📊 Fetching SMS History via MySMSMantra API")
    print("=" * 60)
    print(f"URL: {API_BASE_REPORT}")
    print(f"Method: GET")
    print(f"Params: start={start}, length={length}, fromdate={fromdate}, enddate={enddate}")
    print("-" * 60)

    try:
        headers = {
            'Accept': 'application/json'
        }
        response = requests.get(url, headers=headers, timeout=30)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")

        if response.status_code == 200:
            try:
                json_response = response.json()
                error_code = str(json_response.get('ErrorCode', ''))
                if error_code == '0':
                    print("\n✅ History fetched successfully!")
                    print(f"Data count: {len(json_response.get('Data', []))}")
                    return {'success': True, 'response': json_response}
                else:
                    print(f"\n❌ Failed – ErrorCode: {error_code}")
                    print("ErrorDescription:", json_response.get('ErrorDescription'))
                    return {'success': False, 'error': json_response}
            except json.JSONDecodeError:
                print("\n⚠️ Non-JSON response received")
                return {'success': False, 'error': 'Invalid JSON response'}
        else:
            print(f"\n❌ HTTP Error: {response.status_code}")
            return {'success': False, 'error': f'HTTP {response.status_code}'}

    except requests.RequestException as e:
        print(f"\n❌ Request Error: {e}")
        return {'success': False, 'error': str(e)}


def main():
    print("🧪 MySMSMantra API Test – History / Report")
    print("=" * 60)

    if not all([API_KEY, CLIENT_ID]):
        print("❌ Missing required configuration! Fill in API_KEY & CLIENT_ID")
        return

    result = fetch_sms_history(API_KEY, CLIENT_ID, START, LENGTH, FROM_DATE, END_DATE)

    if result['success']:
        print("\n🎉 Test completed successfully!")
    else:
        print("\n⚠️ Test failed:")
        print(result.get('error'))


if __name__ == "__main__":
    main()
