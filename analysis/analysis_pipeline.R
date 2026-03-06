#install.packages("tidyverse")
#install.packages("rstatix")
#install.packages("coin") # Used internally by rstatix's Wilcox_effsize()
#install.packages("rcompanion") # has implementations for the Vargha-Delaney A12 measure.
library(tidyverse)
library(rstatix)
library(rcompanion)


options(scipen = 50) # Show decimals instead of scientific notation (RStudio)


#=================================== USAGE ====================================#

# This R script performs a full statistical analysis on the desired input data.

# The analysis includes: 
#   - Friedman NHST (non-parametric NHST for repeated measures)
#   - Post-hoc pairwise Wilcoxon signed-rank test (paired)
#     - with Holm-Bonferroni correction for multiple testing
#   - Custom Paired VDA implementation for effect size estimation

# Simply set "USE_RQ1" flag to TRUE/FALSE for the desired analysis and the
# pipeline will handle the execution automatically.

# The script filters out treatments with no variance and blocked groups with 
# fewer than 2 members, as these are not suitable for pairwise post-hoc analysis.

# The results are written to file using the corresponding prefix: "rq1" | "rq2". 
# However, changing destination output and file name requires manual changes
# in the section "OUTPUT RESULTS" close to the bottom.


# Note: there is a deprecated Wilcoxon r effect size implementation at the
# bottom of the file. It currently does not execute when running.


#============================== SELECT WHICH RQ ===============================#

# TRUE  -> results for RQ1
# FALSE -> results for RQ2

USE_RQ1 = FALSE


#============================ LOAD EXPERIMENT DATA ============================#

# Load data for the correct RQ and set VDA flag (see effect size method)
if (USE_RQ1) {
  raw_df <- read.csv("./data/PT6_prompt/rq1_flat_df-PT6.csv")
} else {
  raw_df <- read.csv("./data/PT6_prompt/rq2_flat_df-PT6.csv")
}


#=============================== PRE-PROCESSING ===============================#

# Metrics to test
RQ1_METRICS <- c("balanced_accuracy", "recall", "precision", "f1")
RQ2_METRICS <- c("time_to_analyze", "vram_max_usage_mib")

# Set which RQ metrics to use
metrics <- if (USE_RQ1) RQ1_METRICS else RQ2_METRICS


# Expand the metrics columns to "true" long format
long_df <- raw_df %>%
  select(model, quantization, dataset, iteration, all_of(metrics)) %>%
  pivot_longer(cols = all_of(metrics), names_to = "metric", values_to = "value")

# Group by: model, dataset, metric
grouped_df <- long_df %>%
  group_by(model, dataset, metric) %>%
  nest() # puts the actual data inside a tibble for each row (group)



#=============================== FRIEDMAN TEST ================================#

# Wrapper function for Friedman test
# This lets us apply the function on the nested data
run_friedman <- function(df) {
  friedman_test(df, value ~ quantization | iteration)
}

# Apply test using the map function
friedman_results <- grouped_df %>%
  mutate(test_result = map(data, run_friedman)) %>%
  unnest(cols = test_result) %>% # this unpacks the test result tibble
  select(-.y., -method) %>% # remove redundant columns
  mutate(significant = p < 0.05)

# Filter the significant results
significant_results <- friedman_results %>%
  filter(p < 0.05)



#=================== FILTER NO-VARIANCE QUANTIZATION GROUPS ===================#

# Function to remove quantization groups with zero or NA variance
filter_variance <- function(df) {
  # Calculate variance per quantization group
  group_vars <- df %>%
    group_by(quantization) %>%
    summarize(var = var(value), .groups = "drop") %>%
    filter(!is.na(var) & var > 0)
  
  # Keep only groups with variance
  df %>% 
    filter(quantization %in% group_vars$quantization)
}

# Apply the filtering to each nested data frame
filtered_df <- grouped_df %>%
  mutate(data = map(data, filter_variance))

# Remove rows with not enough quantization groups left for pairwise comparison
filtered_df <- filtered_df %>%
  # n_distinct counts distinct quantization groups for each nested dataframe
  # map_lgl returns a vector of boolean values; filter rows using the vector
  filter(map_lgl(data, function(x) dplyr::n_distinct(x$quantization) >= 2))



#========================= POST-HOC PAIRWISE TESTING ==========================#

# Wrapper function for Pairwise Wilcox test
run_posthoc <- function(df) {
  pairwise_wilcox_test(
    df, 
    value ~ quantization,
    paired = TRUE,
    p.adjust.method = "holm")
}

# Guide--Interpreting adjusted P-value column:
# *** == Very strong evidence of difference
# **  == Strong evidence
# *   == Moderate evidence
# ns  == Not significant


# Version evaluating ALL pairs regardless of Friedman results
posthoc_results <- filtered_df %>%
  mutate(posthoc = map(data, run_posthoc))

