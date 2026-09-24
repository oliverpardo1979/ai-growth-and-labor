"""Competitive fixed-B equilibrium above the AI-dominance threshold.

The inherited capital stock need not be on a balanced-growth path. Solve
the Ramsey resource constraint and Euler equation with C/K -> rho-n,
using log(K/(AN)) with its limiting trend removed and log(C/K).
"""
from dataclasses import dataclass
import math
import numpy as np
from scipy.integrate import solve_bvp
from scipy.special import expit


def static_block(log_k, B, sigma, p):
    """Competitive optimum, per unit of effective labor, in stable logs."""
    if sigma <= 1 or B <= 0:
        raise ValueError('This solver is for sigma>1 and B>0.')
    log_k = np.asarray(log_k, dtype=float)
    phi = (sigma-1)/sigma
    constant = (p.alpha*math.log(p.omega_l)/phi
        - math.log(p.omega_x)/phi-math.log(B*(1-p.alpha)))/p.alpha
    target = log_k-constant
    q = np.where(target > 0, target*phi, target*p.alpha*(sigma-1))
    for _ in range(40):
        s = expit(q)
        error = (q+(p.alpha*sigma-1)*np.logaddexp(0,q))/(p.alpha*(sigma-1))-target
        derivative = (1+(p.alpha*sigma-1)*s)/(p.alpha*(sigma-1))
        change = error/derivative
        q -= change
        if np.max(np.abs(change)) < 2e-13:
            break
    if np.max(np.abs(error)) > 1e-10:
        raise RuntimeError('Competitive static root failed.')
    s, one_minus_s = expit(q), expit(-q)
    log_z = (math.log(p.omega_l)+np.logaddexp(0,q))/phi
    log_x = (math.log(p.omega_l/p.omega_x)+q)/phi
    log_y = p.alpha*log_k+(1-p.alpha)*log_z
    yk = np.exp(log_y-log_k)
    net_over_k = yk*(p.alpha+(1-p.alpha)*one_minus_s)
    denominator = 1+(p.alpha*sigma-1)*s
    return dict(log_k=log_k, log_x=log_x, log_y=log_y,
        log_w=math.log(1-p.alpha)-np.logaddexp(0,q)+log_y,
        share=s, labor_share=(1-p.alpha)*one_minus_s,
        yk=yk, net_over_k=net_over_k, r=p.alpha*yk-p.depreciation,
        x_log_gradient=p.alpha*sigma/denominator,
        y_log_gradient=p.alpha*(1+(sigma-1)*s)/denominator,
        w_log_gradient=p.alpha/denominator,
        static_residual=math.log((1-p.alpha)*B)+np.log(s)+log_y-log_x)


def limiting_return(B, sigma, p):
    return (p.alpha*((1-p.alpha)*B*p.omega_x**(sigma/(sigma-1)))
        **((1-p.alpha)/p.alpha)-p.depreciation)


@dataclass
class CompetitivePath:
    raw: object
    B: float
    sigma: float
    parameters: object
    capital: float
    horizon: float
    trend: float


def rhs(t, z, B, sigma, p, trend):
    block = static_block(z[0]+trend*np.asarray(t), B, sigma, p)
    ck = np.exp(z[1])
    gk = block['net_over_k']-ck-p.depreciation
    # gk is aggregate capital growth, not growth relative to AN.
    return np.array([gk-p.population_growth-p.labor_productivity_growth-trend,
        p.population_growth+block['r']-p.discount-gk])


def solve(B, sigma, p, capital, horizon=1200., previous=None):
    trend = limiting_return(B,sigma,p)-p.discount-p.labor_productivity_growth
    if trend <= 0 or capital <= 0:
        raise ValueError('Require positive capital and AI-dominated competition.')
    scale = p.initial_labor_productivity*p.initial_population
    if scale <= 0:
        raise ValueError('Initial effective labor must be positive.')
    log_initial_k = math.log(capital/scale)
    times = np.unique(np.r_[np.linspace(0,10,101),np.linspace(10,horizon,700)])
    guess = np.vstack([np.full_like(times,log_initial_k),
                       np.full_like(times,math.log(p.discount-p.population_growth))])
    if previous is not None:
        inside = times <= previous.horizon
        guess[:,inside] = previous.raw.sol(times[inside])
        guess[:,~inside] = previous.raw.sol(previous.horizon)[:,None]
    bc = lambda a,b: np.array([a[0]-log_initial_k,
        b[1]-math.log(p.discount-p.population_growth)])
    raw = solve_bvp(lambda t,z:rhs(t,z,B,sigma,p,trend),bc,times,guess,
        tol=1e-10,bc_tol=1e-12,max_nodes=40000)
    if not raw.success:
        raise RuntimeError(raw.message)
    return CompetitivePath(raw,B,sigma,p,capital,horizon,trend)


