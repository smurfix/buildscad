import math

solids_count = 1
tolerance = 10

def work():
    result = Box(20, 20, 10, align=(Align.CENTER,) * 3)
    for angle_deg in [0, 90, 180, 270]:
        angle_rad = math.radians(angle_deg)
        x = 8 * math.cos(angle_rad)
        y = 8 * math.sin(angle_rad)
        result = result - Box(4, 4, 14, align=(Align.CENTER,) * 3).move(Location((x, y, 0)))
    return result
