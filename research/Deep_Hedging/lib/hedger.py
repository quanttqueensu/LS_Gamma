"""Deep hedger v2 training core: book-scale R2 episodes, rollout, bounded policies.

Episode: on day d, sell the put the book would sell at a delta target (15/20/25),
sized by the book's own stress rule (trading.sizing.stress_qty), and follow it
daily at 10:15 to the 7-DTE exit, with the stop and profit-take on option +
hedge P&L, the 10-share band, $0.005/share with a $1 minimum per order, the
share half-spread and option fills at the fill-view bid/ask (x spread mult).

Policy: ratio in [lo, hi] times the delta-hedge shares. Objective (maximized):
mean episode P&L - lam x CVaR95 (mean loss of the worst 5% of episodes).
Exit flags and the band test are not differentiated.
"""
import functools
import math
import pickle
from datetime import date

import numpy as np
import torch

from lsgamma.backtest import deep_hedge, engine
from lsgamma.history import marks
from lsgamma.trading.sizing import stress_qty

from . import panel

MULT = 100
STATIC = ["abs_delta", "tau", "iv", "vix", "vix_vix3m", "rv20", "ret5", "ret20", "vega_s"]
RAW = ["delta", "vega", "spot", "years"]
MKT = ["vix", "vix_vix3m", "rv20", "ret5", "ret20"]
DYN_SCALE = {"pnl_frac": (0.0, 0.5), "hold_frac": (1.0, 0.25)}  # fixed scale, path inputs


# ---------------------------------------------------------------- episodes
def episodes(daily, puts, cfg, end_cut, targets=panel.TARGETS):
    """Episodes whose time exit is before end_cut (outcomes known by then)."""
    daily = daily.reset_index(drop=True)
    dates = list(daily["date"])
    pos = {d: i for i, d in enumerate(dates)}
    key = puts.set_index(["date", "expiry", "strike"]).sort_index()
    budget = cfg["backtest"]["stress_budget"] * cfg["size"]["capital"]
    eps = []
    for i, r in daily.iterrows():
        if r["entry_expiry"] is None:
            continue
        exp = date.fromisoformat(r["entry_expiry"])
        days = [d for d in dates[i:i + 45] if d <= exp]
        exit_day = next((d for d in days if (exp - d).days <= cfg["exit"]["exit_dte"]), None)
        if exit_day is None or exit_day >= end_cut:
            continue
        days = days[:days.index(exit_day) + 1]
        for t in targets:
            k = r[panel.col(t)]
            if math.isnan(k):
                continue
            ep = one(daily, pos, key, r, k, days, exp, cfg, budget)
            if ep is not None:
                eps.append({**ep, "target": t})
    return eps


def one(daily, pos, key, r, strike, days, exp, cfg, budget):
    rows = []
    for d in days:
        try:
            row = key.loc[(d, r["entry_expiry"], strike)]
            row = row.iloc[0] if row.ndim == 2 else row  # duplicate quote rows
        except KeyError:
            row = None
        dl = daily.iloc[pos[d]]
        rows.append((d, dl, row))
    d0, _, first = rows[0]
    if first is None or any(math.isnan(first[c]) for c in ("f_bid", "f_ask", "gamma", "delta")):
        return None  # no entry fill or greeks: the engine would not open
    years = float(marks.years(engine.at(d0, "10:15"), [exp])[0])
    qty = stress_qty(cfg, {**first.to_dict(), "strike": strike}, float(r["spot"]), years, budget)
    if not qty:
        return None
    st = {k: [] for k in ("S", "F", "M", "FB", "FA", "FM", "delta", "iv", "vega", "left", *MKT)}
    for d, dl, row in rows:
        st["S"].append(dl["spot"])
        st["F"].append(dl["fspot"])
        for a, b in (("M", "mid"), ("FB", "f_bid"), ("FA", "f_ask"), ("FM", "f_mid"),
                     ("delta", "delta"), ("iv", "iv"), ("vega", "vega")):
            st[a].append(math.nan if row is None else row[b])
        st["left"].append((exp - d).days)
        for m in MKT:
            st[m].append(dl[m])
    return {"entry": d0, "exit": days[-1], "strike": strike, "qty": qty,
            "steps": {k: np.asarray(v, dtype=float) for k, v in st.items()}}


