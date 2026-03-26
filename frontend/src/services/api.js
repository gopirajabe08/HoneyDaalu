/**
 * API barrel — re-exports every endpoint from the split modules.
 *
 * All existing imports like `import { getMarketRegime } from '../services/api'`
 * continue to work unchanged.
 */

export * from './api/market'
export * from './api/fyers'
export * from './api/trading'
export * from './api/options'
export * from './api/futures'
export * from './api/btst'
export * from './api/analysis'
