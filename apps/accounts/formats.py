"""Shared settings for typed dates, so every date-of-birth box behaves the same way."""

# What the boxes accept. The page fills in the slashes as you type; the server also accepts 10141988 and 10-14-1988.
DATE_FORMATS = ["%m/%d/%Y", "%m%d%Y", "%m-%d-%Y", "%m.%d.%Y"]

DATE_ATTRS = {"placeholder": "MM/DD/YYYY", "autocomplete": "off", "inputmode": "numeric", "maxlength": "10", "data-format": "date"}
