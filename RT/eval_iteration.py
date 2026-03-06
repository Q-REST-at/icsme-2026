"""
Evaluates the performance of different runs by checking the out/
folder.

Uses the format `out/{session}/{date}/{time}/{iteration}/res.json`, 
which is the output from `send_data.py`.
The evaluation requires the files specified by the responses'
metadata.

Copyright:
----------
(c) 2024 Anonymous software testing consultancy company

License:
--------
MIT (see LICENSE for more information)
"""

import csv
import datetime
import json
import os
from contextlib import redirect_stdout
from typing import Any
from platform import system

from .core.rest import RESTSpecification
from .core.stats import Stats

from dotenv import load_dotenv
load_dotenv()

# Get the system/OS name
current_environment = system()

# Reads the env var as a string; defaults to "0" if not set
USE_LOG = os.getenv("USE_LOG", "0") == "1"

now: datetime.datetime = datetime.datetime.now()

date_str: str = str(now.date())
time_str: str = str(now.time())

log_path: str = f"./res/{date_str}/{time_str}/eval.log" # Note: path to stdout redirect log (!log per treatment)

# Data cache for easy access
req_data: dict[str, set[str]] = {}
test_data: dict[str, set[str]] = {}
mapping_data: dict[str, dict[str, set[str]]] = {}


def get_specs(req_path: str, test_path: str, mapping_path: str) -> tuple[
        set[str],
        set[str],
        dict[str, set[str]]
    ]:
    # Try to find cached data
    reqs: set[str] | None = req_data.get(req_path, None)
    tests: set[str] | None = test_data.get(test_path, None)
    mapping: dict[str, set[str]] | None = mapping_data.get(mapping_path, None)

    # Load if any of them are missing
    if None in (reqs, tests, mapping):
        print(f"Info - \tLoading {req_path}")
        print(f"Info - \tLoading {test_path}")
        print(f"Info - \tLoading {mapping_path}")

        specs = RESTSpecification.load_specs(
            req_path, test_path
        )

        map_: dict[str, set[str]]
        with open(mapping_path, "r") as f:
            fields: list[str] = [
                "Req ID",
                "Test ID"
            ]
            reader: csv.DictReader = csv.DictReader(f)

            # {"Req ID": <Req ID>, "Test IDs": <Test IDs>} for each row
            tmp: list[dict[str, str | list[str]]] = [
                {k: row[k] for k in row.keys() if k in fields}
                for row in reader
            ]

            for e in tmp:
                e["Test ID"] = e["Test ID"].replace(" ", "").split(",") if e["Test ID"] else []

            map_ = {
                e["Req ID"]: (set(e["Test ID"]) if e["Test ID"] else set())
                for e in tmp
            }

        req_data[req_path] = reqs = reqs or specs.req_ids
        test_data[test_path] = tests = tests or specs.test_ids
        mapping_data[mapping_path] = mapping = mapping or map_

    return reqs, tests, mapping


