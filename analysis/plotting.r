#install.packages("tidyverse")
#install.packages("rstatix")
#install.packages("patchwork")
#install.packages("ggbreak")

library(tidyverse)
library(rstatix)
library(patchwork)
library(ggbreak)

options(scipen = 50) # Show decimals instead of scientific notation (RStudio)

CUSTOM_PALLETE = c("GPTQ" = "#A97FED",  
                   "AWQ" = "#24ECDE", "AQLM"="#34D773", 
                   "NONE"="#2A503B")
#34D773 - Emerald  
#24ECDE - Turquoise  
#A97FED - Tropical Indigo  
#2A503B - Brunswick Green  
#D4C4EA - Thistle


#============================== SELECT WHICH RQ ===============================#

# USE_RQ1 == TRUE   -> output RQ1 tables
# USE_RQ1 == FALSE  -> output RQ2 tables

USE_RQ1 = FALSE


#============================ LOAD EXPERIMENT DATA ============================#

# Load data
if (USE_RQ1) {
  raw_df <- read.csv("./data/PT6_prompt/rq1_flat_df-PT6.csv")

} else {
  raw_df <- read.csv("./data/PT6_prompt/rq2_flat_df-PT6.csv")
}


#=============================== PRE-PROCESSING ===============================#

# Metrics for each RQ
RQ1_METRICS <- c("balanced_accuracy", "recall", "precision", "f1")
RQ2_METRICS <- c("time_to_analyze", "vram_max_usage_mib")

# Set which metrics to use
metrics <- if (USE_RQ1) RQ1_METRICS else RQ2_METRICS

# Expand the metrics columns to "true" long format
long_df <- raw_df %>%
  select(model, quantization, dataset, iteration, all_of(metrics)) %>%
  #filter(dataset == "BTHS") %>% # filter for specific datasets
  pivot_longer(cols = all_of(metrics), names_to = "metric", values_to = "value") %>%
  # Rename columns to a more human-readable format
  # "." is a placeholder for the value being piped, which is needed since we 
  # don't pass it as the first argument to "gsub" (default pipe behaviour)
  mutate(metric = metric %>% 
           gsub("_", " ", .) %>%
           tools::toTitleCase()) %>% 
  # Essentially a ternary: ifelse(test_condition, value_if_true, value_if_false)
  mutate(metric = ifelse(metric == "Vram Max Usage Mib", "VRAM Max Usage MiB", metric))
  #mutate(dataset = ifelse(dataset == "HW", "HEALTHWATCHER", dataset))
  
# Group by: quantization, dataset, metric
summary_df <- long_df %>%
  select(-model) %>% # drop the model column, we only have one in the experiment
  group_by(quantization, dataset, metric) %>%
  summarise(Mean = mean(value), Median = median(value), SD = sd(value),
            YMin = Mean - SD, YMax = Mean + SD)

summary_df$quantization <- factor(summary_df$quantization, levels = c("AQLM", "AWQ", "GPTQ", "NONE"))


#================================ PLOTTING RQ1 ================================#

