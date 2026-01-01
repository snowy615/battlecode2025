import random
from battlecode25.stubs import *

# Globals
directions = [
    Direction.NORTH,
    Direction.NORTHEAST,
    Direction.EAST,
    Direction.SOUTHEAST,
    Direction.SOUTH,
    Direction.SOUTHWEST,
    Direction.WEST,
    Direction.NORTHWEST,
]

SPAWN_LOC = None
MAP_CENTER = None
# V7: Store dominant direction for each unit
# Key: Robot ID, Value: Direction
UNIT_DOMINANT_DIR = {}

# V7: Map Memory (from V4)
MAP_MEMORY = {}
UNEXPLORED_TARGETS = []

def turn():
    global SPAWN_LOC, MAP_CENTER
    try:
        if SPAWN_LOC is None:
            SPAWN_LOC = get_location()
            
        if MAP_CENTER is None:
            w = get_map_width()
            h = get_map_height()
            MAP_CENTER = MapLocation(w//2, h//2)
            init_exploration_targets(w, h)
        
        # Update map memory each turn
        update_map_memory()
            
        my_type = get_type()
        if my_type == UnitType.SOLDIER:
            run_soldier()
        elif my_type == UnitType.MOPPER:
            run_mopper()
        elif my_type == UnitType.SPLASHER:
            run_splasher()
        elif my_type.is_tower_type():
            run_tower()
    except Exception as e:
        log(f"Error in turn: {e}")

# --- MAP MEMORY HELPERS (from V4) ---
def init_exploration_targets(w, h):
    global UNEXPLORED_TARGETS
    UNEXPLORED_TARGETS = [
        MapLocation(2, 2), MapLocation(w-3, 2),
        MapLocation(2, h-3), MapLocation(w-3, h-3),
        MapLocation(w//2, 2), MapLocation(w//2, h-3),
        MapLocation(2, h//2), MapLocation(w-3, h//2),
        MapLocation(w//2, h//2),
    ]

def update_map_memory():
    global MAP_MEMORY
    my_loc = get_location()
    nearby = sense_nearby_map_infos()
    for info in nearby:
        loc = info.get_map_location()
        key = (loc.x, loc.y)
        MAP_MEMORY[key] = {
            'explored': True,
            'has_ruin': info.has_ruin(),
            'is_enemy': info.get_paint().is_enemy(),
        }

def get_unexplored_target(my_loc):
    global UNEXPLORED_TARGETS
    unexplored = []
    for target in UNEXPLORED_TARGETS:
        key = (target.x, target.y)
        if key not in MAP_MEMORY or not MAP_MEMORY[key].get('explored', False):
            unexplored.append(target)
    if unexplored:
        unexplored.sort(key=lambda t: my_loc.distance_squared_to(t))
        return unexplored[0]
    return None

# --- TOWER ---
def run_tower():
    my_location = get_location()
    
    # 1. Attack
    nearby_enemies = sense_nearby_robots(team=get_team().opponent())
    if len(nearby_enemies) > 0:
        target = nearby_enemies[0]
        if can_attack(target.get_location()):
            attack(target.get_location())
            return

    # 2. Spawn
    round_num = get_round_num()
    money = get_money()
    
    # Economy Buffer
    if round_num < 400:
        MIN_CHIPS = 0
    else:
        MIN_CHIPS = 500
        
    if not nearby_enemies and money < MIN_CHIPS:
        return

    # V7: "More soldiers at the front in all directions!"
    # Boosted soldier ratios for maximum expansion pressure
    
    if round_num < 500:
        # MAXIMUM SOLDIER SWARM
        prob_soldier = 0.90  # Increased from 0.85
        prob_mopper = 0.03
        prob_splasher = 0.07
    elif round_num < 1000:
        # Heavy Soldier Transition
        prob_soldier = 0.75  # Increased from 0.65
        prob_mopper = 0.10
        prob_splasher = 0.15
    else:
        # Late Game (Still Soldier-Heavy)
        prob_soldier = 0.60  # Increased from 0.50
        prob_mopper = 0.20
        prob_splasher = 0.20
        
    spawn_dir = directions[random.randint(0, 7)]
    spawn_loc = my_location.add(spawn_dir)
    
    roll = random.random()
    
    if roll < prob_soldier:
        if can_build_robot(UnitType.SOLDIER, spawn_loc):
            build_robot(UnitType.SOLDIER, spawn_loc)
            return
    elif roll < prob_soldier + prob_mopper:
        if can_build_robot(UnitType.MOPPER, spawn_loc):
            build_robot(UnitType.MOPPER, spawn_loc)
            return
    else:
        if can_build_robot(UnitType.SPLASHER, spawn_loc):
            build_robot(UnitType.SPLASHER, spawn_loc)
            return

    # Fallback
    if can_build_robot(UnitType.SOLDIER, spawn_loc):
         build_robot(UnitType.SOLDIER, spawn_loc)

# --- SOLDIER ---
def run_soldier():
    """
    V7 Hybrid Behavior:
    - 80% Directional Explorers (Dominant Direction)  
    - 20% Random Explorers (Map Memory + Random Walk)
    """
    my_loc = get_location()
    my_id = get_id()
    
    # Assign Role: 80% Directional, 20% Random
    is_directional = (my_id % 100) < 80
    
    # 1. Critical: Complete Structure
    if try_complete_structure(my_loc): return

    # 2. Paint Project
    if try_paint_project(my_loc): return

    # 3. Combat
    if try_combat(my_loc): return
    
    # 4. Mark Tower/SRP
    if try_mark_structure(my_loc): return
    
    # 5. Aggressive Paint
    if try_aggressive_paint(my_loc): return
    
    # 6. MOVEMENT (Hybrid)
    if is_directional:
        # Directional Explorer: Use dominant direction
        navigate_dominant(my_loc, my_id)
    else:
        # Random Explorer: Use map memory to find unexplored areas
        smart_explore(my_loc) 

def navigate_dominant(my_loc, my_id):
    """
    V7 Refined:
    1. Try Dominant Dir
    2. Try Dominant +/- 45 (Diagonals)
    3. Try Perpendiculars (90 deg)
    4. If all fail (Dead End), SWITCH Dominant to Opposite.
    """
    global UNIT_DOMINANT_DIR
    
    if my_id not in UNIT_DOMINANT_DIR:
        # Initial: Random valid direction
        d = directions[random.randint(0, 7)]
        UNIT_DOMINANT_DIR[my_id] = d
        
    dom_dir = UNIT_DOMINANT_DIR[my_id]
    
    # 1. Try Dominant
    if can_move(dom_dir):
        move(dom_dir)
        return True
        
    # 2. Try Diagonals (Left/Right 45) -> "Next in {EW} {NS}" approximation
    d_left = dom_dir.rotate_left()
    if can_move(d_left):
        move(d_left)
        return True
        
    d_right = dom_dir.rotate_right()
    if can_move(d_right):
        move(d_right)
        return True
        
    # 3. Try Perpendiculars (Left/Right 90)
    d_left90 = d_left.rotate_left()
    if can_move(d_left90):
        move(d_left90)
        return True
        
    d_right90 = d_right.rotate_right()
    if can_move(d_right90):
        move(d_right90)
        return True
        
    # 4. DEAD END / WALL -> Switch Dominant to Opposite
    new_dom = dom_dir.opposite()
    UNIT_DOMINANT_DIR[my_id] = new_dom
    
    # Try moving to new dominant immediately
    if can_move(new_dom):
        move(new_dom)
        return True
        
    # If even opposite is blocked (Surrounded?), try ANY valid direction
    for d in directions:
        if can_move(d):
            move(d)
            return True
            
    return False


# --- MOPPER ---
def run_mopper():
    my_loc = get_location()
    # Standard logic
    nearby = sense_nearby_map_infos()
    random.shuffle(nearby)
    for tile in nearby:
        if tile.get_paint().is_enemy() and can_attack(tile.get_map_location()):
             attack(tile.get_map_location())
             return
    
    best_enemy = None
    best_dist = 999
    for tile in nearby:
        if tile.get_paint().is_enemy():
            dist = my_loc.distance_squared_to(tile.get_map_location())
            if dist < best_dist:
                best_dist = dist
                best_enemy = tile.get_map_location()
    
    if best_enemy:
        navigate_bounce(best_enemy)
        return
        
    for tile in nearby:
        if tile.get_paint() == PaintType.EMPTY and can_attack(tile.get_map_location()):
             attack(tile.get_map_location())
             return
             
    navigate_randomly()

# --- SPLASHER ---
def run_splasher():
    my_loc = get_location()
    nearby = sense_nearby_map_infos()
    enemy_count = 0
    empty_count = 0
    for tile in nearby:
        p = tile.get_paint()
        if p.is_enemy(): enemy_count += 1
        elif p == PaintType.EMPTY: empty_count += 1
        
    if can_attack(my_loc) and (enemy_count > 0 or empty_count > 2):
        attack(my_loc)
        return
        
    navigate_randomly()

# --- UTILS ---
def smart_explore(my_loc):
    """V7: Use map memory to explore unexplored areas, fallback to random."""
    # 70% try to go to unexplored target, 30% random
    if random.random() < 0.7:
        target = get_unexplored_target(my_loc)
        if target:
            navigate_bounce(target)
            return
    # Fallback to random
    navigate_randomly()

def navigate_bounce(target_loc):
    if not target_loc: return
    my_loc = get_location()
    if my_loc.distance_squared_to(target_loc) <= 2: return
    d = my_loc.direction_to(target_loc)
    if can_move(d):
        move(d)
        return
    dl = d
    dr = d
    for _ in range(3):
        dl = dl.rotate_left()
        if can_move(dl): move(dl); return
        dr = dr.rotate_right()
        if can_move(dr): move(dr); return
    navigate_randomly()

def navigate_randomly():
    choices = list(directions)
    random.shuffle(choices)
    for d in choices:
        if can_move(d):
            move(d)
            return

def try_complete_structure(my_loc):
    nearby_map_infos = sense_nearby_map_infos()
    for info in nearby_map_infos:
        if info.has_ruin():
            ruin_loc = info.get_map_location()
            tower_type = UnitType.LEVEL_ONE_PAINT_TOWER
            if can_complete_tower_pattern(tower_type, ruin_loc):
                complete_tower_pattern(tower_type, ruin_loc)
                log("Completed Tower!")
                return True
    
    if can_complete_resource_pattern(my_loc):
        complete_resource_pattern(my_loc)
        return True
    for d in directions:
        adj = my_loc.add(d)
        if can_complete_resource_pattern(adj):
            complete_resource_pattern(adj)
            return True
    return False

def try_paint_project(my_loc):
    nearby_map_infos = sense_nearby_map_infos()
    best_project = None
    best_dist = 999
    for info in nearby_map_infos:
        mark = info.get_mark()
        if mark != PaintType.EMPTY and info.get_paint() != mark:
            dist = my_loc.distance_squared_to(info.get_map_location())
            if dist < best_dist:
                best_dist = dist
                best_project = info.get_map_location()
    if best_project:
        if can_attack(best_project):
            target_info = sense_map_info(best_project)
            use_secondary = (target_info.get_mark() == PaintType.ALLY_SECONDARY)
            attack(best_project, use_secondary)
            return True
        else:
            navigate_bounce(best_project)
            return True
    return False

def try_combat(my_loc):
    nearby_enemies = sense_nearby_robots(team=get_team().opponent())
    if nearby_enemies:
        target = nearby_enemies[0]
        if can_attack(target.get_location()):
            attack(target.get_location())
        dist = my_loc.distance_squared_to(target.get_location())
        if dist > 2:
            navigate_bounce(target.get_location())
        return True
    return False

def try_mark_structure(my_loc):
    nearby_map_infos = sense_nearby_map_infos()
    best_ruin = None
    best_dist = 999
    for info in nearby_map_infos:
        if info.has_ruin() and info.get_mark() == PaintType.EMPTY:
            loc = info.get_map_location()
            rob = sense_robot_at_location(loc)
            if rob and rob.get_team() == get_team(): continue
            dist = my_loc.distance_squared_to(loc)
            if dist < best_dist:
                best_dist = dist
                best_ruin = info
                
    if best_ruin:
        ruin_loc = best_ruin.get_map_location()
        if my_loc.distance_squared_to(ruin_loc) <= 2:
            tower_type = UnitType.LEVEL_ONE_PAINT_TOWER
            # V7: Maybe prioritize Defense? Keeping simple Paint Tower for now as per V4 success.
            # User didn't specify tower type change.
            if can_mark_tower_pattern(tower_type, ruin_loc):
                mark_tower_pattern(tower_type, ruin_loc)
                log("Marked Tower!")
                return True
        else:
            navigate_bounce(ruin_loc)
            return True
            
    # SRP
    nearby_enemies = sense_nearby_robots(team=get_team().opponent())
    if not nearby_enemies:
        for dx in range(-2, 3):
            for dy in range(-2, 3):
                loc = my_loc.translate(dx, dy)
                if can_mark_resource_pattern(loc):
                    mark_resource_pattern(loc)
                    return True
    return False

def try_aggressive_paint(my_loc):
    nearby_8 = [my_loc.translate(dx, dy) for dx in (-1,0,1) for dy in (-1,0,1)]
    random.shuffle(nearby_8)
    best_target = None
    best_priority = -1
    for loc in nearby_8:
        if can_attack(loc):
            try:
                paint = sense_map_info(loc).get_paint()
                p = 0
                if paint.is_enemy(): p = 3
                elif paint == PaintType.EMPTY: p = 2
                elif not paint.is_ally(): p = 1
                if p > best_priority:
                    best_priority = p
                    best_target = loc
            except: pass
    if best_target and best_priority > 0:
        attack(best_target)
        return True
    return False
