# %% [markdown]
# # Deep hedging 101, on the desk's own trade
#
# A learning sandbox, not an experiment: no R2 data, nothing registered, no pass bar.
# It trains a Buehler-style deep hedger (Deep-Hedging.pdf) on simulated paths for the
# trade the desk's backtests point to:
#
#   short 1 ATM SPY put, entered at 30 calendar DTE (~21 trading days), hedged with shares
#   once a day at 10:15, closed at the 7-DTE exit (~5 trading days left) => 16 hedge days.
#
# Costs are the backtest's IBKR model (configs/backtest.toml): $0.005/share commission,
# $1 minimum per order, fills $0.005 from spot. The $1 minimum is what made the 10-share band
# pass (research/Deep_Hedging/2026-10-16-hedge-band), so it's the cost that matters here.
#
# Four lessons, one per cell block. Run the whole thing (`python deep_hedging_101.py`, ~3-5 min
# on a laptop CPU) or step through the `# %%` cells in VS Code / Jupyter.
#   L1  No costs, Black-Scholes world      -> the deep hedger should rediscover delta hedging.
#   L2  Desk costs, Black-Scholes world    -> does it learn a no-trade band? (It doesn't: see
#                                              the L2 cell. Gradient training can't "see" a
#                                              fixed $1 ticket. Worth understanding why.)
#   L3  Desk costs, Heston (vol moves,     -> where it can beat delta: it sees IV and the
#       spot-vol correlation -0.7)             leverage effect, which delta hedging ignores.
#   L4  Drift in the simulator             -> the objective decides hedger vs speculator.
#
# Figures and tables go to results/deep_hedging_sandbox/ (gitignored).

# %% Setup
import math
import pathlib
import time

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import torch
import torch.nn as nn

try:
    ROOT = pathlib.Path(__file__).resolve().parents[3]
except NameError:  # running cells interactively
    ROOT = pathlib.Path.cwd()
OUT = ROOT / "results" / "deep_hedging_sandbox"
OUT.mkdir(parents=True, exist_ok=True)

# Every number in one place. Change these and re-run: that's the point of the sandbox.
CFG = dict(
    S0=600.0, K=600.0,  # ATM put
    mult=100, contracts=1,  # short 1 contract
    dte_entry=21, hedge_days=16,  # trading days to expiry at entry; days hedged before exit
    commission_share=0.005, min_per_order=1.0, half_spread=0.005,  # backtest.toml, 1x
    n_train=200_000, n_test=100_000,
    batch=4096, iters=2000, lr=1e-3, hidden=64,
    max_adj=25.0,  # the net can move the hedge at most this many shares away from delta
    fee_smooth=0.5,  # shares; width of the smoothed $1 minimum used in training only
    gbm=dict(mu=0.0, sigma=0.18),
    heston=dict(mu=0.0, v0=0.03, kappa=3.0, theta=0.035, xi=0.6, rho=-0.7),
)
DT = 1 / 252
N = CFG["hedge_days"]
SIZE = CFG["mult"] * CFG["contracts"]
PHI = torch.distributions.Normal(0.0, 1.0)
torch.set_default_dtype(torch.float32)


# %% Market simulators
# Buehler's point: the policy only ever sees samples, so any simulator plugs in.
def simulate(model, n, seed, mu=None):
    """Return spot S [n, N+1] and the vol used to mark the option, iv [n, N+1]."""
    g = torch.Generator().manual_seed(seed)
    S = torch.empty(n, N + 1)
    iv = torch.empty(n, N + 1)
    S[:, 0] = CFG["S0"]
    if model == "gbm":
        p = CFG["gbm"]
        mu = p["mu"] if mu is None else mu
        z = torch.randn(n, N, generator=g)
        steps = (mu - 0.5 * p["sigma"] ** 2) * DT + p["sigma"] * math.sqrt(DT) * z
        S[:, 1:] = CFG["S0"] * torch.exp(torch.cumsum(steps, 1))
        iv[:] = p["sigma"]
    elif model == "heston":
        p = CFG["heston"]
        mu = p["mu"] if mu is None else mu
        v = torch.full((n,), p["v0"])
        iv[:, 0] = math.sqrt(p["v0"])
        for i in range(N):
            z1 = torch.randn(n, generator=g)
            z2 = p["rho"] * z1 + math.sqrt(1 - p["rho"] ** 2) * torch.randn(n, generator=g)
            vp = v.clamp(min=0.0)  # full-truncation Euler
            S[:, i + 1] = S[:, i] * torch.exp((mu - 0.5 * vp) * DT + torch.sqrt(vp * DT) * z1)
            v = v + p["kappa"] * (p["theta"] - vp) * DT + p["xi"] * torch.sqrt(vp * DT) * z2
            iv[:, i + 1] = torch.sqrt(v.clamp(min=1e-4))
    else:
        raise ValueError(model)
    return S, iv


