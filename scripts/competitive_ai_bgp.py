"""Competitive fixed-efficiency BGP used before granting exclusive AI rights.

RSI is available, but public access and absence of appropriable research
returns imply M=0. These formulas do not set chi to zero. Stocks, not the
competitive consumption choice, are inherited by the post-event monopoly.
"""
import math


def competitive_fixed_efficiency_bgp(sigma, capability, parameters):
    """Exact labor-bottleneck BGP at A0=N0=1, for any sigma>0 when it exists."""
    p = parameters
    if sigma <= 0 or capability <= 0:
        raise ValueError('Require positive sigma and AI efficiency.')
    if p.initial_labor_productivity != 1 or p.initial_population != 1:
        raise ValueError('This experimental design normalizes A0=N0=1.')
    theta = (p.discount + p.labor_productivity_growth + p.depreciation) / p.alpha
    # F_X=1/B and Y/K=theta determine X/Z independently of the CES identity.
    log_xz = sigma * (math.log(capability * (1-p.alpha) * p.omega_x)
                     - p.alpha/(1-p.alpha)*math.log(theta))
    if sigma == 1:
        sx = p.omega_x
        log_z = p.omega_x / p.omega_l * log_xz
    else:
        power = (sigma-1)/sigma
        sx = p.omega_x * math.exp(power * log_xz)
        if not 0 < sx < 1:
            raise ValueError('No positive labor-bottleneck BGP at this fixed B.')
        log_z = (math.log(p.omega_l)-math.log1p(-sx))/power
    k = math.exp(log_z - math.log(theta)/(1-p.alpha))
    y = theta*k
    x = math.exp(log_z+log_xz)
    u = x/capability
    c = y-u-(p.depreciation+p.population_growth+p.labor_productivity_growth)*k
    if c <= 0:
        raise ValueError('Competitive BGP consumption must be positive.')
    residual = math.log((1-p.alpha)*sx*y/u)
    if abs(residual) > 1e-10:
        raise ValueError('Competitive static pricing condition failed.')
    return dict(sigma=sigma, capital=k, capability=capability, output=y,
                consumption=c, ai_services=x, inference_compute=u, research_compute=0.,
                ai_service_price=1/capability, wage=(1-p.alpha)*(1-sx)*y,
                interest_rate=p.discount+p.labor_productivity_growth,
                capital_output_ratio=k/y, labor_income_share=(1-p.alpha)*(1-sx),
                ai_revenue_output_share=u/y, inference_output_share=u/y,
                research_output_share=0., profit_output_share=0.,
                competitive_foc_log_residual=residual, pre_event_research_available=True)
