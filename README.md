# CSFloatPriceChecker

A script that checks CSFloat Market listings with various filters.

## Usage

1. Install the dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Run the interactive script:
   ```bash
   python csfloat_cli.py
   ```

   The script stores your API key in `csfloat_config.json` and lets you search listings by item type, wear, float range and more. Requests use a custom `User-Agent` so the CSFloat edge doesn't block them, and responses are logged to `csfloat.log` for troubleshooting.


You can still run `secret.py` for a simple one-off price check.
