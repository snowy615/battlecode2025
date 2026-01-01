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
    # Towers have AoE or Single target. 
    # Let's try to attack any enemy in range.
    nearby_enemies = sense_nearby_robots(team=get_team().opponent())
    if len(nearby_enemies) > 0:
        # Simple targeting: closest enemy
        target = nearby_enemies[0]
        if can_attack(target.get_location()):
            attack(target.get_location())
            return # Action used

    # 2. Spawn units
    # Prioritize SOLDIERs for expansion, occasionally MOPPERs
    
    # Try all directions
    spawn_dir = directions[random.randint(0, len(directions) - 1)]
    spawn_loc = get_location().add(spawn_dir)
    
    # Simple ratio: Mostly soldiers, but occasionally a splasher or mopper
    roll = random.random()
    if roll < 0.7:
        if can_build_robot(UnitType.SOLDIER, spawn_loc):
            build_robot(UnitType.SOLDIER, spawn_loc)
    elif roll < 0.9:
        if can_build_robot(UnitType.MOPPER, spawn_loc):
            build_robot(UnitType.MOPPER, spawn_loc)
    else:
        if can_build_robot(UnitType.SPLASHER, spawn_loc):
            build_robot(UnitType.SPLASHER, spawn_loc)

def run_soldier():
    my_loc = get_location()
    
    # Priority 1: Attack visible enemies
    nearby_enemies = sense_nearby_robots(team=get_team().opponent())
    if nearby_enemies:
        target = nearby_enemies[0]
        if can_attack(target.get_location()):
            attack(target.get_location())
            return
        else:
            navigate_to(target.get_location())
            return

    # Priority 2: Building Towers on Ruins
    nearby_map_infos = sense_nearby_map_infos()
    closest_ruin = None
    min_dist = 99999
    
    for info in nearby_map_infos:
        if info.has_ruin():
            # Only go to ruins that don't have our towers
            # We can't easily check if it's OUR tower without sensing the robot on it
            # But has_ruin() is true for bare ruins. 
            # If there is a robot there, we can check sense_robot_at_location
            loc = info.get_map_location()
            robot_on_ruin = sense_robot_at_location(loc)
            
            # If no robot, or enemy robot (we can attack it later), go there
            # If friendly tower, skip
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
            # We are close enough to work on it
            # Using Paint Tower for simplicity
            tower_type = UnitType.LEVEL_ONE_PAINT_TOWER
            
            if can_mark_tower_pattern(tower_type, ruin_loc):
                mark_tower_pattern(tower_type, ruin_loc)
                
            if can_complete_tower_pattern(tower_type, ruin_loc):
                complete_tower_pattern(tower_type, ruin_loc)
                log("Completed Tower!")
                return
            
            # Paint the pattern
            painted_something = False
            for tile in nearby_map_infos:
                if tile.get_map_location().distance_squared_to(ruin_loc) <= 8:
                    mark = tile.get_mark()
                    paint = tile.get_paint()
                    if mark != PaintType.EMPTY and mark != paint:
                        # Needs painting
                        if can_attack(tile.get_map_location()):
                            use_secondary = (mark == PaintType.ALLY_SECONDARY)
                            attack(tile.get_map_location(), use_secondary)
                            painted_something = True
                            break 
            
            if painted_something:
                return

        else:
            navigate_to(ruin_loc)
            return

    # Priority 3: Paint the ground (Expansion)
    cur_tile = sense_map_info(my_loc)
    cur_paint = cur_tile.get_paint()
    
    if not cur_paint.is_ally():
        if can_attack(my_loc):
            attack(my_loc)
            return

    # Priority 4: Explore / Move Randomly
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
