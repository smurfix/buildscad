import sys
from build123d import *

if "/src/openscadq/src" not in sys.path:
    sys.path.insert(0,"/src/openscadq/src")
if "/src/openscadq" not in sys.path:
    sys.path.insert(0,"/src/openscadq")

import openscadq.main as scq
from openscadq._test import testcase
# from build123d import *

try:
    show_object
except NameError:
    def show_object(*a):
        print(a)

def tc(i):
    a,b = testcase(i)
    show_object(a,f"OpenSCAD {i}")
    show_object(b,f"Reference {i}")


tc(1)

if False:
    pr("Cyl","""
    cylinder(1,2, center=true);
    """)

    pr("Cyl2","""
    cylinder(1,2,1);
    """)
    pr("Cylhole","""
    difference() {
        cylinder(2,2);
        cylinder(2,1);
    }
    """)

    pr("SQ","""
       square(3);
       """
       )
    pr("LEx","""
       linear_extrude(2, twist=30 ) square([1,2]);
    """)

    pr("scale", """
       scale([1,2,3]) cube(1);
    """)

    pr("poly", """
       linear_extrude(0.1) 
       polygon([[2,2],[3,3],[3,5],[2,5]]);
    """)

    pr("rot", """
       rotate_extrude(-45) 
       polygon([[2,2],[3,3],[3,5],[2,5]]);
    """)
    
    pr("bx","""
       union() {
           cylinder(10,1, center=true);
           rotate([60,0,0]) cylinder(10,1, center=true);
           rotate([0,30,0]) cylinder(10,1, center=true);
       }
    """)

    pr("rot", """
       text("Helga!",font="Courier",size=40, halign="right");
    """)

    pr("pyr","""
       x=180; h=100;
       
    polyhedron(
      points=[ [x,x,0],[x,-x,0],[-x,-x,0],[-x,x,0],
               [0,0,h]  ],                                 
      faces=[ [0,1,4],[1,2,4],[2,3,4],[3,0,4],              
              [1,0,3],[2,1,3] ]                         
    );
    """)

if False:
    res = scq.process("/d/src/3d/Schublade/Schublade.scad", preload=["examples/smooth_cubes.py"])
    show_object(res[0].wrapped,"Schub")