# CSFloatPriceChecker

A script that checks CSFloat Market listings with various filters.
Prices are shown in US dollars rather than cents for easier reading.

## Usage

1. Install the dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Run the interactive script:
   ```bash
   python csfloat_cli.py
   ```

   The script stores your API key in `csfloat_config.json` and lets you search listings by item type, wear, float range and more. It now also allows you to include or exclude auction listings from the results. The key is sent using the `Authorization` header as required by the CSFloat API. All requests and responses are logged to `csfloat.log` for troubleshooting.


You can still run `secret.py` for a simple one-off price check.
