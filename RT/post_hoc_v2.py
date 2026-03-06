import pandas as pd

# TODO: add `\resizebox{\linewidth}{!}{...}` for in-text

RQ: int = 2
full_table: bool = False

# Load the CSV file
file_path = f"analysis/results/PT6/rq{RQ}_post-hoc_results-PT6.csv"
df = pd.read_csv(file_path)

# raw_name, is_in_small_table, extra_label
TABLE_DEF = list[tuple[str, bool, str | None]]

TABLE: TABLE_DEF = [
    ('dataset',      True,  None),
    ('metric',       True,  None),
    ('group1',       True,  'Group $1$'),
    ('group2',       True,  'Group $2$'),
    ('statistic',    False, None),
    ('p',            False, '$p$'),
    ('p.adj',        True,  '$p$.adj'),
    ('p.adj.signif', True,  '$p$.adj.signif'),
    ('vda',          True,  'VDA'),
    ('magnitude',    True,  None)
]

REMAP_METRIC: dict[str, str | None] = {
    "balanced_accuracy":  "Balanced accuracy",
    "recall":             None,
    "precision":          None,
    "f1":                 "$F_1$-score",
    "vram_max_usage_mib": "Maximum VRAM Usage (MiB)",
    "time_to_analyze":    "Inference Time (s)"
}

REMAP_DATASET: dict[str, str | None] = {
    "AMINA":   None,
    "BTHS":    None,
    "HW":      "Health Watcher",
    "MOZILLA": "Mozilla"
}

def find_metric_label(x: str) -> str:
    if x not in REMAP_METRIC: return x
    l: str | None = REMAP_METRIC[x.lower()]
    return x.capitalize() if l is None else l


def find_dataset_label(x: str) -> str:
    if x not in REMAP_DATASET: return x
    l: str | None = REMAP_DATASET[x.upper()]
    return x if l is None else l


def find_col_label(x: str) -> str | None:
    for name, _, label in TABLE:
        if x == name:
            return label
    return None


if full_table:
    df_filtered = df[[name for name, _, _ in TABLE]]
else:
    df_filtered = df[[name for name, flag, _ in TABLE if flag]]

def map_holm_bonferroni(x: str) -> str:
    if   (x == "***"): return "Very strong"
    elif (x == "**"):  return "Strong"
    elif (x == "*"):   return "Moderate"
    elif (x == "ns"):  return "Not significant"
    print(f"Unrecognized key {x} encountered in \"map_holm_bonferroni\"")
    return ""

if full_table:
    df_filtered['p'] = df_filtered['p.adj'].apply(lambda x: f"{x:.3f}")

df_filtered['p.adj'] = df_filtered['p.adj'].apply(lambda x: f"{x:.2f}")
df_filtered['p.adj.signif'] = df_filtered['p.adj.signif'].apply(
    lambda x: map_holm_bonferroni(str(x))
)
df_filtered['vda'] = df_filtered['vda'].apply(lambda x: f"{x:.2f}")

group_by_dataset = {
    dataset: group for dataset, group in df_filtered.groupby('dataset')
}

tables: list[str] = []


def replace_but_first_with_phantom(column):
    result = [column.iloc[0]]  # Keep the first value
    for i in range(1, len(column)):
        if column.iloc[i] == column.iloc[i - 1]:
            result.append("\\phantom")
        else:
            result.append(column.iloc[i])
    return pd.Series(result, index=column.index)


def apply_midrule(df, col: str = "Metric") -> str:
    lines = []
    for i, row in df.iterrows():
        metric_val = str(row[col]).strip()

        is_new_metric = i > 0 and metric_val != "" and not metric_val.startswith("\\phantom")
        
        if is_new_metric:
            lines.append("\\midrule")
        
        formatted_row = [cell if str(cell).strip() != "" else "\\phantom" for cell in row]
        line = " & ".join(str(x) for x in formatted_row) + " \\\\"
        lines.append(line)

    return "\n".join(lines)


for dataset, df in group_by_dataset.items():
    d_table: str = ""
    del df['dataset']
   
    df['metric'] = replace_but_first_with_phantom(
        df['metric']
    ).apply(lambda x : find_metric_label(x))

    new_cols = {
        k: (v if (v := find_col_label(k)) is not None else k.capitalize())
        for k in df.columns
    }

    df.rename(columns=new_cols, inplace=True)

    """
    insert_midrule_before = df['Metric'].shift(-1).fillna("").apply(lambda x: x != "" and not x.startswith("\\phantom"))

    latex_rows = []
    for i, row in df.iterrows():
        line = " & ".join(str(x) if x != "" else "\\phantom" for x in row) + " \\\\"
        latex_rows.append(line)
        if i + 1 < len(df) and insert_midrule_before.iloc[i]:
            latex_rows.append("\\midrule")
    """

    latex_table = (
        f"\\begin{{table{'*' if not full_table else ''}}}[{'H' if full_table else 'ht'}]\n"
        "\\centering\n"
        f"\\caption*{{{find_dataset_label(dataset)} dataset}}\n"
        f"\\begin{{tabular}}{{{'llllllrlr' if full_table else 'llllrlr'}}}\n"
        "\\toprule\n"
        + " & ".join(list(df.columns)) + "\\\\\n"
        + apply_midrule(df) + "\n"
        "\\bottomrule\n"
        "\\end{tabular}\n"
        f"\\label{{tab:RQ{RQ}_posthoc{'_full' if full_table else ''}}}\n"
        f"\\end{{table{'*' if not full_table else ''}}}\n"
    )

    # caption=f"Post-hoc pairwise comparison and effect size on {}"
    with open(f"tables/posthoc/RQ{RQ}/{'full/' if full_table else ''}{dataset}.tex", 'w') as f:
       f.write(latex_table)
    

    """
    group_by_metric = {
        metric: group for metric, group in df.groupby('metric')
    }
    for metric, _df in group_by_metric.items():
        del _df['dataset']
        del _df['metric']

        new_cols = {
            k: (v if (v := find_col_label(k)) is not None else k.capitalize())
            for k in _df.columns
        }

        _df.rename(columns=new_cols, inplace=True)

        raw_table = _df.to_latex(
            index=False,
            escape=False,
            column_format='llllllrlr' if full_table else 'llllrlr',
            # FIXME: use fixed column widths
        )
        table: str = (
            "\\begin{subtable}{\\columnwidth}\n"
            "\\centering"
            + raw_table.replace("\\begin{table}", "").replace("\\end{table}", "") +
            "\\vspace{0.2em}"
            f"\\caption{{{find_metric_label(metric)}}}\n"
            "\\end{subtable}\n"
        )

        d_table += table


final_table: str = (
    # "".join(colors) + "\n" +
    f"\\begin{{table}}[{'H' if full_table else 'ht'}]\n"
    "\\centering\n"
    f"\\caption*{{{find_dataset_label(dataset)} dataset}}\n"
    + d_table +
    f"\\label{{tab:RQ{RQ}_posthoc{'_full' if full_table else ''}}}\n"
    "\\end{table}\n"
)

# caption=f"Post-hoc pairwise comparison and effect size on {}"

with open(f"tables/posthoc/RQ{RQ}/{'full_' if full_table else ''}{dataset}.tex", 'w') as f:
   f.write(final_table)

    """
