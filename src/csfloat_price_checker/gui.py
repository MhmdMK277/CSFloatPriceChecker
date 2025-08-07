import os
import json
import difflib
import threading
import time
from datetime import datetime
import logging
import queue
from typing import Callable
import tkinter as tk
from tkinter import messagebox
import webbrowser
import ttkbootstrap as ttk
from ttkbootstrap.toast import ToastNotification
from ttkbootstrap.icons import Icon
import requests

from .notification import show_desktop_notification


def fade_in(window: tk.Tk | tk.Toplevel, delay: int = 10, step: float = 0.05) -> None:
    """Fade a window in by gradually increasing its opacity."""
    try:
        alpha = window.attributes('-alpha')
    except tk.TclError:
        alpha = 1.0
    if alpha is None:
        alpha = 0.0
    if alpha < 1.0:
        alpha = min(alpha + step, 1.0)
        window.attributes('-alpha', alpha)
        window.after(delay, lambda: fade_in(window, delay, step))

LOG_FILE = os.path.join(os.path.dirname(__file__), 'csfloat.log')
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s %(levelname)s:%(message)s'
)
logger = logging.getLogger(__name__)

# Track API request timestamps for rate information
REQUEST_TIMES: list[float] = []

def record_request() -> None:
    """Record a request timestamp and prune entries older than a minute."""
    now = time.time()
    REQUEST_TIMES.append(now)
    while REQUEST_TIMES and now - REQUEST_TIMES[0] > 60:
        REQUEST_TIMES.pop(0)

CONFIG_FILE = 'csfloat_config.json'
ITEM_DB_FILE = 'cs2_items.json'
HISTORY_FILE = 'search_history.json'
TRACK_FILE = 'tracked_items.json'


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


def load_history() -> list:
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as fh:
                return json.load(fh)
        except Exception:
            return []
    return []


def save_history(data: list) -> None:
    with open(HISTORY_FILE, 'w', encoding='utf-8') as fh:
        json.dump(data, fh)


def load_tracked() -> dict:
    if os.path.exists(TRACK_FILE):
        try:
            with open(TRACK_FILE, 'r', encoding='utf-8') as fh:
                return json.load(fh)
        except Exception:
            return {}
    return {}


def save_tracked(data: dict) -> None:
    with open(TRACK_FILE, 'w', encoding='utf-8') as fh:
        json.dump(data, fh)


def get_api_key(cfg: dict, root: ttk.Window) -> str:
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
            ToastNotification(title='Error', message='API key is required.', duration=3000, bootstyle='danger').show_toast()

    win = ttk.Toplevel(root)
    win.title('Enter API Key')
    try:
        win.attributes('-alpha', 0.0)
        fade_in(win)
    except tk.TclError:
        pass
    ttk.Label(win, text='CSFloat API Key:').pack(padx=10, pady=5)
    entry = ttk.Entry(win, width=40)
    entry.pack(padx=10, pady=5)
    ttk.Button(win, text='Save', command=save, bootstyle='success').pack(pady=10)
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
SORT_OPTIONS = ['most_recent', 'lowest_price', 'lowest_float']


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
        record_request()
        logger.info('Response status: %s', resp.status_code)
        if resp.status_code == 429:
            ToastNotification(title='Rate Limit', message='API rate limit reached', duration=3000, bootstyle='warning').show_toast()
            return None
        resp.raise_for_status()
        logger.info('Response body: %s', resp.text[:200])
        return resp.json()
    except Exception as exc:
        logger.exception('Failed to query API: %s', exc)
        ToastNotification(title='Error', message=f'Failed to query API: {exc}', duration=3000, bootstyle='danger').show_toast()
        return None


