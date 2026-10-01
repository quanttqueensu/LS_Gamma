def decide(rv_forecast, iv, cfg):
    spread = rv_forecast - iv
    if spread > cfg["signal"]["long_band"]:
        return "long"
    if spread < cfg["signal"]["short_band"]:
        return "short"
    return "flat"
