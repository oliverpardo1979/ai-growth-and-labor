"""Static checks for the sufficient all-S allocation threshold."""
from math import log
from pathlib import Path
import json
import numpy as np


def ces(h,x,sigma):
    if sigma<1 and (h==0 or x==0):
        return 0.
    r=(sigma-1)/sigma
    return (.5*h**r+.5*x**r)**(1/r)


def main():
    records=[]
    for sS in [1.5,3.]:
        for sC in [.25,.5,.9]:
            bL=.5**(sC/(sC-1))
            rS=(sS-1)/sS
            threshold=(((bL/.5)**(sS-1)-.5)/.5)**(1/rS)
            rows=[]
            for multiplier in [1.01,2.,10.]:
                X=threshold*multiplier
                allS=ces(1.,X,sS)
                mpS=.5*allS**(1/sS)
                assert mpS>bL
                max_gain=-1e99
                max_bound_violation=0.
                for hc in np.linspace(0,1,101):
                    for ai_share in np.linspace(0,1,101):
                        xc=X*ai_share
                        alt=ces(1-hc,X-xc,sS)+ces(hc,xc,sC)
                        bound=allS-(mpS-bL)*hc
                        max_gain=max(max_gain,alt/allS-1)
                        max_bound_violation=max(max_bound_violation,(alt-bound)/allS)
                assert max_gain<1e-10
                assert max_bound_violation<1e-10
                rows.append(dict(X_over_H=X,max_relative_alternative_gain=max_gain,
                                 max_relative_bound_violation=max_bound_violation))
            records.append(dict(sigma_S=sS,sigma_C=sC,threshold=threshold,rows=rows))
    out=dict(status='PASS',cases=records,scope='Static checks of a proved sufficient threshold. Not a necessary threshold, a transition simulation or an existence proof.')
    Path(__file__).with_name('mobile_labor_checks.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
    print(json.dumps(out,indent=2))


if __name__=='__main__':
    main()
