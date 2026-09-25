import math, sys
sys.path.insert(0,'.')
from fractions import Fraction as F
from anko.core.interp import Interp
from anko.core.values import *
from anko.core.parser import parse

def ev(t, **kw):
    i = Interp(); i.complex_mode = kw.pop('cx', False)
    for k,v in kw.items(): setattr(i.s,k,v)
    return i.evaluate(t)

def show(v):
    if isinstance(v, Exact): return ('E', {k:str(c) for k,c in v.t.items()})
    if isinstance(v, CNum): return ('C', show(v.re), show(v.im))
    return v

cases = [
 ("1/3+1/6", F(1,2)), ("2+3*4", F(14)), ("2^10", F(1024)), ("-2^2", F(-4)),
 ("6/2(1+2)", F(1)), ("sqrt(8)", None), ("sin(30)", F(1,2)), ("cos(60)", F(1,2)),
 ("tan(45)", F(1)), ("sin(180)", F(0)), ("asin(1/2)", F(30)), ("5!", F(120)),
 ("nCr(5,2)", None), ("ncr(5,2)", F(10)), ("npr(5,2)", F(20)), ("gcd(12,18)", F(6)),
 ("(-8)^(1/3)", F(-2)), ("0.1+0.2", None), ("50%", F(1,2)), ("2°30'0\"", F(5,2)),
 ("log(1000)", F(3)), ("logb(2,32)", F(5)), ("ln(1)", F(0)), ("abs(-5)", F(5)),
 ("integ(x^2,0,1)", None), ("deriv(x^3,2)", None), ("sigma(x,x,1,10)", F(55)),
 ("prod(x,x,1,5)", F(120)), ("1+2=3", True), ("A=5", F(5)), ("A*2", F(10)),
]
for t, exp in cases:
    try: r = ev(t)
    except Exception as e: r = f"ERR {type(e).__name__}: {e}"
    ok = "" if exp is None else ("OK" if r == exp else "FAIL")
    print(f"{t:22} -> {show(r)} {ok}")
i=Interp(); i.s.angle='RAD'
print('rad sin(pi/6):', i.evaluate('sin(pi/6)'), ' sin(pi):', i.evaluate('sin(pi)'), 'cos(pi/4):', show(i.evaluate('cos(pi/4)')))
print('asin(1) rad:', show(i.evaluate('asin(1)')))
c=Interp(); c.complex_mode=True
print('cx', show(c.evaluate('(1+2i)(3-i)')), show(c.evaluate('sqrt(-4)')), show(c.evaluate('2∠60')), show(c.evaluate('arg(1+i)')))
print('solve', ev('1')==1, Interp().solve('x^2-2=0','x',1.0), Interp().solve('cos(x)=x','x',0))
print('sqrt2*sqrt3', show(ev('sqrt(2)*sqrt(3)')), show(ev('1/(1+sqrt(2))')), show(ev('2pi/3')))
for bad in ['1/0','sqrt(-1)','5!!!','(1+','2**','ln(0)','tan(90)','70!']:
    try: print(bad, '->', ev(bad))
    except Exception as e: print(bad, '-> ', type(e).__name__, e)
