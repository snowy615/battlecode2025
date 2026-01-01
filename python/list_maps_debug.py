
import battlecode25.maps
import os

print("Maps path:", battlecode25.maps.__path__)
for p in battlecode25.maps.__path__:
    print(f"Listing {p}:")
    try:
        print(os.listdir(p))
    except Exception as e:
        print(e)
