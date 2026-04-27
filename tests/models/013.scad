// Test that [0:90:270] produces exactly 4 iterations (step-based for loop)
// Boxes are subtracted from a box so the result is a single connected solid.
$fn=10;

difference() {
    cube([20, 20, 10], center=true);
    for (angle = [0:90:270]) {
        rotate([0, 0, angle])
        translate([8, 0, 0])
        cube([4, 4, 14], center=true);
    }
}
