"""Compare both research productivities at sigma=1.5 using stored paths only.

This is a presentation selection, not a new simulation. The original
four-elasticity figures and their source data remain unchanged.
"""
import hashlib
import json

from report_competitive_to_monopoly import (
    ROOT, FIGDIR, LEVEL_PANELS, LEVEL_WINDOWS, checked_data, make_design,
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
        }
    return datasets, sources


def make_figure(datasets):
    """Shared axes for the two chi values; no line bridges the impact jump."""
    fig, axes = plt.subplots(3, 3, figsize=(8.6, 9.0))
    for view, (start, end) in enumerate(LEVEL_WINDOWS):
        for axis, (field, label, _) in zip(axes[view], LEVEL_PANELS):
            color, style = COMPETITION_STYLE
            axis.plot([start, end], [1, 1], color=color, ls=style, lw=1.3,
                      gid="continued_competition")
            for chi in CHIS:
                color, style = STYLES[chi]
                series = [row for row in datasets[chi] if start <= row["time"] <= end]
                if not series or series[-1]["time"] < end:
                    raise ValueError("The data do not cover the figure window.")
                axis.plot([row["time"] for row in series],
                          [row[field] for row in series], color=color, ls=style,
                          lw=1.5, gid=f"chi_{chi}_post")
                if view == 0:
                    axis.plot([start, 0], [1, 1], color=color, ls=style, lw=1.2,
                              gid=f"chi_{chi}_pre")
                    axis.plot(0, 1, marker="o", mfc="white", mec=color, ms=3)
                    axis.plot(0, series[0][field], marker="o", color=color, ms=3)
            axis.set_title(label, loc="left", pad=8, fontsize=11)
            if view == 0:
                axis.yaxis.set_major_formatter(PercentFormatter(1, decimals=1))
                axis.yaxis.set_major_locator(MaxNLocator(4))
                axis.axvline(0, color="#999999", ls=":", lw=.7)
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
            axis.set_xlim(start, end)
            axis.set_xticks([-2, 0, 5, 10] if view == 0 else
                            ([10, 25, 50, 75, 100] if end == 100 else [10, 100, 250, 500]))
            axis.set_xlabel(("Years: initial transition", "Years: intermediate window",
                             "Years: longer window")[view])
            axis.grid(axis="y", color="#dddddd", lw=.5)
            axis.spines[["top", "right"]].set_visible(False)
            axis.spines[["left", "bottom"]].set_color("#999999")
    handles = [Line2D([], [], color=COMPETITION_STYLE[0], ls=COMPETITION_STYLE[1],
                      lw=1.3, label="Continued competition")]
    handles += [Line2D([], [], color=STYLES[chi][0], ls=STYLES[chi][1], lw=1.5,
                       label=fr"Monopoly, $\chi={chi:g}$") for chi in CHIS]
    fig.suptitle(r"Levels relative to continued competition | $\sigma=1.5$",
                 fontsize=14, y=.99)
    fig.legend(handles=handles, loc="upper center", bbox_to_anchor=(.5, .948),
               ncol=3, frameon=False, fontsize=9)
    fig.text(.08, .018,
             "Top: 100.0% = continued competition. Middle/bottom: multiples (log scale); 1x = competition.\n"
             "Open/filled dots: before/after exclusive rights. Vertical scales differ across windows.",
             fontsize=8, color="#444444", va="bottom")
    fig.subplots_adjust(left=.10, right=.97, top=.855, bottom=.105,
                        wspace=.48, hspace=.95)
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
    manifest = {
        "sigma": SIGMA, "chis": CHIS, "windows": LEVEL_WINDOWS,
        "scales": ["linear_percent", "log_multiple", "log_multiple"],
        "percent_decimals": 1, "ratio_fields": RATIO_FIELDS, "sources": sources,
        "files": [path.relative_to(ROOT).as_posix() for path in (png, pdf)],
        "note": "Reads existing audited data only. Original four-elasticity figures are preserved.",
    }
    (FIGDIR / f"{STEM}_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(pdf, flush=True)


if __name__ == "__main__":
    main()
