import React, { useEffect, useState } from 'react';
import {
  AlertTriangle,
  Package,
  Warehouse as WarehouseIcon,
  CheckCircle2,
  TrendingUp,
  ArrowRight,
  RefreshCw,
  Search,
  Filter,
} from 'lucide-react';
import { ReplenishmentAlert, SKU } from '../types';
import { fetchReplenishmentAlerts, fetchSKUs } from '../api';

interface DashboardViewProps {
  onNavigate: (tab: string, context?: { skuId?: string; warehouseId?: string }) => void;
}

export const DashboardView: React.FC<DashboardViewProps> = ({ onNavigate }) => {
  const [alerts, setAlerts] = useState<ReplenishmentAlert[]>([]);
  const [skus, setSkus] = useState<SKU[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterText, setFilterText] = useState('');
  const [statusFilter, setStatusFilter] = useState<'ALL' | 'CRITICAL' | 'WARNING'>('ALL');

  const loadData = async () => {
    setLoading(true);
    try {
      const [alertsData, skusData] = await Promise.all([
        fetchReplenishmentAlerts(100),
        fetchSKUs(),
      ]);
      setAlerts(alertsData);
      setSkus(skusData);
    } catch (err) {
      console.error('Failed to load dashboard data:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const criticalCount = alerts.filter((a) => a.status === 'CRITICAL').length;
  const warningCount = alerts.filter((a) => a.status === 'WARNING').length;

  const filteredAlerts = alerts.filter((a) => {
    const matchesText =
      a.sku_id.toLowerCase().includes(filterText.toLowerCase()) ||
      a.warehouse_id.toLowerCase().includes(filterText.toLowerCase());
    const matchesStatus = statusFilter === 'ALL' || a.status === statusFilter;
    return matchesText && matchesStatus;
  });

  return (
    <div className="page-body">
      {/* KPI Stats Grid */}
      <div className="stats-grid">
        <div className="glass-panel stat-card">
          <div className="stat-label">
            <span>Critical Deficit Items</span>
            <AlertTriangle size={18} color="#f43f5e" />
          </div>
          <div className="stat-value" style={{ color: '#f43f5e' }}>
            {criticalCount}
          </div>
          <div className="stat-sub">Stock depleted below safety buffer</div>
        </div>

        <div className="glass-panel stat-card">
          <div className="stat-label">
            <span>Reorder Warnings</span>
            <TrendingUp size={18} color="#f59e0b" />
          </div>
          <div className="stat-value" style={{ color: '#f59e0b' }}>
            {warningCount}
          </div>
          <div className="stat-sub">Stock below Reorder Point (ROP)</div>
        </div>

        <div className="glass-panel stat-card">
          <div className="stat-label">
            <span>Active SKUs</span>
            <Package size={18} color="#6366f1" />
          </div>
          <div className="stat-value">{skus.length || 50}</div>
          <div className="stat-sub">Across 5 price & tier categories</div>
        </div>

        <div className="glass-panel stat-card">
          <div className="stat-label">
            <span>Regional Warehouses</span>
            <WarehouseIcon size={18} color="#06b6d4" />
          </div>
          <div className="stat-value">5</div>
          <div className="stat-sub">Delhi, Mumbai, Chennai, Kolkata, Pune</div>
        </div>
      </div>

      {/* Main Alert & Replenishment Table */}
      <div className="glass-panel" style={{ padding: '24px' }}>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            marginBottom: '20px',
            flexWrap: 'wrap',
            gap: '12px',
          }}
        >
          <div>
            <h2 style={{ fontSize: '18px', fontWeight: 600, color: '#fff' }}>
              Priority Replenishment & Stockout Alerts
            </h2>
            <p style={{ fontSize: '13px', color: 'var(--text-muted)', marginTop: '2px' }}>
              Real-time monitoring of SKU stock levels against dynamic safety stock & ROP thresholds
            </p>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div style={{ position: 'relative' }}>
              <Search
                size={16}
                color="#94a3b8"
                style={{ position: 'absolute', left: '10px', top: '9px' }}
              />
              <input
                type="text"
                placeholder="Search SKU or WH..."
                value={filterText}
                onChange={(e) => setFilterText(e.target.value)}
                className="form-input"
                style={{ paddingLeft: '32px', width: '180px' }}
              />
            </div>

            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as any)}
              className="form-select"
            >
              <option value="ALL">All Risk Levels</option>
              <option value="CRITICAL">Critical Only</option>
              <option value="WARNING">Warnings Only</option>
            </select>

            <button
              onClick={loadData}
              className="btn btn-secondary"
              title="Refresh alerts"
            >
              <RefreshCw size={15} className={loading ? 'animate-spin' : ''} />
            </button>
          </div>
        </div>

        {loading ? (
          <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>
            Loading replenishment data...
          </div>
        ) : filteredAlerts.length === 0 ? (
          <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>
            No stock alerts matching current filter. All items healthy!
          </div>
        ) : (
          <div className="table-container">
            <table className="custom-table">
              <thead>
                <tr>
                  <th>Status</th>
                  <th>SKU ID</th>
                  <th>Warehouse</th>
                  <th>Current Stock</th>
                  <th>Reorder Point</th>
                  <th>Safety Stock</th>
                  <th>Deficit</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredAlerts.slice(0, 15).map((item) => {
                  const isCrit = item.status === 'CRITICAL';
                  return (
                    <tr key={`${item.sku_id}-${item.warehouse_id}`}>
                      <td>
                        <span className={`badge ${isCrit ? 'badge-critical' : 'badge-warning'}`}>
                          <span className="badge-pulse" />
                          {item.status}
                        </span>
                      </td>
                      <td style={{ fontWeight: 600, color: '#fff' }}>{item.sku_id}</td>
                      <td>{item.warehouse_id}</td>
                      <td style={{ fontWeight: 600 }}>{item.current_stock.toLocaleString()}</td>
                      <td>{item.reorder_point.toLocaleString()}</td>
                      <td>{item.safety_stock.toLocaleString()}</td>
                      <td style={{ color: isCrit ? '#fb7185' : '#fbbf24', fontWeight: 600 }}>
                        {item.deficit > 0 ? `-${item.deficit.toLocaleString()}` : '0'}
                      </td>
                      <td>
                        <div style={{ display: 'flex', gap: '8px' }}>
                          <button
                            className="btn btn-primary"
                            style={{ padding: '5px 10px', fontSize: '11px' }}
                            onClick={() =>
                              onNavigate('chat', {
                                skuId: item.sku_id,
                                warehouseId: item.warehouse_id,
                              })
                            }
                          >
                            AI Reason
                          </button>
                          <button
                            className="btn btn-secondary"
                            style={{ padding: '5px 10px', fontSize: '11px' }}
                            onClick={() =>
                              onNavigate('transfers', {
                                skuId: item.sku_id,
                                warehouseId: item.warehouse_id,
                              })
                            }
                          >
                            Transfer
                          </button>
                          <button
                            className="btn btn-secondary"
                            style={{ padding: '5px 10px', fontSize: '11px' }}
                            onClick={() =>
                              onNavigate('forecast', {
                                skuId: item.sku_id,
                                warehouseId: item.warehouse_id,
                              })
                            }
                          >
                            Forecast
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