def bs_put(S, tau, vol, K=CFG["K"]):
    """Black-Scholes put (r = 0): price, delta, gamma per share."""
    sd = vol * torch.sqrt(tau)
    d1 = (torch.log(S / K) + 0.5 * sd**2) / sd
    d2 = d1 - sd
    price = K * PHI.cdf(-d2) - S * PHI.cdf(-d1)
    delta = PHI.cdf(d1) - 1.0
    gamma = torch.exp(PHI.log_prob(d1)) / (S * sd)
    return price, delta, gamma


def make_paths(model, n, seed, mu=None):
    """Paths plus the marks every hedger needs. The option is marked with Black-Scholes at the
    path's vol (Cao et al. 2021, p. 1: the valuation model can be simpler than the simulator)."""
    S, iv = simulate(model, n, seed, mu)
    tau = (CFG["dte_entry"] - torch.arange(N + 1, dtype=torch.float32)) * DT
    P, D, G = bs_put(S, tau.expand_as(S), iv)
    return dict(S=S, iv=iv, P=P, D=D, G=G, tau=tau)


def subset(paths, idx):
    return {k: (v[idx] if k != "tau" else v) for k, v in paths.items()}


# %% Costs and the P&L of one hedging run
def cost(q, smooth=False, on=True):
    """IBKR cost of trading q shares. The $1 minimum is a jump at q = 0, which has zero gradient,
    so training uses a smooth version (1 - exp(-|q|/0.5) is ~$1 for any trade of a share or more).
    Evaluation always uses the exact desk rule on whole shares."""
    if not on:
        return torch.zeros_like(q)
    a = q.abs()
    per_share = (CFG["commission_share"] + CFG["half_spread"]) * a
    if smooth:
        return CFG["min_per_order"] * (1 - torch.exp(-a / CFG["fee_smooth"])) + per_share
    fee = torch.maximum(torch.full_like(a, CFG["min_per_order"]), CFG["commission_share"] * a)
    return torch.where(a >= 1, fee + CFG["half_spread"] * a, torch.zeros_like(a))


def run(policy, paths, train=False, costs=True):
    """Hedge every path for N days. Short put P&L + share P&L - hedge costs (incl. the unwind).
    Option commissions ($0.65 x 2) are the same for every hedger and are left out."""
    S = paths["S"]
    n = S.shape[0]
    h_prev = torch.zeros(n)
    hedge_pnl = torch.zeros(n)
    fees = torch.zeros(n)
    trades = torch.zeros(n)
    log = []  # (day, mismatch before trade, trade) for the no-trade-zone plots
    for i in range(N):
        h = policy(i, paths, h_prev)
        if not train:
            h = torch.round(h)
        q = h - h_prev
        fees = fees + cost(q, smooth=train, on=costs)
        trades = trades + (q.abs() >= 0.5).float()
        if not train:
            log.append((i, (h_prev - SIZE * paths["D"][:, i]), q))
        hedge_pnl = hedge_pnl + h * (S[:, i + 1] - S[:, i])
        h_prev = h
    fees = fees + cost(-h_prev, smooth=train, on=costs)  # flatten shares at the 7-DTE exit
    option_pnl = SIZE * (paths["P"][:, 0] - paths["P"][:, N])  # we sold the put
    return dict(pnl=option_pnl + hedge_pnl - fees, fees=fees, trades=trades, log=log)