def rows(path, times):
    p, B, sigma = path.parameters, path.B, path.sigma
    times = np.asarray(times,dtype=float)
    if min(times)<0 or max(times)>path.horizon:
        raise ValueError('Cannot extrapolate a competitive path.')
    z = path.raw.sol(times)
    log_k = z[0]+path.trend*times
    block = static_block(log_k,B,sigma,p)
    derivative = rhs(times,z,B,sigma,p,path.trend)
    gkn = derivative[0]+path.trend
    out=[]
    for j,t in enumerate(times):
        out.append(dict(time=float(t),sigma=sigma,
            output_effective_labor=float(np.exp(block['log_y'][j])),
            capital_effective_labor=float(np.exp(log_k[j])),
            consumption_effective_labor=float(np.exp(log_k[j]+z[1,j])),
            wage_productivity=float(np.exp(block['log_w'][j])),
            ai_services_effective_labor=float(np.exp(block['log_x'][j])),
            capability=B, ai_service_price=1/B,
            output_per_person_growth=float(p.labor_productivity_growth+block['y_log_gradient'][j]*gkn[j]),
            wage_growth=float(p.labor_productivity_growth+block['w_log_gradient'][j]*gkn[j]),
            consumption_per_person_growth=float(block['r'][j]-p.discount),
            net_interest=float(block['r'][j]),
            labor_income_share=float(block['labor_share'][j]),
            inference_output_share=float((1-p.alpha)*block['share'][j]),
            research_output_share=0.,profit_output_share=0.))
    return out


def audit(shorter, longer, display_horizon=500.):
    p=longer.parameters
    times=np.unique(np.r_[np.linspace(.001,10,801),np.linspace(10,longer.horizon-1,1001)])
    z=longer.raw.sol(times)
    exact=rhs(times,z,longer.B,longer.sigma,p,longer.trend)
    residuals=[]
    for step in (.0001,.0003):
        deriv=(-longer.raw.sol(times+2*step)+8*longer.raw.sol(times+step)
            -8*longer.raw.sol(times-step)+longer.raw.sol(times-2*step))/(12*step)
        residuals.append(float(np.max(np.abs(deriv-exact))))
    block=static_block(z[0]+longer.trend*times,longer.B,longer.sigma,p)
    common=np.linspace(0,display_horizon,1001)
    gap=float(np.max(np.abs(shorter.raw.sol(common)-longer.raw.sol(common))))
    last=rows(longer,np.array([longer.horizon]))[0]
    rlimit=limiting_return(longer.B,longer.sigma,p)
    final_error=max(abs(last['net_interest']-rlimit),
        abs(last['output_per_person_growth']-(rlimit-p.discount)))
    payload=dict(horizons=[shorter.horizon,longer.horizon],
        common_window=display_horizon,maximum_common_window_coordinate_change=gap,
        maximum_finite_difference_residuals=residuals,
        maximum_static_foc_log_residual=float(np.max(np.abs(block['static_residual']))),
        maximum_collocation_residual=float(np.max(longer.raw.rms_residuals)),
        log_initial_capital_error=float(abs(longer.raw.sol(0)[0]-math.log(
            longer.capital/(p.initial_labor_productivity*p.initial_population)))),
        consumption_capital_limit=p.discount-p.population_growth,
        terminal_rate_error=final_error,
        household_tvc_log=float((p.population_growth-p.discount)*longer.horizon-longer.raw.sol(longer.horizon)[1]),
        limiting_interest_rate=rlimit,
        limiting_output_per_worker_growth=rlimit-p.discount,
        limiting_wage_growth=p.labor_productivity_growth+longer.trend/longer.sigma,
        method='Concave competitive Ramsey problem; positive log-state path; C/K -> rho-n; independent finite differences and horizon extension.')
    payload['passes']=bool(gap<2e-5 and max(residuals)<1e-6
        and payload['maximum_static_foc_log_residual']<1e-9
        and payload['log_initial_capital_error']<1e-10
        and final_error<1e-6 and payload['household_tvc_log']<-30)
    return payload
