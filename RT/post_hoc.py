import pandas as pd

# Load the CSV file
file_path = "analysis/results/PT6/rq1_post-hoc_results-PT6.csv"
# file_path = "analysis/results/PT6/rq2_post-hoc_results-PT6.csv"
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

def find_metric_label(x: str) -> str:
    l: str | None = REMAP_METRIC[x]
    return x.capitalize() if l is None else l


def find_col_label(x: str) -> str | None:
    for name, _, label in TABLE:
        if x == name:
            return label
    return None

full_table: bool = False

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

group_by_metric = {
    metric: group for metric, group in df_filtered.groupby('metric')
}

for metric, df in group_by_metric.items():
    new_cols = {
        k: (v if (v := find_col_label(k)) is not None else k.capitalize())
        for k in df.columns
    }

    df.rename(columns=new_cols, inplace=True)

    del df['Metric']
    latex_table = df.to_latex(
        index=False,
        escape=False,
        column_format='llllllrlr' if full_table else 'llllrlr',
        caption=f"Post-hoc pairwise comparison and effect size on {find_metric_label(str(metric))}"
    )

    with open(f"tables/{'full_' if full_table else ''}{metric}.tex", 'w') as f:
       f.write(latex_table)