# %% Baseline hedgers: the ones the deep hedger has to beat
def no_hedge(i, paths, h_prev):
    return torch.zeros_like(h_prev)


def delta_hedge(i, paths, h_prev):
    # Short put: book delta = -SIZE * put_delta > 0, so hold SIZE * put_delta shares (short).
    return SIZE * paths["D"][:, i]


def band_hedge(width):
    """Desk rule: re-hedge to delta only when the drift reaches `width` shares (band10 = 10)."""
    def policy(i, paths, h_prev):
        target = SIZE * paths["D"][:, i]
        return torch.where((target - h_prev).abs() >= width, target, h_prev)
    return policy


def ww_hedge(k):
    """The backtest's ww_band: width = max(1, k * sqrt(book gamma))."""
    def policy(i, paths, h_prev):
        target = SIZE * paths["D"][:, i]
        width = torch.clamp(k * torch.sqrt(SIZE * paths["G"][:, i]), min=1.0)
        return torch.where((target - h_prev).abs() >= width, target, h_prev)
    return policy


# %% The deep hedger
class DeepHedger(nn.Module):
    """Holding = delta hedge + a bounded, learned adjustment (the RL-hedger report's suggestion).
    The last layer starts at zero, so training begins exactly at delta hedging and only learns
    deviations. The previous holding is an input: without it the net can't know what a trade costs
    (Cao et al. 2021, p. 11)."""

    def __init__(self, hidden=CFG["hidden"], max_adj=CFG["max_adj"]):
        super().__init__()
        self.max_adj = max_adj
        self.net = nn.Sequential(
            nn.Linear(5, hidden), nn.SiLU(),
            nn.Linear(hidden, hidden), nn.SiLU(),
            nn.Linear(hidden, 1),
        )
        nn.init.zeros_(self.net[-1].weight)
        nn.init.zeros_(self.net[-1].bias)

    def forward(self, i, paths, h_prev):
        target = SIZE * paths["D"][:, i]
        tau = paths["tau"][i] / paths["tau"][0]
        x = torch.stack([
            torch.log(paths["S"][:, i] / CFG["K"]) / 0.05,  # moneyness
            paths["iv"][:, i] / 0.2 - 1,                     # vol level (what Heston adds)
            torch.full_like(h_prev, float(tau)),             # time left
            paths["D"][:, i],                                # BS delta
            (h_prev - target) / 10,                          # how far the book has drifted
        ], dim=1)
        return target + self.max_adj * torch.tanh(self.net(x).squeeze(-1))


def train(paths, objective="cvar", alpha=0.95, costs=True, label=""):
    """Buehler et al. 2019: run the policy through every path, back-propagate the risk measure.
    CVaR uses Rockafellar-Uryasev: CVaR_a(L) = min_w  w + E[(L - w)+] / (1 - a), L = -P&L."""
    torch.manual_seed(0)
    net = DeepHedger()
    opt = torch.optim.Adam(net.parameters(), lr=CFG["lr"])
    n = paths["S"].shape[0]
    t0 = time.time()
    for it in range(CFG["iters"]):
        batch = subset(paths, torch.randint(n, (CFG["batch"],)))
        loss_dollars = -run(net, batch, train=True, costs=costs)["pnl"] / 100  # scale for Adam
        if objective == "cvar":
            # The optimal w is the batch VaR, so plug it in rather than learning it (a learned w
            # moves ~lr per step and takes thousands of steps to reach a $400 VaR).
            w = torch.quantile(loss_dollars.detach(), alpha)
            loss = w + torch.relu(loss_dollars - w).mean() / (1 - alpha)
        elif objective == "mean":  # pure expected P&L: the profit-seeking reward
            loss = loss_dollars.mean()
        else:
            raise ValueError(objective)
        opt.zero_grad()
        loss.backward()
        opt.step()
        if it % 500 == 0 or it == CFG["iters"] - 1:
            print(f"  [{label}] iter {it:5d}  objective {loss.item() * 100:9.2f}  ({time.time() - t0:.0f}s)")
    net.eval()
    return lambda i, p, h: net(i, p, h).detach()


