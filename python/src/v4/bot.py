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

# V4: MAP MEMORY - Track explored areas and interesting locations
# Format: {(x, y): {'explored': bool, 'has_ruin': bool, 'is_enemy': bool}}
MAP_MEMORY = {}
UNEXPLORED_TARGETS = []  # Locations we want to explore

def turn():
    global SPAWN_LOC, MAP_CENTER
    try:
        if SPAWN_LOC is None:
            SPAWN_LOC = get_location()
            
        if MAP_CENTER is None:
            w = get_map_width()
            h = get_map_height()
            MAP_CENTER = MapLocation(w//2, h//2)
            # V4: Initialize exploration targets (edges and center)
            init_exploration_targets(w, h)
            
        # V4: Update map memory with what we see
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
    """V4: Create list of strategic locations to explore."""
    global UNEXPLORED_TARGETS
    # Corners
    UNEXPLORED_TARGETS = [
        MapLocation(2, 2),
        MapLocation(w-3, 2),
        MapLocation(2, h-3),
        MapLocation(w-3, h-3),
        # Midpoints
        MapLocation(w//2, 2),
        MapLocation(w//2, h-3),
        MapLocation(2, h//2),
        MapLocation(w-3, h//2),
        # Center
        MapLocation(w//2, h//2),
    ]

def update_map_memory():
    """V4: Remember what we see. Track ruins and enemy areas."""
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
            'is_ally': info.get_paint().is_ally(),
        }

def get_unexplored_target(my_loc):
    """V4: Find a location we haven't explored yet."""
    global UNEXPLORED_TARGETS
    
    # Filter out explored targets
    unexplored = []
    for target in UNEXPLORED_TARGETS:
        key = (target.x, target.y)
        if key not in MAP_MEMORY or not MAP_MEMORY[key].get('explored', False):
            unexplored.append(target)
    
    if unexplored:
        # Return closest unexplored
        unexplored.sort(key=lambda t: my_loc.distance_squared_to(t))
        return unexplored[0]
    return None

def is_near_center(loc):
    """V4: Check if location is in the center region of the map."""
    if MAP_CENTER:
        dist = loc.distance_squared_to(MAP_CENTER)
        # Within ~8 tiles of center
        return dist <= 64
    return False

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
    
    # V4: Keep some buffer for operations
    if round_num < 400:
        MIN_CHIPS = 0
    else:
        MIN_CHIPS = 500  # V4: Lower buffer, more units
    
    RICH_THRESHOLD = 2000
    
    under_threat = len(nearby_enemies) > 0
    
    if not under_threat:
        if money < MIN_CHIPS:
            return 

    # V4 PHASED STRATEGY:
    # Phase 1 (rounds 0-800): Soldiers + Splashers for expansion & tower building
    # Phase 2 (rounds 800+): Add Moppers for paint conversion in enemy territory
    
    if round_num < 800:
        # EXPANSION PHASE: Heavy soldiers + splashers, minimal moppers
        prob_soldier = 0.65
        prob_mopper = 0.05   # Almost no moppers early
        prob_splasher = 0.30
    else:
        # CONVERSION PHASE: Moppers push into enemy territory
        prob_soldier = 0.40
        prob_mopper = 0.35   # Heavy moppers for conversion
        prob_splasher = 0.25
        
    spawn_dir = directions[random.randint(0, len(directions) - 1)]
    spawn_loc = my_location.add(spawn_dir)
    
    roll = random.random()
    
    limit_soldier = prob_soldier
    limit_mopper = limit_soldier + prob_mopper
    
    if roll < limit_soldier: 
        if can_build_robot(UnitType.SOLDIER, spawn_loc):
            build_robot(UnitType.SOLDIER, spawn_loc)
            return
    elif roll < limit_mopper:
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
    V4 Behavior Tree (Phased Strategy):
    Phase 1 (0-800): Expand and build towers
    Phase 2 (800+): Stay home, complete patterns
    """
    my_loc = get_location()
    round_num = get_round_num()
    
    # 1. Critical Actions - Always complete structures first
    if try_complete_structure(my_loc): return

    # 2. Paint Projects
    if try_paint_project(my_loc): return

    # 3. Combat
    if try_combat(my_loc): return
    
    # 4. Expansion (Tower Marking) - Always try
    if try_mark_structure(my_loc): return
    
    # 5. Paint nearby
    if try_aggressive_paint(my_loc): return
    
    # 6. Movement Strategy depends on phase
    if round_num < 800:
        # EXPANSION PHASE: Explore everywhere
        smart_explore(my_loc)
    else:
        # CONSOLIDATION PHASE: Stay near home to complete patterns
        stay_near_home(my_loc)

def stay_near_home(my_loc):
    """V4: In late game, soldiers stay near spawn to help complete patterns."""
    if SPAWN_LOC:
        dist_to_spawn = my_loc.distance_squared_to(SPAWN_LOC)
        # If too far from spawn, move back
        if dist_to_spawn > 100:  # ~10 tiles
            navigate_bounce(SPAWN_LOC)
            return
    # Otherwise explore nearby
    navigate_randomly()

def smart_explore(my_loc):
    """V4: Random exploration (like V5) but occasionally check unexplored corners."""
    # 80% random, 20% targeted exploration
    if random.random() < 0.8:
        navigate_randomly()
    else:
        target = get_unexplored_target(my_loc)
        if target:
            navigate_bounce(target)
        else:
            navigate_randomly()

def try_aggressive_paint(my_loc):
    """Paint empty or enemy tiles aggressively."""
    nearby_8 = [my_loc.translate(dx, dy) for dx in (-1,0,1) for dy in (-1,0,1)]
    random.shuffle(nearby_8)
    
    best_target = None
    best_priority = -1
    
    for loc in nearby_8:
        if can_attack(loc):
            try:
                tile = sense_map_info(loc)
                paint = tile.get_paint()
                
                priority = 0
                if paint.is_enemy():
                    priority = 3
                elif paint == PaintType.EMPTY:
                    priority = 2
                elif not paint.is_ally():
                    priority = 1
                    
                if priority > best_priority:
                    best_priority = priority
                    best_target = loc
            except: pass
    
    if best_target and best_priority > 0:
        attack(best_target)
        return True
    return False

def try_mark_structure(my_loc):
    nearby_map_infos = sense_nearby_map_infos()
    
    best_ruin = None
    best_dist = 999999
    
    for info in nearby_map_infos:
        if info.has_ruin():
            loc = info.get_map_location()
            robot = sense_robot_at_location(loc)
            if robot and robot.get_team() == get_team(): continue
            if info.get_mark() != PaintType.EMPTY: continue
            
            dist = my_loc.distance_squared_to(loc)
            if dist < best_dist:
                best_dist = dist
                best_ruin = info

    if best_ruin:
        ruin_loc = best_ruin.get_map_location()
        if my_loc.distance_squared_to(ruin_loc) <= 2:
            # V4: Always mark PAINT tower (simpler, works)
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
    if len(nearby_enemies) == 0:
        for dx in range(-2, 3):
            for dy in range(-2, 3):
                check_loc = my_loc.translate(dx, dy)
                if can_mark_resource_pattern(check_loc):
                    mark_resource_pattern(check_loc)
                    log("Marked SRP!")
                    return True
        
    return False

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
        log("Completed SRP!")
        return True
        
    for d in directions:
        adj = my_loc.add(d)
        if can_complete_resource_pattern(adj):
            complete_resource_pattern(adj)
            log("Completed SRP!")
            return True
            
    return False

def try_paint_project(my_loc):
    nearby_map_infos = sense_nearby_map_infos()
    
    best_project = None
    best_dist = 999
    
    for info in nearby_map_infos:
        mark = info.get_mark()
        if mark != PaintType.EMPTY:
            paint = info.get_paint()
            if paint != mark:
                dist = my_loc.distance_squared_to(info.get_map_location())
                if dist < best_dist:
                    best_dist = dist
                    best_project = info.get_map_location()
    
    if best_project:
        if can_attack(best_project):
            target_info = sense_map_info(best_project)
            needed_mark = target_info.get_mark()
            use_secondary = (needed_mark == PaintType.ALLY_SECONDARY)
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
        
        dist_sq = my_loc.distance_squared_to(target.get_location())
        if dist_sq > 2:
             navigate_bounce(target.get_location())
        return True
    return False

# --- MOPPER ---
def run_mopper():
    """V4: Moppers convert enemy paint. In late game, push towards enemy."""
    my_loc = get_location()
    round_num = get_round_num()
    update_map_memory()
    
    nearby = sense_nearby_map_infos()
    random.shuffle(nearby)
    
    # 1. Attack Enemy Paint (Priority #1)
    for tile in nearby:
        if tile.get_paint().is_enemy() and can_attack(tile.get_map_location()):
             attack(tile.get_map_location())
             return

    # 2. Move towards visible enemy paint
    best_enemy_tile = None
    best_dist = 999
    for tile in nearby:
        if tile.get_paint().is_enemy():
            dist = my_loc.distance_squared_to(tile.get_map_location())
            if dist < best_dist:
                best_dist = dist
                best_enemy_tile = tile.get_map_location()
    
    if best_enemy_tile:
        navigate_bounce(best_enemy_tile)
        return
    
    # 3. Attack empty (spread paint)
    for tile in nearby:
        if tile.get_paint() == PaintType.EMPTY and can_attack(tile.get_map_location()):
             attack(tile.get_map_location())
             return
             
    # 4. Movement: Push towards enemy territory in late game
    if round_num >= 800 and MAP_CENTER:
        # Push towards center (enemy territory)
        navigate_bounce(MAP_CENTER)
    else:
        smart_explore(my_loc)

# --- SPLASHER ---
def run_splasher():
    my_loc = get_location()
    update_map_memory()  # V4: Keep memory updated
    
    nearby = sense_nearby_map_infos()
    
    enemy_count = 0
    empty_count = 0
    
    for tile in nearby:
        paint = tile.get_paint()
        if paint.is_enemy():
            enemy_count += 1
        elif paint == PaintType.EMPTY:
            empty_count += 1
    
    # Attack if worthwhile
    if can_attack(my_loc) and (enemy_count > 0 or empty_count > 2):
        attack(my_loc)
        return
        
    # Move towards enemy paint
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

    # V4: Smart exploration
    smart_explore(my_loc)

# --- UTILS ---
def navigate_bounce(target_loc):
    if not target_loc: return
    my_loc = get_location()
    
    if my_loc.distance_squared_to(target_loc) <= 2:
        return

    d_desired = my_loc.direction_to(target_loc)
    
    if can_move(d_desired):
        move(d_desired)
        return
        
    d_left = d_desired
    for _ in range(3):
        d_left = d_left.rotate_left()
        if can_move(d_left):
            move(d_left)
            return
            
    d_right = d_desired
    for _ in range(3):
        d_right = d_right.rotate_right()
        if can_move(d_right):
            move(d_right)
            return
            
    navigate_randomly()

def navigate_randomly():
    choices = list(directions)
    random.shuffle(choices)
    for d in choices:
        if can_move(d):
            move(d)
            return
