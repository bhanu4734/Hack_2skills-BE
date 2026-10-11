"""
Hardcoded realistic café order queues and preset scenarios for BrewBatch.
Represents peak morning rush at 8:15 AM - 8:30 AM.
"""

from typing import List
from optimizer import DrinkItem

PEAK_RUSH_ORDERS: List[DrinkItem] = [
    DrinkItem(
        id="item-101",
        order_id="ORD-101",
        customer_name="Alice M.",
        drink_name="Latte",
        category="hot_espresso_milk",
        milk_type="oat",
        size="12oz",
        temperature="hot",
        shots=2,
        syrup=None,
        notes="Extra creamy texture",
        arrival_time_offset_sec=10,
        solo_prep_time_sec=95
    ),
    DrinkItem(
        id="item-102",
        order_id="ORD-102",
        customer_name="Marcus T.",
        drink_name="Flat White",
        category="hot_espresso_milk",
        milk_type="whole",
        size="8oz",
        temperature="hot",
        shots=2,
        syrup=None,
        notes="Velveteen microfoam",
        arrival_time_offset_sec=45,
        solo_prep_time_sec=95
    ),
    DrinkItem(
        id="item-103",
        order_id="ORD-103",
        customer_name="Dave K.",
        drink_name="Latte",
        category="hot_espresso_milk",
        milk_type="oat",
        size="12oz",
        temperature="hot",
        shots=2,
        syrup="Vanilla (1 pump)",
        notes=None,
        arrival_time_offset_sec=90,
        solo_prep_time_sec=100
    ),
    DrinkItem(
        id="item-104",
        order_id="ORD-104",
        customer_name="Liam W.",
        drink_name="Cold Brew",
        category="cold_brew",
        milk_type="none",
        size="16oz",
        temperature="iced",
        shots=0,
        syrup=None,
        notes="Light ice",
        arrival_time_offset_sec=115,
        solo_prep_time_sec=35
    ),
    DrinkItem(
        id="item-105",
        order_id="ORD-105",
        customer_name="Chloe S.",
        drink_name="Latte",
        category="hot_espresso_milk",
        milk_type="oat",
        size="16oz",
        temperature="hot",
        shots=2,
        syrup=None,
        notes=None,
        arrival_time_offset_sec=140,
        solo_prep_time_sec=95
    ),
    DrinkItem(
        id="item-106",
        order_id="ORD-106",
        customer_name="Sarah B.",
        drink_name="Cappuccino",
        category="hot_espresso_milk",
        milk_type="whole",
        size="12oz",
        temperature="hot",
        shots=2,
        syrup="Dust of cinnamon",
        notes=None,
        arrival_time_offset_sec=165,
        solo_prep_time_sec=95
    ),
    DrinkItem(
        id="item-107",
        order_id="ORD-107",
        customer_name="Sophia R.",
        drink_name="Cold Brew",
        category="cold_brew",
        milk_type="none",
        size="12oz",
        temperature="iced",
        shots=0,
        syrup=None,
        notes=None,
        arrival_time_offset_sec=190,
        solo_prep_time_sec=35
    ),
    DrinkItem(
        id="item-108",
        order_id="ORD-108",
        customer_name="Jack D.",
        drink_name="Latte",
        category="hot_espresso_milk",
        milk_type="oat",
        size="12oz",
        temperature="hot",
        shots=2,
        syrup="Caramel",
        notes=None,
        arrival_time_offset_sec=260,
        solo_prep_time_sec=100
    ),
    DrinkItem(
        id="item-109",
        order_id="ORD-109",
        customer_name="Emma L.",
        drink_name="Latte",
        category="hot_espresso_milk",
        milk_type="oat",
        size="12oz",
        temperature="hot",
        shots=2,
        syrup=None,
        notes=None,
        arrival_time_offset_sec=310,
        solo_prep_time_sec=95
    ),
    DrinkItem(
        id="item-110",
        order_id="ORD-110",
        customer_name="Noah C.",
        drink_name="Iced Americano",
        category="iced_espresso_milk",
        milk_type="none",
        size="16oz",
        temperature="iced",
        shots=2,
        syrup=None,
        notes="Extra ice",
        arrival_time_offset_sec=350,
        solo_prep_time_sec=55
    ),
    DrinkItem(
        id="item-111",
        order_id="ORD-111",
        customer_name="Zoe H.",
        drink_name="Iced Americano",
        category="iced_espresso_milk",
        milk_type="none",
        size="16oz",
        temperature="iced",
        shots=2,
        syrup=None,
        notes=None,
        arrival_time_offset_sec=390,
        solo_prep_time_sec=55
    ),
    DrinkItem(
        id="item-112",
        order_id="ORD-112",
        customer_name="Elena P.",
        drink_name="Cortado",
        category="hot_espresso_milk",
        milk_type="almond",
        size="4oz",
        temperature="hot",
        shots=2,
        syrup=None,
        notes="Glass cup if dine-in",
        arrival_time_offset_sec=430,
        solo_prep_time_sec=85
    )
]

PRESET_SCENARIOS = {
    "oat_rush": {
        "title": "Problem Statement Core: The 3x Oat Latte Scenario",
        "description": "Alice, Dave, and Chloe order Oat Lattes within 3 minutes. Barista makes 3 together instead of 3 separate times.",
        "items": [PEAK_RUSH_ORDERS[0], PEAK_RUSH_ORDERS[2], PEAK_RUSH_ORDERS[4]]
    },
    "morning_peak": {
        "title": "Morning Rush Hour (Full Queue 12 Drinks)",
        "description": "Full peak queue with mix of Oat Lattes, Whole Milk Flat Whites, Cold Brews, and Iced Americanos.",
        "items": PEAK_RUSH_ORDERS
    },
    "mixed_variety": {
        "title": "Mixed Specialty Milk Wave",
        "description": "Various milk types and temperatures highlighting compatibility segregation.",
        "items": [
            PEAK_RUSH_ORDERS[0], PEAK_RUSH_ORDERS[1], PEAK_RUSH_ORDERS[2],
            PEAK_RUSH_ORDERS[3], PEAK_RUSH_ORDERS[5], PEAK_RUSH_ORDERS[6],
            PEAK_RUSH_ORDERS[11]
        ]
    }
}
