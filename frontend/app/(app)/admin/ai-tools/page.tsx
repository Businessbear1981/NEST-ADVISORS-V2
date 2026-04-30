'use client';
import { useState, useEffect } from 'react';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export default function AIToolsPage() {
  const [tools, setTools] = useState<any>(null);
  const [rates, setRates] = useState<any>(null);
  const [taskType, setTaskType] = useState('credit_memo');
  const [prompt, setPrompt] = useState('');
  const [routeResult, setRouteResult] = useState<any>(null);
  const [routing, setRouting] = useState(false);

  useEffect(() => {
    const token = localStorage.getItem('nest_token');
    fetch(`${API}/api/ai/status`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.json()).then(d => setTools(d.data)).catch(() => {});
    fetch(`${API}/api/ai/market-rates`).then(r => r.json()).then(d => setRates(d.data)).catch(() => {});
  }, []);

  async function routeTask() {
    if (!prompt.trim()) return;
    setRouting(true);
    const token = localStorage.getItem('nest_token');
    const res = await fetch(`${API}/api/ai/route`, {
      method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ task_type: taskType, prompt }),
    });
    const d = await res.json();
    setRouteResult(d.data);
    setRouting(false);
  }

  const TASK_TYPES = ['credit_memo', 'business_plan', 'risk_assessment', 'feasibility_narrative', 'bd_outreach', 'investor_teaser', 'bond_structuring', 'executive_summary', 'ma_analysis', 'legal_summary', 'market_rates', 'treasury_rates', 'market_news', 'competitor_intel'];

  const toolList = tools?.tools ? Object.entries(tools.tools) : [];

  return (
    <div>
      <h1 className="serif" style={{ fontSize: 36, color: 'var(--gold)', marginBottom: 4 }}>AI Tool Network</h1>
      <p className="sage" style={{ fontSize: 13, marginBottom: 32, fontStyle: 'italic' }}>NEST Advisors is the power strip. Every AI tool plugs in.</p>

      {/* Power Strip Visual */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 12, marginBottom: 32 }}>
        {toolList.map(([name, info]: [string, any]) => (
          <div key={name} className="card" style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <span className="status-dot" style={{ background: info.configured ? 'var(--sage)' : '#333', animation: info.configured ? 'pulse-dot 2s infinite' : 'none' }} />
            <div>
              <div style={{ fontSize: 13, fontWeight: 500, textTransform: 'capitalize' }}>{name}</div>
              <div className="mono" style={{ fontSize: 9, color: 'var(--moss)' }}>{info.model || info.use || '—'}</div>
              {info.primary && <span className="tag-gold" style={{ fontSize: 8 }}>PRIMARY</span>}
            </div>
          </div>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24 }}>
        {/* Market Rates */}
        <div className="card">
          <div className="section-header">Live Market Rates</div>
          {rates && (
            <>
              <span className={rates.source === 'grok' ? 'tag-gold' : rates.source === 'FRED' ? 'tag-green' : 'tag-gray'} style={{ marginBottom: 12, display: 'inline-block' }}>
                Source: {rates.source}
              </span>
              {rates.treasury_10yr_pct && (
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8, marginTop: 12 }}>
                  <div className="kpi"><div className="kpi-label">10yr Treasury</div><div className="kpi-value">{rates.treasury_10yr_pct}%</div></div>
                  <div className="kpi"><div className="kpi-label">SOFR</div><div className="kpi-value">{rates.sofr_pct}%</div></div>
                  <div className="kpi"><div className="kpi-label">IG Spread</div><div className="kpi-value">{rates.ig_spread_bps}bp</div></div>
                </div>
              )}
              {rates.data && <p className="sage" style={{ fontSize: 12, marginTop: 12 }}>{rates.data}</p>}
            </>
          )}
        </div>

        {/* Task Router */}
        <div className="card">
          <div className="section-header">Task Router</div>
          <select className="nest-input nest-select" value={taskType} onChange={e => setTaskType(e.target.value)} style={{ marginBottom: 12 }}>
            {TASK_TYPES.map(t => <option key={t} value={t}>{t.replace(/_/g, ' ')}</option>)}
          </select>
          <textarea className="nest-input" rows={4} placeholder="Enter prompt..." value={prompt} onChange={e => setPrompt(e.target.value)} style={{ marginBottom: 12, resize: 'vertical' }} />
          <button className="btn-gold" onClick={routeTask} disabled={routing || !prompt.trim()}>
            {routing ? 'Routing...' : 'Route Task'}
          </button>
        </div>
      </div>

      {routeResult && (
        <div className="card" style={{ marginTop: 24 }}>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 12 }}>
            <span className="tag-gold">Tool: {routeResult.tool}</span>
            {routeResult.model && <span className="tag-gray">{routeResult.model}</span>}
            <span className={routeResult.success ? 'tag-green' : 'tag-red'}>{routeResult.success ? 'Success' : 'Failed'}</span>
          </div>
          <div style={{ fontSize: 13, lineHeight: 1.6, whiteSpace: 'pre-wrap' }}>{routeResult.content || routeResult.error}</div>
        </div>
      )}
    </div>
  );
}
