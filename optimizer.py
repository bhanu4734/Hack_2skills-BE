"""
BrewBatch Engine - Batch-Aware Order Grouping Optimizer
Balances throughput optimization with customer fairness constraints.
"""

from typing import List, Dict, Any, Optional, Tuple
from pydantic import BaseModel, Field
import time
from datetime import datetime, timedelta

class DrinkItem(BaseModel):
    id: str
    order_id: str
    customer_name: str
    drink_name: str
    category: str  # "hot_espresso_milk", "iced_espresso_milk", "cold_brew", "hot_black", "tea_matcha"
    milk_type: str  # "oat", "whole", "almond", "skim", "soy", "none"
    size: str  # "small", "medium", "large"
    temperature: str  # "hot", "iced", "extra_hot"
    shots: int = 2
    syrup: Optional[str] = None
    notes: Optional[str] = None
    arrival_time_offset_sec: int  # seconds relative to rush start (e.g. 0 to 600)
    solo_prep_time_sec: int = 90  # Default solo prep time in seconds

class BatchGroup(BaseModel):
    batch_id: str
    recipe_signature: str
    display_title: str
    category: str
    milk_type: str
    temperature: str
    item_ids: List[str]
    items: List[DrinkItem]
    solo_total_time_sec: int
    batch_prep_time_sec: int
    time_saved_sec: int
    savings_percent: float
    oldest_item_arrival_offset: int
    fairness_delay_sec: int  # how much the oldest order is delayed vs immediate solo start
    status: str = "queued"  # "queued", "in_progress", "completed"
    efficiency_score: float = 0.0
    prep_instructions: List[str] = []

class OptimizationResult(BaseModel):
    batches: List[BatchGroup]
    fifo_total_prep_sec: int
    batched_total_prep_sec: int
    total_time_saved_sec: int
    prep_time_reduction_percent: float
    avg_customer_wait_fifo_sec: float
    avg_customer_wait_batched_sec: float
    wait_time_reduction_percent: float
    throughput_drinks_per_hour_fifo: float
    throughput_drinks_per_hour_batched: float
    wand_purges_saved: int
    fairness_threshold_sec: int


def calculate_solo_prep_time(item: DrinkItem) -> int:
    """Calculates realistic solo prep time for an isolated drink."""
    if item.category == "cold_brew":
        return 35  # Pour over ice, tap pull, lid
    elif item.category == "hot_black":
        return 50  # Americano/Drip: hot water + pull 2 shots / pour
    elif item.category in ["hot_espresso_milk", "iced_espresso_milk"]:
        # Grind & dose (15s) + Tamp/Pull shot (28s) + Steam milk / Pour milk (35s) + Pour/lid/wipe wand (17s)
        base = 95
        if item.milk_type != "none":
            base += 5
        if item.shots > 2:
            base += 15
        return base
    elif item.category == "tea_matcha":
        return 105  # Whisk matcha powder (35s) + steam milk (35s) + combine & lid (35s)
    return 90


def get_recipe_signature(item: DrinkItem) -> str:
    """
    Returns compatibility key.
    Drinks can be batched together if:
    1. Same category
    2. Same milk type (CRITICAL: cannot steam oat milk and dairy together!)
    3. Same temperature (cannot steam cold milk with hot milk)
    Syrups and cup sizes can vary within the batch as long as milk & espresso match.
    """
    return f"{item.category}|{item.temperature}|{item.milk_type}"


def get_max_batch_capacity(category: str, milk_type: str) -> int:
    """
    Physical equipment constraints:
    - Steaming pitcher: standard commercial large pitcher holds up to 650-700ml (3 drinks max).
    - Cold brew tap: up to 4 drinks in rapid succession.
    - Espresso group heads: 2 group heads = max 4 shots parallel = 2-3 drinks.
    """
    if category == "cold_brew":
        return 4
    if category in ["hot_espresso_milk", "iced_espresso_milk"]:
        return 3  # Pitcher & dual portafilter limits
    if category == "tea_matcha":
        return 2  # Whisking bowl limit
    return 3


