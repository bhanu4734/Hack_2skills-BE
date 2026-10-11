"""
FastAPI Server for BrewBatch - Batch-Aware Order Grouping
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import copy
import uuid

from optimizer import (
    DrinkItem,
    BatchGroup,
    OptimizationResult,
    run_batch_optimization,
    calculate_solo_prep_time
)
from sample_data import PEAK_RUSH_ORDERS, PRESET_SCENARIOS

app = FastAPI(
    title="BrewBatch API",
    description="Intelligent Batch-Aware Order Grouping for Cafes",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory application state
state = {
    "fairness_threshold_sec": 120,
    "current_scenario": "morning_peak",
    "active_orders": copy.deepcopy(PEAK_RUSH_ORDERS),
    "completed_items": [],
    "in_progress_batch_id": None,
    "completed_batches": [],
    "active_batch_start_timestamp": None,
}


def get_current_optimized_batches() -> OptimizationResult:
    # Filter out completed items
    queued_orders = [o for o in state["active_orders"] if o.id not in [c["id"] for c in state["completed_items"]]]
    result = run_batch_optimization(
        queued_orders,
        fairness_threshold_sec=state["fairness_threshold_sec"]
    )
    # Update status of in_progress batch if any
    for b in result.batches:
        if b.batch_id == state["in_progress_batch_id"]:
            b.status = "in_progress"
    return result


@app.get("/api/health")
def health_check():
    return {"status": "healthy", "service": "BrewBatch Engine"}


@app.get("/api/state")
def get_state():
    opt_result = get_current_optimized_batches()
    
    # Calculate customer ETAs
    now_offset = 0
    cum_prep = 0
    customer_etas = []
    
    for b in opt_result.batches:
        batch_eta_sec = cum_prep + b.batch_prep_time_sec
        cum_prep += b.batch_prep_time_sec
        for item in b.items:
            customer_etas.append({
                "item_id": item.id,
                "order_id": item.order_id,
                "customer_name": item.customer_name,
                "drink_name": item.drink_name,
                "milk_type": item.milk_type,
                "size": item.size,
                "syrup": item.syrup,
                "batch_id": b.batch_id,
                "status": "making_in_batch" if b.batch_id == state["in_progress_batch_id"] else "queued_in_batch",
                "estimated_wait_sec": max(30, batch_eta_sec),
                "is_batched": len(b.items) > 1,
                "batch_size": len(b.items),
                "batch_title": b.display_title
            })

    # Add already completed
    for item_data in state["completed_items"]:
        customer_etas.append({
            "item_id": item_data["id"],
            "order_id": item_data["order_id"],
            "customer_name": item_data["customer_name"],
            "drink_name": item_data["drink_name"],
            "milk_type": item_data["milk_type"],
            "size": item_data["size"],
            "syrup": item_data.get("syrup"),
            "batch_id": item_data.get("batch_id", "DONE"),
            "status": "ready_for_pickup",
            "estimated_wait_sec": 0,
            "is_batched": True,
            "batch_size": 1,
            "batch_title": "Ready"
        })

    return {
        "fairness_threshold_sec": state["fairness_threshold_sec"],
        "current_scenario": state["current_scenario"],
        "in_progress_batch_id": state["in_progress_batch_id"],
        "optimization": opt_result.model_dump(),
        "total_active_drinks": len(state["active_orders"]) - len(state["completed_items"]),
        "total_completed_drinks": len(state["completed_items"]),
        "customer_etas": customer_etas,
        "scenarios": [
            {"id": k, "title": v["title"], "description": v["description"], "count": len(v["items"])}
            for k, v in PRESET_SCENARIOS.items()
        ]
    }


class FairnessUpdate(BaseModel):
    fairness_threshold_sec: int


@app.post("/api/settings/fairness")
def update_fairness(payload: FairnessUpdate):
    state["fairness_threshold_sec"] = max(30, min(360, payload.fairness_threshold_sec))
    return {"status": "ok", "fairness_threshold_sec": state["fairness_threshold_sec"]}


@app.post("/api/scenario/{scenario_id}")
def load_scenario(scenario_id: str):
    if scenario_id not in PRESET_SCENARIOS:
        raise HTTPException(status_code=404, detail="Scenario not found")
    state["current_scenario"] = scenario_id
    state["active_orders"] = copy.deepcopy(PRESET_SCENARIOS[scenario_id]["items"])
    state["completed_items"] = []
    state["in_progress_batch_id"] = None
    state["completed_batches"] = []
    return {"status": "ok", "scenario": scenario_id}


class NewOrderPayload(BaseModel):
    customer_name: str
    drink_name: str
    category: str
    milk_type: str
    size: str
    temperature: str
    shots: int = 2
    syrup: Optional[str] = None
    notes: Optional[str] = None


@app.post("/api/orders/add")
def add_order(payload: NewOrderPayload):
    new_id = f"item-{len(state['active_orders']) + 101}"
    ord_id = f"ORD-{len(state['active_orders']) + 101}"
    # Offset based on latest order arrival + 20 seconds
    max_offset = max([o.arrival_time_offset_sec for o in state["active_orders"]], default=0)
    new_offset = max_offset + 25

    item = DrinkItem(
        id=new_id,
        order_id=ord_id,
        customer_name=payload.customer_name,
        drink_name=payload.drink_name,
        category=payload.category,
        milk_type=payload.milk_type,
        size=payload.size,
        temperature=payload.temperature,
        shots=payload.shots,
        syrup=payload.syrup,
        notes=payload.notes,
        arrival_time_offset_sec=new_offset,
        solo_prep_time_sec=95
    )
    item.solo_prep_time_sec = calculate_solo_prep_time(item)
    state["active_orders"].append(item)
    return {"status": "added", "item": item.model_dump()}


@app.post("/api/batches/{batch_id}/start")
def start_batch(batch_id: str):
    opt_result = get_current_optimized_batches()
    target_batch = next((b for b in opt_result.batches if b.batch_id == batch_id), None)
    if not target_batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    state["in_progress_batch_id"] = batch_id
    return {"status": "started", "batch_id": batch_id}


@app.post("/api/batches/{batch_id}/complete")
def complete_batch(batch_id: str):
    opt_result = get_current_optimized_batches()
    target_batch = next((b for b in opt_result.batches if b.batch_id == batch_id), None)
    if not target_batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    for item in target_batch.items:
        state["completed_items"].append({
            "id": item.id,
            "order_id": item.order_id,
            "customer_name": item.customer_name,
            "drink_name": item.drink_name,
            "milk_type": item.milk_type,
            "size": item.size,
            "syrup": item.syrup,
            "batch_id": batch_id
        })

    state["completed_batches"].append(target_batch.model_dump())
    if state["in_progress_batch_id"] == batch_id:
        state["in_progress_batch_id"] = None

    return {"status": "completed", "batch_id": batch_id, "items_completed": len(target_batch.items)}


@app.post("/api/reset")
def reset_state():
    state["fairness_threshold_sec"] = 120
    state["current_scenario"] = "morning_peak"
    state["active_orders"] = copy.deepcopy(PEAK_RUSH_ORDERS)
    state["completed_items"] = []
    state["in_progress_batch_id"] = None
    state["completed_batches"] = []
    return {"status": "reset"}


# ============================================================================
# GEMINI AI AGENT ENDPOINTS (Free Tier & Built-in Agents)
# ============================================================================
from gemini_agents import (
    run_barista_advisor,
    run_order_parser,
    run_customer_concierge,
    run_shift_audit,
    get_api_key,
    set_api_key,
    gemini_config
)


class GeminiConfigPayload(BaseModel):
    api_key: str


@app.get("/api/gemini/status")
def get_gemini_status():
    api_key = get_api_key()
    return {
        "has_api_key": bool(api_key and len(api_key) > 5),
        "model": gemini_config["model"],
        "free_tier_supported": True,
        "agents": [
            {"id": "barista_copilot", "name": "Barista Shift Copilot", "description": "Tactical queue advisory & wand purge recommendations"},
            {"id": "order_parser", "name": "Smart Order NLP Transcriber", "description": "Converts natural speech/text into structured batch tickets"},
            {"id": "customer_concierge", "name": "Guest ETA Concierge", "description": "Hospitality assistant explaining batching and pickup times"},
            {"id": "shift_auditor", "name": "Rush Hour Efficiency Auditor", "description": "Post-rush performance analytics and labor savings"}
        ]
    }


@app.post("/api/gemini/config")
def update_gemini_config(payload: GeminiConfigPayload):
    set_api_key(payload.api_key)
    return {
        "status": "ok",
        "has_api_key": bool(payload.api_key.strip()),
        "model": gemini_config["model"]
    }


class BaristaAdvisorPayload(BaseModel):
    query: Optional[str] = None


@app.post("/api/gemini/barista-advisor")
async def barista_advisor_endpoint(payload: BaristaAdvisorPayload):
    current_state = get_state()
    res = await run_barista_advisor(current_state, user_question=payload.query)
    return res


class ParseOrderPayload(BaseModel):
    text: str


@app.post("/api/gemini/parse-order")
async def parse_order_endpoint(payload: ParseOrderPayload):
    parsed_items = await run_order_parser(payload.text)
    return {"status": "ok", "orders": parsed_items}


class ConciergePayload(BaseModel):
    customer_name: str
    inquiry: str


@app.post("/api/gemini/customer-concierge")
async def customer_concierge_endpoint(payload: ConciergePayload):
    current_state = get_state()
    res = await run_customer_concierge(
        payload.customer_name,
        payload.inquiry,
        customer_etas=current_state.get("customer_etas", [])
    )
    return res


@app.post("/api/gemini/shift-audit")
async def shift_audit_endpoint():
    current_state = get_state()
    res = await run_shift_audit(current_state)
    return res

