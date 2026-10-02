def decide(rv_forecast, iv, cfg):
    vrp = iv - rv_forecast
    if vrp > cfg["signal"]["short_band"]:
        return "short"
    if vrp < cfg["signal"]["long_band"]:
        return "long"
    return "flat"
