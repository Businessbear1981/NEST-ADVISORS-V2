import { useState } from "react";

const LS_KEY = "nest_access_granted";

export function hasAccess(): boolean {
  if (typeof window === "undefined") return false;
  const params = new URLSearchParams(window.location.search);
  if (params.get("access") === "nest2026") {
    try { localStorage.setItem(LS_KEY, "true"); } catch {}
    return true;
  }
  try { return localStorage.getItem(LS_KEY) === "true"; } catch { return false; }
}

export default function ComingSoon() {
  const [email, setEmail] = useState("");
  const [submitted, setSubmitted] = useState(false);

  return (
    <div className="min-h-screen flex flex-col items-center justify-center relative overflow-hidden"
      style={{ background: "linear-gradient(145deg, #020508 0%, #07101a 40%, #0a1520 60%, #04080e 100%)" }}>

      <div className="absolute inset-0 pointer-events-none opacity-[0.025]"
        style={{
          backgroundImage: "linear-gradient(rgba(196,160,72,0.2) 1px, transparent 1px), linear-gradient(90deg, rgba(196,160,72,0.2) 1px, transparent 1px)",
          backgroundSize: "60px 60px",
        }} />

      <div className="absolute top-[20%] left-[15%] w-[500px] h-[500px] rounded-full opacity-[0.06]"
        style={{ background: "radial-gradient(circle, rgba(34,211,238,0.4), transparent 70%)" }} />
      <div className="absolute bottom-[15%] right-[10%] w-[400px] h-[400px] rounded-full opacity-[0.05]"
        style={{ background: "radial-gradient(circle, rgba(196,160,72,0.4), transparent 70%)" }} />

      <div className="relative z-10 max-w-lg w-full mx-auto px-6 text-center">
        <div className="mb-10">
          <div className="flex items-center justify-center gap-3 mb-6">
            <div className="w-10 h-10 rounded-xl border border-[#C4A048]/30 bg-[#C4A048]/10 flex items-center justify-center">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#C4A048" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 2L2 7l10 5 10-5-10-5z" />
                <path d="M2 17l10 5 10-5" />
                <path d="M2 12l10 5 10-5" />
              </svg>
            </div>
          </div>

          <h1 className="text-4xl sm:text-5xl font-light tracking-tight text-white/95 mb-2"
            style={{ fontFamily: "'Cormorant Garamond', serif" }}>
            NEST Advisors
          </h1>
          <p className="text-sm font-light tracking-[0.25em] uppercase text-[#C4A048]/70 mb-8"
            style={{ fontFamily: "'Space Grotesk', sans-serif" }}>
            The Architecture of Permanent Wealth
          </p>

          <div className="w-16 h-px bg-gradient-to-r from-transparent via-[#C4A048]/40 to-transparent mx-auto mb-8" />

          <p className="text-base text-slate-400 leading-relaxed max-w-md mx-auto mb-2"
            style={{ fontFamily: "'Space Grotesk', sans-serif" }}>
            Private bond structuring and capital markets intelligence for institutional investors.
          </p>
          <p className="text-sm text-slate-500"
            style={{ fontFamily: "'Space Grotesk', sans-serif" }}>
            Our platform is currently in private development.
          </p>
        </div>

        <div className="rounded-2xl border border-white/[0.06] bg-white/[0.02] backdrop-blur-sm p-8 mb-8">
          <p className="font-mono text-xs uppercase tracking-[0.2em] text-[#C4A048]/60 mb-6">
            Coming Soon
          </p>

          {submitted ? (
            <div className="py-4">
              <div className="w-10 h-10 rounded-full border border-emerald-400/30 bg-emerald-400/10 flex items-center justify-center mx-auto mb-3">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#34d399" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="20 6 9 17 4 12" />
                </svg>
              </div>
              <p className="text-sm text-slate-300" style={{ fontFamily: "'Space Grotesk', sans-serif" }}>
                We'll be in touch.
              </p>
            </div>
          ) : (
            <form onSubmit={(e) => { e.preventDefault(); if (email) setSubmitted(true); }}
              className="flex gap-2">
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="Email for early access"
                className="flex-1 rounded-lg border border-white/[0.08] bg-white/[0.03] px-4 py-2.5 text-sm text-white placeholder:text-slate-600 focus:outline-none focus:border-[#C4A048]/30 focus:ring-1 focus:ring-[#C4A048]/20 transition"
                style={{ fontFamily: "'Space Grotesk', sans-serif" }}
              />
              <button
                type="submit"
                className="rounded-lg border border-[#C4A048]/25 bg-[#C4A048]/10 px-5 py-2.5 text-sm font-medium text-[#C4A048] hover:bg-[#C4A048]/20 hover:border-[#C4A048]/40 transition-all"
                style={{ fontFamily: "'Space Grotesk', sans-serif" }}>
                Notify Me
              </button>
            </form>
          )}
        </div>

        <div className="flex items-center justify-center gap-6 text-[0.65rem] font-mono uppercase tracking-[0.15em] text-slate-600">
          <span>Arden Edge Capital</span>
          <span className="text-slate-700">&times;</span>
          <span>Soparrow Capital</span>
        </div>
      </div>

      <div className="absolute bottom-6 text-center">
        <p className="font-mono text-[0.6rem] text-slate-700 tracking-wider">
          &copy; {new Date().getFullYear()} NEST Advisors. All rights reserved.
        </p>
      </div>
    </div>
  );
}
