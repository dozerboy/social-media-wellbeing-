# Data source, licence and redistribution

## Source

- **Dataset:** Youth Risk Behavior Survey (YRBS), 2023 national high-school data.
- **Publisher:** U.S. Centers for Disease Control and Prevention (CDC).
- **Where to get it:** https://www.cdc.gov/yrbs/data/index.html → 2023 → **ASCII** (`XXH2023_YRBS_Data.dat`).

## Licence status

- CDC's data page does not state a licence or terms of use.
- Works produced by the U.S. federal government are generally not subject to copyright in the United States (17 U.S.C. § 105), so the data is generally treated as public domain in the US.
- This is not legal advice. If your college has its own rules on data use, follow them.

## What this repository contains

| File | Included? | Why |
|---|---|---|
| `data/processed/cleaned_data.csv` | Yes | A derived subset of CDC's file: 25 columns, 20,078 rows, answer codes turned into labels. The online dashboard needs it, so the app does not depend on downloading from CDC at runtime. |
| `data/processed/data_dictionary.csv` | Yes | Column descriptions |
| `data/raw/documentation/` | Yes | CDC's SAS programs and Data User's Guide, used to read the file correctly |
| `data/raw/XXH2023_YRBS_Data.dat` | No (`.gitignore`) | The original file. Download it from CDC with `python -m src.download_data`, or manually from the page above |

The YRBS public-use file is anonymous. It contains no names, addresses or school identifiers, and nothing here links to individual people.

## Attribution

Cite CDC whenever you show or share results:

> Centers for Disease Control and Prevention. Youth Risk Behavior Survey, 2023 national data.
> https://www.cdc.gov/yrbs/data/index.html. Processed by the authors; CDC is not responsible for this analysis.
