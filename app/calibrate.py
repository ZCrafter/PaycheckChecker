"""Helper: turn numbers from ONE paystub into values for your .env file.

Example:
  python -m app.calibrate --gross 2400 --net 1830.55 --taxes 310.20 --health 85 --k401 120
    --taxes = federal + state + local income tax withheld (NOT social security/medicare)
    --health = pre-tax health/dental/vision deducted
    --k401  = traditional 401k dollars deducted (use 0 if Roth or none)
"""
import argparse

from . import pay
from .config import load

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--gross", type=float, required=True)
ap.add_argument("--net", type=float, required=True)
ap.add_argument("--taxes", type=float, required=True, help="fed+state+local income tax withheld")
ap.add_argument("--health", type=float, default=0.0)
ap.add_argument("--k401", type=float, default=0.0)
a = ap.parse_args()

taxable = a.gross - a.health - a.k401
print(f"NET_RATIO={a.net / a.gross:.4f}")
print(f"EFFECTIVE_TAX_RATE={a.taxes / taxable:.4f}")
print(f"HEALTH_PRETAX={a.health:.2f}")
if a.k401:
    print(f"K401_PCT={a.k401 / a.gross:.4f}")

c = load()
est = pay.expected_net(a.gross, c)
print(f"\nWith your CURRENT .env, gross {a.gross:.2f} gives expected net {est:.2f} "
      f"(stub says {a.net:.2f}, difference {est - a.net:+.2f}).")
