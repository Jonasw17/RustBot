"""
Rust Server Manager - Information Database
Contains all costs, recipes, and Q&A information for Rust items
"""

# === CRAFT DATA ===
CRAFT_DATA = {
    "assault rifle": {"Metal Frags": 50, "HQM": 1, "Wood": 200, "Springs": 4},
    "ak47": {"Metal Frags": 50, "HQM": 1, "Wood": 200, "Springs": 4},
    "bolt action rifle": {"Metal Frags": 25, "HQM": 3, "Wood": 50, "Springs": 4},
    "semi-automatic rifle": {"Metal Frags": 450, "HQM": 4, "Springs": 2},
    "lr-300": {"Metal Frags": 30, "HQM": 2, "Wood": 100, "Springs": 3},
    "mp5": {"Metal Frags": 500, "Springs": 3, "Empty Tins": 2},
    "thompson": {"Metal Frags": 450, "Wood": 100, "Springs": 4},
    "python": {"Metal Frags": 350, "HQM": 15, "Springs": 4},
    "revolver": {"Metal Frags": 125, "Springs": 1},
    "pump shotgun": {"Metal Frags": 100, "Wood": 75, "Springs": 4},
    "rocket launcher": {"Metal Frags": 50, "HQM": 4, "Wood": 200, "Springs": 4},
    "rocket": {"Explosives": 10, "Metal Pipe": 2, "Gun Powder": 150},
    "c4": {"Explosives": 20, "Tech Trash": 2, "Cloth": 5},
    "satchel charge": {"Beancan Grenade": 4, "Small Stash": 1, "Rope": 1},
    "f1 grenade": {"Metal Frags": 50, "Gun Powder": 60},
    "beancan grenade": {"Metal Frags": 60, "Gun Powder": 40},
    "stone wall": {"Stone": 300},
    "sheet metal wall": {"Metal Frags": 200},
    "armored wall": {"HQM": 25, "Metal Frags": 100},
    "wood wall": {"Wood": 200},
    "furnace": {"Stone": 200, "Wood": 100, "Low Grade": 50},
    "large furnace": {"Stone": 500, "Wood": 500, "Low Grade": 75},
}

# === RESEARCH DATA ===
RESEARCH_DATA = {
    "assault rifle": 500, "ak47": 500,
    "bolt action rifle": 750,
    "semi-automatic rifle": 125,
    "lr-300": 500, "mp5": 250, "thompson": 125,
    "python": 125, "revolver": 75,
    "pump shotgun": 125, "rocket launcher": 500,
    "c4": 500, "satchel charge": 75, "f1 grenade": 75,
    "stone wall": 75, "sheet metal wall": 125, "armored wall": 500,
    "furnace": 75, "large furnace": 125,
    "workbench t1": 75, "workbench t2": 500, "workbench t3": 1500,
}

# === RECYCLE DATA ===
RECYCLE_DATA = {
    "assault rifle": {"Metal Frags": 25, "HQM": 1, "Springs": 2},
    "bolt action rifle": {"Metal Frags": 13, "HQM": 2, "Springs": 2},
    "semi-automatic rifle": {"Metal Frags": 225, "HQM": 2, "Springs": 1},
    "rocket launcher": {"Metal Frags": 25, "HQM": 2, "Springs": 2},
    "pump shotgun": {"Metal Frags": 50, "Springs": 2},
    "revolver": {"Metal Frags": 63, "Springs": 1},
    "sheet metal door": {"Metal Frags": 75},
    "armored door": {"HQM": 13, "Metal Frags": 50},
    "sheet metal wall": {"Metal Frags": 100},
    "armored wall": {"HQM": 13, "Metal Frags": 50},
    "gears": {"Metal Frags": 25},
    "pipe": {"Metal Frags": 13},
    "springs": {"Metal Frags": 13},
    "tech trash": {"HQM": 1, "Scrap": 13},
}

# === DECAY DATA ===
DECAY_DATA = {
    "twig wall": 1, "twig foundation": 1,
    "wood wall": 3, "wood foundation": 3, "wood door": 3,
    "stone wall": 5, "stone foundation": 5,
    "sheet metal wall": 8, "sheet metal door": 8,
    "armored wall": 12, "armored door": 12,
    "furnace": 6, "large furnace": 6,
    "sleeping bag": 24, "bed": 24,
    "tool cupboard": 24, "tc": 24,
}

