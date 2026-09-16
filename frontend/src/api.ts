import {
  SKU,
  Warehouse,
  ReplenishmentAlert,
  ForecastResponse,
  TransferOption,
  WhatIfResult,
  ApprovalItem,
} from './types';

const BASE = '';

export async function fetchHealth(): Promise<{ status: string; version: string }> {
  const res = await fetch(`${BASE}/health`);
  return res.json();
}

export async function fetchSKUs(category?: string): Promise<SKU[]> {
  const url = category ? `${BASE}/api/skus?category=${encodeURIComponent(category)}` : `${BASE}/api/skus`;
  const res = await fetch(url);
  return res.json();
}

export async function fetchCategories(): Promise<string[]> {
  const res = await fetch(`${BASE}/api/categories`);
  return res.json();
}

export async function fetchWarehouses(): Promise<Warehouse[]> {
  const res = await fetch(`${BASE}/api/warehouses`);
  return res.json();
}

export async function fetchReplenishmentAlerts(limit = 50): Promise<ReplenishmentAlert[]> {
  const res = await fetch(`${BASE}/api/replenishment/alerts?limit=${limit}`);
  return res.json();
}

export async function fetchReplenishmentDetail(skuId: string, warehouseId: string): Promise<any> {
  const res = await fetch(`${BASE}/api/replenishment/${skuId}/${warehouseId}`);
  return res.json();
}

export async function fetchForecast(
  skuId: string,
  warehouseId: string,
  horizonDays = 30,
  model = 'prophet'
): Promise<ForecastResponse> {
  const res = await fetch(`${BASE}/api/forecast`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      sku_id: skuId,
      warehouse_id: warehouseId,
      horizon_days: horizonDays,
      model: model,
    }),
  });
  return res.json();
}

export async function fetchTransferOptions(
  skuId: string,
  warehouseId: string,
  quantity = 50
): Promise<TransferOption[]> {
  const res = await fetch(`${BASE}/api/transfers/${skuId}/${warehouseId}?quantity=${quantity}`);
  return res.json();
}

export async function runWhatIfSimulation(params: {
  sku_id: string;
  warehouse_id: string;
  demand_shock_pct: number;
  lead_time_delay_days: number;
  promo_lift_pct: number;
  horizon_days?: number;
}): Promise<WhatIfResult> {
  const res = await fetch(`${BASE}/api/whatif`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  });
  return res.json();
}

export async function fetchApprovals(status?: string): Promise<ApprovalItem[]> {
  const url = status ? `${BASE}/api/approvals?status=${status}` : `${BASE}/api/approvals`;
  const res = await fetch(url);
  return res.json();
}

export async function createApprovalRequest(data: {
  recommendation_type: string;
  sku_id: string;
  warehouse_id: string;
  action: string;
  quantity: number;
  ai_reasoning: string;
  ai_confidence?: number;
}): Promise<ApprovalItem> {
  const res = await fetch(`${BASE}/api/approvals`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    throw new Error(`Failed to queue approval: ${res.statusText}`);
  }
  return res.json();
}

export async function reviewApproval(
  approvalId: number,
  action: 'approved' | 'rejected',
  reviewedBy = 'manager',
  editedQuantity?: number,
  notes?: string
): Promise<any> {
  const res = await fetch(`${BASE}/api/approvals/${approvalId}/review`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      action,
      reviewed_by: reviewedBy,
      edited_quantity: editedQuantity,
      review_notes: notes,
    }),
  });
  return res.json();
}

export async function sendChatMessage(message: string, conversationId?: string): Promise<{
  reply: string;
  conversation_id: string;
  model_used: string;
  tool_calls: Array<{ name: string; args: any; output?: any }>;
}> {
  const res = await fetch(`${BASE}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message,
      conversation_id: conversationId,
    }),
  });
  return res.json();
}