def tensors(eps, mult=1.0):
    """Padded numpy arrays [episode, step]; fills at mid -/+ half spread x mult."""
    n, L = len(eps), max(len(e["steps"]["S"]) for e in eps)
    A = {k: np.full((n, L), np.nan) for k in ("S", "F", "M", "C", "delta", "iv", "vega", "left",
                                               *MKT)}
    P0, qty, last = np.zeros(n), np.zeros(n), np.zeros(n, dtype=int)
    for i, e in enumerate(eps):
        st, m = e["steps"], len(e["steps"]["S"])
        for k in ("S", "F", "M", "delta", "iv", "vega", "left", *MKT):
            A[k][i, :m] = st[k]
        A["C"][i, :m] = np.maximum(st["FM"] + (st["FA"] - st["FB"]) / 2 * mult, 0.01)
        P0[i] = max(st["FM"][0] - (st["FA"][0] - st["FB"][0]) / 2 * mult, 0.01)
        qty[i], last[i] = e["qty"], m - 1
        # contract gone at the exit (far OTM): settle at intrinsic, as the engine does
        for k, ref in (("C", "F"), ("M", "S")):
            if np.isnan(A[k][i, m - 1]):
                A[k][i, m - 1] = max(e["strike"] - A[ref][i, m - 1], 0.0)
    valid = (~np.isnan(A["delta"]) & ~np.isnan(A["F"]) & ~np.isnan(A["M"]) & ~np.isnan(A["vega"])
             & ~np.isnan(A["C"]))  # no close quote: no stop or profit-take that day
    # model inputs, exactly as deep_hedge.inputs builds them
    X = {"abs_delta": np.abs(A["delta"]), "tau": A["left"] / 30.0, "iv": A["iv"],
         **{m: A[m] for m in MKT}, "vega_s": 100.0 * A["vega"] / A["S"],
         "delta": A["delta"], "vega": A["vega"], "spot": A["S"], "years": A["left"] / 365.0}
    return {**{k: A[k] for k in ("S", "F", "M", "C")}, "X": X, "P0": P0, "qty": qty,
            "last": last, "valid": valid, "entry": np.array([e["entry"] for e in eps]),
            "target": np.array([e["target"] for e in eps])}


def to_torch(T):
    f = lambda a: torch.tensor(np.nan_to_num(a), dtype=torch.float64)  # noqa: E731
    t = {k: f(T[k]) for k in ("S", "F", "M", "C", "P0", "qty")}
    t["X"] = {k: f(v) for k, v in T["X"].items()}
    t["valid"], t["last"] = torch.tensor(T["valid"]), torch.tensor(T["last"])
    return t


def subset(T, mask):
    out = {k: (v[mask] if isinstance(v, np.ndarray) else v) for k, v in T.items() if k != "X"}
    out["X"] = {k: v[mask] for k, v in T["X"].items()}
    return out


# ---------------------------------------------------------------- rollout
def rollout(t, policy, ex):
    """Book-scale net P&L of each episode. policy(dict of [n] tensors) -> [n] ratios."""
    cs, mn = ex["commission_share"], ex["min_per_order"]
    half = ex["share_half_spread"] * ex["spread_mult"]
    band = ex["min_shares"] - 0.5  # engine trades round(gap) >= min_shares
    q, P0 = t["qty"], t["P0"]
    prem = P0 * MULT * q
    fee_opt = torch.clamp(ex["commission_contract"] * q, min=mn)
    zero = torch.zeros_like(q)

    def cost(x):
        a = x.abs()
        return torch.where(a > 0, torch.clamp(cs * a, min=mn) + half * a, zero)

    h, cash, out = zero.clone(), zero.clone(), zero.clone()
    alive = torch.ones_like(q, dtype=torch.bool)
    for k in range(t["S"].shape[1]):
        v = t["valid"][:, k]
        S, F, M, C = t["S"][:, k], t["F"][:, k], t["M"][:, k], t["C"][:, k]
        comb = (P0 - M) * MULT * q + h * S + cash  # engine combined_pnl; cash nets share fees
        if k > 0:
            with torch.no_grad():
                hit = v & ((comb <= -ex["short_stop_mult"] * prem)
                           | (comb >= ex["short_profit_frac"] * prem))
                go = alive & ((k == t["last"]) | hit)
            final = (P0 - C) * MULT * q + h * F - cost(h) + cash - 2 * fee_opt
            out = torch.where(go, final, out)
            alive = alive & ~go
        base = -t["X"]["delta"][:, k].abs() * MULT * q
        d = {n: x[:, k] for n, x in t["X"].items()}
        d["pnl_frac"] = comb / prem
        d["hold_frac"] = torch.where(base != 0, h / torch.where(base != 0, base, -1.0), zero)
        gap = policy(d) * base - h
        trade = (alive & v & (gap.abs() >= band)).detach()
        dh = torch.where(trade, gap, zero)
        cash = cash - dh * F - cost(dh)
        h = h + dh
    return out


def cvar(pnl, q=0.05):
    k = max(1, int(math.ceil(q * len(pnl))))
    return torch.topk(-pnl, k).values.mean()


def objective(pnl, lam):
    return pnl.mean() - lam * cvar(pnl)