# === UPKEEP DATA ===
UPKEEP_DATA = {
    "wood wall": {"Wood": 7},
    "wood foundation": {"Wood": 7},
    "stone wall": {"Stone": 5},
    "stone foundation": {"Stone": 5},
    "sheet metal wall": {"Metal Frags": 3},
    "sheet metal foundation": {"Metal Frags": 3},
    "armored wall": {"HQM": 1},
    "armored foundation": {"HQM": 1},
}

# === CCTV DATA ===
CCTV_DATA = {
    "airfield": ["AIRFIELDLOOKOUT1", "AIRFIELDLOOKOUT2", "AIRFIELDHANGAR1", "AIRFIELDHANGAR2", "AIRFIELDTARMAC"],
    "bandit camp": ["BANDITCAMP1", "BANDITCAMP2", "BANDITCAMP3"],
    "dome": ["DOME1", "DOME2"],
    "gas station": ["GASSTATION1"],
    "harbour": ["HARBOUR1", "HARBOUR2"],
    "junkyard": ["JUNKYARD1", "JUNKYARD2"],
    "launch site": ["LAUNCHSITE1", "LAUNCHSITE2", "LAUNCHSITE3", "LAUNCHSITE4", "ROCKETFACTORY1"],
    "lighthouse": ["LIGHTHOUSE1"],
    "military tunnel": ["MILITARYTUNNEL1", "MILITARYTUNNEL2", "MILITARYTUNNEL3", "MILITARYTUNNEL4", "MILITARYTUNNEL5", "MILITARYTUNNEL6"],
    "oil rig": ["OILRIG1", "OILRIG1L1", "OILRIG1L2", "OILRIG1L3", "OILRIG1L4", "OILRIG1DOCK"],
    "large oil rig": ["OILRIG2", "OILRIG2L1", "OILRIG2L2", "OILRIG2L3", "OILRIG2L4", "OILRIG2L5", "OILRIG2L6", "OILRIG2DOCK"],
    "outpost": ["OUTPOST1", "OUTPOST2", "OUTPOST3"],
    "power plant": ["POWERPLANT1", "POWERPLANT2", "POWERPLANT3", "POWERPLANT4"],
    "satellite dish": ["SATELLITEDISH1", "SATELLITEDISH2", "SATELLITEDISH3"],
    "sewer branch": ["SEWERBRANCH1", "SEWERBRANCH2"],
    "supermarket": ["SUPERMARKET1"],
    "train yard": ["TRAINYARD1", "TRAINYARD2", "TRAINYARD3"],
    "water treatment": ["WATERTREATMENT1", "WATERTREATMENT2", "WATERTREATMENT3", "WATERTREATMENT4", "WATERTREATMENT5"],
    "mining outpost": ["MININGOUTPOST1"],
    "fishing village": ["FISHINGVILLAGE1"],
}

# === VEHICLE COSTS ===
VEHICLE_COSTS = {
    # Boats
    "rowboat": {
        "name": "Rowboat",
        "scrap": 125,
        "location": "Fishing Village"
    },
    "rhib": {
        "name": "RHIB",
        "scrap": 300,
        "location": "Fishing Village"
    },
    "submarine": {
        "name": "Submarine",
        "scrap": 200,
        "location": "Fishing Village (Duo) or Underwater Labs (Solo)"
    },

    # Helicopters
    "minicopter": {
        "name": "Minicopter",
        "scrap": 750,
        "location": "Airfield, Junkyard, or Oilrig"
    },
    "scrap_heli": {
        "name": "Scrap Transport Helicopter",
        "scrap": 1250,
        "location": "Airfield, Junkyard, or Oilrig"
    },
    "attack_heli": {
        "name": "Attack Helicopter",
        "scrap": 0,
        "location": "Patrol Helicopter (destroy and claim)",
        "note": "Free but must destroy Patrol Heli first"
    }
}

