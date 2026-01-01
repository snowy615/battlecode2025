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
    """
    Main entry point for every robot's turn.
    """
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

def run_tower():
    # 1. Attack enemies if possible
    nearby_enemies = sense_nearby_robots(team=get_team().opponent())
    if len(nearby_enemies) > 0:
        target = nearby_enemies[0]
        if can_attack(target.get_location()):
            attack(target.get_location())
            return

    # 2. Spawn units
    # Dynamic Ratios based on Game Phase
    round_num = get_round_num()
    
    # Probabilities
    # Default (Early Game)
    prob_soldier = 0.8
    prob_mopper = 0.1
    # Splasher = 0.1
    
    if round_num > 400:
        # Mid/Late Game
        # FIX: Don't drop soldiers too low. We need them for map control (score).
        prob_soldier = 0.7
        prob_mopper = 0.2
        # Splasher = 0.1
        
    spawn_dir = directions[random.randint(0, len(directions) - 1)]
    spawn_loc = get_location().add(spawn_dir)
    
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

def run_soldier():
    my_loc = get_location()
    
    # 0. Process Communication (Disabled)
    
    # 1. Attack visible enemies
    nearby_enemies = sense_nearby_robots(team=get_team().opponent())
    if nearby_enemies:
        target = nearby_enemies[0]
        if can_attack(target.get_location()):
            attack(target.get_location())
            return
        else:
            navigate_to(target.get_location())
            return
    
    # 2. Economy: Resource Patterns (SRP)
    # FIX: Prioritize completing existing patterns before starting new ones.
    nearby_map_infos = sense_nearby_map_infos()
    
    # Check if we are near a pending SRP (marked but not complete)
    # We look for tiles with markers that need painting.
    # Actually, let's scan for a valid SRP center that is MARKED.
    # We can't directly "sense SRPs", but we can sense markers.
    
    # Simple Logic: If we see a spot allowing `complete_resource_pattern`, we do it.
    if can_complete_resource_pattern(my_loc):
        complete_resource_pattern(my_loc)
        log("Completed SRP!")
        return
        
    # Check neighbors for completion
    for dir in directions:
        check_loc = my_loc.add(dir)
        if can_complete_resource_pattern(check_loc):
            complete_resource_pattern(check_loc)
            log("Completed SRP nearby!")
            return

    # Scan for opportunities to paint SRPs
    # If we find a tile with a marker, treat it as a high priority "Project"
    srp_project_loc = None
    for tile in nearby_map_infos:
        if tile.get_map_location().distance_squared_to(my_loc) <= 8:
            mark = tile.get_mark()
            paint = tile.get_paint()
            # If marked and not painted, it's a project (SRP or Tower)
            if mark != PaintType.EMPTY and mark != paint:
                # Check if it's an SRP marker? 
                # Diff between SRP and Tower marker is subtle (just colors).
                # But we should help build it anyway.
                srp_project_loc = tile.get_map_location()
                break
    
    if srp_project_loc:
        # We found a project! Contribute to it.
        if can_attack(srp_project_loc):
             # Determine needed color
             target_tile = sense_map_info(srp_project_loc)
             use_secondary = (target_tile.get_mark() == PaintType.ALLY_SECONDARY)
             attack(srp_project_loc, use_secondary)
             return
        else:
            navigate_to(srp_project_loc)
            return

    # If no active projects, consider Starting a new SRP
    # Only if we aren't near a ruin we should be building?
    # Ruins are higher priority than new SRPs usually. 
    # Let's move this AFTER ruin logic.
    pass # Fall through
    
    # 3. Building Towers on Ruins
    closest_ruin = None
    min_dist = 99999
    width = get_map_width()
    
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
        
        # Broadcast (Disabled)

        if dist <= 2: 
            tower_type = UnitType.LEVEL_ONE_PAINT_TOWER
            
            if can_mark_tower_pattern(tower_type, ruin_loc):
                mark_tower_pattern(tower_type, ruin_loc)
                
            if can_complete_tower_pattern(tower_type, ruin_loc):
                complete_tower_pattern(tower_type, ruin_loc)
                log("Completed Tower!")
                return
            
            # Use generic painter loop below
            pass

        else:
            navigate_to(ruin_loc)
            return

    # 3b. Start new SRP (If no Ruin and no Active Project)
    # Only if safe?
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
        log("Started new SRP at " + str(best_srp_loc))
        return

    # 4. Generic Painting (Projects found above or generic expansion)
    # We already handled "Project" painting in 2.
    # So this is just fallback for things we missed or expansion.
    
    # 5. Paint the ground (Expansion)
    cur_tile = sense_map_info(my_loc)
    cur_paint = cur_tile.get_paint()
    if not cur_paint.is_ally():
        if can_attack(my_loc):
            attack(my_loc)
            return

    # 6. Explore
    rand_dir = directions[random.randint(0, 7)]
    if can_move(rand_dir):
        move(rand_dir)

def run_mopper():
    # Moppers remove enemy paint efficiently
    nearby = sense_nearby_map_infos()
    
    # 1. Attack/Mop enemy paint
    for tile in nearby:
        if tile.get_paint().is_enemy() and can_attack(tile.get_map_location()):
             attack(tile.get_map_location()) # Mopper attack removes paint
             return
             
    # 2. Move Randomly
    navigate_randomly()

def run_splasher():
    # Splashers have AoE attack
    # Move towards enemies or enemy paint
    my_loc = get_location()
    
    # 1. Attack clumps of enemies or enemy paint
    nearby_enemies = sense_nearby_robots(team=get_team().opponent())
    if nearby_enemies:
        target = nearby_enemies[0]
        if can_attack(target.get_location()):
             attack(target.get_location())
             return
        else:
            navigate_to(target.get_location())
            return
            
    # 2. Basic Random Movement
    navigate_randomly()

# --- Helpers ---

def navigate_to(target_loc):
    """
    Simple greedy pathfinding
    """
    if not target_loc: return
    
    my_loc = get_location()
    direction = my_loc.direction_to(target_loc)
    
    if can_move(direction):
        move(direction)
    else:
        # Try adjacent dirs
        left = direction.rotate_left()
        right = direction.rotate_right()
        if can_move(left):
            move(left)
        elif can_move(right):
            move(right)

def navigate_randomly():
    if random.random() < 0.2:
        return # Idle sometimes
    d = directions[random.randint(0, 7)]
    if can_move(d):
        move(d)
