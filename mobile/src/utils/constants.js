import { colors } from '../theme/colors'

export const STRATEGY_NAMES = {
  play1_ema_crossover: 'EMA Crossover',
  play2_triple_ma: 'Triple MA',
  play3_vwap_pullback: 'VWAP Pullback',
  play4_supertrend: 'Supertrend',
  play5_bb_squeeze: 'BB Squeeze',
  play6_bb_contra: 'BB Contra',
  bull_call_spread: 'Bull Call Spread',
  bull_put_spread: 'Bull Put Spread',
  bear_call_spread: 'Bear Call Spread',
  bear_put_spread: 'Bear Put Spread',
  iron_condor: 'Iron Condor',
  long_straddle: 'Long Straddle',
  futures_volume_breakout: 'Volume Breakout',
  futures_candlestick_reversal: 'Candlestick Reversal',
  futures_mean_reversion: 'Mean Reversion',
  futures_ema_rsi_pullback: 'EMA & RSI Pullback',
}

export const SOURCE_LABELS = {
  auto: 'Live',
  paper: 'Paper',
  swing: 'Swing',
  swing_paper: 'Swing Paper',
  options_auto: 'Opt Live',
  options_paper: 'Opt Paper',
  options_swing: 'Opt Swing',
  options_swing_paper: 'Opt Swing Paper',
  futures_auto: 'Fut Live',
  futures_paper: 'Fut Paper',
  futures_swing: 'Fut Swing',
  futures_swing_paper: 'Fut Swing Paper',
}

export const SOURCE_COLORS = {
  auto: colors.orange[400],
  paper: colors.blue[400],
  swing: colors.emerald[400],
  swing_paper: colors.teal[400],
  options_auto: colors.purple[400],
  options_paper: colors.cyan[400],
  options_swing: colors.pink[400],
  options_swing_paper: colors.violet[400],
  futures_auto: colors.yellow[400],
  futures_paper: colors.blue[400],
  futures_swing: colors.emerald[400],
  futures_swing_paper: colors.teal[400],
}

export const LOG_COLORS = {
  START: colors.green[400],
  STOP: colors.red[400],
  SCAN: colors.blue[400],
  ORDER: colors.orange[400],
  INFO: colors.text.secondary,
  WARN: colors.yellow[400],
  ERROR: colors.red[500],
  ALERT: colors.pink[400],
  SQUAREOFF: colors.purple[400],
  RESTORE: colors.teal[400],
}

export const POLL_INTERVAL = 30000