def main() -> None:
    # Evaluate results of every output
    # Note: each outermost directory name is composed of: treatment + dataset.
    # However, for simplicity we simply call the variable here "treatment".
    for treatment in os.listdir(f"./out"):
        # Skip current iteration if we encountered a file
        if not os.path.isdir(f"./out/{treatment}"): 
            print(f"{treatment} is not a directory - skipping...")
            continue

        # Output directory filepath
        res_dir: str = f"./res/{date_str}/{time_str}/{treatment}"
        # Replace ":" in Windows environement to avoid crashes due to illegal filename characters
        if current_environment == "Windows": res_dir = res_dir.replace(":", "-")

        # Create current "session" res directory
        os.makedirs(res_dir, exist_ok=True) 

        # Model stats
        all_n: list[int] = []
        all_tp: list[int] = []
        all_tn: list[int] = []
        all_fp: list[int] = []
        all_fn: list[int] = []

        all_accuracy: list[float] = []
        all_recall: list[float] = []
        all_precision: list[float] = []
        all_specificity: list[float] = []
        all_balanced_accuracy: list[float] = []
        all_f1: list[float] = []

        all_err: list[int] = []

        all_time_to_analyze: list[float] = []

        # GPU utilization mean and max
        all_gpu_util_mean: list[float] = []
        all_gpu_util_max: list[float] = []

        # VRAM utilization mean and max
        all_vram_util_mean: list[float] = []
        all_vram_util_max: list[float] = []

        # VRAM maximum memory usage
        all_vram_max_usage_MiB: list[float] = []

        json_list = []

        # Frequency table of predicted true links split into true and false
        # Accumulates the links over all runs in a session
        frequency_table: dict[bool, dict[str, dict[str, int]]] = {True: {}, False: {}}


        for d in os.listdir(f"./out/{treatment}"):
            for t in os.listdir(f"./out/{treatment}/{d}"):
                for iteration in os.listdir(f"./out/{treatment}/{d}/{t}"):
                    current_dir = f"./out/{treatment}/{d}/{t}/{iteration}"

                    out_path: str = f"{current_dir}/res.json"
                    print(f"Info - Evaluating {out_path}")

                    # Load the tool output
                    payload: dict[str, dict]
                    with open(out_path, "r") as f:
                        payload = json.load(f)

                    meta: dict[str, str] = payload["meta"]

                    # Each key is a requirement ID
                    res: dict[str, list[str]] = payload["data"]["links"]
                    err: dict[str, list[str]] = payload["data"]["err"]

                    time_to_analyze: float = payload["data"]["time_to_analyze"]
                    
                    # GPU and VRAM metrics are single nested dictionaries
                    # GPU and VRAM can be null
                    gpu: dict[str, Any] | None = payload.get("data", {}).get("GPU")
                    vram: dict[str, Any] | None = payload.get("data", {}).get("VRAM")

                    curr_tests: set[str]
                    curr_mapping: dict[str, set[str]]

                    _, curr_tests, curr_mapping = get_specs(
                        meta["req_path"],
                        meta["test_path"],
                        meta["mapping_path"]
                    )
                    print("Info - Current tests:")
                    print(json.dumps(list(curr_tests), indent=2).replace("\n", "\nInfo - \t"))
                    print("\n")

                    # Values for confusion matrix
                    n: int = 0
                    tp: int = 0
                    tn: int = 0
                    fp: int = 0
                    fn: int = 0
                    
                    for req in res:
                        actual_tests: set[str] = set(res[req])

                        expected_tests: set[str] = curr_mapping.get(req, None)
                        # Skip if req ID returned None
                        if expected_tests is None:
                            print(f"Error - {current_dir}: Faulty requirement ID ({req})")
                            continue

                        print(f"Info - {current_dir}: {req}:")

                        # Positives
                        curr_tp_set: set[str] = actual_tests & expected_tests
                        curr_tp_count: int = len(curr_tp_set)
                        print(f"Info - \t\t({curr_tp_count}) {curr_tp_set = }")

                        curr_fp_set: set[str] = actual_tests - expected_tests
                        curr_fp_count: int = len(curr_fp_set)
                        print(f"Info - \t\t({curr_fp_count}) {curr_fp_set = }")
                        
                        # Negatives
                        expected_ns: set[str] = curr_tests - expected_tests
                        actual_ns: set[str] = curr_tests - actual_tests

                        curr_tn_set: set[str] = actual_ns & expected_ns
                        curr_tn_count: int = len(curr_tn_set)
                        print(f"Info - \t\t({curr_tn_count}) {curr_tn_set = }")

                        curr_fn_set: set[str] = actual_ns - expected_ns
                        curr_fn_count: int = len(curr_fn_set)
                        print(f"Info - \t\t({curr_fn_count}) {curr_fn_set = }")

                        curr_n: int = curr_tp_count + curr_fp_count + curr_tn_count + curr_fn_count
                        
                        # Check so only the right amount of trace links were detected
                        expected_curr_n: int = len(curr_tests)
                        if curr_n != expected_curr_n:
                            print(f"Error - \t\tExpected curr_n = {expected_curr_n}, got {curr_n = }")
                        else:
                            print(f"Info - \t\t{curr_n = }")

                        # Update the frequency table

                        # Get the true positives
                        true_positives: dict[str, int] = frequency_table[True].get(req, None)
                        # Assign a dict if one doesn't exist
                        if true_positives is None:
                            true_positives = {}
                            frequency_table[True][req] = true_positives
                        
                        # Get the false positives
                        false_positives: dict[str, int] = frequency_table[False].get(req, None)
                        # Assign a dict if one doesn't exist
                        if false_positives is None:
                            false_positives = {}
                            frequency_table[False][req] = false_positives

                        # Add 1 for each true positive link
                        for test in curr_tp_set:
                            true_positives[test] = true_positives.get(test, 0) + 1

                        # Add 1 for each false positive link
                        for test in curr_fp_set:
                            false_positives[test] = false_positives.get(test, 0) + 1

                        n += curr_n
                        tp += curr_tp_count
                        tn += curr_tn_count
                        fp += curr_fp_count
                        fn += curr_fn_count

                    all_n.append(n)
                    all_tp.append(tp)
                    all_tn.append(tn)
                    all_fp.append(fp)
                    all_fn.append(fn)
                    
                    accuracy: float = (tp + tn) / n if n != 0 else 0.0
                    recall: float = tp / (tp + fn) if tp + fn != 0 else 0.0
                    precision: float = tp / (tp + fp) if tp + fp != 0 else 0.0
                    specificity: float = tn / (tn + fn) if tn + fn != 0 else 0.0
                    balanced_accuracy: float = (precision + specificity) / 2
                    f1: float = 2 * (recall * precision) / (recall + precision) if recall + precision != 0 else 0.0

                    all_accuracy.append(accuracy)
                    all_recall.append(recall)
                    all_precision.append(precision)
                    all_specificity.append(specificity)
                    all_balanced_accuracy.append(balanced_accuracy)
                    all_f1.append(f1)

                    all_err.append(len(err))

                    all_time_to_analyze.append(time_to_analyze)
                    
                    # Append only if GPU and VRAM are not None
                    if gpu is not None and vram is not None:
                        all_gpu_util_mean.append(gpu["utilization"].get("avg"))
                        all_gpu_util_max.append(gpu["utilization"].get("max"))

                        all_vram_util_mean.append(vram["utilization"]["avg"])
                        all_vram_util_max.append(vram["utilization"]["max"])

                        all_vram_max_usage_MiB.append(vram["max_usage_MiB"])

                    prevalence: float = (tp + fn) / n

                    eval_path = f"{current_dir}/eval.json"
                    data: dict = {
                        "prevalence": prevalence,
                        "n": n,
                        "tp": tp,
                        "tn": tn,
                        "fp": fp,
                        "fn": fn,
                        "accuracy": accuracy,
                        "balanced_accuracy": balanced_accuracy,
                        "f1": f1,
                        "recall": recall,
                        "precision": precision,
                        "specificity": specificity,
                        "err": len(err),
                        "time_to_analyze": time_to_analyze,
                    }
                    if gpu is not None:
                        data["GPU"] = gpu
                    if vram is not None:
                        data["VRAM"] = vram

                    with open(eval_path, "w+") as f:
                        json.dump(data, f, indent=2)

                    # Write current session log file
                    with open(f"{res_dir}/res.log", "a+") as f:
                        f.write(f"{current_dir}\n")
                        json.dump(data, f, indent=2)
                        f.write("\n")

                    data_json: dict = {
                        "data_path": f"{current_dir}",
                        "prevalence": prevalence,
                        "n": n,
                        "tp": tp,
                        "tn": tn,
                        "fp": fp,
                        "fn": fn,
                        "accuracy": accuracy,
                        "balanced_accuracy": balanced_accuracy,
                        "f1": f1,
                        "recall": recall,
                        "precision": precision,
                        "specificity": specificity,
                        "err": len(err),
                        "time_to_analyze": time_to_analyze,
                    }
                    if gpu is not None:
                        data_json["GPU"] = gpu
                    if vram is not None:
                        data_json["VRAM"] = vram

                    json_list.append(data_json)
                
            res_path_json: str = f"{res_dir}/all_data_{treatment}.json"

            # Write the list of dictionaries to a JSON file
            with open(res_path_json, 'w') as file:
                json.dump(json_list, file, indent=2)  # 'indent=4' for pretty printing
                     

        prevalence: float = (sum(all_tp) + sum(all_fn)) / sum(all_n)

        data: dict = {
            "prevalence": prevalence,
            "all_n": Stats("all_n", all_n).as_dict,
            "all_tp": Stats("all_tp", all_tp).as_dict,
            "all_tn": Stats("all_tn", all_tn).as_dict,
            "all_fp": Stats("all_fp", all_fp).as_dict,
            "all_fn": Stats("all_fn", all_fn).as_dict,
            "all_accuracy": Stats("all_accuracy", all_accuracy).as_dict,
            "all_balanced_accuracy": Stats("all_balanced_accuracy", all_balanced_accuracy).as_dict,
            "all_f1": Stats("all_f1", all_f1).as_dict,
            "all_recall": Stats("all_recall", all_recall).as_dict,
            "all_precision": Stats("all_precision", all_precision).as_dict,
            "all_specificity": Stats("all_specificity", all_specificity).as_dict,
            "frequency_table": frequency_table,
            "all_err": Stats("all_err", all_err).as_dict,
            "all_time_to_analyze": Stats("all_time_to_analyze", all_time_to_analyze).as_dict,
        }

        # Additional error checking - including only if GPU and VRAM data is present
        if all_gpu_util_mean:
            data["all_gpu_util_mean"] = Stats("all_gpu_util_mean", all_gpu_util_mean).as_dict
        if all_gpu_util_max:
            data["all_gpu_util_max"] = Stats("all_gpu_util_max", all_gpu_util_max).as_dict
        if all_vram_util_mean:
            data["all_vram_util_mean"] = Stats("all_vram_util_mean", all_vram_util_mean).as_dict
        if all_vram_util_max:
            data["all_vram_util_max"] = Stats("all_vram_util_max", all_vram_util_max).as_dict
        if all_vram_max_usage_MiB:
            data["all_vram_max_usage_MiB"] = Stats("all_vram_max_usage_MiB", all_vram_max_usage_MiB).as_dict


        print(f"Info - Logging total and average metrics for {treatment}")
        with open(f"{res_dir}/{treatment}.json", "w") as f:
            f.write(json.dumps(data, indent=2) + "\n")



if __name__ == "__main__":
    # Redirect stdout to a log file only if .env flag is set
    if USE_LOG:
        with open(log_path, "a+") as out, redirect_stdout(out):
            main()
    else:
        main()