# %% Scoring
def score(name, out):
    loss = -out["pnl"]
    var = torch.quantile(loss, 0.95)
    return dict(
        hedger=name,
        mean=out["pnl"].mean().item(),
        se=(out["pnl"].std() / math.sqrt(len(loss))).item(),
        std=out["pnl"].std().item(),
        var95=var.item(),
        es95=loss[loss >= var].mean().item(),  # the desk's 5% ES, as a positive loss
        fees=out["fees"].mean().item(),
        trades=out["trades"].mean().item(),
    )


def table(rows, title):
    lines = [f"\n{title}",
             f"{'hedger':<26}{'mean P&L':>10}{'(se)':>7}{'std':>9}{'VaR95':>9}{'ES95':>9}{'fees':>8}{'trades':>8}"]
    for r in rows:
        lines.append(f"{r['hedger']:<26}{r['mean']:>10.1f}{r['se']:>7.1f}{r['std']:>9.1f}"
                     f"{r['var95']:>9.1f}{r['es95']:>9.1f}{r['fees']:>8.2f}{r['trades']:>8.1f}")
    text = "\n".join(lines)
    print(text)
    return text


def tune(make, grid, paths, costs=True):
    """Pick a baseline's parameter on the TRAINING paths by the same CVaR95 the deep hedger
    minimizes. Tuning the baseline too is what makes the comparison fair."""
    best = min(grid, key=lambda k: score("", run(make(k), paths, costs=costs))["es95"])
    return best


def compare(model, title, costs=True, mu=None, deep_kwargs=None):
    tr = make_paths(model, CFG["n_train"], seed=1, mu=mu)
    te = make_paths(model, CFG["n_test"], seed=2, mu=mu)  # fresh paths: out-of-sample
    deep = train(tr, costs=costs, label=title, **(deep_kwargs or {}))
    hedgers = {"no hedge": no_hedge, "delta (every share)": delta_hedge}
    if costs:
        b = tune(band_hedge, [2, 3, 5, 7, 10, 15, 20, 30], tr)
        k = tune(ww_hedge, [1, 2, 3, 4, 6, 8, 12], tr)
        hedgers.update({"band10 (desk)": band_hedge(10), f"band{b} (tuned)": band_hedge(b),
                        f"ww_band k={k} (tuned)": ww_hedge(k)})
    hedgers["deep hedger (CVaR95)"] = deep
    outs = {name: run(h, te, costs=costs) for name, h in hedgers.items()}
    text = table([score(name, o) for name, o in outs.items()], title)
    return te, deep, outs, text


REPORT = []


# %% L1: no costs, Black-Scholes world. Deep hedging should rediscover delta.
te, deep, outs, text = compare("gbm", "L1  GBM, no costs", costs=False)
REPORT.append(text)
day = N // 2
h_deep = torch.round(deep(day, te, SIZE * te["D"][:, day]))  # one-step view at mid-life
fig, ax = plt.subplots(figsize=(5, 4))
ax.scatter(SIZE * te["D"][:2000, day], h_deep[:2000], s=3, alpha=0.4)
ax.plot([-100, 0], [-100, 0], "k--", lw=1)
ax.set(xlabel="delta hedge (shares)", ylabel="deep hedger (shares)",
       title=f"L1: learned hedge vs delta, day {day}")
fig.tight_layout()
fig.savefig(OUT / "L1_deep_vs_delta.png", dpi=130)


# %% L2: desk costs, Black-Scholes world.
# Two things to look at:
#  1. Under CVaR95, how much do the $1 tickets matter next to gamma risk? Compare band10's fees
#     saved with the ES it adds.
#  2. The deep hedger keeps trading ~15 times. A fixed fee is flat almost everywhere, so its
#     gradient is ~0 unless the trade is already ~0 shares: the net never learns that skipping
#     saves $1. Raising fee_smooth or min_per_order to $10 doesn't fix it either (tried
#     2026-11-17). Cao et al. 2021 avoid this by using proportional costs only. Fixes to try:
#     have the net output a band WIDTH and apply the band rule with a soft (sigmoid) threshold,
#     or make trade/no-trade a stochastic decision trained with policy gradients (real RL).
te, deep, outs, text = compare("gbm", "L2  GBM, desk IBKR costs")
REPORT.append(text)


