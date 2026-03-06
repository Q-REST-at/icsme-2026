"""
A simplistic DeepL wrapper with minimal dependencies.
Usage:
    $ deepl.py

Note: the datasets can be up to 100k characters, use cautiously!
"""

from os import getenv
import pandas as pd
from time import sleep
from requests import post, Response
from dotenv import load_dotenv

load_dotenv()
DEEPL_API_KEY = getenv('DEEPL_API_KEY')

class Config:
    """
    Edit manually, for simplicity.
    """
    # IN_FILE_PATH: str        = 'AMINA_ST.csv'
    # OUT_FILE_PATH: str       = 'AMINA_ST_translated.csv'
    # COLS_TO_TRANS: list[str] = [
    #     "Purpose",
    #     "Test steps"
    # ]
    IN_FILE_PATH: str        = 'AMINA_RE.csv'
    OUT_FILE_PATH: str       = 'AMINA_RE_translated.csv'
    COLS_TO_TRANS: list[str] = [
        "Feature",
        "Description"
    ]

def translate_text(text, source_lang='SV', target_lang='EN-US') -> str:
    """
    A helper function that queries DeepL to translate a single entry from
    Swedish to English (US).
    """

    DEEPL_API_URL: str = 'https://api-free.deepl.com/v2/translate'

    if pd.isna(text) or text.strip() == '': return ''

    response: Response = post(
        DEEPL_API_URL,
        data={
            'auth_key': DEEPL_API_KEY,
            'text': text,
            'source_lang': source_lang,
            'target_lang': target_lang
        }
    )

    if response.status_code == 200:
        return response.json()['translations'][0]['text']
    else:
        print(f"Error {response.status_code}: {response.text}")
        return text


df = pd.read_csv(Config.IN_FILE_PATH)

res: dict[str, list[str]] = {k: [] for k in Config.COLS_TO_TRANS}

for index, row in df.iterrows():
    print(f"Translating row: {index+1}")
    for col in Config.COLS_TO_TRANS:
        res[col].append(translate_text(row[col]))
        sleep(0.25)

    sleep(1) # Avoid hitting rate limits

# Add new cols
for col in Config.COLS_TO_TRANS:
    new_key: str = f"{col}.Translated"
    df[new_key] = res[col]

df.to_csv(Config.OUT_FILE_PATH, index=False)
