# CSFloatPriceChecker

A script that checks CSFloat Market listings with various filters.
Prices are shown in US dollars rather than cents for easier reading.
The GUI uses the `ttkbootstrap` theme library for a modern look.

## Installation

Install the package in editable mode so the command line entry points become
available:

```bash
pip install -e .
```

This exposes the `csfloat-price` and `csfloat-price-gui` commands.

## Usage

1. Run the interactive CLI:
   ```bash
   csfloat-price
   ```
2. Run the graphical interface:
   ```bash
   csfloat-price-gui
   ```

The script stores your API key in `csfloat_config.json` and lets you search listings by item type, wear, float range and more. It now also allows you to include or exclude auction listings from the results. The key is sent using the `Authorization` header as required by the CSFloat API. All requests and responses are logged to `csfloat.log` for troubleshooting.

After showing search results you can opt in to tracking. Two modes are available:

1. **Alerts** – get notified when a listing meets your price or float filters.
2. **Price evolution** – log every listing's price and float over time to `tracked_logs/<item>.csv`.

You can enable either or both modes. When price tracking is enabled a small window opens showing progress; click **Stop** to cancel.

The GUI remembers your last used filters. The results table supports column sorting and a **Copy URL** button to quickly copy the selected listing's link. A status bar shows how many requests were made in the last minute and the time of the most recent refresh. If the API returns a rate limit response, a warning toast is displayed.

From the results window you can also open the selected listing in your web browser using the **Open Listing** button (or by double clicking a row).


You can still run a one-off price check:
```bash
python -m csfloat_price_checker.api
```
