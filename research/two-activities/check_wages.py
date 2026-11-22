"""Static price, allocation and limiting checks. Not dynamic simulations."""
import json
from math import log, exp
from pathlib import Path


def sector(Q,p,sigma,omega=.5):
    r=(sigma-1)/sigma
    denom=(p/(Q*omega))**(sigma-1)-omega
    assert denom>0
    x=(omega/denom)**(1/r)
    z=(omega+omega*x**r)**(1/r)
    zh=omega*z**(1/sigma)
    zx=omega*(z/x)**(1/sigma)
    wage=Q*zh
    dual=((Q**(1-sigma)-omega**sigma*p**(1-sigma))/omega**sigma)**(1/(1-sigma))
    return dict(x=x,z=z,wage=wage,price_error=abs(Q*zx/p-1),
                dual_error=abs(wage/dual-1),euler_error=abs((zh+zx*x)/z-1))


def main():
    p,alpha=.1,.33
    records=[]
    maxerror=0.
    for sigS in [1.1,1.5,3.]:
        cs=.5**(sigS/(sigS-1))
        qstar=p/cs
        for sigC in [.5,.9]:
            target=((qstar**(1-sigC)-.5**sigC*p**(1-sigC))/.5**sigC)**(1/(1-sigC))
            rows=[]
            for gap in [1e-2,1e-4,1e-6]:
                Q=qstar*(1-gap)
                S=sector(Q,p,sigS)
                C=sector(Q,p,sigC)
                kappa=(Q/(1-alpha))**(1/alpha)
                zs,zc=S['z'],C['z']
                ks,kc=kappa*zs,kappa*zc
                ys,yc=ks**alpha*zs**(1-alpha),kc**alpha*zc**(1-alpha)
                allocation_error=abs((ys+yc)/((ks+kc)**alpha*(zs+zc)**(1-alpha))-1)
                maxerror=max(maxerror,allocation_error,*[S[k] for k in ['price_error','dual_error','euler_error']],*[C[k] for k in ['price_error','dual_error','euler_error']])
                rows.append(dict(gap=gap,wS_over_A=S['wage'],wC_over_A=C['wage'],
                                 wC_limit=target,Yc_share=yc/(ys+yc),
                                 wage_growth_identity_error=abs(log(S['wage']/Q/.5)-log(zs)/sigS)))
            assert abs(rows[-1]['wC_over_A']/target-1)<1e-4
            assert rows[-1]['wS_over_A']>rows[0]['wS_over_A']
            assert rows[-1]['Yc_share']<rows[0]['Yc_share']
            records.append(dict(sigma_S=sigS,sigma_C=sigC,rows=rows))
    assert maxerror<1e-7
    out=dict(status='PASS',max_identity_error=maxerror,cases=records,
             scope='Static common-price allocations and conditional asymptotic wage formulas, not equilibrium existence or transitions.')
    Path(__file__).with_name('wage_checks.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
    print(json.dumps(out,indent=2))


if __name__=='__main__':
    main()