# Modular Car Components (Electrical Bench Branch Down Costs)
CAR_MODULE_COSTS = {
    "camper_module": {
        "name": "Camper Module",
        "scrap": 125,
        "workbench": "Electrical Branch Down (Level 2)",
        "storage": "48 slots",
        "features": ["Sleeping bags", "Storage", "BBQ"]
    },
    "flatbed_module": {
        "name": "Flatbed Module",
        "scrap": 125,
        "workbench": "Electrical Branch Down (Level 2)",
        "storage": "18 slots"
    },
    "cockpit_module": {
        "name": "Cockpit with Armored Passenger Module",
        "scrap": 125,
        "workbench": "Electrical Branch Down (Level 2)",
        "armor": "Yes"
    },
    "engine_module": {
        "name": "Engine Module",
        "scrap": 75,
        "workbench": "Electrical Branch Down (Level 2)",
        "note": "Required to drive"
    }
}

# Smart Switch Information
SMART_SWITCH_INFO = {
    "name": "Smart Switch",
    "power_usage": 1,
    "can_toggle": True,
    "remote_control": True,
    "max_output": "Power Input",
    "crafting": {
        "tech_trash": 1,
        "scrap": 75
    }
}

# Device Categories
DEVICE_CATEGORIES = {
    "pairing": {
        "name": "Server Pairing Devices",
        "description": "Devices you pair to access the server",
        "devices": ["Tool Cupboard", "Code Lock", "Key Lock", "Auto Turret"]
    },
    "smart_items": {
        "name": "Smart Items",
        "description": "In-game items you can control remotely",
        "devices": ["Smart Switch", "Smart Alarm", "RF Broadcaster", "RF Receiver"]
    },
    "vehicles": {
        "name": "Vehicles & Drones",
        "description": "Vehicles and flying devices",
        "devices": ["Minicopter", "Scrap Heli", "RHIB", "Rowboat", "Submarine", "Drone"]
    }
}

# Common Q&A
COMMON_QUESTIONS = {
    "tc_range": {
        "question": "What is the Tool Cupboard range?",
        "answer": "The Tool Cupboard has a range of approximately 25 meters in all directions (including up and down)."
    },
    "auto_turret_range": {
        "question": "What is the Auto Turret range?",
        "answer": "Auto Turrets have a range of 30 meters and require 10 power to operate."
    },
    "smart_switch_usage": {
        "question": "How do I use Smart Switches?",
        "answer": "Smart Switches can be controlled remotely via the Rust+ app. Add them with !addswitch, then use !sson and !ssoff to toggle them."
    },
    "vehicle_decay": {
        "question": "How long until vehicles decay?",
        "answer": "Vehicles decay after 3 hours outside. Keep them in a garage or on a boat lift to prevent decay."
    },
    "boat_lift_cost": {
        "question": "How much does a boat lift cost?",
        "answer": "Boat Lift costs 200 scrap to research at a workbench and requires: 200 Wood, 200 Metal Fragments, 1 Gear."
    },
    "blueprint_fragments": {
        "question": "How do I get Blueprint Fragments?",
        "answer": "Basic Fragments: Green puzzles (x1), Blue puzzles (x2), monuments, airdrops. Advanced Fragments: Hackable crates (pairs), elite crates (1/10 chance), major monuments. Convert 20 Basic to 1 Advanced."
    }
}

# Workbench Information
WORKBENCH_INFO = {
    "level1": {
        "name": "Workbench Level 1",
        "cost": {
            "metal_fragments": 500,
            "wood": 100,
            "scrap": 50
        },
    },
    "level2": {
        "name": "Workbench Level 2",
        "cost": {
            "metal_fragments": 500,
            "HQM": 20,
            "scrap": 250,
            "Basic Blueprint Fragments": 5
        },
    },
    "level3": {
        "name": "Workbench Level 3",
        "cost": {
            "metal_fragments": 1000,
            "HQM": 100,
            "scrap": 500,
            "Advanced Blueprint Fragments": 5
        },
    }
}

