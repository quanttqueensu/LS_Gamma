from lsgamma.forecasting.GARCH import GARCH
from lsgamma.forecasting.HAR import HAR
from lsgamma.forecasting.HARX import HARGK, HARX
from lsgamma.forecasting.RF import RF

FORECASTERS = {"garch": GARCH, "har": HAR}
# research only: fit on the features table
FEATURE_FORECASTERS = {"har_gk": HARGK, "harx": HARX, "rf": RF}
