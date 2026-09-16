import React, { useState, useEffect } from 'react';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
  ReferenceLine,
} from 'recharts';
import { SlidersHorizontal, AlertTriangle, TrendingDown, DollarSign } from 'lucide-react';
import { WhatIfResult, SKU } from '../types';
import { runWhatIfSimulation, fetchSKUs } from '../api';

export const WhatIfView: React.FC = () => {
  const [skuId, setSkuId] = useState('SKU_001');
  const [warehouseId, setWarehouseId] = useState('WH_01');
  const [demandShockPct, setDemandShockPct] = useState(25);
  const [delayDays, setDelayDays] = useState(4);
  const [promoLiftPct, setPromoLiftPct] = useState(20);

  const [skus, setSkus] = useState<SKU[]>([]);
  const [simResult, setSimResult] = useState<WhatIfResult | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchSKUs().then((data) => setSkus(data));
  }, []);

  const runSim = async () => {
    setLoading(true);
    try {
      const data = await runWhatIfSimulation({
        sku_id: skuId,
        warehouse_id: warehouseId,
        demand_shock_pct: demandShockPct,
        lead_time_delay_days: delayDays,
        promo_lift_pct: promoLiftPct,
        horizon_days: 30,
      });
      setSimResult(data);
    } catch (err) {
      console.error('What-if error:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    runSim();
  }, [skuId, warehouseId, demandShockPct, delayDays, promoLiftPct]);

  return (
    <div className="page-body">
      {/* Simulation Controls Panel */}
      <div className="glass-panel" style={{ padding: '24px', marginBottom: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '18px' }}>
          <SlidersHorizontal size={20} color="#6366f1" />
          <h2 style={{ fontSize: '17px', fontWeight: 600, color: '#fff' }}>
            What-If Scenario Stress Testing
          </h2>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '20px' }}>
          <div>
            <label style={{ fontSize: '12px', color: 'var(--text-muted)', display: 'block', marginBottom: '6px' }}>
              Target SKU
            </label>
            <select value={skuId} onChange={(e) => setSkuId(e.target.value)} className="form-select" style={{ width: '100%' }}>
              {skus.map((s) => (
                <option key={s.sku_id} value={s.sku_id}>
                  {s.sku_id} ({s.category})
                </option>
              ))}
            </select>
          </div>

          <div>
            <label style={{ fontSize: '12px', color: 'var(--text-muted)', display: 'block', marginBottom: '6px' }}>
              Warehouse Hub
            </label>
            <select value={warehouseId} onChange={(e) => setWarehouseId(e.target.value)} className="form-select" style={{ width: '100%' }}>
              <option value="WH_01">WH_01 - Delhi</option>
              <option value="WH_02">WH_02 - Mumbai</option>
              <option value="WH_03">WH_03 - Chennai</option>
              <option value="WH_04">WH_04 - Kolkata</option>
              <option value="WH_05">WH_05 - Pune</option>
            </select>
          </div>

          {/* Slider 1: Demand Shock */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', marginBottom: '6px' }}>
              <span style={{ color: 'var(--text-muted)' }}>Demand Surge / Drop</span>
              <span style={{ color: demandShockPct >= 0 ? '#38bdf8' : '#fb7185', fontWeight: 700 }}>
                {demandShockPct > 0 ? `+${demandShockPct}%` : `${demandShockPct}%`}
              </span>
            </div>
            <input
              type="range"
              min="-40"
              max="100"
              step="5"
              value={demandShockPct}
              onChange={(e) => setDemandShockPct(Number(e.target.value))}
              style={{ width: '100%' }}
            />
          </div>

          {/* Slider 2: Supplier Delay */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', marginBottom: '6px' }}>
              <span style={{ color: 'var(--text-muted)' }}>Supplier Lead-Time Delay</span>
              <span style={{ color: delayDays > 0 ? '#fbbf24' : '#10b981', fontWeight: 700 }}>
                +{delayDays} days
              </span>
            </div>
            <input
              type="range"
              min="0"
              max="20"
              step="1"
              value={delayDays}
              onChange={(e) => setDelayDays(Number(e.target.value))}
              style={{ width: '100%' }}
            />
          </div>

          {/* Slider 3: Promo Lift */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', marginBottom: '6px' }}>
              <span style={{ color: 'var(--text-muted)' }}>Festive Campaign Lift</span>
              <span style={{ color: '#f59e0b', fontWeight: 700 }}>
                +{promoLiftPct}%
              </span>
            </div>
            <input
              type="range"
              min="0"
              max="80"
              step="5"
              value={promoLiftPct}
              onChange={(e) => setPromoLiftPct(Number(e.target.value))}
              style={{ width: '100%' }}
            />
          </div>
        </div>
      </div>

      {/* Stress Outcome KPIs */}
      <div className="stats-grid">
        <div className="glass-panel stat-card">
          <div className="stat-label">Stockout Status</div>
          <div
            className="stat-value"
            style={{ color: simResult?.stockout_occurred ? '#f43f5e' : '#10b981' }}
          >
            {simResult?.stockout_occurred ? `Stockout on Day ${simResult.stockout_day}` : 'No Stockout'}
          </div>
          <div className="stat-sub">
            {simResult?.stockout_occurred
              ? `Estimated depletion: ${simResult.stockout_date}`
              : 'Safety stock holds throughout horizon'}
          </div>
        </div>

        <div className="glass-panel stat-card">
          <div className="stat-label">Revenue at Risk</div>
          <div className="stat-value" style={{ color: '#fb7185' }}>
            ₹{(simResult?.revenue_at_risk || 0).toLocaleString()}
          </div>
          <div className="stat-sub">Unmet demand units: {simResult?.total_unmet_demand || 0}</div>
        </div>

        <div className="glass-panel stat-card">
          <div className="stat-label">Recommended Safety Buffer</div>
          <div className="stat-value" style={{ color: '#38bdf8' }}>
            {simResult?.recommended_safety_stock_adjustment || 50} units
          </div>
          <div className="stat-sub">Recommended dynamic target to hedge this scenario</div>
        </div>
      </div>

      {/* Trajectory Area Chart */}
      <div className="glass-panel" style={{ padding: '24px' }}>
        <div style={{ marginBottom: '20px' }}>
          <h2 style={{ fontSize: '17px', fontWeight: 600, color: '#fff' }}>
            Simulated Inventory Trajectory Under Stress
          </h2>
          <p style={{ fontSize: '13px', color: 'var(--text-muted)', marginTop: '2px' }}>
            Daily on-hand stock progression vs. simulated demand surges & delayed replenishment
          </p>
        </div>

        <div style={{ width: '100%', height: '360px' }}>
          <ResponsiveContainer>
            <AreaChart data={simResult?.trajectory || []} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="stockGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#10b981" stopOpacity={0.4} />
                  <stop offset="95%" stopColor="#10b981" stopOpacity={0.02} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
              <XAxis dataKey="day" stroke="#64748b" tickFormatter={(v) => `Day ${v}`} />
              <YAxis stroke="#64748b" />
              <Tooltip
                contentStyle={{
                  backgroundColor: 'rgba(15, 23, 42, 0.95)',
                  border: '1px solid rgba(255,255,255,0.1)',
                  borderRadius: '8px',
                  fontSize: '12px',
                }}
              />
              <Legend wrapperStyle={{ fontSize: '12px', paddingTop: '10px' }} />

              <Area
                type="monotone"
                dataKey="stock_level"
                name="Projected On-Hand Stock"
                stroke="#10b981"
                fill="url(#stockGradient)"
                strokeWidth={2.5}
              />
              <Area
                type="monotone"
                dataKey="projected_demand"
                name="Simulated Daily Demand"
                stroke="#f59e0b"
                fill="transparent"
                strokeWidth={1.5}
                strokeDasharray="4 4"
              />
              <ReferenceLine y={0} stroke="#f43f5e" strokeDasharray="3 3" label="Stockout Threshold" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
};
