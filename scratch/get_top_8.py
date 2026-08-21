import pandas as pd
import re

def parse_md_table(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    table_lines = [line for line in content.split('\n') if line.strip().startswith('|')]
    if not table_lines: return None
    
    headers = [h.strip() for h in table_lines[0].split('|')[1:-1]]
    data = []
    for line in table_lines[2:]:
        row = [cell.strip() for cell in line.split('|')[1:-1]]
        if len(row) == len(headers):
            data.append(row)
            
    return pd.DataFrame(data, columns=headers)

df = parse_md_table('reports/opportunity_ranking.md')
if df is not None:
    # Filter candidates
    candidates = df[df['Next-Day Label'].str.contains('Candidate', na=False, case=False)]
    
    # Sort by Next-Day Score
    # The score might be "75/100" so we extract the numerator
    def extract_score(x):
        try: return float(x.split('/')[0])
        except: return 0.0
    
    candidates['Prob'] = candidates['Next-Day Score'].apply(extract_score)
    top8 = candidates.sort_values('Prob', ascending=False).head(8)
    
    res = top8[['Symbol', 'Latest Close', 'Next-Day Score', 'Next-Day Label']]
    print("TOP 8 CANDIDATES FOR TOMORROW (2026-08-11):")
    print(res.to_markdown(index=False))
else:
    print("No data found")
