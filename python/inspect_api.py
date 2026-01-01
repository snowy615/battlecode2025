from battlecode25.stubs import *
import inspect

print("Message functions:")
for name, obj in list(locals().items()):
    if "message" in name and callable(obj):
        try:
            print(f"{name}: {inspect.signature(obj)}")
        except:
            print(f"{name}: (cannot inspect)")
