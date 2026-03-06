"""
Clean up the dataset provided by Göteborg Energi of the AMINA subsystem.
"""

import re
import pandas as pd
from collections import defaultdict

RE_df = pd.read_csv('AMINA_RE_raw.csv', sep=';')

# Retain only the desired columns (Swedish) and translate on the spot
RE_df = RE_df[['ID', 'Rubrik', 'Beskrivning']]
RE_df.columns = ['ID', 'Feature', 'Description']

"""
A system defined ID is labeled 'Krav ID' (requirement ID) in the raw CSV
files. These IDs follow the format: <SN> | <BN>, where N is a number up to 999
(i.e., 3 digits). In most cases, the ID is followed by a hyphen " - " which
should be ignored.
"""

req_id_pattern = re.compile(
        r'\b([SB]\d{1,3})\s*-\s*|\b([SB]\d{1,3})\b'
        # case 1 (with -), case 2 (without) to be sure.
, re.IGNORECASE)

def extract_and_clean_feature(text):
    if isinstance(text, str):
        match = req_id_pattern.search(text)
        if match:
            code = match.group(1) or match.group(2)
            cleaned = req_id_pattern.sub('', text).strip()
            return code, cleaned
    return None, None

extracted = RE_df['Feature'].apply(extract_and_clean_feature)
RE_df['ID']      = extracted.apply(lambda x: x[0])  # Assign extracted code to 'ID'
RE_df['Feature'] = extracted.apply(lambda x: x[1])  # Apply cleaned text

RE_df = RE_df.dropna(subset=['ID'])

# Also, in the descriptions, we find (<ID>) which should be filtered.
desc_req_id_pattern = re.compile(r'\(\s*[SB]\d{1,3}\s*\)', re.IGNORECASE)
if 'Description' in RE_df.columns:
    RE_df['Description'] = RE_df['Description'].apply(
        lambda text:
            re.sub(r'\s{2,}', ' ', desc_req_id_pattern.sub('', text)).strip()
                if isinstance(text, str) else text
)

RE_df.to_csv('AMINA_RE.csv', index=False)

###############################################################################

RE_df = pd.read_csv('AMINA_RE_raw.csv', sep=';')
ST_df = pd.read_csv('AMINA_ST_raw.csv', sep=';')

# Concatenate all test steps; beskrivning = description.
desc_cols = [col for col in ST_df.columns if col.startswith('Beskrivning')]

def clean_concat(row):
    items = [str(val).strip() for val in row if pd.notna(val) and str(val).strip() != '']
    return ','.join(items)

ST_df['Test steps'] = ST_df[desc_cols].apply(clean_concat, axis=1)

ST_df = ST_df[ST_df['Test steps'] != ''] # Filter out rows where 'Test steps' is empty
ST_df.drop(columns=desc_cols, inplace=True)      # Drop the original 'Beskrivning' columns

# Rename remaining columns
ST_df.rename(columns={
    ST_df.columns[0]: 'ID',
    ST_df.columns[1]: 'Purpose'
}, inplace=True)

# Now, we want to make the mapping. But for that, we still need the Req. Ids in
# the tests, so we'll filter them later.

# Extract all req. IDs
ge_krav_ids = RE_df['GE KravID'].dropna().astype(str).unique()

krav_to_ids = defaultdict(list)

regex_patterns = {
    krav_id: re.compile(rf'(?<!\w){re.escape(krav_id)}(?!\w)', re.IGNORECASE)
    for krav_id in ge_krav_ids
}

for _, row in ST_df.iterrows():
    purpose_text = str(row['Purpose'])
    test_id = row['ID']
    
    # Check if the Req. id appears in the test; if so, take record of this and
    # map the Req. id to the test.
    for req_id, req_id_pattern in regex_patterns.items():
        if req_id_pattern.search(purpose_text):
            krav_to_ids[req_id].append(test_id)

# Prepare for saving, we want to group all test IDs if they have a Req. ID in
# common.
mappings = []
for req_id, ids in krav_to_ids.items():
    id_str = ",".join(map(str, sorted(set(ids))))
    mappings.append({'Req ID': req_id, 'Test ID': id_str})

mapping_df = pd.DataFrame(mappings)
mapping_df.to_csv('AMINA-mapping.csv', index=False)

###############################################################################

# Now we've made the mapping, we want to hide all Req. Ids from the tests.
req_id_pattern = re.compile(r'\b[SB]\d{1,3}(?:\s*-\s*)?', re.IGNORECASE)

def clean_purpose(text):
    if isinstance(text, str) and req_id_pattern.search(text):
        return req_id_pattern.sub('', text).strip()
    return None

ST_df['Purpose'] = ST_df['Purpose'].apply(clean_purpose)
cleaned_df = ST_df.dropna(subset=['Purpose']) # filter empty

cleaned_df.to_csv('AMINA_ST.csv', index=False)