def track_price(
    key: str,
    params: dict,
    name: str,
    show_ui: bool = True,
    stop_event: threading.Event | None = None,
    on_stop: Callable[[], None] | None = None,
) -> threading.Event:
    fname = f"track_{name.replace(' ', '_').replace('|', '_')}.csv"

    logger.info(
        'Starting minute-based price tracking for "%s"; params=%s; output=%s',
        name,
        params,
        fname,
    )

    if stop_event is None:
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
        root = ttk.Toplevel()
        root.title(f'Tracking {name}')
        try:
            root.attributes('-alpha', 0.0)
            fade_in(root)
        except tk.TclError:
            pass
        status_lbl = ttk.Label(root, text='Running', anchor='w')
        status_lbl.pack(fill='x', padx=10, pady=(10, 0))

        pb = ttk.Progressbar(root, mode='indeterminate', bootstyle='info-striped')
        pb.pack(fill='x', padx=10, pady=10)

        log_box = ttk.ScrolledText(root, height=10, width=40)
        log_box.pack(fill='both', padx=10, pady=10)

        def stop() -> None:
            stop_event.set()
            status_lbl.configure(text='Stopped')

        ttk.Button(root, text='Stop', command=stop, bootstyle='danger').pack(pady=(0, 10))
        root.protocol('WM_DELETE_WINDOW', stop)

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
    if show_ui:
        threading.Thread(target=_ui, daemon=True).start()
        ToastNotification(title='Tracking', message=f'Tracking price in {fname}. Close window to stop.', duration=3000, bootstyle='info').show_toast()

    return stop_event


