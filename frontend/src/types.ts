export interface SKU {
  sku_id: string;
  description?: string;
  category: string;
  unit_cost: number;
  unit_price: number;
  margin_pct?: number;
}

export interface Warehouse {
  warehouse_id: string;
  primary_region: string;
  city: string;
  capacity_units: number;
  fixed_cost_per_day_inr: number;
}

export interface ReplenishmentAlert {
  sku_id: string;
  warehouse_id: string;
  current_stock: number;
  reorder_point: number;
  safety_stock: number;
  deficit: number;
  status: 'CRITICAL' | 'WARNING' | 'HEALTHY';
}

export interface ForecastPoint {
  date: string;
  point_forecast: number;
  lower_bound?: number;
  upper_bound?: number;
}

export interface ForecastResponse {
  sku_id: string;
  warehouse_id: string;
  model_used: string;
  horizon_days: number;
  mape?: number;
  rmse?: number;
  forecasts: ForecastPoint[];
  historical_points?: Array<{ date: string; quantity: number }>;
}

export interface TransferOption {
  source_warehouse_id: string;
  source_city: string;
  available_surplus: number;
  transferable_quantity: number;
  distance_km: number;
  transit_days: number;
  cost_per_unit: number;
  total_transfer_cost: number;
  supplier_lead_time_days: number;
  days_saved: number;
  is_faster_than_supplier: boolean;
  recommendation: string;
}

export interface WhatIfResult {
  sku_id: string;
  warehouse_id: string;
  stockout_occurred: boolean;
  stockout_day?: number;
  stockout_date?: string;
  total_unmet_demand: number;
  revenue_at_risk: number;
  margin_at_risk: number;
  recommended_safety_stock_adjustment: number;
  trajectory: Array<{
    day: number;
    date: string;
    stock_level: number;
    projected_demand: number;
    unmet_demand: number;
    is_stockout: boolean;
  }>;
}

export interface ApprovalItem {
  id: number;
  recommendation_type: string;
  sku_id: string;
  warehouse_id: string;
  action: string;
  quantity: number;
  ai_reasoning: string;
  ai_confidence?: number;
  status: 'pending' | 'approved' | 'rejected';
  created_at: string;
  reviewed_by?: string;
  reviewed_at?: string;
  edited_quantity?: number;
}

export interface ChatMessage {
  id: string;
  sender: 'user' | 'assistant';
  content: string;
  model_used?: string;
  tool_calls?: Array<{ name: string; args: any; output?: any }>;
  timestamp: string;
}
