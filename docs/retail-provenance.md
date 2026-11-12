# UCI Online Retail provenance

Source: https://archive.ics.uci.edu/dataset/352/online+retail

Attribution: Chen, D. (2015). Online Retail [Dataset]. UCI Machine Learning Repository. https://doi.org/10.24432/C5BW33. Licence: CC BY 4.0, https://creativecommons.org/licenses/by/4.0/ . This project profiles and will transform the source; it is not endorsed by its creator.

The original archive and workbook are retained locally under ignored `data/raw/online-retail/`. Download with `.\.venv\Scripts\python.exe scripts/profile_online_retail.py --download`; rerun without `--download` to reproduce the profile without network access. The manifest records hashes, worksheet, software versions and acquisition/profile time. No source rows or customer identifiers are published.

Observed source: 541,909 rows, 2010-12-01 08:26 through 2011-12-09 12:50, worksheet Online Retail. See [manifest](evidence/phase-1/manifest.json) and [profile](evidence/phase-1/profile.json). Actual missingness contradicts the source page's no-missing-values metadata; the workbook governs preparation.
