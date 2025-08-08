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
from ttkbootstrap.tooltip import ToolTip
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

# Default API rate limit (requests per minute); updated dynamically
API_RATE_LIMIT: int = 60


def update_rate_limit(headers: dict) -> None:
    """Update the global API rate limit from response headers."""
    global API_RATE_LIMIT
    try:
        limit = int(headers.get('X-RateLimit-Limit', API_RATE_LIMIT))
        if limit > 0:
            API_RATE_LIMIT = limit
    except (TypeError, ValueError):
        pass


def rate_limit_interval() -> float:
    """Return the recommended delay between requests based on the limit."""
    return 60.0 / API_RATE_LIMIT if API_RATE_LIMIT else 6.0


def record_request() -> None:
    """Record a request timestamp and prune entries older than a minute."""
    now = time.time()
    REQUEST_TIMES.append(now)
    while REQUEST_TIMES and now - REQUEST_TIMES[0] > 60:
        REQUEST_TIMES.pop(0)

CONFIG_FILE = 'csfloat_config.json'
ITEM_DB_FILE = 'cs2_items.json'
HISTORY_FILE = 'search_history.json'


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


SEARCH_INTERVAL = 300  # seconds between automatic search checks


def make_search_key(params: dict) -> str:
    """Create a display key for a search based on name and wear."""
    name = params.get('market_hash_name', 'Unknown')
    wear = params.get('wear')
    return f"{name} ({wear})" if wear else name

TRACKED_ITEMS_FILE = 'tracked_items.json'


def load_tracked_items() -> dict:
    """Load tracked item definitions from disk."""
    if os.path.exists(TRACKED_ITEMS_FILE):
        try:
            with open(TRACKED_ITEMS_FILE, 'r', encoding='utf-8') as fh:
                return json.load(fh)
        except Exception:
            return {}
    return {}


