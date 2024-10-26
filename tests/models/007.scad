$fn=20;

module bar(h) { cylinder(h=h,r=1,center=true); }

module work() {
   bar(4);
   rotate([0,90,0]) { bar(6); }
   rotate([90,0,0]) bar(8);
}

work();
