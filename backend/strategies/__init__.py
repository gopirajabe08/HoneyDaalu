from .play1_ema_crossover import EMA_Crossover
from .play2_triple_ma import TripleMA
from .play3_vwap_pullback import VWAPPullback
from .play4_supertrend import SupertrendPowerTrend
from .play5_bb_squeeze import BBSqueeze
from .play6_bb_contra import BBContra
from .play7_orb import ORBBreakout
from .play8_rsi_divergence import RSIDivergence
from .play9_gap_analysis import GapAnalysis
from .play10_momentum_rank import MomentumRank

STRATEGY_MAP = {
    "play1_ema_crossover": EMA_Crossover(),
    "play2_triple_ma": TripleMA(),
    "play3_vwap_pullback": VWAPPullback(),
    "play4_supertrend": SupertrendPowerTrend(),
    "play5_bb_squeeze": BBSqueeze(),
    "play6_bb_contra": BBContra(),
    "play7_orb": ORBBreakout(),
    "play8_rsi_divergence": RSIDivergence(),
    "play9_gap_analysis": GapAnalysis(),
    "play10_momentum_rank": MomentumRank(),
}
