import requests


def main():
    key = input("Enter your CSFloat API key: ").strip()
    if not key:
        print("API key is required.")
        return

    item_name = input("Enter the item name to check price for: ").strip()
    if not item_name:
        print("Item name is required.")
        return

    url = "https://csfloat.com/api/v1/listings"
    params = {
        "market_hash_name": item_name,
        "limit": 1,
        "sort_by": "lowest_price",
    }
    headers = {"Authorization": key}

    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        if isinstance(data, list) and data:
            price = data[0].get("price")
        elif isinstance(data, dict) and data.get("listings"):
            price = data["listings"][0].get("price")
        else:
            price = None

        if price is None:
            print(f"No price information found for '{item_name}'.")
        else:
            print(f"Lowest price for '{item_name}' is {price} cents.")
    except requests.RequestException as exc:
        print(f"Failed to fetch price: {exc}")


if __name__ == "__main__":
    main()
