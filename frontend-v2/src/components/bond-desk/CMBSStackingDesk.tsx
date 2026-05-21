import { useState } from "react";
import { motion } from "framer-motion";
import { useDealState, type PoolDeal } from "@/contexts/DealStateContext";
import { useBernard } from "@/contexts/BernardContext";
import { trpc } from "@/lib/trpc";

const CLASS_COLORS: Record<string, string> = {
  senior: "#C4A048",
  mezzanine: "#22d3ee",
  subordinate: "#f59e0b",
  equity: "#ef4444",
};

export default function CMBSStackingDesk() {
  const { state, addToPool, removeFromPool, log } = useDealState();
  const bernard = useBernard();
  const poolMutation = trpc.bondStructuring.poolAnalysis.useMutation();
  const [subordination, setSubordination] = useState(18);

  const poolDealIds = new Set(state.cmbsPool.map((p) => p.deal.id));

  const handleAddToPool = () => {
    if (!state.activeDeal || !state.metrics || state.tranches.length === 0) return;
    if (poolDealIds.has(state.activeDeal.id)) return;

    const poolDeal: PoolDeal = {
      deal: state.activeDeal,
      tranches: [...state.tranches],
      metrics: { ...state.metrics },
    };
    addToPool(poolDeal);
    log("NEST", "pool_add", `${state.activeDeal.name} added to CMBS pool`);

    const allDeals = [...state.cmbsPool, poolDeal].map((p) => ({
      total_debt_usd: p.metrics.total_debt_usd,
      blended_coupon_pct: p.metrics.blended_coupon_pct,
      stabilized_noi_usd: p.deal.stabilized_noi_usd,
      sector: p.deal.sector,
      weighted_avg_life_yrs: 10,
      tranches: p.tranches.map((t) => ({ series: t.series, size_usd: t.size_usd })),
    }));
    poolMutation.mutate({ deals: allDeals }, {
      onSuccess: (data: any) => {
        const pm = data.pool_metrics;
        bernard.push({
          type: "pool_updated",
          depths: {
            expert: `Pool: ${pm.deal_count} deals, $${(pm.total_commitment_usd/1e6).toFixed(0)}M, ${pm.wac_pct.toFixed(2)}% WAC, ${pm.pool_dscr.toFixed(2)}x DSCR.`,
            standard: `Added ${state.activeDeal!.name} to pool. ${pm.deal_count} deals totaling $${(pm.total_commitment_usd/1e6).toFixed(0)}M. Diversification score: ${pm.diversification_score}/100. Pool DSCR: ${pm.pool_dscr.toFixed(2)}x.`,
            educational: `Adding ${state.activeDeal!.name} brings the CMBS pool to ${pm.deal_count} deals with $${(pm.total_commitment_usd/1e6).toFixed(0)}M total commitment. The weighted average coupon (WAC) is ${pm.wac_pct.toFixed(2)}% — this is what investors receive on average. Diversification score of ${pm.diversification_score}/100 reflects how spread out the pool is across sectors and deals. Higher diversification generally means lower risk and better ratings. Pool DSCR of ${pm.pool_dscr.toFixed(2)}x ${pm.pool_dscr >= 1.5 ? 'is investment grade.' : 'needs improvement.'}`,
          },
        });
      },
    });
  };

  const handleRemoveFromPool = (dealId: string) => {
    const deal = state.cmbsPool.find((p) => p.deal.id === dealId);
    removeFromPool(dealId);
    if (deal) {
      log("NEST", "pool_remove", `${deal.deal.name} removed from CMBS pool`);
    }
  };

  const poolMetrics = poolMutation.data as any;
  const totalPool = state.cmbsPool.reduce((s, p) => s + p.metrics.total_debt_usd, 0);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-[Cormorant_Garamond] text-xl font-semibold text-slate-200">
            CMBS Stacking Desk
          </h2>
          <p className="font-mono text-[0.6rem] text-slate-500">
            Pool structured deals into a CMBS offering
          </p>
        </div>
        {totalPool > 0 && (
          <div className="rounded-xl border border-[#C4A048]/20 bg-[#C4A048]/10 px-4 py-2">
            <div className="font-mono text-[0.55rem] text-[#C4A048]/60">Pool Commitment</div>
            <div className="font-mono text-lg font-semibold text-[#C4A048]">
              ${(totalPool / 1e6).toFixed(0)}M
            </div>
          </div>
        )}
      </div>

      <div className="grid grid-cols-12 gap-4">
        <div className="col-span-4">
          <div className="rounded-2xl border border-white/[0.08] bg-white/[0.02] p-4">
            <h4 className="mb-2 font-mono text-[0.6rem] uppercase tracking-wider text-slate-500">
              Active Deal
            </h4>
            {state.activeDeal && state.metrics ? (
              <div className="space-y-3">
                <div className="rounded-xl border border-white/10 bg-white/[0.03] p-3">
                  <div className="font-[Space_Grotesk] text-sm text-slate-200">{state.activeDeal.name}</div>
                  <div className="mt-1 grid grid-cols-2 gap-1 font-mono text-[0.6rem]">
                    <span className="text-slate-500">Debt</span>
                    <span className="text-right text-[#C4A048]">${(state.metrics.total_debt_usd/1e6).toFixed(0)}M</span>
                    <span className="text-slate-500">Grade</span>
                    <span className="text-right text-slate-200">{state.metrics.obligor_grade}</span>
                    <span className="text-slate-500">DSCR</span>
                    <span className="text-right text-slate-200">{state.metrics.dscr.toFixed(2)}x</span>
                  </div>
                </div>
                <button
                  onClick={handleAddToPool}
                  disabled={poolDealIds.has(state.activeDeal.id)}
                  className="w-full rounded-xl bg-gradient-to-r from-cyan-500 to-cyan-400 px-4 py-2 font-mono text-xs font-semibold text-[#030A06] disabled:opacity-30 transition-all hover:shadow-[0_0_16px_rgba(34,211,238,0.3)]"
                >
                  {poolDealIds.has(state.activeDeal.id) ? "Already in Pool" : "Add to CMBS Pool"}
                </button>
              </div>
            ) : (
              <p className="font-mono text-[0.65rem] text-slate-600">
                Structure a deal above to add it to the pool
              </p>
            )}
          </div>
        </div>

        <div className="col-span-8">
          <div className="rounded-2xl border border-white/[0.08] bg-white/[0.02] p-4">
            <h4 className="mb-2 font-mono text-[0.6rem] uppercase tracking-wider text-slate-500">
              CMBS Pool ({state.cmbsPool.length} deals)
            </h4>
            {state.cmbsPool.length > 0 ? (
              <div className="grid grid-cols-2 gap-2">
                {state.cmbsPool.map((p) => (
                  <motion.div
                    key={p.deal.id}
                    layout
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{ opacity: 1, scale: 1 }}
                    className="group rounded-xl border border-cyan-500/20 bg-cyan-500/[0.04] p-3"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-[Space_Grotesk] text-sm text-slate-200">{p.deal.name}</span>
                      <button
                        onClick={() => handleRemoveFromPool(p.deal.id)}
                        className="opacity-0 group-hover:opacity-100 text-slate-600 hover:text-rose-400 text-xs transition-all"
                      >
                        x
                      </button>
                    </div>
                    <div className="mt-1 flex gap-3 font-mono text-[0.55rem] text-slate-400">
                      <span>${(p.metrics.total_debt_usd/1e6).toFixed(0)}M</span>
                      <span>{p.metrics.obligor_grade}</span>
                      <span>{p.metrics.dscr.toFixed(2)}x</span>
                      <span className="capitalize">{p.deal.sector}</span>
                    </div>
                  </motion.div>
                ))}
              </div>
            ) : (
              <div className="flex h-24 items-center justify-center rounded-xl border border-dashed border-white/[0.06]">
                <p className="font-mono text-[0.65rem] text-slate-600">No deals in pool yet</p>
              </div>
            )}
          </div>
        </div>
      </div>

      {poolMetrics && state.cmbsPool.length > 0 && (
        <div className="grid grid-cols-2 gap-4">
          <div className="rounded-2xl border border-white/[0.08] bg-white/[0.02] p-4">
            <h4 className="mb-3 font-mono text-[0.6rem] uppercase tracking-wider text-slate-500">
              Tranche Waterfall
            </h4>
            <div className="space-y-1.5">
              {Object.entries(poolMetrics.tranche_classes as Record<string, number>)
                .filter(([, v]) => v > 0)
                .map(([cls, amount]) => {
                  const pct = totalPool > 0 ? (amount / totalPool) * 100 : 0;
                  return (
                    <div key={cls} className="flex items-center gap-3">
                      <div className="w-20 font-mono text-[0.6rem] capitalize text-slate-400">{cls}</div>
                      <div className="flex-1 h-6 rounded-md bg-white/[0.04] overflow-hidden">
                        <motion.div
                          initial={{ width: 0 }}
                          animate={{ width: `${pct}%` }}
                          transition={{ duration: 0.6 }}
                          className="h-full rounded-md"
                          style={{ backgroundColor: CLASS_COLORS[cls] ?? "#666" }}
                        />
                      </div>
                      <div className="w-16 text-right font-mono text-[0.6rem] text-[#C4A048]">
                        ${(amount/1e6).toFixed(0)}M
                      </div>
                      <div className="w-10 text-right font-mono text-[0.55rem] text-slate-500">
                        {pct.toFixed(0)}%
                      </div>
                    </div>
                  );
                })}
            </div>

            <div className="mt-4 rounded-xl border border-white/5 bg-white/[0.02] p-3">
              <div className="flex items-center justify-between">
                <span className="font-mono text-[0.55rem] uppercase tracking-wider text-slate-500">
                  Push Leverage
                </span>
                <span className="font-mono text-xs text-amber-400">{subordination}% sub</span>
              </div>
              <input
                type="range"
                min={5}
                max={30}
                value={subordination}
                onChange={(e) => setSubordination(parseInt(e.target.value))}
                className="mt-2 w-full accent-[#C4A048]"
              />
              <div className="mt-1 flex justify-between font-mono text-[0.5rem] text-slate-600">
                <span>Max Leverage (5%)</span>
                <span>Conservative (30%)</span>
              </div>
            </div>
          </div>

          <div className="rounded-2xl border border-white/[0.08] bg-white/[0.02] p-4">
            <h4 className="mb-3 font-mono text-[0.6rem] uppercase tracking-wider text-slate-500">
              Pool Economics
            </h4>
            <div className="grid grid-cols-2 gap-3">
              <PoolStat label="Total Commitment" value={`$${(poolMetrics.pool_metrics.total_commitment_usd/1e6).toFixed(0)}M`} />
              <PoolStat label="Deals" value={poolMetrics.pool_metrics.deal_count} />
              <PoolStat label="WAC" value={`${poolMetrics.pool_metrics.wac_pct.toFixed(2)}%`} />
              <PoolStat label="WAL" value={`${poolMetrics.pool_metrics.wal_yrs.toFixed(1)} yrs`} />
              <PoolStat label="Pool DSCR" value={`${poolMetrics.pool_metrics.pool_dscr.toFixed(2)}x`} />
              <PoolStat label="Diversification" value={`${poolMetrics.pool_metrics.diversification_score}/100`} />
              <PoolStat label="Senior %" value={`${poolMetrics.pool_metrics.senior_pct.toFixed(0)}%`} />
              <PoolStat label="Subordination" value={`${poolMetrics.pool_metrics.subordination_pct.toFixed(0)}%`} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function PoolStat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-lg border border-white/5 bg-white/[0.02] p-2.5">
      <div className="font-mono text-[0.5rem] uppercase tracking-wider text-slate-600">{label}</div>
      <div className="font-mono text-sm font-semibold text-[#C4A048]">{value}</div>
    </div>
  );
}
