"""Verifies the explorer's in-browser computations against the replication results of the paper.

Runs the page in headless Chromium (Playwright), calls the page's own functions (window.__p6) and
compares 44 values with results/doctrine_results.json and results/stochastic_results.json of the
replication package; 12 further checks read the page as it opens (pressed presets, slider values,
readout) and compare the readout with an independent Python computation from the package's
code/population.py.

    pip install playwright numpy scipy && python -m playwright install chromium
    python verify/verify_explorer.py --package /path/to/unpacked/replication/package
    python verify/verify_explorer.py --package ... --url https://tafew.github.io/doctrine-fixed-point/

Exit 0 when every check agrees; the table is written to verify/explorer_check.json.
"""
import argparse, json, math, pathlib, sys
from playwright.sync_api import sync_playwright
HERE = pathlib.Path(__file__).resolve().parent
ap = argparse.ArgumentParser()
ap.add_argument("--package", required=True, help="root of the unpacked replication package (results/, code/)")
ap.add_argument("--url", default=(HERE.parent / "index.html").as_uri(), help="page to test (default: ../index.html)")
ap.add_argument("--out", default=str(HERE / "explorer_check.json"))
A = ap.parse_args()
PKG = pathlib.Path(A.package).resolve()
J = json.load(open(PKG / "results" / "doctrine_results.json")); S = json.load(open(PKG / "results" / "stochastic_results.json"))
JS = r"""
() => {
  const P6 = window.__p6, base = {lam:3, c:2.134908073838304, h:0.20, sg:0.20, l1:1.5};
  const q = (o) => Object.assign({}, base, o);
  const fpv = (p, N) => P6.fixedPoints(P6.M(p), N).map(f => f.m);
  const out = {};
  out.fp_uk = fpv(base);
  out.fp_de = fpv(q({lam:24}), 8000); out.fp_at = fpv(q({lam:1})); out.fp_l2 = fpv(q({lam:2}));
  out.fp_h15 = fpv(q({h:0.15, c:2.0978})); out.fp_h10 = fpv(q({h:0.10, c:2.0727}));
  out.ld = P6.lambdaDagger(P6.M(base));
  const fo = P6.folds(base); out.folds = [fo.lo, fo.hi];
  const cs = P6.maxwell(base, fo); out.cstar = cs;
  const o = P6.M(base), r = P6.roles(P6.fixedPoints(o));
  out.dUL = o.U(r.mu) - o.U(r.mL); out.dUH = o.U(r.mu) - o.U(r.mH);
  out.tauL = {}; [0.05,0.10,0.15,0.20].forEach(s => out.tauL[s] = P6.logMFPT(o, s, r.mL, r.mu)/Math.LN10);
  out.exitAtCstar = {};
  [0.10,0.20,0.2763].forEach(s => { const oc = P6.M(q({c:2.5+1e-6})), rc = P6.roles(P6.fixedPoints(oc,3000));
     out.exitAtCstar[s] = P6.logMFPT(oc, s, rc.mH, rc.mu)/Math.LN10; });
  out.cdag = {}; [0.10,0.20,0.2763].forEach(s => { const pp = q({sg:s}); const f2 = P6.folds(pp); out.cdag[s] = P6.cDagger(pp, P6.maxwell(pp, f2), f2); });
  out.fuse = {}; [1.0,1.5,1.7,1.74,1.76,1.764,1.765,1.8].forEach(l => out.fuse[l] = P6.fuse(o, r, l));
  out.edge = P6.admissibleEdge(0.20);
  const f4 = P6.folds(q({lam:4})); out.cstar4 = P6.maxwell(q({lam:4}), f4);
  const f2l = P6.folds(q({lam:2})); out.cstar2 = P6.maxwell(q({lam:2}), f2l);
  return out;
}
"""
with sync_playwright() as pw:
    b = pw.chromium.launch()
    pg = b.new_page(viewport={"width": 1280, "height": 1800})
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("console", lambda m: errs.append("console:" + m.text) if m.type == "error" else None)
    pg.goto(A.url)
    pg.wait_for_timeout(1500)
    R = pg.evaluate(JS)
    read = {i: pg.inner_text("#" + i) for i in ["r-regime","r-ratio","r-fp","r-mu","r-folds","r-cstar","r-cdag","r-tauL","r-tauH","r-fuse"]}
    pressed = pg.eval_on_selector_all('button.chip[aria-pressed="true"]', "els => els.map(e => e.textContent.trim())")
    sliders = {i: pg.eval_on_selector("#" + i, "e => parseFloat(e.value)") for i in ["s-lam","s-c","s-h","s-sg","s-l1"]}
    shown = {i: pg.inner_text("#" + i) for i in ["v-lam","v-c","v-h","v-sg","v-l1"]}
    b.close()
print("page:", A.url)
print("page errors:", [e for e in errs if "fonts.g" not in e and "ERR_TUNNEL" not in e])
rows = []
def chk(name, got, want, tol):
    ok = abs(got - want) <= tol; rows.append((name, got, want, ok)); return ok
