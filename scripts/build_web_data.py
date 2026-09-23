"""Export the eight published trajectories for the read-only web explorer.

Only the Python standard library is required. No model is solved, sampled,
interpolated, or extrapolated here. Run from any directory; --check verifies
that the generated file matches the validated sources without writing it.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = Path("docs/generated/simulations.json")
SIGMAS = (0.9, 1.0, 1.1, 1.5)
DESIGNS = ((7.5, "rsi_chi_7_5"), (1.5, "rsi_chi_1_5"))
RAW_BASE = "https://raw.githubusercontent.com/oliverpardo1979/ai-growth-and-labor/main/"


def field(key, label, definition, unit, *, axis_scale="linear"):
    return dict(key=key, label=label, definition=definition, unit=unit,
                display_scale=1 if unit == "final_good_per_ai_service" else 100,
                axis_scale=axis_scale)


FIELDS = [
    field("output_effective_labor_growth", "Output per unit of effective labor",
          "Instantaneous growth of Y/(AL): g_Y - n - gamma.", "instantaneous_percent_per_year"),
    field("ai_services_effective_labor_growth", "AI services per unit of effective labor",
          "Instantaneous growth of X/(AL): g_X - n - gamma.", "instantaneous_percent_per_year"),
    field("capital_effective_labor_growth", "Capital per unit of effective labor",
          "Instantaneous growth of K/(AL): g_K - n - gamma.", "instantaneous_percent_per_year"),
    field("output_per_person_growth", "Output-per-worker growth",
          "Instantaneous growth of Y/N: g_Y - n; L=N.", "instantaneous_percent_per_year"),
    field("wage_growth", "Real wage growth", "Instantaneous growth of w.",
          "instantaneous_percent_per_year"),
    field("net_interest", "Net real interest rate", "r; depreciation is already deducted.",
          "percent_per_year"),
    field("ai_service_price", "AI-service price", "p_X in final-good units per effective AI service.",
          "final_good_per_ai_service", axis_scale="log"),
    field("labor_income_share", "Labor income", "wL/Y; denominator is output.", "percent_of_output"),
    field("profit_output_share", "Developer net profit", "Pi/Y, after inference and research costs.",
          "percent_of_output"),
    field("inference_output_share", "Inference expenditure", "U/Y; denominator is output, not AI revenue.",
          "percent_of_output"),
    field("research_output_share", "Research expenditure", "M/Y at the sampled date, not an annual integral.",
          "percent_of_output"),
    field("capability_frontier_ratio", "AI efficiency relative to its upper bound", "B/Bbar.",
          "percent_of_upper_bound"),
    field("ai_revenue_output_share", "AI-industry revenue", "p_X X/Y = 1 - alpha - wL/Y.",
          "percent_of_output"),
]
FIELD_KEYS = tuple(item["key"] for item in FIELDS)


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def close(left, right):
    return math.isclose(left, right, rel_tol=0, abs_tol=2e-12)


def sigma_key(sigma):
    return "sigma_" + f"{sigma:.2f}".replace(".", "_")


def validate_csv_hash(digest, paths, figures, summary):
    require(digest == paths["csv_sha256"] == figures["data_sha256"] == summary["data_sha256"],
            "CSV hash does not match every publication manifest.")


def pre_event_values(pre, parameters, frontier):
    """Translate the saved analytical pre-RSI BGP, not post-event samples."""
    gamma = parameters["labor_productivity_growth"]
    result = {
        "output_effective_labor_growth": 0.0,
        "ai_services_effective_labor_growth": 0.0,
        "capital_effective_labor_growth": 0.0,
        "output_per_person_growth": gamma,
        "wage_growth": gamma,
        "net_interest": pre["interest_rate"],
        "ai_service_price": pre["ai_service_price"],
        "capability_frontier_ratio": pre["capability"] / frontier,
        "ai_revenue_output_share": 1 - parameters["alpha"] - pre["labor_income_share"],
    }
    for key in ("labor_income_share", "profit_output_share", "inference_output_share", "research_output_share"):
        result[key] = pre[key]
    require(close(result["ai_revenue_output_share"], pre["ai_revenue_output_share"]),
            "Pre-event AI revenue disagrees with the income identity.")
    require(pre["research_compute"] == result["research_output_share"] == 0,
            "Pre-event reference unexpectedly includes research.")
    return result


def load_dataset(root, chi, design):
    folder = root / "numerical_rewrite" / design
    names = ("scenario", "paths_manifest", "figure_manifest", "summary",
             "activation_audit", "pre_rsi_reference", "annual_moments")
    source = {name: load_json(folder / f"{name}.json") for name in names}
    spec, paths, figures = (source[name] for name in ("scenario", "paths_manifest", "figure_manifest"))
    summary, activation = source["summary"], source["activation_audit"]
    parameters = spec["parameters"]
    require(spec["status"] == "numerically_admitted", f"{design}: scenario is not admitted.")
    require(spec["outcomes_not_targets"] and spec["empirical_target"] is None,
            f"{design}: expected illustrative outcomes, not calibration targets.")
    require(parameters["chi"] == chi and paths["parameters"] == parameters,
            f"{design}: inconsistent parameters.")
    require(paths["design"] == figures["design"] == summary["design"] == activation["design"] == design,
            f"{design}: inconsistent design identities.")
    require(paths["horizon"] == figures["horizon"] == 500.0,
            f"{design}: unexpected displayed horizon.")
    require(figures["sigmas"] == list(SIGMAS) and figures["all_scenarios_admitted"],
            f"{design}: incomplete elasticity comparison.")
    require(activation["passes"] and sha256(folder / "activation_audit.json") == figures["activation_audit_sha256"],
            f"{design}: activation audit is invalid or has changed.")
    require(summary["instantaneous_growth_rates"] is True and source["annual_moments"]["outcomes_not_targets"],
            f"{design}: rate or annual-outcome semantics have changed.")
    require(set(figures["analytical_limits"]) == {"sigma_1_50"},
            f"{design}: unexpected analytical-limit coverage.")
    require(all(view["windows"] == [[-2.0, 10.0], [10.0, 500.0]] for view in figures["two_window_views"]),
            f"{design}: unexpected figure windows.")

    csv_path = folder / "equilibrium_paths.csv"
    csv_bytes = csv_path.read_bytes()
    digest = hashlib.sha256(csv_bytes).hexdigest()
    validate_csv_hash(digest, paths, figures, summary)
    rows = csv.DictReader(io.StringIO(csv_bytes.decode("utf-8")))
    require(set(("sigma", "time") + FIELD_KEYS).issubset(rows.fieldnames or []),
            f"{design}: a required CSV column is missing.")
    grouped = {sigma: {"times": [], "columns": {key: [] for key in FIELD_KEYS}} for sigma in SIGMAS}
    alpha, gamma = parameters["alpha"], parameters["labor_productivity_growth"]
    for record in rows:
        values = {key: float(value) for key, value in record.items()}
        require(all(math.isfinite(value) for value in values.values()), f"{design}: nonfinite CSV value.")
        sigma, time = values["sigma"], values["time"]
        require(sigma in grouped and 0 <= time <= 500, f"{design}: unsupported sigma or date.")
        series = grouped[sigma]
        require(not series["times"] or time > series["times"][-1],
                f"{design}: duplicated or unordered dates for sigma={sigma}.")
        require(close(values["output_per_person_growth"], values["output_effective_labor_growth"] + gamma),
                f"{design}: inconsistent growth normalization.")
        revenue = 1 - alpha - values["labor_income_share"]
        require(close(revenue, values["ai_revenue_output_share"]), f"{design}: inconsistent AI revenue.")
        require(close(revenue, sum(values[key] for key in
                    ("profit_output_share", "inference_output_share", "research_output_share"))),
                f"{design}: income shares do not reconcile.")
        require(values["ai_service_price"] > 0 and 0 < values["capability_frontier_ratio"] <= 1,
                f"{design}: invalid price or AI-efficiency ratio.")
        series["times"].append(time)
        for key in FIELD_KEYS:
            series["columns"][key].append(revenue if key == "ai_revenue_output_share" else values[key])

    times = grouped[SIGMAS[0]]["times"]
    require(len(times) == paths["points_per_scenario"] and times[0] == 0 and times[-1] == 500,
            f"{design}: incomplete sampled horizon.")
    scenarios, audit_hashes = {}, {}
    for sigma, series in grouped.items():
        key = sigma_key(sigma)
        require(series["times"] == times, f"{design}: elasticity time grids differ.")
        audit_path = folder / f"{key}_audit.json"
        audit = load_json(audit_path)
        require(audit["status"] == "numerically_admitted" and audit["equilibrium_certified"]
                and audit["early_window_checks"]["passes"], f"{design}/{key}: failed equilibrium audit.")
        require(audit["sigma_xl"] == sigma and audit["checkpoint_sha256"] == paths["checkpoint_sha256"][key],
                f"{design}/{key}: inconsistent checkpoint provenance.")
        pre = figures["pre_event_bgp"][key]
        require(activation["scenarios"][key]["passes"] and pre == activation["scenarios"][key]["pre"]
                == source["pre_rsi_reference"]["scenarios"][key], f"{design}/{key}: conflicting pre-event references.")
        require(spec["initial_stocks_by_sigma"][key] == [pre["capital"], pre["capability"]],
                f"{design}/{key}: initial stocks disagree with the reference.")
        annual = source["annual_moments"]["scenarios"][key]
        require(annual["maximum_horizon_log_change"] < 2e-5,
                f"{design}/{key}: annual outcome failed its horizon check.")
        scenarios[f"{sigma:g}"] = {
            "sigma": sigma,
            "columns": series["columns"],
            "pre_event": pre_event_values(pre, parameters, spec["frontier"]),
            "analytical_limits": figures["analytical_limits"].get(key),
        }
        audit_hashes[key] = sha256(audit_path)
    relative_csv = csv_path.relative_to(root).as_posix()
    dataset = {
        "chi": chi, "design": design, "scenarios": scenarios,
        "frontier": spec["frontier"], "initial_capability": spec["initial_capability"],
        "initial_stocks_by_sigma": spec["initial_stocks_by_sigma"],
        "provenance": {
            "csv_path": relative_csv, "csv_sha256": digest, "raw_csv_url": RAW_BASE + relative_csv,
            "manifest_sha256": {name: sha256(folder / f"{name}.json") for name in names},
            "audit_sha256": audit_hashes, "checkpoint_sha256": paths["checkpoint_sha256"],
            "all_recorded_checks_pass": True,
        },
    }
    return dataset, parameters, times


def build_data(root=ROOT):
    root = Path(root)
    datasets, common_parameters, common_times = {}, None, None
    for chi, design in DESIGNS:
        dataset, parameters, times = load_dataset(root, chi, design)
        parameters = {key: value for key, value in parameters.items() if key != "chi"}
        if common_parameters is not None:
            require(parameters == common_parameters and times == common_times,
                    "The two research-productivity comparisons do not share parameters and dates.")
            first = next(iter(datasets.values()))
            require(dataset["initial_stocks_by_sigma"] == first["initial_stocks_by_sigma"]
                    and dataset["frontier"] == first["frontier"], "Initial conditions differ between comparisons.")
        common_parameters, common_times = parameters, times
        datasets[f"{chi:g}"] = dataset
    return {
        "schema_version": 1,
        "description": "Eight stored equilibrium approximations; no new simulations or interpolation across parameters.",
        "storage_units": "Rates and shares are fractions. Apply each field's display_scale only when formatting.",
        "time_unit": "Years since unexpected RSI activation; not calendar years.",
        "pre_event_semantics": "Analytical fixed-efficiency BGP reference on [-2,0-]; sampled rows begin at 0+.",
        "limit_semantics": "Stored analytical limits exist only for sigma=1.5. Missing fields are not zero.",
        "windows": {"short": [-2, 10], "long": [10, 500]},
        "fields": FIELDS, "parameters": common_parameters, "times": common_times, "datasets": datasets,
    }


def serialized_data(root=ROOT):
    return (json.dumps(build_data(root), ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n").encode("utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify the generated file without writing")
    args = parser.parse_args()
    payload = serialized_data()
    destination = ROOT / OUTPUT
    if args.check:
        require(destination.is_file() and destination.read_bytes() == payload,
                "Web data are absent or stale; run scripts/build_web_data.py.")
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(payload)
    print(f"{'Verified' if args.check else 'Generated'} {OUTPUT.as_posix()}: {len(payload):,} bytes; eight exact sampled trajectories.")


if __name__ == "__main__":
    main()
