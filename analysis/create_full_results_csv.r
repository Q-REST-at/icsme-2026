#install.packages("tidyverse")
library(tidyverse)

options(scipen = 50) # Show decimals instead of scientific notation (RStudio)


#============================ LOAD EXPERIMENT DATA ============================#

rq1_llm_df <- read.csv("./data/PT6_prompt/rq1_flat_df-PT6.csv")
rq2_llm_df <- read.csv("./data/PT6_prompt/rq2_flat_df-PT6.csv")


#=============================== PRE-PROCESSING ===============================#

RQ1_METRICS <- c("balanced_accuracy", "recall", "precision", "f1")
RQ2_METRICS <- c("time_to_analyze", "vram_max_usage_mib")
ALL_METRICS <- c(RQ1_METRICS, RQ2_METRICS)

# Clean dataframe
rq2_llm_df <- rq2_llm_df %>%
  select(model, quantization, dataset, iteration, all_of(RQ2_METRICS))

# Extract shared columns
shared_cols <- intersect(names(rq1_llm_df), names(rq2_llm_df))

# Full join the two dataframes
full_llm_df <- full_join(rq1_llm_df, rq2_llm_df, by=c(shared_cols))

# Sort the table
full_df <- arrange(full_llm_df, across(1:3))


# Expand the metrics columns to "true" long format
full_long_df <- full_df %>%
  select(model, quantization, dataset, iteration, all_of(ALL_METRICS)) %>%
  pivot_longer(cols = all_of(ALL_METRICS), names_to = "metric", values_to = "value") %>%
  # Rename columns to a more human-readable format
  # "." is a placeholder for the value being piped, which is needed since we 
  # don't pass it as the first argument to "gsub" (default pipe behaviour)
  mutate(metric = metric %>% 
           gsub("_", " ", .) %>%
           tools::toTitleCase()) %>% 
  # Essentially a ternary: ifelse(test_condition, value_if_true, value_if_false)
  mutate(metric = ifelse(metric == "Vram Max Usage Mib", "VRAM Max Usage MiB", metric))


#============================== OUTPUT RESULTS ================================#

# Group by: quantization, dataset, metric
full_summary_df <- full_long_df %>%
  select(-model) %>% # drop the model column, we only have one in the experiment
  group_by(quantization, dataset, metric) %>%
  summarise(Mean = mean(value), SD = sd(value))

write_csv(full_summary_df, "results/full_summary_table.csv")
