"""
Determines the average prompt string size of each dataset dynamically.

<PROMPT_TEMPLATE>
    REQ         : one at a time
    {ALL_TESTS} : * sample_size | st_row_count
<PROMPT_TEMPLATE>
"""

import pandas as pd

def average_text_length_in_column(csv_file_path: str, column_name: str) -> float:
    avg = 0
    try:
        df = pd.read_csv(csv_file_path)
        
        if column_name not in df.columns:
            print(f"Column '{column_name}' not found in CSV.")
            return avg
        
        text_data = df[column_name].dropna().astype(str)
        
        # Compute the average string length
        total_length = text_data.apply(len).sum()
        avg = total_length / len(text_data) if len(text_data) > 0 else 0
        
        print(f"Average text string length in column '{column_name}': {avg:.2f}")
    
    except Exception as e:
        print(f"Error: {e}")

    return avg


def number_of_rows(csv_file_path) -> int:
    size = 0
    try:
        df = pd.read_csv(csv_file_path)
        size = df.shape[0]
        print(f"{csv_file_path} Number of entries: {size}")
    
    except Exception as e:
        print(f"Error: {e}")
    return size


RE_column_to_check: list[str] = [
    "Feature", "Description"
]
ST_column_to_check: list[str] = [
    "Purpose", "Test steps"
]

datasets = ["AMINA", "BTHS", "Mozilla", "HealthWatcher"]

SAMPLE_SIZE: int = 25
PROMPT_TEMPLATE_CHAR_COUNT = 518 # the text without the req. & tests

for data in datasets:
    re_path = f"./data/{data}/RE.csv"
    st_path = f"./data/{data}/ST.csv"
    
    re_count = number_of_rows(re_path) # nr. of REs
    if re_count < SAMPLE_SIZE:
        st_row_count = number_of_rows(st_path)
    else:
        st_row_count = SAMPLE_SIZE
    
    re_char_count = st_char_count = 0
    prompt_char_count = PROMPT_TEMPLATE_CHAR_COUNT

    for re_col in RE_column_to_check:
        avg = average_text_length_in_column(re_path, re_col)
        re_char_count += avg 

    for st_col in ST_column_to_check:
        avg = average_text_length_in_column(st_path, st_col)
        st_char_count += st_row_count * avg 

    prompt_char_count += re_char_count # One requirement (Feature + Description)
    prompt_char_count += st_char_count # All tests (Purpose + Test steps)

    print(f"{data}'s avg. prompt size (char): {round(prompt_char_count):,d} chars")
