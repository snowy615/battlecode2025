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
    prob_soldier = 0.8
    prob_mopper = 0.1
    # Splasher/Rest = Remainder
    
    if round_num > 400:
        # Mid/Late Game: Need more cleaning and AoE
        prob_soldier = 0.5
        prob_mopper = 0.3
        # Splasher = 0.2
        
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
    
    # 0. Process Communication to find claimed ruins
    claimed_ruins = set()
    # messages = read_messages(get_round_num())
    # for m in messages:
    #     val = m.get_bytes() 
    #     if isinstance(val, int):
    #         claimed_ruins.add(val)

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
    
    # 2. Economy: Check for Resource Pattern spots (SRP)
    # Check 8 neighbors + center for potential SRP center
    # This is expensive? No, 9 checks.
    nearby_map_infos = sense_nearby_map_infos()
    width = get_map_width()
    
    best_srp_loc = None
    for dx in range(-2, 3):
        for dy in range(-2, 3):
            # We are scanning for a place to put the CENTER of the SRP
            check_loc = my_loc.translate(dx, dy)
            if can_mark_resource_pattern(check_loc):
                best_srp_loc = check_loc
                break
        if best_srp_loc: break
        
    if best_srp_loc:
        mark_resource_pattern(best_srp_loc)
        log("Marked SRP at " + str(best_srp_loc))
        return

    # Check if we are working on an SRP (painting it)
    # SRP marking is global? Or marker based?
    # can_complete_resource_pattern(loc) checks if it's ready
    # We need to paint if marked.
    # Scan nearby tiles for markers consistent with SRP?
    # The API might simplify this. If `mark_resource_pattern` places markers, 
    # then subsequent turns we just see markers and paint.
    # So we just need generic "Paint Markers" logic, which we have for towers.
    # It should be covered by generic paint logic below or specific painting loop.

    # 3. Building Towers on Ruins
    closest_ruin = None
    min_dist = 99999
    
    for info in nearby_map_infos:
        if info.has_ruin():
            loc = info.get_map_location()
            
            # Check if claimed by message
            loc_id = loc.x + loc.y * width
            if loc_id in claimed_ruins:
                continue
                
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
        
        # Broadcast claim
        # Scream it to the world!
        loc_id = ruin_loc.x + ruin_loc.y * width
        # if can_broadcast_message():
        #     broadcast_message(loc_id)
        
        if dist <= 2: 
            tower_type = UnitType.LEVEL_ONE_PAINT_TOWER
            
            if can_mark_tower_pattern(tower_type, ruin_loc):
                mark_tower_pattern(tower_type, ruin_loc)
                
            if can_complete_tower_pattern(tower_type, ruin_loc):
                complete_tower_pattern(tower_type, ruin_loc)
                log("Completed Tower!")
                return
            
            # Paint the pattern (Generic for Tower or SRP)
            # Both leave markers.
            painted_something = False
            for tile in nearby_map_infos:
                if tile.get_map_location().distance_squared_to(ruin_loc) <= 8:
                    mark = tile.get_mark()
                    paint = tile.get_paint()
                    if mark != PaintType.EMPTY and mark != paint:
                        use_secondary = (mark == PaintType.ALLY_SECONDARY)
                        if can_attack(tile.get_map_location()):
                            attack(tile.get_map_location(), use_secondary)
                            painted_something = True
                            break 
            
            if painted_something:
                return

        else:
            navigate_to(ruin_loc)
            return

    # 4. Generic Painting (Expansion + Completing patterns found on ground)
    # Check current tile and neighbors for Markers that need painting
    # This covers SRPs marked by us or others
    for tile in nearby_map_infos:
         # Only check very close tiles we can paint
         if tile.get_map_location().distance_squared_to(my_loc) <= 2:
             mark = tile.get_mark()
             paint = tile.get_paint()
             if mark != PaintType.EMPTY and mark != paint:
                  use_secondary = (mark == PaintType.ALLY_SECONDARY)
                  if can_attack(tile.get_map_location()):
                        attack(tile.get_map_location(), use_secondary)
                        return

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
