import os
import time
import datetime
import requests
import pytz
import json

# CONFIG
TELEGRAM_TOKEN   = os.getenv("8518811167:AAEiPN-wa_bdiZCHGCDmas8FaH84lhYe1og")
TELEGRAM_CHAT_ID = os.getenv("8773798653")

EBAY_APP_ID      = os.getenv("BrianCor-Mysniper-PRD-9a937d837-dfdfab74")  # Free eBay developer key

SNIPE_SECONDS    = 2  # Place bid this many seconds before auction ends

# List of auctions to snipe
# Add item numbers and max bids here
AUCTIONS = [
    # {"item_id": "123456789012", "max_bid": 50.00, "description": "Luka Doncic PSA 10"},
    # {"item_id": "987654321098", "max_bid": 25.00, "description": "Wembanyama rookie raw"},
]

def now_pt():
    return datetime.datetime.now(pytz.timezone("America/Los_Angeles"))

def send_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print(message)
        return
    try:
        url = "https://api.telegram.org/bot" + TELEGRAM_TOKEN + "/sendMessage"
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": message}, timeout=10)
    except Exception as e:
        print("Telegram error: " + str(e))

def get_auction_info(item_id):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        url = "https://www.ebay.com/itm/" + item_id
        r   = requests.get(url, headers=headers, timeout=10)

        import re

        # Get current price
        price_match = re.search(r'"auctionPrice":\{"value":"([^"]+)"', r.text)
        if not price_match:
            price_match = re.search(r'itemprop="price" content="([^"]+)"', r.text)
        current_price = float(price_match.group(1)) if price_match else 0.0

        # Get end time
        time_match = re.search(r'"endTime":"([^"]+)"', r.text)
        end_time_str = time_match.group(1) if time_match else None

        # Get title
        title_match = re.search(r'<title>([^<]+)</title>', r.text)
        title = title_match.group(1).strip() if title_match else "Unknown Item"

        return {
            "title":         title,
            "current_price": current_price,
            "end_time_str":  end_time_str,
            "url":           url,
        }

    except Exception as e:
        print("Auction info error: " + str(e))
        return None

def seconds_until_end(end_time_str):
    try:
        import re
        end_time_str = re.sub(r'\.\d+', '', end_time_str).replace('Z', '+00:00')
        end_time = datetime.datetime.fromisoformat(end_time_str)
        now      = datetime.datetime.now(datetime.timezone.utc)
        diff     = (end_time - now).total_seconds()
        return diff
    except Exception as e:
        print("Time parse error: " + str(e))
        return None

def place_bid(item_id, max_bid, description):
    send_telegram(
        "EBAY SNIPE TRIGGERED!\n\n"
        "Item: " + description + "\n"
        "Item ID: " + item_id + "\n"
        "Max bid: $" + str(max_bid) + "\n"
        "Time: " + now_pt().strftime("%I:%M:%S %p PT") + "\n\n"
        "Opening eBay to place bid now!\n"
        "Link: https://www.ebay.com/itm/" + item_id
    )

    print("Placing bid on item " + item_id + " for $" + str(max_bid))