def save_tracked_items(data: dict) -> None:
    """Persist tracked item definitions to disk."""
    with open(TRACKED_ITEMS_FILE, 'w', encoding='utf-8') as fh:
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
        update_rate_limit(resp.headers)
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
    fname = os.path.join('tracked_logs', f"{name.replace(' ', '_').replace('|', '_')}.csv")
    os.makedirs(os.path.dirname(fname), exist_ok=True)

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
                    ts = datetime.now().isoformat()
                    with open(fname, 'a', encoding='utf-8') as fh:
                        for item in listings:
                            price_cents = item.get('price')
                            float_val = item.get('float', {}).get('float_value')
                            listing_id = item.get('id')
                            if isinstance(price_cents, (int, float)):
                                price = price_cents / 100
                                fh.write(f'{ts},{price},{float_val},{listing_id}\n')
                    logger.info('Tracked %s listings at %s', len(listings), ts)
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
        self.theme = self.cfg.get('theme', 'darkly')
        try:
            self.style = ttk.Style(theme=self.theme)
        except Exception:
            self.style = ttk.Style()
            self.style.theme_use(self.theme)
        self.last_filters: dict = self.cfg.get('last_filters', {})
        self.api_key = get_api_key(self.cfg, root)
        self.history = load_history()
        self.tracked_items = load_tracked_items()
        self.active_tracks: dict[str, threading.Event] = {}
        self.search_threads: dict[str, threading.Event] = {}
        self.bulk_items: list[dict] = []
        self.status_var = tk.StringVar()
        self.build_main()
        self.last_refresh_time: str | None = None
        for key, data in list(self.tracked_items.items()):
            if data.get('track_alerts'):
                self.start_search_checker(key)
            if data.get('track_prices'):
                self.start_tracking(key, data.get('params', {}), show_window=False)
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
        self.root.rowconfigure(0, weight=1)
        self.root.columnconfigure(1, weight=1)
        self.style.configure('TButton', font=('Helvetica', 11))
        self.style.configure('TLabel', font=('Helvetica', 11))

        self.sidebar = ttk.Frame(self.root, padding=10)
        self.sidebar.grid(row=0, column=0, sticky='ns')

        self.content = ttk.Frame(self.root, padding=10)
        self.content.grid(row=0, column=1, sticky='nsew')

        self.status = ttk.Label(self.root, textvariable=self.status_var, anchor='w')
        self.status.grid(row=1, column=0, columnspan=2, sticky='ew')

        # icons
        self.info_img = tk.PhotoImage(data=Icon.info)

        ttk.Button(
            self.sidebar,
            text='Search Listings',
            image=self.info_img,
            compound='left',
            command=self.show_search,
            bootstyle='primary',
        ).pack(pady=5, fill='x')
        ttk.Button(
            self.sidebar,
            text='Bulk Search',
            command=self.show_bulk_search,
            bootstyle='success',
        ).pack(pady=5, fill='x')
        ttk.Button(
            self.sidebar,
            text='Tracked Items',
            command=self.show_tracked_items,
            bootstyle='secondary',
        ).pack(pady=5, fill='x')
        ttk.Button(
            self.sidebar,
            text='Tracked Alerts',
            command=self.show_tracked_alerts,
            bootstyle='info',
        ).pack(pady=5, fill='x')
        ttk.Button(
            self.sidebar,
            text='Replace API Key',
            command=self.replace_key,
            bootstyle='warning',
        ).pack(pady=5, fill='x')
        ttk.Button(
            self.sidebar,
            text='Delete API Key',
            command=self.delete_key,
            bootstyle='danger',
        ).pack(pady=5, fill='x')

        ttk.Separator(self.sidebar).pack(fill='x', pady=5)
        ttk.Button(
            self.sidebar,
            text='Toggle Theme',
            command=self.toggle_theme,
            bootstyle='light',
        ).pack(pady=5, fill='x')

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

    def toggle_theme(self) -> None:
        new_theme = 'flatly' if self.theme == 'darkly' else 'darkly'
        self.style.theme_use(new_theme)
        self.theme = new_theme
        self.cfg['theme'] = new_theme
        save_config(self.cfg)

    def show_search(self) -> None:
        if not self.api_key:
            self.api_key = get_api_key(self.cfg, self.root)
            if not self.api_key:
                return

        self.clear_content()
        frame = self.content
        frame.columnconfigure(1, weight=1)

        params = {}

        ttk.Label(frame, text='Item Type:').grid(row=0, column=0, sticky='e', pady=2)
        item_type_var = tk.StringVar(value=self.last_filters.get('item_type', 'Skin'))
        item_type_cb = ttk.Combobox(frame, textvariable=item_type_var, values=list(ITEM_TYPES))
        item_type_cb.grid(row=0, column=1, sticky='ew', pady=2)
        ToolTip(item_type_cb, text='Choose the item category to search.')

        ttk.Label(frame, text='Item Name:').grid(row=1, column=0, sticky='e', pady=2)
        name_var = tk.StringVar(value=self.last_filters.get('name', ''))
        name_entry = ttk.Entry(frame, textvariable=name_var, width=40)
        name_entry.grid(row=1, column=1, sticky='ew', pady=2)
        ToolTip(name_entry, text='Enter the market name of the item.')

        suggest_box = tk.Listbox(frame, height=5, width=40)
        suggest_box.grid(row=2, column=1, sticky='ew')
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

        ttk.Label(frame, text='Wear:').grid(row=3, column=0, sticky='e', pady=2)
        wear_var = tk.StringVar(value=self.last_filters.get('wear', ''))
        wear_cb = ttk.Combobox(frame, textvariable=wear_var, values=WEAR_LIST)
        wear_cb.grid(row=3, column=1, sticky='ew', pady=2)
        ToolTip(wear_cb, text='Select a specific wear level.')

        ttk.Label(frame, text='Min Float:').grid(row=4, column=0, sticky='e', pady=2)
        min_float_var = tk.StringVar(value=str(self.last_filters.get('min_float', '')))
        min_entry = ttk.Entry(frame, textvariable=min_float_var, width=10)
        min_entry.grid(row=4, column=1, sticky='w', pady=2)
        ToolTip(min_entry, text='Minimum acceptable float value.')

        ttk.Label(frame, text='Max Float:').grid(row=5, column=0, sticky='e', pady=2)
        max_float_var = tk.StringVar(value=str(self.last_filters.get('max_float', '')))
        max_entry = ttk.Entry(frame, textvariable=max_float_var, width=10)
        max_entry.grid(row=5, column=1, sticky='w', pady=2)
        ToolTip(max_entry, text='Maximum acceptable float value.')

        ttk.Label(frame, text='Category:').grid(row=6, column=0, sticky='e', pady=2)
        category_var = tk.StringVar(value=self.last_filters.get('category', 'Any'))
        category_cb = ttk.Combobox(frame, textvariable=category_var, values=list(CATEGORY_CHOICES))
        category_cb.grid(row=6, column=1, sticky='ew', pady=2)
        ToolTip(category_cb, text='Filter results by sub-category.')

        ttk.Label(frame, text='Sort By:').grid(row=7, column=0, sticky='e', pady=2)
        sort_var = tk.StringVar(value=self.last_filters.get('sort_by', 'most_recent'))
        sort_cb = ttk.Combobox(frame, textvariable=sort_var, values=SORT_OPTIONS)
        sort_cb.grid(row=7, column=1, sticky='ew', pady=2)
        ToolTip(sort_cb, text='Choose how results are sorted.')

        include_auctions_var = tk.BooleanVar(value=self.last_filters.get('include_auctions', True))
        include_chk = ttk.Checkbutton(frame, text='Include Auctions', variable=include_auctions_var)
        include_chk.grid(row=8, column=1, sticky='w', pady=2)
        ToolTip(include_chk, text='Toggle to include auction listings.')

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

        search_btn = ttk.Button(frame, text='Search', command=search, bootstyle='primary')
        search_btn.grid(row=9, column=1, pady=10, sticky='e')
        ToolTip(search_btn, text='Execute search (Enter)')
        self.root.unbind('<Return>')
        self.root.bind('<Return>', lambda e: search())

        if self.history:
            ttk.Label(frame, text='Recent Searches:').grid(row=10, column=0, sticky='ne')
            hist_frame = ttk.Frame(frame)
            hist_frame.grid(row=10, column=1, sticky='w')
            for entry in self.history:
                summary = self.format_history_entry(entry)
                params_copy = entry['params'].copy()
                ttk.Button(hist_frame, text=summary, command=lambda p=params_copy: self.perform_search(p), bootstyle='secondary').pack(fill='x', pady=2)

    def show_bulk_search(self) -> None:
        if not self.api_key:
            self.api_key = get_api_key(self.cfg, self.root)
            if not self.api_key:
                return

        self.clear_content()
        frame = self.content

        listbox = tk.Listbox(frame, height=10)
        listbox.pack(fill='both', expand=True, pady=5)
        self.bulk_listbox = listbox
        for entry in self.bulk_items:
            listbox.insert('end', entry['label'])

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(pady=10, fill='x')

        ttk.Button(btn_frame, text='Add Item', command=self.open_bulk_item_modal).pack(side='left')

        def remove_selected() -> None:
            sel = listbox.curselection()
            if sel:
                idx = sel[0]
                listbox.delete(idx)
                del self.bulk_items[idx]

        ttk.Button(btn_frame, text='Remove Selected', command=remove_selected).pack(side='left', padx=5)
        ttk.Button(btn_frame, text='Search All', command=self.perform_bulk_search, bootstyle='primary').pack(side='right')

    def open_bulk_item_modal(self) -> None:
        win = ttk.Toplevel(self.root)
        win.title('Add Bulk Search Item')
        try:
            win.attributes('-alpha', 0.0)
            fade_in(win)
        except tk.TclError:
            pass

        params: dict = {}

        ttk.Label(win, text='Item Type:').grid(row=0, column=0, sticky='e')
        item_type_var = tk.StringVar(value='Skin')
        ttk.Combobox(win, textvariable=item_type_var, values=list(ITEM_TYPES)).grid(row=0, column=1, sticky='w')

        ttk.Label(win, text='Item Name:').grid(row=1, column=0, sticky='e')
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

        ttk.Label(win, text='Wear:').grid(row=3, column=0, sticky='e')
        wear_var = tk.StringVar()
        ttk.Combobox(win, textvariable=wear_var, values=WEAR_LIST).grid(row=3, column=1, sticky='w')

        ttk.Label(win, text='Min Float:').grid(row=4, column=0, sticky='e')
        min_float_var = tk.StringVar()
        ttk.Entry(win, textvariable=min_float_var, width=10).grid(row=4, column=1, sticky='w')

        ttk.Label(win, text='Max Float:').grid(row=5, column=0, sticky='e')
        max_float_var = tk.StringVar()
        ttk.Entry(win, textvariable=max_float_var, width=10).grid(row=5, column=1, sticky='w')

        ttk.Label(win, text='Category:').grid(row=6, column=0, sticky='e')
        category_var = tk.StringVar(value='Any')
        ttk.Combobox(win, textvariable=category_var, values=list(CATEGORY_CHOICES)).grid(row=6, column=1, sticky='w')

        ttk.Label(win, text='Sort By:').grid(row=7, column=0, sticky='e')
        sort_var = tk.StringVar(value='most_recent')
        ttk.Combobox(win, textvariable=sort_var, values=SORT_OPTIONS).grid(row=7, column=1, sticky='w')

        include_auctions_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(win, text='Include Auctions', variable=include_auctions_var).grid(row=8, column=1, sticky='w')

        def save() -> None:
            params.clear()
            params['type'] = 'buy_now' if not include_auctions_var.get() else None
            itype = ITEM_TYPES.get(item_type_var.get())
            if itype and itype in {'Skin', 'Glove'}:
                w = wear_var.get().strip()
                if w:
                    params['wear'] = w
            name = name_var.get().strip()
            if not name:
                self.toast('Item name required', 'danger')
                return
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
            if include_auctions_var.get() and params.get('type'):
                params.pop('type')
            entry_label = self.format_history_entry({'name': name, 'params': params})
            self.bulk_items.append({'params': params.copy(), 'label': entry_label})
            if getattr(self, 'bulk_listbox', None):
                self.bulk_listbox.insert('end', entry_label)
            win.destroy()

        ttk.Button(win, text='Add', command=save, bootstyle='success').grid(row=9, column=1, pady=10, sticky='e')
        win.grab_set()
        self.root.wait_window(win)

    def perform_bulk_search(self) -> None:
        if not self.bulk_items:
            self.toast('No items to search', 'warning')
            return
        def worker() -> None:
            results: list[dict] = []
            interval = rate_limit_interval()
            for idx, entry in enumerate(self.bulk_items):
                params = entry['params'].copy()
                params['limit'] = 1
                params['sort_by'] = 'lowest_price'
                start = time.time()
                data = query_listings(self.api_key, params)
                if data:
                    listings = data.get('data') if isinstance(data, dict) else data
                    if listings:
                        item = listings[0]
                        price_cents = item.get('price')
                        float_val = item.get('float', {}).get('float_value')
                        listing_id = item.get('id')
                        price = price_cents / 100 if isinstance(price_cents, (int, float)) else None
                        results.append({
                            'name': params.get('market_hash_name', ''),
                            'price': price,
                            'float': float_val,
                            'id': listing_id,
                            'params': params,
                        })
                self.last_refresh_time = datetime.now().strftime('%H:%M:%S')
                self.root.after(0, self.update_status)
                elapsed = time.time() - start
                if idx < len(self.bulk_items) - 1:
                    time.sleep(max(0, interval - elapsed))
            self.root.after(0, lambda: self.show_bulk_results(results))

        threading.Thread(target=worker, daemon=True).start()

    def show_bulk_results(self, results: list[dict]) -> None:
        win = ttk.Toplevel(self.root)
        win.title('Bulk Search Results')
        try:
            win.attributes('-alpha', 0.0)
            fade_in(win)
        except tk.TclError:
            pass
        frame = ttk.Frame(win, padding=10)
        frame.pack(fill='both', expand=True)

        tree = ttk.Treeview(frame, columns=('item', 'price', 'float'), show='headings')
        tree.heading('item', text='Item')
        tree.heading('price', text='Lowest Price')
        tree.heading('float', text='Float')
        tree.column('item', width=300)
        tree.pack(fill='both', expand=True)

        for res in results:
            price = f"${res['price']:.2f}" if isinstance(res['price'], (int, float)) else ''
            float_val = res['float'] if res['float'] is not None else ''
            tree.insert('', 'end', values=(res['name'], price, float_val))

        lowest = min((r['price'] for r in results if isinstance(r['price'], (int, float))), default=None)
        if lowest is not None:
            ttk.Label(frame, text=f'Overall lowest price: ${lowest:.2f}').pack(anchor='w', pady=5)

        def open_listing(event=None) -> None:
            sel = tree.selection()
            if not sel:
                self.toast('No item selected', 'warning')
                return
            idx = tree.index(sel[0])
            listing_id = results[idx].get('id')
            if listing_id:
                webbrowser.open_new_tab(f'https://csfloat.com/item/{listing_id}')

        def track_selected() -> None:
            sel = tree.selection()
            if not sel:
                self.toast('No item selected', 'warning')
                return
            idx = tree.index(sel[0])
            params = results[idx].get('params', {})
            self.open_search_track_modal(params)

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(pady=10, anchor='e', fill='x')
        ttk.Button(btn_frame, text='Open Listing', command=open_listing, bootstyle='secondary').pack(side='left')
        ttk.Button(btn_frame, text='Track Selected', command=track_selected, bootstyle='warning').pack(side='right')

        tree.bind('<Double-1>', open_listing)
        tree.bind('<Return>', open_listing)

    def perform_search(self, params: dict) -> None:
        if not params:
            return

        self.clear_content()
        overlay = ttk.Toplevel(self.root)
        overlay.transient(self.root)
        overlay.grab_set()
        overlay.title('Searching')
        overlay.geometry('200x100')
        ttk.Label(overlay, text='Searching...').pack(pady=10)
        pb = ttk.Progressbar(overlay, mode='indeterminate', bootstyle='info-striped')
        pb.pack(fill='x', padx=20, pady=10)
        pb.start()

        def worker() -> None:
            data = query_listings(self.api_key, params)
            if data is not None:
                self.last_refresh_time = datetime.now().strftime('%H:%M:%S')
            self.root.after(0, lambda: display_results(data))
            self.root.after(0, self.update_status)

        def display_results(data):
            pb.stop()
            overlay.destroy()
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

        columns = ['Name', 'Wear', 'Float', 'Price', 'Type', 'Time left']
        tree = ttk.Treeview(self.content, columns=columns, show='headings', bootstyle='success')
        for col in columns:
            tree.heading(col, text=col, command=lambda c=col: self._sort(tree, c, False))
            anchor = 'w' if col in {'Name', 'Wear', 'Type', 'Time left'} else 'e'
            tree.column(col, anchor=anchor, width=120, stretch=True)
        tree.column('Name', width=250)

        self.col_vars = {col: tk.BooleanVar(value=True) for col in columns}

        def update_columns() -> None:
            display = [c for c, v in self.col_vars.items() if v.get()]
            tree['displaycolumns'] = display

        menu = tk.Menu(tree, tearoff=0)
        for col in columns:
            menu.add_checkbutton(label=col, variable=self.col_vars[col], command=update_columns)

        def show_menu(event):
            menu.tk_popup(event.x_root, event.y_root)

        tree.bind('<Button-3>', show_menu)
        tree['displaycolumns'] = columns

        id_map: dict[str, str] = {}
        search_key = make_search_key(params)
        settings = self.tracked_items.get(search_key)

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
            iid = tree.insert('', 'end', values=(name, wear_name, float_val, price, auction_info, time_left or ''))
            if item.get('id'):
                id_map[iid] = item['id']

            if settings and settings.get('track_alerts') and isinstance(price_cents, (int, float)) and isinstance(float_val, (int, float)):
                price_val = price_cents / 100
                if price_val <= settings.get('threshold', float('inf')) and settings.get('float_min', 0) <= float_val <= settings.get('float_max', 1):
                    tree.item(iid, tags=('match',))
                    tree.tag_configure('match', background='yellow')
                    last = settings.get('last_notified_price')
                    if last is None or price_val < last:
                        show_desktop_notification(search_key, {'price': price_val, 'float': float_val})
                        settings['last_notified_price'] = price_val
                        save_tracked_items(self.tracked_items)

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

        def track_search() -> None:
            self.open_search_track_modal(params)

        btn_frame = ttk.Frame(self.content)
        btn_frame.pack(pady=10, anchor='e', fill='x')
        ttk.Button(btn_frame, text='Open Listing', command=open_listing, bootstyle='secondary').pack(side='left')
        ttk.Button(btn_frame, text='Copy URL', command=copy_url, bootstyle='secondary').pack(side='left', padx=5)
        ttk.Button(btn_frame, text='Track This Search', command=track_search, bootstyle='warning').pack(side='right')

        tree.bind('<Double-1>', open_listing)
        tree.bind('<Return>', open_listing)
        tree.bind('<Control-c>', lambda e: copy_url())

    def show_results_window(self, listings: list, params: dict) -> None:
        win = ttk.Toplevel(self.root)
        win.title(make_search_key(params))
        try:
            win.attributes('-alpha', 0.0)
            fade_in(win)
        except tk.TclError:
            pass
        frame = ttk.Frame(win, padding=10)
        frame.pack(fill='both', expand=True)
        old = self.content
        self.content = frame
        try:
            self.show_results(listings, params)
        finally:
            self.content = old

    def _sort(self, tree: ttk.Treeview, col: str, reverse: bool) -> None:
        data = [(tree.set(k, col), k) for k in tree.get_children('')]
        try:
            data.sort(key=lambda t: float(t[0].strip('$')) if t[0] else 0.0, reverse=reverse)
        except ValueError:
            data.sort(reverse=reverse)
        for idx, (_, k) in enumerate(data):
            tree.move(k, '', idx)
        tree.heading(col, command=lambda: self._sort(tree, col, not reverse))

    
    def open_search_track_modal(self, params: dict) -> None:
        key = make_search_key(params)
        data = self.tracked_items.get(key, {})
        win = ttk.Toplevel(self.root)
        win.title(f'Track search: {key}')
        try:
            win.attributes('-alpha', 0.0)
            fade_in(win)
        except tk.TclError:
            pass
        alert_var = tk.BooleanVar(value=data.get('track_alerts', True))
        price_var = tk.BooleanVar(value=data.get('track_prices', False))
        thresh_var = tk.StringVar(value=str(data.get('threshold', '')))
        fmin_var = tk.StringVar(value=str(data.get('float_min', '')))
        fmax_var = tk.StringVar(value=str(data.get('float_max', '')))

        ttk.Checkbutton(win, text='Track for alerts', variable=alert_var).pack(padx=10, pady=(10, 0), anchor='w')
        ttk.Checkbutton(win, text='Track for price evolution', variable=price_var).pack(padx=10, pady=0, anchor='w')
        frm = ttk.Frame(win)
        frm.pack(padx=10, pady=5, fill='x')
        ttk.Label(frm, text='Max Price:').grid(row=0, column=0, sticky='e')
        ttk.Entry(frm, textvariable=thresh_var, width=10).grid(row=0, column=1, sticky='w')
        ttk.Label(frm, text='Float Range:').grid(row=1, column=0, sticky='e')
        ttk.Entry(frm, textvariable=fmin_var, width=10).grid(row=1, column=1, sticky='w')
        ttk.Entry(frm, textvariable=fmax_var, width=10).grid(row=1, column=2, sticky='w', padx=(5, 0))

        def save() -> None:
            try:
                threshold = float(thresh_var.get()) if thresh_var.get() else float('inf')
                fmin = float(fmin_var.get()) if fmin_var.get() else 0.0
                fmax = float(fmax_var.get()) if fmax_var.get() else 1.0
            except ValueError:
                self.toast('Invalid number entered', 'danger')
                return
            existing = self.tracked_items.get(key, {})
            self.tracked_items[key] = {
                'params': params.copy(),
                'track_alerts': alert_var.get(),
                'track_prices': price_var.get(),
                'threshold': threshold,
                'float_min': fmin,
                'float_max': fmax,
                'last_notified_price': existing.get('last_notified_price'),
            }
            save_tracked_items(self.tracked_items)
            if alert_var.get():
                self.start_search_checker(key)
            else:
                ev = self.search_threads.pop(key, None)
                if ev:
                    ev.set()
            if price_var.get():
                self.start_tracking(key, params)
            else:
                ev = self.active_tracks.pop(key, None)
                if ev:
                    ev.set()
            win.destroy()
            self.toast('Tracking preferences saved', 'success')

        ttk.Button(win, text='Save', command=save, bootstyle='success').pack(pady=(5, 10))
        win.grab_set()
        self.root.wait_window(win)

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
            if name in self.tracked_items:
                self.tracked_items[name]['track_prices'] = False
                save_tracked_items(self.tracked_items)

        stop_event = track_price(self.api_key, params, name, show_window, on_stop=_on_stop)
        self.active_tracks[name] = stop_event
        entry = self.tracked_items.setdefault(name, {'params': params.copy()})
        entry['params'] = params.copy()
        entry['track_prices'] = True
        save_tracked_items(self.tracked_items)

    def toggle_price_tracking(self, name: str) -> None:
        data = self.tracked_items.get(name)
        if not data:
            return
        if data.get('track_prices'):
            ev = self.active_tracks.pop(name, None)
            if ev:
                ev.set()
            data['track_prices'] = False
            self.toast(f'Tracking paused for {name}', 'info')
        else:
            self.start_tracking(name, data.get('params', {}), show_window=False)
            self.toast(f'Tracking resumed for {name}', 'success')
        save_tracked_items(self.tracked_items)

    def toggle_alert_tracking(self, name: str) -> None:
        data = self.tracked_items.get(name)
        if not data:
            return
        if data.get('track_alerts'):
            ev = self.search_threads.pop(name, None)
            if ev:
                ev.set()
            data['track_alerts'] = False
            self.toast(f'Alerts paused for {name}', 'info')
        else:
            data['track_alerts'] = True
            self.start_search_checker(name)
            self.toast(f'Alerts enabled for {name}', 'success')
        save_tracked_items(self.tracked_items)

    def delete_tracking(self, name: str) -> None:
        data = self.tracked_items.pop(name, None)
        if data:
            ev = self.active_tracks.pop(name, None)
            if ev:
                ev.set()
            ev = self.search_threads.pop(name, None)
            if ev:
                ev.set()
            save_tracked_items(self.tracked_items)
            fname = os.path.join('tracked_logs', f"{name.replace(' ', '_').replace('|', '_')}.csv")
            if os.path.exists(fname):
                try:
                    os.remove(fname)
                except OSError:
                    pass
            self.toast(f'Removed tracking for {name}', 'danger')
            self.show_tracked_items()

    def start_search_checker(self, key: str) -> None:
        data = self.tracked_items.get(key)
        if not data or not data.get('track_alerts') or key in self.search_threads:
            return
        stop_event = threading.Event()
        self.search_threads[key] = stop_event

        def _run() -> None:
            while not stop_event.is_set():
                res = query_listings(self.api_key, data.get('params', {}))
                if res:
                    listings = res.get('data') if isinstance(res, dict) else res
                    for item in listings:
                        price_cents = item.get('price')
                        float_val = item.get('float', {}).get('float_value')
                        if isinstance(price_cents, (int, float)) and isinstance(float_val, (int, float)):
                            price_val = price_cents / 100
                            if price_val <= data.get('threshold', float('inf')) and data.get('float_min', 0) <= float_val <= data.get('float_max', 1):
                                last = data.get('last_notified_price')
                                if last is None or price_val < last:
                                    show_desktop_notification(key, {'price': price_val, 'float': float_val})
                                    data['last_notified_price'] = price_val
                                    save_tracked_items(self.tracked_items)
                for _ in range(SEARCH_INTERVAL):
                    if stop_event.is_set():
                        break
                    time.sleep(1)

        threading.Thread(target=_run, daemon=True).start()

    def open_csv(self, name: str) -> None:
        fname = os.path.join('tracked_logs', f"{name.replace(' ', '_').replace('|', '_')}.csv")
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
        btn_txt = tk.StringVar(value='Pause' if self.tracked_items.get(name, {}).get('track_prices') else 'Resume')

        def toggle() -> None:
            self.toggle_price_tracking(name)
            btn_txt.set('Pause' if self.tracked_items.get(name, {}).get('track_prices') else 'Resume')

        ttk.Button(btn_frame, textvariable=btn_txt, command=toggle).pack(side='left', padx=5)
        ttk.Button(btn_frame, text='Close', command=win.destroy).pack(side='right')

    def show_tracked_items(self) -> None:
        self.clear_content()
        if not self.tracked_items:
            ttk.Label(self.content, text='No tracked items').pack(pady=10)
            return
        ttk.Label(self.content, text='Tracked Items', font=('Helvetica', 14, 'bold')).pack(pady=(0, 10))
        for name, data in self.tracked_items.items():
            row = ttk.Frame(self.content)
            row.pack(fill='x', pady=2)
            ttk.Label(row, text=name).pack(side='left')
            modes = []
            if data.get('track_alerts'):
                modes.append('Alert')
            if data.get('track_prices'):
                modes.append('Evolution')
            ttk.Label(row, text='+'.join(modes) or 'None').pack(side='left', padx=10)
            if data.get('track_prices'):
                ttk.Button(row, text='Open CSV', command=lambda n=name: self.open_csv(n)).pack(side='right', padx=5)
            price_txt = 'Pause Price' if data.get('track_prices') else 'Start Price'
            alert_txt = 'Pause Alert' if data.get('track_alerts') else 'Start Alert'
            ttk.Button(row, text='Delete', command=lambda n=name: self.delete_tracking(n), bootstyle='danger').pack(side='right')
            ttk.Button(row, text=price_txt, command=lambda n=name: self.toggle_price_tracking(n)).pack(side='right', padx=5)
            ttk.Button(row, text=alert_txt, command=lambda n=name: self.toggle_alert_tracking(n)).pack(side='right', padx=5)

    def show_tracked_alerts(self) -> None:
        self.show_tracked_items()

def main() -> None:
    cfg = load_config()
    theme = cfg.get('theme', 'darkly')
    root = ttk.Window(themename=theme)
    app = PriceCheckerGUI(root)
    root.mainloop()


if __name__ == '__main__':
    main()
