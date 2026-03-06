# TODO
# - consider filtering blank entries in the logs. This has a negative impact on
# the mean, etc. There's always some overhead when using utils like these.
import pandas as pd
from json import dumps
from os import PathLike
from typing import Final
import matplotlib.pyplot as plt
from scipy.signal import find_peaks

ProfileDict = dict[str, dict[str, dict[str, float] | float | int]]
ProfileResponse = None | str | ProfileDict


class GPUProfiler:
    """
    A minimalistic abstraction of a GPU 'profiler' used to perform calculations
    on gathered GPU profile logs based on querying the `nvidia-smi` utility. It
    allows for reading profile logs from multiple GPU instances (WIP).

    Optionally, the profile may be visualized onto a figure.
    """

    __slots__ = "path", "interval", "gpu_count", "df"

    def __init__(self,
                 path      : PathLike | str | None = None,
                 interval  : float                 = 1   ,
                 gpu_count : int                   = 1   ,
                 ) -> None:
        """
        Initializes a GPUProfiler object. By default, an empty DataFrame is
        created with the default columns. Immediately, we attempt to populate
        the DataFrame with some profile data which will overwrite the empty
        state upon success.

        Parameters:
        -----------
          path      : a path to a selected CSV profile file.
          interval  : an interval between samples (default: 1s).
          gpu_count : number of GPUs active during monitor (default: 1).
        """
        self.path      = path
        self.interval  = interval
        self.gpu_count = gpu_count # TODO: not used!
        
        # Empty df, just columns to prevent indexing errors
        self.df: pd.DataFrame = pd.DataFrame(columns=[
            "timestamp",
            "gpu_uuid",
            "utilization.gpu",
            "utilization.memory",
            "memory.used",
            "temperature.gpu"
        ])

        self.load_to_memory()


    def load_to_memory(self) -> None:
        _df = self.read_csv()
        if _df is not None:
            self.df = _df
        else:
            print('Reading failed. Using an empty DataFrame.')


    def compute(self, jsonify = False) -> ProfileResponse:
        """
        Performs some elementary computations on the profile data.

        Parameters:
        -----------
        jsonify : whether to turn the dictionary into a JSON-like instance.

        Returns:
        --------
        A `ProfileResponse` is either (i) a `ProfileDict`, a Python `dict` with
        GPU/vRAM metrics or (ii) the very same `dict` but JSON-ified.
        """
        df = self.df

        result: ProfileDict = {
            "GPU": {
                "utilization": {
                    "avg": float(df["utilization.gpu"].mean()),
                    "std": float(df["utilization.gpu"].std()),
                    "max": float(df["utilization.gpu"].max())
                },
                "avg_temperature": float(df["temperature.gpu"].mean())
            },
            "VRAM": {
                "max_usage_MiB": float(df["memory.used"].max()),
                "utilization": {
                    "avg": float(df["utilization.memory"].mean()),
                    "std": float(df["utilization.memory"].std()),
                    "max": float(df["utilization.memory"].max())
                }
            }
        }

        if jsonify:
            return dumps(result, indent=4)
        else:
            return result


    def read_csv(self, filter_inactive: bool = True) -> pd.DataFrame | None:
        """
        A helper function that reads the selected profile CSV file into memory
        and converts columns to desired data types.

        Parameters:
        -----------
        filter_inactive : discard rows where GPU and vRAM utilization are zero
                          and allocated vRAM > 1 MiB.

        Returns:
        --------
        A DataFrame if the read and conversion were successful. Otherwise, None.
        """
        try:
            df: pd.DataFrame = pd.read_csv(self.path)
        except Exception:
            return None
        
        for col in [
            "utilization.gpu",
            "utilization.memory",
            # add more if needed
        ]:
            df[col] = df[col].str.replace(" %", "", regex=False)

        df["memory.used"] = df["memory.used"].str.\
                replace(" MiB", "", regex=False)

        # Cols to convert to numeric datatype
        cols_to_convert_numeric: Final[list[str]] = [
            "utilization.gpu",
            "utilization.memory",
            "memory.used", 
            "temperature.gpu"
        ]

        df[cols_to_convert_numeric] = df[cols_to_convert_numeric].\
                apply(pd.to_numeric, errors="coerce")

        df = df.sort_values("timestamp").reset_index(drop=True)

        if filter_inactive:
            df_filtered = df[
                (df["utilization.gpu"] > 0)    &
                (df["utilization.memory"] > 0) &
                (df["memory.used"] > 1)
            ]

            return df_filtered

        # TODO: Are we interested in average deltas (diff) for either
        # utilization? The problem becomes that deltas are either +/- because
        # values can increase/decrease, so making sense of this data without
        # any processing is unsure.

        # This is left for reference.
        # 
        # df["gpu_util_rate"]    = df["utilization.gpu"].diff() / self.interval
        # df["memory_util_rate"] = df["utilization.memory"].diff() / self.interval

        return df


    def get_peaks(self) -> tuple[list[int], list[int]]:
        """
        Returns:
        --------
        A tuple of peaks (i) of GPU utilization and (ii) vRAM utilization. A
        'peak' is simply a one-dimensional array with indices of sample data
        points that are (local) peaks.
        """
        cols: Final[list[str]] = ["utilization.gpu", "utilization.memory"]
        return tuple(
                find_peaks(self.df[col].fillna(0))[0] # get 1st param
                for col in cols
        )


    def visualize(self) -> None:
        """
        This function visualizes the GPU (vRAM) utilization over the samples.
        Both figures are displayed onto a single combined figure. All local
        peaks are labeled with a red color.
        """
        df = self.df

        peaks_gpu, peaks_memory = self.get_peaks()

        fig, axes = plt.subplots(2, 1, figsize=(14, 10), sharex=True)
        fig.suptitle(self.path, fontsize=16)

        axes[0].plot(df.index, df["utilization.gpu"], marker="o", label="GPU Utilization (%)", zorder=1)
        axes[0].scatter(
            df.index[peaks_gpu],
            df["utilization.gpu"].iloc[peaks_gpu],
            color="red",
            s=80,
            label="Peaks",
            zorder=2
        )
        axes[0].set_title("GPU Utilization Over Samples")
        axes[0].set_ylabel("Utilization (%)")
        axes[0].legend()
        axes[0].grid(True)

        axes[1].plot(
            df.index, df["utilization.memory"],
            marker="o", label="GPU Memory Utilization (%)",
            color="tab:purple", zorder=1
        )
        axes[1].scatter(
            df.index[peaks_memory],
            df["utilization.memory"].iloc[peaks_memory],
            color="red", s=80, label="Peaks", zorder=2
        )
        axes[1].set_title("GPU Memory Utilization Over Samples")
        axes[1].set_xlabel("Sample Index")
        axes[1].set_ylabel("Utilization (%)")
        axes[1].legend()
        axes[1].grid(True)

        plt.tight_layout()
        plt.show()