# === BLUEPRINT FRAGMENT DATA ===
BLUEPRINT_FRAGMENT_DATA = {
    "basic": {
        "name": "Basic Blueprint Fragments",
        "sources": {
            "guaranteed": [
                "Green puzzle rooms (x1 per room)",
                "Blue-card puzzles next to red keycard (x2)",
            ],
            "common": [
                "Medium to large monuments",
                "Airdrops",
            ],
            "chance": [
                "Military crates",
                "Large underwater crates",
                "Junkpile scientists",
                "Roadside metal detecting",
            ]
        },
        "notes": [
            "Chaining green and blue puzzles gives 3 fragments in one run",
            "20 Basic Fragments can be converted to 1 Advanced Fragment"
        ]
    },
    "advanced": {
        "name": "Advanced Blueprint Fragments",
        "sources": {
            "guaranteed": [
                "Hackable crates (always spawn in pairs)",
            ],
            "chance": [
                "Elite crates (1 in 10 chance)",
            ],
            "locations": [
                "Launch Site",
                "Military Tunnels",
                "Nuclear Missile Silo",
                "Underwater Labs",
                "Small Oil Rig",
                "Large Oil Rig",
                "Cargo Ship event",
                "CH47 Chinook crate drop",
            ]
        },
        "notes": [
            "Always spawn in pairs when found",
            "Fallback: Convert 20 Basic Fragments to 1 Advanced Fragment"
        ]
    }
}

def get_blueprint_fragment_info(fragment_type: str = None):
    """Get blueprint fragment information"""
    if fragment_type and fragment_type.lower() in BLUEPRINT_FRAGMENT_DATA:
        data = BLUEPRINT_FRAGMENT_DATA[fragment_type.lower()]
        lines = [f"**{data['name']}**\n"]

        for category, items in data['sources'].items():
            lines.append(f"\n__{category.title()}:__")
            for item in items:
                lines.append(f"• {item}")

        if 'notes' in data:
            lines.append("\n__Notes:__")
            for note in data['notes']:
                lines.append(f"• {note}")

        return "\n".join(lines)
    else:
        # Return both types
        basic = get_blueprint_fragment_info("basic")
        advanced = get_blueprint_fragment_info("advanced")
        return f"{basic}\n\n{advanced}"

def get_vehicle_cost(vehicle_name):
    """Get the cost information for a specific vehicle"""
    vehicle_key = vehicle_name.lower().replace(" ", "_")
    return VEHICLE_COSTS.get(vehicle_key)

def get_car_module_cost(module_name):
    """Get the cost information for a car module"""
    module_key = module_name.lower().replace(" ", "_")
    return CAR_MODULE_COSTS.get(module_key)

def get_all_vehicle_costs():
    """Get all vehicle costs formatted as a string"""
    boats = "\n".join([
        f"**{v['name']}**: {v['scrap']} scrap at {v['location']}"
        for v in VEHICLE_COSTS.values()
        if 'boat' in v['name'].lower() or 'submarine' in v['name'].lower()
    ])

    helis = "\n".join([
        f"**{v['name']}**: {v['scrap']} scrap at {v['location']}" +
        (f" - {v['note']}" if 'note' in v else "")
        for v in VEHICLE_COSTS.values()
        if 'heli' in v['name'].lower() or 'copter' in v['name'].lower()
    ])

    return f"**Boats:**\n{boats}\n\n**Helicopters:**\n{helis}"

def get_all_car_module_costs():
    """Get all car module costs formatted as a string"""
    modules = "\n".join([
        f"**{m['name']}**: {m['scrap']} scrap (Branch down from {m['workbench']})"
        for m in CAR_MODULE_COSTS.values()
    ])
    return f"**Modular Car Components:**\n{modules}"

def search_info(query):
    """Search for information based on a query"""
    query_lower = query.lower()
    results = []

    # Search vehicles
    for key, vehicle in VEHICLE_COSTS.items():
        if query_lower in vehicle['name'].lower():
            results.append({
                'type': 'vehicle',
                'data': vehicle
            })

    # Search car modules
    for key, module in CAR_MODULE_COSTS.items():
        if query_lower in module['name'].lower():
            results.append({
                'type': 'car_module',
                'data': module
            })

    # Search Q&A
    for key, qa in COMMON_QUESTIONS.items():
        if query_lower in qa['question'].lower() or query_lower in qa['answer'].lower():
            results.append({
                'type': 'qa',
                'data': qa
            })

    # Search blueprint fragments
    if 'fragment' in query_lower or 'blueprint' in query_lower:
        for key, data in BLUEPRINT_FRAGMENT_DATA.items():
            results.append({
                'type': 'blueprint_fragment',
                'data': data
            })

    return results