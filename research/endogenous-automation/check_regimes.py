"""Algebraic and stationary-allocation checks, not dynamic simulations."""
import json
from math import exp
from pathlib import Path
from check_task_block import block_from_m, c_ai, bisect_root


def main():
    alpha, beta, rho, gamma, delta, n = .33, 2., .04, .01, .05, .01
    Rstar = rho + gamma + delta
    a = (alpha/Rstar)**(1/(1-alpha))
    Ba = 1/((1-alpha)*a**alpha)
    cases = []
    max_error = 0.
    for sigma in [.6, .9, 1., 1.1, 1.5, 3.5]:
        c = c_ai(sigma, beta)
        Bg = Ba/c
        B = (Ba+Bg)/2
        m = bisect_root(lambda v: Ba/B-block_from_m(v,sigma,beta)[3],
                        1e-10,1-1e-10)
        x,z,zh,zx = block_from_m(m,sigma,beta)
        k = a*z
        y = k**alpha*z**(1-alpha)
        u = x/B
        consumption = y-u-(delta+n+gamma)*k
        r = alpha*y/k-delta
        p = (1-alpha)*(k/z)**alpha*zx
        wage = (1-alpha)*(k/z)**alpha*zh
        errors = [abs(r-rho-gamma),abs(p*B-1),
                  abs((alpha*y+(1-alpha)*(k/z)**alpha*zh+p*x)/y-1),
                  abs(wage*B/exp(beta*m)-1)]
        max_error=max(max_error,*errors)
        assert consumption/k>rho-n
        def ret(Bvalue,lam):
            return alpha*(Bvalue*lam*(1-alpha)*c)**((1-alpha)/alpha)-delta
        assert abs(ret(Bg,1)-rho-gamma)<1e-12
        assert abs(ret(Bg/(1-alpha),1-alpha)-rho-gamma)<1e-12
        assert ret(1.1*Bg,1)>rho+gamma
        assert ret(.9*Bg,1)<rho+gamma
        cases.append(dict(sigma=sigma,Ba=Ba,Bg_mc=Bg,Bg_mon=Bg/(1-alpha),
                          B_coexistence=B,m=m,k=k,x=x,r=r,
                          consumption_over_K=consumption/k))
    assert max_error<1e-10
    means=[c_ai(s, beta) for s in [.01,.1,.6,.9,1.,1.1,1.5,3.5,10.,100.]]
    assert all(b>a for a,b in zip(means,means[1:]))
    out=dict(status='PASS',max_identity_error=max_error,cases=cases,
             scope='Stationary competitive allocations and conditional return thresholds only. No monopoly dynamic existence test.')
    Path(__file__).with_name('regime_checks.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
    print(json.dumps(out,indent=2))


if __name__=='__main__':
    main()
