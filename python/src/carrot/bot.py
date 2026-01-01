import random

from battlecode25.stubs import *

# This is an example bot written by the developers!
# Use this to help write your own code, or run it against your bot to see how well you can do!


# Globals
turn_count = 0
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
    MUST be defined for robot to run
    This function will be called at the beginning of every turn and should contain the bulk of your robot commands
    """
    global turn_count
    turn_count += 1

    if get_type() == UnitType.SOLDIER:
        run_soldier()
    elif get_type() == UnitType.MOPPER:
        run_mopper()
    elif get_type() == UnitType.SPLASHER:
        run_splasher()
    elif get_type().is_tower_type():
        run_tower()
    else:
        pass  # Other robot types?


def run_tower():
    nearby_enemies = sense_nearby_robots(team=get_team().opponent())
    nearby_allies = sense_nearby_robots(team=get_team())

    # Count nearby allies to balance production.
    soldier_count = 0
    mopper_count = 0
    splasher_count = 0
    for ally in nearby_allies:
        ally_type = ally.get_type()
        if ally_type == UnitType.SOLDIER:
            soldier_count = soldier_count + 1
        elif ally_type == UnitType.MOPPER:
            mopper_count = mopper_count + 1
        elif ally_type == UnitType.SPLASHER:
            splasher_count = splasher_count + 1

    # Decide what to spawn.
    spawn_type = UnitType.SOLDIER
    if len(nearby_enemies) > 0:
        # Close defense: prefer Mopper, otherwise Soldier.
        spawn_type = UnitType.MOPPER
    else:
        # Balanced growth: keep soldiers highest, splashers behind.
        if soldier_count < mopper_count + 1:
            spawn_type = UnitType.SOLDIER
        elif splasher_count * 2 < soldier_count:
            spawn_type = UnitType.SPLASHER
        else:
            spawn_type = UnitType.SOLDIER

    # Try to build in a valid direction.
    build_dirs = list(directions)
    random.shuffle(build_dirs)
    for dir in build_dirs:
        next_loc = get_location().add(dir)
        if can_build_robot(spawn_type, next_loc):
            build_robot(spawn_type, next_loc)
            log("BUILT A " + str(spawn_type))
            break

    # Read incoming messages
    messages = read_messages()
    for m in messages:
        log(f"Tower received message: '#{m.get_sender_id()}: {m.get_bytes()}'")

    # TODO: can we attack other bots?


def run_soldier():
    # 0. Combat: attack nearby enemies first, or move toward them.
    nearby_enemies = sense_nearby_robots(team=get_team().opponent())
    if len(nearby_enemies) > 0:
        closest = nearby_enemies[0]
        closest_dist = get_location().distance_squared_to(closest.get_location())
        for enemy in nearby_enemies:
            dist = get_location().distance_squared_to(enemy.get_location())
            if dist < closest_dist:
                closest = enemy
                closest_dist = dist
        if can_attack(closest.get_location()):
            attack(closest.get_location())
            return
        else:
            dir = get_location().direction_to(closest.get_location())
            if can_move(dir):
                move(dir)
                return

    # Sense information about all visible nearby tiles.
    nearby_tiles = sense_nearby_map_infos()

    # Search for the nearest nearby ruin to complete.
    cur_ruin = None
    cur_ruin_dist = None
    for tile in nearby_tiles:
        if tile.has_ruin():
            dist = get_location().distance_squared_to(tile.get_map_location())
            if cur_ruin is None or dist < cur_ruin_dist:
                cur_ruin = tile
                cur_ruin_dist = dist

    if cur_ruin is not None:
        target_loc = cur_ruin.get_map_location()
        dir = get_location().direction_to(target_loc)
        if can_move(dir):
            move(dir)

        # Mark the pattern we need to draw to build a tower here if we haven't already.
        should_mark = cur_ruin.get_map_location().subtract(dir)
        if sense_map_info(should_mark).get_mark() == PaintType.EMPTY and can_mark_tower_pattern(UnitType.LEVEL_ONE_PAINT_TOWER, target_loc):
            mark_tower_pattern(UnitType.LEVEL_ONE_PAINT_TOWER, target_loc)
            log("Trying to build a tower at " + str(target_loc))

        # Fill in any spots in the pattern with the appropriate paint.
        for pattern_tile in sense_nearby_map_infos(target_loc, 8):
            if pattern_tile.get_mark() != pattern_tile.get_paint() and pattern_tile.get_mark() != PaintType.EMPTY:
                use_secondary = pattern_tile.get_mark() == PaintType.ALLY_SECONDARY
                if can_attack(pattern_tile.get_map_location()):
                    attack(pattern_tile.get_map_location(), use_secondary)

        # Complete the ruin if we can.
        if can_complete_tower_pattern(UnitType.LEVEL_ONE_PAINT_TOWER, target_loc):
            complete_tower_pattern(UnitType.LEVEL_ONE_PAINT_TOWER, target_loc)
            set_timeline_marker("Tower built", 0, 255, 0)
            log("Built a tower at " + str(target_loc) + "!")

    # Move and attack randomly if no objective.
    dir = directions[random.randint(0, len(directions) - 1)]
    next_loc = get_location().add(dir)
    if can_move(dir):
        move(dir)

    # Try to paint beneath us as we walk to avoid paint penalties.
    # Avoiding wasting paint by re-painting our own tiles.
    current_tile = sense_map_info(get_location())
    if not current_tile.get_paint().is_ally() and can_attack(get_location()):
        attack(get_location())


def run_mopper():
    # Move and attack randomly.
    dir = directions[random.randint(0, len(directions) - 1)]
    next_loc = get_location().add(dir)
    if can_move(dir):
        move(dir)
    if can_mop_swing(dir):
        mop_swing(dir)
        log("Mop Swing! Booyah!");
    elif can_attack(next_loc):
        attack(next_loc)

    # We can also move our code into different methods or classes to better organize it!
    update_enemy_robots()


def run_splasher():
    # Prefer attacking clusters, otherwise paint/expand.
    nearby_enemies = sense_nearby_robots(team=get_team().opponent())
    if len(nearby_enemies) >= 2:
        best_loc = None
        best_hits = 0
        for enemy in nearby_enemies:
            center = enemy.get_location()
            hits = 0
            for other in nearby_enemies:
                if other.get_location().distance_squared_to(center) <= 2:
                    hits = hits + 1
            if hits > best_hits and can_attack(center):
                best_hits = hits
                best_loc = center
        if best_loc is not None and best_hits >= 2:
            attack(best_loc)
            return

    # Single target attack if possible.
    if len(nearby_enemies) > 0:
        target = nearby_enemies[0].get_location()
        if can_attack(target):
            attack(target)
            return

    # Paint beneath us if needed.
    my_loc = get_location()
    current_tile = sense_map_info(my_loc)
    if not current_tile.get_paint().is_ally() and can_attack(my_loc):
        attack(my_loc)
        return

    # Paint adjacent tiles, preferring enemy paint.
    best_paint_target = None
    for dir in directions:
        target_loc = my_loc.add(dir)
        if can_attack(target_loc):
            paint = sense_map_info(target_loc).get_paint()
            if paint.is_enemy():
                best_paint_target = target_loc
                break
            if paint == PaintType.EMPTY and best_paint_target is None:
                best_paint_target = target_loc

    if best_paint_target is not None:
        attack(best_paint_target)
        return

    # Move to expand territory.
    dir = directions[random.randint(0, len(directions) - 1)]
    if can_move(dir):
        move(dir)

def update_enemy_robots():
    # Sensing methods can be passed in a radius of -1 to automatically 
    # use the largest possible value.
    enemy_robots = sense_nearby_robots(team=get_team().opponent())
    if len(enemy_robots) == 0:
        return

    set_indicator_string("There are nearby enemy robots! Scary!");

    # Save an array of locations with enemy robots in them for possible future use.
    enemy_locations = [None] * len(enemy_robots)
    for i in range(len(enemy_robots)):
        enemy_locations[i] = enemy_robots[i].get_location()

    # Occasionally try to tell nearby allies how many enemy robots we see.
    ally_robots = sense_nearby_robots(team=get_team())
    if get_round_num() % 20 == 0:
        for ally in ally_robots:
            if can_send_message(ally.location):
                send_message(ally.location, len(enemy_robots))