if (USE_RQ1) {
  
  #---------------------------------- BAR PLOT ---------------------------------#
  # Bar chart for easy to understand overview of all relevant information
  rq1_bar_plot <- ggplot(summary_df, aes(x = quantization, y = Median, fill = quantization, group = metric)) +
    geom_col(width = 0.5) + 
    geom_errorbar(aes(ymin = YMin, ymax = YMax), alpha = 0.8, width = 0.5) +
    scale_y_continuous(limits = c(0,1), breaks = seq(0,1,by=0.1)) +
    facet_grid(vars(metric), vars(dataset), scales = "free") +
    scale_fill_manual(values = CUSTOM_PALLETE) +
    labs(title = NULL, x = NULL, fill = "Quantization:") +
    theme_bw() + theme(legend.position = "bottom", axis.text.x = element_text(angle = 90))
  
  ggsave(rq1_bar_plot, filename = "results/RQ1 Bar Plot.pdf", width = 24, height = 20, units = "cm", device = cairo_pdf())
  dev.off()
  
  #---------------------------------- Box PLOT ---------------------------------#
  # Box plot to show variance + outliers
  rq1_box_plot <- ggplot(long_df, aes(x = quantization, y = value, fill = quantization)) +
    geom_boxplot(alpha = 0.8, width = 0.5) +
    geom_jitter(width = 0.15, alpha = 0.4, size = 1) +
    scale_y_continuous(limits = c(0,1), breaks = seq(0,1,by=0.1)) + 
    facet_grid(vars(metric), vars(dataset), scales = "free") +  # full grid with all datasets
    #facet_wrap(vars(metric), ncol = 2, scales = "free") + # 2x2 grid for just one dataset
    scale_fill_manual(values = CUSTOM_PALLETE) +
    labs(title = NULL, x = NULL, y = NULL, fill = "Quantization:") +
    theme_bw() +
    theme_bw() + theme(legend.position = "bottom", axis.text.x = element_text(angle = 90))
  
  # 2x2 grid: width = 15, height = 15
  # full grid: width = 24, height = 20
  ggsave(rq1_box_plot, filename = "results/RQ1 Box Plot.pdf", width = 24, height = 20, units = "cm", device = cairo_pdf())
  dev.off()
  
  
    
#================================ PLOTTING RQ2 ================================#
  
} else {
  
  #---------------------------------- BAR PLOT ---------------------------------#
  #Split data so we can define ranges and breaks separately
  bar_vram_data <- summary_df %>% filter(metric == "VRAM Max Usage MiB")
  bar_time_data <- summary_df %>% filter(metric == "Time to Analyze")
  
  # Cap the YMin values as 0 (can't have negative time)
  bar_time_data <- bar_time_data %>%
    mutate(YMin = pmax(YMin, 0))
  
  # Plot 1: VRAM
  bar_vram <- ggplot(bar_vram_data, aes(x = quantization, y = Median, fill = quantization)) +
    geom_col(width = 0.5) +
    geom_errorbar(aes(ymin = YMin, ymax = YMax), width = 0.5) +
    facet_grid(. ~ dataset) +
    scale_y_continuous(limits = c(0, 17000), breaks = seq(0, 17000, 2000)) +
    scale_fill_manual(values = CUSTOM_PALLETE) +
    labs(title = "VRAM Max Usage MiB", x = NULL, fill = "Quantization:") +
    theme_bw() + 
    theme(legend.position = "bottom", axis.text.x = element_text(angle = 90))
  
  # Plot 2: Time (with trimmed Y range)
  box_time <- ggplot(bar_time_data, aes(x = quantization, y = Median, fill = quantization)) +
    geom_col(width = 0.5) +
    geom_errorbar(aes(ymin = YMin, ymax = YMax), width = 0.5) +
    facet_grid(. ~ dataset) +
    scale_y_continuous(
      breaks = c(seq(0, 30, by = 5), seq(100, 700, by = 100)),
      limits = c(0, 700)  # Hard cap on top (we have an outlier in the 1000+)
    ) +
    scale_y_break(c(30, 100), scales = 0.5 ) +
    scale_fill_manual(values = CUSTOM_PALLETE) +
    labs(title = "Inference Time in Seconds", x = NULL, fill = "Quantization:") +
    theme_bw() +
    theme(
      legend.position = "none",
      axis.text.x = element_text(angle = 90),
      axis.text.y.right = element_blank(),
      axis.ticks.y.right = element_blank()
    )
  
  # Combine vertically (with relative height control)
  combined_rq2_bar_plot <- box_time / bar_vram +
    plot_layout(heights = c(1, 1.2)) +
    plot_annotation(
      theme = theme(
        plot.caption = element_text(hjust = 0.5, size = 12)
      )
    )
  
  ggsave(combined_rq2_bar_plot, filename = "results/RQ2 Bar Plot.pdf", width = 20, height = 20, units = "cm", device = cairo_pdf())
  dev.off()
  
  #---------------------------------- Box PLOT ---------------------------------#
  #Split data so we can define ranges and breaks separately
  box_vram_data <- long_df %>% filter(metric == "VRAM Max Usage MiB")
  box_time_data <- long_df %>% filter(metric == "Time to Analyze")
  
  # Plot 1: VRAM
  box_vram <- ggplot(box_vram_data, aes(x = quantization, y = value, fill = quantization)) +
    geom_boxplot(alpha = 0.8, width = 0.5) +
    geom_jitter(width = 0.15, alpha = 0.4, size = 0.5) +
    facet_grid(. ~ dataset) +
    scale_y_continuous(
      breaks = c(seq(3500, 7500, by = 1000), seq(15000, 17000, by = 1000)),
      limits = c(3500, 17000)
    ) +
    scale_y_break(c(7500, 15000), scales = 0.5 ) +
    scale_fill_manual(values = CUSTOM_PALLETE) +
    labs(title = "VRAM Max Usage MiB", 
         x = NULL, y = NULL, 
         fill = "Quantization:"
    ) +
    theme_bw() + 
    theme(legend.position = "bottom", axis.text.x = element_text(angle = 90),
          axis.text.y.right = element_blank(),  # Hide right y-axis labels
          axis.ticks.y.right = element_blank()   # Hide right y-axis ticks
    )
  
  
  # Plot 2: Time 
  box_time <- ggplot(box_time_data, aes(x = quantization, y = value, fill = quantization)) +
    geom_boxplot(alpha = 0.8, width = 0.5) +
    geom_jitter(width = 0.15, alpha = 0.4, size = 0.5) +
    facet_grid(. ~ dataset) +
    scale_y_continuous(
      breaks = c(seq(0, 40, by = 5), seq(100, 700, by = 100)),
      limits = c(0, 700)  # Hard cap on top (we have an outlier in the 1000+)
    ) +
    scale_y_break(c(40, 100), scales = 0.5 ) +
    scale_fill_manual(values = CUSTOM_PALLETE) +
    labs(title = "Inference Time in Seconds", x = NULL, y = NULL, fill = "Quantization:") +
    theme_bw() +
    theme(
      legend.position = "none",
      axis.text.x = element_text(angle = 90),
      axis.text.y.right = element_blank(),
      axis.ticks.y.right = element_blank()
    )
  
  # Combine vertically (with relative height control)
  combined_rq2_box_plot <- box_time / box_vram +
    plot_layout(heights = c(1, 1.2)) +
    plot_annotation(
      theme = theme(
        plot.caption = element_text(hjust = 0.5, size = 12)
      )
    )
  
  # full box: width = 18, height = 22
  # 2x2 box: width = 10, height = 20
  ggsave(combined_rq2_box_plot, filename = "results/RQ2 Box Plot.pdf", width = 18, height = 22, units = "cm", device = cairo_pdf())
  dev.off()
  
} # end of if-statement
