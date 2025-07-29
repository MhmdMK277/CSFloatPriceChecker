import os
import json
import requests

CONFIG_FILE = 'csfloat_config.json'


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


def query_listings(key: str, params: dict):
    url = 'https://csfloat.com/api/v1/listings'
    headers = {'Authorization': key}
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return data
    except Exception as exc:
        print(f'Failed to query API: {exc}')
        return None


def display_results(data):
    if not isinstance(data, list):
        print('Unexpected response')
        return
    for item in data[:5]:
        name = item.get('item', {}).get('market_hash_name')
        price = item.get('price')
        wear_name = item.get('item', {}).get('wear_name')
        print(f"{name} - {wear_name or 'N/A'} - {price} cents")



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
                if item_type == 'Skin' or item_type == 'Glove':
                    wear = prompt_wear()
                    if wear:
                        params['wear'] = wear
                    min_f, max_f = prompt_float_range()
                    if min_f is not None:
                        params['min_float'] = min_f
                    if max_f is not None:
                        params['max_float'] = max_f
                    cat = prompt_category()
                    if cat:
                        params['category'] = cat
                name = input('Enter item name (or leave blank to skip): ').strip()
                if name:
                    params['market_hash_name'] = name
                break
            if params:
                data = query_listings(key, params)
                if data:
                    display_results(data)
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
