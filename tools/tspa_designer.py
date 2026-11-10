#!/usr/bin/env python3
"""tSPA designer: process window and allowable pressure for heat-sealed textile
soft pneumatic actuators, following Zournatzis et al. (see README / CITATION.cff).

Usage examples:
  python tspa_designer.py --denier 420 --w 4 --dinc 60
  python tspa_designer.py --fabric "Red Lipstick 210D" --w 3 --dinc 80 --elongated --sf 2
"""
import argparse, math

N_CRIT = {"Navy Blue 70D": 5.52, "Red Lipstick 210D": 5.45, "Light Blue 420D": 7.63, "Blue 840D": 10.38}
DENIER = {"Navy Blue 70D": 70, "Red Lipstick 210D": 210, "Light Blue 420D": 420, "Blue 840D": 840}
WINDOW = {"Red Lipstick 210D": (162, "0.6-0.75"), "Light Blue 420D": (154, "0.5-0.65"), "Blue 840D": (147, "any (>=0.5 tested)")}
K, KS_ELONG, T_MAX = 1.05, 1.19, 175.0

def n_crit_from_denier(d):            # double-sided TPU-coated nylon, 210-840 D
    return 7.6 * (d / 420.0) ** 0.46

def t_min_from_denier(d):             # minimum sealing temperature [degC]
    return 154.0 - 7.6 * math.log2(d / 420.0)

def phi_w(w):                          # seam-width factor (=1 at w = 4 mm)
    return (1 - math.exp(-K * w)) / (1 - math.exp(-4 * K))

def failure_pressure_kPa(n_crit, w, dinc, elongated=False):
    ks = KS_ELONG if elongated else 1.0
    return 4 * n_crit * phi_w(w) / (ks * dinc) * 1000.0

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--fabric", choices=list(N_CRIT), help="tested fabric")
    g.add_argument("--denier", type=float, help="double-sided TPU-coated nylon, 210-840 D (interpolation laws)")
    ap.add_argument("--w", type=float, default=4.0, help="seam width [mm] (2-8)")
    ap.add_argument("--dinc", type=float, required=True, help="maximum inscribed circle of the chamber [mm] (60-100 validated)")
    ap.add_argument("--elongated", action="store_true", help="chamber aspect ratio >= 2")
    ap.add_argument("--sf", type=float, default=1.0, help="safety factor applied to the failure pressure")
    a = ap.parse_args()
    warn = []
    if a.fabric:
        d = DENIER[a.fabric]; n = N_CRIT[a.fabric]
        if a.fabric in WINDOW:
            tmin, pmin = WINDOW[a.fabric]
            print(f"Process window (t = 110 s): T = {tmin}-{T_MAX:.0f} degC, P >= {pmin} MPa")
        else:
            print("Process window: not defined (single-sided fabric; substrate-limited)")
        if "840D" in a.fabric: warn.append("N_crit of 840D is a lower bound (fitting failures).")
    else:
        d = a.denier; n = n_crit_from_denier(d)
        if not 210 <= d <= 840: warn.append("denier outside 210-840 D: interpolation laws not validated.")
        tmin = t_min_from_denier(d); pmin = 0.6 if d <= 300 else 0.5
        print(f"Process window (t = 110 s, estimated): T = {min(tmin, T_MAX):.0f}-{T_MAX:.0f} degC, P >= {pmin} MPa")
        if tmin >= T_MAX: warn.append("estimated window is empty (T_min >= 175 degC).")
    if not 2 <= a.w <= 8: warn.append("seam width outside the tested 2-8 mm range.")
    if not 60 <= a.dinc <= 100: warn.append("D_inc outside the validated 60-100 mm range.")
    if a.w < 3: warn.append("w < 3 mm: below the critical seam width (~2.9 mm).")
    pf = failure_pressure_kPa(n, a.w, a.dinc, a.elongated)
    print(f"N_crit = {n:.2f} N/mm | predicted failure pressure P_f = {pf:.0f} kPa | allowable (SF {a.sf:g}) = {pf / a.sf:.0f} kPa")
    for m in warn: print("WARNING:", m)

if __name__ == "__main__":
    main()
