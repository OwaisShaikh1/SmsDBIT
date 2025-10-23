#!/usr/bin/env python3
"""
MySMSMantra API Test — Send SMS + Delivery Status Summary (Multi-Recipient)
"""

import requests
import json
import time
from prettytable import PrettyTable  # pip install prettytable if not present

# ---------- CONFIG ----------
API_BASE_SEND = "https://api.mylogin.co.in/api/v2/SendSMS"
API_BASE_STATUS = "https://api.mylogin.co.in/api/v2/MessageStatus"

API_KEY = "****"
CLIENT_ID = "****"
SENDER_ID = "BOMBYS"
MOBILE_NUMBERS = "919769714298,918605134503"
MESSAGE = "Dear Parent, Parent Teacher Meeting on 10/2/2025 at 2pm. DBIT, THE BOMBAY SALESIAN SOCIETY"

# ---------- SEND SMS ----------
def send_sms(api_key, client_id, sender_id, message, mobile_numbers):
    url = (
        f"{API_BASE_SEND}?"
        f"ApiKey={api_key}&"
        f"ClientId={client_id}&"
        f"SenderId={sender_id}&"
        f"Message={requests.utils.requote_uri(message)}&"
        f"MobileNumbers={mobile_numbers}"
    )

    print("📱 Sending SMS via MySMSMantra API")
    print("=" * 60)
    print(f"Recipients: {mobile_numbers}")
    print(f"Message: {message[:60]}...")
    print("-" * 60)

    headers = {"Accept": "application/json"}
    response = requests.get(url, headers=headers, timeout=30)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")

    if response.status_code == 200:
        resp = response.json()
        if str(resp.get("ErrorCode")) == "0":
            data = resp.get("Data", [])
            message_data = []
            if isinstance(data, list):
                for item in data:
                    message_data.append({
                        "MobileNumber": item.get("MobileNumber"),
                        "MessageId": item.get("MessageId")
                    })
            print(f"\n✅ SMS SENT SUCCESSFULLY to {len(message_data)} recipients!")
            return {"success": True, "data": message_data}
        else:
            print(f"\n❌ SMS Failed – ErrorCode: {resp.get('ErrorCode')}")
            print("ErrorDescription:", resp.get("ErrorDescription"))
            return {"success": False, "error": resp.get("ErrorDescription")}
    else:
        print(f"\n❌ HTTP Error: {response.status_code}")
        return {"success": False, "error": f"HTTP {response.status_code}"}

# ---------- CHECK STATUS ----------
def check_delivery_status(api_key, client_id, message_id):
    url = (
        f"{API_BASE_STATUS}?"
        f"ApiKey={api_key}&"
        f"ClientId={client_id}&"
        f"MessageId={message_id}"
    )

    headers = {"Accept": "application/json"}
    response = requests.get(url, headers=headers, timeout=30)

    if response.status_code == 200:
        resp = response.json()
        if str(resp.get("ErrorCode")) == "0":
            data = resp.get("Data", {})
            if isinstance(data, dict):
                return {
                    "success": True,
                    "MobileNumber": data.get("MobileNumber"),
                    "Status": data.get("Status"),
                    "SubmitDate": data.get("SubmitDate"),
                    "DoneDate": data.get("DoneDate"),
                }
    return {"success": False, "error": response.text}

# ---------- MAIN ----------
def main():
    print("🧪 MySMSMantra API Test — Send + Delivery Summary")
    print("=" * 60)

    result = send_sms(API_KEY, CLIENT_ID, SENDER_ID, MESSAGE, MOBILE_NUMBERS)
    if not result["success"]:
        print("\n⚠️ SMS sending failed:", result.get("error"))
        return

    print("\n⏳ Waiting 10 seconds before checking delivery status...")
    time.sleep(10)

    message_data = result["data"]
    summary = []

    print("\n📡 Fetching delivery status for each recipient...")
    for entry in message_data:
        mobile = entry.get("MobileNumber")
        msg_id = entry.get("MessageId")
        status_result = check_delivery_status(API_KEY, CLIENT_ID, msg_id)

        if status_result["success"]:
            status_code = status_result.get("Status", "Unknown")
            summary.append([
                mobile,
                msg_id,
                status_code,
                status_result.get("SubmitDate", "-"),
                status_result.get("DoneDate", "-")
            ])
        else:
            summary.append([mobile, msg_id, "Error", "-", "-"])

    # ---------- SHOW SUMMARY TABLE ----------
    print("\n📊 Delivery Status Summary")
    print("=" * 60)
    table = PrettyTable(["Mobile Number", "Message ID", "Status", "Submit Time", "Delivery Time"])
    for row in summary:
        table.add_row(row)
    print(table)

    # ---------- CLASSIFY STATUSES ----------
    delivered_codes = {"DELIVRD", "DELIVERED"}
    submitted_codes = {"SUBMITTED", "SENT"}
    failed_codes = {"UNDELIV", "FAILED", "REJECTD", "EXPIRED", "ERROR"}

    delivered = sum(1 for row in summary if row[2].upper() in delivered_codes)
    submitted = sum(1 for row in summary if row[2].upper() in submitted_codes)
    failed = sum(1 for row in summary if row[2].upper() in failed_codes or row[2].upper() == "ERROR")

    print(f"\n✅ Delivered: {delivered} | 📤 Submitted: {submitted} | ❌ Failed/Error: {failed}\n")

    # ---------- EMOJI LEGEND ----------
    print("🟩 DELIVRD = Delivered | 🟨 SUBMITTED = In progress | 🟥 FAILED/REJECTD/UNDELIV = Not delivered\n")

if __name__ == "__main__":
    main()
