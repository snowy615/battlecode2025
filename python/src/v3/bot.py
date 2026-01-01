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
    
    # Economy Safety: Don't spend if we are poor!
    # Reserve some chips for Paint Towers (Expansion)
    # Defense Towers are luxury items.
    
    MIN_CHIPS_FOR_UNIT = 200 
    MIN_CHIPS_FOR_DEFENSE = 1000
    
    # If enemies are nearby, PANIC SPEND (ignore limits)
    under_threat = len(nearby_enemies) > 0
    
    if not under_threat:
        if money < MIN_CHIPS_FOR_UNIT:
            return # Save money
            
    # Ratios (Adjusted for Defense)
    prob_soldier = 0.8
    prob_mopper = 0.1
    prob_money = 0.05
    prob_defense = 0.0 
    
    if round_num > 400:
        prob_soldier = 0.65 
        prob_mopper = 0.2
        prob_money = 0.0
        prob_defense = 0.10 
    
    spawn_dir = directions[random.randint(0, len(directions) - 1)]
    spawn_loc = my_location.add(spawn_dir)
    
    # Check Special Towers
    roll = random.random()
    
    # Defense Tower (Mid/Late Game) - Only if rich!
    if roll < prob_defense and round_num > 400:
        if money > MIN_CHIPS_FOR_DEFENSE or under_threat:
             if can_build_robot(UnitType.LEVEL_ONE_DEFENSE_TOWER, spawn_loc):
                build_robot(UnitType.LEVEL_ONE_DEFENSE_TOWER, spawn_loc)
                return

    # Money Tower (Early Game)
    if roll < prob_money and round_num < 200:
        if can_build_robot(UnitType.LEVEL_ONE_MONEY_TOWER, spawn_loc):
             build_robot(UnitType.LEVEL_ONE_MONEY_TOWER, spawn_loc)
             return

    # Standard Units (Re-roll for standard distribution)
    roll = random.random()
    if roll < prob_soldier:
        if can_build_robot(UnitType.SOLDIER, spawn_loc):
            build_robot(UnitType.SOLDIER, spawn_loc)
    elif roll < prob_soldier + prob_mopper:
        if can_build_robot(UnitType.MOPPER, spawn_loc):
            build_robot(UnitType.MOPPER, spawn_loc)
    else:
        if can_build_robot(UnitType.SPLASHER, spawn_loc):
            build_robot(UnitType.SPLASHER, spawn_loc)

