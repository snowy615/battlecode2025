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
MAP_MEMORY = {}
UNEXPLORED_TARGETS = []

# V6: Tower Spawn State
# Key: Tower ID, Value: 'SOLDIER', 'MOPPER', etc.
TOWER_LAST_SPAWN = {}

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

def is_near_center(loc):
    if MAP_CENTER:
        return loc.distance_squared_to(MAP_CENTER) <= 64
    return False

# --- TOWER ---
def run_tower():
    my_location = get_location()
    my_id = get_id()
    
    # 1. Attack
    nearby_enemies = sense_nearby_robots(team=get_team().opponent())
    if len(nearby_enemies) > 0:
        target = nearby_enemies[0]
        if can_attack(target.get_location()):
            attack(target.get_location())
            return

    # 2. Spawn Logic
    round_num = get_round_num()
    money = get_money()
    
    # V6 Phase Logic
    PHASE_1_END = 1000 
    
    # Economy Buffer
    if round_num < 400:
        MIN_CHIPS = 0
    else:
        MIN_CHIPS = 500
        
    if not nearby_enemies and money < MIN_CHIPS:
        return

    spawn_dir = directions[random.randint(0, 7)]
    spawn_loc = my_location.add(spawn_dir)
    
    target_type = None
    
    if round_num < PHASE_1_END:
        # Phase 1: High Soldier count (70%), Low Mopper (5%)
        # Moppers still follow soldiers (handled in run_mopper)
        roll = random.random()
        if roll < 0.70:
            target_type = UnitType.SOLDIER
        elif roll < 0.75: # 5% Mopper
            target_type = UnitType.MOPPER
        else:
            target_type = UnitType.SPLASHER
            
    else:
        # Phase 2: Squad Logic
        # User wants "2 soldiers mapping, 1 mopper following, 1 soldier building"
        # This implies a ratio of 3 Soldiers : 1 Mopper (75% / 25%)
        # Let's keep the cycle logic as it enforces this EXACT composition.
        spawn_cycle = TOWER_LAST_SPAWN.get(f"{my_id}_cycle", 0)
        
        if spawn_cycle == 0:
            target_type = UnitType.SOLDIER # Scout 1
        elif spawn_cycle == 1:
            target_type = UnitType.SOLDIER # Scout 2
        elif spawn_cycle == 2:
            target_type = UnitType.MOPPER # Follower
        else:
            target_type = UnitType.SOLDIER # Builder
            
    # Try build
    if target_type and can_build_robot(target_type, spawn_loc):
        build_robot(target_type, spawn_loc)
        
        # Update cycle for Phase 2
        if round_num >= PHASE_1_END:
            current_cycle = TOWER_LAST_SPAWN.get(f"{my_id}_cycle", 0)
            TOWER_LAST_SPAWN[f"{my_id}_cycle"] = (current_cycle + 1) % 4
        return
        
    # Fallback
    if can_build_robot(UnitType.SOLDIER, spawn_loc):
         build_robot(UnitType.SOLDIER, spawn_loc)

# --- SOLDIER ---
def run_soldier():
    my_loc = get_location()
    round_num = get_round_num()
    my_id = get_id()
    
    # 1. Critical
    if try_complete_structure(my_loc): return
    if try_paint_project(my_loc): return
    if try_combat(my_loc): return
    
    # 2. Marking (Expansion)
    if try_mark_structure(my_loc): return
    
    # 3. Paint
    if try_aggressive_paint(my_loc): return
    
    # 4. Movement / Role
    PHASE_1_END = 1000
    
    if round_num < PHASE_1_END:
        # Phase 1: "Painting and Building" -> Explore
        smart_explore(my_loc)
    else:
        # Phase 2: "2 mapping, 1 follower mopper, 1 builder soldier"
        # Assign roles based on ID or simple heuristic?
        # "Mapping" = Explore. "Building" = Follow behind?
        # Let's use ID parity.
        # Check if I am a "Builder" (follow behind).
        # Heuristic: If I just spawned, I might be the builder?
        # Let's say: Odd IDs map, Even IDs build/consolidate.
        if my_id % 2 != 0:
            # Mapper / Scout
            smart_explore(my_loc)
        else:
            # Builder / Follower
            # Search for allied paint to defend/complete? or stay near spawn?
            stay_near_home(my_loc)

def stay_near_home(my_loc):
    if SPAWN_LOC:
        if my_loc.distance_squared_to(SPAWN_LOC) > 100:
            navigate_bounce(SPAWN_LOC)
            return
    navigate_randomly()

def smart_explore(my_loc):
    if random.random() < 0.7:
        navigate_randomly()
    else:
        target = get_unexplored_target(my_loc)
        if target:
            navigate_bounce(target)
        else:
            navigate_randomly()

# --- MOPPER ---
def run_mopper():
    # V6: "Follow one of them [Soldiers]"
    my_loc = get_location()
    
    # 1. Combat / Paint (Standard priority)
    nearby_map = sense_nearby_map_infos()
    random.shuffle(nearby_map)
    for tile in nearby_map:
        if tile.get_paint().is_enemy() and can_attack(tile.get_map_location()):
             attack(tile.get_map_location())
             return
             
    # 2. Follow Soldier (Looser logic)
    nearby_robots = sense_nearby_robots(team=get_team())
    closest_soldier = None
    min_dist = 999
    
    for bot in nearby_robots:
        if bot.get_type() == UnitType.SOLDIER:
            dist = my_loc.distance_squared_to(bot.get_location())
            if dist < min_dist:
                min_dist = dist
                closest_soldier = bot
    
    if closest_soldier:
        start_dist = my_loc.distance_squared_to(closest_soldier.get_location())
        
        # If too far (> 16), move closer
        if start_dist > 16:
            navigate_bounce(closest_soldier.get_location())
            return
        # If too close (< 4), move away or explore outwards
        elif start_dist < 4:
            smart_explore(my_loc) # Spread out a bit
            return
        else:
            # Sweet spot (4-16): Paint/Explore nearby without moving too far
            pass  # Fall through to explore/paint nearby

    # Fallback: Explore
    smart_explore(my_loc)

# --- SPLASHER ---
def run_splasher():
    my_loc = get_location()
    # Standard aggressive
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
        
    smart_explore(my_loc)

# --- UTILS (Standard) ---
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
        if can_move(dl):
            move(dl)
            return
        dr = dr.rotate_right()
        if can_move(dr):
            move(dr)
            return
    navigate_randomly()

def navigate_randomly():
    choices = list(directions)
    random.shuffle(choices)
    for d in choices:
        if can_move(d):
            move(d)
            return
