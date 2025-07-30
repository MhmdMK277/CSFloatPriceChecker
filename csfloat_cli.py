import os
import json
import difflib
import threading
import time
from datetime import datetime
import requests

CONFIG_FILE = 'csfloat_config.json'
ITEM_DB_FILE = 'cs2_items.json'

def load_item_names(path: str = ITEM_DB_FILE):
    """Load item names from the CS2 items database."""
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as fh:
            data = json.load(fh)
            return list(data.keys())
    return []

ITEM_NAMES = load_item_names()


def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as fh:
            return json.load(fh)
    return {}


def save_config(cfg: dict) -> None:
    with open(CONFIG_FILE, 'w') as fh:
        json.dump(cfg, fh)


def get_api_key(cfg: dict) -> str:
    key = cfg.get('api_key')
    if not key:
        key = input('Enter your CSFloat API key: ').strip()
        if key:
            cfg['api_key'] = key
            save_config(cfg)
        else:
            print('API key is required to query the API.')
    return key


ITEM_TYPES = {
    '1': 'Skin',
    '2': 'Glove',
    '3': 'Case',
    '4': 'Sticker',
    '5': 'Key',
    '6': 'Other'
}

WEAR_LIST = ['FN', 'MW', 'FT', 'WW', 'BS']
CATEGORY_CHOICES = {
    '1': 1,
    '2': 2,
    '3': 3
}


def fuzzy_search_name(query: str, names: list, limit: int = 5) -> list:
    """Return a list of close matches for the query."""
    q_tokens = query.lower().split()
    results = [n for n in names if all(tok in n.lower() for tok in q_tokens)]
    if not results:
        results = difflib.get_close_matches(query, names, n=limit)
    return results[:limit]


def prompt_item_name() -> str | None:
    """Prompt user for item name and resolve via fuzzy search."""
    if not ITEM_NAMES:
        name = input('Enter item name: ').strip()
        return name or None
    while True:
        query = input('Enter item name: ').strip()
        if not query:
            return None
        matches = fuzzy_search_name(query, ITEM_NAMES)
        if not matches:
            print('No items found. Try again.')
            continue
        print('Did you mean?:')
        for idx, m in enumerate(matches, 1):
            print(f'{idx}) {m}')
        print('0) Cancel')
        choice = input('> ').strip()
        if choice == '0':
            return None
        if choice.isdigit() and 1 <= int(choice) <= len(matches):
            return matches[int(choice) - 1]
        print('Invalid selection.')


def prompt_item_type():
    print('Select item type:')
    for k, v in ITEM_TYPES.items():
        print(f'{k}. {v}')
    print('0. Cancel')
    choice = input('> ').strip()
    return choice


def prompt_wear():
    print('Select wear (optional):')
    for idx, w in enumerate(WEAR_LIST, start=1):
        print(f'{idx}. {w}')
    print('0. Skip')
    choice = input('> ').strip()
    if choice and choice.isdigit() and 1 <= int(choice) <= len(WEAR_LIST):
        return WEAR_LIST[int(choice) - 1]
    return None


def prompt_float_range():
    print('Enter minimum float (or leave blank):')
    min_f = input('> ').strip()
    print('Enter maximum float (or leave blank):')
    max_f = input('> ').strip()
    try:
        min_val = float(min_f) if min_f else None
    except ValueError:
        min_val = None
    try:
        max_val = float(max_f) if max_f else None
    except ValueError:
        max_val = None
    return min_val, max_val


def prompt_category():
    print('Select category:')
    print('1. Normal')
    print('2. StatTrak')
    print('3. Souvenir')
    print('0. Any')
    choice = input('> ').strip()
    return CATEGORY_CHOICES.get(choice)


def prompt_sort_by() -> str | None:
    print('Enter sort order (most_recent, lowest_price, lowest_float):')
    sort_by = input('> ').strip()
    return sort_by or None