# --- SOLDIER ---
def run_soldier():
    my_loc = get_location()

    # 1. Combat & Kiting
    nearby_enemies = sense_nearby_robots(team=get_team().opponent())
    if nearby_enemies:
        target = nearby_enemies[0]
        dist_sq = my_loc.distance_squared_to(target.get_location())
        
        # Kiting Logic (Refined)
        # Optimal Range: 13-20 (Attack Range is 20)
        # If too close (<10), retreat.
        # If in effective range (10-20), stand and fight.
        # If too far (>20), approach.
        
        # Priority: Attack if possible
        has_attacked = False
        if can_attack(target.get_location()):
            attack(target.get_location())
            has_attacked = True
        
        # Movement logic (independent of attack if cooldowns separate)
        # Assuming move and attack share some cooldown resource (paint/action)?
        # If we attacked, can we move? 
        # Check `can_move` handles cooldowns.
        
        should_retreat = (dist_sq < 10) or (get_health() < 20) # Retreat if low hp
        
        if should_retreat:
             # Retreat towards nearest friendly tower if exists, else away from enemy
             dir_away = target.get_location().direction_to(my_loc)
             if can_move(dir_away):
                 move(dir_away)
             else:
                 # Try side step
                 navigate_bounce(my_loc.add(dir_away))
        elif dist_sq > 20:
             # Pursue
             navigate_bounce(target.get_location())
        else:
             # In sweet spot. Hold ground or jiggle?
             # If we haven't attacked (e.g. out of range slightly?), move closer
             if not has_attacked and dist_sq > 16:
                 navigate_bounce(target.get_location())
        
        return # Combat focus

    # 2. Economy Projects
    nearby_map_infos = sense_nearby_map_infos()
    
    if can_complete_resource_pattern(my_loc):
        complete_resource_pattern(my_loc)
        return
    for d in directions:
        if can_complete_resource_pattern(my_loc.add(d)):
             complete_resource_pattern(my_loc.add(d))
             return

    srp_project_loc = None
    for tile in nearby_map_infos:
        if tile.get_map_location().distance_squared_to(my_loc) <= 8:
            mark = tile.get_mark()
            paint = tile.get_paint()
            if mark != PaintType.EMPTY and mark != paint:
                srp_project_loc = tile.get_map_location()
                break
    
    if srp_project_loc:
        if can_attack(srp_project_loc):
             target_tile = sense_map_info(srp_project_loc)
             use_secondary = (target_tile.get_mark() == PaintType.ALLY_SECONDARY)
             attack(srp_project_loc, use_secondary)
             return
        else:
            navigate_bounce(srp_project_loc)
            return

    # 3. Ruins
    closest_ruin = None
    min_dist = 99999
    
    for info in nearby_map_infos:
        if info.has_ruin():
            loc = info.get_map_location()
            robot_on_ruin = sense_robot_at_location(loc)
            if robot_on_ruin and robot_on_ruin.get_team() == get_team() and robot_on_ruin.get_type().is_tower_type():
                continue
                
            dist = my_loc.distance_squared_to(loc)
            if dist < min_dist:
                min_dist = dist
                closest_ruin = info
            
    if closest_ruin:
        ruin_loc = closest_ruin.get_map_location()
        dist = min_dist

        if dist <= 2: 
            tower_type = UnitType.LEVEL_ONE_PAINT_TOWER
            # Late game Defense Towers are built by run_tower spawning, 
            # here soldiers build base Paint/Money towers on ruins?
            # Or should soldiers build Defense Towers?
            # Soldiers build the tower initially. 
            # Let's say if we are consistently losing, we build Defense.
            # For now, keep Paint Tower as default expansion. 
            # Defense towers are upgraded? No, distinct types.
            # Let's add a small chance for Soldier to build Defense Tower if deep in game?
            # Or stick to Paint Tower for expansion (Radius is key).
            
            if can_mark_tower_pattern(tower_type, ruin_loc):
                mark_tower_pattern(tower_type, ruin_loc)
            if can_complete_tower_pattern(tower_type, ruin_loc):
                complete_tower_pattern(tower_type, ruin_loc)
                return
        else:
            navigate_bounce(ruin_loc)
            return

    # 4. New SRP
    best_srp_loc = None
    for dx in range(-2, 3):
        for dy in range(-2, 3):
            check_loc = my_loc.translate(dx, dy)
            if can_mark_resource_pattern(check_loc):
                best_srp_loc = check_loc
                break
        if best_srp_loc: break
        
    if best_srp_loc:
        mark_resource_pattern(best_srp_loc)
        return

    # 5. Paint Ground
    cur_tile = sense_map_info(my_loc)
    if not cur_tile.get_paint().is_ally():
        if can_attack(my_loc):
            attack(my_loc)
            return

    # 6. Explore
    navigate_randomly()

def run_mopper():
    nearby = sense_nearby_map_infos()
    for tile in nearby:
        if tile.get_paint().is_enemy() and can_attack(tile.get_map_location()):
             attack(tile.get_map_location())
             return
    navigate_randomly()

def run_splasher():
    navigate_randomly()

# --- Helpers ---

def navigate_bounce(target_loc):
    """
    Stateless Tangent Bug / Bounce Logic
    Try direct, then "bounce" around obstacles by checking side angles.
    """
    if not target_loc: return
    my_loc = get_location()
    
    if my_loc.distance_squared_to(target_loc) <= 2:
        return

    d_desired = my_loc.direction_to(target_loc)
    
    if can_move(d_desired):
        move(d_desired)
        return
        
    # Obstacle encountered!
    # Try angles: +/- 45, +/- 90, +/- 135
    
    # Left side scan
    d_left = d_desired
    for _ in range(3):
        d_left = d_left.rotate_left()
        if can_move(d_left):
            move(d_left)
            return
            
    # Right side scan
    d_right = d_desired
    for _ in range(3):
        d_right = d_right.rotate_right()
        if can_move(d_right):
            move(d_right)
            return
            
    # If completely blocked, do nothing (wait) or random?
    # Maybe random to unstuck
    navigate_randomly()

def navigate_randomly():
    if random.random() < 0.2: return
    d = directions[random.randint(0, 7)]
    if can_move(d): move(d)
