"""
GenAI Reasoning Agent using OpenRouter (with free model fallback chain) and tool calling.
Includes smart mock mode if OPENROUTER_API_KEY is unset or placeholder.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

import httpx
from openai import OpenAI

from src.config import get_settings
from src.tools.inventory_tools import TOOL_DEFINITIONS, execute_tool
from src.rag.retriever import retrieve_context, format_context_for_prompt

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are the GenAI Inventory & Demand-Forecasting Assistant, an enterprise AI decision-support system for supply chain and inventory management.
Your role is to explain demand trends, evaluate stockout risks, recommend optimal replenishment actions (purchase order vs. inter-warehouse transfer), and formulate proposals for human-in-the-loop approval.

Operational & Presentation Guidelines:
1. Maintain a professional, clean executive presentation at all times.
2. DO NOT use emojis (no robot, chart, light, check, alert, or status icon emojis).
3. DO NOT use square bracket label tags like [PROMOTION], [FESTIVAL], or [DISRUPTION]. Use clean bold titles or bullet points instead (e.g. "**Promotion Event** — North Region").
4. Always provide specific metrics: SKU ID, Warehouse ID, units to transfer/order, lead times, and estimated costs.
5. Format inventory & demand diagnostics in a clear Markdown table with columns: Metric, Current Value, Planning Threshold, Status / Diagnostic.
6. When comparing replenishment options, use a clear comparison table (Transfer vs Supplier Purchase Order) highlighting transit days saved and total cost impact.
7. End recommendations with a clear, concise Executive Action Summary.
"""


