# buildSCAD

An interpreter for OpenSCAD that emits OCC objects, wrapped with build123d.


## Rationale

Today's 3D programs can import STEP models, thus can deal with "real"
curves and solids instead of mesh approximations.

Unfortunately, the CGAL 3D package used by OpenSCAD is mesh-based. Owch.

On the other hand, OpenSCAD is somewhat widely used for creating
parameterized models algorithmically. Sites like Thingiverse or Printables
contain quite a few models built with it.

The code in this package interprets OpenSCAD code and returns "real" 3D models.


## Approach

The OpenSCAD code is parsed into a syntax tree and interpreted on the fly
when a "module" (in OpenSCAD terms) is called.

The result is an OCC Solid (or sketch if 2D), wrapped with build123d.
It can be used just like any other OCCT object.


### Functional replacements

If a module cannot be implemented in build123d/OCC, most likely because it
uses ``hull`` or ``minkowsky``, the most expedient fix is to write a
replacement in Python.

Usage: simply call `set_mod(NAME, pymod)` on the parse result.

The same is possible with functions, and even the values of variables.
Because BuildSCAD evaluates all expressions at runtime, this works
seamlessly.

To read global variables, Python code can access the current
environment via the contextvar ``buildscad.cur_env``.


## Limitations

This tool started off as a proof of concept. A few OpenSCAD built-ins and
some rarely-used syntax rules are not implemented yet, though the grammar
itself should be complete.

Variables whose name start with a '$' are usable. However, they cannot be
passed to functions as keywords. Instead, $-prefixed keywords get passed to
called functions in the environment so that functions implemented in Python
don't have to deal with them.

Creating a six-sided polygon by calling ``circle(r=2, $fn=6)`` is not
supported.

BuildSCAD is entirely non-optimized. That's not a problem in practice
because most time is spent inside OCCT anyway.

The ``minkowski`` and ``hull`` operators don't exist in OCCT.
Implementing them is *way* out of scope for this project.

``undef`` is evaluated as ``None``.


## Differences to OpenSCAD

### Evaluation Order

Our parser delays evaluation of variables until they're needed.

In other words, this …

::
	bar = foo(b);
	function foo(x) = x;
        a = 5;
        b = 2 \* a;

… works just fine; `b` will change if you override `a`.


### Variable handling

Unknown variables (i.e. those that are never assigned to) cause an error.
As in OpenSCAD, unfilled parameters are `undef`/`None`, i.e.

	function xx(a,b) = b;
	echo(xx(1));

emits "ECHO: None".


### Included Files

Variables declared in include files can be overridden in the main code, as in OpenSCAD.
However, values from included files don't filter back to the main code.

### Invalid Values

OpenSCAD tends to return `undef` whenever it doesn't understand something,
which typically results in any numer of follow-up warnings.

We don't do that. Errors raise exceptions.


## Testing

The subdirectory ``tests/models`` includes various OpenSCAD files, with
accompanying Python code.

The models in these files are built in three ways:

* directly by OpenSCAD
* by emulating OpenSCAD
* by Python code (optional)

The test builder calls the ``work`` function (Python) / module (OpenSCAD).
If that doesn't exist, top-level objects (OpenSCAD) / variables (Python) are used.

The following Python variables are recognized:

* tolerance

  The maximum difference (volume) between the various models. The default
  is 0.001 but anything that depends on OpenSCAD's ``$fn`` probably
  requires looser constraints.

* volume

  The volume (in mm³) that the model is supposed to have.

* skip

  Skip this test when running ``pytest``. Used when the test takes way too
  long or crashes OCCT (yes it happens …).

* no\_add

  When set to `True`, do not add the various volumes. This is a workaround
  for an OCCT bug which causes an endless loop.

  Setting this flag causes the testcase to only compare volumes and bounding
  boxes, which is not as accurate.

* trace

  Log (some) calls to build123. Seee below.


If the Python part of the test only contains constants, it must declare
`work=None`. Otherwise the test code assumes that you wrote e.g.
``Sphere(42)`` without assigning the result to anything, and thus refuses
to accept the testcase.

If you want to test the result of a function call against OpenSCAD, the
best way is to create a `Box(result,1,1)` object.


### Viewing tests

``examples/test_viewer.py`` can be opened with CQ-Editor to compare test
results visually.

### Test Traces

If the testcase sets ``tracing=True``, the actual `build123d` calls will be
logged and the STL file from OpenSCAD will not be deleted.

The trace output is executable Python code so that you can find prolems
more easily when a test fails, or if/when OCCT misbehaves.

Trace support is still somewhat incomplete.


## TODO

Improve error reporting. Seriously.

To fix:
* linear\_extrude with scaling
* linear\_extrude with scaling and twist
* use/include from a library (via envvar OPENSCADPATH)

Implement missing functions.

Test working with 2D.

An option to generate an (algebraic) build123d script that mirrors the
OpenSCAD code structure would be nice.
