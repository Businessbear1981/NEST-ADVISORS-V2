import { useState } from "react";
import { Loader2, Users, Target, FileText, BookOpen, Send, DollarSign, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { trpc } from "@/lib/trpc";

function money(val: number) {
  if (val >= 1_000_000_000) return `$${(val / 1_000_000_000).toFixed(1)}B`;
  if (val >= 1_000_000) return `$${(val / 1_000_000).toFixed(1)}M`;
  if (val >= 1_000) return `$${(val / 1_000).toFixed(0)}K`;
  return `$${val}`;
}

const matchColors: Record<string, string> = {
  high: "border-emerald-300/30 bg-emerald-400/10",
  medium: "border-amber-300/30 bg-amber-300/10",
  low: "border-slate-400/30 bg-slate-500/10",
};

export default function HawkeyePlacementScout({ dealId, summaryMode }: { dealId?: string; summaryMode?: boolean }) {
  const [matchParams, setMatchParams] = useState({
    naics: "6232",
    rating: "A",
    coupon_pct: 6.5,
    total_raise_usd: 150_000_000,
  });

  const buyersQuery = trpc.hawkeye.buyers.useQuery();
  const matchMutation = trpc.hawkeye.match.useMutation();
  const teaserMutation = trpc.hawkeye.teaser.useMutation();
  const orderBookQuery = trpc.hawkeye.orderBook.useQuery(
    dealId ? { dealId } : undefined,
    { enabled: !!dealId },
  );
  const indicateMutation = trpc.hawkeye.indicate.useMutation({
    onSuccess: () => orderBookQuery.refetch(),
  });
  const allocateMutation = trpc.hawkeye.allocate.useMutation();

  const [indicationForm, setIndicationForm] = useState({ investorName: "", amount: "" });

  const matches = (matchMutation.data as any)?.matches ?? [];
  const orderBook = (orderBookQuery.data as any);

  if (summaryMode) {
    return (
      <div className="p-4">
        <div className="flex items-center gap-2 font-mono text-[0.62rem] font-semibold uppercase tracking-[0.16em] text-fuchsia-200">
          <Target size={14} /> Hawkeye Placement
        </div>
        <div className="mt-3 grid grid-cols-2 gap-3">
          <div>
            <p className="font-mono text-[0.56rem] uppercase tracking-[0.14em] text-slate-500">Buyers</p>
            <p className="font-mono text-xl font-semibold text-white">{(buyersQuery.data as any)?.total ?? "—"}</p>
          </div>
          <div>
            <p className="font-mono text-[0.56rem] uppercase tracking-[0.14em] text-slate-500">Book</p>
            <p className="font-mono text-xl font-semibold text-amber-100">{orderBook ? money(orderBook.total_indications_usd) : "—"}</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <div className="flex items-center gap-2 font-mono text-[0.72rem] font-semibold uppercase tracking-[0.16em] text-fuchsia-200">
          <Target size={17} /> Hawkeye — Institutional Placement Engine
        </div>
        <p className="mt-1 text-sm text-slate-400">Buyer matching, AI teasers, order book management, and allocation.</p>
      </div>

      {/* Match controls */}
      <div className="rounded-2xl border border-fuchsia-300/25 bg-black/35 p-5">
        <h3 className="font-mono text-[0.68rem] font-semibold uppercase tracking-[0.14em] text-white">Buyer Matching</h3>
        <div className="mt-3 grid grid-cols-4 gap-3">
          <div>
            <label className="font-mono text-[0.56rem] uppercase tracking-[0.14em] text-slate-500">Sector</label>
            <select
              value={matchParams.naics}
              onChange={(e) => setMatchParams({ ...matchParams, naics: e.target.value })}
              className="w-full rounded-xl border border-fuchsia-300/20 bg-black/45 px-3 py-2 font-mono text-sm text-slate-100 outline-none"
            >
              <option value="6232">Assisted Living</option>
              <option value="6231">Nursing Care</option>
              <option value="5311">Property Mgmt</option>
            </select>
          </div>
          <div>
            <label className="font-mono text-[0.56rem] uppercase tracking-[0.14em] text-slate-500">Rating</label>
            <select
              value={matchParams.rating}
              onChange={(e) => setMatchParams({ ...matchParams, rating: e.target.value })}
              className="w-full rounded-xl border border-fuchsia-300/20 bg-black/45 px-3 py-2 font-mono text-sm text-slate-100 outline-none"
            >
              <option value="A">A</option>
              <option value="BBB+">BBB+</option>
              <option value="BBB">BBB</option>
              <option value="BBB-">BBB-</option>
            </select>
          </div>
          <div>
            <label className="font-mono text-[0.56rem] uppercase tracking-[0.14em] text-slate-500">Coupon %</label>
            <input
              type="number"
              value={matchParams.coupon_pct}
              onChange={(e) => setMatchParams({ ...matchParams, coupon_pct: Number(e.target.value) })}
              step="0.25"
              className="w-full rounded-xl border border-fuchsia-300/20 bg-black/45 px-3 py-2 font-mono text-sm text-slate-100 outline-none"
            />
          </div>
          <div className="flex items-end">
            <Button
              onClick={() => matchMutation.mutate(matchParams)}
              disabled={matchMutation.isPending}
              className="w-full rounded-xl border border-fuchsia-300/35 bg-fuchsia-500/12 px-4 py-2.5 font-mono text-[0.72rem] font-semibold uppercase tracking-[0.14em] text-fuchsia-100 hover:bg-fuchsia-500/20"
            >
              {matchMutation.isPending ? <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" /> : <Users className="mr-2 h-3.5 w-3.5" />}
              Match Buyers
            </Button>
          </div>
        </div>
      </div>

      {/* Match results */}
      {matches.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="font-mono text-[0.68rem] font-semibold uppercase tracking-[0.14em] text-white">
              {(matchMutation.data as any)?.total_matched} Matched · {money((matchMutation.data as any)?.potential_demand_usd ?? 0)} potential demand
            </h3>
            <Button
              onClick={() => teaserMutation.mutate({
                dealId: dealId || "new",
                dealName: "NEST Bond Offering",
                totalRaise: matchParams.total_raise_usd,
                coupon: matchParams.coupon_pct,
                rating: matchParams.rating,
              })}
              disabled={teaserMutation.isPending}
              className="rounded-lg border border-cyan-300/30 bg-cyan-400/10 px-3 py-1.5 font-mono text-[0.62rem] font-semibold uppercase tracking-[0.12em] text-cyan-100 hover:bg-cyan-400/20"
            >
              <FileText className="mr-1 h-3 w-3" /> {teaserMutation.isPending ? "Generating..." : "Generate AI Teaser"}
            </Button>
          </div>

          {matches.map((buyer: any) => {
            const tier = buyer.match_score >= 70 ? "high" : buyer.match_score >= 40 ? "medium" : "low";
            return (
              <article key={buyer.id} className={`rounded-2xl border p-4 ${matchColors[tier]}`}>
                <div className="flex items-start justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <h4 className="font-mono text-sm font-semibold text-white">{buyer.name}</h4>
                      <span className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5 font-mono text-[0.56rem] uppercase text-slate-400">{buyer.type}</span>
                      {buyer.relationship === "existing" && (
                        <span className="rounded-full border border-emerald-300/30 bg-emerald-400/10 px-2 py-0.5 font-mono text-[0.56rem] uppercase text-emerald-200">existing</span>
                      )}
                    </div>
                    <p className="mt-1 font-mono text-[0.62rem] text-slate-400">
                      AUM: {money(buyer.aum_usd)} · Ticket: {money(buyer.min_ticket_usd)}–{money(buyer.max_ticket_usd)} · Floor: {buyer.yield_floor_pct}%
                    </p>
                    <div className="mt-1 flex flex-wrap gap-1">
                      {buyer.rationale?.map((r: string, i: number) => (
                        <span key={i} className="rounded bg-white/5 px-1.5 py-0.5 font-mono text-[0.52rem] text-slate-400">{r}</span>
                      ))}
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="font-mono text-lg font-semibold text-white">{buyer.match_score}/100</p>
                    <p className="font-mono text-[0.56rem] text-amber-200">Suggested: {money(buyer.suggested_ticket_usd)}</p>
                  </div>
                </div>
              </article>
            );
          })}
        </div>
      )}

      {/* AI Teaser */}
      {teaserMutation.data && (
        <div className="rounded-2xl border border-cyan-300/25 bg-black/35 p-5">
          <div className="flex items-center gap-2 font-mono text-[0.62rem] font-semibold uppercase tracking-[0.16em] text-cyan-200">
            <FileText size={14} /> AI-Generated Investor Teaser
          </div>
          <p className="mt-3 whitespace-pre-wrap font-mono text-sm leading-6 text-slate-300">
            {(teaserMutation.data as any).content}
          </p>
        </div>
      )}

      {/* Order Book */}
      {dealId && (
        <div className="rounded-2xl border border-amber-300/25 bg-black/35 p-5">
          <div className="flex items-center justify-between">
            <h3 className="flex items-center gap-2 font-mono text-[0.68rem] font-semibold uppercase tracking-[0.14em] text-amber-200">
              <BookOpen size={14} /> Order Book
              {orderBook && <span className="text-slate-400">· {orderBook.order_count} orders · {money(orderBook.total_indications_usd)}</span>}
            </h3>
            <Button
              onClick={() => allocateMutation.mutate({ dealId, params: { target_raise_usd: matchParams.total_raise_usd } })}
              disabled={allocateMutation.isPending || !orderBook?.order_count}
              className="rounded-lg border border-emerald-300/30 bg-emerald-400/10 px-3 py-1.5 font-mono text-[0.62rem] font-semibold uppercase tracking-[0.12em] text-emerald-100 hover:bg-emerald-400/20"
            >
              <CheckCircle2 className="mr-1 h-3 w-3" /> Run Allocation
            </Button>
          </div>

          {/* Add indication */}
          <div className="mt-3 flex gap-2">
            <input
              type="text"
              value={indicationForm.investorName}
              onChange={(e) => setIndicationForm({ ...indicationForm, investorName: e.target.value })}
              placeholder="Investor name"
              className="flex-1 rounded-xl border border-amber-300/20 bg-black/45 px-3 py-2 font-mono text-sm text-slate-100 outline-none placeholder:text-slate-600"
            />
            <input
              type="number"
              value={indicationForm.amount}
              onChange={(e) => setIndicationForm({ ...indicationForm, amount: e.target.value })}
              placeholder="Amount ($)"
              className="w-40 rounded-xl border border-amber-300/20 bg-black/45 px-3 py-2 font-mono text-sm text-slate-100 outline-none placeholder:text-slate-600"
            />
            <Button
              onClick={() => {
                if (indicationForm.investorName && indicationForm.amount) {
                  indicateMutation.mutate({
                    dealId,
                    indication: {
                      investorName: indicationForm.investorName,
                      amount_usd: Number(indicationForm.amount),
                    },
                  });
                  setIndicationForm({ investorName: "", amount: "" });
                }
              }}
              disabled={indicateMutation.isPending}
              className="rounded-xl border border-amber-300/35 bg-amber-300/12 px-4 py-2 font-mono text-[0.72rem] font-semibold uppercase text-amber-100 hover:bg-amber-300/20"
            >
              <Send className="mr-1 h-3 w-3" /> Indicate
            </Button>
          </div>

          {/* Order list */}
          {orderBook?.orders?.length > 0 && (
            <div className="mt-3 space-y-1">
              {orderBook.orders.map((order: any) => (
                <div key={order.id} className="flex items-center justify-between rounded-xl border border-white/5 bg-white/[0.02] px-3 py-2">
                  <span className="font-mono text-sm text-white">{order.investorName}</span>
                  <span className="font-mono text-sm font-semibold text-amber-100">{money(order.amount_usd)}</span>
                </div>
              ))}
            </div>
          )}

          {/* Allocation results */}
          {allocateMutation.data && (
            <div className="mt-4 rounded-xl border border-emerald-300/25 bg-emerald-400/8 p-3">
              <p className="font-mono text-[0.62rem] font-semibold uppercase text-emerald-200">
                Allocation complete · {(allocateMutation.data as any).coverage_pct}% coverage · {money((allocateMutation.data as any).total_allocated_usd)} allocated
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