def calculate_batched_prep_time(items: List[DrinkItem], category: str) -> Tuple[int, List[str]]:
    """
    Calculates parallel/batched prep time and step-by-step instructions.
    """
    n = len(items)
    if n <= 1:
        solo = calculate_solo_prep_time(items[0])
        return solo, [
            f"Pull {items[0].shots} shots of espresso",
            f"Steam {items[0].milk_type.title()} milk",
            f"Assemble for {items[0].customer_name}"
        ]

    milk_type = items[0].milk_type.title()
    temp = items[0].temperature

    if category == "cold_brew":
        # Fill N cups with ice (15s) + Pour from nitro/cold brew tap (10s * N) + Lid (10s)
        batch_time = 15 + (12 * n) + 10
        instructions = [
            f"Prep {n} cups with ice ({', '.join(i.size for i in items)})",
            f"Pour {n}x Cold Brew directly from tap ({batch_time - 25}s)",
            f"Lid and label for: {', '.join(i.customer_name for i in items)}"
        ]
        return batch_time, instructions

    if category in ["hot_espresso_milk", "iced_espresso_milk"]:
        # Parallel espresso pulling:
        # 1 dual portafilter = 2 shots (can make 1-2 drinks)
        # 2 dual portafilters = 4 shots (can make 2-3 drinks)
        # Large pitcher steaming: 1 large steam cycle (50s) instead of N x 38s
        # Pours: 1 continuous pour across cups (25s)
        shots_needed = sum(i.shots for i in items)
        grind_pull_time = 35 if shots_needed <= 2 else 45
        steam_time = 42 + (n - 1) * 12  # Steam 1 large 650ml pitcher instead of separate pitchers
        finish_time = 15 + (n * 10)
        batch_time = grind_pull_time + steam_time + finish_time

        instructions = [
            f"🥛 Steaming: 1x Large Pitcher of {milk_type} Milk (~{250 * n}ml)",
            f"☕ Shots: Pull {shots_needed} shots across {'1 portafilter' if shots_needed <= 2 else '2 portafilters'}",
            f"⚡ Pour & Finish: Split into {n} cups ({', '.join(f'{i.customer_name}: {i.size} {i.syrup or 'plain'}' for i in items)})",
            "✨ 1 wand purge & wipe instead of " + str(n) + " purges"
        ]
        return batch_time, instructions

    if category == "tea_matcha":
        batch_time = 45 + (n * 20) + 35
        instructions = [
            f"Whisk {n}x matcha bowls simultaneously",
            f"Steam shared pitcher of {milk_type} milk",
            f"Combine and serve for: {', '.join(i.customer_name for i in items)}"
        ]
        return batch_time, instructions

    # Fallback
    batch_time = int(sum(calculate_solo_prep_time(i) for i in items) * 0.65)
    return batch_time, [f"Prep {n} drinks together"]


