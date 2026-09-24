"""Algebra checks for the competitive benchmark; no simulation files are used.

These tests check identities used in the analytical proof, not equilibrium
existence or convergence (which are established in the manuscript).
"""

import math
import unittest


def logaddexp(a, b):
    top = max(a, b)
    return top + math.log(math.exp(a - top) + math.exp(b - top))


def static_allocation(k, B, alpha, sigma, omega):
    """Solve Y_U=1 in log compute, independently of the limiting formulas."""
    p = (sigma - 1) / sigma

    def quantities(log_u):
        log_x = math.log(B) + log_u
        log_total = logaddexp(math.log1p(-omega), math.log(omega) + p * log_x)
        log_s = math.log(omega) + p * log_x - log_total
        log_y = alpha * math.log(k) + (1 - alpha) * log_total / p
        log_mp = math.log1p(-alpha) + log_s + log_y - log_u
        return log_mp, log_y, log_s

    lo, hi = -2000.0, 2000.0
    for _ in range(180):
        mid = (lo + hi) / 2
        if quantities(mid)[0] > 0:
            lo = mid
        else:
            hi = mid
    log_u = (lo + hi) / 2
    residual, log_y, log_s = quantities(log_u)
    y, u, s = math.exp(log_y), math.exp(log_u), math.exp(log_s)
    return {"y": y, "u": u, "s": s, "f": y - u,
            "fp": alpha * y / k, "w": (1 - alpha) * (1 - s) * y,
            "e": (1 - s) / sigma + alpha * s, "residual": residual}


def threshold(alpha, sigma, omega, rho=0.04, gamma=0.02, delta=0.06):
    return ((rho + gamma + delta) / alpha) ** (alpha / (1 - alpha)) / (
        (1 - alpha) * omega ** (sigma / (sigma - 1)))


def limiting_return(B, alpha, sigma, omega, monopoly=False, delta=0.06):
    price_factor = (1 - alpha) ** (2 if monopoly else 1)
    return alpha * (price_factor * B * omega ** (sigma / (sigma - 1))) ** (
        (1 - alpha) / alpha) - delta


