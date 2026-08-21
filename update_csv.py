import csv

filepath = r'C:\Users\moody\.gemini\antigravity\scratch\Praecursor-EGX\config\symbols.csv'

sectors = {
    'COMI': 'Banks', 'HRHO': 'Financials', 'TMGH': 'Real Estate', 'ADIB': 'Banks',
    'CIEB': 'Banks', 'FAITA': 'Banks', 'FAIT': 'Banks', 'HDBK': 'Banks', 'EXPA': 'Banks',
    'PHDC': 'Real Estate', 'HELI': 'Real Estate', 'ORHD': 'Real Estate', 'EMFD': 'Real Estate',
    'OCDI': 'Real Estate', 'MNHD': 'Real Estate', 'SWDY': 'Industrials', 'ABUK': 'Basic Resources',
    'AMOC': 'Basic Resources', 'MFPC': 'Basic Resources', 'SKPC': 'Basic Resources',
    'EAST': 'Food & Beverage', 'JUFO': 'Food & Beverage', 'EFID': 'Food & Beverage',
    'DOMT': 'Food & Beverage', 'ISPH': 'Healthcare & Pharma', 'CLHO': 'Healthcare & Pharma',
    'FWRY': 'Technology', 'EFIH': 'Technology', 'ETEL': 'Telecommunications'
}

with open(filepath, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    fieldnames = reader.fieldnames
    if 'sector' not in fieldnames:
        fieldnames = fieldnames[:-1] + ['sector', fieldnames[-1]]
    rows = list(reader)

for row in rows:
    sym = row['egx_symbol']
    row['sector'] = sectors.get(sym, 'General')

with open(filepath, 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
print('Done modifying symbols.csv')
