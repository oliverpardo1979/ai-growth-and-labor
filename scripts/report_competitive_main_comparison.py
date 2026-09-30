"""Compare both research productivities at sigma=1.5 using stored paths only.

This is a presentation selection, not a new simulation. The original
four-elasticity figures and their source data remain unchanged.
"""
import hashlib
import json

from report_competitive_to_monopoly import (
    ROOT, FIGDIR, checked_data, make_design,
    first_upcrossing, np, plt, Line2D, PercentFormatter, MaxNLocator,
    FixedLocator, LogLocator, NullLocator, FuncFormatter,
)

SIGMA = 1.5
CHIS = (7.5, 1.5)
STYLES = {
    7.5: ("#24618c", "-"),
    1.5: ("#bd8620", (0, (5, 1.8, 1, 1.8))),
}
COMPETITION_STYLE = ("#414141", (0, (4, 2)))
STEM = "competitive_to_monopoly_sigma_1_5_levels"
REVENUE_STEM = "competitive_to_monopoly_sigma_1_5_revenue"
MAIN_WINDOWS = ((-2., 10.), (10., 50.))
MAIN_PANELS = (
    ("output_counterfactual_ratio", "A. Output per worker", "ratio"),
    ("wage_counterfactual_ratio", "B. Wage", "ratio"),
    ("consumption_counterfactual_ratio", "C. Consumption\nper person", "ratio"),
)
PRESERVED_SUPPLEMENTAL_FILES = (
    ROOT / "scripts/report_competitive_to_monopoly.py",
    *(FIGDIR / f"competitive_to_monopoly_chi_{chi}_levels.{extension}"
      for chi in ("7_5", "1_5") for extension in ("pdf", "png")),
)
RATIO_FIELDS = {
    "output_counterfactual_ratio": ("output_effective_labor", "output"),
    "wage_counterfactual_ratio": ("wage_productivity", "wage"),
    "consumption_counterfactual_ratio": ("consumption_effective_labor", "consumption"),
}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_comparison():
    """Verify audit hashes; select sigma=1.5 and calculate ratios in memory."""
    datasets, sources = {}, {}
    common_reference = None
    common_parameters = None
    for chi in CHIS:
        design = make_design(chi)
        rows, pre = checked_data(design)
        ref = pre["sigma_1_50"]
        scenario = json.loads((design.output_directory / "scenario.json").read_text())
        parameters = dict(scenario["parameters"])
        if parameters.pop("chi") != chi:
            raise ValueError("Incorrect research productivity in the stored scenario.")
        comparison_inputs = (parameters, scenario["frontier"], scenario["initial_capability"])
        if common_reference is not None:
            if ref != common_reference or comparison_inputs != common_parameters:
                raise ValueError("The chi comparison must use identical other inputs.")
        common_reference, common_parameters = ref, comparison_inputs
        series = [dict(row) for row in rows if row["sigma"] == SIGMA]
        if not series or series[0]["time"] != 0:
            raise ValueError("Expected a date-zero observation.")
        if not all(a["time"] < b["time"] for a, b in zip(series, series[1:])):
            raise ValueError("Dates must be strictly increasing within each path.")
        for ratio, (numerator, denominator) in RATIO_FIELDS.items():
            if ref[denominator] <= 0:
                raise ValueError("The competitive denominator must be positive.")
            for row in series:
                row[ratio] = row[numerator] / ref[denominator]
                if not np.isfinite(row[ratio]) or row[ratio] <= 0:
                    raise ValueError("Invalid level ratio.")
        if abs(series[0]["capital_effective_labor"] / ref["capital"] - 1) > 1e-9:
            raise ValueError("The inherited capital stock must not jump.")
        if ref["profit_output_share"] != 0:
            raise ValueError("Continued competition must have zero developer profit.")
        competitive_revenue = ref["ai_revenue_output_share"]
        if (not np.isfinite(competitive_revenue) or competitive_revenue <= 0
                or abs(competitive_revenue - ref["inference_output_share"]) > 1e-12
                or abs(competitive_revenue - (1 - parameters["alpha"]
                                              - ref["labor_income_share"])) > 1e-12):
            raise ValueError("Competitive AI revenue must cover inference and reconcile with income shares.")
        for row in series:
            row["competitive_ai_revenue_output_share"] = competitive_revenue
            net_profit = (row["ai_revenue_output_share"]
                          - row["inference_output_share"] - row["research_output_share"])
            if (not np.isfinite(row["profit_output_share"])
                    or abs(row["profit_output_share"] - net_profit) > 1e-12):
                raise ValueError("Net profit must deduct both inference and research costs.")
            if (not np.isfinite(row["ai_revenue_output_share"])
                    or abs(row["ai_revenue_output_share"] - (1 - parameters["alpha"]
                                                           - row["labor_income_share"])) > 1e-12):
                raise ValueError("AI revenue must reconcile with capital and labor income shares.")
        datasets[chi] = series
        sources[str(chi)] = {
            "files": {
                (design.output_directory / name).relative_to(ROOT).as_posix():
                    sha256(design.output_directory / name)
                for name in ("equilibrium_paths.csv", "competitive_reference.json",
                             "paths_manifest.json", "sigma_1_50_audit.json", "scenario.json")
            },
            "initial_change_percent": {
                ratio: 100 * (series[0][ratio] - 1) for ratio in RATIO_FIELDS
            },
            "first_recovery_year": {
                ratio: first_upcrossing(series, ratio) for ratio in RATIO_FIELDS
            },
            "competitive_ai_revenue_output_share": competitive_revenue,
        }
    return datasets, sources


