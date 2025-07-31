import os
import json
import difflib
import threading
import time
from datetime import datetime
import logging
import queue
import tkinter as tk
from tkinter import ttk, messagebox
import requests

LOG_FILE = os.path.join(os.path.dirname(__file__), 'csfloat.log')
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s %(levelname)s:%(message)s'
)
logger = logging.getLogger(__name__)

CONFIG_FILE = 'csfloat_config.json'
ITEM_DB_FILE = 'cs2_items.json'


def load_item_names(path: str = ITEM_DB_FILE):
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as fh:
            data = json.load(fh)
            return list(data.keys())
    return []

ITEM_NAMES = sorted(load_item_names())


def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as fh:
            return json.load(fh)
    return {}


def save_config(cfg: dict) -> None:
    with open(CONFIG_FILE, 'w') as fh:
        json.dump(cfg, fh)


def get_api_key(cfg: dict, root: tk.Tk) -> str:
    key = cfg.get('api_key')
    if key:
        return key

    def save():
        val = entry.get().strip()
        if val:
            cfg['api_key'] = val
            save_config(cfg)
            nonlocal key
            key = val
            win.destroy()
        else:
            messagebox.showerror('Error', 'API key is required.')

    win = tk.Toplevel(root)
    win.title('Enter API Key')
    tk.Label(win, text='CSFloat API Key:').pack(padx=10, pady=5)
    entry = tk.Entry(win, width=40)
    entry.pack(padx=10, pady=5)
    tk.Button(win, text='Save', command=save).pack(pady=10)
    win.grab_set()
    root.wait_window(win)
    return key or ''


ITEM_TYPES = {
    'Skin': 'Skin',
    'Glove': 'Glove',
    'Case': 'Case',
    'Sticker': 'Sticker',
    'Key': 'Key',
    'Other': 'Other',
}

WEAR_LIST = ['FN', 'MW', 'FT', 'WW', 'BS']
CATEGORY_CHOICES = {
    'Any': None,
    'Normal': 1,
    'StatTrak': 2,
    'Souvenir': 3,
}


def fuzzy_search_name(query: str, names: list, limit: int = 10) -> list:
    q = query.lower()
    results = [n for n in names if q in n.lower()]
    if not results:
        results = difflib.get_close_matches(query, names, n=limit)
    results.sort()
    return results[:limit]


def query_listings(key: str, params: dict):
    url = 'https://csfloat.com/api/v1/listings'
    params = params.copy()
    params.setdefault('limit', 50)
    headers = {'Authorization': key}
    logger.info('Request params: %s', params)
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        logger.info('Response status: %s', resp.status_code)
        resp.raise_for_status()
        logger.info('Response body: %s', resp.text[:200])
        return resp.json()
    except Exception as exc:
        logger.exception('Failed to query API: %s', exc)
        messagebox.showerror('Error', f'Failed to query API: {exc}')
        return None


def track_price(key: str, params: dict, name: str) -> None:
    fname = f"track_{name.replace(' ', '_').replace('|', '_')}.csv"

    logger.info(
        'Starting minute-based price tracking for "%s"; params=%s; output=%s',
        name,
        params,
        fname,
    )

    stop_event = threading.Event()
    progress_queue: queue.Queue[str] = queue.Queue()

    def _run() -> None:
        while not stop_event.is_set():
            data = query_listings(key, params)
            if data:
                listings = data.get('data') if isinstance(data, dict) else data
                if listings:
                    price_cents = listings[0].get('price')
                    price = price_cents / 100 if isinstance(price_cents, (int, float)) else price_cents
                    ts = datetime.now().isoformat()
                    with open(fname, 'a', encoding='utf-8') as fh:
                        fh.write(f'{ts},{price}\n')
                    logger.info('Tracked price %s at %s', price, ts)
                    progress_queue.put(ts)
            for _ in range(60):
                if stop_event.is_set():
                    break
                time.sleep(1)

    def _ui() -> None:
        root = tk.Toplevel()
        root.title(f'Tracking {name}')

        pb = ttk.Progressbar(root, mode='indeterminate')
        pb.pack(fill='x', padx=10, pady=10)

        log_box = tk.Text(root, height=10, width=40)
        log_box.pack(fill='both', padx=10, pady=10)

        def stop() -> None:
            stop_event.set()

        tk.Button(root, text='Stop', command=stop).pack(pady=(0, 10))

        def update() -> None:
            while not progress_queue.empty():
                ts = progress_queue.get()
                log_box.insert('end', f'{ts}\n')
                log_box.see('end')
            if stop_event.is_set():
                pb.stop()
                root.destroy()
            else:
                pb.start(1000)
                root.after(1000, update)

        update()
        root.mainloop()

    threading.Thread(target=_run, daemon=True).start()
    threading.Thread(target=_ui, daemon=True).start()
    messagebox.showinfo('Tracking', f'Tracking price in {fname}. Close window to stop.')


class PriceCheckerGUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.cfg = load_config()
        self.api_key = get_api_key(self.cfg, root)
        self.build_main()

    def build_main(self) -> None:
        self.root.title('CSFloat Price Checker')
        ttk.Button(self.root, text='Search Listings', command=self.open_search).pack(pady=5, fill='x')
        ttk.Button(self.root, text='Replace API Key', command=self.replace_key).pack(pady=5, fill='x')
        ttk.Button(self.root, text='Delete API Key', command=self.delete_key).pack(pady=5, fill='x')

    def replace_key(self) -> None:
        new_key = tk.simpledialog.askstring('API Key', 'Enter new API key:', parent=self.root)
        if new_key:
            self.cfg['api_key'] = new_key.strip()
            save_config(self.cfg)
            self.api_key = new_key.strip()
            messagebox.showinfo('API Key', 'API key updated.')

    def delete_key(self) -> None:
        if 'api_key' in self.cfg:
            del self.cfg['api_key']
            save_config(self.cfg)
            self.api_key = ''
            messagebox.showinfo('API Key', 'API key deleted.')
        else:
            messagebox.showinfo('API Key', 'No API key stored.')

    def open_search(self) -> None:
        if not self.api_key:
            self.api_key = get_api_key(self.cfg, self.root)
            if not self.api_key:
                return
        win = tk.Toplevel(self.root)
        win.title('Search Listings')

        params = {}

        tk.Label(win, text='Item Type:').grid(row=0, column=0, sticky='e')
        item_type_var = tk.StringVar(value='Skin')
        ttk.Combobox(win, textvariable=item_type_var, values=list(ITEM_TYPES)).grid(row=0, column=1, sticky='w')

        tk.Label(win, text='Item Name:').grid(row=1, column=0, sticky='e')
        name_var = tk.StringVar()
        name_entry = ttk.Entry(win, textvariable=name_var, width=40)
        name_entry.grid(row=1, column=1, sticky='w')

        suggest_box = tk.Listbox(win, height=5, width=40)
        suggest_box.grid(row=2, column=1, sticky='w')
        suggest_box.grid_remove()

        def update_suggestions(event=None):
            query = name_var.get()
            matches = fuzzy_search_name(query, ITEM_NAMES)
            suggest_box.delete(0, 'end')
            for m in matches:
                suggest_box.insert('end', m)
            if matches:
                suggest_box.grid()
            else:
                suggest_box.grid_remove()

        def select_suggestion(event):
            if suggest_box.curselection():
                name_var.set(suggest_box.get(suggest_box.curselection()[0]))
                suggest_box.grid_remove()

        name_entry.bind('<KeyRelease>', update_suggestions)
        suggest_box.bind('<<ListboxSelect>>', select_suggestion)

        tk.Label(win, text='Wear:').grid(row=3, column=0, sticky='e')
        wear_var = tk.StringVar()
        ttk.Combobox(win, textvariable=wear_var, values=WEAR_LIST).grid(row=3, column=1, sticky='w')

        tk.Label(win, text='Min Float:').grid(row=4, column=0, sticky='e')
        min_float_var = tk.StringVar()
        ttk.Entry(win, textvariable=min_float_var, width=10).grid(row=4, column=1, sticky='w')

        tk.Label(win, text='Max Float:').grid(row=5, column=0, sticky='e')
        max_float_var = tk.StringVar()
        ttk.Entry(win, textvariable=max_float_var, width=10).grid(row=5, column=1, sticky='w')

        tk.Label(win, text='Category:').grid(row=6, column=0, sticky='e')
        category_var = tk.StringVar(value='Any')
        ttk.Combobox(win, textvariable=category_var, values=list(CATEGORY_CHOICES)).grid(row=6, column=1, sticky='w')

        tk.Label(win, text='Sort By:').grid(row=7, column=0, sticky='e')
        sort_var = tk.StringVar(value='most_recent')
        ttk.Entry(win, textvariable=sort_var, width=20).grid(row=7, column=1, sticky='w')

        include_auctions_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(win, text='Include Auctions', variable=include_auctions_var).grid(row=8, column=1, sticky='w')

        def search():
            params.clear()
            params['type'] = 'buy_now' if not include_auctions_var.get() else None
            itype = ITEM_TYPES.get(item_type_var.get())
            if itype:
                # wear only for skin or glove
                if itype in {'Skin', 'Glove'}:
                    w = wear_var.get().strip()
                    if w:
                        params['wear'] = w
            name = name_var.get().strip()
            if name:
                params['market_hash_name'] = name
            mn = min_float_var.get().strip()
            if mn:
                try:
                    params['min_float'] = float(mn)
                except ValueError:
                    pass
            mx = max_float_var.get().strip()
            if mx:
                try:
                    params['max_float'] = float(mx)
                except ValueError:
                    pass
            cat = CATEGORY_CHOICES.get(category_var.get())
            if cat:
                params['category'] = cat
            sort = sort_var.get().strip()
            if sort:
                params['sort_by'] = sort
            if not include_auctions_var.get() and 'type' in params:
                params['type'] = 'buy_now'
            elif include_auctions_var.get() and params.get('type'):
                params.pop('type')
            win.destroy()
            self.perform_search(params)

        ttk.Button(win, text='Search', command=search).grid(row=9, column=1, pady=10, sticky='e')

    def perform_search(self, params: dict) -> None:
        if not params:
            return
        data = query_listings(self.api_key, params)
        if not data:
            return
        listings = data.get('data') if isinstance(data, dict) else data
        if not listings:
            messagebox.showinfo('Results', 'No listings found.')
            return
        win = tk.Toplevel(self.root)
        win.title('Results')
        listbox = tk.Listbox(win, width=100, height=20)
        for item in listings:
            name = item.get('item', {}).get('market_hash_name')
            price_cents = item.get('price')
            price = f"${price_cents/100:.2f}" if isinstance(price_cents, (int, float)) else price_cents
            wear_name = item.get('item', {}).get('wear_name')
            float_val = item.get('float', {}).get('float_value')
            is_auction = (
                item.get('is_auction')
                or item.get('auction') is True
                or item.get('listing_type') == 'auction'
                or item.get('sale_type') == 'auction'
                or item.get('type') == 'auction'
            )
            time_left = (
                item.get('time_remaining')
                or item.get('auction_ends_in')
                or item.get('auction_ends_at')
                or item.get('expires_at')
            )
            auction_info = 'Auction' if is_auction else 'Buy now'
            if time_left:
                auction_info += f' (time left: {time_left})'
            listbox.insert('end', f"{name} | {wear_name} | float={float_val} | price={price} | {auction_info}")
        listbox.pack(fill='both', expand=True)

        def start_track():
            track_price(self.api_key, params, params['market_hash_name'])

        ttk.Button(win, text='Track Price', command=start_track).pack(pady=5)


def main() -> None:
    root = tk.Tk()
    app = PriceCheckerGUI(root)
    root.mainloop()


if __name__ == '__main__':
    main()