# ---------------------------------------------------------------- policies
class Bounded(torch.nn.Module):
    """ratio = lo + (hi - lo) sigmoid(net(x)); starts at the box middle (1.0)."""

    def __init__(self, mu, sd, hidden, lo, hi, names=tuple(deep_hedge.V2)):
        super().__init__()
        self.names, self.lo, self.hi = list(names), lo, hi
        self.mu, self.sd = mu, sd
        dims = [len(self.names), *hidden]
        self.body = torch.nn.ModuleList(torch.nn.Linear(a, b) for a, b in zip(dims, dims[1:]))
        self.head = torch.nn.Linear(dims[-1], 1)
        torch.nn.init.zeros_(self.head.weight)
        torch.nn.init.zeros_(self.head.bias)
        self.double()

    def forward(self, d):
        z = (torch.stack([d[n] for n in self.names], 1) - self.mu) / self.sd
        for layer in self.body:
            z = torch.tanh(layer(z))
        return self.lo + (self.hi - self.lo) * torch.sigmoid(self.head(z)).squeeze(1)

    def export(self):
        return {"mu": self.mu.tolist(), "sd": self.sd.tolist(),
                "layers": [(l.weight.detach().T.tolist(), l.bias.detach().tolist())
                           for l in [*self.body, self.head]]}


def ensemble(members):
    return lambda d: torch.stack([m(d) for m in members]).mean(0)


def delta_policy(d):
    return torch.ones_like(d["delta"])


def hw_policy(coef, lo, hi):
    a, b, c = coef

    def f(d):
        delta, yrs = d["delta"], d["years"].clamp(min=1e-6)
        mv = delta + 100.0 * d["vega"] / (d["spot"] * yrs.sqrt()) * (a + b * delta + c * delta ** 2)
        r = torch.where(delta.abs() > 1e-4, mv / torch.where(delta.abs() > 1e-4, delta, -1.0),
                        torch.ones_like(delta))
        return r.clamp(lo, hi)
    return f


def scaling(T, names=deep_hedge.V2):
    v = T["valid"]
    mu, sd = [], []
    for n in names:
        if n in DYN_SCALE:
            m, s = DYN_SCALE[n]
        else:
            x = T["X"][n][v]
            m, s = float(x.mean()), float(x.std()) + 1e-8
        mu.append(m)
        sd.append(s)
    return torch.tensor(mu, dtype=torch.float64), torch.tensor(sd, dtype=torch.float64)


def train_member(job):
    """One ensemble member with early stopping on the inner validation set."""
    torch.set_num_threads(1)
    hp, ex = job["hp"], job["ex"]
    torch.manual_seed(job["seed"])
    fit, val = to_torch(job["fit"]), to_torch(job["val"])
    mu, sd = scaling(job["fit"])
    net = Bounded(mu, sd, hp["hidden"], hp["lo"], hp["hi"])
    opt = torch.optim.Adam(net.parameters(), lr=hp["lr"], weight_decay=hp["weight_decay"])

    def score():
        with torch.no_grad():
            return float(objective(rollout(val, net, ex), job["lam"]))
    best, best_epoch, state = score(), 0, {k: v.clone() for k, v in net.state_dict().items()}
    start = best
    for epoch in range(1, hp["epochs"] + 1):
        opt.zero_grad()
        (-objective(rollout(fit, net, ex), job["lam"]) / 1000.0).backward()
        opt.step()
        if epoch % hp["eval_every"] == 0:
            s = score()
            if s > best:
                best, best_epoch = s, epoch
                state = {k: v.clone() for k, v in net.state_dict().items()}
    net.load_state_dict(state)
    return {"key": job["key"], "member": net.export(), "best_epoch": best_epoch,
            "val_start": start, "val_best": best}


def model_json(members, hp, names=deep_hedge.V2):
    return {"kind": "net", "features": list(names), "lo": hp["lo"], "hi": hp["hi"],
            "members": members}


def from_json(model):
    """Torch policy from an exported model (for evaluation on episodes)."""
    if model.get("kind") == "hw":
        return hw_policy(model["coef"], model["lo"], model["hi"])
    nets = []
    for m in model["members"]:
        hidden = [len(b) for _, b in m["layers"][:-1]]
        net = Bounded(torch.tensor(m["mu"], dtype=torch.float64),
                      torch.tensor(m["sd"], dtype=torch.float64), hidden, model["lo"],
                      model["hi"], model["features"])
        with torch.no_grad():
            for layer, (w, b) in zip([*net.body, net.head], m["layers"]):
                layer.weight.copy_(torch.tensor(w, dtype=torch.float64).T)
                layer.bias.copy_(torch.tensor(b, dtype=torch.float64))
        nets.append(net)
    return ensemble(nets)


@functools.lru_cache(maxsize=4)
def _cached(path):
    with open(path, "rb") as f:
        return pickle.load(f)


def train_cached(job):
    # worker entry: (fit, val) tensors read once per process from a pickle
    fit, val = _cached(job["data"])
    return train_member({**job, "fit": fit, "val": val})