def search_options(params: dict) -> bool:
    """Allow user to adjust parameters before searching."""
    while True:
        print('Options:')
        print('1. Begin search')
        print('2. Specify float range')
        print('3. Specify wear')
        print('4. Specify category')
        print('5. Specify sort order')
        print('0. Cancel')
        choice = input('> ').strip()
        if choice == '1':
            return True
        elif choice == '2':
            mn, mx = prompt_float_range()
            if mn is not None:
                params['min_float'] = mn
            if mx is not None:
                params['max_float'] = mx
        elif choice == '3':
            w = prompt_wear()
            if w:
                params['wear'] = w
            elif 'wear' in params:
                params.pop('wear')
        elif choice == '4':
            c = prompt_category()
            if c:
                params['category'] = c
            elif 'category' in params:
                params.pop('category')
        elif choice == '5':
            s = prompt_sort_by()
            if s:
                params['sort_by'] = s
        elif choice == '0':
            return False
        else:
            print('Invalid option')


def query_listings(key: str, params: dict):
    """Query CSFloat listings endpoint with provided parameters."""
    url = 'https://csfloat.com/api/v1/listings'
    params = params.copy()
    headers = {'Authorization': key}
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        print(f'Failed to query API: {exc}')
        return None


def track_price(key: str, params: dict, hours: int, name: str):
    """Track price in the background for the given hours."""
    fname = f"track_{name.replace(' ', '_').replace('|', '_')}.csv"

    def _run():
        end = time.time() + hours * 3600
        while time.time() < end:
            data = query_listings(key, params)
            if data:
                listings = data.get('listings') if isinstance(data, dict) else data
                if listings:
                    price = listings[0].get('price')
                    ts = datetime.now().isoformat()
                    with open(fname, 'a', encoding='utf-8') as fh:
                        fh.write(f'{ts},{price}\n')
            time.sleep(3600)

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    print(f'Tracking price in {fname} for {hours} hours...')



def display_results(data):
    """Display a few results from the listings response."""
    if isinstance(data, list):
        listings = data
    elif isinstance(data, dict):
        listings = data.get('listings')
    else:
        listings = None

    if not listings:
        print('No listings found')
        return

    for item in listings[:5]:
        name = item.get('item', {}).get('market_hash_name')
        price = item.get('price')
        wear_name = item.get('item', {}).get('wear_name')
        float_val = item.get('float', {}).get('float_value')
        print(f'{name} | {wear_name} | float={float_val} | price={price}')




def main():
    cfg = load_config()
    while True:
        print('\nMenu:')
        print('1. Search listings')
        print('2. Replace API key')
        print('3. Delete API key')
        print('0. Exit')
        action = input('> ').strip()
        if action == '1':
            key = get_api_key(cfg)
            if not key:
                continue
            params = {}
            while True:
                choice = prompt_item_type()
                if choice == '0':
                    break
                item_type = ITEM_TYPES.get(choice)
                if not item_type:
                    print('Invalid choice')
                    continue
                if item_type in {'Skin', 'Glove'}:
                    wear = prompt_wear()
                    if wear:
                        params['wear'] = wear
                name = prompt_item_name()
                if name:
                    params['market_hash_name'] = name
                if not search_options(params):
                    params = {}
                break
            if params:
                data = query_listings(key, params)
                if data:
                    display_results(data)
                    hrs = input('Track price for how many hours (0 to skip)? ').strip()
                    if hrs.isdigit() and int(hrs) > 0:
                        track_price(key, params, int(hrs), params['market_hash_name'])
        elif action == '2':
            new_key = input('Enter new API key: ').strip()
            if new_key:
                cfg['api_key'] = new_key
                save_config(cfg)
                print('API key updated.')
        elif action == '3':
            if 'api_key' in cfg:
                del cfg['api_key']
                save_config(cfg)
                print('API key deleted.')
            else:
                print('No API key stored.')
        elif action == '0':
            break
        else:
            print('Invalid option')


if __name__ == '__main__':
    main()
