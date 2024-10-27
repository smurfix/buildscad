# buildSCAD

An interpreter for OpenSCAD that emits OCC objects, wrapped with build123d.


## Rationale

Today's 3D programs can import STEP models, thus can deal with "real"
curves and solids instead of mesh approximations.

Unfortunately, the CGAL 3D package used by OpenSCAD is mesh-based. Owch.

On the other hand, OpenSCAD is somewhat widely used for creating
parameterized models algorithmically. Sites like Thingiverse or Printables
contain quite a few models built with it.

This package translates OpenSCAD to "real" 3D models.


## Approach

The OpenSCAD code is parsed into a syntax tree and interpreted on the fly
when a "module" (in OpenSCAD terms) is called.

The result is an OCC Solid (or sketch if 2D), wrapped with build123d,
and can be used just like any other object.


### Functional replacements

If a module cannot be implemented in build123d/OCC, most likely because it
uses ``hull`` or ``minkowsky``, often the most expedient fix is to write a
replacement in Python.

To use this feature, simply add a function with the desired name to the
environment you pass to ``process``, or pre-load a Python file.

In order to read global variables, functions may access the current
environment via the contextvar ``openscadq.env``.

## Limitations

This tool started off as a proof of concept. A lot of methods and some
support functions are not implemented yet, though the grammar itself
should be complete.

Variables whose name start with a '$' are usable. However, they cannot be
passed to functions as keywords. Instead, $-prefixed keywords get passed to
called functions in the environment so that functions implemented in Python
don't have to deal with them.

Corollary: Don't even think of creating a six-sided polygon by using
``circle(r=2, $fn=6``) with this code.

Speed could probably be improved; on the other hand, let's face it,
OpenSCAD's mesh rendering can be slow as molasses too.

The ``minkowski`` and ``hull`` operators don't exist in build123d.
Implementing them is *way* out of scope for this project.

``undef`` is evaluated as ``None``.


## Differences to OpenSCAD

### Evaluation Order

Our parser delays evaluation of variables until they're needed.

In other words, this …

::
	bar = foo(123);
	function foo(x) = x;

… works just fine.


### Variable handling

Unknown variables (i.e. those that are never assigned to) cause an error.
As in OpenSCAD, unfilled parameters are "undef", i.e.

	function xx(a,b) = b;
	echo(xx(1));

does emit "ECHO: undef".


### Value redefinition

Updating a variable will emit a warning but not change the value.


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
* by Python code

The test builder calls the ``work`` function (Python) / module (OpenSCAD).
If that doesn't exist, top-level objects (OpenScad) / variables (Python) are used.

The following special constants are recognized:

* tolerance

  The maximum difference (volume) between the various models. The default
  is 0.001 but anything that depends on OpenSCAD's ``$fn`` probably
  requires looser constraints.

* volume

  The volume (in mm³) that the model is supposed to have.

* skip

  Skip this test when auto-running.

* no\_add

  When set to `True`, do not add the various volumes. This is a workaround
  for an OCC bug which causes an endless loop.

  Setting this flag causes this testcase to only compare volumes and bounding
  boxes, which is not as accurate.

* trace

  Log (some) calls to build123.

If the Python part only contains constants, it must declare `work=None`.
Otherwise the test code assumes that you wrote e.g. ``Sphere(42)`` without
assigning the result to anything, and thus refuses to accept the testcase.

If you want to test a functional result against OpenSCAD, the best way is
to create a `Box(result,1,1)` object.


### Viewing tests

``examples/test_viewer.py`` can be opened with CQ-Editor to compare models
visually.

### Test Traces

If the testcase sets ``trace=True``, the actual `build123d` calls will be
logged and the STL file from OpenSCAD will not be deleted.

This is mainly useful for generating a test case for bug reports that
doesn't depend on this code.

Trace support is still somewhat incomplete.

## TODO

To fix:
* linear\_extrude with scaling
* linear\_extrude with scaling and twist
* polyhedrons
* use/include from a library (via envvar OPENSCADPATH)

Implement a lot of functions.

Improve error reporting.

Test working with 2D.

An option to generate a build123d script instead of the actual objects would
be nice.