class InventoryAgent:
    """Multi-model reasoning agent powered by OpenRouter."""

    def __init__(self):
        self.settings = get_settings()
        self.api_key = self.settings.openrouter_api_key.strip()
        self.models = self.settings.all_models
        self.client = None

        if self.api_key and "your-openrouter-api-key" not in self.api_key:
            self.client = OpenAI(
                base_url=self.settings.openrouter_base_url,
                api_key=self.api_key,
                default_headers={
                    "HTTP-Referer": "https://github.com/inventory-assistant",
                    "X-Title": "GenAI Inventory Assistant",
                },
            )
            logger.info(f"OpenRouter client initialized with primary model: {self.models[0]}")
        else:
            logger.info("No active OpenRouter key provided. Running in smart heuristic simulation mode.")

    def run_conversation(
        self,
        messages: List[Dict[str, Any]],
        context_query: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute conversation turn with tool calling and model fallback.
        """
        # If no key or placeholder, run heuristic demo mode
        if not self.client:
            return self._run_mock_turn(messages)

        # Inject RAG context if query provided
        augmented_messages = list(messages)
        if context_query:
            rag_docs = retrieve_context(query=context_query, n_results=3)
            context_block = format_context_for_prompt(rag_docs)
            augmented_messages.insert(
                0,
                {"role": "system", "content": f"{SYSTEM_PROMPT}\n\n{context_block}"},
            )
        else:
            augmented_messages.insert(0, {"role": "system", "content": SYSTEM_PROMPT})

        # Try models in fallback sequence
        last_error = None
        for model in self.models:
            try:
                logger.info(f"Invoking model: {model}")
                return self._call_model_loop(model, augmented_messages)
            except Exception as e:
                logger.warning(f"Model {model} failed: {e}. Trying fallback...")
                last_error = e

        # Fallback to smart heuristic if all OpenRouter calls fail
        logger.warning(f"All LLM models failed ({last_error}). Falling back to internal engine.")
        return self._run_mock_turn(messages)

    def _call_model_loop(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        max_tool_iterations: int = 5,
    ) -> Dict[str, Any]:
        """Tool-calling iteration loop."""
        current_messages = list(messages)
        tool_call_history: List[Dict[str, Any]] = []

        for _ in range(max_tool_iterations):
            if self.client is None:
                return self._run_mock_turn(messages)
            response = self.client.chat.completions.create(  # type: ignore[arg-type]
                model=model,
                messages=current_messages,
                tools=TOOL_DEFINITIONS,
                tool_choice="auto",
            )
            message = response.choices[0].message

            if not message.tool_calls:
                return {
                    "role": "assistant",
                    "content": message.content or "",
                    "model_used": model,
                    "tool_calls": tool_call_history,
                }

            # Process tool calls
            current_messages.append(message)
            for tool_call in message.tool_calls:
                fn_name = tool_call.function.name
                fn_args = json.loads(tool_call.function.arguments or "{}")

                logger.info(f"Agent called tool '{fn_name}' with args {fn_args}")
                tool_output = execute_tool(fn_name, fn_args)
                tool_call_history.append({"name": fn_name, "args": fn_args, "output": tool_output})

                current_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(tool_output),
                })

        return {
            "role": "assistant",
            "content": "Completed multi-step analysis and tool executions.",
            "model_used": model,
            "tool_calls": tool_call_history,
        }

    def _run_mock_turn(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Smart heuristic simulation when API key is not yet set.
        Inspects user prompt for SKU, Warehouse, or scenario keywords and executes actual tools.
        """
        user_msg = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                user_msg = str(m.get("content", ""))
                break

        # Check for SKU pattern (e.g. SKU_001, SKU_1, sku 5)
        import re
        sku_match = re.search(r"sku[_ ]?(\d+)", user_msg, re.IGNORECASE)
        sku_id = f"SKU_{int(sku_match.group(1)):03d}" if sku_match else "SKU_001"

        # Check for Warehouse pattern (e.g. WH_01, WH_1, delhi, mumbai)
        wh_match = re.search(r"wh[_ ]?0?(\d+)", user_msg, re.IGNORECASE)
        wh_id = f"WH_{int(wh_match.group(1)):02d}" if wh_match else "WH_01"
        if "mumbai" in user_msg.lower():
            wh_id = "WH_02"
        elif "chennai" in user_msg.lower():
            wh_id = "WH_03"
        elif "kolkata" in user_msg.lower():
            wh_id = "WH_04"
        elif "pune" in user_msg.lower():
            wh_id = "WH_05"

        # Execute domain tools
        replenish_status = execute_tool("get_replenishment_recommendation", {"sku_id": sku_id, "warehouse_id": wh_id})
        forecast_res = execute_tool("get_forecast", {"sku_id": sku_id, "warehouse_id": wh_id, "horizon_days": 30})
        transfers = execute_tool("check_transfer_options", {
            "sku_id": sku_id,
            "deficit_warehouse_id": wh_id,
            "needed_quantity": replenish_status.get("recommended_order_quantity", 50),
        })
        rag_info = execute_tool("search_rag_context", {"query": f"festival demand for {sku_id} {wh_id}"})

        # Generate comprehensive markdown analysis
        current_stock = replenish_status.get("current_stock", 0)
        rop = replenish_status.get("reorder_point", 0)
        safety_stock = replenish_status.get("safety_stock", 0)
        eoq = replenish_status.get("eoq", 0)
        rec_qty = replenish_status.get("recommended_order_quantity", 0)
        status_label = replenish_status.get("status", "HEALTHY")
        days_inv = replenishment_status_days(replenish_status)

        if status_label == "CRITICAL":
            status_badge = "Critical Deficit"
        elif status_label == "REORDER_NEEDED":
            status_badge = "Reorder Triggered"
        else:
            status_badge = "Healthy"

        rop_flag = "Action Required (Sub-ROP)" if current_stock < rop else "Buffer Protected"
        
        try:
            doi_num = float(days_inv if days_inv != '90+' else 99)
        except (ValueError, TypeError):
            doi_num = 30.0

        if doi_num < 10:
            doi_flag = "High Runout Risk"
        elif doi_num < 15:
            doi_flag = "Moderate Runway"
        else:
            doi_flag = "Adequate Runway (15-30 Days)"

        projected_30d = forecast_res.get('total_projected_demand', 'N/A')
        daily_avg = forecast_res.get('avg_daily_demand', 'N/A')

        transfer_options = transfers.get("transfer_options", [])
        best_transfer = transfer_options[0] if transfer_options else None

        content = f"""### Inventory & Demand Diagnostics: **{sku_id}** at **{wh_id}**

| Core Metric | Current Value | Planning Threshold | Health Diagnostic |
| :--- | :--- | :--- | :--- |
| **Current Stock** | {current_stock:,} units | Safety Stock: {safety_stock:,} units | {status_badge} |
| **Reorder Point (ROP)** | {rop:,} units | Lead-Time Buffer | {rop_flag} |
| **Days of Inventory (DOI)** | {days_inv} days | Target: 15-30 days | {doi_flag} |
| **30-Day Demand Forecast** | {projected_30d} units | Daily Run-Rate: ~{daily_avg}/day | Active Model Projection |

---

### Key Context & Demand Drivers
{rag_info.get('context_summary', '*No regional festival disruptions or active promotional campaigns registered for this SKU window.*')}

---

### Recommended Replenishment Strategy
"""
        if best_transfer and best_transfer.get("is_faster_than_supplier") and rec_qty > 0:
            content += f"""| Decision Dimension | Proposed Inter-Warehouse Transfer | External Supplier Purchase Order |
| :--- | :--- | :--- |
| **Fulfillment Route** | **{best_transfer['source_city']} ({best_transfer['source_warehouse_id']}) to {wh_id}** | External Supplier ({replenish_status.get('supplier_name', 'Primary Supplier')}) |
| **Transferable Quantity** | **{best_transfer['transferable_quantity']:,} units** | {rec_qty:,} units (EOQ: {eoq}) |
| **Lead / Transit Time** | **{best_transfer['transit_days']} days** (saves {best_transfer['days_saved']} days vs supplier) | {replenish_status.get('lead_time_days', 7)} days |
| **Estimated Outlay** | **₹{best_transfer['total_transfer_cost']:,.2f}** (₹{best_transfer['cost_per_unit']}/unit) | ₹{rec_qty * replenish_status.get('unit_cost', 100):,.2f} |
| **Operational Impact** | Surplus at {best_transfer['source_city']}: {best_transfer['available_surplus']} units. Fast-track rebalancing eliminates stockout risk. | Standard external replenishment cycle. |

**Executive Recommendation:** Inter-warehouse transfer from **{best_transfer['source_city']}** delivers **{best_transfer['days_saved']} days faster** and utilizes existing network surplus without incremental procurement lead time.
"""
        elif rec_qty > 0:
            content += f"""| Decision Dimension | Recommended Supplier Purchase Order |
| :--- | :--- |
| **Target Supplier** | **{replenish_status.get('supplier_name', 'Primary Supplier')}** |
| **Recommended Order Quantity** | **{rec_qty:,} units** (Calculated EOQ: {eoq}) |
| **Supplier Lead Time** | **{replenish_status.get('lead_time_days', 7)} business days** |
| **Estimated PO Cost** | **₹{rec_qty * replenish_status.get('unit_cost', 100):,.2f}** (₹{replenish_status.get('unit_cost', 100)}/unit) |
| **Network Transfer Check** | Evaluated network warehouses; no facility currently has surplus above safety buffer. |

**Executive Recommendation:** Place purchase order with **{replenish_status.get('supplier_name', 'Primary Supplier')}** for {rec_qty:,} units to restore stock above target reorder point.
"""
        else:
            content += f"""**Executive Summary:** Stock is currently optimal ({current_stock:,} units on hand vs. ROP buffer of {rop:,} units). No immediate replenishment is required. Next reorder review will trigger if inventory approaches the reorder threshold buffer."""

        return {
            "role": "assistant",
            "content": content,
            "model_used": "simulated-agent (OpenRouter key not configured)",
            "tool_calls": [
                {"name": "get_replenishment_recommendation", "args": {"sku_id": sku_id, "warehouse_id": wh_id}},
                {"name": "get_forecast", "args": {"sku_id": sku_id, "warehouse_id": wh_id, "horizon_days": 30}},
                {"name": "check_transfer_options", "args": {"sku_id": sku_id, "deficit_warehouse_id": wh_id}},
                {"name": "search_rag_context", "args": {"query": f"festival demand for {sku_id} {wh_id}"}},
            ],
        }


def replenishment_status_days(status: Dict[str, Any]) -> str:
    doi = status.get("days_of_inventory", 0)
    return f"{doi:.1f}" if doi < 999 else "90+"


_agent_instance: Optional[InventoryAgent] = None


def get_agent() -> InventoryAgent:
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = InventoryAgent()
    return _agent_instance
