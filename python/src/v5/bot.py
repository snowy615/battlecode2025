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

def turn():
    global SPAWN_LOC, MAP_CENTER
    try:
        if SPAWN_LOC is None:
            SPAWN_LOC = get_location()
            
        if MAP_CENTER is None:
            w = get_map_width()
            h = get_map_height()
            MAP_CENTER = MapLocation(w//2, h//2)
            
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
    
    # V5: More aggressive early game (no buffer until round 600)
    if round_num < 600:
        MIN_CHIPS = 0
    else:
        MIN_CHIPS = 1000 
    
    MIN_CHIPS_FOR_DEFENSE = 1000
    RICH_THRESHOLD = 2000
    
    under_threat = len(nearby_enemies) > 0
    
    if not under_threat:
        if money < MIN_CHIPS:
            return 

    # V5: More Splashers for map coverage, more Moppers for paint conversion
    prob_soldier = 0.50  # Reduced from 0.75
    prob_mopper = 0.20   # Increased from 0.05 - for paint conversion
    prob_splasher = 0.30 # Increased - for AoE expansion
    
    prob_money = 0.0
    prob_defense = 0.0
    
    if round_num > 400:
        prob_soldier = 0.40
        prob_mopper = 0.25
        prob_splasher = 0.25
        prob_defense = 0.10
    
    if money > RICH_THRESHOLD:
        prob_defense = 0.30
        
    spawn_dir = directions[random.randint(0, len(directions) - 1)]
    spawn_loc = my_location.add(spawn_dir)
    
    roll = random.random()
    
    # Defense Tower
    if (round_num > 400 and roll < prob_defense) or (money > RICH_THRESHOLD and roll < 0.3):
        if money > MIN_CHIPS_FOR_DEFENSE or under_threat:
             if can_build_robot(UnitType.LEVEL_ONE_DEFENSE_TOWER, spawn_loc):
                build_robot(UnitType.LEVEL_ONE_DEFENSE_TOWER, spawn_loc)
                return

    # Standard Units
    roll = random.random()
    
    limit_soldier = prob_soldier
    limit_mopper = limit_soldier + prob_mopper
    limit_splasher = limit_mopper + prob_splasher
    
    if roll < limit_soldier: 
        if can_build_robot(UnitType.SOLDIER, spawn_loc):
            build_robot(UnitType.SOLDIER, spawn_loc)
            return
    elif roll < limit_mopper:
        if can_build_robot(UnitType.MOPPER, spawn_loc):
            build_robot(UnitType.MOPPER, spawn_loc)
            return
    else:
        # Splasher
        if can_build_robot(UnitType.SPLASHER, spawn_loc):
            build_robot(UnitType.SPLASHER, spawn_loc)
            return

    # Final Fallback to Soldier
    if can_build_robot(UnitType.SOLDIER, spawn_loc):
         build_robot(UnitType.SOLDIER, spawn_loc)

# --- SOLDIER ---
def run_soldier():
    """
    V5 Behavior Tree:
    1. Complete Tower/SRP
    2. Paint Projects
    3. Combat
    4. Mark Tower/SRP
    5. AGGRESSIVE EXPANSION (paint enemy/empty tiles)
    6. Explore towards enemy territory
    """
    my_loc = get_location()
    
    # 1. Critical Actions
    if try_complete_structure(my_loc): return

    # 2. Paint Projects (Existing Marks)
    if try_paint_project(my_loc): return

    # 3. Combat
    if try_combat(my_loc): return
    
    # 4. Expansion Actions (Marking)
    if try_mark_structure(my_loc): return
    
    # 5. V5: Aggressive Paint (Higher chance)
    if try_aggressive_paint(my_loc): return
    
    # 6. V5: Explore towards MAP_CENTER (enemy territory)
    explore_aggressively(my_loc)

# --- V5 NEW BEHAVIORS ---

def try_aggressive_paint(my_loc):
    """V5: Always try to paint empty or enemy tiles. More aggressive than V3."""
    nearby_8 = [my_loc.translate(dx, dy) for dx in (-1,0,1) for dy in (-1,0,1)]
    random.shuffle(nearby_8)
    
    # Priority: Enemy > Empty > Self
    best_target = None
    best_priority = -1
    
    for loc in nearby_8:
        if can_attack(loc):
            try:
                tile = sense_map_info(loc)
                paint = tile.get_paint()
                
                priority = 0
                if paint.is_enemy():
                    priority = 3  # HIGH: Convert enemy paint
                elif paint == PaintType.EMPTY:
                    priority = 2  # MEDIUM: Claim empty
                elif not paint.is_ally():
                    priority = 1  # LOW: Other
                    
                if priority > best_priority:
                    best_priority = priority
                    best_target = loc
            except: pass
    
    if best_target and best_priority > 0:
        attack(best_target)
        return True
    return False

def explore_aggressively(my_loc):
    """V5: Spread out in ALL directions for full map coverage."""
    # Don't cluster towards center - explore randomly to cover more area
    navigate_randomly()

def try_mark_structure(my_loc):
    nearby_map_infos = sense_nearby_map_infos()
    
    # V5: LESS emphasis on safe ruins, more on expansion
    # Score = Distance(Me) only (grab any ruin fast)
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
            tower_type = UnitType.LEVEL_ONE_PAINT_TOWER
            if can_mark_tower_pattern(tower_type, ruin_loc):
                mark_tower_pattern(tower_type, ruin_loc)
                log("Marked Tower!")
                return True
        else:
            navigate_bounce(ruin_loc)
            return True

    # SRP (only if no enemies nearby)
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

# --- MOPPER (V5: More aggressive paint conversion) ---
def run_mopper():
    my_loc = get_location()
    nearby = sense_nearby_map_infos()
    random.shuffle(nearby)
    
    # V5: Prioritize enemy paint conversion
    # 1. Attack Enemy Paint (Convert!)
    for tile in nearby:
        if tile.get_paint().is_enemy() and can_attack(tile.get_map_location()):
             attack(tile.get_map_location())
             return

    # 2. Move towards enemy paint
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
    
    # 3. Attack empty (expand)
    for tile in nearby:
        if tile.get_paint() == PaintType.EMPTY and can_attack(tile.get_map_location()):
             attack(tile.get_map_location())
             return
             
    # 4. Explore in all directions (spread out)
    navigate_randomly()

# --- SPLASHER (V5: AoE expansion, seek enemy paint) ---
def run_splasher():
    my_loc = get_location()
    nearby = sense_nearby_map_infos()
    
    # V5: Count enemy/empty tiles. If high, attack for AoE conversion.
    enemy_count = 0
    empty_count = 0
    
    for tile in nearby:
        paint = tile.get_paint()
        if paint.is_enemy():
            enemy_count += 1
        elif paint == PaintType.EMPTY:
            empty_count += 1
    
    # If there are enemy or empty tiles, attack!
    if can_attack(my_loc) and (enemy_count > 0 or empty_count > 2):
        attack(my_loc)  # Splasher AoE
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

    # Explore in all directions (spread out for map coverage)
    navigate_randomly()

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
