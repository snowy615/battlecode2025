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

def turn():
    try:
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
    
    # DYNAMIC ECONOMY
    # Early Game: Swarm (0 Buffer). Late Game: Build Towers (1000 Buffer).
    if round_num < 400:
        MIN_CHIPS = 0
    else:
        MIN_CHIPS = 1000 
    
    MIN_CHIPS_FOR_DEFENSE = 1000
    RICH_THRESHOLD = 2000
    
    under_threat = len(nearby_enemies) > 0
    
    if not under_threat:
        if money < MIN_CHIPS:
            return 
 
            
    # Ratios
    # Favor Splashers (AoE) over Moppers for combat survival
    prob_soldier = 0.75
    prob_mopper = 0.05
    # prob_splasher = remainder (~0.20)
    
    prob_money = 0.0
    prob_defense = 0.0
    
    if round_num > 400:
        prob_soldier = 0.65
        prob_mopper = 0.10
        prob_money = 0.0
        prob_defense = 0.10
    
    if money > RICH_THRESHOLD:
        prob_defense = 0.50
        
    spawn_dir = directions[random.randint(0, len(directions) - 1)]
    spawn_loc = my_location.add(spawn_dir)
    
    roll = random.random()
    
    # Defense Tower
    if (round_num > 400 and roll < prob_defense) or (money > RICH_THRESHOLD and roll < 0.5):
        if money > MIN_CHIPS_FOR_DEFENSE or under_threat:
             if can_build_robot(UnitType.LEVEL_ONE_DEFENSE_TOWER, spawn_loc):
                build_robot(UnitType.LEVEL_ONE_DEFENSE_TOWER, spawn_loc)
                return

    # Money Tower
    if roll < prob_money and round_num < 200 and money < RICH_THRESHOLD:
        if can_build_robot(UnitType.LEVEL_ONE_MONEY_TOWER, spawn_loc):
             build_robot(UnitType.LEVEL_ONE_MONEY_TOWER, spawn_loc)
             return

    # Standard Units
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
        # Splasher
        if can_build_robot(UnitType.SPLASHER, spawn_loc):
            build_robot(UnitType.SPLASHER, spawn_loc)
            return

    # Final Fallback to Soldier if Splasher failed
    if can_build_robot(UnitType.SOLDIER, spawn_loc):
         build_robot(UnitType.SOLDIER, spawn_loc)

# --- SOLDIER ---
def run_soldier():
    """
    Behavior Tree Structure:
    1. Try Complete Tower/SRP (Critical Economy)
    2. Try Paint Project (Working on existing Marks)
    3. Try Combat (Survival/Offense)
    4. Try Mark Tower/SRP (Expansion)
    5. Explore/Paint
    """
    my_loc = get_location()
    
    # 1. Critical Actions
    if try_complete_structure(my_loc): return

    # 2. Paint Projects (Existing Marks)
    # This MUST be higher priority than Marking to prevent infinite loops.
    if try_paint_project(my_loc): return

    # 3. Combat
    if try_combat(my_loc): return
    
    # 4. Expansion Actions (Marking)
    if try_mark_structure(my_loc): return
    
    # 5. Explore / Paint Ground
    if try_paint_ground(my_loc): return
    
    navigate_randomly()

# --- BEHAVIORS ---

def try_complete_structure(my_loc):
    # 1. Check for Towers at Ruins
    nearby_map_infos = sense_nearby_map_infos()
    for info in nearby_map_infos:
        if info.has_ruin():
            ruin_loc = info.get_map_location()
            tower_type = UnitType.LEVEL_ONE_PAINT_TOWER
            
            if can_complete_tower_pattern(tower_type, ruin_loc):
                complete_tower_pattern(tower_type, ruin_loc)
                log("Completed Tower!")
                return True
                
    # 2. Check for SRPs (Immediate Vicinity)
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
    # Scan for tiles that are MARKED but need painting.
    nearby_map_infos = sense_nearby_map_infos()
    
    best_project = None
    best_dist = 999
    
    for info in nearby_map_infos:
        mark = info.get_mark()
        # If marked and not empty, it's a project.
        if mark != PaintType.EMPTY:
            # Check if paint matches mark (simple check: if paint != mark)
            # Actually, we need to correct it.
            paint = info.get_paint()
            if paint != mark:
                dist = my_loc.distance_squared_to(info.get_map_location())
                if dist < best_dist:
                    best_dist = dist
                    best_project = info.get_map_location()
    
    if best_project:
        if can_attack(best_project):
            # Determine needed paint type
            target_info = sense_map_info(best_project)
            needed_mark = target_info.get_mark()
            use_secondary = (needed_mark == PaintType.ALLY_SECONDARY)
            attack(best_project, use_secondary)
            return True
        else:
            # Move towards it
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