fj = J["baseline_UK"]["fixed_points"]
for a, w in zip(R["fp_uk"], fj): chk("England FP", a, w, 1e-4)
for a, w in zip(R["fp_de"], [1.0, 1.5314, 25.0]): chk("Germany FP", a, w, 1e-4)
chk("Austria #FP", len(R["fp_at"]), 1, 0); chk("Austria FP", R["fp_at"][0], 1.0, 0)
for a, w in zip(R["fp_l2"], [1.0, 2.2001, 2.7999]): chk("lambar=2 FP", a, w, 1e-4)
for a, w in zip(R["fp_h15"], [1.0, 1.8537, 4.0]): chk("range [0.25,0.55] FP", a, w, 2e-4)
for a, w in zip(R["fp_h10"], [1.0, 1.9313, 4.0]): chk("range [0.30,0.50] FP", a, w, 2e-4)
chk("lambda dagger", R["ld"], J["baseline_UK"]["lambda_dagger"], 1e-4)
chk("fold low", R["folds"][0], J["hysteresis"]["c_fold_low"], 1e-4)
chk("fold high", R["folds"][1], J["hysteresis"]["c_fold_high"], 1e-4)
chk("Maxwell c* (closed)", R["cstar"]["c"], 2.5, 1e-12)
chk("barrier out of compensation", R["dUL"], S["potential"]["barrier_out_of_low"], 1e-5)
chk("barrier out of permissive well", R["dUH"], S["potential"]["barrier_out_of_high"], 1e-5)
tab = {r["sigma"]: r["log10_tau_exact"] for r in S["mfpt"]["table"]}
for s in (0.05, 0.10, 0.15, 0.20): chk(f"log10 recovery sigma={s}", R["tauL"][str(s) if str(s) in R["tauL"] else s] if False else R["tauL"][{0.05:"0.05",0.10:"0.1",0.15:"0.15",0.20:"0.2"}[s]], tab[s], 0.01)
ex = S["policy_threshold"]["log10_exit_time_of_permissive_doctrine_at_cstar"]
for s, k in ((0.10, "0.1"), (0.20, "0.2"), (0.2763, "0.2763")): chk(f"log10 exit at c* sigma={s}", R["exitAtCstar"][k], ex[k], 0.02)
cd = S["policy_threshold"]["c_dagger"]
for k in ("0.1", "0.2", "0.2763"): chk(f"c-dagger(sigma={k},30)", R["cdag"][k]["c"], cd[k]["30"], 2e-3)
for l, t in ((1.0, 2), (1.5, 3), (1.7, 4), (1.74, 5), (1.76, 8), (1.764, 10), (1.765, 14)):
    key = str(l) if str(l) in R["fuse"] else str(int(l)) if l == int(l) else str(l)
    chk(f"fuse t* at {l}", R["fuse"][key]["t"], t, 0)
ok18 = R["fuse"]["1.8"]["kind"] == "reversed"; rows.append(("fuse at 1.80 reversed", R["fuse"]["1.8"]["kind"], "reversed", ok18))
chk("admissible edge", R["edge"], 1.66432, 1e-5)
chk("Maxwell lambar=4 (closed)", R["cstar4"]["c"], 3.0, 1e-12)
rows.append(("Maxwell lambar=2 route", "closed" if R["cstar2"]["closed"] else "numerical", "numerical (support not inside at c*)", not R["cstar2"]["closed"]))
# ---- start state (23 Sep 2026): the page opens at England & India, Maxwell point c = 2.5.
# Expected readout computed independently in Python from v6/code/population.py.
sys.path.insert(0, str(PKG / "code"))
from population import BASE, make_D, fixed_points as py_fp, lambda_dagger as py_ld
_pop = BASE.at_mean(2.5); _fp = py_fp(make_D(3.0, _pop), lam=3.0); _ld = py_ld(_pop)[0]
def eq(name, got, want): rows.append((name, got, want, got == want))
eq("start: pressed chips", pressed, ["England & India", "Maxwell point 2.50"])
eq("start: sliders", sliders, {"s-lam": 3.0, "s-c": 2.5, "s-h": 0.2, "s-sg": 0.2, "s-l1": 1.5})
eq("start: shown values", shown, {"v-lam": "3.00", "v-c": "2.500", "v-h": "0.200", "v-sg": "0.200", "v-l1": "1.500"})
eq("start: regime", read["r-regime"].strip(), "multiple")
eq("start: equilibria (population.py)", read["r-fp"], " · ".join(f"{float(x):.3f}" for x in _fp))
eq("start: watershed (population.py)", read["r-mu"], f"{float(_fp[1]):.3f}")
import re  # inner_text joins the value and its unit span without a space
eq("start: lambar/lambar-dagger (population.py)", re.fullmatch(r"([\d.]+)λ̄† ([\d.]+)", read["r-ratio"]).groups(), (f"{3.0/_ld:.2f}", f"{_ld:.3f}"))
eq("start: folds (results)", read["r-folds"], f'{J["hysteresis"]["c_fold_low"]:.3f} / {J["hysteresis"]["c_fold_high"]:.3f}')
eq("start: Maxwell point, closed form", read["r-cstar"], "2.500" + "1 + λ̄/2")
eq("start: c-dagger(0.2, 30) (results)", read["r-cdag"], f'{cd["0.2"]["30"]:.3f}')
eq("start: exit of permissive doctrine at c* (results)", read["r-tauH"], f'10{ex["0.2"]:.1f}periods')
eq("start: fuse", read["r-fuse"], "2periods")
bad = [r for r in rows if not r[3]]
for r in rows: print(("OK  " if r[3] else "BAD ") + f"{r[0]}: got {r[1]}, want {r[2]}")
print("\nreadout:", json.dumps(read, ensure_ascii=False))
print(f"\n{len(rows) - len(bad)}/{len(rows)} checks agree")
json.dump({"page": A.url, "rows": [list(map(str, r)) for r in rows], "readout": read, "lambar2_maxwell": R["cstar2"]}, open(A.out, "w"), ensure_ascii=False, indent=1)
sys.exit(1 if bad else 0)
