import { useState } from "react";
import { Loader2, CloudRain, Flame, Wind, Thermometer, AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { trpc } from "@/lib/trpc";

const riskIcons: Record<string, any> = {
  flood: CloudRain, hurricane: Wind, wildfire: Flame,
  earthquake: AlertTriangle, heat_stress: Thermometer,
};

function riskColor(val: number) {
  if (val >= 70) return "text-red-300 border-red-400/30 bg-red-500/10";
  if (val >= 40) return "text-amber-200 border-amber-300/30 bg-amber-300/10";
  return "text-emerald-200 border-emerald-300/30 bg-emerald-400/10";
}

export default function ClimateResilienceDashboard({ dealId, summaryMode }: { dealId?: string; summaryMode?: boolean }) {
  const [state, setState] = useState("FL");
  const climateMutation = trpc.ratingEsg.climateAssess.useMutation();

  const data = climateMutation.data as any;

  if (summaryMode) {
    return (
      <div className="p-4">
        <div className="flex items-center gap-2 font-mono text-[0.62rem] font-semibold uppercase tracking-[0.16em] text-cyan-200">
          <CloudRain size={14} /> Climate Resilience
        </div>
        <p className="mt-2 font-mono text-sm text-slate-400">Physical + transition risk scoring</p>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 font-mono text-[0.72rem] font-semibold uppercase tracking-[0.16em] text-cyan-200">
          <CloudRain size={17} /> Climate Resilience Assessment
        </div>
        <div className="flex gap-2">
          <select value={state} onChange={(e) => setState(e.target.value)} className="rounded-xl border border-cyan-300/20 bg-black/45 px-3 py-2 font-mono text-sm text-slate-100 outline-none">
            {["FL", "CA", "TX", "AZ", "WA"].map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
          <Button onClick={() => climateMutation.mutate({ state })} disabled={climateMutation.isPending}
            className="rounded-xl border border-cyan-300/35 bg-cyan-400/12 px-4 py-2 font-mono text-[0.72rem] font-semibold uppercase text-cyan-100 hover:bg-cyan-400/20">
            {climateMutation.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : "Assess"}
          </Button>
        </div>
      </div>

      {data && (
        <>
          <div className="grid grid-cols-3 gap-3">
            <div className="rounded-xl border border-white/10 bg-white/[0.035] p-3 text-center">
              <p className="font-mono text-[0.56rem] uppercase tracking-[0.14em] text-slate-500">Resilience Score</p>
              <p className={`font-mono text-2xl font-bold ${data.resilience_score >= 60 ? "text-emerald-200" : data.resilience_score >= 35 ? "text-amber-200" : "text-red-200"}`}>
                {data.resilience_score}/100
              </p>
            </div>
            <div className="rounded-xl border border-white/10 bg-white/[0.035] p-3 text-center">
              <p className="font-mono text-[0.56rem] uppercase tracking-[0.14em] text-slate-500">Insurance Adj.</p>
              <p className="font-mono text-2xl font-bold text-amber-100">{data.insurance_premium_multiplier}x</p>
            </div>
            <div className="rounded-xl border border-white/10 bg-white/[0.035] p-3 text-center">
              <p className="font-mono text-[0.56rem] uppercase tracking-[0.14em] text-slate-500">Rating Impact</p>
              <p className={`font-mono text-lg font-bold ${data.rating_impact === "Neutral" ? "text-emerald-200" : "text-red-200"}`}>{data.rating_impact}</p>
            </div>
          </div>

          <div className="grid grid-cols-5 gap-2">
            {Object.entries(data.physical_risk).map(([risk, val]: [string, any]) => {
              const Icon = riskIcons[risk] || AlertTriangle;
              return (
                <div key={risk} className={`rounded-xl border p-3 text-center ${riskColor(val)}`}>
                  <Icon size={18} className="mx-auto" />
                  <p className="mt-1 font-mono text-[0.56rem] uppercase">{risk.replace("_", " ")}</p>
                  <p className="font-mono text-lg font-bold">{val}</p>
                </div>
              );
            })}
          </div>

          {data.recommended_mitigations?.length > 0 && (
            <div className="space-y-1">
              <h4 className="font-mono text-[0.62rem] font-semibold uppercase tracking-[0.14em] text-slate-400">Required Mitigations</h4>
              {data.recommended_mitigations.map((m: any, i: number) => (
                <div key={i} className="flex items-center justify-between rounded-xl border border-white/5 bg-white/[0.02] px-3 py-2">
                  <span className="font-mono text-sm text-white">{m.action}</span>
                  <span className={`rounded-full border px-2 py-0.5 font-mono text-[0.56rem] uppercase ${m.priority === "high" ? "border-red-400/30 bg-red-500/10 text-red-200" : "border-amber-300/30 bg-amber-300/10 text-amber-200"}`}>
                    {m.priority}
                  </span>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