# Version with filtering to only evaluate significant results
#posthoc_results <- filtered_df %>%
#  semi_join(significant_results, by = c("model", "dataset", "metric")) %>%
#  mutate(posthoc = map(data, run_posthoc))



#========================== EFFECT SIZE CALCULATION ===========================#

# Vargha, A. and H.D. Delaney. A Critique and Improvement of the CL Common Language Effect Size Statistics of
# McGraw and Wong. 2000. Journal of Educational and Behavioral Statistics 25(2):101–132.
# 
# Of course, these interpretations have no universal authority. They are just guidelines based on the judgement of 
# the authors, and are probably specific to field of study and specifics of the situation under study.
# 
# You might see the original paper for their discussion on the derivation of these guidelines.
# 
# Small : 0.56  – < 0.64 or > 0.34 – 0.44
# Medium: 0.64  – < 0.71 or > 0.29 – 0.34
# Large : ≥ 0.71 or ≤ 0.29

map_vda_effect <- function(vda_value) {
  if((0.56 <= vda_value & vda_value < 0.64) | (0.34 < vda_value & vda_value <= 0.44)) {
    effect <- "Small"
  } else if((0.64 <= vda_value & vda_value < 0.71) | (0.29 < vda_value & vda_value <= 0.34)) {
    effect <- "Medium"
  } else if(vda_value >= 0.71 | vda_value <= 0.29) {
    effect <- "Large"
  } else {
    effect <- "Negligible"
  }
}


# Custom paired VDA function (for within-subjects/repeated-measures design)
# (there are no existing paired implementations available in packages)
run_paired_vda <- function(df) {
  # Count the unique number of quantization groups
  q_groups <- unique(df$quantization)
  
  # If the row does not contain at least two quantization groups, we can't
  # perform any meaningful pairwise (effect size) analysis
  if (length(q_groups) < 2) { 
    return(tibble(
        group1 = NA, 
        group2 = NA, 
        vda = NA,
        magnitude = NA, 
        status = "skip")
      ) 
  }
  
  # Generate all unique pairwise combinations of the quantization levels (n choose 2)
  group_pairs <- combn(sort(q_groups), 2, simplify = FALSE)
  
  # Apply the VDA calculations to each unique pair
  map_dfr(group_pairs, function(pair) {
    df_pair <- df %>% filter(quantization %in% pair)
    
    # Extract values as vectors for each group
    values_group1 <- df_pair %>% filter(quantization == pair[1]) %>% pull(value)
    values_group2 <- df_pair %>% filter(quantization == pair[2]) %>% pull(value)
    
    # Ensure equal length 
    if (length(values_group1) != length(values_group2)) {
      stop("Unequal lengths for paired samples")
    }
    
    # Calculate the differences
    differences = values_group1 - values_group2
    
    # Count the number of positive, negative, and zero differences
    n <- length(differences)
    n_pos <- sum(differences > 0)   # Trials where group1 > group2
    n_neg <- sum(differences < 0)   # Trials where group1 < group2
    n_zero <- sum(differences == 0) # Trials where group1 == group2 (tie)
    
    # VDA formula:
    # A_paired = (#(A > B) + 0.5 * #(A < B)) / n
    # Where:
    #   A ~ Group A
    #   B ~ Group B
    #   n ~ number of paired comparisons
    
    # Compute A_paired (VDA for paired data)
    # Interpretation: probability that group1 outperforms group2
    # Ties are given half credit (0.5), as in rank-based methods
    A_paired <- (n_pos + 0.5 * n_zero) / n

    # Create result row as a tibble
    tibble(
      group1 = pair[1],
      group2 = pair[2],
      vda = A_paired,
      magnitude = map_vda_effect(A_paired), # Get magnitude label
      status = "ok"
    )
  })
}

# Apply the paired VDA effect size function to each nested dataframe
effsize_results <- posthoc_results %>%
  mutate(effsize = map(data, run_paired_vda))



#============================== COMBINE RESULTS ===============================#

# Combine posthoc and effect size nested data frames row-by-row
combined_results <- effsize_results %>%
  mutate(
    # Combine the posthoc and effsize nested data frames
    # The map2 function iterates over two arguments simultaneously
    analysis_results = map2(posthoc, effsize, function(post, eff) {
      # Join by group1/group2 (inner join keeps only matching comparisons)
      full_join(post, eff, by = c("group1", "group2")) %>%
        select(
          group1, group2,
          n1, n2, statistic, p, p.adj, p.adj.signif,
          vda, magnitude, status
        )
    })
  ) %>%
  select(-posthoc, -effsize)  # Drop the old nested columns



#============================== OUTPUT RESULTS ================================#

# Remove the nested data before flattening
summary_results <- combined_results %>%
  select(-data) %>%
  unnest(analysis_results)

rq_label <- if (USE_RQ1) "rq1" else "rq2"
file_path <- paste0("results/PT6/", rq_label, "_post-hoc_results-PT6.csv")

write_csv(summary_results, file_path)
