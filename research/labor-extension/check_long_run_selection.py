"""Static global-candidate searches at rising K/H, not dynamic simulations."""
from math import exp,log
from pathlib import Path
import json
import numpy as np
from check_joint_supply import joint,golden_max


def solve(K,B,sigC):
    cs=.125
    def objective(t):
        o=joint(cs*(1+exp(t)),K=K,sigC=sigC)
        return (o['P']-1/B)*o['X']/K
    grid=np.unique(np.r_[np.linspace(-25,12,12001),log((.5**(sigC/(sigC-1)))/cs-1)])
    values=[objective(float(t)) for t in grid]
    candidates=[]
    for i in range(1,len(grid)-1):
        if values[i]>values[i-1] and values[i]>values[i+1]:
            t,profit=golden_max(objective,float(grid[i-1]),float(grid[i+1]))
            o=joint(cs*(1+exp(t)),K=K,sigC=sigC)
            candidates.append((profit,o))
    assert candidates
    profit,o=max(candidates,key=lambda z:z[0])
    # Endpoint checks detect a search that has not covered the optimum.
    assert profit>0 and profit>values[0] and profit>values[-1]
    return profit,o,len(candidates)


def main():
    alpha,B,cs=.33,8.,.125
    target=(B*(1-alpha)**2*cs**(1-alpha))**(1/alpha)
    target_price=1/(B*(1-alpha))
    target_Q=target_price/cs
    records=[]
    for sigC in [.25,.9]:
        wageCtarget=((target_Q**(1-sigC)-.5**sigC*target_price**(1-sigC))/.5**sigC)**(1/(1-sigC))
        rows=[]
        for K in [1e2,1e4,1e6,1e8]:
            profit,o,count=solve(K,B,sigC)
            Q=(1-alpha)*(K/o['G'])**alpha
            zC=o['C']['z']
            wC=Q*.5*zC**(1/sigC)
            rows.append(dict(K_over_H=K/2,X_over_K=o['X']/K,
                relative_supply_error=abs(o['X']/K/target-1),price=o['P'],
                relative_price_error=abs(o['P']/target_price-1),
                wC_over_A=wC,relative_wC_error=abs(wC/wageCtarget-1),
                local_candidates=count,profit_over_K=profit))
        assert rows[-1]['relative_supply_error']<.01
        assert rows[-1]['relative_price_error']<.01
        assert rows[-1]['relative_wC_error']<.01
        assert rows[-1]['local_candidates']==1
        records.append(dict(sigma_C=sigC,rows=rows))
    out=dict(status='PASS',target_X_over_K=target,target_price=target_price,
             cases=records,scope='Static candidate comparison and limit checks. The proof, not the numerical grid, establishes eventual uniqueness. No dynamic existence, research optimality or transition test.')
    Path(__file__).with_name('long_run_checks.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
    print(json.dumps(out,indent=2))


if __name__=='__main__':
    main()
