# CSFloatPriceChecker

A script that checks CSFloat Market listings with various filters.
Prices are shown in US dollars rather than cents for easier reading.

## Usage

1. Install the dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Run the interactive CLI script:
   ```bash
   python csfloat_cli.py
   ```
3. Run the graphical interface:
   ```bash
   python csfloat_gui.py
   ```

The script stores your API key in `csfloat_config.json` and lets you search listings by item type, wear, float range and more. It now also allows you to include or exclude auction listings from the results. The key is sent using the `Authorization` header as required by the CSFloat API. All requests and responses are logged to `csfloat.log` for troubleshooting.

After showing search results you can opt in to background price tracking. If accepted, a small window opens that logs a new price check every minute and displays an indeterminate progress bar. Close the window or press the **Stop** button to end tracking. Data is appended to a `track_<item>.csv` file.


You can still run `secret.py` for a simple one-off price check.