class CompetitiveBenchmarkIdentities(unittest.TestCase):
    def test_static_envelope_curvature_and_wage_elasticity(self):
        for alpha in (0.2, 0.33, 0.6):
            for sigma in (1.1, 1.5, 3.0):
                omega = 0.2
                B = threshold(alpha, sigma, omega)
                for k in (0.1, 1.0, 10.0, 100.0):
                    with self.subTest(alpha=alpha, sigma=sigma, k=k):
                        a = static_allocation(k, B, alpha, sigma, omega)
                        step = 1e-4
                        minus = static_allocation(k * math.exp(-step), B, alpha, sigma, omega)
                        plus = static_allocation(k * math.exp(step), B, alpha, sigma, omega)
                        self.assertAlmostEqual(a["residual"], 0, delta=1e-11)
                        self.assertAlmostEqual(a["u"] / a["y"], (1 - alpha) * a["s"], delta=1e-12)
                        self.assertAlmostEqual((a["f"] - k * a["fp"]) / a["y"], a["w"] / a["y"], delta=1e-12)
                        num_fp = (plus["f"] - minus["f"]) / (2 * step * k)
                        self.assertAlmostEqual(num_fp / a["fp"], 1, delta=2e-7)
                        elasticity_fp = math.log(plus["fp"] / minus["fp"]) / (2 * step)
                        predicted_fp = -(1 - alpha) * (1 - a["s"]) / (sigma * a["e"])
                        self.assertAlmostEqual(elasticity_fp, predicted_fp, delta=2e-7)
                        elasticity_w = math.log(plus["w"] / minus["w"]) / (2 * step)
                        self.assertAlmostEqual(elasticity_w, alpha / (sigma * a["e"]), delta=2e-7)
                        self.assertLess(predicted_fp, 0)

    def test_threshold_and_monopoly_comparison(self):
        for alpha in (0.2, 0.33, 0.6):
            for sigma in (1.1, 1.5, 3.0):
                B_mc = threshold(alpha, sigma, 0.1)
                B_mon = B_mc / (1 - alpha)
                self.assertAlmostEqual(limiting_return(B_mc, alpha, sigma, 0.1), 0.06)
                self.assertAlmostEqual(limiting_return(B_mon, alpha, sigma, 0.1, True), 0.06)
                for factor in (0.5, 1.0, 2.0):
                    B = factor * B_mc
                    self.assertAlmostEqual(
                        limiting_return(B, alpha, sigma, 0.1),
                        limiting_return(B / (1 - alpha), alpha, sigma, 0.1, True))

    def test_asymptotic_net_output_and_growth_identities(self):
        alpha, sigma, omega = 0.33, 1.5, 0.1
        for factor in (0.75, 1.0, 1.5):
            B = factor * threshold(alpha, sigma, omega)
            a = static_allocation(1e30, B, alpha, sigma, omega)
            R = limiting_return(B, alpha, sigma, omega)
            self.assertAlmostEqual(a["fp"], R + 0.06, delta=1e-8)
            self.assertAlmostEqual(a["f"] / 1e30, R + 0.06, delta=1e-8)
            self.assertAlmostEqual(a["u"] / a["y"], 1 - alpha, delta=1e-8)
        # Exact ratio equation used in the shooting construction.
        a = static_allocation(3.0, B, alpha, sigma, omega)
        n, gamma, delta, rho, k, c = 0.01, 0.02, 0.06, 0.04, 3.0, 0.2
        k_growth = (a["f"] - c) / k - delta - n - gamma
        c_growth = a["fp"] - delta - rho - gamma
        ratio_growth = c / k - (rho - n) - (a["f"] - k * a["fp"]) / k
        self.assertAlmostEqual(c_growth - k_growth, ratio_growth)

    def test_regime_reversal_despite_higher_monopoly_efficiency(self):
        """Check the corollary's threshold region, not local path existence."""
        rho, gamma = 0.04, 0.02
        for alpha in (0.2, 0.33, 0.6):
            for sigma in (1.1, 1.5, 3.0):
                B_mc = threshold(alpha, sigma, 0.1, rho=rho, gamma=gamma)
                B_mon = B_mc / (1 - alpha)
                for cap_fraction in (0.25, 0.5, 0.75):
                    cap = B_mc + cap_fraction * (B_mon - B_mc)
                    for initial_fraction in (0.5, 0.99, 0.9999):
                        with self.subTest(alpha=alpha, sigma=sigma,
                                          cap_fraction=cap_fraction,
                                          initial_fraction=initial_fraction):
                            B0 = B_mc + initial_fraction * (cap - B_mc)
                            self.assertLess(B_mc, B0)
                            self.assertLess(B0, cap)
                            self.assertLess(cap, B_mon)
                            R_mc = limiting_return(B0, alpha, sigma, 0.1)
                            R_mon = limiting_return(cap, alpha, sigma, 0.1,
                                                    monopoly=True)
                            self.assertGreater(R_mc, rho + gamma)
                            self.assertLess(R_mon, rho + gamma)
                            self.assertGreater(R_mc - rho, gamma)
                            self.assertGreater(
                                gamma + (R_mc - rho - gamma) / sigma, gamma)

    def test_conditional_growth_ordering_with_different_efficiencies(self):
        """Check the ranking conditional on both AI-dominated limits existing."""
        rho, gamma = 0.04, 0.02
        for alpha in (0.2, 0.33, 0.6):
            for sigma in (1.1, 1.5, 3.0):
                B_mc = threshold(alpha, sigma, 0.1, rho=rho, gamma=gamma)
                B_mon = B_mc / (1 - alpha)
                cap = 4 * B_mon / (1 - alpha)
                R_mon = limiting_return(cap, alpha, sigma, 0.1, monopoly=True)
                for fraction, sign in ((0.5 * (1 - alpha), -1),
                                       (1 - alpha, 0), (1 - alpha / 2, 1)):
                    with self.subTest(alpha=alpha, sigma=sigma, fraction=fraction):
                        B0 = fraction * cap
                        self.assertGreater(B0, B_mc)
                        self.assertLess(B0, cap)
                        self.assertGreater(cap, B_mon)
                        R_mc = limiting_return(B0, alpha, sigma, 0.1)
                        output_gap = (R_mc - rho) - (R_mon - rho)
                        wage_gap = ((gamma + (R_mc - rho - gamma) / sigma)
                                    - (gamma + (R_mon - rho - gamma) / sigma))
                        if sign == 0:
                            self.assertAlmostEqual(R_mc / R_mon, 1.0, delta=1e-12)
                        else:
                            self.assertGreater(sign * output_gap, 0.0)
                            self.assertGreater(sign * wage_gap, 0.0)
                        self.assertAlmostEqual(wage_gap, output_gap / sigma,
                                               delta=1e-12 * R_mon)


if __name__ == "__main__":
    unittest.main()