def competitive_benchmark(datasets, field):
    if field == "ai_revenue_output_share":
        return datasets[CHIS[0]][0]["competitive_ai_revenue_output_share"]
    return 1.


def plot_comparison(axis, datasets, field, start, end):
    """Plot actual stored observations with separate before/after impact marks."""
    benchmark = competitive_benchmark(datasets, field)
    color, style = COMPETITION_STYLE
    axis.plot([start, end], [benchmark, benchmark], color=color, ls=style, lw=1.3,
              gid="continued_competition")
    for chi in CHIS:
        color, style = STYLES[chi]
        series = [row for row in datasets[chi] if start <= row["time"] <= end]
        if not series or series[-1]["time"] < end:
            raise ValueError("The data do not cover the figure window.")
        axis.plot([row["time"] for row in series],
                  [row[field] for row in series], color=color, ls=style,
                  lw=1.5, gid=f"chi_{chi}_post")
        if start < 0:
            axis.plot([start, 0], [benchmark, benchmark], color=color, ls=style, lw=1.2,
                      gid=f"chi_{chi}_pre")
            axis.plot(0, benchmark, marker="o", mfc="white", mec=color, ms=3,
                      gid=f"chi_{chi}_before")
            axis.plot(0, series[0][field], marker="o", color=color, ms=3,
                      gid=f"chi_{chi}_after")


def comparison_handles():
    handles = [Line2D([], [], color=COMPETITION_STYLE[0], ls=COMPETITION_STYLE[1],
                      lw=1.3, label="Continued competition")]
    return handles + [Line2D([], [], color=STYLES[chi][0], ls=STYLES[chi][1], lw=1.5,
                             label=fr"Monopoly, $\chi={chi:g}$") for chi in CHIS]


def make_figure(datasets):
    """Shared axes for the two chi values; no line bridges the impact jump."""
    fig, axes = plt.subplots(2, 3, figsize=(8.6, 6.4))
    for view, (start, end) in enumerate(MAIN_WINDOWS):
        for axis, (field, label, unit) in zip(axes[view], MAIN_PANELS):
            plot_comparison(axis, datasets, field, start, end)
            axis.set_title(label, loc="left", pad=8, fontsize=11)
            if view == 0 or unit == "share":
                axis.yaxis.set_major_formatter(PercentFormatter(1, decimals=1))
                axis.yaxis.set_major_locator(MaxNLocator(4))
            else:
                axis.set_yscale("log")
                lo, hi = axis.get_ylim()
                if hi / lo < 10:
                    ticks = [v for v in (.5, .75, 1, 1.5, 2, 3, 5, 10)
                             if lo <= v <= hi]
                    axis.yaxis.set_major_locator(FixedLocator(ticks))
                else:
                    axis.yaxis.set_major_locator(LogLocator(base=10, numticks=5))
                axis.yaxis.set_minor_locator(NullLocator())
                axis.yaxis.set_major_formatter(FuncFormatter(
                    lambda v, pos: fr"$10^{{{int(round(np.log10(v)))}}}\times$"
                    if v >= 10000 else "$" + format(v, "g") + r"\times$"))
            if view == 0:
                axis.axvline(0, color="#999999", ls=":", lw=.7)
            axis.set_xlim(start, end)
            axis.set_xticks([-2, 0, 5, 10] if view == 0 else [10, 20, 30, 40, 50])
            axis.set_xlabel(("Years: initial transition", "Years: subsequent transition")[view])
            axis.grid(axis="y", color="#dddddd", lw=.5)
            axis.spines[["top", "right"]].set_visible(False)
            axis.spines[["left", "bottom"]].set_color("#999999")
    fig.suptitle(r"From competition to monopoly | $\sigma=1.5$",
                 fontsize=14, y=.99)
    fig.legend(handles=comparison_handles(), loc="upper center", bbox_to_anchor=(.5, .93),
               ncol=3, frameon=False, fontsize=9)
    fig.text(.08, .018,
             "Top: 100% = competition. Bottom: multiples (log scale), 1x = competition.\n"
             "Open/filled dots: before/after exclusive rights. Vertical scales differ across windows.",
             fontsize=8, color="#444444", va="bottom")
    fig.subplots_adjust(left=.10, right=.97, top=.80, bottom=.175,
                        wspace=.48, hspace=.95)
    return fig


