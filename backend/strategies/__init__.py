from .play1_ema_crossover import EMA_Crossover
from .play2_triple_ma import TripleMA
from .play3_vwap_pullback import VWAPPullback
from .play4_supertrend import SupertrendPowerTrend
from .play5_bb_squeeze import BBSqueeze
from .play6_bb_contra import BBContra

STRATEGY_MAP = {
    "play1_ema_crossover": EMA_Crossover(),
    "play2_triple_ma": TripleMA(),
    "play3_vwap_pullback": VWAPPullback(),
    "play4_supertrend": SupertrendPowerTrend(),
    "play5_bb_squeeze": BBSqueeze(),
    "play6_bb_contra": BBContra(),
}