def run_batch_optimization(
    items: List[DrinkItem],
    fairness_threshold_sec: int = 120
) -> OptimizationResult:
    """
    Batching algorithm with fairness guardrails:
    1. Sort incoming queue by arrival time (FCFS base).
    2. Scan ahead in a dynamic window to find compatible drinks.
    3. Evaluate if grouping order j with earlier order i violates the fairness threshold:
       Delay(i) = WaitTime_with_batch(i) - WaitTime_fifo(i).
       If Delay(i) > fairness_threshold_sec, do NOT wait to include more items; finalize batch now.
    4. Calculate FIFO vs Batched metrics.
    """
    if not items:
        return OptimizationResult(
            batches=[],
            fifo_total_prep_sec=0,
            batched_total_prep_sec=0,
            total_time_saved_sec=0,
            prep_time_reduction_percent=0.0,
            avg_customer_wait_fifo_sec=0.0,
            avg_customer_wait_batched_sec=0.0,
            wait_time_reduction_percent=0.0,
            throughput_drinks_per_hour_fifo=0.0,
            throughput_drinks_per_hour_batched=0.0,
            wand_purges_saved=0,
            fairness_threshold_sec=fairness_threshold_sec
        )

    # Sort strictly by arrival time
    sorted_items = sorted(items, key=lambda x: x.arrival_time_offset_sec)

    unassigned = list(sorted_items)
    batches: List[BatchGroup] = []
    batch_counter = 1

    current_sim_time = 0

    while unassigned:
        lead_item = unassigned.pop(0)
        lead_sig = get_recipe_signature(lead_item)
        max_cap = get_max_batch_capacity(lead_item.category, lead_item.milk_type)

        batch_members = [lead_item]
        remaining_unassigned = []

        for candidate in unassigned:
            cand_sig = get_recipe_signature(candidate)
            # Check compatibility
            is_compatible = (cand_sig == lead_sig)
            
            # Check capacity
            has_capacity = (len(batch_members) < max_cap)
            
            # Check arrival proximity and fairness constraint:
            # Candidate arrived after lead_item.
            # If candidate arrived too far in the future compared to when lead_item could finish,
            # or if waiting for candidate delays lead_item beyond fairness_threshold_sec:
            arrival_gap = candidate.arrival_time_offset_sec - lead_item.arrival_time_offset_sec
            fairness_respected = (arrival_gap <= fairness_threshold_sec)

            if is_compatible and has_capacity and fairness_respected:
                batch_members.append(candidate)
            else:
                remaining_unassigned.append(candidate)

        unassigned = remaining_unassigned

        # Calculate times for this batch
        solo_total = sum(calculate_solo_prep_time(it) for it in batch_members)
        batched_time, instructions = calculate_batched_prep_time(batch_members, lead_item.category)
        time_saved = max(0, solo_total - batched_time)
        savings_pct = (time_saved / solo_total * 100.0) if solo_total > 0 else 0.0

        # Title formatting
        milk_label = f"{lead_item.milk_type.title()} " if lead_item.milk_type != "none" else ""
        if len(batch_members) > 1:
            title = f"{len(batch_members)}x {milk_label}{lead_item.drink_name}"
        else:
            title = f"1x {milk_label}{lead_item.drink_name} ({batch_members[0].customer_name})"

        batches.append(BatchGroup(
            batch_id=f"B-{batch_counter:02d}",
            recipe_signature=lead_sig,
            display_title=title,
            category=lead_item.category,
            milk_type=lead_item.milk_type,
            temperature=lead_item.temperature,
            item_ids=[it.id for it in batch_members],
            items=batch_members,
            solo_total_time_sec=solo_total,
            batch_prep_time_sec=batched_time,
            time_saved_sec=time_saved,
            savings_percent=round(savings_pct, 1),
            oldest_item_arrival_offset=lead_item.arrival_time_offset_sec,
            fairness_delay_sec=min(fairness_threshold_sec, max(0, batch_members[-1].arrival_time_offset_sec - lead_item.arrival_time_offset_sec)),
            prep_instructions=instructions,
            efficiency_score=round(solo_total / batched_time, 2) if batched_time > 0 else 1.0
        ))
        batch_counter += 1

    # SIMULATE FIFO PERFORMANCE
    # In FIFO, barista makes each drink 1 by 1 in arrival order
    fifo_clock = 0
    fifo_wait_times = []
    total_solo_prep = 0
    for it in sorted_items:
        prep = calculate_solo_prep_time(it)
        start_time = max(fifo_clock, it.arrival_time_offset_sec)
        finish_time = start_time + prep
        fifo_wait_times.append(finish_time - it.arrival_time_offset_sec)
        fifo_clock = finish_time
        total_solo_prep += prep

    avg_fifo_wait = sum(fifo_wait_times) / len(fifo_wait_times) if fifo_wait_times else 0

    # SIMULATE BATCHED PERFORMANCE
    # In Batched, barista processes batches sequentially
    batch_clock = 0
    batch_wait_times = []
    total_batched_prep = 0
    for b in batches:
        # Barista can start batch when oldest order has arrived, and previous batch finished
        start_time = max(batch_clock, b.oldest_item_arrival_offset)
        finish_time = start_time + b.batch_prep_time_sec
        # All items in this batch finish together at finish_time
        for it in b.items:
            batch_wait_times.append(finish_time - it.arrival_time_offset_sec)
        batch_clock = finish_time
        total_batched_prep += b.batch_prep_time_sec

    avg_batched_wait = sum(batch_wait_times) / len(batch_wait_times) if batch_wait_times else 0

    total_time_saved = max(0, total_solo_prep - total_batched_prep)
    prep_reduction_pct = (total_time_saved / total_solo_prep * 100.0) if total_solo_prep > 0 else 0.0
    wait_reduction_pct = ((avg_fifo_wait - avg_batched_wait) / avg_fifo_wait * 100.0) if avg_fifo_wait > 0 else 0.0

    # Throughput calculations (drinks per hour based on prep time)
    n_drinks = len(sorted_items)
    fifo_throughput = (n_drinks / (total_solo_prep / 3600.0)) if total_solo_prep > 0 else 0
    batched_throughput = (n_drinks / (total_batched_prep / 3600.0)) if total_batched_prep > 0 else 0

    # Wand purges saved: each batched milk drink saves (n-1) wand purge & wipe cycles
    wand_purges_saved = sum(len(b.items) - 1 for b in batches if b.milk_type != "none")

    return OptimizationResult(
        batches=batches,
        fifo_total_prep_sec=total_solo_prep,
        batched_total_prep_sec=total_batched_prep,
        total_time_saved_sec=total_time_saved,
        prep_time_reduction_percent=round(prep_reduction_pct, 1),
        avg_customer_wait_fifo_sec=round(avg_fifo_wait, 1),
        avg_customer_wait_batched_sec=round(avg_batched_wait, 1),
        wait_time_reduction_percent=round(wait_reduction_pct, 1),
        throughput_drinks_per_hour_fifo=round(fifo_throughput, 1),
        throughput_drinks_per_hour_batched=round(batched_throughput, 1),
        wand_purges_saved=wand_purges_saved,
        fairness_threshold_sec=fairness_threshold_sec
    )