def make_revenue_figure(datasets):
    """AI revenue is a share of each economy's own output, not a level ratio."""
    fig, axes = plt.subplots(1, 2, figsize=(8.6, 3.8), sharey=True)
    for view, (axis, (start, end)) in enumerate(zip(axes, MAIN_WINDOWS)):
        plot_comparison(axis, datasets, "ai_revenue_output_share", start, end)
        axis.set_title(("A. Initial transition", "B. Subsequent transition")[view],
                       loc="left", pad=8, fontsize=11)
        axis.yaxis.set_major_formatter(PercentFormatter(1, decimals=1))
        axis.yaxis.set_major_locator(MaxNLocator(4))
        axis.tick_params(axis="y", labelleft=True)
        if view == 0:
            axis.axvline(0, color="#999999", ls=":", lw=.7)
        axis.set_xlim(start, end)
        axis.set_xticks([-2, 0, 5, 10] if view == 0 else [10, 20, 30, 40, 50])
        axis.set_xlabel("Years after exclusive rights")
        axis.grid(axis="y", color="#dddddd", lw=.5)
        axis.spines[["top", "right"]].set_visible(False)
        axis.spines[["left", "bottom"]].set_color("#999999")
    fig.suptitle(r"AI-industry revenue | $\sigma=1.5$", fontsize=14, y=.99)
    fig.legend(handles=comparison_handles(), loc="upper center", bbox_to_anchor=(.5, .91),
               ncol=3, frameon=False, fontsize=9)
    fig.text(.08, .018,
             r"Revenue $p_X X/Y$: percent of each economy's own output; not net profit." "\n"
             "Open/filled dots: before/after exclusive rights. Both panels use the same linear scale.",
             fontsize=8, color="#444444", va="bottom")
    fig.subplots_adjust(left=.10, right=.97, top=.72, bottom=.27, wspace=.30)
    return fig


def main():
    datasets, sources = load_comparison()
    FIGDIR.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.family": "DejaVu Serif", "font.size": 10, "pdf.fonttype": 42})
    fig = make_figure(datasets)
    png, pdf = FIGDIR / f"{STEM}.png", FIGDIR / f"{STEM}.pdf"
    fig.savefig(png, dpi=165)
    fig.savefig(pdf, metadata={"Title": "Competition to monopoly: sigma=1.5, two research productivities"})
    plt.close(fig)
    revenue = make_revenue_figure(datasets)
    revenue_png, revenue_pdf = FIGDIR / f"{REVENUE_STEM}.png", FIGDIR / f"{REVENUE_STEM}.pdf"
    revenue.savefig(revenue_png, dpi=165)
    revenue.savefig(revenue_pdf, metadata={"Title": "AI-industry revenue: competition to monopoly, sigma=1.5"})
    plt.close(revenue)
    manifest = {
        "sigma": SIGMA, "chis": CHIS, "windows": MAIN_WINDOWS,
        "panels": [
            {"field": field, "competitive_benchmark": competitive_benchmark(datasets, field),
             "scales_by_window": ["linear_percent", "linear_percent"
                                  if unit == "share" else "log_multiple"]}
            for field, _, unit in MAIN_PANELS
        ],
        "revenue_definition": "p_X X / own output = 1 - alpha - labor income share; includes inference, research and net profit",
        "supplementary_revenue": {
            "stem": REVENUE_STEM, "field": "ai_revenue_output_share",
            "windows": MAIN_WINDOWS, "scales_by_window": ["linear_percent", "linear_percent"],
            "competitive_benchmark": competitive_benchmark(datasets, "ai_revenue_output_share"),
            "files": [path.relative_to(ROOT).as_posix() for path in (revenue_png, revenue_pdf)],
        },
        "percent_decimals": 1, "ratio_fields": RATIO_FIELDS, "sources": sources,
        "preserved_supplemental_files": {
            path.relative_to(ROOT).as_posix(): sha256(path)
            for path in PRESERVED_SUPPLEMENTAL_FILES
        },
        "files": [path.relative_to(ROOT).as_posix() for path in (png, pdf, revenue_png, revenue_pdf)],
        "note": "Both figures read the same existing audited data only. Original four-elasticity figures are preserved.",
    }
    (FIGDIR / f"{STEM}_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(pdf, flush=True)
    print(revenue_pdf, flush=True)


if __name__ == "__main__":
    main()
