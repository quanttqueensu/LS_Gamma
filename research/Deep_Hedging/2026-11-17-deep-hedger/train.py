"""Walk-forward training of the deep hedger (Buehler-style direct policy search).

Each training episode is one short put, per contract, from entry to exit. The
policy picks a hedge ratio each morning; the rollout applies the book's stop
and profit-take on the combined P&L (exit flags are not differentiated), and
P&L is back-propagated through the share holdings.

Objective (maximized): mean episode P&L minus kappa x the amount by which the
worst-5% mean loss (CVaR 95) exceeds the delta hedge's on the same episodes.
In words: make as much as possible without a worse tail than delta hedging.
"""
import math

import numpy as np
import torch

from lsgamma.backtest import deep_hedge

MULT = 100  # shares per contract


def to_torch(T):
    t = {k: torch.tensor(np.nan_to_num(v), dtype=torch.float64)
         for k, v in T.items() if k not in ("valid", "last")}
    t["valid"] = torch.tensor(T["valid"])
    t["last"] = torch.tensor(T["last"])
    return t


def rollout(t, ratio_fn, ex):
    """Per-contract net P&L of each episode. ratio_fn(x[n, 9]) -> [n]."""
    cps = ex["commission_share"] + ex["share_half_spread"] * ex["spread_mult"]
    fee = 2 * ex["commission_contract"]
    P0, prem = t["P0"], t["P0"] * MULT
    n, L = t["S"].shape
    h = torch.zeros(n, dtype=torch.float64)
    cash = torch.zeros(n, dtype=torch.float64)
    alive = torch.ones(n, dtype=torch.bool)
    out = torch.zeros(n, dtype=torch.float64)
    steps = torch.arange(L)
    for k in range(L):
        v = t["valid"][:, k]
        S, F, M, C = t["S"][:, k], t["F"][:, k], t["M"][:, k], t["C"][:, k]
        comb = (P0 - M) * MULT + h * S + cash - fee / 2
        if k > 0:
            with torch.no_grad():
                time = steps[k] == t["last"]
                hit = v & ((comb <= -ex["short_stop_mult"] * prem)
                           | (comb >= ex["short_profit_frac"] * prem))
                go = alive & (time | hit)
            final = (P0 - C.clamp(min=0.01)) * MULT - fee + h * F - h.abs() * cps + cash
            out = torch.where(go, final, out)
            alive = alive & ~go
        act = alive & v
        x = torch.cat([t["X"][:, k], (comb / prem).unsqueeze(1)], dim=1)
        r = ratio_fn(x)
        dh = torch.where(act, -r * t["ad"][:, k] * MULT - h, torch.zeros_like(h))
        cash = cash - dh * F - dh.abs() * cps
        h = h + dh
    return out


def cvar(pnl, q=0.05):
    k = max(1, int(math.ceil(q * len(pnl))))
    return torch.topk(-pnl, k).values.mean()


def objective(pnl, ref_cvar, kappa):
    return pnl.mean() - kappa * torch.relu(cvar(pnl) - ref_cvar)


class Net(torch.nn.Module):
    def __init__(self, mu, sd, hidden):
        super().__init__()
        self.mu, self.sd = mu, sd
        dims = [len(deep_hedge.FEATURES), *hidden]
        self.body = torch.nn.ModuleList(torch.nn.Linear(a, b) for a, b in zip(dims, dims[1:]))
        self.head = torch.nn.Linear(dims[-1], 1)
        torch.nn.init.zeros_(self.head.weight)  # start exactly at delta hedging
        torch.nn.init.constant_(self.head.bias, math.log(1 / (deep_hedge.MAX_RATIO - 1)))

    def forward(self, x):
        z = (x - self.mu) / self.sd
        for layer in self.body:
            z = torch.tanh(layer(z))
        return deep_hedge.MAX_RATIO * torch.sigmoid(self.head(z)).squeeze(1)

    def export(self):
        layers = [(l.weight.detach().T.tolist(), l.bias.detach().tolist())
                  for l in [*self.body, self.head]]
        return {"mu": self.mu.tolist(), "sd": self.sd.tolist(), "layers": layers}


def scaling(T):
    # training-set feature scale; pnl_frac fixed
    v = T["valid"]
    X = T["X"][v]
    mu, sd = np.append(X.mean(0), 0.0), np.append(X.std(0) + 1e-8, 0.5)
    return torch.tensor(mu), torch.tensor(sd)


def const_fn(c):
    return lambda x: torch.full((x.shape[0],), float(c), dtype=torch.float64)


def fit_const(t, ex, grid, kappa, ref_cvar):
    with torch.no_grad():
        scores = {c: float(objective(rollout(t, const_fn(c), ex), ref_cvar, kappa)) for c in grid}
    return max(scores, key=scores.get), scores


def fit_net(T, t, ex, hp, seed, ref_cvar):
    torch.manual_seed(seed)
    mu, sd = scaling(T)
    net = Net(mu, sd, hp["hidden"]).double()
    opt = torch.optim.Adam(net.parameters(), lr=hp["lr"], weight_decay=hp["weight_decay"])
    for _ in range(hp["epochs"]):
        opt.zero_grad()
        loss = -objective(rollout(t, net, ex), ref_cvar, hp["kappa"])
        loss.backward()
        opt.step()
    return net


def evaluate(t, ex, fn):
    with torch.no_grad():
        pnl = rollout(t, fn, ex)
    return {"mean": float(pnl.mean()), "cvar95": float(cvar(pnl)), "sd": float(pnl.std()),
            "n": len(pnl)}
