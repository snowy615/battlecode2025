from battlecode25.stubs import UnitType

print("Checking Unit Costs:")
t = UnitType.LEVEL_ONE_PAINT_TOWER
print(f"Tower: {t}")
print(f"Dir: {dir(t)}")
# Guess attributes
try:
    print(f"money_cost: {t.money_cost}")
    print(f"paint_cost: {t.paint_cost}")
    print(f"chip_cost: {t.chip_cost}")
except:
    pass