class PriceCheckerGUI:
    def __init__(self, root: ttk.Window) -> None:
        self.root = root
        self.cfg = load_config()
        self.last_filters: dict = self.cfg.get('last_filters', {})
        self.api_key = get_api_key(self.cfg, root)
        self.history = load_history()
        self.tracked = load_tracked()
        self.active_tracks: dict[str, threading.Event] = {}
        self.style = ttk.Style()
        self.status_var = tk.StringVar()
        self.build_main()
        self.last_refresh_time: str | None = None
        self.update_status()
        try:
            self.root.attributes('-alpha', 0.0)
            fade_in(self.root)
        except tk.TclError:
            pass
        self.show_search()

    def clear_content(self) -> None:
        for child in self.content.winfo_children():
            child.destroy()

    def toast(self, message: str, style: str = 'info') -> None:
        ToastNotification(title='CSFloat', message=message, duration=3000, bootstyle=style).show_toast()

    def update_status(self) -> None:
        """Update the status bar with current request rate and last refresh."""
        rate = len([t for t in REQUEST_TIMES if time.time() - t <= 60])
        last = self.last_refresh_time or 'N/A'
        self.status_var.set(f'Requests/min: {rate} | Last refresh: {last}')

    def build_main(self) -> None:
        self.root.title('CSFloat Price Checker')
        self.root.geometry('900x600')
        self.style.configure('TButton', font=('Helvetica', 11))
        self.style.configure('TLabel', font=('Helvetica', 11))

        self.sidebar = ttk.Frame(self.root, padding=10)
        self.sidebar.pack(side='left', fill='y')

        self.content = ttk.Frame(self.root, padding=10)
        self.content.pack(side='left', fill='both', expand=True)

        self.status = ttk.Label(self.root, textvariable=self.status_var, anchor='w')
        self.status.pack(side='bottom', fill='x')

        # icons
        self.info_img = tk.PhotoImage(data=Icon.info)

        ttk.Button(self.sidebar, text='Search Listings', image=self.info_img, compound='left', command=self.show_search, bootstyle='primary').pack(pady=5, fill='x')
        ttk.Button(self.sidebar, text='Tracked Alerts', command=self.show_tracked, bootstyle='info').pack(pady=5, fill='x')
        ttk.Button(self.sidebar, text='Replace API Key', command=self.replace_key, bootstyle='warning').pack(pady=5, fill='x')
        ttk.Button(self.sidebar, text='Delete API Key', command=self.delete_key, bootstyle='danger').pack(pady=5, fill='x')

    def replace_key(self) -> None:
        new_key = tk.simpledialog.askstring('API Key', 'Enter new API key:', parent=self.root)
        if new_key:
            self.cfg['api_key'] = new_key.strip()
            save_config(self.cfg)
            self.api_key = new_key.strip()
            self.toast('API key updated', 'success')

    def delete_key(self) -> None:
        if 'api_key' in self.cfg:
            del self.cfg['api_key']
            save_config(self.cfg)
            self.api_key = ''
            self.toast('API key deleted', 'success')
        else:
            self.toast('No API key stored', 'warning')

    def show_search(self) -> None:
        if not self.api_key:
            self.api_key = get_api_key(self.cfg, self.root)
            if not self.api_key:
                return

        self.clear_content()
        frame = self.content

        params = {}

        ttk.Label(frame, text='Item Type:').grid(row=0, column=0, sticky='e')
        item_type_var = tk.StringVar(value=self.last_filters.get('item_type', 'Skin'))
        ttk.Combobox(frame, textvariable=item_type_var, values=list(ITEM_TYPES)).grid(row=0, column=1, sticky='w')

        ttk.Label(frame, text='Item Name:').grid(row=1, column=0, sticky='e')
        name_var = tk.StringVar(value=self.last_filters.get('name', ''))
        name_entry = ttk.Entry(frame, textvariable=name_var, width=40)
        name_entry.grid(row=1, column=1, sticky='w')

        suggest_box = tk.Listbox(frame, height=5, width=40)
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

        ttk.Label(frame, text='Wear:').grid(row=3, column=0, sticky='e')
        wear_var = tk.StringVar(value=self.last_filters.get('wear', ''))
        ttk.Combobox(frame, textvariable=wear_var, values=WEAR_LIST).grid(row=3, column=1, sticky='w')

        ttk.Label(frame, text='Min Float:').grid(row=4, column=0, sticky='e')
        min_float_var = tk.StringVar(value=str(self.last_filters.get('min_float', '')))
        ttk.Entry(frame, textvariable=min_float_var, width=10).grid(row=4, column=1, sticky='w')

        ttk.Label(frame, text='Max Float:').grid(row=5, column=0, sticky='e')
        max_float_var = tk.StringVar(value=str(self.last_filters.get('max_float', '')))
        ttk.Entry(frame, textvariable=max_float_var, width=10).grid(row=5, column=1, sticky='w')

        ttk.Label(frame, text='Category:').grid(row=6, column=0, sticky='e')
        category_var = tk.StringVar(value=self.last_filters.get('category', 'Any'))
        ttk.Combobox(frame, textvariable=category_var, values=list(CATEGORY_CHOICES)).grid(row=6, column=1, sticky='w')

        ttk.Label(frame, text='Sort By:').grid(row=7, column=0, sticky='e')
        sort_var = tk.StringVar(value=self.last_filters.get('sort_by', 'most_recent'))
        ttk.Combobox(frame, textvariable=sort_var, values=SORT_OPTIONS).grid(row=7, column=1, sticky='w')

        include_auctions_var = tk.BooleanVar(value=self.last_filters.get('include_auctions', True))
        ttk.Checkbutton(frame, text='Include Auctions', variable=include_auctions_var).grid(row=8, column=1, sticky='w')

        def search():
            params.clear()
            params['type'] = 'buy_now' if not include_auctions_var.get() else None
            itype = ITEM_TYPES.get(item_type_var.get())
            if itype:
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
            self.add_history(params.copy())
            self.last_filters = {
                'item_type': item_type_var.get(),
                'name': name_var.get(),
                'wear': wear_var.get(),
                'min_float': min_float_var.get(),
                'max_float': max_float_var.get(),
                'category': category_var.get(),
                'sort_by': sort_var.get(),
                'include_auctions': include_auctions_var.get(),
            }
            self.cfg['last_filters'] = self.last_filters
            save_config(self.cfg)
            self.perform_search(params)

        ttk.Button(frame, text='Search', command=search, bootstyle='primary').grid(row=9, column=1, pady=10, sticky='e')

        if self.history:
            ttk.Label(frame, text='Recent Searches:').grid(row=10, column=0, sticky='ne')
            hist_frame = ttk.Frame(frame)
            hist_frame.grid(row=10, column=1, sticky='w')
            for entry in self.history:
                summary = self.format_history_entry(entry)
                params_copy = entry['params'].copy()
                ttk.Button(hist_frame, text=summary, command=lambda p=params_copy: self.perform_search(p), bootstyle='secondary').pack(fill='x', pady=2)

    def perform_search(self, params: dict) -> None:
        if not params:
            return

        self.clear_content()
        loading = ttk.Label(self.content, text='Searching...')
        loading.pack(pady=10)
        pb = ttk.Progressbar(self.content, mode='indeterminate', bootstyle='info-striped')
        pb.pack(fill='x', padx=10)
        pb.start()

        def worker() -> None:
            data = query_listings(self.api_key, params)
            if data is not None:
                self.last_refresh_time = datetime.now().strftime('%H:%M:%S')
            self.root.after(0, lambda: display_results(data))
            self.root.after(0, self.update_status)

        def display_results(data):
            pb.stop()
            loading.destroy()
            pb.destroy()
            if not data:
                self.toast('Query failed', 'danger')
                return
            listings = data.get('data') if isinstance(data, dict) else data
            if not listings:
                self.toast('No listings found', 'warning')
                return
            self.show_results(listings, params)

        threading.Thread(target=worker, daemon=True).start()

    def show_results(self, listings: list, params: dict) -> None:
        self.clear_content()

        columns = ['Name', 'Wear', 'Float', 'Price', 'Type', 'Time left', 'Track']
        tree = ttk.Treeview(self.content, columns=columns, show='headings', bootstyle='success')
        for col in columns:
            tree.heading(col, text=col, command=lambda c=col: self._sort(tree, c, False))
            anchor = 'w' if col in {'Name', 'Wear', 'Type', 'Time left', 'Track'} else 'e'
            tree.column(col, anchor=anchor, width=120)
        tree.column('Name', width=250)
        tree.column('Track', width=80)

        id_map: dict[str, str] = {}
        listing_map: dict[str, dict] = {}

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
            iid = tree.insert('', 'end', values=(name, wear_name, float_val, price, auction_info, time_left or '', 'Track'))
            if item.get('id'):
                id_map[iid] = item['id']
            listing_map[iid] = item

            settings = self.tracked.get(name)
            if settings and isinstance(price_cents, (int, float)) and isinstance(float_val, (int, float)):
                price_val = price_cents / 100
                if price_val <= settings.get('threshold', float('inf')) and settings.get('float_min', 0) <= float_val <= settings.get('float_max', 1):
                    tree.item(iid, tags=('match',))
                    tree.tag_configure('match', background='yellow')
                    last = settings.get('last_notified_price')
                    should_notify = True
                    if settings.get('notify_once', True) and last is not None and price_val >= last:
                        should_notify = False
                    if should_notify and price_val != last:
                        show_desktop_notification(name, {'price': price_val, 'float': float_val})
                        settings['last_notified_price'] = price_val
                        save_tracked(self.tracked)

        tree.pack(fill='both', expand=True)

        def open_listing(event=None) -> None:
            sel = tree.selection()
            if not sel:
                self.toast('No listing selected', 'warning')
                return
            iid = sel[0]
            listing_id = id_map.get(iid)
            if not listing_id:
                self.toast('Unable to determine listing ID', 'danger')
                return
            webbrowser.open_new_tab(f'https://csfloat.com/item/{listing_id}')

        def copy_url() -> None:
            sel = tree.selection()
            if not sel:
                self.toast('No listing selected', 'warning')
                return
            iid = sel[0]
            listing_id = id_map.get(iid)
            if not listing_id:
                self.toast('Unable to determine listing ID', 'danger')
                return
            url = f'https://csfloat.com/item/{listing_id}'
            self.root.clipboard_clear()
            self.root.clipboard_append(url)
            self.toast('URL copied', 'success')

        btn_frame = ttk.Frame(self.content)
        btn_frame.pack(pady=10, anchor='e', fill='x')
        ttk.Button(btn_frame, text='Open Listing', command=open_listing, bootstyle='secondary').pack(side='left')
        ttk.Button(btn_frame, text='Copy URL', command=copy_url, bootstyle='secondary').pack(side='left', padx=5)

        def on_tree_click(event) -> None:
            col = tree.identify_column(event.x)
            iid = tree.identify_row(event.y)
            if col == f"#{len(columns)}" and iid:
                item = listing_map.get(iid)
                name = item.get('item', {}).get('market_hash_name') if item else None
                if name and item:
                    self.open_track_modal(name, item)

        tree.bind('<Double-1>', open_listing)
        tree.bind('<Button-1>', on_tree_click)
    def _sort(self, tree: ttk.Treeview, col: str, reverse: bool) -> None:
        data = [(tree.set(k, col), k) for k in tree.get_children('')]
        try:
            data.sort(key=lambda t: float(t[0].strip('$')) if t[0] else 0.0, reverse=reverse)
        except ValueError:
            data.sort(reverse=reverse)
        for idx, (_, k) in enumerate(data):
            tree.move(k, '', idx)
        tree.heading(col, command=lambda: self._sort(tree, col, not reverse))

    
    def open_track_modal(self, name: str, listing: dict | None = None) -> None:
        data = self.tracked.get(name, {})
        win = ttk.Toplevel(self.root)
        win.title(f'Track alert for: {name}')
        try:
            win.attributes('-alpha', 0.0)
            fade_in(win)
        except tk.TclError:
            pass
        notify_var = tk.BooleanVar(value=data.get('notify_once', True))
        thresh_var = tk.StringVar(value=str(data.get('threshold', '')))
        fmin_var = tk.StringVar(value=str(data.get('float_min', '')))
        fmax_var = tk.StringVar(value=str(data.get('float_max', '')))

        ttk.Checkbutton(win, text='Notify once only', variable=notify_var).pack(padx=10, pady=(10, 0), anchor='w')
        frm = ttk.Frame(win)
        frm.pack(padx=10, pady=5, fill='x')
        ttk.Label(frm, text='Max Price:').grid(row=0, column=0, sticky='e')
        ttk.Entry(frm, textvariable=thresh_var, width=10).grid(row=0, column=1, sticky='w')
        ttk.Label(frm, text='Float Range:').grid(row=1, column=0, sticky='e')
        ttk.Entry(frm, textvariable=fmin_var, width=10).grid(row=1, column=1, sticky='w')
        ttk.Entry(frm, textvariable=fmax_var, width=10).grid(row=1, column=2, sticky='w', padx=(5, 0))

        def save() -> None:
            try:
                threshold = float(thresh_var.get())
                fmin = float(fmin_var.get())
                fmax = float(fmax_var.get())
            except ValueError:
                self.toast('Invalid number entered', 'danger')
                return
            inspect = data.get('inspect_link')
            if listing:
                inspect = listing.get('inspect_url') or listing.get('inspect_link') or inspect
            self.tracked[name] = {
                'inspect_link': inspect,
                'threshold': threshold,
                'float_min': fmin,
                'float_max': fmax,
                'notify_once': notify_var.get(),
                'last_notified_price': data.get('last_notified_price'),
            }
            save_tracked(self.tracked)
            win.destroy()
            self.toast('Alert saved', 'success')

        ttk.Button(win, text='Save Alert', command=save, bootstyle='success').pack(pady=(5, 10))
        win.grab_set()
        self.root.wait_window(win)

    def delete_alert(self, name: str) -> None:
        if name in self.tracked:
            del self.tracked[name]
            save_tracked(self.tracked)
            self.show_tracked()
            self.toast('Alert deleted', 'info')