def monitor_auctions():
    if not AUCTIONS:
        print("No auctions in list. Add item IDs to the AUCTIONS list.")
        return

    print("[" + now_pt().strftime("%H:%M:%S") + "] Monitoring " + str(len(AUCTIONS)) + " auctions...")

    for auction in AUCTIONS:
        item_id     = auction["item_id"]
        max_bid     = auction["max_bid"]
        description = auction.get("description", item_id)

        info = get_auction_info(item_id)
        if not info:
            print("  Could not get info for item " + item_id)
            continue

        current_price = info["current_price"]
        end_time_str  = info["end_time_str"]

        if not end_time_str:
            print("  " + description + " | Could not get end time")
            continue

        seconds_left = seconds_until_end(end_time_str)
        if seconds_left is None:
            continue

        print("  " + description + " | Current: $" + str(current_price) + " | Time left: " + str(int(seconds_left)) + "s")

        if current_price >= max_bid:
            print("  Current price $" + str(current_price) + " exceeds max bid $" + str(max_bid) + " — skipping")
            send_telegram(
                "SNIPE SKIPPED: " + description + "\n"
                "Current price $" + str(current_price) + " exceeds your max bid of $" + str(max_bid)
            )
            continue

        if 0 < seconds_left <= SNIPE_SECONDS + 30:
            print("  SNIPE WINDOW APPROACHING for " + description + "!")
            wait_time = seconds_left - SNIPE_SECONDS
            if wait_time > 0:
                print("  Waiting " + str(round(wait_time, 1)) + " seconds before bidding...")
                time.sleep(wait_time)
            place_bid(item_id, max_bid, description)

        elif seconds_left <= 0:
            print("  Auction ended for " + description)

        time.sleep(1)

def add_auction(item_id, max_bid, description=""):
    AUCTIONS.append({
        "item_id":     item_id,
        "max_bid":     max_bid,
        "description": description or item_id,
    })
    msg = (
        "Auction added to snipe list!\n\n"
        "Item ID: " + item_id + "\n"
        "Description: " + (description or "N/A") + "\n"
        "Max bid: $" + str(max_bid) + "\n"
        "Will bid " + str(SNIPE_SECONDS) + " seconds before end\n"
        "Link: https://www.ebay.com/itm/" + item_id
    )
    print(msg)
    send_telegram(msg)

def get_updates(offset=None):
    try:
        url    = "https://api.telegram.org/bot" + TELEGRAM_TOKEN + "/getUpdates"
        params = {"timeout": 10}
        if offset:
            params["offset"] = offset
        r = requests.get(url, params=params, timeout=15)
        return r.json().get("result", [])
    except:
        return []

def handle_message(text):
    text  = text.strip()
    parts = text.split()

    if parts[0].lower() == "snipe" and len(parts) >= 3:
        try:
            item_id     = parts[1]
            max_bid     = float(parts[2])
            description = " ".join(parts[3:]) if len(parts) > 3 else ""
            add_auction(item_id, max_bid, description)
        except:
            send_telegram(
                "Could not parse snipe command. Try:\n"
                "snipe 123456789012 50.00 Luka Doncic PSA 10"
            )
        return

    if text.lower() == "list":
        if not AUCTIONS:
            send_telegram("No auctions in snipe list.")
        else:
            lines = ["Current snipe list:\n"]
            for a in AUCTIONS:
                lines.append(
                    "Item: " + a["description"] + "\n"
                    "ID: " + a["item_id"] + "\n"
                    "Max bid: $" + str(a["max_bid"]) + "\n"
                )
            send_telegram("\n".join(lines))
        return

    send_telegram(
        "eBay Sniper Commands:\n\n"
        "Add auction:\nsnipe ITEM_ID MAX_BID DESCRIPTION\n\n"
        "Example:\nsnipe 123456789012 50.00 Luka Doncic PSA 10\n\n"
        "List auctions:\nlist"
    )

if __name__ == "__main__":
    print("eBay Auction Sniper Bot")
    print("Snipe time: " + str(SNIPE_SECONDS) + " seconds before end")
    print("Telegram: " + ("enabled" if TELEGRAM_TOKEN else "disabled"))
    print()

    send_telegram(
        "eBay Auction Sniper started!\n\n"
        "Snipe time: " + str(SNIPE_SECONDS) + " seconds before auction ends\n\n"
        "To add an auction to snipe:\nsnipe ITEM_ID MAX_BID DESCRIPTION\n\n"
        "Example:\nsnipe 123456789012 50.00 Luka Doncic PSA 10"
    )

    offset = None
    while True:
        updates = get_updates(offset)
        for update in updates:
            offset = update["update_id"] + 1
            if "message" in update and "text" in update["message"]:
                handle_message(update["message"]["text"])

        monitor_auctions()
        time.sleep(5)