def no_trade_plot(outs, names, fname, title):
    fig, axes = plt.subplots(1, len(names), figsize=(5 * len(names), 4), sharey=True)
    for ax, name in zip(axes, names):
        mism = torch.cat([m for d, m, q in outs[name]["log"] if d > 0])[:20000]
        q = torch.cat([q for d, m, q in outs[name]["log"] if d > 0])[:20000]
        ax.scatter(mism, q, s=2, alpha=0.25)
        ax.set(xlabel="holding - delta, before trading (shares)", title=name, xlim=(-30, 30))
    axes[0].set_ylabel("shares traded")
    fig.suptitle(title)
    fig.tight_layout()
    fig.savefig(OUT / fname, dpi=130)


no_trade_plot(outs, ["delta (every share)", "band10 (desk)", "deep hedger (CVaR95)"],
              "L2_no_trade_zone.png",
              "L2: who skips small re-hedges? (a flat segment at 0 = no trade)")


# %% L3: Heston. Vol moves and is correlated with spot (-0.7): the leverage effect.
te, deep, outs, text = compare("heston", "L3  Heston (rho=-0.7), desk costs")
REPORT.append(text)
no_trade_plot(outs, ["delta (every share)", "band10 (desk)", "deep hedger (CVaR95)"],
              "L3_no_trade_zone.png", "L3: Heston")
fig, ax = plt.subplots(figsize=(6, 4))
for name in ["delta (every share)", "band10 (desk)", "deep hedger (CVaR95)"]:
    ax.hist(outs[name]["pnl"].numpy(), bins=200, histtype="step", density=True, label=name)
ax.set(xlabel="P&L per trade ($)", xlim=(-1500, 1000), title="L3: hedged P&L distributions")
ax.legend()
fig.tight_layout()
fig.savefig(OUT / "L3_pnl_hist.png", dpi=130)
# How far from delta does it sit, and does that depend on vol? (A learned min-variance tilt?)
d = N // 2
adj = (deep(d, te, SIZE * te["D"][:, d]) - SIZE * te["D"][:, d])
fig, ax = plt.subplots(figsize=(5, 4))
ax.scatter(te["iv"][:3000, d], adj[:3000], s=3, alpha=0.4)
ax.set(xlabel="vol on day %d" % d, ylabel="deep - delta (shares), starting at delta",
       title="L3: learned tilt away from delta")
fig.tight_layout()
fig.savefig(OUT / "L3_tilt_vs_vol.png", dpi=130)


# %% L4: put 15%/yr drift in the simulator. Same net, two objectives.
# Under "mean" (pure profit) the net should keep long delta to ride the drift: speculation.
# Under CVaR99 it should stay a hedger (François et al. 2024, p. 12).
rows = []
tr = make_paths("gbm", CFG["n_train"], seed=1, mu=0.15)
te = make_paths("gbm", CFG["n_test"], seed=2, mu=0.15)
for label, kw in [("mean P&L (profit-seeking)", dict(objective="mean")),
                  ("CVaR50", dict(alpha=0.50)),
                  ("CVaR99", dict(alpha=0.99))]:
    pol = train(tr, label="L4 " + label, **kw)
    out = run(pol, te)
    held = torch.stack([pol(i, te, SIZE * te["D"][:, i]) - SIZE * te["D"][:, i] for i in range(N)])
    r = score(label, out)
    r["hedger"] = f"{label} [{held.mean().item():+.1f} sh]"
    rows.append(r)
rows.append(score("delta (every share)", run(delta_hedge, te)))
REPORT.append(table(rows, "L4  GBM with mu=15%, desk costs. [x sh] = avg shares kept off delta (+ = long)"))

(OUT / "results.txt").write_text("\n".join(REPORT) + "\n")
print(f"\nFigures and tables in {OUT}")