# --- History Helpers ---
    def add_history(self, params: dict) -> None:
        if 'market_hash_name' not in params:
            return
        entry = {'name': params['market_hash_name'], 'params': params.copy()}
        entry['params'] = {k: v for k, v in entry['params'].items() if v is not None}
        for ex in list(self.history):
            if ex['name'] == entry['name'] and ex['params'] == entry['params']:
                self.history.remove(ex)
                break
        self.history.insert(0, entry)
        self.history = self.history[:5]
        save_history(self.history)

    def format_history_entry(self, entry: dict) -> str:
        p = entry.get('params', {})
        parts = []
        if p.get('wear'):
            parts.append(f"Wear {p['wear']}")
        if 'min_float' in p or 'max_float' in p:
            parts.append(f"{p.get('min_float', '')}-{p.get('max_float', '')}")
        if 'category' in p:
            cat = next((k for k, v in CATEGORY_CHOICES.items() if v == p['category']), p['category'])
            parts.append(f"Category {cat}")
        if p.get('sort_by'):
            parts.append(f"Sort {p['sort_by']}")
        parts.append('No Auction' if p.get('type') == 'buy_now' else 'Auctions')
        desc = ' | '.join(parts)
        return f"{entry['name']} ({desc})"

    # --- Tracking management ---
    def start_tracking(self, name: str, params: dict, show_window: bool = True) -> None:
        if name in self.active_tracks:
            self.toast('Already tracking this item', 'warning')
            return
        def _on_stop() -> None:
            self.active_tracks.pop(name, None)
            if name in self.tracked:
                self.tracked[name]['active'] = False
                save_tracked(self.tracked)

        stop_event = track_price(self.api_key, params, name, show_window, on_stop=_on_stop)
        self.active_tracks[name] = stop_event
        self.tracked[name] = {'params': params.copy(), 'active': True}
        save_tracked(self.tracked)

    def toggle_tracking(self, name: str) -> None:
        data = self.tracked.get(name)
        if not data:
            return
        if data.get('active'):
            ev = self.active_tracks.pop(name, None)
            if ev:
                ev.set()
            data['active'] = False
            self.toast(f'Tracking paused for {name}', 'info')
        else:
            def _on_stop() -> None:
                self.active_tracks.pop(name, None)
                if name in self.tracked:
                    self.tracked[name]['active'] = False
                    save_tracked(self.tracked)

            stop_event = track_price(self.api_key, data['params'], name, show_ui=False, on_stop=_on_stop)
            self.active_tracks[name] = stop_event
            data['active'] = True
            self.toast(f'Tracking resumed for {name}', 'success')
        save_tracked(self.tracked)

    def open_csv(self, name: str) -> None:
        fname = f"track_{name.replace(' ', '_').replace('|', '_')}.csv"
        win = ttk.Toplevel(self.root)
        win.title(f'Tracked data: {name}')
        try:
            win.attributes('-alpha', 0.0)
            fade_in(win)
        except tk.TclError:
            pass
        text = ttk.ScrolledText(win, width=60, height=20)
        text.pack(fill='both', expand=True, padx=10, pady=10)
        try:
            with open(fname, 'r', encoding='utf-8') as fh:
                text.insert('end', fh.read())
        except FileNotFoundError:
            text.insert('end', 'No data')
        btn_frame = ttk.Frame(win)
        btn_frame.pack(pady=5)
        btn_txt = tk.StringVar(value='Pause' if self.tracked.get(name, {}).get('active') else 'Resume')

        def toggle() -> None:
            self.toggle_tracking(name)
            btn_txt.set('Pause' if self.tracked.get(name, {}).get('active') else 'Resume')

        ttk.Button(btn_frame, textvariable=btn_txt, command=toggle).pack(side='left', padx=5)
        ttk.Button(btn_frame, text='Close', command=win.destroy).pack(side='right')

    def show_tracked(self) -> None:
        self.clear_content()
        if not self.tracked:
            ttk.Label(self.content, text='No tracked alerts').pack(pady=10)
            return
        columns = ['Skin', 'Threshold', 'Float Range', 'Notify Once']
        tree = ttk.Treeview(self.content, columns=columns, show='headings', bootstyle='info')
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=150, anchor='w')
        tree.pack(fill='both', expand=True)
        for name, data in self.tracked.items():
            thr = f"${data.get('threshold',0):.2f}"
            frange = f"{data.get('float_min',0)}-{data.get('float_max',1)}"
            once = 'Yes' if data.get('notify_once') else 'No'
            tree.insert('', 'end', values=(name, thr, frange, once))

        btn_frame = ttk.Frame(self.content)
        btn_frame.pack(pady=10, anchor='e')

        def edit() -> None:
            sel = tree.selection()
            if not sel:
                self.toast('No alert selected', 'warning')
                return
            name = tree.item(sel[0])['values'][0]
            self.open_track_modal(name)

        def delete() -> None:
            sel = tree.selection()
            if not sel:
                self.toast('No alert selected', 'warning')
                return
            name = tree.item(sel[0])['values'][0]
            self.delete_alert(name)

        ttk.Button(btn_frame, text='Edit', command=edit, bootstyle='secondary').pack(side='left')
        ttk.Button(btn_frame, text='Delete', command=delete, bootstyle='danger').pack(side='left', padx=5)

def main() -> None:
    root = ttk.Window(themename='morph')
    app = PriceCheckerGUI(root)
    root.mainloop()


if __name__ == '__main__':
    main()
