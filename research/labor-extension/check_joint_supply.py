"""Static two-activity supply checks. No equilibrium transition simulation."""
import json
from math import exp, log
from pathlib import Path
import numpy as np


def ces_at_mu(mu,H,sigma,wL=.5,wX=.5):
    if sigma<1 and mu>=wX**(sigma/(sigma-1)):
        return dict(x=0.,z=0.,dx=0.)
    power=(sigma-1)/sigma
    d=(mu/wX)**(sigma-1)-wX
    x=H*(wL/d)**(1/power)
    z=H*(wL+wX*(x/H)**power)**(1/power)
    shareL=wL*(H/z)**power
    dx=-sigma*x/(mu*shareL)
    return dict(x=x,z=z,dx=dx)


def joint(mu,alpha=.33,K=1.,HS=1.,HC=1.,sigS=1.5,sigC=.25):
    S=ces_at_mu(mu,HS,sigS)
    C=ces_at_mu(mu,HC,sigC)
    X=S['x']+C['x']
    G=S['z']+C['z']
    Q=(1-alpha)*(K/G)**alpha
    P=Q*mu
    Gpp=1/(S['dx']+C['dx'])
    e=alpha*X*mu/G-X*Gpp/mu
    return dict(X=X,G=G,P=P,e=e,MR=P*(1-e),S=S,C=C)


def golden_max(fun,lo,hi):
    ratio=(5**.5-1)/2
    c=hi-ratio*(hi-lo)
    d=lo+ratio*(hi-lo)
    for _ in range(120):
        if fun(c)>fun(d):
            hi,d=d,c
            c=hi-ratio*(hi-lo)
        else:
            lo,c=c,d
            d=lo+ratio*(hi-lo)
    x=(lo+hi)/2
    return x,fun(x)


def main():
    alpha,sigS,sigC=.33,1.5,.25
    cs=.5**(sigS/(sigS-1))
    dc=.5**(sigC/(sigC-1))
    # At entry, C's right second derivative is zero for sigma_C<1/2.
    at=joint(dc)
    MR_before=at['MR']
    MR_after=at['P']*(1-alpha*at['X']*dc/at['G'])
    cost=(MR_before+MR_after)/2
    B=1/cost
    def obj(t):
        out=joint(cs*(1+exp(t)))
        return (out['P']-cost)*out['X']
    entry=log(dc/cs-1)
    grid=np.unique(np.r_[np.linspace(-18,18,20001),entry])
    vals=[obj(float(t)) for t in grid]
    maxima=[]
    for i in range(1,len(grid)-1):
        if vals[i]>vals[i-1] and vals[i]>vals[i+1]:
            t,v=golden_max(obj,float(grid[i-1]),float(grid[i+1]))
            o=joint(cs*(1+exp(t)))
            maxima.append(dict(mu=cs*(1+exp(t)),X=o['X'],profit=v,
                               marginal_revenue=o['MR'],unit_cost=cost,
                               XC=o['C']['x']))
    assert len(maxima)==2
    assert any(v['XC']==0 for v in maxima)
    assert any(v['XC']>0 for v in maxima)
    assert all(abs(v['marginal_revenue']/cost-1)<1e-5 for v in maxima)
    errors=[]
    for mu in [cs*1.001,.5,dc*.999,dc*1.001,3.,10.]:
        o=joint(mu)
        eps=1e-6
        lo,hi=joint(mu*(1-eps)),joint(mu*(1+eps))
        efd=-log(hi['P']/lo['P'])/log(hi['X']/lo['X'])
        errors.append(abs(efd-o['e']))
        for s in [o['S'],o['C']]:
            if s['x']>0:
                assert s['z']>0
        Kparts=[s['z']/o['G'] for s in [o['S'],o['C']]]
        ysum=sum(k**alpha*s['z']**(1-alpha) if k>0 else 0.
                 for k,s in zip(Kparts,[o['S'],o['C']]))
        assert abs(ysum/o['G']**(1-alpha)-1)<1e-12
    assert max(errors)<1e-6
    limit=joint(cs*(1+1e-8))
    assert abs(limit['G']/limit['X']/cs-1)<1e-6
    assert abs(limit['e']-alpha)<1e-6
    out=dict(status='PASS',parameters=dict(alpha=alpha,sigma_S=sigS,sigma_C=sigC,
               K=1,HS=1,HC=1,omega_L=.5,omega_X=.5,B=B),entry_mu=dc,
             entry_MR_before=MR_before,entry_MR_after=MR_after,
             maxima=maxima,max_elasticity_fd_error=max(errors),
             scope='Static counterexample to unimodality and verification of aggregation and demand. Not nonuniqueness of the global maximizer or dynamic equilibrium.')
    Path(__file__).with_name('joint_supply_checks.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
    print(json.dumps(out,indent=2))


if __name__=='__main__':
    main()
