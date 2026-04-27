// Test for loops with step values 0, 90, 180, 270
// Spheres are large enough (r=4) relative to circle radius (5) that
// adjacent ones overlap, forming a single connected solid.
$fn=10;

for (angle = [0:90:270]) {
    rotate([0, 0, angle])
    translate([5, 0, 0])
    sphere(r = 4);
}
