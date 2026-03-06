# TODO: remap metric names properly
import re
import pandas as pd

file_path = "./analysis/summary_table.csv"

df = pd.read_csv(file_path)

numeric_cols: list[str] = list(df.columns)
numeric_cols.remove('Treatment')

# Use `min` on these, not `max`
min_cols: list[str] = ['Time to Analyze', 'VRAM Max Usage MiB']

def format_latex_mathmode(t: tuple[float, float]) -> str:
    return f"${t[0]}\\pm{t[1]}$"

def parse_uncertainty(value: str) -> tuple[float, float]:
    # Allow for both "±" and "+/-" symbols
    pattern = r"^\s*([+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)\s*(?:±|\+/-)\s*([+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)\s*$"
    
    match = re.match(pattern, value)
    if not match:
        raise ValueError(f"Invalid uncertainty format: '{value}'")
    
    mean = float(match.group(1))
    uncertainty = float(match.group(2))
    return mean, uncertainty


# for n_col in numeric_cols:
#     df[n_col] = df[n_col].apply(format_latex_mathmode)

highlight_color: str = "9fd6b5" # that's what we decided on ultimately

REMAP_DATASET: dict[str, str | None] = {
    "AMINA":   None,
    "BTHS":    None,
    "HW":      "Health Watcher",
    "MOZILLA": "Mozilla"
}

def find_dataset_label(x: str) -> str:
    l: str | None = REMAP_DATASET[x.upper()]
    return x if l is None else l


df['dataset'] = df['Treatment'].apply(lambda x: x.split("_")[2])
df['Treatment'] = df['Treatment'].apply(lambda x: x.split("_")[1])
group_by_dataset = df.groupby('dataset')

tables: list[str] = []

for dataset, df in group_by_dataset:
    del df['dataset']

    for n_col in numeric_cols:
        df[f'{n_col}_tuple'] = df[n_col].apply(parse_uncertainty)

        if n_col in min_cols:
            best = min(df[f'{n_col}_tuple'], key=lambda x : (x[0], -x[1]))
        else:
            best = max(df[f'{n_col}_tuple'], key=lambda x : (x[0], -x[1]))
        
        df[f'{n_col}_str'] = df[f'{n_col}_tuple'].apply(
            lambda x: f"\\colorbox{{hl_color_green}}{{{format_latex_mathmode(x)}}}" if x == best else format_latex_mathmode(x)
        )

    df = df[['Treatment'] + [col for col in df.columns if col.endswith('_str')]]
    df.rename(columns={'Treatment': 'Model'}, inplace=True) # Use Treatment instead of Model
    df.columns = [col.replace("_str", "") for col in df.columns]

    latex_table = df.to_latex(
        index=False,
        escape=False,
        column_format="p{1cm} p{2.2cm} p{1.5cm} p{1.5cm} p{1.5cm} p{2cm} p{2.8cm}"
    )

    table = (
        "\\begin{subtable}{\\textwidth}\n"
        "\\centering\n"
        f"\\caption*{{{find_dataset_label(dataset)} dataset}}\n"
        + latex_table +
        "\\end{subtable}\n"
    )
    tables.append(table)

final_table: str = (
    f"\\definecolor{{hl_color_green}}{{HTML}}{{{highlight_color}}}\n\n"
    "\\begin{table*}[ht]\n"
    "\\centering\n"
    + "\n".join(table.replace("\\begin{table}", "").replace("\\end{table}", "") for table in tables) +
    "\\caption{Key metrics summary table}\n"
    "\\label{tab:metric_summary}\n"
    "\\end{table*}\n"
)

with open(f"tables/summary_table.tex", 'w') as f:
   f.write(final_table)
