$fn=30;

// the original had 10:50, which takes ages
for (i = [10:13])
{
    angle = i*360/20;
    distance = i*10;
    r = i*2;
    rotate(angle, [1, 2, 3])
    translate([0, distance, 0])
    sphere(r = r);
}