def try_mark_structure(my_loc):
    # 1. Check for Unmarked Ruins (Tower)
    nearby_map_infos = sense_nearby_map_infos()
    closest_ruin = None
    min_dist = 999
    
    for info in nearby_map_infos:
        if info.has_ruin():
            # Check if occupied by friend
            loc = info.get_map_location()
            robot = sense_robot_at_location(loc)
            if robot and robot.get_team() == get_team(): continue
            
            # Check if already marked (Handled by try_paint_project, so we only care about UNMARKED here)
            if info.get_mark() != PaintType.EMPTY: continue
            
            dist = my_loc.distance_squared_to(loc)
            if dist < min_dist:
                min_dist = dist
                closest_ruin = info

    if closest_ruin:
        ruin_loc = closest_ruin.get_map_location()
        if my_loc.distance_squared_to(ruin_loc) <= 2:
            tower_type = UnitType.LEVEL_ONE_PAINT_TOWER
            if can_mark_tower_pattern(tower_type, ruin_loc):
                mark_tower_pattern(tower_type, ruin_loc)
                log("Marked Tower!")
                return True
        else:
            navigate_bounce(ruin_loc)
            return True

    # 2. Start SRP (If safe)
    # Simple check: Scan nearby 5x5 area
    start_srp_loc = None
    for dx in range(-2, 3):
        for dy in range(-2, 3):
            check_loc = my_loc.translate(dx, dy)
            if can_mark_resource_pattern(check_loc):
                start_srp_loc = check_loc
                break
        if start_srp_loc: break
        
    if start_srp_loc:
        mark_resource_pattern(start_srp_loc)
        log("Marked SRP!")
        return True
        
    return False

def try_paint_ground(my_loc):
    # Endgame Frenzy
    round_num = get_round_num()
    force = False
    
    if round_num > 1750:
        force = True
    elif random.random() < 0.10: # 10% chance to paint empty tiles while exploring
        force = True
        
    return smart_paint(my_loc, force_paint=force)

# --- UTILS ---

def smart_paint(my_loc, force_paint=False):
    if not can_attack(my_loc): return False
    
    # 1. Check self
    try:
        my_tile = sense_map_info(my_loc)
        if not my_tile.get_paint().is_ally():
            attack(my_loc)
            return True
    except: pass
        
    nearby_8 = [my_loc.translate(dx, dy) for dx in (-1,0,1) for dy in (-1,0,1) if not (dx==0 and dy==0)]
    random.shuffle(nearby_8) 
    
    for loc in nearby_8:
        if can_attack(loc): 
            try:
                tile = sense_map_info(loc)
                paint = tile.get_paint()
                if paint.is_ally():
                    continue
                priority = 0
                if paint.is_enemy():
                    priority = 2
                elif force_paint:
                    priority = 1
                if priority > 0:
                    attack(loc)
                    return True
            except: pass 
    return False

def run_mopper():
    # Priority: 1. Enemy Paint, 2. Empty Paint, 3. Move
    nearby = sense_nearby_map_infos()
    # Shuffle to not get stuck
    random.shuffle(nearby)
    
    # 1. Attack Enemy Paint
    for tile in nearby:
        if tile.get_paint().is_enemy() and can_attack(tile.get_map_location()):
             attack(tile.get_map_location())
             return

    # 2. Attack Empty Paint (Expand)
    for tile in nearby:
        if tile.get_paint() == PaintType.EMPTY and can_attack(tile.get_map_location()):
             attack(tile.get_map_location())
             return
             
    navigate_randomly()

def run_splasher():
    # Priority: 1. Enemy/Empty Paint (Area Effect), 2. Move
    my_loc = get_location()
    
    if can_attack(my_loc):
        # Scan 1-radius area (Splasher hits 9 tiles?)
        # Actually Splasher attack is special. Let's just try to paint if we are not surrounded by allies.
        # Simple heuristic: If standing on non-ally or near non-ally, attack.
        if smart_paint(my_loc, force_paint=True):
            return

    navigate_randomly()

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
