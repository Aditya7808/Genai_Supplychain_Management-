import React, { useState, useEffect } from 'react';
import { ArrowLeftRight, Clock, Truck, ShieldCheck, CheckCircle2 } from 'lucide-react';
import { TransferOption, SKU } from '../types';
import { fetchTransferOptions, fetchSKUs, createApprovalRequest } from '../api';

interface TransfersViewProps {
  initialSkuId?: string;
  initialWarehouseId?: string;
}

export const TransfersView: React.FC<TransfersViewProps> = ({
  initialSkuId = 'SKU_001',
  initialWarehouseId = 'WH_01',
}) => {
  const [skuId, setSkuId] = useState(initialSkuId);
  const [warehouseId, setWarehouseId] = useState(initialWarehouseId);
  const [neededQty, setNeededQty] = useState(50);
  const [skus, setSkus] = useState<SKU[]>([]);
  const [options, setOptions] = useState<TransferOption[]>([]);
  const [loading, setLoading] = useState(false);
  const [submittedMsg, setSubmittedMsg] = useState<string | null>(null);

  useEffect(() => {
    fetchSKUs().then((data) => setSkus(data));
  }, []);

  const loadTransfers = async () => {
    setLoading(true);
    setSubmittedMsg(null);
    try {
      const data = await fetchTransferOptions(skuId, warehouseId, neededQty);
      setOptions(data);
    } catch (err) {
      console.error('Failed to load transfer options:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTransfers();
  }, [skuId, warehouseId, neededQty]);

  const handleQueueTransfer = async (opt: TransferOption) => {
    try {
      await createApprovalRequest({
        recommendation_type: 'WAREHOUSE_TRANSFER',
        sku_id: skuId,
        warehouse_id: warehouseId,
        action: `Transfer from ${opt.source_warehouse_id} (${opt.source_city})`,
        quantity: Math.round(opt.transferable_quantity),
        ai_reasoning: `AI Transfer Recommendation: Saves ${opt.days_saved} days vs. supplier order. Transit cost ₹${opt.total_transfer_cost.toLocaleString()}.`,
        ai_confidence: 0.95,
      });
      setSubmittedMsg(
        `Transfer proposal queued for human approval: ${Math.round(opt.transferable_quantity)} units from ${opt.source_city} (${opt.source_warehouse_id})`
      );
    } catch (e: any) {
      console.error(e);
      setSubmittedMsg(`Failed to submit proposal: ${e.message || 'Error'}`);
    }
  };

  return (
    <div className="page-body">
      {/* Control Strip */}
      <div
        className="glass-panel"
        style={{
          padding: '20px 24px',
          marginBottom: '24px',
          display: 'flex',
          alignItems: 'center',
          gap: '16px',
          flexWrap: 'wrap',
        }}
      >
        <div>
          <label style={{ fontSize: '11px', color: 'var(--text-muted)', display: 'block', marginBottom: '4px' }}>
            Target SKU in Deficit
          </label>
          <select value={skuId} onChange={(e) => setSkuId(e.target.value)} className="form-select">
            {skus.map((s) => (
              <option key={s.sku_id} value={s.sku_id}>
                {s.sku_id} - {s.category}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label style={{ fontSize: '11px', color: 'var(--text-muted)', display: 'block', marginBottom: '4px' }}>
            Deficit Receiving Warehouse
          </label>
          <select value={warehouseId} onChange={(e) => setWarehouseId(e.target.value)} className="form-select">
            <option value="WH_01">WH_01 - Delhi (North)</option>
            <option value="WH_02">WH_02 - Mumbai (West)</option>
            <option value="WH_03">WH_03 - Chennai (South)</option>
            <option value="WH_04">WH_04 - Kolkata (East)</option>
            <option value="WH_05">WH_05 - Pune (West)</option>
          </select>
        </div>

        <div>
          <label style={{ fontSize: '11px', color: 'var(--text-muted)', display: 'block', marginBottom: '4px' }}>
            Needed Units
          </label>
          <input
            type="number"
            value={neededQty}
            onChange={(e) => setNeededQty(Math.max(1, Number(e.target.value)))}
            className="form-input"
            style={{ width: '120px' }}
          />
        </div>
      </div>

      {submittedMsg && (
        <div
          className="badge badge-healthy"
          style={{ width: '100%', padding: '12px 18px', marginBottom: '20px', borderRadius: '8px' }}
        >
          <CheckCircle2 size={16} />
          <span>{submittedMsg}</span>
        </div>
      )}

      {/* Transfer Opportunities Cards */}
      <div className="glass-panel" style={{ padding: '24px' }}>
        <div style={{ marginBottom: '20px' }}>
          <h2 style={{ fontSize: '17px', fontWeight: 600, color: '#fff' }}>
            Candidate Surplus Warehouses for Rebalancing
          </h2>
          <p style={{ fontSize: '13px', color: 'var(--text-muted)', marginTop: '2px' }}>
            Comparing inter-warehouse transit days & costs against external supplier lead times
          </p>
        </div>

        {loading ? (
          <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>
            Evaluating inter-warehouse network routes and distance matrices...
          </div>
        ) : options.length === 0 ? (
          <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>
            No other warehouse currently has safe surplus of this SKU to transfer without risking its own stockout.
            <div style={{ marginTop: '8px', color: '#fbbf24' }}>
              Recommendation: Proceed with standard external Supplier Purchase Order.
            </div>
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '18px' }}>
            {options.map((opt) => (
              <div
                key={opt.source_warehouse_id}
                className="glass-panel"
                style={{
                  padding: '20px',
                  background: 'rgba(255,255,255,0.02)',
                  borderColor: opt.is_faster_than_supplier ? 'rgba(16, 185, 129, 0.3)' : 'var(--border-glass)',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '14px',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div style={{ fontSize: '15px', fontWeight: 700, color: '#fff' }}>
                    {opt.source_city} ({opt.source_warehouse_id})
                  </div>
                  {opt.is_faster_than_supplier && (
                    <span className="badge badge-healthy" style={{ fontSize: '11px' }}>
                      Saves {opt.days_saved} Days
                    </span>
                  )}
                </div>

                <div style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
                  <div>• Available Safe Surplus: <strong>{opt.available_surplus} units</strong></div>
                  <div>• Transferable Quantity: <strong>{opt.transferable_quantity} units</strong></div>
                  <div>• Route Distance: <strong>{opt.distance_km} km</strong></div>
                  <div>• Transit Time: <strong>{opt.transit_days} day(s)</strong> (vs {opt.supplier_lead_time_days} days supplier)</div>
                  <div>• Transfer Cost: <strong>₹{opt.total_transfer_cost.toLocaleString()}</strong> (₹{opt.cost_per_unit}/unit)</div>
                </div>

                <div style={{ fontSize: '12px', color: '#38bdf8', background: 'rgba(56, 189, 248, 0.08)', padding: '8px 12px', borderRadius: '6px' }}>
                  {opt.recommendation}
                </div>

                <button
                  className="btn btn-primary"
                  style={{ width: '100%', marginTop: 'auto' }}
                  onClick={() => handleQueueTransfer(opt)}
                >
                  <ArrowLeftRight size={14} />
                  <span>Queue Transfer for Human Approval</span>
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
