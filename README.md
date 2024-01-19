# OpensCadQ

An interpreter for OpenSCAD that emits CadQuery workplanes.

## Rationale

Today's 3D programs can import STEP models, thus can deal with "real"
curves and solids instead of mesh approximations.

Unfortunately, the CGAL 3D package used by OpenSCAD is mesh-based and can't
deal with that.

On the other hand, OpenSCAD is reasonably common for creating parameterized
models algorithmically.


## Approach

This Python package interprets OpenSCAD code and builds a CadQuery
workplane. The result can be used just like any other workplane.


## Limitations

This is a proof of concept. A lot of methods and syntax support functions
are not implemented yet, though the grammar itself should be complete.

Variables whose name start with a '$' are usable. However, they cannot be
passed to functions as keywords. Instead, $-prefixed keywords get passed to
called functions in the environment so that functions implemented in Python
don't have to deal with them.

Corollary: Don't even think of creating a six-sided polygon by using
``circle(r=2, $fn=6``) with this code.

Speed could probably be improved; on the other hand, let's face it,
OpenSCAD's mesh rendering can be slow as molasses.

There is no (general) ``minkowski`` operator.

``undef`` is evaluated as ``None``.

# Variable handling

Unknown variables (i.e. those that are never assigned to) cause an error.
Unfilled parameters are still "undef", i.e.

	function xx(a,b) = b;
	echo(xx(1));

does emit "ECHO: undef".

## Value redefinition

OpenSCAD warns when redeclaring a variable: in effect, it re-orders
statements, which can have undesired side effects.

By contrast, in opensCadQ updating a variable will emit a warning but not
change the value.

## included files

Variables declared in include files can be overridden in the main code, as in OpenSCAD.
However, the 

## TODO

Implement a lot of functions.

Test working with 2D.

An option to generate a cadquery script instead of the actual objects would
be nice.
