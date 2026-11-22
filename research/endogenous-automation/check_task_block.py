"""Static identity and derivative checks. Not equilibrium-transition simulations."""
from math import exp, expm1, log, log1p
import json
from pathlib import Path

import numpy as np

def bisect_root(fun, lo, hi):
    assert fun(lo) < 0 < fun(hi)
    for _ in range(180):
        mid = (lo + hi) / 2
        if mid == lo or mid == hi:
            return mid
        if fun(mid) > 0:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


def ingredients(m, sigma, beta):
    v = sigma - 1.0
    D = m if v == 0 else -expm1(-beta * v * m) / (beta * v)
    E = exp(beta * v * m)
    S = 1.0 - m + D * E
    return D, E, S


def block_from_m(m, sigma, beta):
    """H=1. Return X/H, Z/H, Z_H, Z_X, inverse-demand elasticity."""
    D, E, S = ingredients(m, sigma, beta)
    if sigma == 1.0:
        log_zh = beta * m * m / 2.0
        log_z = log_zh - log1p(-m)
    else:
        log_zh = log(S) / (sigma - 1.0)
        log_z = sigma * log_zh - log1p(-m)
    x = D * exp(sigma * beta * m) / (1.0 - m)
    z = exp(log_z)
    zh = exp(log_zh)
    zx = zh * exp(-beta * m)
    return x, z, zh, zx


def block(x, sigma, beta):
    if x == 0:
        return 0.0, 1.0, 1.0, 1.0
    def log_ratio(m):
        D, _, _ = ingredients(m, sigma, beta)
        return log(D) + sigma * beta * m - log1p(-m) - log(x)
    m = bisect_root(log_ratio, 1e-16, 1 - 1e-13)
    _, z, zh, zx = block_from_m(m, sigma, beta)
    return m, z, zh, zx


def partition_value(m, x, sigma, beta):
    """Efficient allocation within a FIXED exclusive task partition, H=1."""
    D, _, _ = ingredients(m, sigma, beta)
    if sigma == 1:
        # log Z = m log(X/m) + (1-m) log(H/(1-m)) - beta*m^2/2.
        return exp(m * log(x / m) - (1-m) * log(1-m) - beta*m*m/2)
    rho = (sigma-1) / sigma
    return ((1-m)**(1/sigma) + D**(1/sigma) * x**rho)**(1/rho)


def c_ai(sigma, beta):
    if sigma == 1:
        return exp(-beta / 2)
    D, _, _ = ingredients(1.0, sigma, beta)
    return D**(1/(sigma-1))


def inverse_price(m, sigma, beta, alpha, k_h):
    x, z, _, zx = block_from_m(m, sigma, beta)
    return (1-alpha) * k_h**alpha * z**(-alpha) * zx


def elasticity(m, sigma, beta, alpha):
    D, E, S = ingredients(m, sigma, beta)
    dlogz = sigma * beta * D * E / S + 1/(1-m)
    dlogx = exp(-beta*(sigma-1)*m)/D + sigma*beta + 1/(1-m)
    return (alpha*dlogz + beta*(1-m)/S) / dlogx


def main():
    checks = {k: 0.0 for k in [
        'max_relative_euler_error', 'max_relative_zx_fd_error',
        'max_relative_zh_fd_error', 'max_relative_partition_error',
        'max_positive_partition_gain', 'max_log_wage_price_boundary_error',
        'max_relative_inverse_elasticity_fd_error',
    ]}
    alpha, beta, kh = 0.33, 2.0, 3.0
    count = 0
    for sigma in [0.6, 0.9, 1.0, 1.1, 1.5, 3.5]:
        for m in [0.001, 0.02, 0.2, 0.5, 0.8, 0.98, 0.999]:
            x, z, zh, zx = block_from_m(m, sigma, beta)
            checks['max_relative_euler_error'] = max(
                checks['max_relative_euler_error'], abs((zh+zx*x)/z-1))
            eps = 1e-5
            zx_fd = (block(x*(1+eps),sigma,beta)[1] - block(x*(1-eps),sigma,beta)[1])/(2*eps*x)
            # Envelope theorem: hold the optimal task partition fixed for this
            # partial derivative, avoiding root-resolution cancellation near m=1.
            zh_fd = ((1+eps)*partition_value(m,x/(1+eps),sigma,beta) - (1-eps)*partition_value(m,x/(1-eps),sigma,beta))/(2*eps)
            checks['max_relative_zx_fd_error'] = max(checks['max_relative_zx_fd_error'],abs(zx_fd/zx-1))
            checks['max_relative_zh_fd_error'] = max(checks['max_relative_zh_fd_error'],abs(zh_fd/zh-1))
            checks['max_relative_partition_error'] = max(checks['max_relative_partition_error'],abs(partition_value(m,x,sigma,beta)/z-1))
            grid = np.unique(np.r_[np.linspace(1e-5,1-1e-5,401),m])
            gain = max(partition_value(v,x,sigma,beta)/z-1 for v in grid)
            checks['max_positive_partition_gain'] = max(checks['max_positive_partition_gain'],gain)
            checks['max_log_wage_price_boundary_error'] = max(checks['max_log_wage_price_boundary_error'],abs(log(zh/zx)-beta*m))
            dm = min(m,1-m)*1e-4
            xlo = block_from_m(m-dm,sigma,beta)[0]
            xhi = block_from_m(m+dm,sigma,beta)[0]
            e_fd = -log(inverse_price(m+dm,sigma,beta,alpha,kh)/inverse_price(m-dm,sigma,beta,alpha,kh))/log(xhi/xlo)
            checks['max_relative_inverse_elasticity_fd_error'] = max(checks['max_relative_inverse_elasticity_fd_error'],abs(e_fd/elasticity(m,sigma,beta,alpha)-1))
            count += 1
    limits = []
    for sigma in [0.6,0.9,1.0,1.1,1.5,3.5]:
        x,z,zh,zx = block_from_m(1-1e-8,sigma,beta)
        c = c_ai(sigma,beta)
        limits.append({'sigma':sigma,'c_sigma':c,'z_over_x':z/x,'zx':zx,
                       'w_over_ApX':zh/zx,'limit_w_over_ApX':exp(beta),
                       'inverse_demand_elasticity':elasticity(1-1e-8,sigma,beta,alpha)})
        assert abs(z/x/c-1) < 1e-6
        assert abs(zx/c-1) < 1e-6
        assert abs(elasticity(1-1e-8,sigma,beta,alpha)-alpha) < 1e-6
    print('Diagnostic residuals:', json.dumps(checks))
    assert checks['max_relative_euler_error'] < 1e-10
    assert checks['max_relative_zx_fd_error'] < 2e-5
    assert checks['max_relative_zh_fd_error'] < 2e-5
    assert checks['max_relative_partition_error'] < 1e-10
    assert checks['max_positive_partition_gain'] < 1e-10
    assert checks['max_log_wage_price_boundary_error'] < 1e-10
    assert checks['max_relative_inverse_elasticity_fd_error'] < 1e-5
    result = {'status':'PASS','cases':count,'checks':checks,'limits':limits,
              'scope':'Static identities and asymptotics, not dynamic equilibrium existence or novelty.'}
    target = Path(__file__).with_name('static_checks.json')
    target.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__ == '__main__':
    main()
